"""`director` CLI (see README). All commands are read-only towards shops/Meta: OBSERVE mode has no write path."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select, text

from director.config import get_settings

app = typer.Typer(
    help="AI E-commerce Performance Director", no_args_is_help=True, pretty_exceptions_enable=False
)
db_app = typer.Typer(help="database")
demo_app = typer.Typer(help="offline demo")
run_app = typer.Typer(help="workflows")
connectors_app = typer.Typer(help="source connectors")
decisions_app = typer.Typer(help="decision journal")
costs_app = typer.Typer(help="cost versions")
report_app = typer.Typer(help="reports")
for name, sub in (
    ("db", db_app),
    ("demo", demo_app),
    ("run", run_app),
    ("connectors", connectors_app),
    ("decisions", decisions_app),
    ("costs", costs_app),
    ("report", report_app),
):
    app.add_typer(sub, name=name)

DEMO_FIXTURES = Path("var/fixtures/demo")


def _services(mode: str | None = None, fixture_dir: Path | None = None):
    from director.services import build_services

    settings = get_settings()
    if mode == "fixture":
        fixture_dir = fixture_dir or settings.fixture_dir or DEMO_FIXTURES
        if not fixture_dir.exists():
            typer.echo(f"fixture dir {fixture_dir} missing - run `director demo seed` first", err=True)
            raise typer.Exit(2)
    elif mode == "live":
        fixture_dir = None
    else:
        fixture_dir = settings.fixture_dir
    return build_services(settings, fixture_dir=fixture_dir)


def _parse_day(value: str) -> date:
    if value == "yesterday":
        s = get_settings()
        from director.metrics.calendar import business_date_of

        return business_date_of(datetime.now(UTC), s.business_timezone) - timedelta(days=1)
    return date.fromisoformat(value)


@db_app.command("migrate")
def db_migrate() -> None:
    """Apply Alembic migrations to DATABASE_URL."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    os.environ.setdefault("DATABASE_URL", get_settings().database_url)
    command.upgrade(cfg, "head")
    typer.echo("migrations applied")


@demo_app.command("seed")
def demo_seed(
    end_day: Annotated[
        str, typer.Option(help="last business day of the fixtures (default: yesterday)")
    ] = "yesterday",
    fixture_dir: Annotated[Path, typer.Option()] = DEMO_FIXTURES,
) -> None:
    """Generate deterministic fixtures + seed costs and historical observations."""
    from director.demo.seed import generate, seed_historical_observations
    from director.ingestion.sync import ensure_reference_data
    from director.metrics.costs import import_costs_yaml

    day = _parse_day(end_day)
    summary = generate(fixture_dir, end_day=day)
    svc = _services("fixture", fixture_dir)
    with svc.session_factory() as s:
        shops = ensure_reference_data(s, svc)
        import_costs_yaml(
            s,
            svc.settings.config_dir
            / ("costs.yaml" if (svc.settings.config_dir / "costs.yaml").exists() else "costs.example.yaml"),
        )
        from director.db.models import HistoricalObservation

        if s.execute(select(HistoricalObservation)).first() is None:
            seed_historical_observations(s, shops)
        s.commit()
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    typer.echo(f"\nnext: uv run director run daily --date {day.isoformat()} --mode fixture")


@run_app.command("daily")
def run_daily(
    date_: Annotated[str, typer.Option("--date")] = "yesterday",
    mode: Annotated[str, typer.Option(help="fixture | live")] = "live",
    first_import: Annotated[bool, typer.Option(help="pull FIRST_IMPORT_DAYS of history")] = False,
    print_report: bool = True,
) -> None:
    """Run the full daily workflow for one business date and print the report."""
    from director import pipeline

    svc = _services(mode)
    day = _parse_day(date_)
    if mode == "fixture":  # freeze the clock just after the fixture day so 'as_of' is coherent
        frozen = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC) + timedelta(
            hours=5, minutes=30
        )
        svc.set_clock(lambda: frozen)
    rid = pipeline.run_daily(svc, day, first_import=first_import)
    with svc.session_factory() as s:
        from director.db.models import Report

        rep = s.get(Report, rid)
        typer.echo(
            f"report {rep.id} revision={rep.revision} status={rep.status} completeness={rep.completeness}"
        )
        if print_report:
            typer.echo(rep.rendered_markdown)


