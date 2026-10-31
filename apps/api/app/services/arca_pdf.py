"""Render only frozen, authorized WSFE business snapshots; no database or network.

QR specification consulted 2026-10-20:
https://www.afip.gob.ar/fe/qr/documentos/QRespecificaciones.pdf (version 1).
The normative URL in its technical table is https://www.arca.gob.ar/fe/qr/;
the older AFIP URL in the example is intentionally not used.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.schemas.fiscal_issuer import normalize_cuit


QR_BASE_URL = "https://www.arca.gob.ar/fe/qr/"
QR_ASSET_URL = "vetflow-qr://authorized/current.svg"
TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"
MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class AuthorizedPdfArtifact:
    pdf_bytes: bytes
    qr_url: str
    sha256: str


def _decimal(value, *, places=2) -> Decimal:
    try:
        result = Decimal(str(value))
        quantum = Decimal(1).scaleb(-places)
        if not result.is_finite() or result < 0 or result != result.quantize(quantum):
            raise ValueError("Importe fiscal inválido")
        return result.quantize(quantum)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Importe fiscal inválido") from exc


def _integer(value, *, minimum=0, maximum=10**20 - 1) -> int:
    text = str(value)
    if not text.isascii() or not text.isdecimal():
        raise ValueError("Identificador fiscal inválido")
    result = int(text)
    if not minimum <= result <= maximum:
        raise ValueError("Identificador fiscal fuera de rango")
    return result


def _iso_date(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _numeric_json(value) -> str:
    """Emit Decimal as exact JSON number lexemes, never as floats or strings."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Número QR inválido")
        return format(value, "f")
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key) + ":" + _numeric_json(item) for key, item in value.items()) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def build_authorized_qr_url(snapshot: dict, authorization: dict, environment: str) -> str:
    if environment not in {"homologation", "production"} or snapshot.get("environment") != environment:
        raise ValueError("El ambiente del comprobante autorizado no puede cambiar")
    number = _integer(authorization.get("number"), minimum=1, maximum=99999999)
    if snapshot.get("number") is None or _integer(snapshot["number"], minimum=1, maximum=99999999) != number:
        raise ValueError("El número autorizado no coincide con el snapshot")
    cae = str(authorization.get("cae", ""))
    if len(cae) != 14:
        raise ValueError("Se requiere un CAE autorizado de 14 dígitos")
    expiry = _iso_date(authorization.get("cae_expiry"))
    voucher_date = _iso_date(snapshot["voucher_date"])
    if expiry < voucher_date:
        raise ValueError("El vencimiento del CAE no puede ser anterior al comprobante")
    cuit = str(snapshot["issuer"]["cuit"])
    if len(cuit) != 11 or normalize_cuit(cuit) != cuit:
        raise ValueError("CUIT autorizado inválido")
    if snapshot.get("currency") != "PES" or _decimal(snapshot.get("exchange_rate"), places=6) != Decimal(1):
        raise ValueError("El alcance de este comprobante exige pesos y cotización uno")
    document_type = _integer(snapshot["document_type"])
    if document_type not in {11, 15}:
        raise ValueError("Tipo de comprobante fuera del alcance CAE C")
    total = _decimal(snapshot["total"])
    if total <= 0 or total > Decimal("9999999999999.99"):
        raise ValueError("Importe QR fuera de rango")
    receiver = snapshot["receiver"]
    payload = {
        "ver": 1,
        "fecha": voucher_date,
        "cuit": _integer(cuit, minimum=10000000000, maximum=99999999999),
        "ptoVta": _integer(snapshot["point_of_sale"], minimum=1, maximum=99999),
        "tipoCmp": document_type,
        "nroCmp": number,
        "importe": total,
        "moneda": "PES",
        "ctz": _decimal(snapshot["exchange_rate"], places=6),
        "tipoDocRec": _integer(receiver["document_type"], maximum=99),
        "nroDocRec": _integer(receiver["document_number"]),
        "tipoCodAut": "E",
        "codAut": _integer(cae, minimum=10000000000000, maximum=99999999999999),
    }
    encoded = base64.b64encode(_numeric_json(payload).encode("utf-8")).decode("ascii")
    return QR_BASE_URL + "?" + urlencode({"p": encoded})


def _qr_svg_data_uri(qr_url: str) -> str:
    import qrcode
    from qrcode.image.svg import SvgPathImage

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image(image_factory=SvgPathImage).save(output)
    return "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _controlled_qr_fetcher(qr_data_uri: str):
    from weasyprint.urls import URLFetcher, URLFetcherResponse

    prefix = "data:image/svg+xml;base64,"
    if not qr_data_uri.startswith(prefix):
        raise ValueError("El recurso QR generado tiene un formato inválido")
    svg_bytes = base64.b64decode(qr_data_uri[len(prefix):], validate=True)

    class ControlledQrFetcher(URLFetcher):
        def __init__(self):
            # URLFetcher.__call__ invokes our fetch method in WeasyPrint 69.
            # Resolve only the generated bytes in memory. The stable private
            # alias prevents data/identity-bearing URLs appearing in image logs.
            super().__init__(allowed_protocols={"vetflow-qr"}, allow_redirects=False, fail_on_errors=True)
            self.loaded_qr = False

        def fetch(self, url, headers=None):
            if url != QR_ASSET_URL:
                raise ValueError("Sólo se admite el QR generado para este comprobante")
            self.loaded_qr = True
            return URLFetcherResponse(QR_ASSET_URL, body=svg_bytes, headers={"Content-Type": "image/svg+xml"})

    return ControlledQrFetcher()


