from sqlalchemy import create_engine, desc as sqlalchemy_desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Create the Base class
Base = declarative_base()

from app.models import FlightsSearchConfiguration, AppRun

class DbService:
    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
    
    def select(self, model, filters, order_by=None, limit=None, desc=False):
        session = self.SessionLocal()
        query = session.query(model).filter_by(**filters) if filters else session.query(model)
        
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
    
    def insert(self, model, data):
        session = self.SessionLocal()
        instance = model(**data)
        session.add(instance)
        session.commit()
        session.close()

    def update(self, model, id, data):
        session = self.SessionLocal()
        instance = session.query(model).filter_by(id=id).first()
        for key, value in data.items():
            setattr(instance, key, value)
        session.commit()
        session.close()