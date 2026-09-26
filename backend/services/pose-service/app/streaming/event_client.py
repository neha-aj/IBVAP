"""Reports a trained-model Fighting Detected event to Event/Alert
Service's shared internal event contract (Phase 2 doc08 §4) -- same
pattern and same contract as fire-smoke-service's own EventClient. Always
`severity="critical", requiresReview=True`, same reasoning as every other
heuristic/model-based behavioral detector in this codebase: a human must
confirm before anything happens."""

from __future__ import annotations

import httpx

from ibvap_common.logging import correlated_headers, get_logger
from ibvap_common.offline_queue import OfflineEventQueue

from app.core.config import Settings

logger = get_logger(__name__)


class EventClient:
    def __init__(
        self, http_client: httpx.AsyncClient, settings: Settings, offline_queue: OfflineEventQueue | None = None,
    ) -> None:
        self._http = http_client
        self._settings = settings
        # None (default): exactly the old behavior, a failed report is
        # logged and dropped. Set when USE_OFFLINE_EVENT_QUEUE is enabled.
        self._offline_queue = offline_queue

    async def report_fighting(self, *, camera_id: str, confidence: float) -> None:
        description = (
            f"Fighting Detected (trained pose model) -- confidence {confidence * 100:.0f}% "
            "-- confirm visually before acting"
        )
        url = f"{self._settings.event_alert_service_url}/internal/events"
        headers = {"X-Internal-Token": self._settings.internal_service_token, **correlated_headers()}
        payload = {
            "sourceService": "pose-service",
            "eventType": "Fighting Detected",
            "cameraId": camera_id,
            "objectType": "person",
            "severity": "critical",
            "requiresReview": True,
            "description": description,
        }
        try:
            response = await self._http.post(url, json=payload, headers=headers, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("pose_fighting_event_report_failed", camera_id=camera_id, error=str(exc))
            if self._offline_queue is not None:
                await self._offline_queue.enqueue(url=url, json_body=payload, headers=headers)
