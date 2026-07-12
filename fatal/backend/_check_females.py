import sys
sys.path.insert(0, '.')
import db
import sqlite3
import json

conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Find ftest_0's user_uid
user = db.get_user_by_login_id("ftest_0")
if not user:
    print("ftest_0 user not found")
    sys.exit(1)

print(f"ftest_0: uid={user.uid}, gender={user.gender}, school={user.school_name}")

profile = db.get_profile_by_user_uid(user.uid)
if profile:
    print(f"  matching_phase: {profile.matching_phase}")
    print(f"  hope_halls: {profile.hope_halls}")
    print(f"  interest_room_type_ids: {profile.interest_room_type_ids}")
    print(f"  preferred_room_type_ids: {profile.preferred_room_type_ids}")
    print(f"  room_capacity: {profile.room_capacity}")

# Check how many female preliminary profiles exist with overlapping hope_halls
rows = conn.execute("""
    SELECT p.user_uid, p.name, p.matching_phase, p.hope_halls, p.interest_room_type_ids, p.room_capacity, u.gender
    FROM profiles p JOIN users u ON u.uid = p.user_uid
    WHERE u.gender = 'female' AND p.matching_phase = 'preliminary'
""").fetchall()

print(f"\nFemale preliminary profiles: {len(rows)}")
for r in rows[:10]:
    hh = r['hope_halls']
    irti = r['interest_room_type_ids']
    try:
        hh_list = json.loads(hh) if hh else []
    except:
        hh_list = []
    try:
        irti_list = json.loads(irti) if irti else []
    except:
        irti_list = []
    print(f"  {r['name']}: halls={hh_list} interest={irti_list} cap={r['room_capacity']}")

conn.close()
