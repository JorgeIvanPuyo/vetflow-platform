"""Frozen C-voucher business data; no transport credentials belong in this schema.

Sources checked 2026-10-20: official WSFEv1 manuals 4.8 (homologation,
history date 2026-12-01) and 4.7 (general, 2026-09-01), FECAESolicitar
request/amount/date tables and FEParamGetCondicionIvaReceptor's class-C table.
https://www.afip.gob.ar/fe/ayuda/documentos/wsfev1-RG-4291.pdf
https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf
No remembered identification-by-amount threshold is applied: identification
and consumer-final selection must be reviewed explicitly.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.fiscal_issuer import normalize_cuit


Money = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2, allow_inf_nan=False)]


class FiscalIssuerDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cuit: str
    legal_name: str = Field(min_length=1, max_length=255)
    tax_condition: str = Field(min_length=1, max_length=120)
    fiscal_address: str = Field(min_length=1, max_length=500)
    gross_income_registration: str | None = Field(default=None, min_length=1, max_length=120)
    activity_start_date: date | None = None
    fiscal_data_review_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("cuit", mode="before")
    @classmethod
    def valid_cuit(cls, value):
        normalized = normalize_cuit(value)
        if normalized is None:
            raise ValueError("Completa el CUIT del emisor")
        return normalized

    @field_validator("legal_name", "tax_condition", "fiscal_address", "gross_income_registration", "fiscal_data_review_note", mode="before")
    @classmethod
    def trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reviewed_missing_fields(self):
        if (not self.gross_income_registration or self.activity_start_date is None) and not self.fiscal_data_review_note:
            raise ValueError("Completa ingresos brutos e inicio de actividades, o documenta por qué no corresponden")
        return self


class FiscalReceiverDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_type: int = Field(ge=0, le=999)
    document_number: int = Field(ge=0, le=99999999999)
    iva_condition_id: int = Field(ge=1, le=999)
    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    consumer_final: bool

    @field_validator("name", "address", mode="before")
    @classmethod
    def trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def explicit_identification(self):
        if self.consumer_final != (self.iva_condition_id == 5):
            raise ValueError("Confirma expresamente consumidor final y su condición de IVA")
        if self.document_type == 99:
            if not self.consumer_final or self.document_number != 0:
                raise ValueError("Sin identificar requiere consumidor final explícito y documento 99/0 revisado")
        elif self.document_number == 0:
            raise ValueError("Completa el número correspondiente al tipo de documento del receptor")
        if self.document_type in {80, 86}:
            normalize_cuit(str(self.document_number))
        return self


class FiscalDisplayLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    description: str = Field(min_length=1, max_length=2000)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    unit_price: Money
    total: Money

    @field_validator("quantity", "unit_price", "total")
    @classmethod
    def canonical_decimal(cls, value):
        return value.quantize(Decimal("0.01"))

    @field_validator("description", mode="before")
    @classmethod
    def trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def consistent_amount(self):
        expected = (self.quantity * self.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if expected != self.total:
            raise ValueError("Cada detalle debe cerrar al centavo con su cantidad y precio")
        return self


class FiscalBusinessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    environment: Literal["homologation", "production"]
    issuer: FiscalIssuerDetails
    receiver: FiscalReceiverDetails
    point_of_sale: int = Field(ge=1, le=99999)
    document_type: Literal[11, 15]
    concept: Literal[1, 2, 3]
    voucher_date: date
    service_from: date | None = None
    service_to: date | None = None
    payment_due: date | None = None
    currency: Literal["PES"] = "PES"
    exchange_rate: Decimal = Field(default=Decimal("1"), ge=1, le=1, allow_inf_nan=False)
    total: Money
    net_amount: Money
    non_taxed_amount: Money = Decimal("0.00")
    exempt_amount: Money = Decimal("0.00")
    tax_amount: Money = Decimal("0.00")
    vat_amount: Money = Decimal("0.00")
    lines: tuple[FiscalDisplayLine, ...] = Field(min_length=1, max_length=200)
    number: int | None = Field(default=None, ge=1, le=99999999)

    @field_validator("total", "net_amount", "non_taxed_amount", "exempt_amount", "tax_amount", "vat_amount")
    @classmethod
    def canonical_money(cls, value):
        return value.quantize(Decimal("0.01"))

    @field_validator("exchange_rate")
    @classmethod
    def canonical_rate(cls, value):
        return value.normalize()

    @model_validator(mode="after")
    def coherent_c_voucher(self):
        if self.total <= 0 or self.total != self.net_amount:
            raise ValueError("El comprobante C debe cerrar con su subtotal, sin discriminar IVA")
        if any(value != 0 for value in (self.non_taxed_amount, self.exempt_amount, self.tax_amount, self.vat_amount)):
            raise ValueError("Este circuito C no discrimina IVA ni admite tributos adicionales sin revisión específica")
        if sum((line.total for line in self.lines), Decimal("0.00")) != self.total:
            raise ValueError("La representación del comprobante debe sumar exactamente su porción documentada")
        if self.concept in {2, 3}:
            if not all((self.service_from, self.service_to, self.payment_due)):
                raise ValueError("Servicios requieren fechas desde/hasta y vencimiento de pago")
            if self.service_to < self.service_from or self.payment_due < self.voucher_date:
                raise ValueError("Revisa las fechas del servicio y su vencimiento")
        elif any((self.service_from, self.service_to, self.payment_due)):
            raise ValueError("Las fechas de servicio sólo corresponden a conceptos 2 o 3")
        if self.issuer.activity_start_date and self.issuer.activity_start_date > self.voucher_date:
            raise ValueError("El inicio de actividades no puede ser posterior al comprobante")
        return self


class FiscalEmissionPrepare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: FiscalBusinessPayload
    confirm_fiscal_identity: Literal[True]
