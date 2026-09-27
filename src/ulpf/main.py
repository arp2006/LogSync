import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ulpf.api import api_v1_router
from ulpf.api.errors import setup_exception_handlers
from ulpf.api.health import router as health_router
from ulpf.config import settings


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure raw evidence directory exists
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Universal Log Pre-processing Framework (ULPF)",
    description=(
        "Backend-first security telemetry pipeline: lossless ingestion, "
        "preservation, and normalization."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Exception handlers
setup_exception_handlers(app)

# Middlewares
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route registration
app.include_router(health_router)
app.include_router(api_v1_router)
