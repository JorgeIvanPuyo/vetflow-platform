from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.sale_fiscal import (
    SaleFiscalDocument,
    SaleFiscalDocumentFileVersion,
)
from app.models.user import User


class SaleFiscalDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: SaleFiscalDocument) -> SaleFiscalDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def save(self, document: SaleFiscalDocument) -> SaleFiscalDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def create_file_version(
        self, version: SaleFiscalDocumentFileVersion
    ) -> SaleFiscalDocumentFileVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_active(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SaleFiscalDocument | None:
        statement = (
            select(SaleFiscalDocument)
            .where(
                SaleFiscalDocument.tenant_id == tenant_id,
                SaleFiscalDocument.sale_id == sale_id,
                SaleFiscalDocument.is_active.is_(True),
            )
            .options(
                selectinload(
                    SaleFiscalDocument.uploaded_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
                selectinload(
                    SaleFiscalDocument.file_history.and_(
                        SaleFiscalDocumentFileVersion.tenant_id == tenant_id
                    )
                ).selectinload(
                    SaleFiscalDocumentFileVersion.replaced_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_duplicate(
        self,
        tenant_id: uuid.UUID,
        issuer_id: uuid.UUID,
        document_type: str,
        document_number: str,
        *,
        exclude_document_id: uuid.UUID | None = None,
    ) -> SaleFiscalDocument | None:
        filters = [
            SaleFiscalDocument.tenant_id == tenant_id,
            SaleFiscalDocument.fiscal_issuer_id == issuer_id,
            SaleFiscalDocument.document_type == document_type,
            SaleFiscalDocument.document_number == document_number,
        ]
        if exclude_document_id is not None:
            filters.append(SaleFiscalDocument.id != exclude_document_id)
        return self.db.scalar(select(SaleFiscalDocument).where(*filters))
