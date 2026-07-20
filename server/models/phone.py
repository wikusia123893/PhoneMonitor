from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float  # <-- To jest bardzo ważne!

from server.database.database import Base


class Phone(Base):
    __tablename__ = "phones"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    device_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(
        String,
        nullable=False,
        default=""
    )

    model = Column(
        String,
        nullable=False,
        default=""
    )

    android = Column(
        String,
        nullable=False,
        default=""
    )

    ip = Column(
        String,
        nullable=False,
        default=""
    )

    battery = Column(
        Integer,
        default=0
    )

    battery_temp = Column(  # <-- Nowe pole na temperaturę
        Float,
        default=0.0
    )

    tailscale = Column(
        Boolean,
        default=False
    )

    tailscale_ip = Column(
        String,
        default=""
    )

    every_proxy = Column(
        Boolean,
        default=False
    )

    every_proxy_type = Column(
        String,
        default=""
    )

    every_proxy_address = Column(
        String,
        default=""
    )

    last_seen = Column(
        DateTime,
        default=datetime.utcnow
    )