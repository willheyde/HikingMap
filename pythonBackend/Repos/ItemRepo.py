import psycopg
from uuid import UUID
from typing import Optional, List
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
                # Insert base item
                cur.execute(
                    """
                    INSERT INTO items (id, name, weight, cost, item_type)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (item.id, item.name, item.weight, item.cost, item.item_type)
                )
                
                # Insert subtype-specific data
                if isinstance(item, Shoes):
                    # First insert into clothing
                    cur.execute(
                        """
                        INSERT INTO clothing (item_id, weatherconditions)
                        VALUES (%s, %s)
                        """,
                        (item.id, item.weather_conditions.value)
                    )
                    # Then insert into shoes
                    cur.execute(
                        """
                        INSERT INTO shoes (item_id, crampons)
                        VALUES (%s, %s)
                        """,
                        (item.id, item.crampons)
                    )
                elif isinstance(item, Clothing):
                    cur.execute(
                        """
                        INSERT INTO clothing (item_id, weatherconditions)
                        VALUES (%s, %s)
                        """,
                        (item.id, item.weather_conditions.value)
                    )
                elif isinstance(item, Backpack):
                    cur.execute(
                        """
                        INSERT INTO backpacks (item_id, capacity_liters)
                        VALUES (%s, %s)
                        """,
                        (item.id, item.capacity_liters)
                    )
                
                conn.commit()
        return item.id
    
    def update_item_image(self, item_id: UUID, image_url: str) -> None:
        """Updates the image_url for a specific item"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE items SET image_url = %s WHERE id = %s",
                    (image_url, item_id)
                )
                conn.commit()

    def get_item(self, item_id: UUID) -> Optional[Item]:
        """Retrieve an item with all subtype data"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # UPDATED: Added image_url to SELECT
                cur.execute(
                    "SELECT id, name, weight, cost, item_type, image_url FROM items WHERE id = %s",
                    (item_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                
                # Unpack new column
                id, name, weight, cost, item_type, image_url = row
                
                item_obj = None

                # Fetch subtype-specific data
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
                    weather, crampons = subtype_row
                    item_obj = Shoes(id, name, weight, cost, WeatherConditions(weather), crampons)
                
                elif item_type == "clothing":
                    cur.execute(
                        "SELECT weatherconditions FROM clothing WHERE item_id = %s",
                        (item_id,)
                    )
                    subtype_row = cur.fetchone()
                    weather = subtype_row[0]
                    item_obj = Clothing(id, name, weight, cost, WeatherConditions(weather))
                
                elif item_type == "backpack":
                    cur.execute(
                        "SELECT capacity_liters FROM backpacks WHERE item_id = %s",
                        (item_id,)
                    )
                    subtype_row = cur.fetchone()
                    capacity = subtype_row[0]
                    item_obj = Backpack(id, name, weight, cost, capacity)
                
                else:
                    # Fallback
                    item_obj = Item(id, name, weight, cost, item_type)

                # Manually set the image_url after instantiation
                # This ensures we don't break the subclass __init__ methods
                if item_obj:
                    item_obj.image_url = image_url

                return item_obj
    
    def get_item_by_name(self, name: str) -> Optional[Item]:
        """Get item by name"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM items WHERE name = %s", (name,))
                row = cur.fetchone()
                if row:
                    return self.get_item(row[0])
                return None
    
    def list_items(self) -> List[Item]:
        """List all items"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM items")
                ids = [row[0] for row in cur.fetchall()]
        
        return [self.get_item(id) for id in ids]
    
    def delete_item(self, item_id: UUID) -> None:
        """Delete an item (CASCADE will handle subtypes)"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
                conn.commit()