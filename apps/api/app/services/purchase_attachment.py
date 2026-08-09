from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.purchase_attachment import PurchaseAttachment
from app.repositories.purchase import PurchaseRepository
from app.repositories.purchase_attachment import PurchaseAttachmentRepository
from app.repositories.user import UserRepository
from app.services.storage import ObjectStorageService


logger = logging.getLogger(__name__)

MAX_PURCHASE_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
ATTACHABLE_PURCHASE_STATUSES = {"draft", "received", "reversed", "cancelled"}
CONTENT_TYPES_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
CANONICAL_EXTENSION_BY_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class PurchaseAttachmentService:
    def __init__(self, db: Session, storage: ObjectStorageService) -> None:
        self.db = db
        self.storage = storage
        self.purchase_repository = PurchaseRepository(db)
        self.attachment_repository = PurchaseAttachmentRepository(db)
        self.user_repository = UserRepository(db)

    def attach(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        filename: str | None,
        declared_content_type: str | None,
        content: bytes,
        uploaded_by_user_id: uuid.UUID | None,
    ) -> tuple[PurchaseAttachment, bool]:
        self._validate_optional_user(tenant_id, uploaded_by_user_id)
        purchase = self.purchase_repository.get_by_id(
            tenant_id, purchase_id, for_update=True
        )
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        if purchase.status not in ATTACHABLE_PURCHASE_STATUSES:
            raise AppError(
                409,
                "purchase_attachment_status_not_allowed",
                "El estado actual de la compra no permite adjuntar un comprobante",
            )

        safe_filename, content_type, canonical_extension = self.validate_document_file(
            filename=filename,
            declared_content_type=declared_content_type,
            content=content,
        )
        digest = hashlib.sha256(content).hexdigest()
        active = self.attachment_repository.get_active(
            tenant_id, purchase_id, for_update=True
        )
        if active is not None and active.sha256 == digest:
            return active, True

        attachment_id = uuid.uuid4()
        storage_key = (
            f"tenants/{tenant_id}/purchases/{purchase_id}/attachments/"
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

            attachment = PurchaseAttachment(
                id=attachment_id,
                tenant_id=tenant_id,
                purchase_id=purchase_id,
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
                    "purchase_attachment_persistence_failed",
                    "El comprobante no pudo registrarse; no se modificó el comprobante anterior",
                ) from exc
            raise AppError(
                502,
                "purchase_attachment_upload_failed",
                "El comprobante no pudo almacenarse; la compra se conserva sin cambios",
            ) from exc

        resolved = self.attachment_repository.get_active(tenant_id, purchase_id)
        if resolved is None:
            raise AppError(
                500,
                "purchase_attachment_persistence_failed",
                "El comprobante almacenado no pudo recuperarse",
            )
        return resolved, False

    def download(
        self, tenant_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> tuple[PurchaseAttachment, bytes]:
        purchase = self.purchase_repository.get_by_id(tenant_id, purchase_id)
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        attachment = self.attachment_repository.get_active(tenant_id, purchase_id)
        if attachment is None:
            raise AppError(
                404,
                "purchase_attachment_not_found",
                "La compra no tiene un comprobante adjunto",
            )
        expected_prefix = f"tenants/{tenant_id}/purchases/{purchase_id}/attachments/"
        if not attachment.storage_key.startswith(expected_prefix):
            raise AppError(
                409,
                "purchase_attachment_storage_mismatch",
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
                "purchase_attachment_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        except Exception as exc:
            raise AppError(
                502,
                "purchase_attachment_download_failed",
                "El comprobante no está disponible temporalmente",
            ) from exc
        if hashlib.sha256(content).hexdigest() != attachment.sha256:
            raise AppError(
                409,
                "purchase_attachment_integrity_error",
                "El comprobante almacenado no supera la verificación de integridad",
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

    @classmethod
    def validate_document_file(
        cls,
        *,
        filename: str | None,
        declared_content_type: str | None,
        content: bytes,
    ) -> tuple[str, str, str]:
        safe_filename = cls._sanitize_filename(filename)
        extension = Path(safe_filename).suffix.lower()
        expected_content_type = CONTENT_TYPES_BY_EXTENSION.get(extension)
        if expected_content_type is None:
            raise AppError(
                422,
                "purchase_attachment_extension_not_allowed",
                "El comprobante debe ser PDF, JPEG o PNG",
            )
        normalized_content_type = (
            (declared_content_type or "").split(";", 1)[0].strip().lower()
        )
        if normalized_content_type != expected_content_type:
            raise AppError(
                422,
                "purchase_attachment_content_type_mismatch",
                "La extensión y el tipo MIME del comprobante no coinciden",
            )
        if not content:
            raise AppError(
                422,
                "purchase_attachment_empty",
                "El comprobante no puede estar vacío",
            )
        if len(content) > MAX_PURCHASE_ATTACHMENT_SIZE_BYTES:
            raise AppError(
                413,
                "purchase_attachment_too_large",
                "El comprobante supera el máximo de 10 MB",
            )
        if not cls._matches_magic(expected_content_type, content):
            raise AppError(
                422,
                "purchase_attachment_signature_mismatch",
                "El contenido del archivo no corresponde a un PDF, JPEG o PNG válido",
            )
        return (
            safe_filename,
            expected_content_type,
            CANONICAL_EXTENSION_BY_CONTENT_TYPE[expected_content_type],
        )

    @staticmethod
    def _sanitize_filename(filename: str | None) -> str:
        leaf = Path((filename or "").replace("\\", "/")).name.strip()
        leaf = "".join(character for character in leaf if character.isprintable())
        leaf = re.sub(r"[^\w .()\-]", "_", leaf, flags=re.UNICODE)
        leaf = re.sub(r"\s+", " ", leaf).strip(" .")
        if not leaf:
            raise AppError(
                422,
                "purchase_attachment_filename_required",
                "El comprobante requiere un nombre de archivo",
            )
        extension = Path(leaf).suffix
        stem = leaf[: -len(extension)] if extension else leaf
        max_stem_length = max(1, 255 - len(extension))
        return f"{stem[:max_stem_length]}{extension}"

    @staticmethod
    def _matches_magic(content_type: str, content: bytes) -> bool:
        if content_type == "application/pdf":
            return content.startswith(b"%PDF-")
        if content_type == "image/jpeg":
            return content.startswith(b"\xff\xd8\xff")
        if content_type == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        return False

    def _compensate_upload(self, bucket_name: str, storage_key: str) -> None:
        try:
            self.storage.delete_clinical_file(
                bucket_name=bucket_name,
                object_path=storage_key,
            )
        except Exception:
            logger.exception(
                "Could not remove an orphaned purchase attachment object",
                extra={"storage_key": storage_key},
            )
