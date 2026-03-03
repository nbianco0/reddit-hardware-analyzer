import sqlite3
import time
import hashlib
from datetime import datetime
from vrc_auth import VRChatClient  
from vrchatapi.api import worlds_api
from vrchatapi.exceptions import ApiException

# Global rate limit tracker
last_api_call = 0.0

def generate_checksum(world):
    """Creates a robust, unique hash based on core world properties to detect silent updates."""
    key_fields = [
        world.name or "",
        world.capacity or 0,
        getattr(world, "version", 0) or 0,
        ",".join(world.tags) if world.tags else "",
        getattr(world, "image_url", "") or "",
    ]
    payload = "|".join(str(x) for x in key_fields)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def throttle_request(delay_seconds=10.0):
    """Ensures a polite, steady gap between API calls."""
    global last_api_call
    delta = time.time() - last_api_call
    if delta < delay_seconds:
        sleep_time = delay_seconds - delta
        # Print a temporary message to know it's waiting
        print(f"⏳ Throttling: Waiting {sleep_time:.1f} seconds to respect API...", end="\r", flush=True)
        time.sleep(sleep_time)
        # Clear the line once the wait is over
        print(" " * 60, end="\r", flush=True)
    last_api_call = time.time()

class WorldEngineDB:
    def __init__(self, db_name="vrc_engine.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA busy_timeout = 10000") 
        self.cursor = self.conn.cursor()
        self._build_tables()

    def _build_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                author_name TEXT,
                url TEXT,
                image_url TEXT,
                capacity INTEGER,
                version INTEGER,
                file_size_pc INTEGER,
                file_size_quest INTEGER,
                asset_url_pc TEXT,
                asset_url_quest TEXT,
                tags TEXT,
                favorites INTEGER,
                heat INTEGER,
                update_hash TEXT,
                created_at TEXT,
                last_scraped_at TEXT,
                last_backfilled_at TEXT
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
        
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_world_time ON world_stats(world_id, timestamp DESC)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites ON worlds(favorites)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON worlds(created_at)")
        self.conn.commit()

    def save_world_data(self, world, category):
        clean_tags = ",".join([t.replace('author_tag_', '') for t in world.tags])
        world_url = f"https://vrchat.com/home/world/{world.id}"
        
        image_url = getattr(world, 'image_url', "") or ""
        world_version = getattr(world, 'version', 0)
        current_occupants = getattr(world, 'occupants', 0)
        current_heat = getattr(world, 'heat', 0)
        
        checksum = generate_checksum(world)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute("""
            INSERT INTO worlds (id, name, author_name, url, image_url, capacity, version, tags, favorites, heat, update_hash, created_at, last_scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET 
                name=excluded.name, 
                image_url=excluded.image_url,
                capacity=excluded.capacity, 
                version=excluded.version,
                tags=excluded.tags,
                favorites=excluded.favorites,
                heat=excluded.heat,
                update_hash=excluded.update_hash,
                last_scraped_at=excluded.last_scraped_at
        """, (world.id, world.name, world.author_name, world_url, image_url, world.capacity, 
              world_version, clean_tags, world.favorites, current_heat, checksum, str(world.created_at)[:19], current_time))

        self.cursor.execute("""
            SELECT occupants, favorites, heat FROM world_stats 
            WHERE world_id = ? ORDER BY timestamp DESC LIMIT 1
        """, (world.id,))
        last_stats = self.cursor.fetchone()

        if last_stats:
            last_occ, last_fav, last_heat = last_stats
            if last_occ == current_occupants and last_fav == world.favorites and last_heat == current_heat:
                self.conn.commit()
                return

        self.cursor.execute("""
            INSERT INTO world_stats (world_id, timestamp, category, occupants, favorites, heat)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (world.id, current_time, category, current_occupants, world.favorites, current_heat))
        
        self.conn.commit()

    def close(self):
        self.conn.close()

def safe_search_worlds(w_api, **kwargs):
    """Wraps the API call with dynamic 10s throttling and 429 backoff."""
    while True:
        throttle_request(10.0) # 10 second gap enforced here
        try:
            return w_api.search_worlds(**kwargs)
        except ApiException as e:
            if e.status == 429:
                try:
                    retry_after = int(e.headers.get("Retry-After", 60))
                except:
                    retry_after = 60
                print(f"\n⚠️ Rate limit hit. Backing off for {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                raise e

def run_scraper():
    print("Authenticating...")
    client = VRChatClient()
    client.authenticate()
    w_api = worlds_api.WorldsApi(client.api_client)
    db = WorldEngineDB()

    seen_worlds = set()

    try:
        # TIER 1: Live Pulse (Heat)
        print("\n--- [TIER 1] Scraping 'Heat' (Live Pulse) ---")
        page = 0
        max_pulse_pages = 5 
        zero_streak = 0  
        
        while page < max_pulse_pages:
            offset_value = page * 50
            print(f"Fetching Heat worlds {offset_value + 1} to {offset_value + 50}...".ljust(80), end="\r")
            
            worlds = safe_search_worlds(w_api, release_status="public", sort="heat", n=50, offset=offset_value)
            
            if worlds is None or len(worlds) == 0:
                print("\nNo more worlds returned or API lag detected. Census complete!")
                break
                
            hit_dead_zone = False
            
            for w in worlds:
                current_occ = getattr(w, 'occupants', 0)
                
                if current_occ == 0:
                    zero_streak += 1
                else:
                    zero_streak = 0
                    
                if zero_streak >= 5:
                    hit_dead_zone = True
                    break 
                
                if w.id not in seen_worlds:
                    db.save_world_data(w, "tier1_heat")
                    seen_worlds.add(w.id)
                
            if hit_dead_zone:
                print(f"\nHit 5 consecutive 0-player worlds. Dead zone confirmed. Census complete!")
                break
                
            page += 1

        if page == max_pulse_pages:
            print("\n⚠️ Reached maximum safety cap of 100 pages. Stopping Live Pulse.")

        # TIER 2: Legacy Worlds (Favorites)
        print("\n--- [TIER 2] Scraping 'Favorites' (Legacy Vault) ---")
        pages_to_scrape = 5  
        for page in range(pages_to_scrape):
            offset_value = page * 50
            print(f"Fetching Favorite worlds {offset_value + 1} to {offset_value + 50}...".ljust(80), end="\r")
            
            worlds = safe_search_worlds(w_api, release_status="public", sort="favorites", n=50, offset=offset_value)
            if worlds is None or len(worlds) == 0:
                break
                
            for w in worlds:
                if w.id not in seen_worlds:
                    db.save_world_data(w, "tier2_favorites")
                    seen_worlds.add(w.id)

        # TIER 3: The Newcomer Worlds (Emerging)
        print("\n\n--- [TIER 3] Scraping 'Created' (Newcomer Watchlist) ---")
        pages_to_scrape = 5  
        saved_count = 0
        
        for page in range(pages_to_scrape):
            offset_value = page * 50
            print(f"Fetching Newest worlds {offset_value + 1} to {offset_value + 50}...".ljust(80), end="\r")
            
            worlds = safe_search_worlds(w_api, release_status="public", sort="created", n=50, offset=offset_value)
            if worlds is None or len(worlds) == 0:
                break
                
            for w in worlds:
                has_potential = w.favorites >= 5 or getattr(w, 'heat', 0) >= 5 or getattr(w, 'occupants', 0) >= 3
                
                if has_potential and w.id not in seen_worlds:
                    db.save_world_data(w, "tier3_newcomer")
                    seen_worlds.add(w.id)
                    saved_count += 1
                    
        print(f"\nFiltered out low worlds. Saved {saved_count} highly-rated newcomer worlds.")

        print(f"\n✔ Fast Batch Scrape complete! Processed {len(seen_worlds)} unique worlds.")
    
    except Exception as e:
        print(f"\n❌ Fatal error during pipeline execution: {e}")
    finally:
        db.close()
        print("Database connection closed safely.")

if __name__ == "__main__":
    run_scraper()