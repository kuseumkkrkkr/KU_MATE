import requests
import json

BASE = "http://localhost:5000/api"

with open("../dummy_credentials.json", encoding="utf-8") as f:
    creds = json.load(f)

for user in creds[:5]:
    r = requests.post(f"{BASE}/auth/login", json={"login_id": user["login_id"], "password": user["password"]})
    if r.status_code != 200:
        print(f"  {user['name']}: login failed")
        continue
    token = r.json()["token"]

    # Check profile
    pr = requests.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
    p = pr.json()
    irti = p.get("interest_room_type_ids", "N/A")
    firti = p.get("fixed_interest_room_type_id", "N/A")
    prti = p.get("preferred_room_type_ids", "N/A")
    frti = p.get("fixed_room_type_id", "N/A")
    hh = p.get("hope_halls", "N/A")
    phase = p.get("matching_phase", "N/A")
    print(f"  {user['name']}: phase={phase} hope_halls={hh} interest={irti} fixed_interest={firti} preferred={prti} fixed={frti}")

    # Try pool refresh
    rr = requests.post(f"{BASE}/match/pool/refresh", headers={"Authorization": f"Bearer {token}"})
    if rr.status_code != 200:
        print(f"    refresh ERROR {rr.status_code}: {rr.text[:200]}")
    else:
        cands = rr.json().get("candidates", [])
        print(f"    refresh OK: {len(cands)} candidates")
