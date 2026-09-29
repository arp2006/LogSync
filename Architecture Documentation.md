# Universal Log Pre-processing Framework (ULPF)
## Architecture Document · v1.0

### 1. Overview

ULPF is a backend-first, containerized security telemetry pipeline that ingests raw logs from heterogeneous perimeter network devices, preserves original evidence with cryptographic integrity, parses multiple log formats, and normalizes events into the **OCSF 1.1.0** (Open Cybersecurity Schema Framework) canonical schema for SIEM and AI/ML consumption.

---

### 2. High-Level Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         ULPF PIPELINE ARCHITECTURE                             │
├──────────────┬──────────────────┬──────────────────┬──────────────┬────────────┤
│   STAGE 1    │    STAGE 2       │    STAGE 3       │   STAGE 4    │  STAGE 5   │
│  INGESTION   │  EVIDENCE STORE  │  ASYNC QUEUE     │  PARSE &     │  EGRESS    │
│              │                  │  WORKER          │  NORMALISE   │            │
├──────────────┼──────────────────┼──────────────────┼──────────────┼────────────┤
│ Firewall ──► │ Raw bytes        │ PostgreSQL       │ CEF Parser   │ REST API   │
│ Router   ──► │ streamed to disk │ Job Queue        │ Syslog Pars. │            │
│ VPN      ──► │                  │ (SKIP LOCKED)    │ JSON Parser  │ NDJSON     │
│ IDS/IPS  ──► │ SHA-256 hash     │                  │              │ Stream     │
│              │ computed &       │ Atomic claiming  │ OCSF 1.1.0   │            │
│ CEF          │ stored in DB     │ — no duplicates  │ Validation   │ Splunk     │
│ Syslog       │                  │                  │              │ Elastic    │
│ JSON/NDJSON  │ /verify endpoint │ Fault Isolation: │ Class 4001   │ Chronicle  │
│              │ recomputes hash  │ malformed lines  │ Class 3001   │ Sec. Lake  │
│ FastAPI      │ using            │ → parser_errors  │ Class 1001   │            │
│ 100 MB max   │ hmac.compare_    │ batch continues  │              │ React 18   │
│ 202 Accepted │ digest           │                  │              │ Dashboard  │
└──────────────┴──────────────────┴──────────────────┴──────────────┴────────────┘
```

---

### 3. Deployment Architecture (Docker Compose)

```
┌───────────────────────────────────────────────────────┐
│                  docker-compose.yml                   │
│                                                       │
│  ┌─────────────────┐   ┌───────────────────────────┐  │
│  │    postgres     │   │       api  (FastAPI)      │  │
│  │   port :5432    │◄──│  Alembic migrations       │  │
│  │  PostgreSQL 16  │   │  uvicorn :8000            │  │
│  │  + pgcrypto     │   │  CORS + RequestID MW      │  │
│  └────────┬────────┘   └───────────────────────────┘  │
│           │                          │                │
│           └──────────────────────────┤                │
│                          ┌───────────▼───────────────┐│
│                          │      worker (Python)      ││
│                          │  Polls queue every 5 s    ││
│                          │  Processes queued jobs    ││
│                          └───────────────────────────┘│
│                                                       │
│  Named Volumes:  pgdata  │  raw_evidence_data (disk)  │
└───────────────────────────────────────────────────────┘
```

---

### 4. Database Schema

| Table | Purpose | Key Columns |
|---|---|---|
| `sources` | Device registry | `id`, `name`, `vendor`, `product`, `source_type`, `is_active` |
| `ingestion_jobs` | Job lifecycle | `job_id`, `status`, `format`, `total / processed / failed_records` |
| `raw_events` | Immutable evidence | `id`, `job_id`, `raw_sha256`, `raw_bytes`, `raw_text`, `record_index` |
| `normalized_events` | OCSF events | `id`, `raw_event_id`, `class_uid`, `event_time`, `event_data (JSONB)` |
| `parser_errors` | Per-record failures | `id`, `raw_event_id`, `error_code`, `stage`, `message` |
| `audit_events` | Compliance trail | `id`, `action`, `actor`, `created_at` |

---

### 5. Core Component Design

```
src/ulpf/
├── api/                FastAPI routers (sources, ingestion, events, health)
├── parsers/
│   ├── base.py         BaseParser interface — parse() → Iterator[dict]
│   ├── registry.py     ParserRegistry — register / lookup by format name
│   ├── cef_parser.py   CEF: unescaped pipe split, extension KV unescaping
│   ├── syslog_parser.py    RFC 5424 + RFC 3164 with year-rollover inference
│   └── json_parser.py      NDJSON: line-by-line + timestamp normalisation
├── services/
│   ├── evidence_store.py   Streaming disk write, atomic rename, SHA-256
│   └── normalization.py    OCSF mapper + local schema validator
├── worker/
│   └── processor.py    SKIP LOCKED queue, batch insert, fault isolation
└── models/             SQLAlchemy 2.0 declarative ORM models
```

**Adding a New Format** — implement one class, register one line:

```python
class LEEFParser(BaseParser):
    def parse(self, raw: bytes) -> Iterator[dict]:
        for line in raw.splitlines():
            yield { "src_ip": ..., "action": ..., ... }

