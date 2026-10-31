"""Synthetic authenticated actors for the fiscal endpoint regression fixtures."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import inspect, select

from app.models.user import User
from app.core.tenant import TenantContext
from app.models.fiscal_configuration import FiscalPolicy, FiscalSeries
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.sale_fiscal import FiscalIssuer
from app.models.tenant import Tenant


def context_for(actor):
    return TenantContext(tenant_id=actor.tenant_id, user_id=actor.id, user_email=actor.email,
                         user_full_name=actor.full_name, role=actor.role)


def seed_fiscal_case(db, *, tenant_id=None, total="100.00", payment_amount="100.00",
                     payment_type="bank_transfer", currency="ARS", point_of_sale=1):
    """A wholly synthetic service sale; usable with SQLite or an isolated PG schema."""
    suffix = uuid.uuid4().hex
    if tenant_id is None:
        tenant = Tenant(id=uuid.uuid4(), name="ARCA.1 synthetic clinic")
        db.add(tenant)
        db.flush()
        tenant_id = tenant.id
    actors = {}
    for role in ("clinic_admin", "contador", "medico_veterinario", "secretaria", "superadmin"):
        actor = User(id=uuid.uuid4(), tenant_id=tenant_id, email=f"arca1-{role}-{suffix}@example.com",
                     full_name=f"Synthetic {role}", role=role, is_active=True)
        db.add(actor)
        actors[role] = actor
    db.flush()
    issuer = FiscalIssuer(
        tenant_id=tenant_id, user_id=actors["medico_veterinario"].id,
        display_name="Synthetic fiscal issuer", tax_id="20123456786", cuit="20123456786",
        legal_name="Synthetic fiscal issuer", tax_condition="monotributo", is_active=True,
        can_issue_service_receipt_c=True, service_document_type="receipt_c", service_document_code="015",
        can_issue_product_invoice_c=False,
    )
    db.add(issuer)
    db.flush()
    series = FiscalSeries(
        tenant_id=tenant_id, fiscal_issuer_id=issuer.id, cuit_snapshot=issuer.cuit,
        environment="homologation", point_of_sale=point_of_sale, document_type="receipt_c", concept=2,
        authorization_mode="CAE", is_active=True, credential_reference="opaque://test/credential",
        created_by_user_id=actors["clinic_admin"].id, updated_by_user_id=actors["clinic_admin"].id,
    )
    policy = db.scalar(select(FiscalPolicy).where(FiscalPolicy.tenant_id == tenant_id))
    if policy is None:
        policy = FiscalPolicy(tenant_id=tenant_id, enabled=True, payment_scope="electronic_only")
        db.add(policy)
    method = PaymentMethod(
        tenant_id=tenant_id, label=f"Synthetic transfer {suffix}", normalized_label=f"synthetic-{suffix}",
        type=payment_type, is_active=True, sort_order=0, operational_reference="Synthetic account",
        suggested_fiscal_issuer_id=issuer.id,
    )
    sale = Sale(
        tenant_id=tenant_id, sale_date=date(2026, 10, 20), currency=currency,
        subtotal_ars=Decimal(total), discount_total_ars=Decimal("0"), total_ars=Decimal(total),
        status="confirmed", confirmed_at=datetime.now(UTC), confirmed_by_user_id=actors["clinic_admin"].id,
    )
    sale.items.append(SaleItem(
        tenant_id=tenant_id, line_type="service", description_snapshot="Synthetic veterinary service",
        unit_snapshot="unit", quantity=Decimal("1"), unit_price_ars=Decimal(total),
        discount_percentage=Decimal("0"), line_subtotal_ars=Decimal(total), line_discount_ars=Decimal("0"),
        line_total_ars=Decimal(total), line_order=1,
    ))
    db.add_all([series, method, sale])
    db.flush()
    payment = SalePayment(
        tenant_id=tenant_id, sale_id=sale.id, payment_method_id=method.id,
        payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type,
        amount_ars=Decimal(payment_amount), received_at=datetime.now(UTC), is_active=True,
        created_by_user_id=actors["clinic_admin"].id,
    )
    db.add(payment)
    db.commit()
    return SimpleNamespace(
        tenant_id=tenant_id, sale_id=sale.id, payment_id=payment.id, method_id=method.id,
        issuer_id=issuer.id, series_id=series.id, actors=actors,
        context=context_for(actors["clinic_admin"]),
        tenant=db.scalar(select(Tenant).where(Tenant.id == tenant_id)),
    )


def fiscal_admin_headers(tenant):
    db = inspect(tenant).session
    assert db is not None
    email = f"fiscal-admin-{tenant.id.hex}@example.com"
    actor = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
    if actor is None:
        actor = User(id=uuid.uuid4(), tenant_id=tenant.id, email=email,
                     full_name="Fiscal test administrator", role="clinic_admin", is_active=True)
        db.add(actor)
        db.commit()
    return {"X-User-Email": email}
