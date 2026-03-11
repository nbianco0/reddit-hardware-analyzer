import sqlite3
import time
import re
from datetime import datetime
from vrc_auth import VRChatClient  
from vrchatapi.api import worlds_api, files_api
from vrchatapi.exceptions import ApiException

# Global throttle for the backfill
last_api_call = 0.0

def throttle_request(delay_seconds=2.0):
    # Ensures a polite gap between API calls with visible logging
    global last_api_call
    now = time.time()
    delta = now - last_api_call

    if delta < delay_seconds:
        wait = delay_seconds - delta
        print(f"      ⏳ Throttling... waiting {wait:.2f} seconds before next API call...")
        time.sleep(wait)

    last_api_call = time.time()

def safe_get_world(w_api, world_id):
    base_retry = 60
    attempts = 0
    while attempts < 3:
        throttle_request(3.0)
        try:
            return w_api.get_world(world_id)
        except ApiException as e:
            if e.status == 429:
                retry_after = int(e.headers.get("Retry-After", base_retry)) if "Retry-After" in e.headers else base_retry
                sleep_time = retry_after * (2 ** attempts)
                print(f"\n⚠️ World API Rate limit hit. Backing off for {sleep_time} seconds...")
                time.sleep(sleep_time)
                attempts += 1
            elif e.status == 404:
                print(f"      [!] World {world_id} not found or made private.")
                return None
            else:
                raise e
        except Exception as e:
            print(f"      [!] SDK World Parsing Error (Corrupted Data): {e}. Skipping.")
            return None
            
    print(f"      [!] Failed to fetch {world_id} after 3 rate limit retries.")
    return None

def safe_get_file(f_api, file_id):
    base_retry = 60
    attempts = 0
    while attempts < 3:
        throttle_request(2.0)
        try:
            return f_api.get_file(file_id)
        except ApiException as e:
            if e.status == 429:
                retry_after = int(e.headers.get("Retry-After", base_retry)) if "Retry-After" in e.headers else base_retry
                sleep_time = retry_after * (2 ** attempts)
                print(f"\n⚠️ File API Rate limit hit. Backing off for {sleep_time} seconds...")
                time.sleep(sleep_time)
                attempts += 1
            elif e.status == 404:
                print(f"      [!] File {file_id} not found.")
                return None
            else:
                raise e
        except Exception as e:
            print(f"      [!] SDK File Parsing Error (Corrupted Data): {e}. Skipping.")
            return None
            
    return None

def get_package_size(f_api, pkg):
    # Extracts the file ID, asks VRChat for the metadata, and returns the byte size
    # Layer 1: The defensive approach
    file_id = getattr(pkg, "file_id", None)
    target_version = getattr(pkg, "version", None)

    # Layer 2: Regex fallback
    if not file_id or target_version is None:
        asset_url = getattr(pkg, 'asset_url', "")
        match = re.search(r'/file/(file_[^/]+)/(\d+)', asset_url)
        if match:
            file_id = match.group(1)
            target_version = int(match.group(2))
            
    if not file_id or target_version is None:
        print("      [!] Could not extract File ID or Version.")
        return None

    # Fetch the metadata from VRChat
    file_metadata = safe_get_file(f_api, file_id)
    if not file_metadata:
        return None

    # Loop through the history to find the active version's size
    for version_record in file_metadata.versions:
        if version_record.version == target_version:
            record_dict = version_record.to_dict()
            return record_dict.get('file', {}).get('size_in_bytes', None)
            
    return None

def run_backfill():
    print("Authenticating for Backfill...")
    client = VRChatClient()
    client.authenticate()
    w_api = worlds_api.WorldsApi(client.api_client)
    f_api = files_api.FilesApi(client.api_client) # Initialize the File API
    
    conn = sqlite3.connect("data/vrc_engine.db")
    conn.execute("PRAGMA busy_timeout = 10000")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT w.id, w.name 
        FROM worlds w
        WHERE w.last_backfilled_at IS NULL
        AND w.id IN (
            SELECT world_id 
            FROM world_stats 
            WHERE category IN ('tier1_heat', 'tier2_favorites')
        )
        LIMIT 100
    """)
    worlds_to_update = cursor.fetchall()

    if not worlds_to_update:
        print("✔ Database is fully enriched! No backfill needed right now.")
        conn.close()
        return

    print(f"\n--- Starting Backfill for {len(worlds_to_update)} worlds ---")

    try:
        for idx, (world_id, world_name) in enumerate(worlds_to_update):
            print(f"\n[{idx+1}/{len(worlds_to_update)}] Enriching: {world_name} ({world_id})")

            full_world = safe_get_world(w_api, world_id)
            if not full_world:
                cursor.execute("UPDATE worlds SET last_backfilled_at = ? WHERE id = ?", 
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), world_id))
                conn.commit()
                print("      ✔ Marked as backfilled (not found). Moving on.")
                continue

            desc = getattr(full_world, 'description', "")
            
            pc_url, quest_url = None, None
            pc_size, quest_size = None, None
            
            if hasattr(full_world, 'unity_packages') and full_world.unity_packages:
                for pkg in full_world.unity_packages:
                    if pkg.platform == 'standalonewindows':
                        pc_url = getattr(pkg, 'asset_url', None)
                        pc_size = get_package_size(f_api, pkg)
                    elif pkg.platform == 'android':
                        quest_url = getattr(pkg, 'asset_url', None)
                        quest_size = get_package_size(f_api, pkg)

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE worlds 
                SET description = ?, 
                    file_size_pc = ?, 
                    file_size_quest = ?, 
                    asset_url_pc = ?, 
                    asset_url_quest = ?,
                    last_backfilled_at = ?
                WHERE id = ?
            """, (desc, pc_size, quest_size, pc_url, quest_url, current_time, world_id))
            
            conn.commit()
            print(f"      ✔ Finished enriching {world_name}. Moving to next world.")

        print("\n✔ Backfill batch complete!")

    except Exception as e:
        print(f"\n❌ Fatal error during backfill execution: {e}")
    finally:
        conn.close()
        print("Database connection closed safely.")

if __name__ == "__main__":
    run_backfill()