registry.register("leef", LEEFParser())   # no other changes needed
```

---

### 6. Complete API Surface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Database readiness probe |
| `POST` | `/api/v1/sources` | Register new log source |
| `GET` | `/api/v1/sources` | List all sources |
| `GET` | `/api/v1/sources/{id}` | Get source by ID |
| `POST` | `/api/v1/ingestion-jobs` | Upload log file (multipart) → `202 Accepted` |
| `GET` | `/api/v1/ingestion-jobs/{job_id}` | Poll job status & record counts |
| `GET` | `/api/v1/ingestion-jobs/{job_id}/errors` | Inspect per-record failures |
| `GET` | `/api/v1/events` | Search OCSF events with cursor pagination |
| `GET` | `/api/v1/events/{id}` | Get single normalized event |
| `GET` | `/api/v1/raw-events/{id}` | Retrieve original raw evidence |
| `POST` | `/api/v1/raw-events/{id}/verify` | Recompute & verify SHA-256 |
| `GET` | `/api/v1/exports/events` | Streaming NDJSON export (SIEM / data lake) |

---

### 7. OCSF 1.1.0 Normalization Mapping

| Input Source | Detected Pattern | OCSF Class | UID |
|---|---|---|---|
| CEF (Firewall) | Network allow / deny / reset traffic | Network Activity | **4001** |
| Syslog / JSON (VPN, IAM) | Login success / failure events | Authentication | **3001** |
| Any format (fallback) | Generic security telemetry | Base Event | **1001** |

**Full Traceability Chain:**
`normalized_events` → `raw_event_id` → `raw_events` → `raw_sha256` → disk file

---

### 8. Security & Forensic Design Decisions

| Decision | Implementation | Standard |
|---|---|---|
| Tamper-evident evidence store | SHA-256 at ingest; verify on demand | NIST FIPS 180-4 |
| Constant-time hash comparison | `hmac.compare_digest` — no timing oracle | NIST SP 800-86 |
| Path traversal prevention | Safe path resolution before all disk writes | OWASP |
| Atomic file creation | Write to temp → `os.rename()` | — |
| No duplicate job processing | `SELECT FOR UPDATE SKIP LOCKED` | PostgreSQL 16 |
| Fault-isolated parsing | Per-record try/except → `parser_errors` | — |
| Air-gap deployable | OCSF schema vendored locally; zero outbound calls | — |
| Platform independent | Docker + docker-compose, 3-service stack | — |

---

### 9. Technology Stack

| Layer | Technology |
|---|---|
| **API Framework** | Python 3.12, FastAPI 0.115, Uvicorn, Pydantic v2 |
| **ORM & Migrations** | SQLAlchemy 2.0, Alembic |
| **Database** | PostgreSQL 16-alpine + pgcrypto |
| **Queue** | PostgreSQL `FOR UPDATE SKIP LOCKED` (no Redis / RabbitMQ) |
| **Frontend** | React 18, Vite 5, Tailwind CSS 3, React Router v6 |
| **Containerisation** | Docker, docker-compose (3 services) |
| **Standards** | OCSF 1.1.0 · RFC 5424 · RFC 3164 · ArcSight CEF · NIST SP 800-92/86 · ISO/IEC 27037 |
| **Testing** | Pytest + HTTPX — 33 tests, all passing |

---

*ULPF Architecture Document · v1.0*
