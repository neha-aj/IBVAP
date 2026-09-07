import json

import httpx
import pytest

from app.core.config import Settings
from app.streaming.health_poller import HealthPoller


def _settings(**overrides) -> Settings:
    defaults = dict(
        postgres_user="u", postgres_password="p", postgres_db="d", jwt_secret="s",
        monitored_services=["svc-a", "svc-b"],
    )
    defaults.update(overrides)
    return Settings(**defaults)


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, channel: str, data: str) -> None:
        self.published.append((channel, json.loads(data)))


def _poller(settings: Settings, handler, redis_client=None) -> HealthPoller:
    poller = HealthPoller(redis_client or FakeRedis(), settings)
    poller._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return poller


@pytest.mark.asyncio
async def test_first_check_publishes_initial_status_for_every_service() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    redis_client = FakeRedis()
    poller = _poller(_settings(), handler, redis_client)

    await poller._check_one("svc-a")
    await poller._check_one("svc-b")

    assert redis_client.published == [
        ("system.health", {"service": "svc-a", "status": "up"}),
        ("system.health", {"service": "svc-b", "status": "up"}),
    ]


@pytest.mark.asyncio
async def test_unchanged_status_does_not_republish() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    redis_client = FakeRedis()
    poller = _poller(_settings(), handler, redis_client)

    await poller._check_one("svc-a")
    await poller._check_one("svc-a")
    await poller._check_one("svc-a")

    assert len(redis_client.published) == 1


@pytest.mark.asyncio
async def test_status_transition_up_to_down_publishes_again() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200)
        return httpx.Response(503)

    redis_client = FakeRedis()
    poller = _poller(_settings(), handler, redis_client)

    await poller._check_one("svc-a")
    await poller._check_one("svc-a")

    assert redis_client.published == [
        ("system.health", {"service": "svc-a", "status": "up"}),
        ("system.health", {"service": "svc-a", "status": "down"}),
    ]


@pytest.mark.asyncio
async def test_connection_error_is_treated_as_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    redis_client = FakeRedis()
    poller = _poller(_settings(), handler, redis_client)

    await poller._check_one("svc-a")

    assert redis_client.published == [("system.health", {"service": "svc-a", "status": "down"})]


@pytest.mark.asyncio
async def test_snapshot_reflects_last_known_status_per_service() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200) if "svc-a" in str(request.url) else httpx.Response(503)

    poller = _poller(_settings(), handler)

    assert poller.snapshot() == {}  # nothing probed yet
    await poller._check_one("svc-a")
    await poller._check_one("svc-b")

    assert poller.snapshot() == {"svc-a": "up", "svc-b": "down"}


@pytest.mark.asyncio
async def test_snapshot_returns_a_copy_not_the_live_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    poller = _poller(_settings(), handler)
    await poller._check_one("svc-a")

    snapshot = poller.snapshot()
    snapshot["svc-a"] = "tampered"

    assert poller.snapshot() == {"svc-a": "up"}
