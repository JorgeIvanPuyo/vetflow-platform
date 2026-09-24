import uuid
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import event

from app.core.config import get_settings
from app.models.purchase import Purchase
from app.models.purchase_attachment import PurchaseAttachment
from app.models.supplier import Supplier
from app.models.user import User
from app.services.purchase_dashboard import PurchaseDashboardService


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _create_user(db_session, tenant, *, name="Comprador", email=None) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name=name,
        email=email or f"{uuid.uuid4().hex[:8]}@example.com",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_supplier(db_session, tenant, *, name="Proveedor") -> Supplier:
    supplier = Supplier(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=name,
        normalized_name=name.casefold(),
        is_active=True,
    )
    db_session.add(supplier)
    db_session.commit()
    return supplier


def _create_purchase(
    db_session,
    tenant,
    supplier,
    *,
    purchase_date=None,
    status="draft",
    total="121.00",
    tax="21.00",
    document_type="invoice",
    document_number="FAC-1",
    user=None,
    created_at=None,
) -> Purchase:
    total_value = Decimal(total)
    tax_value = Decimal(tax)
    purchase = Purchase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        purchase_date=purchase_date or date.today(),
        document_type=document_type,
        document_number=document_number,
        currency="ARS",
        subtotal_ars=total_value - tax_value,
        tax_total_ars=tax_value,
        total_ars=total_value,
        status=status,
        created_by_user_id=user.id if user else None,
        created_at=created_at or datetime.now(UTC),
    )
    db_session.add(purchase)
    db_session.commit()
    return purchase


def _attach(db_session, tenant, purchase, user=None) -> PurchaseAttachment:
    attachment = PurchaseAttachment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        purchase_id=purchase.id,
        original_filename="factura.pdf",
        bucket_name="test-bucket",
        storage_key=f"tenants/{tenant.id}/purchases/{purchase.id}/attachment.pdf",
        content_type="application/pdf",
        size_bytes=8,
        sha256="a" * 64,
        uploaded_by_user_id=user.id if user else None,
        uploaded_at=datetime.now(UTC),
        is_active=True,
    )
    db_session.add(attachment)
    db_session.commit()
    return attachment


def _dashboard(client, tenant, **params):
    return client.get(
        "/api/v1/purchases/dashboard", headers=_headers(tenant), params=params
    )


