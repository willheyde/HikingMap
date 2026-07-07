import uuid
from DBConnection import get_connection
from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService
from PyObjects.Hike import Hike
import logging
repo    = HikeRepository()
service = HikeService(repo)


# ── Item resolver ──────────────────────────────────────────────────────────────

def _build_item_query(item_type: str, filters: dict) -> tuple[str, list]:
    """
    Builds a parameterized SELECT from item_type + attribute filters.

    Filter values can be:
        str / int / float  →  equality match on attributes jsonb key
        bool               →  cast to ::boolean before comparing
        {"lte": N}         →  cast to ::float and compare <=
        {"gte": N}         →  cast to ::float and compare >=

    Results are ordered lightest-first — a reasonable proxy for quality
    when multiple items match the same spec.
    """
    conditions = ["item_type = %s"]
    params: list = [item_type]

    for key, val in filters.items():
        if isinstance(val, dict):
            if "lte" in val:
                conditions.append(f"(attributes->>'{key}')::float <= %s")
                params.append(val["lte"])
            elif "gte" in val:
                conditions.append(f"(attributes->>'{key}')::float >= %s")
                params.append(val["gte"])
        elif isinstance(val, bool):
            conditions.append(f"(attributes->>'{key}')::boolean = %s")
            params.append(val)
        else:
            conditions.append(f"attributes->>'{key}' = %s")
            params.append(str(val))

    where = " AND ".join(conditions)
    sql   = f"SELECT id FROM items WHERE {where} ORDER BY weight ASC LIMIT 1"
    return sql, params


def _resolve_item(cur, item_type: str, filters: dict) -> str | None:
    """Returns the best-matching item_id, or None if nothing matches."""
    sql, params = _build_item_query(item_type, filters)
    cur.execute(sql, params)
    row = cur.fetchone()
    return str(row["id"]) if row else None



# ── Seeder ─────────────────────────────────────────────────────────────────────

def seed_hikes(hikes_with_gear: list[tuple]) -> None:
    """
    Upserts each hike and links its gear to real item rows via hike_items.

    Args:
        hikes_with_gear: list of (Hike, gear_reqs) where gear_reqs is a list of
                         {"item_type": str, "filters": dict, "importance": str}
                         dicts from GearInferenceEngine.
    """
    added   = 0
    skipped = 0
    failed  = 0

    for hike, gear_reqs in hikes_with_gear:
        try:
            existing = service.get_by_source_id(hike.source_id)
            if existing:
                skipped += 1
                continue

            created = service.create_hike(hike)
            seed_gear(str(created.id), gear_reqs)
            added += 1

        except Exception as e:
            print(f"  Failed to seed '{hike.name}' ({hike.source_id}): {e}")
            failed += 1

    print(f"Seeding complete — added: {added}, skipped: {skipped}, failed: {failed}")


def seed_gear(hike_id: str, gear_reqs: list[dict]) -> None:
    """
    Deprecated no-op. Per-trail gear needs now live in the catalog-independent
    hikes.gear_requirements jsonb (written on hike create from
    GearInferenceEngine.infer_gear_levels), and GearGapAnalyzer reads them
    directly. The legacy hike_items table this used to populate has been dropped
    (see migration 004), so there is nothing to resolve or insert here. Kept as a
    stub so existing ingestion call sites don't need to change.
    """
    return