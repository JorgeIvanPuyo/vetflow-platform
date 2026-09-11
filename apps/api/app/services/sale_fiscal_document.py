from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.sale import Sale
from app.models.sale_fiscal import (
    FiscalIssuer,
    SaleFiscalDocument,
    SaleFiscalDocumentFileVersion,
)
from app.repositories.fiscal_issuer import FiscalIssuerRepository
from app.repositories.sale import SaleRepository
from app.repositories.sale_fiscal_document import SaleFiscalDocumentRepository
from app.repositories.user import UserRepository
from app.services.purchase_attachment import PurchaseAttachmentService
from app.services.storage import ObjectStorageService


logger = logging.getLogger(__name__)
MAX_SALE_FISCAL_FILE_SIZE_BYTES = 10 * 1024 * 1024


class SaleFiscalDocumentService:
    def __init__(self, db: Session, storage: ObjectStorageService) -> None:
        self.db = db
        self.storage = storage
        self.sale_repository = SaleRepository(db)
        self.issuer_repository = FiscalIssuerRepository(db)
        self.document_repository = SaleFiscalDocumentRepository(db)
        self.user_repository = UserRepository(db)

    def create(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        *,
        issuer_id: uuid.UUID,
        document_type: str,
        document_code: str,
        document_number: str,
        issue_date: date,
        filename: str | None,
        declared_content_type: str | None,
        content: bytes,
        uploaded_by_user_id: uuid.UUID | None,
    ) -> SaleFiscalDocument:
        self._validate_actor(tenant_id, uploaded_by_user_id)
        sale = self._require_sale(tenant_id, sale_id, for_update=True)
        if sale.status != "confirmed":
            raise AppError(
                409,
                "sale_fiscal_document_status_not_allowed",
                "Sólo una venta confirmada puede documentarse inicialmente",
            )
        if self.document_repository.get_active(
            tenant_id, sale_id, for_update=True
        ) is not None:
            raise AppError(
                409,
                "sale_fiscal_document_already_exists",
                "La venta ya tiene un comprobante fiscal activo",
            )
        issuer = self._require_issuer(tenant_id, issuer_id, require_active=True)
        normalized_type, normalized_code, normalized_number = self._validate_identity(
            document_type, document_code, document_number
        )
        self._validate_eligibility(
            sale, issuer, normalized_type, normalized_code
        )
        self._reject_duplicate(
            tenant_id, issuer.id, normalized_type, normalized_number
        )
        safe_filename, content_type, extension = (
            PurchaseAttachmentService.validate_document_file(
                filename=filename,
                declared_content_type=declared_content_type,
                content=content,
            )
        )
        digest = hashlib.sha256(content).hexdigest()
        document_id = uuid.uuid4()
        storage_key = self._storage_key(
            tenant_id, sale_id, document_id, uuid.uuid4(), extension
        )
        bucket_name = self._require_bucket()
        upload_attempted = False
        uploaded = False
        try:
            upload_attempted = True
            self.storage.upload_clinical_file(
                object_path=storage_key,
                content=content,
                content_type=content_type,
            )
            uploaded = True
            now = datetime.now(UTC)
            document = SaleFiscalDocument(
                id=document_id,
                tenant_id=tenant_id,
                sale_id=sale_id,
                fiscal_issuer_id=issuer.id,
                issuer_user_id_snapshot=issuer.user_id,
                issuer_name_snapshot=issuer.display_name,
                issuer_tax_id_snapshot=issuer.tax_id,
                document_type=normalized_type,
                document_code=normalized_code,
                document_number=normalized_number,
                issue_date=issue_date,
                total_ars_snapshot=sale.total_ars,
                original_filename=safe_filename,
                bucket_name=bucket_name,
                storage_key=storage_key,
                content_type=content_type,
                size_bytes=len(content),
                sha256=digest,
                uploaded_by_user_id=uploaded_by_user_id,
                uploaded_at=now,
                is_active=True,
            )
            self.document_repository.create(document)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            raise AppError(
                409,
                "sale_fiscal_document_duplicate",
                "El número de comprobante ya está registrado para este emisor y tipo",
            ) from exc
        except AppError:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            raise
        except Exception as exc:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            code = (
                "sale_fiscal_document_persistence_failed"
                if uploaded
                else "sale_fiscal_document_upload_failed"
            )
            status = 500 if uploaded else 502
            raise AppError(
                status,
                code,
                "El comprobante no pudo registrarse; la venta se conserva sin cambios",
            ) from exc
        return self.get(tenant_id, sale_id)

    def get(self, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> SaleFiscalDocument:
        self._require_sale(tenant_id, sale_id)
        document = self.document_repository.get_active(tenant_id, sale_id)
        if document is None:
            raise AppError(
                404,
                "sale_fiscal_document_not_found",
                "La venta no tiene un comprobante fiscal",
            )
        return document

    def update(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        *,
        issuer_id: uuid.UUID | None,
        document_type: str | None,
        document_code: str | None,
        document_number: str | None,
        issue_date: date | None,
        filename: str | None,
        declared_content_type: str | None,
        content: bytes | None,
        updated_by_user_id: uuid.UUID | None,
    ) -> SaleFiscalDocument:
        self._validate_actor(tenant_id, updated_by_user_id)
        sale = self._require_sale(tenant_id, sale_id, for_update=True)
        document = self.document_repository.get_active(
            tenant_id, sale_id, for_update=True
        )
        if document is None:
            raise AppError(
                404,
                "sale_fiscal_document_not_found",
                "La venta no tiene un comprobante fiscal",
            )
        if sale.status not in {"confirmed", "reversed"}:
            raise AppError(
                409,
                "sale_fiscal_document_status_not_allowed",
                "El estado actual de la venta no permite corregir el comprobante",
            )
        resolved_issuer_id = issuer_id or document.fiscal_issuer_id
        issuer = self._require_issuer(
            tenant_id,
            resolved_issuer_id,
            require_active=resolved_issuer_id != document.fiscal_issuer_id,
        )
        normalized_type, normalized_code, normalized_number = self._validate_identity(
            document_type if document_type is not None else document.document_type,
            document_code if document_code is not None else document.document_code,
            document_number if document_number is not None else document.document_number,
        )
        issuer_changed = issuer.id != document.fiscal_issuer_id
        identity_changed = (
            normalized_type != document.document_type
            or normalized_code != document.document_code
        )
        if issuer_changed or identity_changed:
            self._validate_eligibility(sale, issuer, normalized_type, normalized_code)
        self._reject_duplicate(
            tenant_id,
            issuer.id,
            normalized_type,
            normalized_number,
            exclude_document_id=document.id,
        )

        new_file = None
        bucket_name = document.bucket_name
        storage_key = ""
        upload_attempted = False
        uploaded = False
        if content is not None:
            safe_filename, content_type, extension = (
                PurchaseAttachmentService.validate_document_file(
                    filename=filename,
                    declared_content_type=declared_content_type,
                    content=content,
                )
            )
            digest = hashlib.sha256(content).hexdigest()
            if digest != document.sha256:
                bucket_name = self._require_bucket()
                storage_key = self._storage_key(
                    tenant_id, sale_id, document.id, uuid.uuid4(), extension
                )
                new_file = (
                    safe_filename,
                    content_type,
                    digest,
                    len(content),
                    storage_key,
                )
        try:
            if new_file is not None and content is not None:
                upload_attempted = True
                self.storage.upload_clinical_file(
                    object_path=storage_key,
                    content=content,
                    content_type=new_file[1],
                )
                uploaded = True
            now = datetime.now(UTC)
            if new_file is not None:
                self.document_repository.create_file_version(
                    SaleFiscalDocumentFileVersion(
                        tenant_id=tenant_id,
                        fiscal_document_id=document.id,
                        original_filename=document.original_filename,
                        bucket_name=document.bucket_name,
                        storage_key=document.storage_key,
                        content_type=document.content_type,
                        size_bytes=document.size_bytes,
                        sha256=document.sha256,
                        uploaded_by_user_id=document.uploaded_by_user_id,
                        uploaded_at=document.uploaded_at,
                        replaced_at=now,
                        replaced_by_user_id=updated_by_user_id,
                    )
                )
                document.original_filename = new_file[0]
                document.content_type = new_file[1]
                document.sha256 = new_file[2]
                document.size_bytes = new_file[3]
                document.storage_key = new_file[4]
                document.bucket_name = bucket_name
                document.uploaded_by_user_id = updated_by_user_id
                document.uploaded_at = now
            document.fiscal_issuer_id = issuer.id
            if issuer_changed:
                document.issuer_user_id_snapshot = issuer.user_id
                document.issuer_name_snapshot = issuer.display_name
                document.issuer_tax_id_snapshot = issuer.tax_id
            document.document_type = normalized_type
            document.document_code = normalized_code
            document.document_number = normalized_number
            document.issue_date = issue_date or document.issue_date
            document.updated_at = now
            self.document_repository.save(document)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            raise AppError(
                409,
                "sale_fiscal_document_duplicate",
                "El número de comprobante ya está registrado para este emisor y tipo",
            ) from exc
        except AppError:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            raise
        except Exception as exc:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            code = (
                "sale_fiscal_document_persistence_failed"
                if uploaded
                else "sale_fiscal_document_upload_failed"
            )
            raise AppError(
                500 if uploaded else 502,
                code,
                "El comprobante no pudo corregirse; se conservó la versión anterior",
            ) from exc
        return self.get(tenant_id, sale_id)

    def download(
        self, tenant_id: uuid.UUID, sale_id: uuid.UUID
    ) -> tuple[SaleFiscalDocument, bytes]:
        document = self.get(tenant_id, sale_id)
        expected_prefix = f"tenants/{tenant_id}/sales/{sale_id}/fiscal-documents/"
        if not document.storage_key.startswith(expected_prefix):
            raise AppError(
                409,
                "sale_fiscal_document_storage_mismatch",
                "La referencia privada del comprobante es inconsistente",
            )
        try:
            content = self.storage.download_object_bytes(
                bucket_name=document.bucket_name,
                object_path=document.storage_key,
            )
        except AppError as exc:
            if exc.code == "storage_not_configured":
                raise
            raise AppError(
                502,
                "sale_fiscal_document_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        except Exception as exc:
            raise AppError(
                502,
                "sale_fiscal_document_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        if hashlib.sha256(content).hexdigest() != document.sha256:
            raise AppError(
                409,
                "sale_fiscal_document_integrity_error",
                "El comprobante no supera la verificación de integridad",
            )
        return document, content

    def _require_sale(
        self, tenant_id: uuid.UUID, sale_id: uuid.UUID, *, for_update: bool = False
    ) -> Sale:
        sale = self.sale_repository.get_by_id(
            tenant_id, sale_id, for_update=for_update
        )
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        return sale

    def _require_issuer(
        self, tenant_id: uuid.UUID, issuer_id: uuid.UUID, *, require_active: bool
    ) -> FiscalIssuer:
        issuer = self.issuer_repository.get_by_id(tenant_id, issuer_id)
        if issuer is None:
            raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
        if require_active and not issuer.is_active:
            raise AppError(
                409,
                "fiscal_issuer_inactive",
                "El emisor fiscal está inactivo y no puede seleccionarse",
            )
        return issuer

    def _validate_actor(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        if user_id is not None and self.user_repository.get_by_id(
            tenant_id, user_id
        ) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    @staticmethod
    def _validate_identity(
        document_type: str, document_code: str, document_number: str
    ) -> tuple[str, str, str]:
        resolved_type = document_type.strip()
        resolved_code = document_code.strip()
        resolved_number = document_number.strip()
        if resolved_type not in {"receipt_c", "invoice_c"}:
            raise AppError(422, "sale_fiscal_document_type_invalid", "Tipo fiscal inválido")
        if not resolved_code or len(resolved_code) > 20:
            raise AppError(422, "sale_fiscal_document_code_required", "El código fiscal es obligatorio")
        if not resolved_number or len(resolved_number) > 120:
            raise AppError(422, "sale_fiscal_document_number_required", "El número de comprobante es obligatorio")
        return resolved_type, resolved_code, resolved_number

    @staticmethod
    def _validate_eligibility(
        sale: Sale,
        issuer: FiscalIssuer,
        document_type: str,
        document_code: str,
    ) -> None:
        has_products = any(item.fiscal_line_type == "product" for item in sale.items)
        has_services = any(item.fiscal_line_type == "service" for item in sale.items)
        requested = (document_type, document_code)
        service_pair = (
            issuer.service_document_type,
            issuer.service_document_code,
        )
        product_pair = (
            issuer.product_document_type,
            issuer.product_document_code,
        )
        if has_products and has_services:
            if not (
                issuer.can_issue_service_receipt_c
                and issuer.can_issue_product_invoice_c
                and service_pair == product_pair
                and requested == service_pair
            ):
                raise AppError(
                    409,
                    "sale_fiscal_document_mixed_not_supported",
                    "Esta venta contiene productos y servicios y requiere una estrategia "
                    "de comprobantes separada. No puede documentarse con un único "
                    "comprobante en esta etapa.",
                )
            return
        if has_services and not (
            issuer.can_issue_service_receipt_c and requested == service_pair
        ):
            raise AppError(
                409,
                "sale_fiscal_document_service_not_allowed",
                "El emisor no está habilitado para documentar esta venta de servicios",
            )
        if has_products and not (
            issuer.can_issue_product_invoice_c and requested == product_pair
        ):
            raise AppError(
                409,
                "sale_fiscal_document_product_not_allowed",
                "El emisor no está habilitado para documentar esta venta de productos",
            )

    def _reject_duplicate(
        self,
        tenant_id: uuid.UUID,
        issuer_id: uuid.UUID,
        document_type: str,
        document_number: str,
        *,
        exclude_document_id: uuid.UUID | None = None,
    ) -> None:
        if self.document_repository.get_duplicate(
            tenant_id,
            issuer_id,
            document_type,
            document_number,
            exclude_document_id=exclude_document_id,
        ) is not None:
            raise AppError(
                409,
                "sale_fiscal_document_duplicate",
                "El número de comprobante ya está registrado para este emisor y tipo",
            )

    def _require_bucket(self) -> str:
        if not self.storage.bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "El almacenamiento privado de comprobantes no está configurado",
            )
        return self.storage.bucket_name

    @staticmethod
    def _storage_key(
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        document_id: uuid.UUID,
        file_id: uuid.UUID,
        extension: str,
    ) -> str:
        return (
            f"tenants/{tenant_id}/sales/{sale_id}/fiscal-documents/"
            f"{document_id}/{file_id}/document{extension}"
        )

    def _compensate_upload(self, bucket_name: str, storage_key: str) -> None:
        try:
            self.storage.delete_clinical_file(
                bucket_name=bucket_name, object_path=storage_key
            )
        except Exception:
            logger.exception(
                "Could not remove an orphaned sale fiscal document object",
                extra={"storage_key": storage_key},
            )
