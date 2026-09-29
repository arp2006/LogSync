# ULPF Frontend

React + Vite + Tailwind CSS dashboard for the **Universal Log Pre-processing Framework**.

## Prerequisites

- Node.js 18+ and npm
- ULPF backend running on `http://localhost:8000`

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>

## Pages

| Route       | Purpose |
|-------------|---------|
| `/`         | Dashboard — health, stats, pipeline overview |
| `/sources`  | Register and manage log sources |
| `/ingest`   | Upload CEF / Syslog / JSON log files |
| `/jobs`     | Monitor ingestion job status and errors |
| `/events`   | Browse and filter OCSF normalized events |
| `/evidence` | Fetch raw evidence and verify SHA-256 integrity |
| `/export`   | Stream normalized events as JSONL for SIEM consumption |

## Build for Production

```bash
npm run build
# Output: frontend/dist/
```

The `vite.config.js` dev-server proxies `/api` and `/health` to `http://localhost:8000`.
For production deployments, configure your web server (Nginx, Caddy) to reverse-proxy those paths.
