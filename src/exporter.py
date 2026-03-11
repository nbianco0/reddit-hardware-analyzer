import sqlite3
import csv
import os

def export_data():
    db_file = "data/vrc_engine.db"
    csv_file = "data/processed/vrc_worlds_data.csv"

    if not os.path.exists(db_file):
        print(f"Cannot find {db_file}. Make sure you run the scraper first!")
        return

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # World descriptions left out of .csv export for cleanliness, but can be added back if needed
    cursor.execute("""
        SELECT 
            w.name, 
            s.category, 
            w.author_name, 
            s.occupants AS active_players, 
            w.favorites,
            ROUND(w.file_size_pc / 1048576.0, 2) AS pc_size_mb,
            ROUND(w.file_size_quest / 1048576.0, 2) AS quest_size_mb,
            w.tags,
            CASE WHEN w.last_backfilled_at IS NOT NULL THEN 'Yes' ELSE 'No' END AS is_enriched
        FROM worlds w
        JOIN world_stats s ON w.id = s.world_id
        GROUP BY w.id
        HAVING s.timestamp = MAX(s.timestamp)
        ORDER BY s.occupants DESC
    """)
    
    rows = cursor.fetchall()

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["World Name", "Category", "Author", "Active Players", "Favorites", "PC Size (MB)", "Quest Size (MB)", "Tags", "Enriched"])
        writer.writerows(rows)

    print(f"✔ Successfully exported {len(rows)} clean rows to {csv_file}!")
    conn.close()

if __name__ == "__main__":
    export_data()