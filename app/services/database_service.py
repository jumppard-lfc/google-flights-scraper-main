from sqlalchemy import create_engine, desc as sqlalchemy_desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.models import Base, FlightsSearchConfiguration

class DbService:
    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
    
    def select(self, model, filters, order_by=None, limit=None, desc=False):
        session = self.SessionLocal()
        query = session.query(model).filter_by(**filters)
        
        if order_by:
            if desc:
                query = query.order_by(sqlalchemy_desc(order_by))
            else:
                query = query.order_by(order_by)
        
        if limit:
            query = query.limit(limit)
        
        result = query.all()
        session.close()
        return result