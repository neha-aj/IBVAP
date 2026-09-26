"""Reports a trained-model Fighting Detected event to Event/Alert
Service's shared internal event contract (Phase 2 doc08 §4) -- same
pattern and same contract as fire-smoke-service's own EventClient. Always
`severity="critical", requiresReview=True`, same reasoning as every other
heuristic/model-based behavioral detector in this codebase: a human must
confirm before anything happens."""

from __future__ import annotations

import httpx

from ibvap_common.logging import correlated_headers, get_logger

from app.core.config import Settings

logger = get_logger(__name__)


class EventClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http_client
        self._settings = settings

    async def report_fighting(self, *, camera_id: str, confidence: float) -> None:
        description = (
            f"Fighting Detected (trained pose model) -- confidence {confidence * 100:.0f}% "
            "-- confirm visually before acting"
        )
        try:
            response = await self._http.post(
                f"{self._settings.event_alert_service_url}/internal/events",
                json={
                    "sourceService": "pose-service",
                    "eventType": "Fighting Detected",
                    "cameraId": camera_id,
                    "objectType": "person",
                    "severity": "critical",
                    "requiresReview": True,
                    "description": description,
                },
                headers={"X-Internal-Token": self._settings.internal_service_token, **correlated_headers()},
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Best-effort, same reasoning as fire-smoke-service's own event
            # reporting -- no local persistence to fall back on, a failed
            # report just means this one detection is lost, not retried.
            logger.warning("pose_fighting_event_report_failed", camera_id=camera_id, error=str(exc))
