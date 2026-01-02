from Repos.HikeRepo import HikeRepository

from Services.HikeService import HikeService

repo = HikeRepository()
service = HikeService(repo)
def seed_hikes(hikes):
    for hike in hikes:
        service.create_hike(hike)
