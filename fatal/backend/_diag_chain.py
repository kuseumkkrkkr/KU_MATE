import requests, json, sys

BASE = "http://localhost:5000/api"

with open("../dummy_credentials.json", encoding="utf-8") as f:
    creds = json.load(f)

# Pick a random female user (since they had 0 candidates before)
# Also test a male user
tested = 0
for user in creds:
    if tested >= 3:
        break
    lid = user["login_id"]
    pw = user["password"]

    # 1. Login
    r = requests.post(f"{BASE}/auth/login", json={"login_id": lid, "password": pw})
    if r.status_code != 200:
        continue
    token = r.json()["token"]
    user_uid = r.json()["user"]["uid"]

    # 2. GET /auth/me (like _loadMe)
    me = requests.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    gender = me.json().get("gender", "?")
    name = me.json().get("name", "?")

    # 3. GET /profile (like _hasSavedProfile)
    pr = requests.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
    p = pr.json()
    if p.get("exists") == False or p.get("error"):
        print(f"\n{name} ({gender}): NO PROFILE - skipping")
        continue

    phase = p.get("matching_phase", "?")
    hope_halls = p.get("hope_halls", "?")
    interest = p.get("interest_room_type_ids", "?")
    fixed_interest = p.get("fixed_interest_room_type_id", "?")
    preferred = p.get("preferred_room_type_ids", "?")
    fixed_room = p.get("fixed_room_type_id", "?")

    print(f"\n{'='*60}")
    print(f"USER: {name} ({gender}) uid={user_uid[:10]}")
    print(f"  phase={phase} hope_halls={hope_halls}")
    print(f"  interest={interest} fixed_interest={fixed_interest}")
    print(f"  preferred={preferred} fixed_room={fixed_room}")

    # 4. GET /matching/options (like HomeScreen check)
    opts = requests.get(f"{BASE}/matching/options", headers={"Authorization": f"Bearer {token}"})
    if opts.status_code != 200:
        print(f"  GET /matching/options FAILED: {opts.status_code} {opts.text[:200]}")
        continue
    opts_data = opts.json()
    has_interest = opts_data.get("has_interest_rooms", "?")
    needs_confirm = opts_data.get("needs_hall_confirmation", "?")
    opt_phase = opts_data.get("phase", "?")
    print(f"  matching/options: phase={opt_phase} has_interest_rooms={has_interest} needs_confirm={needs_confirm}")

    # 5. GET /match/pool (like fetchPool)
    pool = requests.get(f"{BASE}/match/pool", headers={"Authorization": f"Bearer {token}"})
    if pool.status_code != 200:
        print(f"  GET /match/pool FAILED: {pool.status_code} {pool.text[:200]}")
        continue
    pool_data = pool.json()
    existing_cands = pool_data.get("candidates", [])
    print(f"  GET /match/pool: {len(existing_cands)} existing candidates")

    # 6. POST /match/pool/refresh (like refreshPool)
    rr = requests.post(f"{BASE}/match/pool/refresh", headers={"Authorization": f"Bearer {token}"}, timeout=120)
    if rr.status_code != 200:
        print(f"  POST /match/pool/refresh FAILED: {rr.status_code}")
        print(f"    Error: {rr.text[:300]}")
    else:
        refreshed = rr.json().get("candidates", [])
        print(f"  POST /match/pool/refresh: {len(refreshed)} candidates")
        for c in refreshed[:3]:
            dn = c.get("display_name", "?")
            sc = c.get("shared_score", c.get("score", "?"))
            tier = c.get("tier", "?")
            ct = c.get("candidate_type", "?")
            print(f"    {dn} | score={sc} | tier={tier} | type={ct}")

    # 7. POST /match/session/enter with top candidate (like enterSession)
    if rr.status_code == 200 and len(rr.json().get("candidates", [])) > 0:
        top_uid = rr.json()["candidates"][0].get("user_uid", "")
        if top_uid:
            sr = requests.post(f"{BASE}/match/session/enter", headers={"Authorization": f"Bearer {token}"}, json={"candidates": [top_uid]})
            print(f"  POST /match/session/enter: {sr.status_code}")
            if sr.status_code != 200 and sr.status_code != 201:
                print(f"    Error: {sr.text[:200]}")
            else:
                print(f"    OK - session created")

    tested += 1

print(f"\n=== DONE ({tested} users tested) ===")
