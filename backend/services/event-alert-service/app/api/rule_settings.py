from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ibvap_common.auth import TokenPayload, require_role
from ibvap_common.errors import NotFoundError

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.rule_setting import RuleSettingListResponse, RuleSettingRead, RuleSettingUpdate
from app.services import rule_settings_service
from app.services.rule_settings_service import TUNABLE_KEYS

router = APIRouter(prefix="/api/v1/alerts/thresholds", tags=["rule-settings"])


def _defaults(settings: Settings) -> dict[str, float]:
    return {key: getattr(settings, key) for key in TUNABLE_KEYS}


@router.get("", response_model=RuleSettingListResponse)
async def list_thresholds(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: TokenPayload = Depends(require_role("admin")),
) -> RuleSettingListResponse:
    """Every tunable rule threshold, its currently-effective value, and
    whether an admin has overridden config.py's own default."""
    effective = await rule_settings_service.list_effective(session, defaults=_defaults(settings))
    return RuleSettingListResponse(
        items=[RuleSettingRead(key=key, **fields) for key, fields in effective.items()]
    )


@router.put("/{key}", response_model=RuleSettingRead)
async def update_threshold(
    key: str,
    payload: RuleSettingUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: TokenPayload = Depends(require_role("admin")),
) -> RuleSettingRead:
    if key not in TUNABLE_KEYS:
        raise NotFoundError(f"Unknown or unmanaged setting key: {key}")
    await rule_settings_service.set_override(session, key=key, value=payload.value, actor=user.username)

    # Force the running rule engine to pick this up immediately, rather
    # than waiting up to a full poll interval (RuleSettingsCache's own
    # background loop still runs regardless, as a safety net).
    manager = request.app.state.reconcile_manager
    await manager.rule_settings.refresh(manager.session_factory)

    effective = await rule_settings_service.list_effective(session, defaults=_defaults(settings))
    return RuleSettingRead(key=key, **effective[key])


@router.delete("/{key}", response_model=RuleSettingRead)
async def reset_threshold(
    key: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: TokenPayload = Depends(require_role("admin")),
) -> RuleSettingRead:
    """Removes an admin override, reverting to config.py's own default."""
    if key not in TUNABLE_KEYS:
        raise NotFoundError(f"Unknown or unmanaged setting key: {key}")
    await rule_settings_service.clear_override(session, key=key)

    manager = request.app.state.reconcile_manager
    await manager.rule_settings.refresh(manager.session_factory)

    effective = await rule_settings_service.list_effective(session, defaults=_defaults(settings))
    return RuleSettingRead(key=key, **effective[key])
