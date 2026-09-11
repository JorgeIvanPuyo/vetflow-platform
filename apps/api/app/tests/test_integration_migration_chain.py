import ast
from pathlib import Path


VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _metadata(filename: str) -> tuple[str, str | None]:
    tree = ast.parse((VERSIONS / filename).read_text())
    values: dict[str, str | None] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in {"revision", "down_revision"}:
            continue
        if isinstance(node.value, ast.Constant) and (
            isinstance(node.value.value, str) or node.value.value is None
        ):
            values[target.id] = node.value.value
    return values["revision"], values["down_revision"]


def test_customization_migrations_are_linear_after_recovery_sales_head():
    expected = [
        ("0040_tenant_preferences_and_services.py", "0040_tenant_prefs_services", "0039_sale_payments"),
        ("0041_catalog_items.py", "0041_catalog_items", "0040_tenant_prefs_services"),
        ("0042_tenant_preference_money_defaults.py", "0042_tenant_pref_money", "0041_catalog_items"),
        ("0043_supplier_inventory_link.py", "0043_supplier_inventory", "0042_tenant_pref_money"),
        ("0044_operational_catalog_references.py", "0044_operational_catalog_refs", "0043_supplier_inventory"),
        ("0045_backfill_catalog_refs.py", "0045_backfill_catalog_refs", "0044_operational_catalog_refs"),
        ("0046_clinical_catalog_extensions.py", "0046_clinical_catalog_ext", "0045_backfill_catalog_refs"),
        ("0047_backfill_species_refs.py", "0047_backfill_species_refs", "0046_clinical_catalog_ext"),
        ("0048_operational_currency_preferences.py", "0048_operational_currency", "0047_backfill_species_refs"),
        ("0049_backfill_inventory_category_refs.py", "0049_inventory_category_refs", "0048_operational_currency"),
        ("0050_service_pricing.py", "0050_service_pricing", "0049_inventory_category_refs"),
    ]

    for filename, revision, down_revision in expected:
        assert _metadata(filename) == (revision, down_revision)


def test_parallel_teammate_migration_files_were_removed():
    removed = {
        "0026_tenant_preferences_and_services.py",
        "0027_catalog_items.py",
        "0028_tenant_preference_money_defaults.py",
        "0029_suppliers.py",
        "0030_operational_catalog_references.py",
        "0031_backfill_catalog_refs.py",
        "0032_clinical_catalog_extensions.py",
        "0033_backfill_species_refs.py",
    }

    assert not removed.intersection(path.name for path in VERSIONS.glob("*.py"))


def test_tenant_preferences_migration_only_bootstraps_unambiguous_admins():
    source = (VERSIONS / "0040_tenant_preferences_and_services.py").read_text()
    assert "_bootstrap_existing_clinic_admins()" in source
    assert "lower(full_name) LIKE '%admin%'" in source
    assert "HAVING COUNT(*) = 1" in source
    assert "WHERE role = 'medico_veterinario'\n          AND is_active IS TRUE" in source
    assert "UPDATE users\n        SET role = 'clinic_admin'\n        WHERE role = 'medico_veterinario'" in source


def test_existing_tenant_money_defaults_are_derived_from_inventory_history():
    source = (VERSIONS / "0042_tenant_preference_money_defaults.py").read_text()
    assert "SET default_purchase_tax_rate = 21" not in source
    assert "GROUP BY ii.purchase_tax_rate_percentage" in source
    assert "GROUP BY ii.sale_tax_rate_percentage" in source
    assert "GROUP BY ii.profit_margin_percentage" in source
    assert "ORDER BY COUNT(*) DESC, ii.purchase_tax_rate_percentage ASC" in source
    assert "ABS(ii.profit_margin_percentage - 35) ASC" in source


def test_operational_currency_migration_removes_ars_only_constraints_and_defaults():
    source = (VERSIONS / "0048_operational_currency_preferences.py").read_text()
    assert "currency = 'ARS'" in source  # downgrade compatibility only
    assert 'server_default=None' in source
    assert '_CURRENCY_CHECK = "length(currency) = 3 AND currency = upper(currency)"' in source


def test_inventory_category_backfill_is_tenant_scoped_and_unambiguous():
    source = (VERSIONS / "0049_backfill_inventory_category_refs.py").read_text()
    assert "COUNT(*) OVER (PARTITION BY tenant_id, code)" in source
    assert "candidate.candidate_count = 1" in source
    assert "candidate.tenant_id = item.tenant_id" in source
    assert "candidate.code = item.category" in source
    assert "item.category_catalog_item_id IS NULL" in source
