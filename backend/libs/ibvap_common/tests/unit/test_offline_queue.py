import httpx
import pytest

from ibvap_common.offline_queue import OfflineEventQueue


class _FakeTransport(httpx.AsyncBaseTransport):
    """Routes every request to a plain callable so tests can flip
    between "downstream is up" and "downstream is down" without a real
    server. Async, matching the AsyncClient these tests exercise."""

    def __init__(self, handler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


def _always_fails(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("downstream unreachable", request=request)


def _always_succeeds(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, request=request)


@pytest.mark.asyncio
async def test_enqueue_persists_when_downstream_is_down(tmp_path) -> None:
    http_client = httpx.AsyncClient(transport=_FakeTransport(_always_fails))
    queue = OfflineEventQueue(queue_path=str(tmp_path / "queue.jsonl"), http_client=http_client)

    await queue.enqueue(url="http://event-alert-service:8000/internal/events", json_body={"eventType": "Fire Detected"}, headers={})

    assert queue.queued_count == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_flush_delivers_and_clears_once_downstream_recovers(tmp_path) -> None:
    http_client = httpx.AsyncClient(transport=_FakeTransport(_always_fails))
    queue = OfflineEventQueue(queue_path=str(tmp_path / "queue.jsonl"), http_client=http_client)
    await queue.enqueue(url="http://event-alert-service:8000/internal/events", json_body={"eventType": "Fire Detected"}, headers={})
    assert queue.queued_count == 1

    # Downstream is back -- same client, new transport, matching a real
    # process's httpx.AsyncClient never being recreated across an outage.
    http_client._transport = _FakeTransport(_always_succeeds)
    await queue._flush_once()

    assert queue.queued_count == 0
    await http_client.aclose()


@pytest.mark.asyncio
async def test_flush_keeps_still_unreachable_entries_queued(tmp_path) -> None:
    http_client = httpx.AsyncClient(transport=_FakeTransport(_always_fails))
    queue = OfflineEventQueue(queue_path=str(tmp_path / "queue.jsonl"), http_client=http_client)
    await queue.enqueue(url="http://event-alert-service:8000/internal/events", json_body={"eventType": "Fire Detected"}, headers={})

    await queue._flush_once()  # still down

    assert queue.queued_count == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_queue_survives_a_new_instance_pointed_at_the_same_file(tmp_path) -> None:
    """A process restart during an outage: a fresh OfflineEventQueue
    pointed at the same on-disk path must still see the queued entry."""
    path = str(tmp_path / "queue.jsonl")
    http_client = httpx.AsyncClient(transport=_FakeTransport(_always_fails))
    queue_a = OfflineEventQueue(queue_path=path, http_client=http_client)
    await queue_a.enqueue(url="http://event-alert-service:8000/internal/events", json_body={"eventType": "Fire Detected"}, headers={})

    queue_b = OfflineEventQueue(queue_path=path, http_client=http_client)
    assert queue_b.queued_count == 1
    await http_client.aclose()
