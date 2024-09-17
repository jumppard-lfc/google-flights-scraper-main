from dataclasses import dataclass

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped
from datetime import datetime

Base = declarative_base()

@dataclass
class AppRun(Base):
    __tablename__ = 'app_run'
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    status: Mapped[str] = Column(String)
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    inserted_records: Mapped[int] = Column(Integer)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)