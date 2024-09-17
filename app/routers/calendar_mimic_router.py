from fastapi import APIRouter, Body, Path, Depends
from fastapi.responses import JSONResponse
from typing import List
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Dict
from app.services import oxylabs_api_service, calendar_mimic_service, database_service, misc_service

calendar_mimic_router = APIRouter()

# Get exchanges info
@calendar_mimic_router.get('/info', response_model=dict, status_code=200)
async def test() -> dict:
    result = {
        "message": "This is a test endpoint"
    }
    return JSONResponse(status_code=200, content=jsonable_encoder(result))





