from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String

from server.database.database import Base


class TailscaleHistory(Base):
    __tablename__ = "tailscale_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    device_id = Column(
        String,
        nullable=False
    )

    old_ip = Column(
        String,
        default=""
    )

    new_ip = Column(
        String,
        default=""
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )