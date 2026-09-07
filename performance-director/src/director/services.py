"""Dependency container shared by CLI, API, workers and tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from director.adapters.registry import AdapterSet, build_adapters
from director.config import LoadedConfig, Settings, get_settings, load_config
from director.db.base import SessionFactory


@dataclass
class Services:
    settings: Settings
    config: LoadedConfig
    session_factory: sessionmaker[Session]
    adapters: AdapterSet
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def now(self) -> datetime:
        return self.clock()

    def set_clock(self, clock: Callable[[], datetime]) -> None:
        self.clock = clock
        _bind_clock(self)

    @property
    def tz(self) -> str:
        return self.settings.business_timezone


def build_services(
    settings: Settings | None = None,
    *,
    fixture_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Services:
    settings = settings or get_settings()
    config = load_config(settings.config_dir)
    adapters = build_adapters(settings, config, fixture_dir=fixture_dir)
    svc = Services(
        settings=settings,
        config=config,
        session_factory=SessionFactory(settings.database_url),
        adapters=adapters,
    )
    if clock is not None:
        svc.clock = clock
    _bind_clock(svc)
    return svc


def _bind_clock(svc: Services) -> None:
    """Fixture adapters stamp envelopes with the service clock so replays are coherent with `as_of`."""
    for name in ("meta", "baselinker", "nailuks", "gethooked", "store_health"):
        adapter = getattr(svc.adapters, name)
        if hasattr(adapter, "clock"):
            adapter.clock = svc.now
