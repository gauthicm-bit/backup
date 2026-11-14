"""Multiverse REST and SSE boundary, API contract 1.0.0."""

import asyncio
import hashlib
import json
import shutil
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any
from queue import Empty
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import BackgroundTasks, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy import text
from sqlmodel import Session, select
from starlette.exceptions import HTTPException
from ulid import ULID

from app.core import db, events
from app.core.db import Audit
from app.core.settings import settings
from app.schemas import api as s
from app.worker.run_audit import run_audit, versions
from engine.backtest.presets import PRESETS
from engine.backtest.templates import TEMPLATES, expand_grid
from engine.common import EngineError
from engine.data.loader import load_prices
from engine.generators import is_available
from engine.metrics.verdict import DEFAULT_THRESHOLDS


class ApiFailure(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Multiverse",
    version="2.2.0",
    lifespan=lifespan,
    responses={code: {"model": s.ErrorResponse} for code in (404, 409, 413, 422, 500, 503)},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "details": details}},
        status_code=status,
        media_type="application/json; charset=utf-8",
    )


@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method == "POST":
        body = await request.body()
        if len(body) > 16 * 1024:
            return error_response(413, "request_too_large", "Request body exceeds 16 KB.")
    response = await call_next(request)
    if response.headers.get("content-type") == "application/json":
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


