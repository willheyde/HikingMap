import psycopg
from uuid import UUID
from typing import Optional, List
from urllib.parse import unquote  # <--- Added for URL decoding
from PyObjects.Items import Item, Backpack, Clothing, Shoes, WeatherConditions

class ItemRepository:
    def __init__(self, db_dsn: str = "dbname=hikingapp user=WillH password=12345 host=localhost"):
        self.db_dsn = db_dsn
    
    def _get_conn(self):
        return psycopg.connect(self.db_dsn)
    
    def create_item(self, item: Item) -> UUID:
        """Create an item and its subtype record"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO items (id, name, weight, cost, item_type)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (item.id, item.name, item.weight, item.cost, item.item_type)
                )
                
                if isinstance(item, Shoes):
                    cur.execute(
                        "INSERT INTO clothing (item_id, weatherconditions) VALUES (%s, %s)",
                        (item.id, item.weather_conditions.value)
                    )
                    cur.execute(
                        "INSERT INTO shoes (item_id, crampons) VALUES (%s, %s)",
                        (item.id, item.crampons)
                    )
                elif isinstance(item, Clothing):
                    cur.execute(
                        "INSERT INTO clothing (item_id, weatherconditions) VALUES (%s, %s)",
                        (item.id, item.weather_conditions.value)
                    )
                elif isinstance(item, Backpack):
                    cur.execute(
                        "INSERT INTO backpacks (item_id, capacity_liters) VALUES (%s, %s)",
                        (item.id, item.capacity_liters)
                    )
                
                conn.commit()
        return item.id
    
    def update_item_image(self, item_id: UUID, image_url: str) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE items SET image_url = %s WHERE id = %s",
                    (image_url, item_id)
                )
                conn.commit()

    def get_item(self, item_id: UUID) -> Optional[Item]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, weight, cost, item_type, image_url FROM items WHERE id = %s",
                    (item_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                
                id, name, weight, cost, item_type, image_url = row
                item_obj = None

                if item_type == "shoes":
                    cur.execute(
                        """
                        SELECT c.weatherconditions, s.crampons
                        FROM clothing c
                        JOIN shoes s ON s.item_id = c.item_id
                        WHERE c.item_id = %s
                        """,
                        (item_id,)
                    )
                    subtype_row = cur.fetchone()
                    if subtype_row:
                        weather, crampons = subtype_row
                        item_obj = Shoes(id, name, weight, cost, WeatherConditions(weather), crampons)
                
                elif item_type == "clothing":
                    cur.execute("SELECT weatherconditions FROM clothing WHERE item_id = %s", (item_id,))
                    subtype_row = cur.fetchone()
                    if subtype_row:
                        weather = subtype_row[0]
                        item_obj = Clothing(id, name, weight, cost, WeatherConditions(weather))
                
                elif item_type == "backpack":
                    cur.execute("SELECT capacity_liters FROM backpacks WHERE item_id = %s", (item_id,))
                    subtype_row = cur.fetchone()
                    if subtype_row:
                        capacity = subtype_row[0]
                        item_obj = Backpack(id, name, weight, cost, capacity)
                
                if not item_obj:
                    item_obj = Item(id, name, weight, cost, item_type)

                item_obj.image_url = image_url
                return item_obj
    
    def get_item_by_name(self, name: str) -> Optional[Item]:
        """
        Get item by name with fuzzy matching logic to handle:
        1. URL Encoded strings (Sun%20Hat)
        2. Kebab-case (sun-hat)
        3. Partial matching (sun-hat -> finds 'Wide Brim Sun Hat')
        """
        # 1. Clean the input: decode URL chars and lower case
        clean_name = unquote(name).lower()
        
        # 2. Create a "spaced" version (sun-hat -> sun hat)
        spaced_name = clean_name.replace("-", " ")

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # Attempt 1: Exact match (Case Insensitive)
                # Matches: "20L Daypack" if input is "20L Daypack"
                cur.execute("SELECT id FROM items WHERE LOWER(name) = %s", (clean_name,))
                row = cur.fetchone()

                # Attempt 2: Spaced match (Case Insensitive)
                # Matches: "sun hat" if input is "sun-hat"
                if not row:
                    cur.execute("SELECT id FROM items WHERE LOWER(name) = %s", (spaced_name,))
                    row = cur.fetchone()
                
                # Attempt 3: Partial "Fuzzy" Match (The "Hail Mary")
                # Matches: "Wide Brim Sun Hat" if input is "sun-hat" (checks if "sun hat" is PART of the name)
                if not row:
                    # Uses Postgres ILIKE with wildcards: '%sun hat%'
                    cur.execute("SELECT id FROM items WHERE LOWER(name) LIKE %s", (f"%{spaced_name}%",))
                    row = cur.fetchone()

                if row:
                    return self.get_item(row[0])
                
                return None
    
    def list_items(self) -> List[Item]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM items")
                ids = [row[0] for row in cur.fetchall()]
        return [self.get_item(id) for id in ids]
    
    def delete_item(self, item_id: UUID) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
                conn.commit()