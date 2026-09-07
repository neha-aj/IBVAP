"""Owns the set of running `FrameConsumer`s and reconciles it against the
Camera Management Service's camera list on a polling interval -- the same
discovery pattern Stream Ingestion's `WorkerManager` uses (M3), so newly
created/deleted cameras are picked up without restarting the service, and a
consumer whose task died gets restarted on the next pass instead of being
stuck forever.
"""

from __future__ import annotations

import asyncio

import httpx
import redis.asyncio as redis

from ibvap_common.logging import get_logger
from ibvap_common.redis_streams import build_redis_client

from app.core.config import Settings
from app.inference.base import InferenceEngine
from app.streaming.detection_publisher import DetectionPublisher
from app.streaming.frame_consumer import FrameConsumer

logger = get_logger(__name__)


class ConsumerManager:
    def __init__(self, settings: Settings, engine: InferenceEngine) -> None:
        self._settings = settings
        self._engine = engine
        self._consumers: dict[str, FrameConsumer] = {}
        self._redis: redis.Redis = build_redis_client(settings)
        self._publisher = DetectionPublisher(
            self._redis,
            stream_maxlen=settings.detections_stream_maxlen,
            current_ttl_seconds=settings.current_detections_ttl_seconds,
        )
        self._http = httpx.AsyncClient()
        self._poll_task: asyncio.Task | None = None
        self._stopped = False

    @property
    def active_consumer_count(self) -> int:
        return len(self._consumers)

    async def start(self) -> None:
        self._stopped = False
        await self._reconcile()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="detection-poll-loop")

    async def stop(self) -> None:
        self._stopped = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(*(c.stop() for c in self._consumers.values()))
        self._consumers.clear()
        await self._http.aclose()
        await self._redis.aclose()

    async def _poll_loop(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self._settings.camera_refresh_interval_seconds)
            try:
                await self._reconcile()
            except Exception as exc:
                logger.warning("camera_list_poll_failed", error=str(exc))

    async def _fetch_camera_ids(self) -> list[str]:
        response = await self._http.get(
            f"{self._settings.camera_service_url}/internal/cameras",
            headers={"X-Internal-Token": self._settings.internal_service_token},
            timeout=10.0,
        )
        response.raise_for_status()
        return [config["id"] for config in response.json()]

    async def _reconcile(self) -> None:
        camera_ids = await self._fetch_camera_ids()
        seen_ids = set(camera_ids)

        for camera_id in camera_ids:
            existing = self._consumers.get(camera_id)
            if existing is not None:
                if existing.is_running:
                    continue
                await existing.stop()
                del self._consumers[camera_id]
                logger.info("frame_consumer_restarting", camera_id=camera_id)

            consumer = FrameConsumer(
                camera_id=camera_id,
                redis_client=self._redis,
                engine=self._engine,
                publisher=self._publisher,
                group_name=self._settings.consumer_group_name,
                read_count=self._settings.frames_read_count,
                block_ms=self._settings.frames_block_ms,
            )
            consumer.start()
            self._consumers[camera_id] = consumer
            logger.info("frame_consumer_started", camera_id=camera_id)

        removed_ids = set(self._consumers) - seen_ids
        for camera_id in removed_ids:
            await self._consumers.pop(camera_id).stop()
            logger.info("frame_consumer_stopped", camera_id=camera_id, reason="camera_removed")
