import time

import httpx
import redis.asyncio as redis

from app.core.config import Settings
from app.workers.camera_worker import CameraWorker


def _settings(**overrides) -> Settings:
    defaults = {
        "postgres_user": "u", "postgres_password": "p", "postgres_db": "d", "jwt_secret": "s",
        "internal_service_token": "t",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _worker() -> CameraWorker:
    return CameraWorker(
        camera_id="CAM-01", camera_type="file", source_url="/videos/a.mp4",
        settings=_settings(), redis_client=redis.Redis(), http_client=httpx.AsyncClient(),
    )


def test_seconds_since_last_frame_starts_near_zero() -> None:
    """Set at construction (not only once the capture loop starts reading)
    so a worker that's slow to open isn't immediately misread as stuck."""
    worker = _worker()
    assert worker.seconds_since_last_frame() < 1.0


def test_seconds_since_last_frame_reflects_time_since_last_update() -> None:
    worker = _worker()
    worker._last_frame_at = time.monotonic() - 45.0
    assert worker.seconds_since_last_frame() >= 45.0
