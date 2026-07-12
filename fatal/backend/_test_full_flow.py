import requests
import json

BASE = "http://localhost:5000/api"

def auth(token):
    return {"Authorization": f"Bearer {token}"}

# Login as a dummy user
with open("../dummy_credentials.json", encoding="utf-8") as f:
    creds = json.load(f)

user = creds[0]
print(f"Testing with: {user['name']} ({user['login_id']})")

r = requests.post(f"{BASE}/auth/login", json={"login_id": user["login_id"], "password": user["password"]})
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text[:200]}")
    exit(1)
token = r.json()["token"]
user_uid = r.json()["user"]["uid"]
print(f"Login OK, uid={user_uid[:12]}")

# Step 1: GET /matching/options (like HomeScreen does)
print("\n--- Step 1: GET /matching/options ---")
r = requests.get(f"{BASE}/matching/options", headers=auth(token))
print(f"Status: {r.status_code}")
opts = r.json()
print(f"  phase: {opts.get('phase')}")
print(f"  has_interest_rooms: {opts.get('has_interest_rooms')}")
print(f"  needs_hall_confirmation: {opts.get('needs_hall_confirmation')}")

# Step 2: POST /profile (like SurveyScreen does - sends empty interest fields)
print("\n--- Step 2: POST /profile (survey save) ---")
profile_data = {
    "matching_phase": "preliminary",
    "hope_halls": ["\uc790\uc720\uad00", "\ubbf8\ub798\uad00"],
    "room_capacity": 2,
    "bedtime": 23, "wake_time": 8,
    "sleep_sensitivity": 3, "noise_sensitivity": 3,
    "desired_intimacy": 3,
}
r = requests.post(f"{BASE}/profile", headers=auth(token), json=profile_data)
print(f"Status: {r.status_code}")
if r.status_code in (200, 201):
    saved = r.json()
    irti = saved.get("interest_room_type_ids", "NOT_IN_RESPONSE")
    prti = saved.get("preferred_room_type_ids", "NOT_IN_RESPONSE")
    firti = saved.get("fixed_interest_room_type_id", "NOT_IN_RESPONSE")
    print(f"  interest_room_type_ids: {irti}")
    print(f"  preferred_room_type_ids: {prti}")
    print(f"  fixed_interest_room_type_id: {firti}")
else:
    print(f"  Error: {r.text[:300]}")

# Step 3: GET /profile/interest-rooms (like InterestRoomsScreen)
print("\n--- Step 3: GET /profile/interest-rooms ---")
r = requests.get(f"{BASE}/profile/interest-rooms", headers=auth(token))
print(f"Status: {r.status_code}")
if r.status_code == 200:
    rooms = r.json().get("interest_rooms", [])
    print(f"  Available rooms: {len(rooms)}")
    for rm in rooms[:5]:
        print(f"    id={rm.get('id')} name={rm.get('dorm_name')} cap={rm.get('capacity')}")

# Step 4: PUT /profile/interest-rooms (select interest rooms)
print("\n--- Step 4: PUT /profile/interest-rooms ---")
if r.status_code == 200:
    rooms = r.json().get("interest_rooms", [])
    room_ids = [rm["id"] for rm in rooms[:2]]
    print(f"  Selecting room IDs: {room_ids}")
    r = requests.put(f"{BASE}/profile/interest-rooms", headers=auth(token), json={"interest_room_type_ids": room_ids})
    print(f"  Status: {r.status_code}")
    if r.status_code != 200:
        print(f"  Error: {r.text[:300]}")
    else:
        result = r.json()
        print(f"  ok: {result.get('ok')}")

# Step 5: POST /matching/preferences (like MatchingSplitScreen)
print("\n--- Step 5: POST /matching/preferences ---")
r = requests.post(f"{BASE}/matching/preferences", headers=auth(token), json={"selected_room_type_ids": room_ids})
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(f"Error: {r.text[:300]}")
else:
    pref_result = r.json()
    print(f"  ok: {pref_result.get('ok')} phase: {pref_result.get('phase')}")

# Step 6: POST /match/pool/refresh
print("\n--- Step 6: POST /match/pool/refresh ---")
r = requests.post(f"{BASE}/match/pool/refresh", headers=auth(token))
print(f"Status: {r.status_code}")
if r.status_code == 200:
    cands = r.json().get("candidates", [])
    print(f"  Candidates: {len(cands)}")
    for c in cands[:3]:
        print(f"    {c.get('display_name','?')} | score={c.get('shared_score', c.get('score','?'))} | tier={c.get('tier','?')}")
else:
    print(f"Error: {r.text[:300]}")

# Step 7: POST /match/session/enter (like MatchScreen)
print("\n--- Step 7: POST /match/session/enter ---")
if r.status_code == 200 and cands:
    cand_uid = cands[0].get("user_uid", "")
    r = requests.post(f"{BASE}/match/session/enter", headers=auth(token), json={"candidates": [cand_uid]})
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:300]}")
else:
    print("No candidates available for session")

# Step 8: Test confirm_change with bool (like frontend sends)
print("\n--- Step 8: Test confirm_change with bool type ---")
r = requests.post(f"{BASE}/matching/preferences", headers=auth(token), json={"selected_room_type_ids": room_ids, "confirm_change": True})
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")

print("\n=== ALL TESTS DONE ===")
