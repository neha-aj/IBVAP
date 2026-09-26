"""Reports a fire/smoke/blood detection to Event/Alert Service's shared
internal event contract (Phase 2 doc08 §4) -- same pattern as ANPR's own
EventClient (M15). doc09 §2.6: severity is always `critical` and
`requiresReview` is always true (a fire/smoke/blood detection always needs
a human to look, unlike a routine ANPR plate read) -- which also means
"Blood Detected" automatically gets the same snapshot + full video-clip
proof as "Fire Detected"/"Smoke Detected" through event-alert-service's
existing generic critical-severity recording pipeline, with no separate
wiring needed here."""

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
        # None (default) keeps this exactly as it was before: a failed
        # report is logged and dropped, no local queue. Set when
        # USE_OFFLINE_EVENT_QUEUE is enabled -- see reconcile_manager.py.
        self._offline_queue = offline_queue

    async def report_detection(self, *, camera_id: str, event_type: str, coverage: float) -> None:
        description = (
            f"{event_type} -- covers ~{coverage * 100:.0f}% of frame "
            "(early-warning heuristic, confirm visually before acting)"
        )
        url = f"{self._settings.event_alert_service_url}/internal/events"
        headers = {"X-Internal-Token": self._settings.internal_service_token, **correlated_headers()}
        payload = {
            "sourceService": "fire-smoke-service",
            "eventType": event_type,
            "cameraId": camera_id,
            "objectType": None,
            "severity": "critical",
            "requiresReview": True,
            "description": description,
        }
        try:
            response = await self._http.post(url, json=payload, headers=headers, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("fire_smoke_event_report_failed", camera_id=camera_id, error=str(exc))
            # event-alert-service (or the network path to it) being
            # unreachable used to mean this detection was lost for good --
            # queued locally instead when enabled, and retried once it's
            # reachable again (see ibvap_common.offline_queue).
            if self._offline_queue is not None:
                await self._offline_queue.enqueue(url=url, json_body=payload, headers=headers)
