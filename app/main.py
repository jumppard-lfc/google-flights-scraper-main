from fastapi import FastAPI

# routers
from app.routers import calendar_mimic_router

# app
app = FastAPI(docs_url="/api-doc", redoc_url=None)

# add routers
app.include_router(calendar_mimic_router, prefix="/api/calendar-mimic", tags=['Calendar Mimic'])

@app.on_event('startup')
async def app_startup():
    print('Starting api...')
    #db: Session = next(get_db())
    #await TaskService(db).process_autorun_tasks()
    print('Api started')

@app.on_event("shutdown")
async def shutdown_event():
    print('Api shutdown detected')

