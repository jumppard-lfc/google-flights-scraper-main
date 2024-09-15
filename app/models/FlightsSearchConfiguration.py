from dataclasses import dataclass

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped
from datetime import datetime

Base = declarative_base()

@dataclass
class FlightsSearchConfiguration(Base):
    __tablename__ = 'flights_search_configurations'
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    origin: Mapped[str] = Column(String)
    destination: Mapped[str] = Column(String)
    days_of_stay: Mapped[int] = Column(Integer)
    is_active: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)