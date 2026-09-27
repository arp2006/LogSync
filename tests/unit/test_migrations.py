from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_migration_upgrade_and_downgrade(tmp_path):
    # Use SQLite file for testing Alembic migration lifecycle
    test_db = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{test_db}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "sources",
        "ingestion_jobs",
        "raw_events",
        "normalized_events",
        "parser_errors",
        "audit_events",
        "alembic_version",
    }
    assert expected_tables.issubset(set(tables))

    # Downgrade to base
    command.downgrade(alembic_cfg, "base")
    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    assert "sources" not in tables_after
