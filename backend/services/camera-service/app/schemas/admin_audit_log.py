import datetime as dt

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AdminAuditLogEntryRead(_CamelModel):
    id: str
    action: str
    actor: str | None
    target_type: str
    target_id: str
    details: str | None
    entry_hash: str
    created_at: dt.datetime


class AdminAuditLogListResponse(_CamelModel):
    items: list[AdminAuditLogEntryRead]
    total: int
    page: int
    page_size: int


class ChainIntegrity(_CamelModel):
    intact: bool
    entries_checked: int
    first_broken_entry_id: str | None
