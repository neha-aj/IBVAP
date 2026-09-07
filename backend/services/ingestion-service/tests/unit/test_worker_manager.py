"""Covers the stuck-worker watchdog added to `WorkerManager._reconcile()` --
a hung `CameraWorker` (blocked forever inside a native video-read call, so
`is_running` stays True) must still get replaced once it's produced no
frames for longer than `stuck_worker_timeout_seconds`. Existing behavior
(healthy workers left alone, dead workers restarted) is covered too, so a
regression in either direction would show up here."""

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.workers.worker_manager import WorkerManager


def _settings(**overrides) -> Settings:
    defaults = {
        "postgres_user": "u", "postgres_password": "p", "postgres_db": "d", "jwt_secret": "s",
        "internal_service_token": "t", "stuck_worker_timeout_seconds": 30,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class FakeWorker:
    def __init__(self, *, is_running: bool, source_url: str | None, idle_seconds: float) -> None:
        self.is_running = is_running
        self.source_url = source_url
        self._idle_seconds = idle_seconds
        self.stop_called = False

    def seconds_since_last_frame(self) -> float:
        return self._idle_seconds

    async def stop(self) -> None:
        self.stop_called = True


def _config(camera_id: str = "CAM-01", source_url: str = "/videos/a.mp4") -> dict:
    return {"id": camera_id, "type": "file", "sourceUrl": source_url}


@pytest.mark.asyncio
async def test_reconcile_leaves_healthy_running_worker_alone() -> None:
    manager = WorkerManager(_settings())
    fake = FakeWorker(is_running=True, source_url="/videos/a.mp4", idle_seconds=1.0)
    manager._workers["CAM-01"] = fake
    manager._fetch_camera_configs = AsyncMock(return_value=[_config()])

    await manager._reconcile()

    assert fake.stop_called is False
    assert manager._workers["CAM-01"] is fake
    await manager.stop()


@pytest.mark.asyncio
async def test_reconcile_replaces_worker_whose_task_already_died() -> None:
    """Pre-existing behavior (not the new watchdog) -- must still work."""
    manager = WorkerManager(_settings())
    fake = FakeWorker(is_running=False, source_url="/videos/a.mp4", idle_seconds=1.0)
    manager._workers["CAM-01"] = fake
    manager._fetch_camera_configs = AsyncMock(return_value=[_config()])

    await manager._reconcile()

    assert fake.stop_called is True
    assert manager._workers["CAM-01"] is not fake
    await manager.stop()


@pytest.mark.asyncio
async def test_reconcile_replaces_stuck_worker_even_though_is_running_true() -> None:
    """The actual bug this watchdog fixes: a hung native read leaves
    `is_running` True forever, so only `seconds_since_last_frame` can catch
    it."""
    manager = WorkerManager(_settings(stuck_worker_timeout_seconds=30))
    fake = FakeWorker(is_running=True, source_url="/videos/a.mp4", idle_seconds=999.0)
    manager._workers["CAM-01"] = fake
    manager._fetch_camera_configs = AsyncMock(return_value=[_config()])

    await manager._reconcile()

    assert fake.stop_called is True
    assert manager._workers["CAM-01"] is not fake
    await manager.stop()


@pytest.mark.asyncio
async def test_reconcile_does_not_flag_worker_within_stuck_threshold() -> None:
    manager = WorkerManager(_settings(stuck_worker_timeout_seconds=30))
    fake = FakeWorker(is_running=True, source_url="/videos/a.mp4", idle_seconds=29.0)
    manager._workers["CAM-01"] = fake
    manager._fetch_camera_configs = AsyncMock(return_value=[_config()])

    await manager._reconcile()

    assert fake.stop_called is False
    assert manager._workers["CAM-01"] is fake
    await manager.stop()
