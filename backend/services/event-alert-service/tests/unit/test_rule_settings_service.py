from app.core.config import Settings
from app.rules.engine import RuleEngine
from app.services.rule_settings_service import RuleSettingsCache


def _settings(**overrides) -> Settings:
    defaults = {
        "postgres_user": "u", "postgres_password": "p", "postgres_db": "d", "jwt_secret": "s",
        "person_count_threshold": 2, "vehicle_count_threshold": 2, "loitering_seconds_threshold": 90,
        "offline_alert_enabled": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


async def _no_zones(_camera_id: str):
    return []


def test_get_falls_back_to_default_when_no_override_set() -> None:
    cache = RuleSettingsCache()
    assert cache.get("loitering_seconds_threshold", 90.0) == 90.0


def test_get_returns_override_once_present() -> None:
    cache = RuleSettingsCache()
    cache._overrides["loitering_seconds_threshold"] = 45.0
    assert cache.get("loitering_seconds_threshold", 90.0) == 45.0


def test_engine_threshold_helper_falls_back_with_no_cache() -> None:
    engine = RuleEngine(_settings(), _no_zones)
    assert engine._threshold("loitering_seconds_threshold", 90.0) == 90.0


def test_engine_threshold_helper_uses_cache_when_provided() -> None:
    cache = RuleSettingsCache()
    cache._overrides["loitering_seconds_threshold"] = 45.0
    engine = RuleEngine(_settings(), _no_zones, rule_settings=cache)
    assert engine._threshold("loitering_seconds_threshold", 90.0) == 45.0
