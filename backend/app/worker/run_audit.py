"""Single worker entry point for RQ and in-process audits (§4.2)."""

import importlib.metadata
import json
import logging
import platform
from datetime import date

import numpy as np
import pandas as pd
from sqlmodel import Session
from rq.timeouts import JobTimeoutException

from app.core import db, events
from app.core.db import Audit, utcnow
from app.core.settings import settings
from engine.backtest.runner import run_backtest
from engine.aggregate.charts import build_charts, write_charts
from engine.backtest.templates import expand_grid
from engine.common import Cancelled, EngineError
from engine.data.loader import load_prices, log_returns
from engine.generators import get_generator
from engine.metrics.dsr import compute_dsr
from engine.metrics.pbo import compute_pbo
from engine.metrics.survival import compute_survival, compute_survival_rate
from engine.metrics.verdict import decide_verdict
from engine.realism.stylized_facts import run_realism

logger = logging.getLogger(__name__)


def versions() -> dict[str, str]:
    result = {"python": platform.python_version(), "app": "2.2.0"}
    for name in ("numpy", "pandas", "arch"):
        result[name] = importlib.metadata.version(name)
    return result


def run_audit(audit_id: str) -> None:
    stage = "fetch"

    def progress(fraction: float) -> None:
        if events.is_cancelled(audit_id):
            raise Cancelled()
        events.publish(
            audit_id,
            "progress",
            {
                "stage": stage,
                "pct": int(np.clip(fraction, 0, 1) * 100),
                "message": {
                    "fetch": "Loading Nifty 50 market history",
                    "simulate": "Generating alternate market histories",
                    "backtest": "Testing strategy variants after costs",
                    "metrics": "Measuring evidence of skill",
                }[stage],
                "ts": utcnow().isoformat().replace("+00:00", "Z"),
            },
        )

    try:
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            if audit is None or audit.status != "queued":
                return
            audit.status = "running"
            audit.started_at = utcnow()
            session.add(audit)
            session.commit()
            config = audit.config
            hash_value = audit.config_hash
        progress(0)
        prices = load_prices(
            config["symbol"],
            date.fromisoformat(config["start"]),
            date.fromisoformat(config["end"]),
            cache_dir=settings.data_dir / "cache" / "prices",
        )
        real = log_returns(prices.close)
        progress(1)
        stage = "simulate"
        progress(0)
        generator = get_generator(config["generator"]["type"]).fit(real)
        paths = generator.sample(
            config["generator"]["n_histories"], len(real), config["generator"]["seed"]
        )
        directory = settings.data_dir / "audits" / audit_id
        directory.mkdir(parents=True, exist_ok=True)
        path_frame = pd.DataFrame(
            paths.T.astype("float32"), columns=[f"p{i:04d}" for i in range(len(paths))]
        )
        path_frame.insert(0, "date", prices.index[1:])
        path_frame.to_parquet(directory / "paths.parquet", index=False)
        progress(1)
        stage = "backtest"
        progress(0)
        variants = expand_grid(config["strategy"]["template"], config["strategy"]["grid"])
        result = run_backtest(
            float(prices.close.iloc[0]),
            real,
            paths,
            config["strategy"]["template"],
            variants,
            config["costs_bps"],
            progress=progress,
        )
        ret_frame = pd.DataFrame(
            result.strat_ret_real, columns=[f"v{i:02d}" for i in range(len(variants))]
        )
        ret_frame.insert(0, "date", prices.index[1:])
        ret_frame.to_parquet(directory / "returns_real.parquet", index=False)
        sharpe_frame = pd.DataFrame(
            result.sharpe_paths, columns=[f"v{i:02d}" for i in range(len(variants))]
        )
        sharpe_frame.insert(0, "path", range(len(paths)))
        sharpe_frame.to_parquet(directory / "sharpe_matrix.parquet", index=False)
        selected = {
            "index": result.selected,
            "params": variants[result.selected],
            "real_sharpe": float(result.sharpe_real[result.selected]),
        }
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            if audit is None:
                raise Cancelled()
            audit.selected_variant = selected
            session.add(audit)
            session.commit()
        progress(1)
        stage = "metrics"
        progress(0)
        pbo = compute_pbo(result.strat_ret_real, progress=lambda x: progress(x * 0.3))
        dsr = compute_dsr(result.strat_ret_real, result.selected)
        survival = compute_survival(paths, result.strat_ret_paths_selected)
        rate = compute_survival_rate(
            result.sharpe_paths[:, result.selected], result.bh_sharpe_paths
        )
        verdict = decide_verdict(pbo.pbo, dsr.dsr_prob, rate, len(paths))
        realism = run_realism(real, paths, progress=lambda x: progress(0.3 + x * 0.5))
        charts = build_charts(
            prices, result, pbo, dsr, survival, realism, rate, config["generator"]["type"]
        )
        write_charts(directory / "charts", charts)
        derived = {
            "n_trials": len(variants),
            "variants": variants,
            "selected_variant": selected,
            "config_hash": hash_value,
            "versions": versions(),
        }
        (directory / "config.json").write_text(
            json.dumps({**config, "derived": derived}, allow_nan=False), encoding="utf-8"
        )
        progress(1)
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            if audit is None or audit.status == "cancelled":
                raise Cancelled()
            audit.status = "done"
            audit.verdict, audit.headline = verdict.verdict, verdict.headline
            audit.pbo, audit.dsr_prob, audit.survival_rate = pbo.pbo, dsr.dsr_prob, rate
            audit.finished_at = utcnow()
            session.add(audit)
            session.commit()
        events.publish(audit_id, "done", {"audit_id": audit_id, "verdict": verdict.verdict})
    except Cancelled:
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            if audit is not None and audit.status in ("queued", "running"):
                audit.status, audit.finished_at = "cancelled", utcnow()
                session.add(audit)
                session.commit()
        events.publish(audit_id, "cancelled", {"audit_id": audit_id})
    except Exception as exc:
        logger.exception("Audit %s failed in %s", audit_id, stage)
        code = (
            exc.code
            if isinstance(exc, EngineError)
            else {
                "simulate": "generator_failed",
                "backtest": "backtest_failed",
                "metrics": "metrics_failed",
            }.get(stage, "internal_error")
        )
        if isinstance(exc, (TimeoutError, JobTimeoutException)):
            code = "timeout"
        message = str(exc) if isinstance(exc, EngineError) else f"The {stage} stage failed."
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            if audit is not None and audit.status in ("queued", "running"):
                audit.status, audit.error_code, audit.error_message = "error", code, message
                audit.finished_at = utcnow()
                session.add(audit)
                session.commit()
            elif audit is None or audit.status in ("done", "cancelled"):
                return
        events.publish(audit_id, "error", {"code": code, "message": message})
