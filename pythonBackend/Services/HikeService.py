# services/hike_service.py
from uuid import UUID, uuid4
from typing import List, Optional

from PyObjects.Hike import Hike, DifficultyLevel
from Repos.HikeRepo import HikeRepository


class HikeService:
    def __init__(self, repo: HikeRepository):
        self.repo = repo

    def create_hike(self, hike: Hike) -> Hike:
        # Central place for rules like:
        # - deduping source_id
        # - validation
        # - default fields
        if hike.id is None:
            hike.id = uuid4()

        return self.repo.create(hike)

    def get_hike(self, hike_id: UUID) -> Optional[Hike]:
        return self.repo.get_by_id(hike_id)

    def list_hikes(self) -> List[Hike]:
        return self.repo.list_all()

    def update_hike(self, hike: Hike) -> Hike:
        existing = self.repo.get_by_id(hike.id)
        if not existing:
            raise ValueError("Hike not found")

        return self.repo.update(hike)

    def delete_hike(self, hike_id: UUID) -> None:
        self.repo.delete(hike_id)
