from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import listing_agent.models  # noqa: F401
from listing_agent.core.config import get_settings
from listing_agent.db.base import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url = settings.resolved_database_url
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        _engine = create_async_engine(
            database_url,
            echo=settings.app_debug,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def check_database() -> None:
    """Verify that the configured database accepts a simple query."""
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


async def init_db() -> None:
    """Create V1 tables and seed fixed data until formal migrations are introduced."""
    from listing_agent.db.seeds import seed_reference_data

    async with get_engine().begin() as connection:
        await connection.run_sync(_drop_legacy_rule_tables_if_needed)
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_sqlite_compat_columns)
    async with get_session_factory()() as session:
        await seed_reference_data(session)


def _drop_legacy_rule_tables_if_needed(sync_connection) -> None:
    """Drop old synced-rule tables once when the legacy rule schema is detected."""
    from sqlalchemy import inspect

    inspector = inspect(sync_connection)
    table_names = set(inspector.get_table_names())
    has_legacy_rule_table = False

    if "rule_sources" in table_names or "rule_snapshots" in table_names:
        has_legacy_rule_table = True
    elif "rules" in table_names:
        rule_columns = {column["name"] for column in inspector.get_columns("rules")}
        has_legacy_rule_table = (
            "rule_source_id" in rule_columns
            or "rule_snapshot_id" in rule_columns
            or "synced_at" in rule_columns
        )

    if not has_legacy_rule_table:
        return

    if "jobs" in table_names:
        sync_connection.exec_driver_sql("DELETE FROM jobs WHERE job_type = 'rule_sync'")

    if sync_connection.dialect.name == "sqlite":
        sync_connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table_name in ("rule_snapshots", "rule_sources", "rules"):
            if table_name in table_names:
                sync_connection.exec_driver_sql(f"DROP TABLE IF EXISTS {table_name}")
        sync_connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        return

    for table_name in ("rule_snapshots", "rule_sources", "rules"):
        if table_name in table_names:
            sync_connection.exec_driver_sql(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def _ensure_sqlite_compat_columns(sync_connection) -> None:
    """Apply additive SQLite columns while the project does not use formal migrations."""
    if sync_connection.dialect.name != "sqlite":
        return

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(competitor_summaries)").fetchall()
    column_names = {row[1] for row in rows}
    if "search_terms" not in column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE competitor_summaries ADD COLUMN search_terms JSON"
        )
    if "extraction_result" not in column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE competitor_summaries ADD COLUMN extraction_result JSON"
        )
    if "analysis_result" not in column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE competitor_summaries ADD COLUMN analysis_result JSON"
        )

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(competitor_analyses)").fetchall()
    analysis_column_names = {row[1] for row in rows}
    if rows and "action_brief" not in analysis_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE competitor_analyses ADD COLUMN action_brief JSON"
        )
    if rows and "constraints" not in analysis_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE competitor_analyses ADD COLUMN constraints JSON"
        )

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(model_configs)").fetchall()
    model_column_names = {row[1] for row in rows}
    if rows and "thinking_config" not in model_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE model_configs ADD COLUMN thinking_config VARCHAR(32) DEFAULT 'disabled' NOT NULL"
        )

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(model_invocation_logs)").fetchall()
    log_column_names = {row[1] for row in rows}
    if rows and "api_endpoint" not in log_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE model_invocation_logs ADD COLUMN api_endpoint VARCHAR(255) DEFAULT '' NOT NULL"
        )

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(product_briefs)").fetchall()
    brief_column_names = {row[1] for row in rows}
    if rows and "color" not in brief_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE product_briefs ADD COLUMN color VARCHAR(255)"
        )
    if rows and "quantity" not in brief_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE product_briefs ADD COLUMN quantity VARCHAR(255)"
        )

    rows = sync_connection.exec_driver_sql("PRAGMA table_info(rules)").fetchall()
    rule_column_names = {row[1] for row in rows}
    if rows and "rule_schema" not in rule_column_names:
        sync_connection.exec_driver_sql(
            "ALTER TABLE rules ADD COLUMN rule_schema JSON"
        )


async def dispose_engine() -> None:
    """Dispose pooled database connections during application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
