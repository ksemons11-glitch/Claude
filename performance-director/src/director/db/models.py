"""SQLAlchemy models. Money = NUMERIC(20,6) + currency; timestamps timestamptz UTC + business_date."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from director.db.base import Base, TenantMixin

Money = Numeric(20, 6)
UUIDT = UUID(as_uuid=True)
TS = DateTime(timezone=True)


# ---------------------------------------------------------------------------- reference


class Shop(TenantMixin, Base):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("tenant_id", "shop_key", name="uq_shops_tenant_key"),)
    shop_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Warsaw")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_date_basis: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    tax_basis: Mapped[str] = mapped_column(String(8), nullable=False, default="gross")
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class SourceAccount(TenantMixin, Base):
    __tablename__ = "source_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "external_id", name="uq_source_accounts"),)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id"), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    config_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mapping_verified_at: Mapped[datetime | None] = mapped_column(TS)


class Product(TenantMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "shop_id", "product_key", name="uq_products_key"),)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    product_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Variant(TenantMixin, Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("tenant_id", "product_id", "sku", name="uq_variants_sku"),)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    stock_qty: Mapped[int | None] = mapped_column(Integer)
    stock_as_of: Mapped[datetime | None] = mapped_column(TS)


class ProductAlias(TenantMixin, Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source", "external_product_id", "valid_from", name="uq_product_aliases"
        ),
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("variants.id"))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class CostVersion(TenantMixin, Base):
    __tablename__ = "cost_versions"
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("variants.id"))
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    cost_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # COGS, SHIPPING, RETURN_SHIPPING, FULFILLMENT, PAYMENT_FEE, COD_FEE, OTHER_VARIABLE
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    tax_basis: Mapped[str] = mapped_column(String(8), nullable=False, default="gross")
    basis: Mapped[str] = mapped_column(
        String(16), nullable=False, default="per_unit"
    )  # per_unit | per_order | pct_of_revenue
    payment_kind: Mapped[str | None] = mapped_column(String(16))  # COD / PREPAID / None=any
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    provenance: Mapped[str] = mapped_column(String(200), nullable=False, default="owner_config")
    recovery_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))  # share of COGS recovered on return


class HistoricalObservation(TenantMixin, Base):
    """Facts from historical notes (e.g. 30.08-07.09) - NOT current snapshots."""

    __tablename__ = "historical_observations"
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id"))
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OBSERVATION"
    )  # OBSERVATION | PLAN | HYPOTHESIS
    text: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class PolicySnapshot(TenantMixin, Base):
    __tablename__ = "policy_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "name", "config_hash", name="uq_policy_snapshots"),)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")


# ---------------------------------------------------------------------------- connectors / ingestion


class ConnectorCapability(TenantMixin, Base):
    __tablename__ = "connector_capabilities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "tool_name", "schema_hash", name="uq_connector_caps"),
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    read_only_hint: Mapped[bool | None] = mapped_column(Boolean)
    discovered_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IngestionBatch(TenantMixin, Base):
    __tablename__ = "ingestion_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_hash", "fetched_at", name="uq_ingestion_batches"),
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    stream: Mapped[str] = mapped_column(String(64), nullable=False)
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_accounts.id"))
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_signature: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    range_start: Mapped[date | None] = mapped_column(Date)
    range_end: Mapped[date | None] = mapped_column(Date)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_uri: Mapped[str | None] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")
    pagination_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fetched_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(TS)


class SyncCheckpoint(TenantMixin, Base):
    __tablename__ = "sync_checkpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_account_id", "stream", name="uq_sync_checkpoints"),
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    stream: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(500))
    high_watermark: Mapped[datetime | None] = mapped_column(TS)
    last_success_at: Mapped[datetime | None] = mapped_column(TS)
    last_attempt_at: Mapped[datetime | None] = mapped_column(TS)
    last_error: Mapped[str | None] = mapped_column(Text)
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------- ad structure


class Campaign(TenantMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("tenant_id", "source_account_id", "external_id", name="uq_campaigns"),)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str | None] = mapped_column(String(64))
    configured_status: Mapped[str | None] = mapped_column(String(32))
    effective_status: Mapped[str | None] = mapped_column(String(32))
    daily_budget: Mapped[Decimal | None] = mapped_column(Money)
    lifetime_budget: Mapped[Decimal | None] = mapped_column(Money)
    budget_type: Mapped[str | None] = mapped_column(String(8))  # CBO | ABO
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(TS)


class AdSet(TenantMixin, Base):
    __tablename__ = "adsets"
    __table_args__ = (UniqueConstraint("tenant_id", "source_account_id", "external_id", name="uq_adsets"),)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    configured_status: Mapped[str | None] = mapped_column(String(32))
    effective_status: Mapped[str | None] = mapped_column(String(32))
    daily_budget: Mapped[Decimal | None] = mapped_column(Money)
    lifetime_budget: Mapped[Decimal | None] = mapped_column(Money)
    targeting: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(TS)


class Ad(TenantMixin, Base):
    __tablename__ = "ads"
    __table_args__ = (UniqueConstraint("tenant_id", "source_account_id", "external_id", name="uq_ads"),)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    adset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("adsets.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    configured_status: Mapped[str | None] = mapped_column(String(32))
    effective_status: Mapped[str | None] = mapped_column(String(32))
    post_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    asset_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    destination_url: Mapped[str | None] = mapped_column(Text)
    url_tags: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(TS)


class EntitySnapshot(TenantMixin, Base):
    __tablename__ = "entity_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity_type", "entity_id", "attributes_hash", "valid_at", name="uq_entity_snapshots"
        ),
    )
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUIDT, nullable=False, index=True)
    valid_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attributes_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_batches.id"))


class StructureChange(TenantMixin, Base):
    """Derived from snapshot diffs. `derivation='snapshot_diff'` -> not a full audit history."""

    __tablename__ = "structure_changes"
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUIDT, nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    before: Mapped[Any] = mapped_column(JSONB)
    after: Mapped[Any] = mapped_column(JSONB)
    observed_from: Mapped[datetime] = mapped_column(TS, nullable=False)
    observed_to: Mapped[datetime] = mapped_column(TS, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(64))
    derivation: Mapped[str] = mapped_column(String(32), nullable=False, default="snapshot_diff")
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_batches.id"))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUIDT)


class AdInsight(TenantMixin, Base):
    __tablename__ = "ad_insights"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "ad_id",
            "business_date",
            "hour",
            "breakdown_key",
            "attribution_key",
            name="uq_ad_insights",
        ),
    )
    ad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ads.id"), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)  # -1 = whole day
    breakdown_key: Mapped[str] = mapped_column(String(128), nullable=False, default="none")
    attribution_key: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    action_report_time: Mapped[str] = mapped_column(String(16), nullable=False, default="conversion")
    spend: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reach: Mapped[int | None] = mapped_column(Integer)  # window-level only; never summed across days
    clicks_all: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_clicks: Mapped[int | None] = mapped_column(Integer)
    landing_page_views: Mapped[int | None] = mapped_column(Integer)
    add_to_cart: Mapped[int | None] = mapped_column(Integer)
    initiate_checkout: Mapped[int | None] = mapped_column(Integer)
    purchases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_value: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    actions_raw: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_batches.id"))
    as_of: Mapped[datetime] = mapped_column(TS, nullable=False)


# ---------------------------------------------------------------------------- orders ledger


class Order(TenantMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_account_id", "external_order_id", name="uq_orders"),
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False, index=True)
    external_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at_source: Mapped[datetime] = mapped_column(TS, nullable=False)
    confirmed_at_source: Mapped[datetime | None] = mapped_column(TS)
    paid_at_source: Mapped[datetime | None] = mapped_column(TS)
    business_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )  # by shop's order_date_basis
    payment_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # COD | PREPAID | UNKNOWN
    payment_method: Mapped[str | None] = mapped_column(String(64))
    current_status: Mapped[str] = mapped_column(String(64), nullable=False)
    status_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="OPEN"
    )  # OPEN|DELIVERED|CANCELLED|UNDELIVERED|RETURNED|VALID
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    products_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    shipping_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    discount_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_utm: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    customer_hash: Mapped[str | None] = mapped_column(String(64))  # pseudonymous; no PII stored
    source_payload_hash: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    matured_at: Mapped[datetime | None] = mapped_column(TS)

    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(TenantMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("tenant_id", "order_id", "source_line_id", name="uq_order_items"),)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    source_line_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(128))
    sku: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(300))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("variants.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_gross: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    discount_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    bundle_key: Mapped[str | None] = mapped_column(String(64))
    returned_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusEvent(TenantMixin, Base):
    __tablename__ = "order_status_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "source_event_hash", name="uq_order_status_events"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    source_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    before_status: Mapped[str | None] = mapped_column(String(64))
    after_status: Mapped[str] = mapped_column(String(64), nullable=False)
    after_class: Mapped[str] = mapped_column(String(16), nullable=False)


class Refund(TenantMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "external_id", name="uq_refunds"),)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    refund_type: Mapped[str] = mapped_column(String(16), nullable=False)  # FULL | PARTIAL | UNDELIVERED
    goods_recovered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    return_shipping_cost: Mapped[Decimal | None] = mapped_column(Money)


class Settlement(TenantMixin, Base):
    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "external_id", name="uq_settlements"),)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # COD_PAYOUT | CARD | REFUND_OUT | FEE


class OrderCost(TenantMixin, Base):
    __tablename__ = "order_costs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "order_item_id", "cost_type", name="uq_order_costs"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("order_items.id"))
    cost_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_actual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_versions.id"))
    recognition_date: Mapped[date] = mapped_column(Date, nullable=False)


class OrderAttribution(TenantMixin, Base):
    __tablename__ = "order_attribution"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "model_version", name="uq_order_attribution"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_accounts.id"))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    adset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("adsets.id"))
    ad_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ads.id"))
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # AD | ADSET | CAMPAIGN | UNKNOWN
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_class: Mapped[str] = mapped_column(String(8), nullable=False)
    parsed_utm: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    parser_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")


# ---------------------------------------------------------------------------- metrics


class CohortMetric(TenantMixin, Base):
    __tablename__ = "cohort_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "entity_key", "cohort_date", "as_of", name="uq_cohort_metrics"
        ),
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # shop | product
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    cohort_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    as_of: Mapped[datetime] = mapped_column(TS, nullable=False)
    age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    orders: Mapped[int] = mapped_column(Integer, nullable=False)
    ordered_revenue: Mapped[Decimal] = mapped_column(Money, nullable=False)
    expected_revenue: Mapped[Decimal | None] = mapped_column(Money)
    expected_costs: Mapped[Decimal | None] = mapped_column(Money)
    expected_contribution: Mapped[Decimal | None] = mapped_column(Money)
    expected_low: Mapped[Decimal | None] = mapped_column(Money)
    expected_high: Mapped[Decimal | None] = mapped_column(Money)
    realized_revenue: Mapped[Decimal | None] = mapped_column(Money)
    realized_costs: Mapped[Decimal | None] = mapped_column(Money)
    realized_contribution: Mapped[Decimal | None] = mapped_column(Money)
    ad_spend: Mapped[Decimal | None] = mapped_column(Money)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW_SAMPLE")
    model_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class DailyMetric(TenantMixin, Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scope",
            "entity_key",
            "business_date",
            "metric",
            "metric_version",
            "as_of",
            name="uq_daily_metrics",
        ),
        Index("ix_daily_metrics_lookup", "scope", "entity_key", "metric", "business_date"),
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    as_of: Mapped[datetime] = mapped_column(TS, nullable=False)
    numerator: Mapped[Decimal | None] = mapped_column(Money)
    denominator: Mapped[Decimal | None] = mapped_column(Money)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    reason: Mapped[str | None] = mapped_column(String(64))
    quality: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")
    evidence_id: Mapped[str] = mapped_column(String(160), nullable=False)


class DataQualityIssue(TenantMixin, Base):
    __tablename__ = "data_quality_issues"
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    expected: Mapped[Any] = mapped_column(JSONB)
    actual: Mapped[Any] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    business_date: Mapped[date | None] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)


# ---------------------------------------------------------------------------- creatives & market


class Concept(TenantMixin, Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("tenant_id", "concept_key", name="uq_concepts"),)
    concept_key: Mapped[str] = mapped_column(String(128), nullable=False)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    problem_desire: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    classification_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class Creative(TenantMixin, Base):
    __tablename__ = "creatives"
    __table_args__ = (UniqueConstraint("tenant_id", "creative_key", name="uq_creatives"),)
    creative_key: Mapped[str] = mapped_column(String(128), nullable=False)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    concept_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("concepts.id"))
    asset_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    post_id: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    hook: Mapped[str | None] = mapped_column(Text)
    angle: Mapped[str | None] = mapped_column(String(200))
    format: Mapped[str | None] = mapped_column(String(64))
    actor: Mapped[str | None] = mapped_column(String(120))
    length_seconds: Mapped[int | None] = mapped_column(Integer)
    offer: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    status_reason: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(TS)
    classification_confidence: Mapped[str | None] = mapped_column(String(8))
    classification_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    classification_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CreativeVariant(TenantMixin, Base):
    __tablename__ = "creative_variants"
    creative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creatives.id"), nullable=False)
    parent_creative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("creatives.id"))
    variation_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # actor | hook | edit | cta | format
    classification_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")


class CreativePlacement(TenantMixin, Base):
    __tablename__ = "creative_placements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "creative_id", "ad_id", "valid_from", name="uq_creative_placements"),
    )
    creative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creatives.id"), nullable=False, index=True)
    ad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ads.id"), nullable=False, index=True)
    post_id: Mapped[str | None] = mapped_column(String(128))
    valid_from: Mapped[datetime] = mapped_column(TS, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TS)


class MarketAd(TenantMixin, Base):
    __tablename__ = "market_ads"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "external_id", name="uq_market_ads"),)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    brand: Mapped[str] = mapped_column(String(200), nullable=False)
    basket: Mapped[str | None] = mapped_column(String(16))
    media_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    media_ref: Mapped[str | None] = mapped_column(String(500))
    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)
    countries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    taxonomy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("concepts.id"))
    transcript_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MarketObservation(TenantMixin, Base):
    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "market_ad_id", "observed_on", name="uq_market_observations"),
    )
    market_ad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("market_ads.id"), nullable=False, index=True)
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    coverage: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_batches.id"))


class MarketSignal(TenantMixin, Base):
    __tablename__ = "market_signals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "concept_id", "window_start", "window_end", name="uq_market_signals"),
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    coverage: Mapped[str] = mapped_column(String(16), nullable=False)  # FULL | PARTIAL
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trend_score: Mapped[int | None] = mapped_column(Integer)
    fit_to_product: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    novelty_for_us: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    source_observation_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


# ---------------------------------------------------------------------------- decisions


class Recommendation(TenantMixin, Base):
    __tablename__ = "recommendations"
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"))
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fact: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    priority_class: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_class: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence_components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_score: Mapped[int | None] = mapped_column(Integer)
    gates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    blocking_gates: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    impact: Mapped[str] = mapped_column(String(8), nullable=False, default="LOW")
    urgency: Mapped[str] = mapped_column(String(8), nullable=False, default="LOW")
    effort: Mapped[str] = mapped_column(String(8), nullable=False, default="LOW")
    execution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alternative: Mapped[str] = mapped_column(Text, nullable=False, default="Bez zmian")
    conditions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    next_check_at: Mapped[datetime | None] = mapped_column(TS)
    expires_at: Mapped[datetime | None] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PROPOSED")


class Experiment(TenantMixin, Base):
    __tablename__ = "experiments"
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # CREATIVE | BUDGET | PRICE | OFFER | AUDIENCE
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_pln: Mapped[Decimal | None] = mapped_column(Money)
    loss_cap_pln: Mapped[Decimal | None] = mapped_column(Money)
    baseline: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    start_at: Mapped[datetime | None] = mapped_column(TS)
    end_at: Mapped[datetime | None] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PLANNED")
    overlap_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    similarity_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    repeat_reason: Mapped[str | None] = mapped_column(Text)


class Decision(TenantMixin, Base):
    __tablename__ = "decisions"
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recommendations.id"))
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("experiments.id"))
    entity_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    entity_ids: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(64))
    state_before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state_after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    data_as_of: Mapped[datetime] = mapped_column(TS, nullable=False)
    expected_effect: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False, default="expected_contribution")
    target: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    risk: Mapped[str | None] = mapped_column(Text)
    test_budget_pln: Mapped[Decimal | None] = mapped_column(Money)
    loss_cap_pln: Mapped[Decimal | None] = mapped_column(Money)
    success_criterion: Mapped[str | None] = mapped_column(Text)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=168)
    alternative: Mapped[str] = mapped_column(Text, nullable=False, default="Bez zmian")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PROPOSED")
    proposed_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    approved_by: Mapped[str | None] = mapped_column(String(120))
    rejected_at: Mapped[datetime | None] = mapped_column(TS)
    executed_at: Mapped[datetime | None] = mapped_column(TS)
    verified_executed_at: Mapped[datetime | None] = mapped_column(TS)
    execution_kind: Mapped[str | None] = mapped_column(String(16))  # MANUAL | EXECUTOR
    outcome: Mapped[str | None] = mapped_column(String(16))
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    expires_at: Mapped[datetime | None] = mapped_column(TS)


class DecisionEvaluation(TenantMixin, Base):
    __tablename__ = "decision_evaluations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "decision_id", "horizon_hours", "as_of", name="uq_decision_evals"),
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped[datetime] = mapped_column(TS, nullable=False)
    outcomes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confounders: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    verdict: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # SUCCESS | INCONCLUSIVE | FAILURE | PENDING
    observational_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------- offers


class Offer(TenantMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("tenant_id", "shop_id", "offer_key", name="uq_offers"),)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    offer_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")


class OfferVersion(TenantMixin, Base):
    __tablename__ = "offer_versions"
    __table_args__ = (UniqueConstraint("tenant_id", "offer_id", "version", name="uq_offer_versions"),)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    price_gross: Mapped[Decimal] = mapped_column(Money, nullable=False)
    reference_price_gross: Mapped[Decimal | None] = mapped_column(Money)
    reference_price_basis: Mapped[str | None] = mapped_column(String(200))  # source of the reference price
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    bundle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    shipping_rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    landing_url: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime | None] = mapped_column(TS)
    valid_to: Mapped[datetime | None] = mapped_column(TS)
    inventory_rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    note: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------- execution / ops


class ActionRequest(TenantMixin, Base):
    __tablename__ = "action_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_action_requests_idem"),)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decisions.id"), nullable=False)
    target: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # exact IDs
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    before_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    precondition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PREVIEW")
    policy_checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    approval_expires_at: Mapped[datetime | None] = mapped_column(TS)
    executed_at: Mapped[datetime | None] = mapped_column(TS)
    verified_at: Mapped[datetime | None] = mapped_column(TS)
    verification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class Report(TenantMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kind", "period_start", "period_end", "scope", "revision", name="uq_reports"
        ),
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # daily | weekly | intraday
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision_reason: Mapped[str | None] = mapped_column(Text)
    as_of: Mapped[datetime] = mapped_column(TS, nullable=False)
    completeness: Mapped[str] = mapped_column(String(16), nullable=False)  # COMPLETE | PARTIAL | FAILED
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_bundle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rendered_markdown: Mapped[str | None] = mapped_column(Text)
    rendered_html: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    llm_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_error: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_pln: Mapped[Decimal | None] = mapped_column(Money)
    missing: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class JobRun(TenantMixin, Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_name", "scheduled_for", "scope", name="uq_job_runs"),
    )
    job_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scheduled_for: Mapped[datetime] = mapped_column(TS, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False, default="global")
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[datetime | None] = mapped_column(TS)
    heartbeat_at: Mapped[datetime | None] = mapped_column(TS)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_class: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Alert(TenantMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("tenant_id", "dedupe_key", name="uq_alerts_dedupe"),)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    episode_key: Mapped[str] = mapped_column(String(128), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    consecutive_reads: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(TS)
    recovered_at: Mapped[datetime | None] = mapped_column(TS)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING"
    )  # PENDING | ACTIVE | RECOVERED


class NotificationOutbox(TenantMixin, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (UniqueConstraint("tenant_id", "dedupe_key", name="uq_notification_outbox"),)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # report | alert
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"))
    alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alerts.id"))
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="in_app")
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_id: Mapped[str | None] = mapped_column(String(200))
    delivered_at: Mapped[datetime | None] = mapped_column(TS)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    last_error: Mapped[str | None] = mapped_column(Text)


class AuditEvent(TenantMixin, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_hash: Mapped[str | None] = mapped_column(String(64))
    after_hash: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
