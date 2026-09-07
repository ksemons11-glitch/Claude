"""Notification outbox: dedupe, retry, delivery marked only after the channel confirms.
Default channel is in_app; external adapters exist but have no recipient until the owner authorizes one."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import NotificationOutbox


@dataclass
class DeliveryResult:
    ok: bool
    delivery_id: str | None = None
    error: str | None = None


class Channel(Protocol):
    name: str

    def deliver(self, item: NotificationOutbox) -> DeliveryResult: ...


class InAppChannel:
    name = "in_app"

    def deliver(self, item: NotificationOutbox) -> DeliveryResult:
        return DeliveryResult(True, delivery_id=f"inapp:{item.id}")


class UnconfiguredChannel:
    """Email / Telegram / Discord placeholder: implemented shape, no recipient -> stays PENDING with a clear error."""

    def __init__(self, name: str):
        self.name = name

    def deliver(self, item: NotificationOutbox) -> DeliveryResult:
        return DeliveryResult(
            False,
            error=f"channel {self.name} has no authorized recipient (owner must configure and approve it)",
        )


def enqueue(
    session: Session,
    *,
    dedupe_key: str,
    kind: str,
    subject: str,
    body: str,
    channel: str = "in_app",
    report_id: uuid.UUID | None = None,
    alert_id: uuid.UUID | None = None,
) -> NotificationOutbox | None:
    existing = session.execute(
        select(NotificationOutbox).where(NotificationOutbox.dedupe_key == dedupe_key)
    ).scalar_one_or_none()
    if existing is not None:
        return None
    item = NotificationOutbox(
        dedupe_key=dedupe_key,
        kind=kind,
        subject=subject,
        body=body,
        channel=channel,
        report_id=report_id,
        alert_id=alert_id,
    )
    session.add(item)
    session.flush()
    return item


def deliver_pending(
    session: Session, channels: dict[str, Channel], *, now: datetime, max_attempts: int = 5
) -> dict[str, int]:
    stats = {"delivered": 0, "failed": 0, "pending": 0}
    for item in session.execute(
        select(NotificationOutbox).where(NotificationOutbox.status == "PENDING")
    ).scalars():
        ch = channels.get(item.channel) or UnconfiguredChannel(item.channel)
        item.attempts += 1
        res = ch.deliver(item)
        if res.ok:
            item.status, item.delivery_id, item.delivered_at, item.last_error = (
                "DELIVERED",
                res.delivery_id,
                now,
                None,
            )
            stats["delivered"] += 1
        else:
            item.last_error = res.error
            if item.attempts >= max_attempts:
                item.status = "FAILED"
                stats["failed"] += 1
            else:
                stats["pending"] += 1
    return stats


def unread(session: Session, limit: int = 50) -> list[NotificationOutbox]:
    return list(
        session.execute(
            select(NotificationOutbox)
            .where(NotificationOutbox.channel == "in_app", NotificationOutbox.read_at.is_(None))
            .order_by(NotificationOutbox.created_at.desc())
            .limit(limit)
        ).scalars()
    )
