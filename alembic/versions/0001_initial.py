"""0001_initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSTGRES_UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'network_device',
    vendor TEXT,
    product TEXT,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sources_name
    ON sources (lower(name));

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id),
    original_filename TEXT NOT NULL,
    input_format TEXT NOT NULL
        CHECK (input_format IN ('cef', 'syslog', 'json')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN (
            'queued', 'processing', 'completed',
            'completed_with_errors', 'failed'
        )),
    raw_file_path TEXT NOT NULL,
    raw_file_sha256 CHAR(64) NOT NULL,
    raw_file_size BIGINT NOT NULL CHECK (raw_file_size >= 0),
    total_records INTEGER NOT NULL DEFAULT 0,
    processed_records INTEGER NOT NULL DEFAULT 0,
    failed_records INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_jobs_queue
    ON ingestion_jobs (created_at)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS ix_jobs_source_created
    ON ingestion_jobs (source_id, created_at DESC);

CREATE TABLE IF NOT EXISTS raw_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id),
    source_id UUID NOT NULL REFERENCES sources(id),
    record_index INTEGER NOT NULL CHECK (record_index >= 0),
    raw_bytes BYTEA NOT NULL,
    raw_text TEXT,
    raw_sha256 CHAR(64) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, record_index)
);

CREATE INDEX IF NOT EXISTS ix_raw_events_source_received
    ON raw_events (source_id, received_at DESC);

CREATE TABLE IF NOT EXISTS normalized_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_event_id UUID NOT NULL UNIQUE REFERENCES raw_events(id),
    source_id UUID NOT NULL REFERENCES sources(id),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id),
    ocsf_version TEXT NOT NULL,
    class_uid INTEGER,
    category_uid INTEGER,
    activity_id INTEGER,
    event_time TIMESTAMPTZ,
    severity_id INTEGER,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_normalized_source_time
    ON normalized_events (source_id, event_time DESC);

CREATE INDEX IF NOT EXISTS ix_normalized_class_time
    ON normalized_events (class_uid, event_time DESC);

CREATE INDEX IF NOT EXISTS ix_normalized_event_data
    ON normalized_events USING GIN (event_data);

CREATE TABLE IF NOT EXISTS parser_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_event_id UUID NOT NULL REFERENCES raw_events(id),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    stage TEXT NOT NULL
        CHECK (stage IN ('parse', 'normalize', 'validate')),
    error_code TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (raw_event_id, parser_name, parser_version, stage)
);

CREATE INDEX IF NOT EXISTS ix_parser_errors_created
    ON parser_errors (created_at DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_resource
    ON audit_events (resource_type, resource_id, created_at DESC);
"""

POSTGRES_DOWNGRADE_SQL = """
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS parser_errors;
DROP TABLE IF EXISTS normalized_events;
DROP TABLE IF EXISTS raw_events;
DROP TABLE IF EXISTS ingestion_jobs;
DROP TABLE IF EXISTS sources;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(POSTGRES_UPGRADE_SQL))
    else:
        # Fallback for SQLite / test environments
        from ulpf.models.base import Base

        Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(POSTGRES_DOWNGRADE_SQL))
    else:
        from ulpf.models.base import Base

        Base.metadata.drop_all(bind=bind)
