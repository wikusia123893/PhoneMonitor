from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from server.database.database import Base


class Command(Base):
    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(String, index=True)

    command = Column(String, nullable=False)

    payload = Column(String, default="")

    status = Column(String, default="PENDING")

    result = Column(String, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

    started_at = Column(DateTime, nullable=True)

    finished_at = Column(DateTime, nullable=True)