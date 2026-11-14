"""Prepare real demo artifacts using the same engine and worker as the API."""

import argparse
import json
from datetime import date

from sqlmodel import Session, select
from ulid import ULID

from app.core import db
from app.core.db import Audit
from app.core.settings import settings
from app.schemas.api import CreateAuditRequest
from app.worker.run_audit import run_audit
from engine.aggregate import realism_report, write_charts
from engine.backtest.presets import PRESETS
from engine.data.loader import load_prices, log_returns
from engine.generators import get_generator
from engine.realism.stylized_facts import run_realism


def warm_presets() -> None:
    from app.main import config_hash, validate_request

    db.init_db()
    for id, body in PRESETS.items():
        request = CreateAuditRequest.model_validate(body)
        variants = validate_request(request)
        config = request.model_dump(mode="json")
        hash_value = config_hash(config)
        with Session(db.engine) as session:
            cached = session.exec(
                select(Audit).where(Audit.config_hash == hash_value, Audit.status == "done")
            ).first()
            if cached:
                print(f"{id}: cached {cached.id} — {cached.verdict}", flush=True)
                continue
            audit = Audit(
                id=f"aud_{ULID()}", config=config, config_hash=hash_value, n_trials=len(variants)
            )
            session.add(audit)
            session.commit()
            session.refresh(audit)
            audit_id = audit.id
        run_audit(audit_id)
        with Session(db.engine) as session:
            audit = session.get(Audit, audit_id)
            print(
                json.dumps(
                    {
                        "preset": id,
                        "audit_id": audit_id,
                        "status": audit.status,
                        "verdict": audit.verdict,
                        "pbo": audit.pbo,
                        "dsr_prob": audit.dsr_prob,
                        "survival_rate": audit.survival_rate,
                        "error": audit.error_message,
                    }
                ),
                flush=True,
            )
            if audit.status != "done":
                raise RuntimeError(f"Preset {id} failed: {audit.error_message}")


def build_realism() -> None:
    prices = load_prices(
        "^NSEI",
        date(2010, 1, 1),
        date(2025, 12, 31),
        cache_dir=settings.data_dir / "cache" / "prices",
    )
    real = log_returns(prices.close)
    paths = get_generator("garch").fit(real).sample(500, len(real), 42)
    report = realism_report(run_realism(real, paths), "garch", 500)
    write_charts(settings.data_dir / "generators" / "garch", {"realism": report})
    print(f"GARCH realism: {report['passed']}/{report['total']} tests passed", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["warm-presets", "build-realism", "export-openapi"])
    args = parser.parse_args()
    if args.command == "warm-presets":
        warm_presets()
    elif args.command == "build-realism":
        build_realism()
    else:
        from app.main import app
        from pathlib import Path

        Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