@run_app.command("weekly")
def run_weekly(week_end: Annotated[str, typer.Option()] = "yesterday", mode: str = "live") -> None:
    from director import pipeline

    svc = _services(mode)
    day = _parse_day(week_end)
    if mode == "fixture":
        svc.set_clock(
            lambda: (
                datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
                + timedelta(hours=6)
            )
        )
    rid = pipeline.run_weekly(svc, day)
    with svc.session_factory() as s:
        from director.db.models import Report

        typer.echo(s.get(Report, rid).rendered_markdown)


@run_app.command("intraday")
def run_intraday(mode: str = "live") -> None:
    from director import pipeline

    svc = _services(mode)
    if (
        mode == "fixture"
    ):  # pretend 'now' is shortly after the last successful sync so freshness checks are meaningful
        from sqlalchemy import func

        from director.db.models import SyncCheckpoint

        with svc.session_factory() as s:
            last = s.execute(select(func.max(SyncCheckpoint.last_success_at))).scalar()
        if last:
            svc.set_clock(lambda: last + timedelta(minutes=10))
    typer.echo(json.dumps(pipeline.run_intraday(svc), indent=2, default=str))


@run_app.command("review-decisions")
def run_review(mode: str = "live") -> None:
    from director import pipeline

    typer.echo(json.dumps(pipeline.review_decisions(_services(mode))))


@connectors_app.command("discover")
def connectors_discover(read_only: Annotated[bool, typer.Option("--read-only")] = True) -> None:
    """List capabilities/health of every configured source; persist MCP tool schemas + hashes."""
    from director.adapters.mcp_client import schema_hash
    from director.db.models import ConnectorCapability

    svc = _services()
    out: dict = {"mode": svc.adapters.mode, "notes": svc.adapters.notes, "sources": {}}
    with svc.session_factory() as s:
        for name in ("meta", "baselinker", "nailuks", "gethooked", "store_health"):
            adapter = getattr(svc.adapters, name)
            try:
                health = adapter.healthcheck()
                caps = adapter.discover_capabilities()
            except Exception as exc:  # noqa: BLE001
                out["sources"][name] = {"error": str(exc)[:300]}
                continue
            for c in caps:
                h = schema_hash(c.input_schema)
                if (
                    s.execute(
                        select(ConnectorCapability).where(
                            ConnectorCapability.source == name,
                            ConnectorCapability.tool_name == c.tool_name,
                            ConnectorCapability.schema_hash == h,
                        )
                    ).scalar_one_or_none()
                    is None
                ):
                    s.add(
                        ConnectorCapability(
                            source=name,
                            tool_name=c.tool_name,
                            description=c.description,
                            input_schema=c.input_schema,
                            schema_hash=h,
                            read_only_hint=c.read_only_hint,
                            discovered_at=datetime.now(UTC),
                        )
                    )
            out["sources"][name] = {
                "status": health.status.value,
                "detail": health.detail,
                "tools": [c.tool_name for c in caps],
            }
        s.commit()
    typer.echo(json.dumps(out, indent=2, ensure_ascii=False))


@app.command("sync")
def sync(
    days: int = 90, read_only: Annotated[bool, typer.Option("--read-only")] = True, mode: str = "live"
) -> None:
    """Initial import: structure, insights and orders for the last N days (read-only)."""
    from director import pipeline

    svc = _services(mode)
    day = pipeline.yesterday(svc)
    svc.settings.first_import_days = days
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        out = pipeline.sync_all(s, svc, day=day, lookback_days=days, first_import=True)
        s.commit()
    typer.echo(json.dumps(out, indent=2, default=str, ensure_ascii=False))


