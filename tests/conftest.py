import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ulpf.db import get_db
from ulpf.main import app
from ulpf.models.base import Base
from ulpf.services.evidence_store import EvidenceStore
from ulpf.services.ingestion_service import IngestionService


@pytest.fixture(scope="session")
def test_engine():
    # In-memory SQLite with StaticPool for fast, isolated testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def temp_evidence_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def evidence_store(temp_evidence_dir) -> EvidenceStore:
    return EvidenceStore(base_dir=temp_evidence_dir)


@pytest.fixture
def client(db_session, evidence_store, monkeypatch) -> Generator[TestClient, None, None]:
    # Override database session dependency
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Patch IngestionService in API to use our test evidence_store
    monkeypatch.setattr(
        "ulpf.api.sources.IngestionService",
        lambda: IngestionService(evidence_store=evidence_store),
    )
    monkeypatch.setattr(
        "ulpf.api.ingestion.IngestionService",
        lambda: IngestionService(evidence_store=evidence_store),
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
