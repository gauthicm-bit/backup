"""REST contracts §§5–8. Tests use isolated SQLite and in-process jobs."""

import os

os.environ["JOB_MODE"] = "inprocess"

from fastapi.testclient import TestClient
import pytest
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core import db
from app.core.settings import settings
from app.core.db import Audit
from sqlmodel import Session


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "job_mode", "inprocess")
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def request_body():
    return {
        "start": "2010-01-01",
        "end": "2025-12-31",
        "strategy": {"template": "ma_crossover", "grid": {"fast": [5, 10], "slow": [50]}},
        "generator": {"n_histories": 100, "seed": 42},
    }


def test_health_and_catalogue(client):
    health = client.get("/api/v1/health").json()
    assert health["contract_version"] == "1.0.0"
    assert health["job_mode"] == "inprocess"
    templates = client.get("/api/v1/strategies/templates").json()
    assert [t["default_n_variants"] for t in templates] == [16, 12, 8, 8]
    generators = client.get("/api/v1/generators").json()
    assert [g["available"] for g in generators] == [True, False, False]


@pytest.mark.parametrize(
    "change,code",
    [
        ({"start": "2007-01-01"}, "invalid_date_range"),
        ({"end": "2011-01-01"}, "invalid_date_range"),
        ({"costs_bps": -1}, "invalid_request"),
        (
            {"strategy": {"template": "ma_crossover", "grid": {"fast": [5], "slow": [50]}}},
            "invalid_grid",
        ),
        ({"generator": {"type": "timegan"}}, "generator_not_trained"),
    ],
)
def test_validation_error_envelope(client, request_body, change, code):
    response = client.post("/api/v1/audits", json={**request_body, **change})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_not_found_and_body_limit(client):
    assert client.get("/api/v1/audits/missing").json()["error"]["code"] == "audit_not_found"
    assert client.get("/api/v1/generators/nope/realism").status_code == 404
    assert client.get("/api/v1/generators/garch/realism").status_code == 409
    assert client.post("/api/v1/audits", content="x" * 16385).status_code == 413


def test_openapi_complete(client):
    schema = client.get("/openapi.json").json()
    assert "AuditDetail" in schema["components"]["schemas"]
    assert "CreateAuditRequest" in schema["components"]["schemas"]
    for name in (
        "FanChart",
        "FanPaths",
        "PBOChart",
        "SurvivalChart",
        "RealismReport",
        "PriceChart",
        "AuditList",
        "CancelResponse",
        "FieldError",
        "ErrorResponse",
    ):
        assert name in schema["components"]["schemas"]


def test_list_cancel_delete_and_chart_errors(client, request_body):
    from app.main import config_hash
    from app.schemas.api import CreateAuditRequest

    config = CreateAuditRequest.model_validate(request_body).model_dump(mode="json")
    with Session(db.engine) as session:
        session.add(
            Audit(id="aud_test", config=config, config_hash=config_hash(config), n_trials=2)
        )
        session.commit()
    listed = client.get("/api/v1/audits?status=queued&limit=1").json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == "aud_test"
    assert client.get("/api/v1/audits/aud_test/charts/fan").status_code == 409
    assert client.get("/api/v1/audits/missing/charts/fan").status_code == 404
    response = client.delete("/api/v1/audits/aud_test")
    assert response.json() == {"id": "aud_test", "status": "cancelled"}
    stream = client.get("/api/v1/audits/aud_test/events")
    assert "event: cancelled" in stream.text
    assert client.delete("/api/v1/audits/aud_test").status_code == 204
    assert client.get("/api/v1/audits/aud_test").status_code == 404


def test_market_validation_and_limits(client, request_body, monkeypatch):
    assert (
        client.get("/api/v1/market/prices?symbol=^NSEI&start=2020-01-01&end=2019-01-01").status_code
        == 422
    )
    monkeypatch.setattr(settings, "max_histories", 100)
    request_body["generator"]["n_histories"] = 500
    assert (
        client.post("/api/v1/audits", json=request_body).json()["error"]["code"]
        == "too_many_histories"
    )


def test_queue_outage(client, request_body, monkeypatch):
    from app.core import events
    from redis.exceptions import ConnectionError

    monkeypatch.setattr(settings, "job_mode", "rq")

    class Down:
        def ping(self):
            raise ConnectionError()

    monkeypatch.setattr(events, "redis_client", lambda: Down())
    response = client.post("/api/v1/audits", json=request_body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"


def test_worker_failure_is_audit_error_and_terminal_event(client, request_body, monkeypatch):
    import importlib
    from engine.common import MarketDataUnavailable

    worker = importlib.import_module("app.worker.run_audit")

    def unavailable(*args, **kwargs):
        raise MarketDataUnavailable("Market prices unavailable")

    monkeypatch.setattr(worker, "load_prices", unavailable)
    response = client.post("/api/v1/audits", json=request_body)
    assert response.status_code == 202
    id = response.json()["audit_id"]
    detail = client.get(f"/api/v1/audits/{id}").json()
    assert detail["status"] == "error"
    assert detail["error"]["code"] == "market_data_unavailable"
    assert detail["metrics"] is None and detail["verdict"] is None
    assert '"code": "market_data_unavailable"' in client.get(f"/api/v1/audits/{id}/events").text


@pytest.mark.parametrize("failure,expected", [("cancel", "cancelled"), ("timeout", "error")])
def test_worker_interruptions(client, request_body, monkeypatch, failure, expected):
    import importlib
    from engine.common import Cancelled

    worker = importlib.import_module("app.worker.run_audit")

    def interrupted(*args, **kwargs):
        raise Cancelled() if failure == "cancel" else TimeoutError()

    monkeypatch.setattr(worker, "load_prices", interrupted)
    id = client.post("/api/v1/audits", json=request_body).json()["audit_id"]
    detail = client.get(f"/api/v1/audits/{id}").json()
    assert detail["status"] == expected
    assert detail["finished_at"] is not None
    if failure == "timeout":
        assert detail["error"]["code"] == "timeout"
