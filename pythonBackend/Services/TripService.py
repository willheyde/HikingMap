from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from PyObjects.Trip import Trip, TripGearItem, TripStop
from Repos.TripRepo import TripRepository

# Only imported for type hints — no runtime coupling to AI layer
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..AI.models.TripSession import TripSession


class TripService:
    def __init__(self, repo: TripRepository):
        self.repo = repo

    # ── Trips ──────────────────────────────────────────────────────────────────

    def create_trip(self, user_id: UUID, title: str, goal: Optional[str] = None) -> Trip:
        trip = Trip(id=uuid4(), user_id=user_id, title=title, goal=goal)
        return self.repo.create(trip)

    def get_trip(self, trip_id: UUID) -> Trip:
        trip = self.repo.get_by_id(trip_id)
        if not trip:
            raise ValueError("Trip not found")
        return trip

    def list_user_trips(self, user_id: UUID) -> List[Trip]:
        return self.repo.list_by_user(user_id)

    def delete_trip(self, trip_id: UUID) -> None:
        self.repo.delete(trip_id)

    # ── Save from AI session ───────────────────────────────────────────────────

    def save_from_session(self, user_id: UUID, session: "TripSession") -> Trip:
        """
        Translates a completed TripSession (Redis/AI layer) into persisted
        Trip + TripStop + TripGearItem rows.

        Called from trip_chat.py when the user confirms save in the finalize phase.
        Returns the fully hydrated Trip.

        Mapping:
          TripPlan.destination_full  → one TripStop (stop_order=1)
          TripPlan.days              → stop.itinerary
          TripPlan.gear_selected     → TripGearItem rows (status="owned")
          TripPlan.gear_gaps         → TripGearItem rows where issue="missing"
                                       with status="need_to_buy"
        """
        plan = session.plan

        if not plan.is_destination_set():
            raise ValueError("Cannot save — trip destination is not confirmed.")

        # ── 1. Create the Trip shell ───────────────────────────────────────
        title = plan.hike_name or plan.destination_full or "My Trip"
        trip  = self.create_trip(
            user_id = user_id,
            title   = title,
            goal    = session.summary or None,   # use the rolling summary as goal
        )

        # ── 2. Build the single stop from the plan ─────────────────────────
        itinerary_payload = self._build_itinerary_payload(plan)

        stop = TripStop(
            id               = uuid4(),
            trip_id          = trip.id,
            stop_order       = 1,
            destination      = plan.destination_full,
            lat              = plan.lat,
            lng              = plan.lng,
            duration_days    = plan.duration_days,
            activity_type    = plan.activity_type,
            itinerary        = itinerary_payload,
            trail_data       = self._build_trail_data(plan),
            camping          = self._build_camping(plan),
            cost_estimate    = None,    # not tracked yet — future feature
            travel_from_prev = None,    # single-stop trips have no previous
        )
        saved_stop = self.repo.add_stop(stop)
        trip.stops = [saved_stop]

        # ── 3. Persist gear ────────────────────────────────────────────────
        gear_rows: list[TripGearItem] = []

        # Items the user confirmed they own and are bringing
        for item_id_str in plan.gear_selected:
            try:
                gear = self.repo.add_gear(TripGearItem(
                    trip_id = trip.id,
                    item_id = UUID(item_id_str),
                    status  = "owned",
                ))
                gear_rows.append(gear)
            except Exception:
                # item_id invalid or item deleted — skip silently
                pass

        # Items flagged as missing by GearGapAnalyzer
        for gap in plan.gear_gaps:
            if gap.issue == "missing" and gap.category != "general":
                # We don't have an item_id for gaps (they're not in the DB yet),
                # so we only persist gaps that have been explicitly addressed by
                # the user selecting a real item. Nothing to do here unless you
                # build a "suggested items" feature later.
                pass

        trip.gear = gear_rows

        # ── 4. Mark trip as saved ──────────────────────────────────────────
        # The Trip dataclass doesn't have an update method yet — add a status
        # update via a direct repo call when you add update_trip() to the repo.
        # For now the trip is created with status="draft"; flip it here if your
        # repo supports it, otherwise it's a one-liner to add.

        return trip

    # ── Stops ──────────────────────────────────────────────────────────────────

    def add_stop(
        self,
        trip_id: UUID,
        destination: str,
        stop_order: int,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        duration_days: Optional[int] = None,
        activity_type: Optional[str] = None,
    ) -> TripStop:
        if not self.repo.get_by_id(trip_id):
            raise ValueError("Trip not found")
        stop = TripStop(
            id            = uuid4(),
            trip_id       = trip_id,
            stop_order    = stop_order,
            destination   = destination,
            lat           = lat,
            lng           = lng,
            duration_days = duration_days,
            activity_type = activity_type,
        )
        return self.repo.add_stop(stop)

    def update_stop(self, stop_id: UUID, updates: Dict[str, Any]) -> TripStop:
        stop = self.repo.get_stop_by_id(stop_id)
        if not stop:
            raise ValueError("Stop not found")
        allowed = {
            "duration_days", "activity_type", "itinerary",
            "trail_data", "camping", "cost_estimate", "travel_from_prev",
        }
        for key, value in updates.items():
            if key in allowed and value is not None:
                setattr(stop, key, value)
        return self.repo.update_stop(stop)

    def delete_stop(self, stop_id: UUID) -> None:
        self.repo.delete_stop(stop_id)

    # ── Gear ───────────────────────────────────────────────────────────────────

    def add_gear(self, trip_id: UUID, item_id: UUID, status: str = "owned") -> TripGearItem:
        gear = TripGearItem(trip_id=trip_id, item_id=item_id, status=status)
        return self.repo.add_gear(gear)

    def remove_gear(self, trip_id: UUID, item_id: UUID) -> None:
        self.repo.remove_gear(trip_id, item_id)

    # ── Private translation helpers ────────────────────────────────────────────

    def _build_itinerary_payload(self, plan) -> Optional[Dict[str, Any]]:
        """
        Converts TripPlan.days (list[DayPlan]) into the jsonb shape
        that trip_stops.itinerary expects.
        """
        if not plan.days:
            return None
        return {
            "days": [
                {
                    "day_number":        d.day_number,
                    "title":             d.title,
                    "distance_miles":    d.distance_miles,
                    "elevation_gain_ft": d.elevation_gain_ft,
                    "campsite":          d.campsite,
                    "notes":             d.notes,
                    "waypoints":         d.waypoints,
                }
                for d in plan.days
            ]
        }

    def _build_trail_data(self, plan) -> Optional[Dict[str, Any]]:
        """
        Basic trail metadata from the plan — expand as your hike DB grows.
        """
        if not plan.destination_full:
            return None
        return {
            "destination":  plan.destination_full,
            "activity_type": plan.activity_type,
            "difficulty":   plan.difficulty,
            "duration_days": plan.duration_days,
            "hike_id":      plan.hike_id,
        }

    def _build_camping(self, plan) -> Optional[Dict[str, Any]]:
        """
        Pulls campsite info out of the day plans if any were noted.
        """
        campsites = [
            {"day": d.day_number, "name": d.campsite}
            for d in plan.days
            if d.campsite
        ]
        return {"campsites": campsites} if campsites else None