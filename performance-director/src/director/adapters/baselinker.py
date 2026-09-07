"""Baselinker connector (https://api.baselinker.com). Read-only methods only.

Request contract (documented): POST connector.php, header X-BLToken, form fields
`method` and `parameters` (JSON). getOrders returns at most 100 orders per call.

Pagination strategy: keep the date filter constant and advance `id_from` to
(last order_id + 1). Order IDs are monotonic, so orders sharing a timestamp never
cause a skip or an infinite loop; results are also de-duplicated by order_id.
This contract was written from the public documentation and MUST be verified
against a live token (see SETUP_REQUIRED.md).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.adapters.http import RetryingClient
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind
from director.jobs.worker import PermanentError, RetryableError
from director.metrics.calendar import business_date_of

PAGE_SIZE = 100
MAX_PAGES = 2000
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_id", "utm_term", "utm_content", "fbclid")


def _ts(value: Any) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return None


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _payment_kind(order: dict[str, Any]) -> str:
    cod = str(order.get("payment_method_cod", "")).lower()
    if cod in ("1", "true", "yes"):
        return "COD"
    if cod in ("0", "false", "no"):
        return "PREPAID"
    method = str(order.get("payment_method", "")).lower()
    if "pobran" in method or "cod" in method or "cash on delivery" in method:
        return "COD"
    return "UNKNOWN" if not method else "PREPAID"


def extract_utm(order: dict[str, Any]) -> dict[str, str]:
    """Look for UTM parameters in the documented free-form fields. Which field the shop
    actually uses must be confirmed during discovery; we record whatever we find verbatim."""
    found: dict[str, str] = {}
    candidates: list[Any] = [
        order.get("custom_extra_fields"),
        order.get("extra_field_1"),
        order.get("extra_field_2"),
        order.get("order_source_info"),
        order.get("user_comments"),
    ]
    for cand in candidates:
        if isinstance(cand, dict):
            for k, v in cand.items():
                lk = str(k).lower()
                if lk in UTM_KEYS and v not in (None, ""):
                    found.setdefault(lk, str(v))
                elif isinstance(v, str) and "utm_" in v:
                    found.update(_parse_query_like(v))
        elif isinstance(cand, str) and "utm_" in cand:
            for k, v in _parse_query_like(cand).items():
                found.setdefault(k, v)
    return found


def _parse_query_like(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if "?" in text:
        text = text.split("?", 1)[1]
    for part in text.replace("\n", "&").replace(";", "&").split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            if k in UTM_KEYS:
                out[k] = v.strip()
    return out


def normalize_orders(payload: dict[str, Any], *, source_tz: str = "Europe/Warsaw") -> list[dict[str, Any]]:
    """Map a getOrders response to the internal order record. Idempotent and pure."""
    records: list[dict[str, Any]] = []
    for o in payload.get("orders", []) or []:
        created = _ts(o.get("date_add"))
        confirmed = _ts(o.get("date_confirmed"))
        if created is None:
            continue
        items = []
        products_amount = Decimal("0")
        for p in o.get("products", []) or []:
            qty = int(p.get("quantity") or 0)
            unit = _dec(p.get("price_brutto"))
            products_amount += unit * qty
            items.append(
                {
                    "line_id": str(p.get("order_product_id") or f"{p.get('product_id')}-{p.get('sku')}"),
                    "external_product_id": str(p.get("product_id") or "") or None,
                    "sku": p.get("sku") or None,
                    "name": p.get("name"),
                    "quantity": qty,
                    "unit_price_gross": str(unit),
                    "tax_rate": str(_dec(p.get("tax_rate")) / 100)
                    if p.get("tax_rate") not in (None, "")
                    else None,
                    "bundle_key": str(p.get("bundle_id"))
                    if p.get("bundle_id") not in (None, 0, "0", "")
                    else None,
                }
            )
        shipping = _dec(o.get("delivery_price"))
        email = str(o.get("email") or "")
        phone = str(o.get("phone") or "")
        customer_hash = (
            hashlib.sha256((email.lower() + "|" + phone).encode()).hexdigest() if (email or phone) else None
        )
        pub = {
            k: v
            for k, v in o.items()
            if k
            not in (
                "email",
                "phone",
                "delivery_fullname",
                "delivery_address",
                "invoice_fullname",
                "invoice_address",
                "delivery_city",
                "invoice_city",
                "delivery_postcode",
                "invoice_postcode",
                "invoice_nip",
                "user_login",
                "delivery_company",
                "invoice_company",
            )
        }
        payload_hash = hashlib.sha256(json.dumps(pub, sort_keys=True, default=str).encode()).hexdigest()
        rec = {
            "external_order_id": str(o["order_id"]),
            "created_at": created.isoformat(),
            "confirmed_at": confirmed.isoformat() if confirmed else None,
            "paid_at": None,
            "payment_done": _dec(o.get("payment_done")),
            "payment_method": o.get("payment_method"),
            "payment_kind": _payment_kind(o),
            "currency": (o.get("currency") or "PLN").upper(),
            "status_id": str(o.get("order_status_id")),
            "status_changed_at": (_ts(o.get("date_in_status")) or created).isoformat(),
            "confirmed": bool(o.get("confirmed", True)),
            "products_amount": str(products_amount),
            "shipping_amount": str(shipping),
            "discount_amount": "0",
            "gross_amount": str(products_amount + shipping),
            "items": items,
            "utm": extract_utm(o),
            "customer_hash": customer_hash,
            "is_test": False,
            "payload_hash": payload_hash,
            "_date": business_date_of(confirmed or created, source_tz).isoformat(),
        }
        records.append(rec)
    return records


def normalize_returns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map getOrderReturns-style rows to internal refund records."""
    out: list[dict[str, Any]] = []
    for r in payload.get("returns", []) or []:
        occurred = _ts(r.get("date_add")) or datetime.now(UTC)
        amount = Decimal("0")
        for p in r.get("products", []) or []:
            amount += _dec(p.get("price_brutto")) * int(p.get("quantity") or 0)
        if r.get("refund_amount") not in (None, ""):
            amount = _dec(r.get("refund_amount"))
        out.append(
            {
                "external_id": str(r.get("return_id") or r.get("id")),
                "external_order_id": str(r.get("order_id")),
                "occurred_at": occurred.isoformat(),
                "amount": str(amount),
                "currency": (r.get("currency") or "PLN").upper(),
                "refund_type": str(
                    r.get("refund_type") or ("UNDELIVERED" if r.get("undelivered") else "FULL")
                ).upper(),
                "goods_recovered": bool(r.get("goods_recovered", True)),
                "return_shipping_cost": str(_dec(r.get("return_shipping_cost")))
                if r.get("return_shipping_cost") not in (None, "")
                else None,
                "_date": occurred.date().isoformat(),
            }
        )
    return out


