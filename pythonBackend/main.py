# main.py
from fastapi import FastAPI
from Controllers.HikeController import router as hike_router

app = FastAPI(title="Hiking App API")

app.include_router(hike_router, prefix="/hikes", tags=["Hikes"])
