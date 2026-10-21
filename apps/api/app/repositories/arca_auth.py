from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.arca_auth import ArcaAuthCache, ArcaTenantTicketGrant


class ArcaAuthRepository:
    """Protected server coordination; only use after CredentialRegistry.authorize.

    These global operations are intentionally named and never accept a tenant
    selected by an HTTP caller. They do not expose fiscal records cross-tenant.
    """
    def __init__(self, db: Session):
        self.db = db

    def lock_global_auth_scope(self, cache_key: str, **identity) -> ArcaAuthCache:
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError("Unsupported fiscal authentication database")
        # Both exact scope retries and conflicting scopes of the same remote
        # certificate identity converge atomically without leaking their owner.
        self.db.execute(insert(ArcaAuthCache).values(id=uuid.uuid4(), cache_key=cache_key, state="idle", fence=0, **identity).on_conflict_do_nothing())
        row = self.db.scalar(select(ArcaAuthCache).where(ArcaAuthCache.cache_key == cache_key).with_for_update().execution_options(populate_existing=True))
        if row is None:
            raise AppError(409, "arca_auth_scope_conflict", "La identidad de autenticación requiere una configuración de ámbito coherente en el servidor")
        return row

    def get_tenant_grant(self, tenant_id, reference, environment, represented_cuit):
        return self.db.scalar(select(ArcaTenantTicketGrant).where(ArcaTenantTicketGrant.tenant_id == tenant_id, ArcaTenantTicketGrant.reference == reference, ArcaTenantTicketGrant.environment == environment, ArcaTenantTicketGrant.represented_cuit == represented_cuit).with_for_update().execution_options(populate_existing=True))

    def publish_global_ticket(self, cache_id, owner, fence, now: datetime, **values) -> bool:
        result = self.db.execute(update(ArcaAuthCache).where(ArcaAuthCache.id == cache_id, ArcaAuthCache.state == "renewing", ArcaAuthCache.lease_owner == owner, ArcaAuthCache.fence == fence, ArcaAuthCache.lease_expires_at > now).values(**values, lease_owner=None, lease_expires_at=None).execution_options(synchronize_session=False))
        return result.rowcount == 1

    def fail_global_claim(self, cache_id, owner, fence, **values) -> bool:
        result = self.db.execute(update(ArcaAuthCache).where(ArcaAuthCache.id == cache_id, ArcaAuthCache.state == "renewing", ArcaAuthCache.lease_owner == owner, ArcaAuthCache.fence == fence).values(**values, lease_owner=None, lease_expires_at=None).execution_options(synchronize_session=False))
        return result.rowcount == 1
