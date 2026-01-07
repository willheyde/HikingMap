# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Controllers.HikeController import router as hike_router
from Controllers.UserController import router as user_router
from Controllers.TripController import router as trip_router
from Controllers.ItemController import router as item_router
from Routers import UserRouter
app = FastAPI(title="Hiking App API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(hike_router, prefix="/hikes", tags=["Hikes"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(trip_router, prefix="/trips", tags=["Trips"])
app.include_router(item_router, prefix="/items", tags=["Items"])
app.include_router(UserRouter.router)
@app.get("/")
def read_root():
    return {"message": "Hiking App API is running"}

