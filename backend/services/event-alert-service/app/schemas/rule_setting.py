import datetime as dt

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RuleSettingRead(_CamelModel):
    key: str
    value: float
    default: float
    is_overridden: bool
    updated_by: str | None
    updated_at: dt.datetime | None


class RuleSettingListResponse(_CamelModel):
    items: list[RuleSettingRead]


class RuleSettingUpdate(_CamelModel):
    value: float
