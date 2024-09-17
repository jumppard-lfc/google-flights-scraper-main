from dataclasses import dataclass

from sqlalchemy import Column, Double, Float, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped
from datetime import datetime

Base = declarative_base()

@dataclass
class Report(Base):
    __tablename__ = 'report'
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    app_run_id: Mapped[int] = Column(Integer)
    destination: Mapped[str] = Column(String)
    days_of_stay: Mapped[int] = Column(Integer)
    best_price: Mapped[float] = Column(Float)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)