@app.exception_handler(ApiFailure)
async def api_failure(request: Request, exc: ApiFailure):
    return error_response(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_failure(request: Request, exc: RequestValidationError):
    return error_response(
        422,
        "invalid_request",
        "Check the request fields.",
        [{"loc": list(e["loc"])[1:], "msg": e["msg"]} for e in exc.errors()],
    )


@app.exception_handler(EngineError)
async def engine_failure(request: Request, exc: EngineError):
    return error_response(503 if exc.code == "market_data_unavailable" else 422, exc.code, str(exc))


@app.exception_handler(HTTPException)
async def http_failure(request: Request, exc: HTTPException):
    return error_response(exc.status_code, "invalid_request", str(exc.detail))


@app.exception_handler(Exception)
async def internal_failure(request: Request, exc: Exception):
    return error_response(500, "internal_error", "The request could not be completed.")


def find_audit(audit_id: str) -> Audit:
    with Session(db.engine) as session:
        audit = session.get(Audit, audit_id)
        if audit is None:
            raise ApiFailure(404, "audit_not_found", "Audit not found.")
        return audit


def config_hash(config: dict) -> str:
    canonical = {k: v for k, v in config.items() if k != "reuse_cached"}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_request(body: s.CreateAuditRequest) -> list[dict[str, float]]:
    # Calendar years, including leap-day clamping.
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if body.start < date(2008, 1, 1) or body.start >= today or body.end > today:
        raise ApiFailure(
            422, "invalid_date_range", "Use at least three years from 2008 through today."
        )
    try:
        minimum_end = body.start.replace(year=body.start.year + 3)
    except ValueError:
        minimum_end = body.start.replace(year=body.start.year + 3, day=28)
    if body.start < date(2008, 1, 1) or body.end > today or body.end < minimum_end:
        raise ApiFailure(
            422, "invalid_date_range", "Use at least three years from 2008 through today."
        )
    if not is_available(body.generator.type):
        raise ApiFailure(422, "generator_not_trained", "This generator is not available yet.")
    if body.generator.n_histories > settings.max_histories:
        raise ApiFailure(422, "too_many_histories", "Requested histories exceed the server limit.")
    return expand_grid(body.strategy.template, body.strategy.grid)


@app.get("/api/v1/health", response_model=s.Health)
def health():
    try:
        redis_ok = bool(events.redis_client().ping())
    except RedisError:
        redis_ok = False
    try:
        with Session(db.engine) as session:
            session.exec(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if redis_ok and db_ok else "degraded",
        "redis": "ok" if redis_ok else "down",
        "db": "ok" if db_ok else "down",
        "job_mode": settings.job_mode,
        "contract_version": "1.0.0",
    }


def ohlc_rows(prices):
    return [
        {
            "date": index.date().isoformat(),
            **{
                name: None if not np.isfinite(row[name]) else float(row[name])
                for name in ("open", "high", "low", "close", "volume")
            },
        }
        for index, row in prices.iterrows()
    ]


@app.get("/api/v1/market/prices", response_model=s.PriceResponse)
def market_prices(symbol: s.Symbol, start: date, end: date):
    if start >= end:
        raise ApiFailure(422, "invalid_date_range", "Start must precede end.")
    cache_file = settings.data_dir / "cache" / "prices" / f"{symbol}.parquet"
    prices = load_prices(symbol, start, end, cache_dir=cache_file.parent)
    return {
        "symbol": symbol,
        "start": start,
        "end": end,
        "source": prices.attrs.get("source", "cache"),
        "fetched_at": prices.attrs.get("fetched_at", db.utcnow()),
        "ohlc": ohlc_rows(prices),
    }


@app.get("/api/v1/strategies/templates", response_model=list[s.TemplateInfo])
def templates():
    output = []
    for template in TEMPLATES.values():
        grid = {p.name: p.default_values for p in template.params}
        output.append(
            {
                **asdict(template),
                "default_grid": grid,
                "default_n_variants": len(expand_grid(template.id, grid)),
            }
        )
    return output


@app.get("/api/v1/generators", response_model=list[s.GeneratorInfo])
def generators():
    output = [
        {
            "id": id,
            "name": name,
            "description": description,
            "trained": is_available(id),
            "available": is_available(id),
            "realism_passed": None,
            "trained_on": None,
        }
        for id, name, description in [
            (
                "garch",
                "GJR-GARCH",
                "Student-t innovations with asymmetric volatility, fitted per audit.",
            ),
            ("timegan", "TimeGAN", "Deep temporal generator. Coming soon."),
            ("diffusion", "Diffusion", "Diffusion market generator. Coming soon."),
        ]
    ]
    for generator in output:
        report_file = settings.data_dir / "generators" / generator["id"] / "realism.json"
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            generator["realism_passed"] = report["passed"] == report["total"]
    return output


@app.get("/api/v1/generators/{id}/realism", response_model=s.RealismReport)
def generator_realism(id: str):
    if id not in ("garch", "timegan", "diffusion"):
        raise ApiFailure(404, "generator_not_found", "Generator not found.")
    file = settings.data_dir / "generators" / id / "realism.json"
    if not file.exists():
        raise ApiFailure(409, "realism_not_ready", "Generator realism has not been built yet.")
    return json.loads(file.read_text(encoding="utf-8"))


@app.get("/api/v1/presets", response_model=list[s.Preset])
def presets():
    output = []
    with Session(db.engine) as session:
        for id, config in PRESETS.items():
            canonical = s.CreateAuditRequest.model_validate(config).model_dump(mode="json")
            cached = session.exec(
                select(Audit).where(
                    Audit.config_hash == config_hash(canonical), Audit.status == "done"
                )
            ).first()
            output.append(
                {
                    "id": id,
                    "name": "Overfit strategy" if id == "overfit" else "Slow trend baseline",
                    "description": "A broad momentum search, tested for selection bias."
                    if id == "overfit"
                    else "A small, slow moving-average grid. Robustness is a hypothesis to test.",
                    "config": canonical,
                    "cached_audit_id": cached.id if cached else None,
                }
            )
    return output


@app.post("/api/v1/audits", status_code=202, response_model=s.CreateAuditResponse)
def create_audit(body: s.CreateAuditRequest, background: BackgroundTasks, response: Response):
    variants = validate_request(body)
    config = body.model_dump(mode="json")
    hash_value = config_hash(config)
    with Session(db.engine) as session:
        if body.reuse_cached:
            cached = session.exec(
                select(Audit).where(Audit.config_hash == hash_value, Audit.status == "done")
            ).first()
            if cached:
                response.headers["Location"] = f"/api/v1/audits/{cached.id}"
                return {"audit_id": cached.id, "status": "done", "cached": True}
        if settings.job_mode == "rq":
            try:
                events.redis_client().ping()
            except RedisError:
                raise ApiFailure(
                    503, "queue_unavailable", "The audit queue is unavailable."
                ) from None
        audit = Audit(
            id=f"aud_{ULID()}", config=config, config_hash=hash_value, n_trials=len(variants)
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        audit_id = audit.id
    if settings.job_mode == "inprocess":
        background.add_task(run_audit, audit_id)
    else:
        try:
            Queue("audits", connection=events.redis_client()).enqueue(
                run_audit, audit_id, job_id=audit_id, job_timeout=900
            )
        except RedisError:
            with Session(db.engine) as session:
                session.delete(session.get(Audit, audit_id))
                session.commit()
            raise ApiFailure(503, "queue_unavailable", "The audit queue is unavailable.") from None
    response.headers["Location"] = f"/api/v1/audits/{audit_id}"
    return {"audit_id": audit_id, "status": "queued", "cached": False}


@app.get("/api/v1/audits/{id}", response_model=s.AuditDetail)
def audit_detail(id: str):
    audit = find_audit(id)
    message = events.last(id)
    persisted_config = settings.data_dir / "audits" / id / "config.json"
    recorded_versions = versions()
    if persisted_config.exists():
        recorded_versions = json.loads(persisted_config.read_text(encoding="utf-8"))["derived"][
            "versions"
        ]
    metrics = {
        name: getattr(audit, name) for name in ("pbo", "dsr_prob", "survival_rate", "n_trials")
    }
    return {
        "id": id,
        "status": audit.status,
        **{
            key: (getattr(audit, key).replace(tzinfo=timezone.utc) if getattr(audit, key) else None)
            for key in ("created_at", "started_at", "finished_at")
        },
        "config": audit.config,
        "derived": {
            "n_trials": audit.n_trials,
            "variants": expand_grid(
                audit.config["strategy"]["template"], audit.config["strategy"]["grid"]
            ),
            "selected_variant": audit.selected_variant,
            "config_hash": audit.config_hash,
            "versions": recorded_versions,
        },
        "verdict": audit.verdict,
        "headline": audit.headline,
        "metrics": metrics if audit.status == "done" else None,
        "thresholds": asdict(DEFAULT_THRESHOLDS),
        "progress": message["data"]
        if message and message["event"] == "progress" and audit.status in ("queued", "running")
        else None,
        "error": {"code": audit.error_code, "message": audit.error_message}
        if audit.status == "error"
        else None,
    }


@app.get("/api/v1/audits", response_model=s.AuditList)
def audit_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: s.AuditStatus | None = None,
):
    with Session(db.engine) as session:
        query = select(Audit)
        if status:
            query = query.where(Audit.status == status)
        rows = session.exec(query.order_by(Audit.created_at.desc())).all()
        return {
            "items": [
                {
                    "id": a.id,
                    "status": a.status,
                    "verdict": a.verdict,
                    "created_at": a.created_at.replace(tzinfo=timezone.utc),
                    "finished_at": a.finished_at.replace(tzinfo=timezone.utc)
                    if a.finished_at
                    else None,
                    **{k: a.config[k] for k in ("symbol", "start", "end")},
                    "template": a.config["strategy"]["template"],
                    "generator": a.config["generator"]["type"],
                    "n_histories": a.config["generator"]["n_histories"],
                    "n_trials": a.n_trials,
                    "metrics": {
                        k: getattr(a, k) for k in ("pbo", "dsr_prob", "survival_rate", "n_trials")
                    }
                    if a.status == "done"
                    else None,
                }
                for a in rows[offset : offset + limit]
            ],
            "total": len(rows),
            "limit": limit,
            "offset": offset,
        }


@app.delete(
    "/api/v1/audits/{id}",
    response_model=s.CancelResponse,
    responses={204: {"description": "Audit deleted"}},
)
def delete_audit(id: str):
    audit = find_audit(id)
    if audit.status in ("queued", "running"):
        events.cancel(id)
        with Session(db.engine) as session:
            row = session.get(Audit, id)
            row.status, row.finished_at = "cancelled", db.utcnow()
            session.add(row)
            session.commit()
        events.publish(id, "cancelled", {"audit_id": id})
        return {"id": id, "status": "cancelled"}
    with Session(db.engine) as session:
        row = session.get(Audit, id)
        session.delete(row)
        session.commit()
    directory = (settings.data_dir / "audits" / id).resolve()
    root = (settings.data_dir / "audits").resolve()
    if directory.parent != root:
        raise ApiFailure(500, "internal_error", "Invalid audit storage path.")
    if directory.exists():
        shutil.rmtree(directory)
    return Response(status_code=204)


@app.get("/api/v1/audits/{id}/events", response_class=StreamingResponse)
async def audit_events(id: str, request: Request):
    find_audit(id)

    def wire(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def stream():
        def terminal(audit):
            audit = find_audit(id)
            if audit.status in ("done", "error", "cancelled"):
                if audit.status == "done":
                    return wire("done", {"audit_id": id, "verdict": audit.verdict})
                elif audit.status == "error":
                    return wire("error", {"code": audit.error_code, "message": audit.error_message})
                return wire("cancelled", {"audit_id": id})
            return None

        connection = None
        local_queue = None
        try:
            if settings.job_mode == "rq":
                connection = events.redis_client().pubsub()
                connection.subscribe(f"audit:{id}")
            else:
                local_queue = events.subscribe(id)
            end = terminal(find_audit(id))
            if end:
                yield end
                return
            latest = events.last(id)
            if latest:
                yield wire(latest["event"], latest["data"])
                if latest["event"] in ("done", "error", "cancelled"):
                    return
            ping_at = time.monotonic()
            while not await request.is_disconnected():
                message = None
                if connection:
                    packet = await asyncio.to_thread(
                        connection.get_message, ignore_subscribe_messages=True, timeout=0.2
                    )
                    if packet:
                        message = json.loads(packet["data"])
                else:
                    try:
                        message = local_queue.get_nowait()
                    except Empty:
                        pass
                if message and message != latest:
                    yield wire(message["event"], message["data"])
                    latest = message
                    if message["event"] in ("done", "error", "cancelled"):
                        return
                if time.monotonic() - ping_at >= 15:
                    yield ": ping\n\n"
                    ping_at = time.monotonic()
                await asyncio.sleep(0.1)
        finally:
            if connection:
                connection.close()
            if local_queue:
                events.unsubscribe(id, local_queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def chart_payload(id: str, name: str):
    audit = find_audit(id)
    if audit.status != "done":
        raise ApiFailure(409, "chart_not_ready", "Charts are available when the audit finishes.")
    path = settings.data_dir / "audits" / id / "charts" / f"{name}.json"
    if not path.exists():
        raise ApiFailure(409, "chart_not_ready", "This audit's chart has not been built.")
    return json.loads(path.read_text(encoding="utf-8"))


def register_chart(path: str, name: str, model):
    def get_chart(id: str):
        return chart_payload(id, name)

    get_chart.__name__ = f"chart_{name}"
    app.get(f"/api/v1/audits/{{id}}/charts/{path}", response_model=model)(get_chart)


for path, name, model in [
    ("fan", "fan", s.FanChart),
    ("fan/paths", "fan_paths", s.FanPaths),
    ("sharpe", "sharpe", s.SharpeChart),
    ("pbo", "pbo", s.PBOChart),
    ("dsr", "dsr", s.DSRChart),
    ("survival", "survival", s.SurvivalChart),
    ("realism", "realism", s.RealismReport),
    ("price", "price", s.PriceChart),
]:
    register_chart(path, name, model)
