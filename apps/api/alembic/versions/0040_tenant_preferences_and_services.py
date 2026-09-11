"""add tenant preferences and services"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0040_tenant_prefs_services"
down_revision = "0039_sale_payments"
branch_labels = None
depends_on = None


EXISTING_TENANT_REGIONAL_PREFERENCE_V1: dict[str, object] = {
    # Before tenant-level preferences existed, the operational modules in the
    # recovery branch used ARS/es-AR behavior globally. Seed every tenant that
    # already exists at migration time with those same values so this migration
    # is behavior-preserving and does not depend on a hard-coded tenant UUID list.
    # Newly provisioned tenants use the application defaults (USD/es-PA).
    "currency_code": "ARS",
    "locale": "es-AR",
    "default_appointment_duration_minutes": 30,
    "appointment_duration_options": [15, 30, 45, 60],
}

SERVICE_TEMPLATES_V1 = (
    {
        "code": "CONSULTA",
        "name": "Consulta general",
        "normalized_name": "consulta general",
        "description": "Atencion clinica general",
        "kind": "consultation",
        "default_duration_minutes": 30,
        "calendar_color": "#2563eb",
        "is_bookable": True,
        "sort_order": 10,
    },
    {
        "code": "SEGUIMIENTO",
        "name": "Seguimiento",
        "normalized_name": "seguimiento",
        "description": "Control posterior a consulta o tratamiento",
        "kind": "follow_up",
        "default_duration_minutes": 30,
        "calendar_color": "#0891b2",
        "is_bookable": True,
        "sort_order": 20,
    },
    {
        "code": "VACUNA",
        "name": "Vacunacion",
        "normalized_name": "vacunacion",
        "description": "Aplicacion de vacunas",
        "kind": "vaccine",
        "default_duration_minutes": 20,
        "calendar_color": "#16a34a",
        "is_bookable": True,
        "sort_order": 30,
    },
    {
        "code": "DESPARASITACION",
        "name": "Desparasitacion",
        "normalized_name": "desparasitacion",
        "description": "Control y aplicacion antiparasitaria",
        "kind": "deworming",
        "default_duration_minutes": 20,
        "calendar_color": "#ca8a04",
        "is_bookable": True,
        "sort_order": 40,
    },
    {
        "code": "EXAMEN",
        "name": "Examen",
        "normalized_name": "examen",
        "description": "Toma o revision de examenes",
        "kind": "exam",
        "default_duration_minutes": 30,
        "calendar_color": "#9333ea",
        "is_bookable": True,
        "sort_order": 50,
    },
)


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('superadmin', 'clinic_admin', 'medico_veterinario', 'contador')",
    )

    _bootstrap_existing_clinic_admins()

    op.create_table(
        "tenant_preferences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("locale", sa.String(length=10), server_default="es-PA", nullable=False),
        sa.Column(
            "default_appointment_duration_minutes",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column("appointment_duration_options", sa.JSON(), nullable=False),
        sa.Column(
            "catalog_template_version",
            sa.String(length=32),
            server_default="regional-v1",
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_tenant_preferences_tenant_id"),
        "tenant_preferences",
        ["tenant_id"],
        unique=True,
    )

    op.create_table(
        "services",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("calendar_color", sa.String(length=32), server_default="#2563eb", nullable=False),
        sa.Column("is_bookable", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('consultation', 'follow_up', 'vaccine', 'deworming', 'exam', 'procedure', 'other')",
            name="ck_services_kind",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_services_tenant_id"), "services", ["tenant_id"])
    op.create_index(op.f("ix_services_code"), "services", ["code"])
    op.create_index(op.f("ix_services_kind"), "services", ["kind"])
    op.create_index(op.f("ix_services_is_bookable"), "services", ["is_bookable"])
    op.create_index(op.f("ix_services_sort_order"), "services", ["sort_order"])
    op.create_index(op.f("ix_services_is_active"), "services", ["is_active"])
    op.create_index(
        op.f("ix_services_created_by_user_id"),
        "services",
        ["created_by_user_id"],
    )
    op.create_index(
        "ux_services_tenant_normalized_name_active",
        "services",
        ["tenant_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active = 1"),
    )

    op.add_column("appointments", sa.Column("service_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_appointments_service_id"),
        "appointments",
        ["service_id"],
    )
    op.create_foreign_key(
        "fk_appointments_service_id_services",
        "appointments",
        "services",
        ["service_id"],
        ["id"],
    )

    _seed_existing_tenants()


def downgrade() -> None:
    op.drop_constraint("fk_appointments_service_id_services", "appointments", type_="foreignkey")
    op.drop_index(op.f("ix_appointments_service_id"), table_name="appointments")
    op.drop_column("appointments", "service_id")

    op.drop_index("ux_services_tenant_normalized_name_active", table_name="services")
    op.drop_index(op.f("ix_services_created_by_user_id"), table_name="services")
    op.drop_index(op.f("ix_services_is_active"), table_name="services")
    op.drop_index(op.f("ix_services_sort_order"), table_name="services")
    op.drop_index(op.f("ix_services_is_bookable"), table_name="services")
    op.drop_index(op.f("ix_services_kind"), table_name="services")
    op.drop_index(op.f("ix_services_code"), table_name="services")
    op.drop_index(op.f("ix_services_tenant_id"), table_name="services")
    op.drop_table("services")

    op.drop_index(op.f("ix_tenant_preferences_tenant_id"), table_name="tenant_preferences")
    op.drop_table("tenant_preferences")

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.execute(
        """
        UPDATE users
        SET role = 'medico_veterinario'
        WHERE role = 'clinic_admin'
        """
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('superadmin', 'medico_veterinario', 'contador')",
    )


def _bootstrap_existing_clinic_admins() -> None:
    """Bootstrap only unambiguous existing clinic administrators.

    Before ``clinic_admin`` existed, every clinic user was stored as
    ``medico_veterinario``. Promoting every veterinarian would grant elevated
    configuration permissions too broadly, while promoting an arbitrary user in
    a multi-user tenant would be equally unsafe.

    Two cases are sufficiently explicit to migrate automatically:
    * the sole active veterinarian in a tenant;
    * an active veterinarian whose display name clearly contains ``admin``.

    The sole-user rule runs first so promoting a named administrator in a
    multi-user tenant cannot make the remaining veterinarian look like the sole
    candidate. Multi-user tenants without an explicitly administrative account
    are left unchanged and must receive a deliberate administrator assignment
    before go-live.
    """
    op.execute(
        """
        WITH sole_active_veterinarian AS (
            SELECT tenant_id
            FROM users
            WHERE role = 'medico_veterinario'
              AND is_active IS TRUE
            GROUP BY tenant_id
            HAVING COUNT(*) = 1
        )
        UPDATE users AS u
        SET role = 'clinic_admin'
        FROM sole_active_veterinarian AS candidate
        WHERE u.tenant_id = candidate.tenant_id
          AND u.role = 'medico_veterinario'
          AND u.is_active IS TRUE
        """
    )
    op.execute(
        """
        UPDATE users
        SET role = 'clinic_admin'
        WHERE role = 'medico_veterinario'
          AND is_active IS TRUE
          AND lower(full_name) LIKE '%admin%'
        """
    )


def _seed_existing_tenants() -> None:
    bind = op.get_bind()
    tenant_ids = [
        row["id"] for row in bind.execute(sa.text("SELECT id FROM tenants")).mappings()
    ]
    if not tenant_ids:
        return

    preferences_table = sa.table(
        "tenant_preferences",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("currency_code", sa.String()),
        sa.column("locale", sa.String()),
        sa.column("default_appointment_duration_minutes", sa.Integer()),
        sa.column("appointment_duration_options", sa.JSON()),
        sa.column("catalog_template_version", sa.String()),
    )
    services_table = sa.table(
        "services",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("kind", sa.String()),
        sa.column("default_duration_minutes", sa.Integer()),
        sa.column("calendar_color", sa.String()),
        sa.column("is_bookable", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )

    preference_rows = []
    service_rows = []
    for tenant_id in tenant_ids:
        tenant_uuid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        preference_rows.append(
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_uuid,
                "currency_code": EXISTING_TENANT_REGIONAL_PREFERENCE_V1["currency_code"],
                "locale": EXISTING_TENANT_REGIONAL_PREFERENCE_V1["locale"],
                "default_appointment_duration_minutes": EXISTING_TENANT_REGIONAL_PREFERENCE_V1[
                    "default_appointment_duration_minutes"
                ],
                "appointment_duration_options": EXISTING_TENANT_REGIONAL_PREFERENCE_V1[
                    "appointment_duration_options"
                ],
                "catalog_template_version": "regional-v1",
            }
        )
        for template in SERVICE_TEMPLATES_V1:
            service_rows.append(
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_uuid,
                    "is_active": True,
                    **template,
                }
            )

    op.bulk_insert(preferences_table, preference_rows)
    op.bulk_insert(services_table, service_rows)