class _RequiredQrImage:
    """Use WeasyPrint 69's SVG draw path without its silent-error fallback.

    The pinned renderer otherwise catches SVG drawing exceptions and writes a
    valid PDF with an empty QR. The image protocol and private SVG call below
    match that pinned version and are covered by real drawing tests.
    """

    def __init__(self, image):
        self.image = image
        self.drawn_count = 0

    def get_intrinsic_size(self, image_resolution, font_size):
        return self.image.get_intrinsic_size(image_resolution, font_size)

    def draw(self, stream, concrete_width, concrete_height, _style):
        try:
            self.image._svg.draw(stream, concrete_width, concrete_height, self.image._base_url, self.image._context)
        except Exception:
            raise ValueError("No se pudo dibujar el QR obligatorio del comprobante") from None
        self.drawn_count += 1


def _require_qr_in_layout(document, fetcher):
    from weasyprint.formatting_structure.boxes import ReplacedBox
    from weasyprint.images import SVGImage

    qr_boxes = [
        box for page in document.pages for box in page._page_box.descendants()
        if isinstance(box, ReplacedBox) and box.element is not None
        and box.element.tag == "img" and box.element.get("src") == QR_ASSET_URL
    ]
    if not fetcher.loaded_qr or len(qr_boxes) != 1:
        raise ValueError("El PDF debe representar exactamente un QR obligatorio")
    box = qr_boxes[0]
    if not isinstance(box.replacement, SVGImage) or box.width <= 0 or box.height <= 0:
        raise ValueError("El QR no tiene una imagen visible válida")
    required_image = _RequiredQrImage(box.replacement)
    box.replacement = required_image
    return required_image


def render_authorized_html(snapshot: dict, authorization: dict, environment: str) -> tuple[str, str, str]:
    qr_url = build_authorized_qr_url(snapshot, authorization, environment)
    total = _decimal(snapshot["total"])
    if _decimal(snapshot["net_amount"]) != total:
        raise ValueError("Un comprobante C no discrimina IVA ni importes ajenos al total")
    if any(_decimal(snapshot.get(key, "0.00")) != 0 for key in ("non_taxed_amount", "exempt_amount", "tax_amount", "vat_amount")):
        raise ValueError("El comprobante C no admite discriminación de IVA o tributos adicionales")
    lines = snapshot.get("lines")
    if not isinstance(lines, list) or not lines:
        raise ValueError("El snapshot debe incluir la porción documentada")
    if len(lines) > 200:
        raise ValueError("Demasiadas líneas en el comprobante")
    normalized_lines = []
    for line in lines:
        description = str(line["description"])
        if not description.strip() or len(description) > 4000:
            raise ValueError("Descripción fiscal inválida")
        quantity = _decimal(line["quantity"], places=6)
        unit_price = _decimal(line["unit_price"], places=6)
        line_total = _decimal(line["total"])
        if quantity <= 0 or (quantity * unit_price).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP) != line_total:
            raise ValueError("El detalle fiscal no cierra al centavo")
        normalized_lines.append({"description": description, "quantity": format(quantity.normalize(), "f"), "unit_price": unit_price, "total": line_total})
    if sum((line["total"] for line in normalized_lines), Decimal("0.00")) != total:
        raise ValueError("Los detalles deben cerrar con la porción documentada")
    qr_data_uri = _qr_svg_data_uri(qr_url)
    template_environment = Environment(loader=FileSystemLoader(TEMPLATE_DIRECTORY), autoescape=select_autoescape(["html", "xml"]), undefined=StrictUndefined)
    template_environment.filters["money"] = lambda value: format(_decimal(value), ".2f")
    template_environment.filters["unitmoney"] = lambda value: format(value.normalize(), "f") if value != value.quantize(MONEY_QUANTUM) else format(value, ".2f")
    html = template_environment.get_template("arca_invoice.html").render(
        invoice=snapshot, authorization=authorization, lines=normalized_lines, total=total,
        cae_expiry=_iso_date(authorization["cae_expiry"]), voucher_date=_iso_date(snapshot["voucher_date"]),
        number=f'{int(snapshot["point_of_sale"]):05d}-{int(authorization["number"]):08d}',
        document_label="FACTURA C" if snapshot["document_type"] == 11 else "RECIBO C",
        document_code=f'{int(snapshot["document_type"]):03d}', qr_asset_url=QR_ASSET_URL,
        is_homologation=environment == "homologation",
    )
    return html, qr_url, qr_data_uri


def render_authorized_pdf(snapshot: dict, authorization: dict, environment: str) -> AuthorizedPdfArtifact:
    html, qr_url, qr_data_uri = render_authorized_html(snapshot, authorization, environment)
    from weasyprint import HTML

    fetcher = _controlled_qr_fetcher(qr_data_uri)
    document = HTML(string=html, url_fetcher=fetcher).render()
    qr_image = _require_qr_in_layout(document, fetcher)
    content = document.write_pdf()
    if qr_image.drawn_count != 1:
        raise ValueError("El PDF no dibujó el QR obligatorio del comprobante")
    if not content.startswith(b"%PDF-") or len(content) < 1000:
        raise ValueError("El renderizador no produjo un PDF válido")
    return AuthorizedPdfArtifact(pdf_bytes=content, qr_url=qr_url, sha256=hashlib.sha256(content).hexdigest())
