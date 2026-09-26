import datetime as dt

from app.services.admin_audit_log_service import GENESIS_HASH, _entry_hash


def _at(hour: int = 12) -> dt.datetime:
    return dt.datetime(2026, 9, 27, hour, 0, 0, tzinfo=dt.UTC)


def test_entry_hash_is_deterministic() -> None:
    a = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.created", actor="alice", target_type="camera",
        target_id="CAM-01", details=None, created_at=_at(),
    )
    b = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.created", actor="alice", target_type="camera",
        target_id="CAM-01", details=None, created_at=_at(),
    )
    assert a == b


def test_entry_hash_changes_if_the_actor_changes() -> None:
    a = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.deleted", actor="alice", target_type="camera",
        target_id="CAM-01", details=None, created_at=_at(),
    )
    b = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.deleted", actor="mallory", target_type="camera",
        target_id="CAM-01", details=None, created_at=_at(),
    )
    assert a != b


def test_entry_hash_changes_if_the_previous_hash_changes() -> None:
    """The chaining property: an entry's hash depends on the one before it."""
    a = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.updated", actor="alice", target_type="camera",
        target_id="CAM-01", details="changed=['name']", created_at=_at(),
    )
    b = _entry_hash(
        prev_hash="f" * 64, action="camera.updated", actor="alice", target_type="camera",
        target_id="CAM-01", details="changed=['name']", created_at=_at(),
    )
    assert a != b


def test_a_missing_actor_or_details_does_not_collide_with_an_empty_string() -> None:
    a = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.deleted", actor=None, target_type="camera",
        target_id="CAM-01", details="verified", created_at=_at(),
    )
    b = _entry_hash(
        prev_hash=GENESIS_HASH, action="camera.deleted", actor="verified", target_type="camera",
        target_id="CAM-01", details=None, created_at=_at(),
    )
    assert a != b
