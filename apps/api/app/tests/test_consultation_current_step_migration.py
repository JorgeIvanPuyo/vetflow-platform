import importlib.util
from pathlib import Path


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0025_consultation_six_step_workflow.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0025_normalize_consultation_current_step",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_consultation_current_step_upgrade_mapping():
    migration = _load_migration_module()

    assert {
        step: migration.upgrade_current_step(step) for step in range(1, 9)
    } == {
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 4,
        6: 6,
        7: 6,
        8: 5,
    }
    assert migration.upgrade_current_step(None) is None
    assert migration.upgrade_current_step(99) == 1


def test_consultation_current_step_downgrade_mapping_is_canonical():
    migration = _load_migration_module()

    assert {
        step: migration.downgrade_current_step(step) for step in range(1, 7)
    } == {
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 8,
        6: 6,
    }
    assert migration.downgrade_current_step(None) is None
    assert migration.downgrade_current_step(99) == 1
