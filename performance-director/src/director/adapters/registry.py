"""Builds the adapter set for the current environment: live when credentials exist,
fixture when a fixture dir is configured, otherwise UnconfiguredAdapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from director.adapters import baselinker as bl
from director.adapters import gethooked as gh
from director.adapters import meta as mt
from director.adapters import nailuks as nk
from director.adapters.base import Adapter, UnconfiguredAdapter
from director.adapters.fixture import FixtureAdapter
from director.adapters.mcp_client import MCPClient
from director.adapters.store_health import StoreHealthAdapter
from director.config import LoadedConfig, Settings
from director.contracts.envelope import SourceKind


@dataclass
class AdapterSet:
    meta: Adapter
    baselinker: Adapter
    nailuks: Adapter
    gethooked: Adapter
    store_health: Adapter
    mode: str = "unconfigured"
    notes: list[str] = field(default_factory=list)

    def by_source(self, source: SourceKind) -> Adapter:
        return {
            SourceKind.META: self.meta,
            SourceKind.BASELINKER: self.baselinker,
            SourceKind.NAILUKS: self.nailuks,
            SourceKind.GETHOOKED: self.gethooked,
            SourceKind.STORE_HEALTH: self.store_health,
        }[source]


def _fixture_normalizers() -> dict[SourceKind, dict[str, Any]]:
    attribution = mt.DEFAULT_ATTRIBUTION
    return {
        SourceKind.BASELINKER: {
            "orders": lambda raw, s: bl.normalize_orders(raw),
            "open_orders": lambda raw, s: bl.normalize_orders(raw),
            "returns": lambda raw, s: bl.normalize_returns(raw),
            "statuses": lambda raw, s: bl.normalize_statuses(raw),
        },
        SourceKind.META: {
            "account": lambda raw, s: raw.get("records", []),
            "structure": lambda raw, s: mt.normalize_structure(raw),
            "insights_daily": lambda raw, s: mt.normalize_insights(
                raw, attribution=attribution, action_report_time="conversion"
            ),
            "insights_hourly": lambda raw, s: mt.normalize_insights(
                raw, attribution=attribution, action_report_time="conversion", hourly=True
            ),
            "insights_window": lambda raw, s: mt.normalize_insights(
                raw, attribution=attribution, action_report_time="conversion"
            ),
        },
        SourceKind.NAILUKS: {
            "panel_summary": lambda raw, s: nk.normalize_panel(raw, s),
            "panel_ads": lambda raw, s: nk.normalize_panel(raw, s),
        },
        SourceKind.GETHOOKED: {
            "market_ads": lambda raw, s: gh.normalize_market_rows(
                raw if isinstance(raw, list) else raw.get("ads", []), source_label="fixture"
            )
        },
        SourceKind.STORE_HEALTH: {"health": lambda raw, s: raw.get("records", [])},
    }


def build_adapters(
    settings: Settings, config: LoadedConfig, *, fixture_dir: Path | None = None
) -> AdapterSet:
    fixture_dir = fixture_dir or settings.fixture_dir
    notes: list[str] = []
    if fixture_dir is not None:
        norms = _fixture_normalizers()
        return AdapterSet(
            meta=FixtureAdapter(SourceKind.META, mt.MetaAdapter.streams, fixture_dir, norms[SourceKind.META]),
            baselinker=FixtureAdapter(
                SourceKind.BASELINKER, bl.BaselinkerAdapter.streams, fixture_dir, norms[SourceKind.BASELINKER]
            ),
            nailuks=FixtureAdapter(
                SourceKind.NAILUKS, nk.NailuksAdapter.streams, fixture_dir, norms[SourceKind.NAILUKS]
            ),
            gethooked=FixtureAdapter(
                SourceKind.GETHOOKED, ("market_ads",), fixture_dir, norms[SourceKind.GETHOOKED]
            ),
            store_health=FixtureAdapter(
                SourceKind.STORE_HEALTH, ("health",), fixture_dir, norms[SourceKind.STORE_HEALTH]
            ),
            mode="fixture",
            notes=[f"fixture dir {fixture_dir}"],
        )

    meta: Adapter
    if settings.meta_access_token and settings.meta_api_version:
        meta = mt.MetaAdapter(settings.meta_access_token, settings.meta_api_version, settings.meta_graph_url)
    else:
        meta = UnconfiguredAdapter(
            SourceKind.META, mt.MetaAdapter.streams, "META_ACCESS_TOKEN/META_API_VERSION not set"
        )
        notes.append("meta unconfigured")

    baselinker: Adapter
    if settings.baselinker_token:
        baselinker = bl.BaselinkerAdapter(
            settings.baselinker_token, settings.baselinker_api_url, source_tz=settings.business_timezone
        )
    else:
        baselinker = UnconfiguredAdapter(
            SourceKind.BASELINKER, bl.BaselinkerAdapter.streams, "BASELINKER_TOKEN not set"
        )
        notes.append("baselinker unconfigured")

    nailuks: Adapter
    if settings.nailuks_mcp_url:
        shop_refs = {s.shop_key: s.nailuks_shop_ref or s.shop_key for s in config.shops.shops}
        nailuks = nk.NailuksAdapter(
            MCPClient(settings.nailuks_mcp_url, settings.nailuks_mcp_token), shop_refs=shop_refs
        )
    else:
        nailuks = UnconfiguredAdapter(
            SourceKind.NAILUKS, nk.NailuksAdapter.streams, "NAILUKS_MCP_URL not set"
        )
        notes.append("nailuks unconfigured")

    gethooked: Adapter
    brands = [b for basket in config.competitors.baskets for b in basket.brands]
    import_dir = settings.config_dir / "market_import"
    if settings.gethooked_mcp_url:
        gethooked = gh.GetHookedMCPAdapter(
            MCPClient(settings.gethooked_mcp_url, settings.gethooked_mcp_token), brands
        )
    elif import_dir.exists():
        gethooked = gh.ManualImportAdapter(import_dir)
        notes.append("gethooked via manual import")
    else:
        gethooked = UnconfiguredAdapter(
            SourceKind.GETHOOKED,
            ("market_ads",),
            "GETHOOKED_MCP_URL not set and no config/market_import directory",
        )
        notes.append("gethooked unavailable")

    store_health = StoreHealthAdapter({s.shop_key: s.health_urls for s in config.shops.shops})
    return AdapterSet(
        meta=meta,
        baselinker=baselinker,
        nailuks=nailuks,
        gethooked=gethooked,
        store_health=store_health,
        mode="live",
        notes=notes,
    )
