import importlib.util
from pathlib import Path


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0045_backfill_catalog_refs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0045_backfill_catalog_refs",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_name_matches_app_normalization():
    migration = _load_migration_module()

    assert migration._normalize_name("  Hemograma   completo ") == "hemograma completo"
    assert migration._normalize_name("Desparasitación externa") == "desparasitacion externa"
    assert migration._normalize_name("RADIOGRAFÍA") == "radiografia"
