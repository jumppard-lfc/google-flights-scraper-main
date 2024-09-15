from fastapi import APIRouter, Body, Path, Depends
from fastapi.responses import JSONResponse
from typing import List
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Dict
from app.services import main_search_form_mimic_service, calendar_mimic_service, database_service, misc_service

calendar_mimic_router = APIRouter()

# Get exchanges info
@calendar_mimic_router.get('/info', response_model=dict, status_code=200)
async def test() -> dict:
    result = {
        "message": "This is a test endpoint"
    }
    return JSONResponse(status_code=200, content=jsonable_encoder(result))

async def main() -> dict:
    ''''
    This is MAIN function, which encapsulates the whole logic of the 
        -   calendar mimic, 
        -   generating cURLs, 
        -   sending then to Oxylabs 
        -   and processing the responses.
    '''

    # initialize services
    search_form_mimic_service = search_form_mimic_service.SearchFormMimicService()
    calendar_mimic_service = calendar_mimic_service.CalendarMimicService() 
    misc_service = misc_service.MiscService()
    db_service = database_service.DbService("sqlite:///./test.db")

    # get all active flights search configurations
    flights_search_configurations = db_service.get_active_flights_search_configurations()

    # group them by destination and days of stay
    destinations = misc_service.group_flights_by_destination(flights_search_configurations).order_by('days_of_stay') # groups flights by destination and order them by days of stay

    # example of `destinations`
    # {
    #     "JFK":
    #     [
    #         FlightsSearchConfiguration(origin='BTS', destination='JFK', days_of_stay=2, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0)),
    #         FlightsSearchConfiguration(origin='BTS', destination='JFK', days_of_stay=3, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0))
    #     ],
    #     "LAX":
    #     [
    #         FlightsSearchConfiguration(origin='BTS', destination='LAX', days_of_stay=2, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0)),
    #         FlightsSearchConfiguration(origin='BTS', destination='LAX', days_of_stay=3, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0))
    #     ]
    # }


    # iterate over `destinations` and for each destination, generate a set of cURLs
    




