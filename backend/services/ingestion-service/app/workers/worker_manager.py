from __future__ import annotations

import asyncio

import httpx
import redis.asyncio as redis

from ibvap_common.logging import get_logger
from ibvap_common.redis_streams import build_redis_client

from app.core.config import Settings
from app.workers.camera_worker import CameraWorker

logger = get_logger(__name__)


class WorkerManager:
    """Owns the set of running `CameraWorker`s and reconciles it against the
    Camera Management Service's camera list on a polling interval, so newly
    created/deleted cameras (via the Cameras page or the upload endpoint)
    are picked up without restarting the ingestion service."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._workers: dict[str, CameraWorker] = {}
        self._redis: redis.Redis = build_redis_client(settings)
        self._http = httpx.AsyncClient()
        self._poll_task: asyncio.Task | None = None
        self._stopped = False

    async def start(self) -> None:
        self._stopped = False
        await self._reconcile()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="ingestion-poll-loop")

    @property
    def active_worker_count(self) -> int:
        return len(self._workers)

    async def stop(self) -> None:
        self._stopped = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(*(w.stop() for w in self._workers.values()))
        self._workers.clear()
        await self._http.aclose()
        await self._redis.aclose()

    async def _poll_loop(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self._settings.camera_refresh_interval_seconds)
            try:
                await self._reconcile()
            except Exception as exc:
                logger.warning("camera_list_poll_failed", error=str(exc))

    async def _fetch_camera_configs(self) -> list[dict]:
        response = await self._http.get(
            f"{self._settings.camera_service_url}/internal/cameras",
            headers={"X-Internal-Token": self._settings.internal_service_token},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def _reconcile(self) -> None:
        configs = await self._fetch_camera_configs()
        seen_ids = set()

        for config in configs:
            camera_id = config["id"]
            seen_ids.add(camera_id)
            existing = self._workers.get(camera_id)
            if existing is not None:
                stuck_seconds = existing.seconds_since_last_frame()
                is_stuck = stuck_seconds > self._settings.stuck_worker_timeout_seconds
                if existing.is_running and existing.source_url == config.get("sourceUrl") and not is_stuck:
                    continue  # already running the current source -- nothing to do
                # Either the task exited (e.g. source failed to open), a new
                # file was uploaded to this camera, or the worker is stuck
                # (see CameraWorker.seconds_since_last_frame's own docstring)
                # -- stop it so it's recreated below against the current
                # config instead of silently continuing to stream a stale/
                # failed/hung source.
                await existing.stop()
                del self._workers[camera_id]
                if is_stuck:
                    logger.warning(
                        "camera_worker_stuck_restarting", camera_id=camera_id, idle_seconds=round(stuck_seconds),
                    )
                else:
                    logger.info("camera_worker_restarting", camera_id=camera_id)

            camera_type = config["type"]
            source_url = config.get("sourceUrl")
            if camera_type == "file" and not source_url:
                continue  # no video uploaded yet -- nothing to open

            worker = CameraWorker(
                camera_id=camera_id,
                camera_type=camera_type,
                source_url=source_url,
                settings=self._settings,
                redis_client=self._redis,
                http_client=self._http,
            )
            worker.start()
            self._workers[camera_id] = worker
            logger.info("camera_worker_started", camera_id=camera_id, type=camera_type)

        # Stop workers for cameras that no longer exist.
        removed_ids = set(self._workers) - seen_ids
        for camera_id in removed_ids:
            await self._workers.pop(camera_id).stop()
            logger.info("camera_worker_stopped", camera_id=camera_id, reason="camera_removed")
