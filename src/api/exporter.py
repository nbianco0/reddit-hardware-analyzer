import sqlite3
import csv
import os

def export_data():
    db_file = "vrc_engine.db"
    csv_file = "vrc_worlds_data.csv"

    if not os.path.exists(db_file):
        print(f"Cannot find {db_file}. Make sure you run the scraper first!")
        return

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT w.name, s.category, w.author_name, s.occupants, s.favorites, w.tags
        FROM world_stats s
        JOIN worlds w ON s.world_id = w.id
        ORDER BY s.occupants DESC, s.timestamp DESC
    """)
    
    rows = cursor.fetchall()

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["World Name", "Category", "Author", "Active Players", "Favorites", "Tags"])
        writer.writerows(rows)

    print(f"✔ Successfully exported {len(rows)} rows to {csv_file}!")
    conn.close()

if __name__ == "__main__":
    export_data()