@app.command("doctor")
def doctor() -> None:
    """Check DB/migrations, timezone, config, credentials presence (never values), source freshness, mapping, last jobs, report channel."""
    from director.db.base import get_engine
    from director.db.models import JobRun, Report, SourceAccount, SyncCheckpoint

    settings = get_settings()
    checks: list[tuple[str, str, str]] = []
    try:
        with get_engine(settings.database_url).connect() as c:
            head = c.execute(text("select version_num from alembic_version")).scalar()
            checks.append(("db", "OK", f"connected; alembic={head}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("db", "FAIL", str(exc)[:200]))
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(settings.business_timezone)
        checks.append(("timezone", "OK", settings.business_timezone))
    except Exception as exc:  # noqa: BLE001
        checks.append(("timezone", "FAIL", str(exc)))
    try:
        svc = _services()
        checks.append(
            (
                "config",
                "OK",
                f"{len(svc.config.shops.shops)} shops, {len(svc.config.schedules.entries)} schedules, adapters={svc.adapters.mode}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(("config", "FAIL", str(exc)[:200]))
        svc = None
    for var in (
        "APP_AUTH_SECRET",
        "APP_ADMIN_PASSWORD",
        "BASELINKER_TOKEN",
        "META_ACCESS_TOKEN",
        "META_API_VERSION",
        "NAILUKS_MCP_URL",
        "GETHOOKED_MCP_URL",
        "LLM_API_KEY",
    ):
        checks.append(
            (
                f"secret:{var}",
                "SET" if os.environ.get(var) or getattr(settings, var.lower(), "") else "MISSING",
                "value hidden",
            )
        )
    checks.append(
        (
            "mode",
            "OK" if settings.mode == "OBSERVE" else "WARN",
            f"MODE={settings.mode} execution_enabled={settings.execution_enabled} kill_switch={settings.kill_switch}",
        )
    )
    checks.append(
        (
            "llm",
            "OK" if settings.llm_provider != "none" else "INFO",
            f"provider={settings.llm_provider} model={settings.llm_model or '-'} budget={settings.llm_daily_budget_pln} PLN/day",
        )
    )
    checks.append(
        (
            "notifications",
            "OK",
            f"channel={settings.notification_channel} (external channels need an authorized recipient)",
        )
    )
    if svc is not None:
        try:
            with svc.session_factory() as s:
                accts = s.execute(select(SourceAccount)).scalars().all()
                unmapped = [a.external_id for a in accts if a.shop_id is None]
                unverified = [a.external_id for a in accts if a.mapping_verified_at is None]
                checks.append(
                    (
                        "mapping",
                        "WARN" if unverified or unmapped else "OK",
                        f"{len(accts)} accounts; unmapped={unmapped}; unverified={len(unverified)} (verify live IDs before first production report)",
                    )
                )
                cps = s.execute(select(SyncCheckpoint)).scalars().all()
                stale = [
                    f"{cp.stream}"
                    for cp in cps
                    if cp.last_success_at is None
                    or (datetime.now(UTC) - cp.last_success_at)
                    > timedelta(minutes=settings.lookback_days * 0 + 180)
                ]
                checks.append(
                    ("freshness", "WARN" if stale else "OK", f"{len(cps)} checkpoints; stale={stale[:6]}")
                )
                last_jobs = (
                    s.execute(select(JobRun).order_by(JobRun.scheduled_for.desc()).limit(5)).scalars().all()
                )
                checks.append(
                    (
                        "jobs",
                        "OK",
                        ", ".join(f"{j.job_name}={j.status}" for j in last_jobs) or "no job runs yet",
                    )
                )
                rep = s.execute(select(Report).order_by(Report.as_of.desc()).limit(1)).scalar_one_or_none()
                checks.append(
                    (
                        "last_report",
                        "OK" if rep else "INFO",
                        f"{rep.kind} {rep.period_start} {rep.status}/{rep.completeness}" if rep else "none",
                    )
                )
            for name in ("meta", "baselinker", "nailuks", "gethooked"):
                h = getattr(svc.adapters, name).healthcheck()
                checks.append((f"source:{name}", h.status.value, h.detail[:120]))
        except Exception as exc:  # noqa: BLE001
            checks.append(("runtime", "FAIL", str(exc)[:200]))
    width = max(len(c[0]) for c in checks)
    for name, status, detail in checks:
        typer.echo(f"{name.ljust(width)}  {status.ljust(12)} {detail}")
    if any(c[1] == "FAIL" for c in checks):
        raise typer.Exit(1)


@costs_app.command("import")
def costs_import(path: Path) -> None:
    from director.metrics.costs import import_costs_yaml

    svc = _services()
    with svc.session_factory() as s:
        from director.ingestion.sync import ensure_reference_data

        ensure_reference_data(s, svc)
        n = import_costs_yaml(s, path)
        s.commit()
    typer.echo(f"imported {n} new cost versions from {path}")


@report_app.command("show")
def report_show(
    date_: Annotated[str, typer.Option("--date")] = "latest", kind: str = "daily", fmt: str = "md"
) -> None:
    from director import pipeline

    svc = _services()
    with svc.session_factory() as s:
        rep = pipeline.latest_report(s, kind, None if date_ == "latest" else date.fromisoformat(date_))
        if rep is None:
            typer.echo("no report")
            raise typer.Exit(1)
        typer.echo(rep.rendered_html if fmt == "html" else rep.rendered_markdown)


@decisions_app.command("list")
def decisions_list(status: str | None = None) -> None:
    from director.db.models import Decision

    svc = _services()
    with svc.session_factory() as s:
        q = select(Decision).order_by(Decision.proposed_at.desc()).limit(50)
        if status:
            q = q.where(Decision.status == status)
        for d in s.execute(q).scalars():
            typer.echo(f"{d.id}  {d.status:<11} {d.action_type:<26} {d.entity_ref:<40} {d.reason[:80]}")


@decisions_app.command("approve")
def decisions_approve(decision_id: str, actor: str = "owner-cli") -> None:
    from director.db.models import Decision
    from director.decisions import journal

    svc = _services()
    with svc.session_factory() as s:
        d = s.get(Decision, uuid.UUID(decision_id))
        journal.approve(s, d, actor=actor, now=svc.now(), correlation_id=uuid.uuid4().hex)
        s.commit()
        typer.echo(
            f"approved {d.id} (OBSERVE mode: execution still requires a separate, explicitly enabled action request)"
        )


@decisions_app.command("reject")
def decisions_reject(decision_id: str, reason: str = "", actor: str = "owner-cli") -> None:
    from director.db.models import Decision
    from director.decisions import journal

    svc = _services()
    with svc.session_factory() as s:
        d = s.get(Decision, uuid.UUID(decision_id))
        journal.reject(s, d, actor=actor, now=svc.now(), correlation_id=uuid.uuid4().hex, reason=reason)
        s.commit()
        typer.echo(f"rejected {d.id}")


@app.command("scheduler")
def scheduler(once: bool = False, tick_seconds: int = 30) -> None:
    """Compute due jobs and enqueue them (safe to run several instances)."""
    import time

    from director.jobs.scheduler import tick

    svc = _services()
    since = datetime.now(UTC) - timedelta(minutes=5)
    scopes = {
        "shop": [c.shop_key for c in svc.config.shops.shops if c.active],
        "source_account": [c.meta_account_id for c in svc.config.shops.shops if c.meta_account_id],
    }
    while True:
        now = datetime.now(UTC)
        with svc.session_factory() as s:
            n = tick(s, svc.config.schedules, since=since, until=now, scopes=scopes)
        since = now
        typer.echo(f"{now.isoformat()} enqueued {n}")
        if once:
            break
        time.sleep(tick_seconds)


@app.command("worker")
def worker(once: bool = False) -> None:
    """Claim and execute jobs (safe to run several instances)."""
    from director.jobs.worker import Worker
    from director.jobs.workflows import HANDLERS

    svc = _services()
    w = Worker(
        svc.session_factory,
        HANDLERS,
        svc,
        lease_seconds=svc.settings.worker_lease_seconds,
        poll_seconds=svc.settings.worker_poll_seconds,
    )
    if once:
        typer.echo("processed" if w.run_once() else "no due jobs")
        return
    typer.echo(f"worker {w.owner} started")
    w.run_forever()


@app.command("api")
def api(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("director.api.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