def normalize_statuses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "status_id": str(s.get("id")),
            "name": s.get("name"),
            "name_for_customer": s.get("name_for_customer"),
        }
        for s in payload.get("statuses", []) or []
    ]


class BaselinkerAdapter:
    source = SourceKind.BASELINKER
    streams = ("orders", "open_orders", "returns", "statuses")

    def __init__(
        self,
        token: str,
        api_url: str,
        *,
        http: RetryingClient | None = None,
        source_tz: str = "Europe/Warsaw",
    ):
        if not token:
            raise PermanentError("BASELINKER_TOKEN missing")
        self.token = token
        self.api_url = api_url
        self.http = http or RetryingClient(timeout=60)
        self.source_tz = source_tz

    def _call(self, method: str, parameters: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.request(
            "POST",
            self.api_url,
            headers={"X-BLToken": self.token},
            data={"method": method, "parameters": json.dumps(parameters)},
        )
        try:
            body = resp.json()
        except ValueError as exc:
            raise RetryableError(f"Baselinker returned non-JSON for {method}") from exc
        if body.get("status") != "SUCCESS":
            code = str(body.get("error_code", ""))
            msg = f"Baselinker {method}: {code} {body.get('error_message', '')}"
            if code in ("ERROR_AUTH_TOKEN", "ERROR_UNKNOWN_METHOD", "ERROR_BAD_TOKEN"):
                raise PermanentError(msg)
            if code in ("ERROR_RATE_LIMIT",):
                raise RetryableError(msg, retry_after=60)
            raise RetryableError(msg)
        return body

    def discover_capabilities(self) -> list[Capability]:
        return [
            Capability(
                "getOrders",
                "orders list, max 100 per call",
                {
                    "properties": {
                        "date_confirmed_from": {},
                        "date_from": {},
                        "id_from": {},
                        "order_id": {},
                        "get_unconfirmed_orders": {},
                        "include_custom_extra_fields": {},
                    }
                },
                True,
            ),
            Capability("getOrderStatusList", "order status dictionary", {}, True),
            Capability(
                "getOrderReturns",
                "returns module (optional)",
                {"properties": {"date_from": {}, "order_id": {}}},
                True,
            ),
        ]

    def healthcheck(self) -> HealthResult:
        started = datetime.now(UTC)
        try:
            self._call("getOrderStatusList", {})
        except PermanentError as exc:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, str(exc))
        except RetryableError as exc:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, str(exc))
        return HealthResult(
            self.source, DataStatus.OK, "ok", (datetime.now(UTC) - started).total_seconds() * 1000
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        return normalize_orders(raw, source_tz=self.source_tz)

    def _envelope(
        self,
        request: SyncRequest,
        records: list[dict[str, Any]],
        *,
        complete: bool,
        warnings: list[str],
        status: DataStatus = DataStatus.OK,
    ) -> DataEnvelope:
        dates = sorted({r["_date"] for r in records if r.get("_date")})
        return DataEnvelope(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            requested_range=(request.date_from, request.date_to)
            if request.date_from and request.date_to
            else None,
            returned_range=(date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])) if dates else None,
            timezone=self.source_tz,
            currency=None,
            pagination_complete=complete,
            status=status if records or complete else DataStatus.PARTIAL,
            records=records,
            warnings=warnings,
            request_signature=request.signature(),
        )

    def sync(self, request: SyncRequest) -> DataEnvelope:
        if request.stream == "orders":
            return self._sync_orders(request)
        if request.stream == "open_orders":
            return self._sync_open_orders(request)
        if request.stream == "returns":
            return self._sync_returns(request)
        if request.stream == "statuses":
            body = self._call("getOrderStatusList", {})
            recs = normalize_statuses(body)
            return self._envelope(request, recs, complete=True, warnings=[])
        raise PermanentError(f"unknown Baselinker stream {request.stream}")

    def _sync_orders(self, request: SyncRequest) -> DataEnvelope:
        if not request.date_from:
            raise PermanentError("orders sync requires date_from")
        since = int(datetime.combine(request.date_from, datetime.min.time(), tzinfo=UTC).timestamp())
        base: dict[str, Any] = {
            "date_confirmed_from": since,
            "get_unconfirmed_orders": True,
            "include_custom_extra_fields": True,
        }
        if request.params.get("date_field") == "date_add":
            base = {"date_from": since, "get_unconfirmed_orders": True, "include_custom_extra_fields": True}
        id_from = int(request.cursor) if request.cursor else None
        seen: set[str] = set()
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        complete = False
        for _ in range(MAX_PAGES):
            params = dict(base)
            if id_from is not None:
                params["id_from"] = id_from
            body = self._call("getOrders", params)
            page = body.get("orders", []) or []
            new = [o for o in page if str(o.get("order_id")) not in seen]
            for o in new:
                seen.add(str(o["order_id"]))
            records.extend(self.normalize({"orders": new}))
            if len(page) < PAGE_SIZE:
                complete = True
                break
            id_from = max(int(o["order_id"]) for o in page) + 1
        else:
            warnings.append(f"stopped after {MAX_PAGES} pages; pagination incomplete")
        if request.date_to:
            end_iso = request.date_to.isoformat()
            records = [r for r in records if r["_date"] <= end_iso]
        env = self._envelope(request, records, complete=complete, warnings=warnings)
        env.request_signature["next_cursor"] = str(id_from) if id_from else None
        return env

    def _sync_open_orders(self, request: SyncRequest) -> DataEnvelope:
        """Re-fetch specific orders by ID (late cancellations/returns)."""
        ids: list[str] = list(request.params.get("order_ids", []))
        records: list[dict[str, Any]] = []
        for oid in ids:
            body = self._call("getOrders", {"order_id": int(oid), "include_custom_extra_fields": True})
            records.extend(self.normalize(body))
        return self._envelope(request, records, complete=True, warnings=[])

    def _sync_returns(self, request: SyncRequest) -> DataEnvelope:
        params: dict[str, Any] = {}
        if request.date_from:
            params["date_from"] = int(
                datetime.combine(request.date_from, datetime.min.time(), tzinfo=UTC).timestamp()
            )
        try:
            body = self._call("getOrderReturns", params)
        except PermanentError as exc:
            if "ERROR_UNKNOWN_METHOD" in str(exc):
                return DataEnvelope(
                    source=self.source,
                    stream=request.stream,
                    account_id=request.account_id,
                    fetched_at_utc=datetime.now(UTC),
                    status=DataStatus.NOT_SUPPORTED,
                    warnings=["returns module not available on this account"],
                    request_signature=request.signature(),
                )
            raise
        return self._envelope(request, normalize_returns(body), complete=True, warnings=[])
