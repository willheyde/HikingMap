import psycopg
from uuid import UUID, uuid4
from typing import Optional, List
from urllib.parse import unquote
from DBConnection import get_connection
from gear_levels import GEAR_CATEGORY_TO_ITEM_TYPE

from PyObjects.Items import (
    Item, Backpack, Footwear, Shelter, SleepingBag, SleepingPad,
    Clothing, WaterSystem, Kitchen, NavigationTool, Lighting,
    SafetyGear, TechnicalGear, TrekkingPoles, ItemType
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _item_to_attributes(item: Item) -> dict:
    """Serialize type-specific fields into the JSONB attributes dict."""
    if isinstance(item, Backpack):
        return {"capacity_liters": item.capacity_liters, "frame_type": item.frame_type}
    if isinstance(item, Footwear):
        return {"waterproof": item.waterproof, "crampon_compatible": item.crampon_compatible, "ankle_support": item.ankle_support}
    if isinstance(item, Shelter):
        return {"capacity_persons": item.capacity_persons, "season_rating": item.season_rating, "shelter_type": item.shelter_type}
    if isinstance(item, SleepingBag):
        return {"temp_rating_f": item.temp_rating_f, "fill_type": item.fill_type}
    if isinstance(item, SleepingPad):
        return {"r_value": item.r_value, "pad_type": item.pad_type}
    if isinstance(item, Clothing):
        return {"layer_type": item.layer_type, "waterproof": item.waterproof, "min_temp_f": item.min_temp_f}
    if isinstance(item, WaterSystem):
        return {"system_type": item.system_type, "flow_rate_lpm": item.flow_rate_lpm}
    if isinstance(item, Kitchen):
        return {"stove_type": item.stove_type, "cookware_included": item.cookware_included, "boil_time_min": item.boil_time_min}
    if isinstance(item, NavigationTool):
        return {"nav_type": item.nav_type}
    if isinstance(item, Lighting):
        return {"lumens": item.lumens, "lighting_type": item.lighting_type}
    if isinstance(item, SafetyGear):
        return {"safety_type": item.safety_type, "avalanche_rated": item.avalanche_rated}
    if isinstance(item, TechnicalGear):
        return {"technical_type": item.technical_type}
    if isinstance(item, TrekkingPoles):
        return {"adjustable": item.adjustable, "material": item.material}
    return {}


def _row_to_item(row) -> Item:
    # ── Normalize to named locals regardless of cursor type ──────────────────
    if hasattr(row, "keys"):          # dict / RealDictRow / psycopg dict_row
        id_       = row["id"]
        name      = row["name"]
        weight    = row["weight"]
        cost      = row["cost"]
        item_type = row["item_type"]
        image_url = row["image_url"]
        attrs     = row.get("attributes") or {}
    else:                             # plain tuple
        id_, name, weight, cost, item_type, image_url, attrs = row
        attrs = attrs or {}

    def mk(cls, **kwargs):
        obj = cls(id=id_, name=name, weight=float(weight), cost=float(cost), item_type=item_type, **kwargs)
        obj.image_url = image_url
        obj.attributes = attrs        # preserve the full jsonb (gear_category, level, …)
        return obj
    if item_type == ItemType.BACKPACK.value:
        return mk(Backpack,
                  capacity_liters=float(attrs.get("capacity_liters", 0)),
                  frame_type=attrs.get("frame_type", "internal"))

    if item_type == ItemType.FOOTWEAR.value:
        return mk(Footwear,
                  waterproof=attrs.get("waterproof", False),
                  crampon_compatible=attrs.get("crampon_compatible", False),
                  ankle_support=attrs.get("ankle_support", "low"))

    if item_type == ItemType.SHELTER.value:
        return mk(Shelter,
                  capacity_persons=int(attrs.get("capacity_persons", 1)),
                  season_rating=attrs.get("season_rating", "3_season"),
                  shelter_type=attrs.get("shelter_type", "tent"))

    if item_type == ItemType.SLEEPING_BAG.value:
        return mk(SleepingBag,
                  temp_rating_f=int(attrs.get("temp_rating_f", 32)),
                  fill_type=attrs.get("fill_type", "synthetic"))

    if item_type == ItemType.SLEEPING_PAD.value:
        return mk(SleepingPad,
                  r_value=float(attrs.get("r_value", 2.0)),
                  pad_type=attrs.get("pad_type", "foam"))

    if item_type == ItemType.CLOTHING.value:
        return mk(Clothing,
                  layer_type=attrs.get("layer_type", "mid"),
                  waterproof=attrs.get("waterproof", False),
                  min_temp_f=int(attrs.get("min_temp_f", 32)))

    if item_type == ItemType.WATER.value:
        return mk(WaterSystem,
                  system_type=attrs.get("system_type", "filter"),
                  flow_rate_lpm=float(attrs.get("flow_rate_lpm", 1.0)))

    if item_type == ItemType.KITCHEN.value:
        return mk(Kitchen,
                  stove_type=attrs.get("stove_type"),
                  cookware_included=attrs.get("cookware_included", False),
                  boil_time_min=float(attrs.get("boil_time_min", 0.0)))

    if item_type == ItemType.NAVIGATION.value:
        return mk(NavigationTool, nav_type=attrs.get("nav_type", "map"))

    if item_type == ItemType.LIGHTING.value:
        return mk(Lighting,
                  lumens=int(attrs.get("lumens", 0)),
                  lighting_type=attrs.get("lighting_type", "headlamp"))

    if item_type == ItemType.SAFETY.value:
        return mk(SafetyGear,
                  safety_type=attrs.get("safety_type", "first_aid"),
                  avalanche_rated=attrs.get("avalanche_rated", False))

    if item_type == ItemType.TECHNICAL.value:
        return mk(TechnicalGear, technical_type=attrs.get("technical_type", "ice_axe"))

    if item_type == ItemType.TREKKING_POLES.value:
        return mk(TrekkingPoles,
                  adjustable=attrs.get("adjustable", True),
                  material=attrs.get("material", "aluminum"))

    # Fallback for MISC or unknown types
    obj = Item(id=id_, name=name, weight=float(weight), cost=float(cost), item_type=item_type)
    obj.image_url = image_url
    obj.attributes = attrs
    return obj


# ─── Repository ───────────────────────────────────────────────────────────────

class ItemRepository:


    def _get_conn(self):
        return psycopg.connect(self.db_dsn)

    # ── Write ──────────────────────────────────────────────────────────────────

    def create_item(self, item: Item) -> UUID:
        attrs = _item_to_attributes(item)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO items (id, name, weight, cost, item_type, image_url, attributes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (str(item.id), item.name, item.weight, item.cost,
                     item.item_type, item.image_url, psycopg.types.json.Jsonb(attrs))
                )
                conn.commit()
        return item.id

    def update_item_image(self, item_id: UUID, image_url: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE items SET image_url = %s WHERE id = %s",
                    (image_url, str(item_id))
                )
                conn.commit()

    def delete_item(self, item_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM items WHERE id = %s", (str(item_id),))
                conn.commit()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_item(self, item_id: UUID) -> Optional[Item]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, weight, cost, item_type, image_url, attributes FROM items WHERE id = %s",
                    (str(item_id),)
                )
                row = cur.fetchone()
        return _row_to_item(row) if row else None

    def get_item_by_name(self, name: str) -> Optional[Item]:
        clean = unquote(name).lower()
        spaced = clean.replace("-", " ")
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Exact (case-insensitive)
                cur.execute("SELECT id FROM items WHERE LOWER(name) = %s", (clean,))
                row = cur.fetchone()
                # 2. Hyphen-to-space
                if not row:
                    cur.execute("SELECT id FROM items WHERE LOWER(name) = %s", (spaced,))
                    row = cur.fetchone()
                # 3. Partial / fuzzy
                if not row:
                    cur.execute("SELECT id FROM items WHERE LOWER(name) LIKE %s", (f"%{spaced}%",))
                    row = cur.fetchone()
        return self.get_item(row[0]) if row else None

    def list_items(self, item_type: Optional[str] = None) -> List[Item]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if item_type:
                    cur.execute(
                        "SELECT id, name, weight, cost, item_type, image_url, attributes FROM items WHERE item_type = %s ORDER BY name",
                        (item_type,)
                    )
                else:
                    cur.execute(
                        "SELECT id, name, weight, cost, item_type, image_url, attributes FROM items ORDER BY item_type, name"
                    )
                rows = cur.fetchall()
        return [_row_to_item(r) for r in rows]
    # In ItemRepository
    def list_by_user(self, user_id: UUID) -> List[Item]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.id, i.name, i.weight, i.cost, i.item_type, i.image_url, i.attributes
                    FROM items i
                    JOIN user_items ui ON ui.item_id = i.id
                    WHERE ui.user_id = %s
                    ORDER BY i.item_type, i.name
                    """,
                    (str(user_id),)
                )
                rows = cur.fetchall()
        return [_row_to_item(r) for r in rows]
    def create_user_gear(
        self,
        user_id:       UUID,
        name:          str,
        gear_category: str,
        level:         Optional[str] = None,
        weight:        float = 0.0,
        cost:          float = 0.0,
        temp_rating_f: Optional[float] = None,
    ) -> Item:
        """
        Free-text "I have this" gear: creates an item described by a functional
        gear_category (+ optional capability level), links it to the user, and
        returns the loaded Item. The functional fields live in attributes jsonb
        (the A+ model); item_type is derived for backward compat with the
        catalog/query code.

        For a shell, waterproof is stamped True so the legacy waterproof-aware
        presence checks (rain_gear) still recognize it.
        """
        item_type = GEAR_CATEGORY_TO_ITEM_TYPE.get(gear_category, "misc")
        attrs: dict = {"gear_category": gear_category}
        if level:
            attrs["level"] = level
        if temp_rating_f is not None:
            attrs["temp_rating_f"] = temp_rating_f
        if gear_category == "shell":
            attrs["waterproof"] = True

        item_id = uuid4()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO items (id, name, weight, cost, item_type, image_url, attributes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (str(item_id), name, weight, cost, item_type, None,
                     psycopg.types.json.Jsonb(attrs)),
                )
                cur.execute(
                    "INSERT INTO user_items (user_id, item_id) VALUES (%s, %s)",
                    (str(user_id), str(item_id)),
                )
                conn.commit()

        item = Item(id=item_id, name=name, weight=float(weight), cost=float(cost),
                    item_type=item_type)
        item.attributes = attrs
        return item

    def create_item_for_user(self, item: Item, user_id: UUID) -> UUID:
        """
        Creates the item row and links it to the given user via user_items,
        in a single transaction. Use this for gear added on behalf of a
        specific user (e.g. post-trip gear suggestions); create_item() alone
        creates an orphaned item with no owner.
        """
        attrs = _item_to_attributes(item)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO items (id, name, weight, cost, item_type, image_url, attributes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (str(item.id), item.name, item.weight, item.cost,
                    item.item_type, item.image_url, psycopg.types.json.Jsonb(attrs))
                )
                cur.execute(
                    """
                    INSERT INTO user_items (user_id, item_id)
                    VALUES (%s, %s)
                    """,
                    (str(user_id), str(item.id))
                )
                conn.commit()
        return item.id