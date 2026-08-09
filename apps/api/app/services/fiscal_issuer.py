from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.sale_fiscal import FiscalIssuer
from app.repositories.fiscal_issuer import FiscalIssuerRepository
from app.repositories.user import UserRepository
from app.schemas.fiscal_issuer import FiscalIssuerCreate, FiscalIssuerUpdate


class FiscalIssuerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FiscalIssuerRepository(db)
        self.user_repository = UserRepository(db)

    def create(
        self, tenant_id: uuid.UUID, payload: FiscalIssuerCreate
    ) -> FiscalIssuer:
        self._require_user(tenant_id, payload.user_id)
        if self.repository.get_by_user(tenant_id, payload.user_id) is not None:
            raise AppError(
                409,
                "fiscal_issuer_user_duplicate",
                "El usuario ya tiene una configuración fiscal en esta clínica",
            )
        issuer = FiscalIssuer(tenant_id=tenant_id, **payload.model_dump())
        try:
            self.repository.create(issuer)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "fiscal_issuer_user_duplicate",
                "El usuario ya tiene una configuración fiscal en esta clínica",
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, issuer.id)

    def list(
        self, tenant_id: uuid.UUID, *, active_only: bool = False
    ) -> list[FiscalIssuer]:
        return self.repository.list(tenant_id, active_only=active_only)

    def get(self, tenant_id: uuid.UUID, issuer_id: uuid.UUID) -> FiscalIssuer:
        issuer = self.repository.get_by_id(tenant_id, issuer_id)
        if issuer is None:
            raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
        return issuer

    def update(
        self,
        tenant_id: uuid.UUID,
        issuer_id: uuid.UUID,
        payload: FiscalIssuerUpdate,
    ) -> FiscalIssuer:
        try:
            issuer = self.repository.get_by_id(
                tenant_id, issuer_id, for_update=True
            )
            if issuer is None:
                raise AppError(
                    404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado"
                )
            changes = payload.model_dump(exclude_unset=True)
            candidate = {
                "user_id": issuer.user_id,
                "display_name": issuer.display_name,
                "tax_id": issuer.tax_id,
                "is_active": issuer.is_active,
                "can_issue_service_receipt_c": issuer.can_issue_service_receipt_c,
                "can_issue_product_invoice_c": issuer.can_issue_product_invoice_c,
                "service_document_type": issuer.service_document_type,
                "service_document_code": issuer.service_document_code,
                "product_document_type": issuer.product_document_type,
                "product_document_code": issuer.product_document_code,
                **changes,
            }
            if candidate["user_id"] is None:
                raise AppError(422, "validation_error", "El usuario es obligatorio")
            if not candidate["can_issue_service_receipt_c"]:
                candidate["service_document_type"] = None
                candidate["service_document_code"] = None
            if not candidate["can_issue_product_invoice_c"]:
                candidate["product_document_type"] = None
                candidate["product_document_code"] = None
            try:
                validated = FiscalIssuerCreate.model_validate(candidate)
            except ValueError as exc:
                raise AppError(
                    422, "fiscal_issuer_invalid_configuration", str(exc)
                ) from exc
            self._require_user(tenant_id, validated.user_id)
            duplicate = self.repository.get_by_user(tenant_id, validated.user_id)
            if duplicate is not None and duplicate.id != issuer.id:
                raise AppError(
                    409,
                    "fiscal_issuer_user_duplicate",
                    "El usuario ya tiene una configuración fiscal en esta clínica",
                )
            for field, value in validated.model_dump().items():
                setattr(issuer, field, value)
            issuer.updated_at = datetime.now(UTC)
            self.repository.save(issuer)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "fiscal_issuer_user_duplicate",
                "El usuario ya tiene una configuración fiscal en esta clínica",
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, issuer_id)

    def _require_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")
