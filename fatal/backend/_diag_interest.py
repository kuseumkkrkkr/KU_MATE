import sys, sqlite3, json
sys.path.insert(0, '.')
import db

conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Check how many profiles have empty interest and empty fixed_interest
r = conn.execute("""
    SELECT u.gender,
           SUM(CASE WHEN (p.interest_room_type_ids = '[]' OR p.interest_room_type_ids IS NULL) AND COALESCE(p.fixed_interest_room_type_id, 0) = 0 THEN 1 ELSE 0 END) as empty_interest,
           SUM(CASE WHEN COALESCE(p.fixed_interest_room_type_id, 0) != 0 OR (p.interest_room_type_ids != '[]' AND p.interest_room_type_ids IS NOT NULL) THEN 1 ELSE 0 END) as has_interest,
           COUNT(*) as total
    FROM profiles p JOIN users u ON u.uid = p.user_uid
    WHERE p.matching_phase = 'preliminary'
    GROUP BY u.gender
""").fetchall()

for row in r:
    print(f"Gender={row['gender']}: empty_interest={row['empty_interest']} has_interest={row['has_interest']} total={row['total']}")

# Check a sample male with empty interest
r2 = conn.execute("""
    SELECT u.name, u.gender, p.interest_room_type_ids, p.fixed_interest_room_type_id, p.preferred_room_type_ids, p.fixed_room_type_id, p.hope_halls, p.matching_phase
    FROM profiles p JOIN users u ON u.uid = p.user_uid
    WHERE u.gender = 'male' AND (p.interest_room_type_ids = '[]' OR p.interest_room_type_ids IS NULL) AND COALESCE(p.fixed_interest_room_type_id, 0) = 0
    LIMIT 5
""").fetchall()

print(f"\nSample males with empty interest:")
for row in r2:
    print(f"  {row['name']}: interest={row['interest_room_type_ids']} fixed_interest={row['fixed_interest_room_type_id']} preferred={row['preferred_room_type_ids']} hope_halls={row['hope_halls']}")

conn.close()
