from uuid import UUID, uuid4
from typing import List, Optional

from PyObjects.Hike import Hike, DifficultyLevel
from Repos.HikeRepo import HikeRepository


class HikeService:
    def __init__(self, repo: HikeRepository):
        self.repo = repo

    def create_hike(self, hike: Hike) -> Hike:
        if hike.id is None:
            hike.id = uuid4()
        return self.repo.create(hike)

    def get_hike(self, hike_id: UUID) -> Optional[Hike]:
        return self.repo.get_by_id(hike_id)

    def get_by_source_id(self, source_id: str) -> Optional[Hike]:
        return self.repo.get_by_source_id(source_id)

    def list_hikes(self) -> List[Hike]:
        return self.repo.list_all()

    def update_hike(self, hike: Hike) -> Hike:
        existing = self.repo.get_by_id(hike.id)
        if not existing:
            raise ValueError("Hike not found")
        return self.repo.update(hike)

    def delete_hike(self, hike_id: UUID) -> None:
        self.repo.delete(hike_id)

    def search_hikes(
        self,
        min_length_km=None,
        min_elevation_gain_m=None,
        difficulty=None,
        region=None,
        state=None,                  # ← NEW
        month=None,
        user_lat=None,
        user_lon=None,
        max_distance_km=None,
        required_tags=None,
        can_camp=None,
        permits_required=None,
        max_length_km=None,
    ):
        return self.repo.search(
            min_length_km=min_length_km,
            min_elevation_gain_m=min_elevation_gain_m,
            difficulty=difficulty,
            region=region,
            state=state,             # ← NEW
            month=month,
            user_lat=user_lat,
            user_lon=user_lon,
            max_distance_km=max_distance_km,
            required_tags=required_tags,
            can_camp=can_camp,
            permits_required=permits_required,
            max_length_km=max_length_km,
        )