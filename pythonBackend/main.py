# main.py
from fastapi import FastAPI
from Controllers.HikeController import router as hike_router
from Controllers.UserController import router as user_router
from Controllers.TripController import router as trip_router
app = FastAPI(title="Hiking App API")

app.include_router(hike_router, prefix="/hikes", tags=["Hikes"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(trip_router, prefix="/trips", tags=["Trips"])