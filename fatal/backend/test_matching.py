import json
import hashlib
import requests

BASE = "http://localhost:5000/api"

PERSONAS = ["standard", "owl", "morning", "social", "sensitive"]

def login(login_id, password="111111"):
    r = requests.post(f"{BASE}/auth/login", json={"login_id": login_id, "password": password})
    return r

def save_profile(token, data):
    return requests.post(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"}, json=data)

def refresh_pool(token):
    return requests.post(f"{BASE}/match/pool/refresh", headers={"Authorization": f"Bearer {token}"})

def make_profile(name, hope_halls, interest_ids, persona_type="standard", gender="male"):
    p = {
        "name": name, "matching_phase": "preliminary",
        "hope_halls": hope_halls, "accepted_hall": "",
        "room_capacity": 2,
        "preferred_room_type_ids": interest_ids[:1],
        "interest_room_type_ids": interest_ids,
        "fixed_room_type_id": 0, "fixed_interest_room_type_id": 0,
        "student_id": f"T-{name}", "birth_year": 2005,
        "college": "공과대학", "department": "컴퓨터공학과", "dorm_duration": 1,
        "home_visit_cycle": 2, "perfume": 0, "indoor_scent_sensitivity": 3,
        "alcohol_tolerance": 2.5, "alcohol_frequency": 2, "drunk_habit": 0,
        "gaming_hours_per_week": 10, "speaker_use": 0, "exercise": 0,
        "bedtime": 23, "wake_time": 8, "sleep_habit": 0,
        "sleep_sensitivity": 3, "alarm_strength": 3, "sleep_light": 0, "snoring": 0,
        "shower_duration": 15, "shower_time": 22, "shower_cycle": 2,
        "cleaning_cycle": 7, "ventilation": 1.0, "hairdryer_in_bathroom": 1,
        "toilet_paper_share": 1, "indoor_eating": 0, "smoking": 0,
        "temperature_pref": 3, "indoor_call": 0, "bug_handling": 3,
        "laundry_cycle": 7, "drying_rack": 1, "fridge_use": 1,
        "study_in_room": 0, "noise_sensitivity": 3,
        "desired_intimacy": 3, "meal_together": 2,
        "exercise_together": 1, "friend_invite": 1,
        "non_negotiable_items": [], "non_negotiable_weights": [],
    }
    import random
    if persona_type == "owl":
        p["bedtime"] = random.randint(1, 3); p["wake_time"] = random.randint(10, 12)
        p["gaming_hours_per_week"] = random.randint(15, 30)
    elif persona_type == "morning":
        p["bedtime"] = random.randint(22, 23); p["wake_time"] = random.randint(6, 7)
        p["gaming_hours_per_week"] = random.randint(0, 5); p["study_in_room"] = 1
        p["sleep_sensitivity"] = 4; p["noise_sensitivity"] = 4
    elif persona_type == "social":
        p["desired_intimacy"] = 5; p["friend_invite"] = 2; p["meal_together"] = 3
    elif persona_type == "sensitive":
        p["sleep_sensitivity"] = 5; p["noise_sensitivity"] = 5; p["indoor_scent_sensitivity"] = 5
    return p

# ---- Step 1: Save profiles for all mtest and ftest users ----
print("=" * 50)
print("STEP 1: Save profiles for test users")
print("=" * 50)

male_users = []
female_users = []

for i in range(10):
    lid = f"mtest_{i}"
    name = f"MTest{i}"
    r = login(lid)
    if r.status_code != 200:
        print(f"  {lid}: login failed, skip")
        continue
    token = r.json()["token"]
    uid = r.json()["user"]["uid"]
    persona = PERSONAS[i % len(PERSONAS)]
    p = make_profile(name, ["자유관", "미래관"], [924, 925], persona)
    sr = save_profile(token, p)
    status = "OK" if sr.status_code in (200, 201) else f"FAIL({sr.status_code})"
    print(f"  {lid}: profile save {status}")
    male_users.append({"lid": lid, "token": token, "uid": uid, "name": name})

for i in range(10):
    lid = f"ftest_{i}"
    name = f"FTest{i}"
    r = login(lid)
    if r.status_code != 200:
        print(f"  {lid}: login failed, skip")
        continue
    token = r.json()["token"]
    uid = r.json()["user"]["uid"]
    persona = PERSONAS[i % len(PERSONAS)]
    p = make_profile(name, ["정의관", "미래관"], [925, 926, 924], persona)
    sr = save_profile(token, p)
    status = "OK" if sr.status_code in (200, 201) else f"FAIL({sr.status_code})"
    print(f"  {lid}: profile save {status}")
    female_users.append({"lid": lid, "token": token, "uid": uid, "name": name})

print(f"\nReady: {len(male_users)} male, {len(female_users)} female")

# ---- Step 2: Pool refresh test ----
print("\n" + "=" * 50)
print("STEP 2: Pool refresh")
print("=" * 50)

for u in male_users[:2] + female_users[:2]:
    name = u["name"]
    token = u["token"]
    print(f"\n  {name} refresh...")
    r = refresh_pool(token)
    if r.status_code != 200:
        print(f"    ERROR {r.status_code}: {r.text[:300]}")
        continue
    cands = r.json().get("candidates", [])
    print(f"    Candidates: {len(cands)}")
    for c in cands[:3]:
        dn = c.get("display_name", "?")
        sc = c.get("shared_score", c.get("score", "?"))
        tier = c.get("tier", "?")
        ct = c.get("candidate_type", "?")
        print(f"      {dn} | score={sc} | tier={tier} | type={ct}")

# ---- Step 3: Also test dummy_credentials users ----
print("\n" + "=" * 50)
print("STEP 3: Dummy credentials users")
print("=" * 50)

with open("../dummy_credentials.json", encoding="utf-8") as f:
    dummies = json.load(f)

for d in dummies[:5]:
    lid = d["login_id"]
    pw = d["password"]
    r = login(lid, pw)
    if r.status_code != 200:
        print(f"  {d['name']} ({lid}): login failed")
        continue
    token = r.json()["token"]
    rr = refresh_pool(token)
    if rr.status_code != 200:
        print(f"  {d['name']}: refresh ERROR {rr.status_code} {rr.text[:200]}")
    else:
        cands = rr.json().get("candidates", [])
        print(f"  {d['name']}: {len(cands)} candidates")

print("\nDONE")
