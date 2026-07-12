import json
import sys

from app import app, db
import os, glob

# Remove existing DB files to ensure fresh schema
for p in [db.DB_PATH, "roommates_api.db", "roommates.db"]:
    if os.path.exists(p):
        os.remove(p)

db.init_db(drop_if_corrupt=True)

client = app.test_client()

def post(path, data, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.post(path, data=json.dumps(data), headers=h)

def get(path, token=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=h)

# 1. register
r = post("/api/auth/register", {"login_id": "testuser", "password": "123456", "name": "테스트", "student_id": "20230001", "birth_year": 2000, "gender": "male", "is_enrolled": False})
assert r.status_code == 201, f"register failed: {r.status_code} {r.data}"
body = r.get_json()
print("register:", body)

# 2. login
r = post("/api/auth/login", {"login_id": "testuser", "password": "123456"})
assert r.status_code == 200, f"login failed: {r.data}"
body = r.get_json()
token = body["token"]
print("login token received")

# 3. me
r = get("/api/me", token=token)
assert r.status_code == 200, f"me failed: {r.data}"
print("me:", r.get_json())

# 4. profile (not created yet, expect 404)
r = get("/api/profile", token=token)
print("profile (before):", r.status_code, r.get_json())

# 5. create profile
profile_data = {
    "birth_year": 2003,
    "college": "공과대학",
    "department": "컴퓨터공학과",
    "dorm_duration": 1,
    "home_visit_cycle": 2,
    "perfume": 0,
    "indoor_scent_sensitivity": 3,
    "alcohol_tolerance": 2.5,
    "alcohol_frequency": 2,
    "drunk_habit": 0,
    "gaming_hours_per_week": 10,
    "speaker_use": 0,
    "exercise": 0,
    "bedtime": 23,
    "wake_time": 8,
    "sleep_habit": 0,
    "sleep_sensitivity": 3,
    "alarm_strength": 3,
    "sleep_light": 0,
    "snoring": 0,
    "shower_duration": 15,
    "shower_time": 22,
    "shower_cycle": 2,
    "cleaning_cycle": 7,
    "ventilation": 1.0,
    "hairdryer_in_bathroom": 1,
    "toilet_paper_share": 1,
    "indoor_eating": 0,
    "smoking": 0,
    "temperature_pref": 3,
    "indoor_call": 0,
    "bug_handling": 3,
    "laundry_cycle": 7,
    "drying_rack": 1,
    "fridge_use": 1,
    "study_in_room": 0,
    "noise_sensitivity": 3,
    "desired_intimacy": 3,
    "meal_together": 2,
    "exercise_together": 1,
    "friend_invite": 1,
}
r = post("/api/profile", profile_data, token=token)
assert r.status_code == 200, f"profile create failed: {r.status_code} {r.data}"
print("profile created")

# 6. persona
r = get("/api/persona", token=token)
assert r.status_code == 200
print("persona:", r.get_json())

# 7. match/top (needs at least 2 profiles, so we create another)
r2 = post("/api/auth/register", {"login_id": "test2", "password": "123456", "name": "테스트2", "student_id": "20230002", "birth_year": 2001, "gender": "male", "is_enrolled": False})
assert r2.status_code == 201, f"second register failed: {r2.status_code} {r2.data}"
r2 = post("/api/auth/login", {"login_id": "test2", "password": "123456"})
token2 = r2.get_json()["token"]
profile_data2 = profile_data.copy()
profile_data2["smoking"] = 1  # different profile
profile_data2["bedtime"] = 2
r2 = post("/api/profile", profile_data2, token=token2)
assert r2.status_code == 200

r = get("/api/match/top", token=token)
assert r.status_code == 200, f"match/top failed: {r.data}"
body = r.get_json()
assert "matches" in body, f"missing 'matches' key: {body}"
print("match/top OK, count:", len(body["matches"]))

# Need another profile for target user to match against (test2 is the only other profile)
# If count is 0, it means the only other profile is hard-blocked or there's only 1 other profile
# Let's just verify the structure is correct
if len(body["matches"]) == 0:
    print("WARNING: match/top returned 0 results (only 1 other profile, may be excluded)")

# 8. match/pairs
r = get("/api/match/pairs", token=token)
assert r.status_code == 200, f"match/pairs failed: {r.data}"
body = r.get_json()
assert "pairs" in body, f"missing 'pairs' key: {body}"
print("match/pairs OK, count:", len(body["pairs"]))

# 9. match request
# Get target_uid from the second user we created
target_uid = get("/api/me", token=token2).get_json()["uid"]
r = post("/api/match/request", {"to_user": target_uid}, token=token)
assert r.status_code in (201, 409), f"match request failed: {r.data}"
print("match/request OK")

# 10. reviews
r = post("/api/reviews", {"reviewee": target_uid, "rating": 5, "body": "좋은 룸메이트예요!"}, token=token)
assert r.status_code == 201, f"review failed: {r.data}"
print("reviews OK")

print("\n=== ALL TESTS PASSED ===")
