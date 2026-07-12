import sys, sqlite3, json
sys.path.insert(0, '.')
import db

conn = db.get_connection()
conn.row_factory = sqlite3.Row

r = conn.execute("""
    SELECT p.interest_room_type_ids, p.fixed_interest_room_type_id
    FROM profiles p JOIN users u ON u.uid = p.user_uid
    WHERE u.gender = 'male' AND (p.interest_room_type_ids = '[]' OR p.interest_room_type_ids IS NULL) AND COALESCE(p.fixed_interest_room_type_id, 0) = 0
""").fetchall()
print(f"Males with empty interest: {len(r)}")

r2 = conn.execute("""
    SELECT p.interest_room_type_ids, p.fixed_interest_room_type_id
    FROM profiles p JOIN users u ON u.uid = p.user_uid
    WHERE u.gender = 'female' AND (p.interest_room_type_ids = '[]' OR p.interest_room_type_ids IS NULL) AND COALESCE(p.fixed_interest_room_type_id, 0) = 0
""").fetchall()
print(f"Females with empty interest: {len(r2)}")

r3 = conn.execute("""
    SELECT COUNT(*) as cnt FROM match_pool_candidates
""").fetchone()
print(f"match_pool_candidates rows: {r3['cnt']}")

r4 = conn.execute("""
    SELECT COUNT(*) as cnt FROM match_sessions
""").fetchone()
print(f"match_sessions rows: {r4['cnt']}")

r5 = conn.execute("""
    SELECT COUNT(*) as cnt FROM match_pool_refresh_log
""").fetchone()
print(f"match_pool_refresh_log rows: {r5['cnt']}")

conn.close()