def test_purchase_dashboard_requires_authentication(client, tenant, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/purchases/dashboard")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_default_period_is_current_calendar_month(client, tenant):
    response = _dashboard(client, tenant)

    assert response.status_code == 200
    period = response.json()["data"]["period"]
    today = date.today()
    assert period["date_from"] == today.replace(day=1).isoformat()
    assert period["date_to"] == today.replace(
        day=monthrange(today.year, today.month)[1]
    ).isoformat()


def test_summary_uses_documented_status_and_attachment_semantics(
    client, db_session, tenant
):
    supplier = _create_supplier(db_session, tenant)
    draft = _create_purchase(db_session, tenant, supplier, status="draft", total="121", tax="21")
    received = _create_purchase(
        db_session, tenant, supplier, status="received", total="242", tax="42"
    )
    _create_purchase(
        db_session, tenant, supplier, status="reversed", total="363", tax="63"
    )
    _create_purchase(
        db_session, tenant, supplier, status="cancelled", total="484", tax="84"
    )
    _attach(db_session, tenant, received)

    response = _dashboard(client, tenant)

    assert response.status_code == 200
    summary = response.json()["data"]["summary"]
    assert summary == {
        "registered_total_ars": "363.00",
        "received_total_ars": "242.00",
        "registered_tax_total_ars": "63.00",
        "received_tax_total_ars": "42.00",
        "returned_total_ars": "0.00",
        "net_received_total_ars": "242.00",
        "confirmed_return_count": 0,
        "purchase_count": 4,
        "draft_count": 1,
        "received_count": 1,
        "reversed_count": 1,
        "cancelled_count": 1,
        "attachment_pending_count": 2,
        "attachment_attached_count": 1,
    }
    assert draft.status == "draft"


def test_dashboard_is_tenant_scoped_in_summary_attention_top_and_recent(
    client, db_session, tenant, other_tenant
):
    own_supplier = _create_supplier(db_session, tenant, name="Propio")
    foreign_supplier = _create_supplier(db_session, other_tenant, name="Ajeno")
    own = _create_purchase(db_session, tenant, own_supplier, status="received", total="100")
    foreign = _create_purchase(
        db_session, other_tenant, foreign_supplier, status="received", total="9999"
    )

    data = _dashboard(client, tenant).json()["data"]

    assert data["summary"]["purchase_count"] == 1
    assert data["summary"]["received_total_ars"] == "100.00"
    assert {row["id"] for row in data["attention"]} == {str(own.id)}
    assert [row["supplier_name"] for row in data["top_suppliers"]] == ["Propio"]
    assert [row["id"] for row in data["recent_purchases"]] == [str(own.id)]
    assert str(foreign.id) not in str(data)


def test_dashboard_validates_and_applies_explicit_date_range(client, db_session, tenant):
    supplier = _create_supplier(db_session, tenant)
    included = _create_purchase(
        db_session, tenant, supplier, purchase_date=date(2026, 7, 15)
    )
    _create_purchase(db_session, tenant, supplier, purchase_date=date(2026, 8, 1))

    response = _dashboard(
        client, tenant, date_from="2026-07-01", date_to="2026-07-31"
    )
    invalid = _dashboard(
        client, tenant, date_from="2026-08-02", date_to="2026-08-01"
    )

    assert response.status_code == 200
    assert response.json()["data"]["summary"]["purchase_count"] == 1
    assert response.json()["data"]["recent_purchases"][0]["id"] == str(included.id)
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_dashboard_filters_supplier_creator_and_document_type(
    client, db_session, tenant
):
    first_supplier = _create_supplier(db_session, tenant, name="Primero")
    second_supplier = _create_supplier(db_session, tenant, name="Segundo")
    first_user = _create_user(db_session, tenant, name="Uno")
    second_user = _create_user(db_session, tenant, name="Dos")
    selected = _create_purchase(
        db_session,
        tenant,
        first_supplier,
        user=first_user,
        document_type="ticket",
        total="300",
    )
    _create_purchase(
        db_session,
        tenant,
        first_supplier,
        user=second_user,
        document_type="ticket",
        total="400",
    )
    _create_purchase(
        db_session,
        tenant,
        second_supplier,
        user=first_user,
        document_type="invoice",
        total="500",
    )

    data = _dashboard(
        client,
        tenant,
        supplier_id=str(first_supplier.id),
        created_by_user_id=str(first_user.id),
        document_type="ticket",
    ).json()["data"]

    assert data["summary"]["purchase_count"] == 1
    assert data["summary"]["registered_total_ars"] == "300.00"
    assert data["recent_purchases"][0]["id"] == str(selected.id)


def test_attention_flags_old_draft_pending_received_missing_document_and_reversal(
    client, db_session, tenant
):
    supplier = _create_supplier(db_session, tenant)
    start = date.today() - timedelta(days=30)
    old_draft = _create_purchase(
        db_session,
        tenant,
        supplier,
        status="draft",
        purchase_date=date.today() - timedelta(days=8),
    )
    recent_draft = _create_purchase(
        db_session, tenant, supplier, status="draft", purchase_date=date.today()
    )
    received = _create_purchase(
        db_session,
        tenant,
        supplier,
        status="received",
        document_number=None,
    )
    reversed_purchase = _create_purchase(
        db_session, tenant, supplier, status="reversed"
    )

    data = _dashboard(
        client,
        tenant,
        date_from=start.isoformat(),
        date_to=date.today().isoformat(),
    ).json()["data"]
    rows = {row["id"]: row for row in data["attention"]}

    assert "old_draft" in rows[str(old_draft.id)]["alerts"]
    assert "attachment_pending" in rows[str(old_draft.id)]["alerts"]
    assert "old_draft" not in rows[str(recent_draft.id)]["alerts"]
    assert rows[str(received.id)]["alerts"] == [
        "attachment_pending",
        "document_number_missing",
    ]
    assert rows[str(received.id)]["priority"] == "high"
    assert rows[str(reversed_purchase.id)]["alerts"] == ["reversed_receipt"]
    assert rows[str(reversed_purchase.id)]["priority"] == "info"


def test_attaching_document_removes_pending_attention_but_keeps_missing_number(
    client, db_session, tenant
):
    supplier = _create_supplier(db_session, tenant)
    purchase = _create_purchase(
        db_session, tenant, supplier, status="received", document_number=None
    )
    _attach(db_session, tenant, purchase)

    data = _dashboard(client, tenant).json()["data"]
    row = next(item for item in data["attention"] if item["id"] == str(purchase.id))

    assert row["attachment_status"] == "attached"
    assert row["alerts"] == ["document_number_missing"]


def test_top_suppliers_orders_by_received_then_registered_and_limits_five(
    client, db_session, tenant
):
    suppliers = [
        _create_supplier(db_session, tenant, name=f"Proveedor {index}")
        for index in range(6)
    ]
    for index, supplier in enumerate(suppliers):
        _create_purchase(
            db_session,
            tenant,
            supplier,
            status="received",
            total=str((index + 1) * 100),
        )
        _create_purchase(
            db_session, tenant, supplier, status="draft", total="50"
        )

    rows = _dashboard(client, tenant).json()["data"]["top_suppliers"]

    assert len(rows) == 5
    assert rows[0]["supplier_name"] == "Proveedor 5"
    assert rows[0]["received_total_ars"] == "600.00"
    assert rows[0]["registered_total_ars"] == "650.00"
    assert rows[0]["purchase_count"] == 2
    assert "Proveedor 0" not in [row["supplier_name"] for row in rows]


def test_recent_purchases_are_limited_ordered_and_include_snapshot_user_and_attachment(
    client, db_session, tenant
):
    supplier = _create_supplier(db_session, tenant, name="Snapshot proveedor")
    user = _create_user(db_session, tenant, name="Compradora reciente")
    purchases = []
    for index in range(10):
        purchases.append(
            _create_purchase(
                db_session,
                tenant,
                supplier,
                user=user,
                created_at=datetime.now(UTC) + timedelta(minutes=index),
                document_number=f"DOC-{index}",
            )
        )
    _attach(db_session, tenant, purchases[-1], user)

    rows = _dashboard(client, tenant).json()["data"]["recent_purchases"]

    assert len(rows) == 8
    assert rows[0]["id"] == str(purchases[-1].id)
    assert rows[0]["supplier_name"] == "Snapshot proveedor"
    assert rows[0]["attachment_status"] == "attached"
    assert rows[0]["created_by_user_name"] == "Compradora reciente"
    assert rows[-1]["id"] == str(purchases[2].id)


def test_dashboard_service_uses_fixed_four_select_queries(db_session, tenant):
    supplier = _create_supplier(db_session, tenant)
    _create_purchase(db_session, tenant, supplier)
    tenant_id = tenant.id
    query_count = 0

    def count_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        nonlocal query_count
        if statement.lstrip().upper().startswith("SELECT"):
            query_count += 1

    event.listen(db_session.bind, "before_cursor_execute", count_selects)
    try:
        PurchaseDashboardService(db_session).get_dashboard(
            tenant_id,
            date_from=None,
            date_to=None,
            supplier_id=None,
            created_by_user_id=None,
            document_type=None,
        )
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count_selects)

    assert query_count == 5


