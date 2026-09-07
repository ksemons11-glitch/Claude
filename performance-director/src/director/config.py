"""Runtime settings (environment) and versioned YAML configuration.

Secrets come exclusively from the environment. YAML files hold thresholds and
mappings; every loaded YAML is also snapshotted into the database (policy_snapshots)
so a report can always be traced to the configuration it was produced under.
"""

from __future__ import annotations

import hashlib
import json
from datetime import time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    OBSERVE = "OBSERVE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    LIMITED_AUTOPILOT = "LIMITED_AUTOPILOT"


class Settings(BaseSettings):
    """Process configuration. Every secret defaults to empty -> connector UNCONFIGURED."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://director:director@localhost:5432/director"
    app_base_url: str = "http://localhost:8000"
    app_auth_secret: str = ""
    app_admin_user: str = "admin"
    app_admin_password: str = ""
    app_api_token: str = ""
    business_timezone: str = "Europe/Warsaw"
    report_currency: str = "PLN"
    mode: Mode = Mode.OBSERVE
    execution_enabled: bool = False
    kill_switch: bool = False
    config_dir: Path = Path("config")
    fixture_dir: Path | None = None

    nailuks_mcp_url: str = ""
    nailuks_mcp_token: str = ""
    baselinker_token: str = ""
    baselinker_api_url: str = "https://api.baselinker.com/connector.php"
    meta_access_token: str = ""
    meta_api_version: str = ""
    meta_graph_url: str = "https://graph.facebook.com"
    gethooked_mcp_url: str = ""
    gethooked_mcp_token: str = ""

    llm_provider: Literal["none", "fake", "anthropic"] = "none"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_daily_budget_pln: Decimal = Decimal("0")
    llm_max_evidence_items: int = 120
    llm_max_output_tokens: int = 2000
    notification_channel: str = "in_app"

    raw_retention_days: int = 90
    metrics_retention_months: int = 24
    lookback_days: int = 28
    first_import_days: int = 90
    worker_lease_seconds: int = 300
    worker_poll_seconds: float = 2.0

    @property
    def test_mode(self) -> bool:
        return self.fixture_dir is not None


def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------- YAML configuration models


class ShopConfig(BaseModel):
    shop_key: str
    name: str
    domain: str
    timezone: str = "Europe/Warsaw"
    currency: str = "PLN"
    active: bool = True
    order_date_basis: Literal["created", "confirmed"] = "confirmed"
    tax_basis: Literal["net", "gross"] = "gross"
    meta_account_id: str | None = None
    meta_account_ui_name: str | None = None
    baselinker_shop_id: str | None = None
    nailuks_shop_ref: str | None = None
    aliases: list[str] = Field(default_factory=list)
    health_urls: list[str] = Field(default_factory=list)
    valid_order_statuses: list[str] = Field(default_factory=list)
    cancelled_statuses: list[str] = Field(default_factory=list)
    returned_statuses: list[str] = Field(default_factory=list)
    delivered_statuses: list[str] = Field(default_factory=list)


class ShopsConfig(BaseModel):
    version: str = "1"
    shops: list[ShopConfig]

    def by_key(self, key: str) -> ShopConfig:
        for s in self.shops:
            if s.shop_key == key:
                return s
        raise KeyError(key)


class ProductPolicy(BaseModel):
    """Per-product economics guard rails. `null` means 'not configured' -> gate blocks."""

    product_key: str
    shop_key: str
    test_loss_cap_pln: Decimal | None = None
    target_cpa_pln: Decimal | None = None
    max_daily_budget_pln: Decimal | None = None


class IntradayPolicy(BaseModel):
    consecutive_reads_required: int = 2
    cooldown_hours: int = 4
    min_history_days: int = 14
    min_daily_orders_for_business_signal: int = 8
    max_source_lag_minutes: int = 45


class ThresholdsPolicy(BaseModel):
    attribution_coverage_min: Decimal = Decimal("0.80")
    min_full_days_since_change: int = 3
    min_purchases_for_cpa_compare: int = 10
    concentration_alert_share: Decimal = Decimal("0.70")
    change_cooldown_hours: int = 72
    max_actions_per_report: int = 5
    robust_z_watch: Decimal = Decimal("2.0")
    robust_z_critical: Decimal = Decimal("3.5")
    min_baseline_days: int = 7
    low_sample_orders: int = 30
    source_freshness_minutes: int = 180
    spend_multiple_of_target_cpa_alert: Decimal = Decimal("2.0")


class ExecutionLimits(BaseModel):
    max_budget_change_pct_per_operation: Decimal = Decimal("0.15")
    max_daily_change_pct_per_account: Decimal = Decimal("0.25")
    max_rolling_24h_total_change_pln: Decimal = Decimal("0")
    portfolio_daily_cap_pln: Decimal | None = None
    approval_ttl_minutes: int = 120
    cooldown_hours_after_change: int = 72
    allowed_accounts: list[str] = Field(default_factory=list)


class PoliciesConfig(BaseModel):
    version: str = "1"
    thresholds: ThresholdsPolicy = Field(default_factory=ThresholdsPolicy)
    intraday: IntradayPolicy = Field(default_factory=IntradayPolicy)
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)
    products: list[ProductPolicy] = Field(default_factory=list)
    cash_reserve_pln: Decimal | None = None
    cod_settlement_lag_days: int | None = None

    def product(self, shop_key: str, product_key: str) -> ProductPolicy | None:
        for p in self.products:
            if p.shop_key == shop_key and p.product_key == product_key:
                return p
        return None


class ScheduleEntry(BaseModel):
    job: str
    every_minutes: int | None = None
    at: list[str] = Field(default_factory=list)  # "HH:MM" local business time
    days: list[str] = Field(default_factory=list)  # mon..sun; empty = every day
    scope: Literal["global", "shop", "source_account"] = "global"
    enabled: bool = True
    timeout_seconds: int = 900
    max_attempts: int = 5

    @field_validator("at")
    @classmethod
    def _validate_at(cls, v: list[str]) -> list[str]:
        for item in v:
            time.fromisoformat(item)
        return v


class SchedulesConfig(BaseModel):
    version: str = "1"
    timezone: str = "Europe/Warsaw"
    entries: list[ScheduleEntry]


class CompetitorBasket(BaseModel):
    basket: Literal["direct", "adjacent", "dtc"]
    brands: list[str]
    countries: list[str] = Field(default_factory=lambda: ["PL"])


class CompetitorsConfig(BaseModel):
    version: str = "1"
    baskets: list[CompetitorBasket] = Field(default_factory=list)
    scan_days: list[str] = Field(default_factory=lambda: ["mon", "wed", "fri"])


class LoadedConfig(BaseModel):
    shops: ShopsConfig
    policies: PoliciesConfig
    schedules: SchedulesConfig
    competitors: CompetitorsConfig
    hashes: dict[str, str]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def _hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _resolve(config_dir: Path, name: str) -> Path:
    """Prefer `<name>.yaml`; fall back to `<name>.example.yaml` (fixture/demo)."""
    real = config_dir / f"{name}.yaml"
    if real.exists():
        return real
    example = config_dir / f"{name}.example.yaml"
    if example.exists():
        return example
    raise FileNotFoundError(f"missing {real} (and no {example})")


def load_config(config_dir: Path) -> LoadedConfig:
    raw = {
        name: _read_yaml(_resolve(config_dir, name))
        for name in ("shops", "policies", "schedules", "competitors")
    }
    return LoadedConfig(
        shops=ShopsConfig.model_validate(raw["shops"]),
        policies=PoliciesConfig.model_validate(raw["policies"]),
        schedules=SchedulesConfig.model_validate(raw["schedules"]),
        competitors=CompetitorsConfig.model_validate(raw["competitors"]),
        hashes={k: _hash(v) for k, v in raw.items()},
    )
