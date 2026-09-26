"""Best-effort local retry queue for internal event reports that fail
because a downstream service (or the network path to it) is temporarily
unreachable -- e.g. event-alert-service being briefly unreachable, or the
kind of connectivity gap a remote border-post deployment could see.

Every detector service's EventClient today (fire-smoke-service,
anpr-service, pose-service, tamper-service, ...) reports a detection with
a plain best-effort HTTP POST: if it fails, the failure is logged and the
detection is dropped for good (SAS §11 "graceful degradation" -- the right
call for a service with no database of its own to hold it in instead).
That means a real connectivity gap silently loses every detection that
happened during it, which is the actual gap this closes.

Deliberately narrow in scope: this queues the JSON body of one internal
event POST, nothing else. It does not queue raw frames or video -- each
detector keeps consuming live frames from Redis Streams regardless (a
separate, already-durable mechanism), so detection itself never stops
during a gap; this only makes sure the *alert produced by that detection*
isn't lost before it can be reported.

Persisted to a local JSONL file (append-only, one entry per line) rather
than kept in memory, so a queued entry survives this process/container
restarting during the outage, not just surviving within one process's
lifetime.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

from ibvap_common.logging import get_logger

logger = get_logger(__name__)


class OfflineEventQueue:
    def __init__(
        self,
        *,
        queue_path: str,
        http_client: httpx.AsyncClient,
        flush_interval_seconds: float = 15.0,
    ) -> None:
        self._queue_path = Path(queue_path)
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._http = http_client
        self._flush_interval_seconds = flush_interval_seconds
        # Guards the queue file against the flush loop and a new enqueue()
        # racing each other -- both read-modify-write the whole file.
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._stopped = False

    def start(self) -> None:
        self._stopped = False
        self._flush_task = asyncio.create_task(self._flush_loop(), name="offline-queue-flush")

    async def stop(self) -> None:
        self._stopped = True
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

    @property
    def queued_count(self) -> int:
        if not self._queue_path.exists():
            return 0
        with self._queue_path.open() as f:
            return sum(1 for _ in f)

    async def enqueue(self, *, url: str, json_body: dict, headers: dict) -> None:
        entry = {"url": url, "json": json_body, "headers": headers, "queued_at": time.time()}
        async with self._lock:
            with self._queue_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        logger.warning("offline_event_queued", url=url, queued_count=self.queued_count)

    async def _flush_loop(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self._flush_interval_seconds)
            try:
                await self._flush_once()
            except Exception as exc:  # noqa: BLE001 -- a flush-loop crash must not stop the loop itself
                logger.warning("offline_queue_flush_failed", error=str(exc))

    async def _flush_once(self) -> None:
        async with self._lock:
            if not self._queue_path.exists():
                return
            lines = [line for line in self._queue_path.read_text().splitlines() if line.strip()]
            if not lines:
                return

            remaining: list[str] = []
            delivered = 0
            for line in lines:
                entry = json.loads(line)
                try:
                    response = await self._http.post(
                        entry["url"], json=entry["json"], headers=entry["headers"], timeout=5.0,
                    )
                    response.raise_for_status()
                    delivered += 1
                except httpx.HTTPError:
                    remaining.append(line)  # still unreachable -- keep it queued, oldest-first order preserved

            self._queue_path.write_text("\n".join(remaining) + ("\n" if remaining else ""))
            if delivered:
                logger.info("offline_queue_flushed", delivered=delivered, remaining=len(remaining))
