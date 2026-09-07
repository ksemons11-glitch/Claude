"""Scenario 10: >=250 orders with identical timestamps, 100-per-page limit, restart with cursor -> no gaps, no duplicates."""

from __future__ import annotations

import json
from datetime import date

import httpx

from director.adapters.base import SyncRequest
from director.adapters.baselinker import BaselinkerAdapter, extract_utm, normalize_orders
from director.adapters.http import RetryingClient
from director.jobs.worker import PermanentError

TS = 1756713600  # 2025-09-01 08:00 UTC - identical for every order


def make_orders(n: int) -> list[dict]:
    return [
        {
            "order_id": 1000 + i,
            "date_add": TS,
            "date_confirmed": TS,
            "order_status_id": 3,
            "payment_method_cod": "1" if i % 2 else "0",
            "currency": "PLN",
            "delivery_price": "14.99",
            "email": f"c{i}@x",
            "phone": "1",
            "custom_extra_fields": {"utm_source": "fb", "utm_content": "120210000000000301"},
            "products": [
                {
                    "order_product_id": i,
                    "product_id": 7,
                    "sku": "SKU-1",
                    "name": "P",
                    "price_brutto": "129.00",
                    "tax_rate": 23,
                    "quantity": 1,
                }
            ],
        }
        for i in range(n)
    ]


class FakeBaselinker:
    def __init__(self, orders: list[dict], fail_once_at: int | None = None):
        self.orders = orders
        self.calls: list[dict] = []
        self.fail_once_at = fail_once_at

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = json.loads(dict(httpx.QueryParams(request.content.decode()))["parameters"])
        method = dict(httpx.QueryParams(request.content.decode()))["method"]
        self.calls.append(params)
        if method == "getOrderStatusList":
            return httpx.Response(200, json={"status": "SUCCESS", "statuses": [{"id": 3, "name": "Wysłane"}]})
        if self.fail_once_at is not None and len(self.calls) == self.fail_once_at:
            self.fail_once_at = None
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"status": "ERROR"})
        id_from = int(params.get("id_from", 0))
        page = [o for o in self.orders if o["order_id"] >= id_from][:100]
        return httpx.Response(200, json={"status": "SUCCESS", "orders": page})


def adapter(fake: FakeBaselinker) -> BaselinkerAdapter:
    client = httpx.Client(transport=httpx.MockTransport(fake.handler))
    return BaselinkerAdapter(
        "token",
        "https://api.baselinker.com/connector.php",
        http=RetryingClient(client=client, sleep=lambda s: None),
    )


def test_paginates_250_plus_orders_with_identical_timestamps_without_gaps_or_duplicates():
    fake = FakeBaselinker(make_orders(257), fail_once_at=2)  # one transient 429 in the middle
    env = adapter(fake).sync(
        SyncRequest(
            stream="orders", account_id="5018371", date_from=date(2025, 9, 1), date_to=date(2025, 9, 30)
        )
    )
    ids = [r["external_order_id"] for r in env.records]
    assert len(ids) == 257 and len(set(ids)) == 257 and env.pagination_complete
    assert sorted({c["id_from"] for c in fake.calls if "id_from" in c}) == [
        1100,
        1200,
    ]  # advances by last id + 1 (one page retried after 429)
    assert all(c.get("date_confirmed_from") for c in fake.calls if c)  # date filter constant across pages


def test_restart_from_cursor_resumes():
    fake = FakeBaselinker(make_orders(150))
    env = adapter(fake).sync(
        SyncRequest(stream="orders", account_id="x", date_from=date(2025, 9, 1), cursor="1100")
    )
    assert len(env.records) == 50 and env.records[0]["external_order_id"] == "1100"


def test_auth_error_is_permanent_not_retried():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "ERROR", "error_code": "ERROR_AUTH_TOKEN", "error_message": "bad token"}
        )

    a = BaselinkerAdapter(
        "t",
        "https://api.baselinker.com/connector.php",
        http=RetryingClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
        ),
    )
    try:
        a.sync(SyncRequest(stream="orders", account_id="x", date_from=date(2025, 9, 1)))
        raise AssertionError("expected PermanentError")
    except PermanentError:
        pass


def test_normalize_drops_pii_and_extracts_utm():
    recs = normalize_orders({"orders": make_orders(1)})
    r = recs[0]
    assert "email" not in json.dumps(r, default=str) and r["customer_hash"] and r["payment_kind"] == "PREPAID"
    assert r["utm"] == {"utm_source": "fb", "utm_content": "120210000000000301"}
    assert extract_utm({"extra_field_1": "https://shop/?utm_source=fb&utm_content=abc"}) == {
        "utm_source": "fb",
        "utm_content": "abc",
    }
