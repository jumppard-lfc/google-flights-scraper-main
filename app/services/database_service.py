from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.models import Base, FlightsSearchConfiguration

class DbService:
    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def get_flights_search_configuration(self, flights_search_configuration_id: int) -> FlightsSearchConfiguration:
        return self.db.get_flights_search_configuration(flights_search_configuration_id)

    def create_flights_search_configuration(self, flights_search_configuration: FlightsSearchConfiguration) -> FlightsSearchConfiguration:
        return self.db.create_flights_search_configuration(flights_search_configuration)

    def update_flights_search_configuration(self, flights_search_configuration: FlightsSearchConfiguration) -> FlightsSearchConfiguration:
        return self.db.update_flights_search_configuration(flights_search_configuration)

    def delete_flights_search_configuration(self, flights_search_configuration_id: int) -> None:
        return self.db.delete_flights_search_configuration(flights_search_configuration_id)