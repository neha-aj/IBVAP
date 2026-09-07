from functools import lru_cache

from ibvap_common.settings import CommonSettings


class Settings(CommonSettings):
    service_name: str = "realtime-gateway"

    # Redis Pub/Sub channels this gateway bridges to WebSocket clients
    # (API Spec §8). One fixed list -- Phase 1 has no dynamic channel
    # discovery need.
    bridged_channels: list[str] = [
        "camera.status_changed",
        "detection.new",
        "event.new",
        "alert.new",
        "alert.updated",
        "system.health",
    ]

    # --- system.health (Phase 2 M24 -- API Spec §8's documented but never-
    # implemented "optional, ops use" topic) ---
    # Same fixed service list as monitoring/prometheus.yml's own static
    # targets -- this gateway is the one service every other service's
    # `/health` is already known to reachable at `http://{name}:8000/health`
    # on the internal network, so no service-discovery mechanism is needed.
    monitored_services: list[str] = [
        "auth-service", "camera-service", "ingestion-service", "detection-service",
        "tracking-service", "event-alert-service", "media-service", "analytics-service",
        "anpr-service", "reid-service", "fire-smoke-service", "tamper-service", "ppe-service",
    ]
    health_poll_interval_seconds: int = 15
    health_check_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
