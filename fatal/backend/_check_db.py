import sys
sys.path.insert(0, '.')
import db
import sqlite3

conn = db.get_connection()
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT uid, user_uid, name, matching_phase, hope_halls, room_capacity, preferred_room_type_ids, interest_room_type_ids, fixed_room_type_id, fixed_interest_room_type_id FROM profiles WHERE matching_phase='preliminary' LIMIT 10").fetchall()
print(f"preliminary profiles: {len(rows)}")
for r in rows[:3]:
    print(dict(r))

rows2 = conn.execute("SELECT matching_phase, count(*) as cnt FROM profiles GROUP BY matching_phase").fetchall()
print("\nPhase distribution:")
for r in rows2:
    print(f"  {r['matching_phase']}: {r['cnt']}")

# Check how many have non-empty interest_room_type_ids
import json
rows3 = conn.execute("SELECT user_uid, interest_room_type_ids, hope_halls FROM profiles").fetchall()
has_interest = 0
has_halls = 0
for r in rows3:
    try:
        irti = json.loads(r['interest_room_type_ids']) if r['interest_room_type_ids'] else []
    except:
        irti = []
    try:
        hh = json.loads(r['hope_halls']) if r['hope_halls'] else []
    except:
        hh = []
    if irti:
        has_interest += 1
    if hh:
        has_halls += 1

print(f"\nTotal profiles: {len(rows3)}")
print(f"Has interest_room_type_ids: {has_interest}")
print(f"Has hope_halls: {has_halls}")

conn.close()
