import requests, json, time

BASE = "http://localhost:5000/api"

with open("../dummy_credentials.json", encoding="utf-8") as f:
    creds = json.load(f)

user = creds[0]
r = requests.post(f"{BASE}/auth/login", json={"login_id": user["login_id"], "password": user["password"]})
if r.status_code != 200:
    print(f"login failed: {r.status_code}")
    exit(1)
token = r.json()["token"]

# Check profile fields first
pr = requests.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
p = pr.json()
print(f"Profile: phase={p.get('matching_phase')} interest={p.get('interest_room_type_ids')} preferred={p.get('preferred_room_type_ids')} fixed_interest={p.get('fixed_interest_room_type_id')} hope_halls={p.get('hope_halls')}")

# Pool refresh
t0 = time.time()
rr = requests.post(f"{BASE}/match/pool/refresh", headers={"Authorization": f"Bearer {token}"}, timeout=120)
t1 = time.time()
print(f"refresh: {rr.status_code} in {t1-t0:.1f}s")
if rr.status_code != 200:
    print(f"Error: {rr.text[:300]}")
else:
    cands = rr.json().get("candidates", [])
    print(f"candidates: {len(cands)}")
    for c in cands[:3]:
        dn = c.get("display_name", "?")
        sc = c.get("shared_score", c.get("score", "?"))
        tier = c.get("tier", "?")
        print(f"  {dn} score={sc} tier={tier}")

# Also test a female user
for user in creds:
    r2 = requests.post(f"{BASE}/auth/login", json={"login_id": user["login_id"], "password": user["password"]})
    if r2.status_code != 200:
        continue
    # Get user gender 
    me = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {r2.json()['token']}"})
    if me.json().get("gender") == "female":
        token_f = r2.json()["token"]
        pf = requests.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token_f}"})
        fp = pf.json()
        print(f"\nFemale user: {fp.get('name')} phase={fp.get('matching_phase')} interest={fp.get('interest_room_type_ids')} hope_halls={fp.get('hope_halls')}")
        t0 = time.time()
        rf = requests.post(f"{BASE}/match/pool/refresh", headers={"Authorization": f"Bearer {token_f}"}, timeout=120)
        t1 = time.time()
        print(f"refresh: {rf.status_code} in {t1-t0:.1f}s")
        if rf.status_code == 200:
            fc = rf.json().get("candidates", [])
            print(f"candidates: {len(fc)}")
        else:
            print(f"Error: {rf.text[:300]}")
        break
