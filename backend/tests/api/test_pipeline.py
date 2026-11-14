"""Gate 1: real GARCH, worker and API against the genuine committed cache."""

import os
from pathlib import Path

os.environ["JOB_MODE"] = "inprocess"

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app.core import db, events
from app.core.settings import settings
from app.main import app


def test_garch_audit_through_api(tmp_path, monkeypatch):
    import shutil

    cache = tmp_path / "cache" / "prices"
    shutil.copytree(Path("data/cache/prices"), cache)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "job_mode", "inprocess")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    SQLModel.metadata.create_all(engine)
    emitted = []
    original = events.publish

    def record(id, event, data):
        emitted.append((event, data))
        original(id, event, data)

    monkeypatch.setattr(events, "publish", record)
    with TestClient(app) as client:
        body = {
            "start": "2010-01-01",
            "end": "2025-12-31",
            "strategy": {
                "template": "ma_crossover",
                "grid": {"fast": [5, 10, 20, 30], "slow": [50, 100, 150, 200]},
            },
            "generator": {"type": "garch", "n_histories": 100, "seed": 42},
            "costs_bps": 5,
        }
        response = client.post("/api/v1/audits", json=body)
        assert response.status_code == 202, response.text
        id = response.json()["audit_id"]
        detail = client.get(f"/api/v1/audits/{id}").json()
        assert detail["status"] == "done", detail
        assert detail["metrics"] is not None
        stages = list(dict.fromkeys(d["stage"] for e, d in emitted if e == "progress"))
        assert stages == ["fetch", "simulate", "backtest", "metrics"]
        for stage in stages:
            percentages = [d["pct"] for e, d in emitted if e == "progress" and d["stage"] == stage]
            assert percentages[0] == 0 and percentages[-1] == 100
            assert percentages == sorted(percentages)
        stream = client.get(f"/api/v1/audits/{id}/events")
        assert "event: done" in stream.text
        assert stream.headers["x-accel-buffering"] == "no"
        assert (tmp_path / "audits" / id / "paths.parquet").exists()
        again = client.post("/api/v1/audits", json=body).json()
        assert again == {"audit_id": id, "status": "done", "cached": True}
        names = ["fan", "fan/paths", "sharpe", "pbo", "dsr", "survival", "realism", "price"]
        payloads = {}
        for name in names:
            chart = client.get(f"/api/v1/audits/{id}/charts/{name}")
            assert chart.status_code == 200, chart.text
            payloads[name] = chart.content
            if name != "price":
                assert len(chart.content) <= 50_000
        # Forced recomputation must yield byte-identical charts and metrics (§1, §4.4).
        body["reuse_cached"] = False
        rerun = client.post("/api/v1/audits", json=body).json()
        second_id = rerun["audit_id"]
        second = client.get(f"/api/v1/audits/{second_id}").json()
        assert second["metrics"] == detail["metrics"]
        assert second["derived"]["config_hash"] == detail["derived"]["config_hash"]
        for name in names:
            assert client.get(f"/api/v1/audits/{second_id}/charts/{name}").content == payloads[name]
