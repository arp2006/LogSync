# Universal Log Pre-processing Framework (ULPF)

Backend-first security telemetry pipeline: ingest logs from perimeter network devices, preserve original evidence with cryptographic integrity, parse diverse formats, normalize into canonical OCSF schema, and ensure forensic traceability.

## Implemented Architecture (Phases 1 - 4)

1. **Bootstrap and Environment**:
   - Python package structure (`src/ulpf/`)
   - `pydantic-settings` configuration (`ulpf.config.Settings`)
   - Dockerfile (pinned base image) and `docker-compose.yml` (PostgreSQL 16 with pgcrypto, API service, Worker service)
   - Ruff linting and Pytest test suite

2. **Database Access & Migrations**:
   - Core tables: `sources`, `ingestion_jobs`, `raw_events`, `normalized_events`, `parser_errors`, `audit_events`
   - Complete PostgreSQL DDL with `pgcrypto`, JSONB, constraints, and indexes
   - Alembic migration scripts (`0001_initial.py`) and standalone `init_db.sql`
   - SQLAlchemy 2.0 declarative models

3. **Immutable Evidence Store**:
   - Streaming disk persistence: `data/raw/YYYY/MM/<job-id>/original.bin`
   - Constant-time SHA-256 integrity calculation (`hmac.compare_digest`)
   - Safe path resolution preventing directory traversal attacks
   - Atomic temporary file creation and rename
   - Configurable upload payload limits with automatic cleanup of aborted uploads

4. **Source Registration & Upload API**:
   - `POST /api/v1/sources`: Register new telemetry source (case-insensitive name uniqueness, 409 conflict handling)
   - `GET /api/v1/sources`: List sources
   - `GET /api/v1/sources/{source_id}`: Retrieve source detail
   - `POST /api/v1/ingestion-jobs`: Multi-part log file upload, validating source and format (`cef`, `syslog`, `json`), persisting raw evidence, returning `202 Accepted`
   - `GET /api/v1/ingestion-jobs/{job_id}`: Job status and progress inspection
   - `GET /health/live` & `GET /health/ready`: Liveness and database readiness probes
   - Standardized structured error envelopes with request IDs

## Quickstart

### Running with Docker Compose (Production / Air-Gapped)
```bash
docker compose up --build
```

### Local Development & Testing
```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest tests -v

# Run linter
ruff check .
```
