# services/trip_service.py
from uuid import UUID, uuid4
from datetime import datetime
from typing import List

from PyObjects.Trip import Trip, TravelMode
from Repos.TripRepo import TripRepository


class TripService:
    def __init__(self, trip_repo: TripRepository):
        self.trip_repo = trip_repo

    def create_trip(
        self,
        user_id: UUID,
        hike_id: UUID,
        start_date: datetime,
        end_date: datetime,
        origin_point: dict,
        travel_mode: TravelMode,
    ) -> Trip:
        """
        Create a new trip with sane defaults.
        """

        trip = Trip(
            id=uuid4(),
            user_id=user_id,
            hike_id=hike_id,
            start_date=start_date,
            end_date=end_date,
            origin_point=origin_point,
            travel_mode=travel_mode,
        )

        return self.trip_repo.create(trip)

    def get_trip(self, trip_id: UUID) -> Trip:
        trip = self.trip_repo.get_by_id(trip_id)
        if not trip:
            raise ValueError("Trip not found")
        return trip

    def list_user_trips(self, user_id: UUID) -> List[Trip]:
        return self.trip_repo.list_by_user(user_id)

    def delete_trip(self, trip_id: UUID) -> None:
        self.trip_repo.delete(trip_id)
    