from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.purchase_return import PurchaseReturnAttachment
from app.repositories.purchase_return import (
    PurchaseReturnAttachmentRepository,
    PurchaseReturnRepository,
)
from app.repositories.user import UserRepository
from app.services.purchase_attachment import PurchaseAttachmentService
from app.services.storage import ObjectStorageService


logger = logging.getLogger(__name__)
MAX_PURCHASE_RETURN_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
ATTACHABLE_RETURN_STATUSES = {"draft", "confirmed", "cancelled"}


class PurchaseReturnAttachmentService:
    def __init__(self, db: Session, storage: ObjectStorageService) -> None:
        self.db = db
        self.storage = storage
        self.return_repository = PurchaseReturnRepository(db)
        self.attachment_repository = PurchaseReturnAttachmentRepository(db)
        self.user_repository = UserRepository(db)

    def attach(
        self,
        tenant_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        filename: str | None,
        declared_content_type: str | None,
        content: bytes,
        uploaded_by_user_id: uuid.UUID | None,
    ) -> tuple[PurchaseReturnAttachment, bool]:
        self._validate_optional_user(tenant_id, uploaded_by_user_id)
        purchase_return = self.return_repository.get_by_id(
            tenant_id, return_id, for_update=True
        )
        if purchase_return is None:
            raise AppError(
                404, "purchase_return_not_found", "Devolución no encontrada"
            )
        if purchase_return.status not in ATTACHABLE_RETURN_STATUSES:
            raise AppError(
                409,
                "purchase_return_attachment_status_not_allowed",
                "El estado actual no permite adjuntar un comprobante",
            )

        safe_filename, content_type, canonical_extension = (
            PurchaseAttachmentService.validate_document_file(
                filename=filename,
                declared_content_type=declared_content_type,
                content=content,
            )
        )
        digest = hashlib.sha256(content).hexdigest()
        active = self.attachment_repository.get_active(
            tenant_id, return_id, for_update=True
        )
        if active is not None and active.sha256 == digest:
            return active, True

        attachment_id = uuid.uuid4()
        storage_key = (
            f"tenants/{tenant_id}/purchase-returns/{return_id}/attachments/"
            f"{attachment_id}/document{canonical_extension}"
        )
        bucket_name = self.storage.bucket_name
        if not bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "El almacenamiento privado de comprobantes no está configurado",
            )

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
            if active is not None:
                active.is_active = False
                active.replaced_at = now
                active.replaced_by_user_id = uploaded_by_user_id
                active.updated_at = now
                self.attachment_repository.save(active)

            attachment = PurchaseReturnAttachment(
                id=attachment_id,
                tenant_id=tenant_id,
                purchase_return_id=return_id,
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
            self.attachment_repository.create(attachment)
            self.db.commit()
        except AppError:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            raise
        except Exception as exc:
            self.db.rollback()
            if upload_attempted:
                self._compensate_upload(bucket_name, storage_key)
            if uploaded:
                raise AppError(
                    500,
                    "purchase_return_attachment_persistence_failed",
                    "El comprobante no pudo registrarse; se conservó el anterior",
                ) from exc
            raise AppError(
                502,
                "purchase_return_attachment_upload_failed",
                "El comprobante no pudo almacenarse",
            ) from exc

        resolved = self.attachment_repository.get_active(tenant_id, return_id)
        if resolved is None:
            raise AppError(
                500,
                "purchase_return_attachment_persistence_failed",
                "El comprobante almacenado no pudo recuperarse",
            )
        return resolved, False

    def download(
        self, tenant_id: uuid.UUID, return_id: uuid.UUID
    ) -> tuple[PurchaseReturnAttachment, bytes]:
        purchase_return = self.return_repository.get_by_id(tenant_id, return_id)
        if purchase_return is None:
            raise AppError(
                404, "purchase_return_not_found", "Devolución no encontrada"
            )
        attachment = self.attachment_repository.get_active(tenant_id, return_id)
        if attachment is None:
            raise AppError(
                404,
                "purchase_return_attachment_not_found",
                "La devolución no tiene un comprobante adjunto",
            )
        expected_prefix = (
            f"tenants/{tenant_id}/purchase-returns/{return_id}/attachments/"
        )
        if not attachment.storage_key.startswith(expected_prefix):
            raise AppError(
                409,
                "purchase_return_attachment_storage_mismatch",
                "La referencia privada del comprobante es inconsistente",
            )
        try:
            content = self.storage.download_object_bytes(
                bucket_name=attachment.bucket_name,
                object_path=attachment.storage_key,
            )
        except AppError as exc:
            if exc.code == "storage_not_configured":
                raise
            raise AppError(
                502,
                "purchase_return_attachment_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        except Exception as exc:
            raise AppError(
                502,
                "purchase_return_attachment_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        if hashlib.sha256(content).hexdigest() != attachment.sha256:
            raise AppError(
                409,
                "purchase_return_attachment_integrity_error",
                "El comprobante no supera la verificación de integridad",
            )
        return attachment, content

    def _validate_optional_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        if (
            user_id is not None
            and self.user_repository.get_by_id(tenant_id, user_id) is None
        ):
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    def _compensate_upload(self, bucket_name: str, storage_key: str) -> None:
        try:
            self.storage.delete_clinical_file(
                bucket_name=bucket_name,
                object_path=storage_key,
            )
        except Exception:
            logger.exception(
                "Could not remove an orphaned purchase return attachment object",
                extra={"storage_key": storage_key},
            )
