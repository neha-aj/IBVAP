"""Lets an admin tune the rule engine's numeric thresholds (loitering
seconds, fighting proximity/jitter, abandoned-object dwell time, person/
vehicle count alerts) from the frontend instead of editing config.py's
env-var defaults and redeploying.

Deliberately NOT the same mechanism as camera-service's Zone.density_threshold
(an HTTP round-trip to a different service, since zones live there) --
these thresholds are read by the rule engine that lives in *this* same
service, so it's a plain in-process cache refreshed from this service's own
Postgres on an interval, the same shape as CameraClient's own zone cache
(app/streaming/camera_client.py) but without the network hop.

Only keys an admin has actually changed get a row in `events.rule_setting`
-- anything missing falls back to config.py's own default, so a fresh
deployment with zero overrides behaves exactly as it did before this
feature existed."""

from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ibvap_common.logging import get_logger

from app.models.rule_setting import RuleSetting

logger = get_logger(__name__)

# The only keys this feature manages -- an admin can't set an arbitrary
# config field through this API, only ones this service explicitly exposes.
TUNABLE_KEYS = (
    "loitering_seconds_threshold",
    "person_count_threshold",
    "vehicle_count_threshold",
    "fighting_proximity_threshold",
    "fighting_jitter_threshold",
    "fighting_min_mean_displacement",
    "abandoned_object_seconds_threshold",
    "abandoned_object_proximity_threshold",
)


class RuleSettingsCache:
    def __init__(self, *, refresh_interval_seconds: float = 30.0) -> None:
        self._overrides: dict[str, float] = {}
        self._refresh_interval_seconds = refresh_interval_seconds
        self._poll_task: asyncio.Task | None = None
        self._stopped = False

    def get(self, key: str, default: float) -> float:
        return self._overrides.get(key, default)

    def start(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._stopped = False
        self._poll_task = asyncio.create_task(self._poll_loop(session_factory), name="rule-settings-poll")

    async def stop(self) -> None:
        self._stopped = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        while not self._stopped:
            try:
                await self.refresh(session_factory)
            except Exception as exc:  # noqa: BLE001 -- a refresh failure must not stop the poll loop or the rule engine
                logger.warning("rule_settings_refresh_failed", error=str(exc))
            await asyncio.sleep(self._refresh_interval_seconds)

    async def refresh(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            rows = (await session.execute(select(RuleSetting))).scalars().all()
            self._overrides = {row.key: row.value for row in rows}


async def list_effective(session: AsyncSession, *, defaults: dict[str, float]) -> dict[str, dict]:
    """Every tunable key, its current effective value (override if one
    exists, else the config default), and whether it's actually overridden
    -- what the admin settings panel shows."""
    rows = (await session.execute(select(RuleSetting))).scalars().all()
    overrides = {row.key: row for row in rows}
    return {
        key: {
            "value": overrides[key].value if key in overrides else defaults[key],
            "default": defaults[key],
            "is_overridden": key in overrides,
            "updated_by": overrides[key].updated_by if key in overrides else None,
            "updated_at": overrides[key].updated_at if key in overrides else None,
        }
        for key in TUNABLE_KEYS
    }


async def set_override(session: AsyncSession, *, key: str, value: float, actor: str | None) -> None:
    if key not in TUNABLE_KEYS:
        raise ValueError(f"Unknown or unmanaged setting key: {key}")
    existing = await session.get(RuleSetting, key)
    now = dt.datetime.now(dt.UTC)
    if existing is None:
        session.add(RuleSetting(key=key, value=value, updated_by=actor, updated_at=now))
    else:
        existing.value = value
        existing.updated_by = actor
        existing.updated_at = now
    await session.commit()


async def clear_override(session: AsyncSession, *, key: str) -> None:
    """Resets a key back to its config.py default by simply deleting the
    override row."""
    existing = await session.get(RuleSetting, key)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
