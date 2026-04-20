from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String

from app.core.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(2000), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
