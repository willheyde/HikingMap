from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import logger

from PyObjects.Trip import Trip, TripGearItem, TripStop, HikeCompletion
from Repos.TripRepo import TripRepository

_VALID_DIFFICULTY_FELT: frozenset = frozenset({"EASY", "MODERATE", "DIFFICULT", "EXPERT"})

# Only imported for type hints — no runtime coupling to AI layer
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..AI.TripSession import TripSession


class TripService:
    def __init__(self, repo: TripRepository):
        self.repo = repo

    # ── Trips ──────────────────────────────────────────────────────────────────

    def create_trip(
        self, user_id: UUID, title: str, goal: Optional[str] = None, status: str = "draft"
    ) -> Trip:
        trip = Trip(id=uuid4(), user_id=user_id, title=title, goal=goal, status=status)
        return self.repo.create(trip)

    def get_trip(self, trip_id: UUID) -> Trip:
        trip = self.repo.get_by_id(trip_id)
        if not trip:
            raise ValueError("Trip not found")
        return trip

    def list_user_trips(
        self, user_id: UUID, statuses: Optional[List[str]] = None, hydrate: bool = True
    ) -> List[Trip]:
        return self.repo.list_by_user(user_id, statuses=statuses, hydrate=hydrate)

    def delete_trip(self, trip_id: UUID) -> None:
        self.repo.delete(trip_id)

    # ── Lifecycle: completed / reviewed ─────────────────────────────────────────

    def mark_completed(self, trip: Trip) -> Trip:
        """'Mark as done' — only valid from 'saved'. Takes the already-fetched
        Trip (caller already did the ownership-checked lookup) rather than
        re-fetching, matching the _owned_trip-then-act pattern used elsewhere."""
        if trip.status != "saved":
            raise ValueError(f"Cannot mark as done — trip status is '{trip.status}', expected 'saved'.")
        self.repo.mark_completed(trip.id)
        trip.status = "completed"
        return trip

    def submit_review(
        self,
        trip:            Trip,
        went:             bool,
        difficulty_felt:  Optional[str] = None,
        elevation_felt:   Optional[str] = None,
        rating:           Optional[int] = None,
        notes:            Optional[str] = None,
    ) -> HikeCompletion:
        """
        Writes the questionnaire to hike_completions and advances
        completed -> reviewed. Only valid from 'completed' — the spec is
        explicit that this shouldn't be reachable straight from 'saved'
        (there's nothing to review until the user has said they went/hiked it,
        via "Mark as done").
        """
        if trip.status != "completed":
            raise ValueError(f"Cannot review — trip status is '{trip.status}', expected 'completed'.")
        if rating is not None and not (1 <= rating <= 5):
            raise ValueError("rating must be between 1 and 5.")
        if difficulty_felt is not None and difficulty_felt.upper() not in _VALID_DIFFICULTY_FELT:
            raise ValueError(f"difficulty_felt must be one of {sorted(_VALID_DIFFICULTY_FELT)}.")

        completion = HikeCompletion(
            trip_id         = trip.id,
            went            = went,
            difficulty_felt = difficulty_felt.upper() if difficulty_felt else None,
            elevation_felt  = elevation_felt,
            rating          = rating,
            notes           = notes,
        )
        self.repo.add_completion(completion)
        self.repo.mark_reviewed(trip.id)
        return completion

    def get_completion(self, trip_id: UUID) -> Optional[HikeCompletion]:
        return self.repo.get_completion(trip_id)

    def get_ratings(self, trip_ids: List[UUID]) -> Dict[str, int]:
        return self.repo.get_ratings(trip_ids)

    def get_past_hikes_stats(self, user_id: UUID) -> Dict[str, Any]:
        """
        Aggregate header for the Past Hikes page: hike count, total miles,
        favorite region. Computed from data already captured elsewhere —
        trip_stops.itinerary (per-day distance_miles) and trip_stops.trail_data
        (the 'state' field Phase 1 added) — rather than a new tracking
        pipeline or a join back to `hikes` (trail_data.state is already a
        direct, always-available proxy for "region" without one).
        """
        trips = self.repo.list_by_user(user_id, statuses=["completed", "reviewed"], hydrate=True)

        total_miles = 0.0
        region_counts: Dict[str, int] = {}
        for trip in trips:
            for stop in trip.stops:
                for day in (stop.itinerary or {}).get("days", []):
                    distance = day.get("distance_miles")
                    if distance:
                        total_miles += distance
                state = (stop.trail_data or {}).get("state")
                if state:
                    region_counts[state] = region_counts.get(state, 0) + 1

        favorite_region = max(region_counts, key=region_counts.get) if region_counts else None

        return {
            "hike_count":      len(trips),
            "total_miles":     round(total_miles, 1),
            "favorite_region": favorite_region,
        }

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
        # status="saved" directly — this IS the promotion out of Redis into
        # the durable lifecycle (active [Redis] -> saved -> completed ->
        # reviewed). create_trip()'s "draft" default stays for the separate,
        # currently-unused POST /trips/ manual-creation path.
        title = plan.hike_name or plan.destination_full or "My Trip"
        trip  = self.create_trip(
            user_id = user_id,
            title   = title,
            goal    = session.summary or None,   # use the rolling summary as goal
            status  = "saved",
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
            except Exception as e:
                logger.warning("Skipping gear item %s: %s", item_id_str, e)

        # Items flagged as missing by GearGapAnalyzer
        for gap in plan.gear_gaps:
            if gap.issue == "missing" and gap.category != "general":
                # We don't have an item_id for gaps (they're not in the DB yet),
                # so we only persist gaps that have been explicitly addressed by
                # the user selecting a real item. Nothing to do here unless you
                # build a "suggested items" feature later.
                pass

        trip.gear = gear_rows

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
        Trail + search metadata from the plan. Widened beyond the original
        destination/difficulty/duration/hike_id set to also capture the
        search criteria (state, length constraints, tag lists) — Phase 3's
        "Go Again" needs enough here to reconstruct a TripIntent-shaped
        object and replay the original search, not just re-show the same
        destination at a different difficulty.

        Known gap: this reflects the criteria at the last full destination
        search (initial parse, or after a destination reset) — a SEARCH_REFINE
        mid-conversation (e.g. "actually make it harder") isn't re-applied to
        plan.required_tags/etc, since that flow re-derives its intent from
        session.phase_data on the fly rather than writing back through
        _apply_intent_to_plan. Good enough for v1; revisit if Go Again turns
        out to replay stale criteria often.
        """
        if not plan.destination_full:
            return None
        return {
            "destination":       plan.destination_full,
            "activity_type":     plan.activity_type,
            "difficulty":        plan.difficulty,
            "duration_days":     plan.duration_days,
            "hike_id":           plan.hike_id,
            "state":             plan.state,
            "max_length_km":     plan.max_length_km,
            "target_length_km":  plan.target_length_km,
            "required_tags":     plan.required_tags,
            "preferred_tags":    plan.preferred_tags,
            "priority_tags":     plan.priority_tags,
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