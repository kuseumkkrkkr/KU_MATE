import sys
sys.path.insert(0, '.')
import db
import sqlite3
import json

conn = db.get_connection()
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT p.user_uid, u.login_id, u.gender, u.school_name, p.matching_phase, p.hope_halls, p.interest_room_type_ids, p.preferred_room_type_ids
    FROM profiles p JOIN users u ON u.uid=p.user_uid
    WHERE p.matching_phase='preliminary' AND u.gender='male'
    LIMIT 5
""").fetchall()
print(f"Male preliminary users: {len(rows)}")
for r in rows[:5]:
    d = dict(r)
    try:
        d['hope_halls'] = json.loads(d['hope_halls']) if d['hope_halls'] else []
    except:
        d['hope_halls'] = []
    try:
        d['interest_room_type_ids'] = json.loads(d['interest_room_type_ids']) if d['interest_room_type_ids'] else []
    except:
        d['interest_room_type_ids'] = []
    try:
        d['preferred_room_type_ids'] = json.loads(d['preferred_room_type_ids']) if d['preferred_room_type_ids'] else []
    except:
        d['preferred_room_type_ids'] = []
    print(d)

# Check if Flask server can be reached
conn.close()
