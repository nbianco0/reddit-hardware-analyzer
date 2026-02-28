import sqlite3
import time
from datetime import datetime
from vrc_auth import VRChatClient  
from vrchatapi.api import worlds_api
from vrchatapi.exceptions import ApiException

class WorldEngineDB:
    def __init__(self, db_name="vrc_engine.db"):
        self.conn = sqlite3.connect(db_name)
        # Add a timeout so it waits up to 10 seconds for the lock to clear 
        # instead of crashing immediately
        self.conn.execute("PRAGMA busy_timeout = 10000") 
        self.cursor = self.conn.cursor()
        self._build_tables()

    def _build_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY,
                name TEXT,
                author_name TEXT,
                capacity INTEGER,
                tags TEXT,
                created_at TEXT
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_id TEXT,
                timestamp TEXT,
                category TEXT,  
                occupants INTEGER,
                favorites INTEGER,
                heat INTEGER,
                FOREIGN KEY(world_id) REFERENCES worlds(id)
            )
        """)
        self.conn.commit()

    def save_world_data(self, world, category):
        # Keep all tags, but remove ugly 'author_tag_' prefix
        clean_tags = ",".join([t.replace('author_tag_', '') for t in world.tags])

        self.cursor.execute("""
            INSERT OR REPLACE INTO worlds (id, name, author_name, capacity, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (world.id, world.name, world.author_name, world.capacity, clean_tags, str(world.created_at)))

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_occupants = getattr(world, 'occupants', 0)
        
        self.cursor.execute("""
            INSERT INTO world_stats (world_id, timestamp, category, occupants, favorites, heat)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (world.id, current_time, category, current_occupants, world.favorites, getattr(world, 'heat', 0)))
        
        self.conn.commit()

    # Method to close the connection
    def close(self):
        self.conn.close()

def safe_search_worlds(w_api, **kwargs):
    while True:
        try:
            return w_api.search_worlds(**kwargs)
        except ApiException as e:
            if e.status == 429:
                try:
                    retry_after = int(e.headers.get("Retry-After", 60))
                except:
                    retry_after = 60
                print(f"⚠️ Server requested a pause. Sleeping for {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                raise e

def run_scraper():
    print("Authenticating...")
    client = VRChatClient()
    client.authenticate()
    w_api = worlds_api.WorldsApi(client.api_client)
    db = WorldEngineDB()

    # Categories and num of pages to scrape - we can easily add more later if we want
    categories = ["heat"]
    pages_to_scrape = 2 

    try:
        for category in categories:
            print(f"\n--- Scraping '{category}' worlds ---")
            
            for page in range(pages_to_scrape):
                offset_value = page * 50
                print(f"Fetching worlds {offset_value + 1} to {offset_value + 50}...")
                
                try:
                    worlds = safe_search_worlds(
                        w_api,
                        release_status="public",
                        sort=category,
                        n=50,
                        offset=offset_value
                    )
                    
                    if not worlds:
                        print("No more worlds returned. Finishing category.")
                        break
                    
                    for w in worlds:
                        db.save_world_data(w, category)
                        
                    print(f"✔ Saved page {page + 1} to database.")
                    
                    if page < pages_to_scrape - 1:
                        print("⏳ Sleeping for 10 seconds to ensure zero server stress...")
                        time.sleep(10)
                    
                except Exception as e:
                    print(f"Fatal error scraping {category}: {e}")
                    break

        print("\n✔ Scrape complete! Database updated cleanly and politely.")
    
    finally:
        # nsure the database connection is ALWAYS closed, even if the script crashes
        db.close()
        print("Database connection closed safely.")

if __name__ == "__main__":
    run_scraper()