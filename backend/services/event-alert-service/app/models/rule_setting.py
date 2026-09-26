import datetime as dt

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RuleSetting(Base):
    """An admin-overridden rule threshold (e.g. loitering_seconds_threshold),
    keyed by the same name as the matching field on app.core.config.Settings.
    Only thresholds an admin has actually changed get a row here -- anything
    without one keeps using config.py's own default (env-var driven), so a
    fresh deployment with no admin overrides behaves exactly as before this
    feature existed."""

    __tablename__ = "rule_setting"
    __table_args__ = {"schema": "events"}

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
