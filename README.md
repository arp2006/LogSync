# Universal Log Pre-processing Framework (ULPF)

Backend-first security telemetry pipeline: ingest logs from perimeter network devices, preserve original evidence with cryptographic integrity, parse diverse formats, normalize into canonical OCSF schema, and ensure forensic traceability.

## End-to-End Architecture Implemented

1. **Bootstrap and Environment**:
   - Python package structure (`src/ulpf/`)
   - `pydantic-settings` configuration (`ulpf.config.Settings`)
   - Pinned Dockerfile and `docker-compose.yml` (PostgreSQL 16 with pgcrypto, API service, Worker service)
   - Ruff linting and Pytest test suite

2. **Database Layer & Migrations**:
   - Tables: `sources`, `ingestion_jobs`, `raw_events`, `normalized_events`, `parser_errors`, `audit_events`
   - Native PostgreSQL DDL with `pgcrypto`, JSONB, constraints, and indexes
   - Alembic migrations (`0001_initial.py`) and standalone `init_db.sql`
   - SQLAlchemy 2.0 declarative models

3. **Immutable Evidence Store**:
   - Streaming disk persistence: `data/raw/YYYY/MM/<job-id>/original.bin`
   - Constant-time SHA-256 integrity calculation (`hmac.compare_digest`)
   - Safe path resolution preventing directory traversal attacks
   - Atomic temporary file creation and rename
   - Configurable upload payload limits with automatic cleanup

4. **Multi-Format Parsers & Registry**:
   - `CEFParser`: Unescaped pipe splitting, extension key-value parser with space/delimiter unescaping, and full header attribute preservation
   - `SyslogParser`: RFC 5424 structured headers, RFC 3164 BSD timestamp handling (with explicit inferred year/timezone tracking), and perimeter network pattern extraction
   - `JSONParser`: NDJSON object validation, timestamp normalization, IP/port extraction, and lossless unmapped field retention
   - `ParserRegistry`: Extensible format registration (`cef`, `syslog`, `json`)

5. **OCSF Canonical Schema & Normalization**:
   - Vendored, pinned OCSF 1.1.0 schema specification (`schemas/ocsf/schema.json`)
   - Local schema validator enforcing required attributes, valid IP formats, and port ranges
   - `OCSFNormalizer`: Maps source telemetry to OCSF classes (4001: Network Activity, 3001: Authentication, 1001: Base Event)
   - Lossless Canonical Envelope linking normalized events to original evidence metadata

6. **Database-Backed Worker**:
   - Atomic row-level job claiming using `FOR UPDATE SKIP LOCKED`
   - Batch-oriented record insertion into `raw_events`
   - Fault-isolated execution: malformed or invalid records are recorded in `parser_errors` linked to `raw_events` without losing the original record
   - Automatic job status transitions (`queued` -> `processing` -> `completed` / `completed_with_errors` / `failed`)

7. **Query, Verification, Error, and Export APIs**:
   - `POST /api/v1/sources`: Register source
   - `GET /api/v1/sources`: List sources
   - `POST /api/v1/ingestion-jobs`: Multi-part log upload returning `202 Accepted`
   - `GET /api/v1/ingestion-jobs/{job_id}`: Job progress and status
   - `GET /api/v1/ingestion-jobs/{job_id}/errors`: Inspect per-record parsing and validation failures
   - `GET /api/v1/events`: Search normalized events with cursor pagination and time/source/class filters
   - `GET /api/v1/raw-events/{raw_event_id}`: Retrieve original raw evidence
   - `POST /api/v1/raw-events/{raw_event_id}/verify`: Recompute SHA-256 and verify cryptographic integrity
   - `GET /api/v1/exports/events`: Stream normalized events as JSONL for SIEM/analytics consumption
   - `GET /health/live` & `GET /health/ready`: System and database health probes

## Verification & Testing

```bash
# Run the complete test suite (33 tests)
.venv/bin/pytest tests -v

# Run the linter
.venv/bin/ruff check .
```

All 10 SIH evaluation criteria are tested and passing end-to-end.
