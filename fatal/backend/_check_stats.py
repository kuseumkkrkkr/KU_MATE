import sys, sqlite3
sys.path.insert(0, '.')
import db

conn = db.get_connection()
conn.row_factory = sqlite3.Row
genders = conn.execute("SELECT gender, COUNT(*) as cnt FROM users GROUP BY gender").fetchall()
for r in genders:
    print(f"{r['gender']}: {r['cnt']}")

profiles = db.fetch_profiles()
empty_hope = sum(1 for p in profiles if p.matching_phase == 'preliminary' and not p.hope_halls)
empty_interest = sum(1 for p in profiles if not p.interest_room_type_ids and not p.fixed_interest_room_type_id)
print(f"Preliminary with empty hope_halls: {empty_hope}")
print(f"Profiles with empty interest: {empty_interest}")
print(f"Total profiles: {len(profiles)}")
conn.close()