def test_advanced_list_summary_covers_all_filtered_rows_not_only_page(
    client, db_session, tenant
):
    supplier = _create_supplier(db_session, tenant)
    _create_purchase(db_session, tenant, supplier, total="121", tax="21")
    _create_purchase(db_session, tenant, supplier, total="242", tax="42")
    _create_purchase(db_session, tenant, supplier, total="363", tax="63")

    response = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"page_size": 1, "sort_by": "status", "sort_direction": "asc"},
    )
    empty_response = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"status": "received"},
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["meta"]["summary"] == {
        "purchase_count": 3,
        "subtotal_ars": "600.00",
        "tax_total_ars": "126.00",
        "total_ars": "726.00",
    }
    assert empty_response.json()["meta"]["summary"] == {
        "purchase_count": 0,
        "subtotal_ars": "0.00",
        "tax_total_ars": "0.00",
        "total_ars": "0.00",
    }


def test_creator_filter_options_are_distinct_and_tenant_scoped(
    client, db_session, tenant, other_tenant
):
    own_user = _create_user(db_session, tenant, name="Usuario propio")
    foreign_user = _create_user(db_session, other_tenant, name="Usuario ajeno")
    own_supplier = _create_supplier(db_session, tenant)
    foreign_supplier = _create_supplier(db_session, other_tenant)
    _create_purchase(db_session, tenant, own_supplier, user=own_user)
    _create_purchase(db_session, tenant, own_supplier, user=own_user)
    _create_purchase(db_session, other_tenant, foreign_supplier, user=foreign_user)

    response = client.get(
        "/api/v1/purchases/filter-options", headers=_headers(tenant)
    )

    assert response.status_code == 200
    assert response.json()["data"]["creators"] == [
        {
            "id": str(own_user.id),
            "full_name": "Usuario propio",
            "email": own_user.email,
            "is_active": True,
        }
    ]
