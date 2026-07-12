import requests
import json

BASE = "http://localhost:5000/api"

def login(lid, pw="111111"):
    r = requests.post(f"{BASE}/auth/login", json={"login_id": lid, "password": pw})
    return r

def auth(token):
    return {"Authorization": f"Bearer {token}"}

r0 = login("mtest_0")
token0 = r0.json()["token"]
uid0 = r0.json()["user"]["uid"]

r = requests.get(f"{BASE}/match/pool", headers=auth(token0))
pool = r.json()
cands = pool.get("candidates", [])
print(f"Pool: {len(cands)} candidates")

if not cands:
    print("No candidates, cannot test session")
    exit(1)

top = cands[0]
cand_uid = top.get("user_uid", "")
cand_name = top.get("display_name", "?")
print(f"Top candidate: {cand_name} uid={cand_uid[:12]}")

r = requests.post(f"{BASE}/match/session/enter", headers=auth(token0), json={"candidates": [cand_uid]})
print(f"Enter session: {r.status_code}")
data = r.json()
print(json.dumps(data, indent=2, ensure_ascii=False)[:600])

session_uid = data.get("session_id", "")
thread_ids = data.get("thread_ids", [])
print(f"Session created: {session_uid[:12]}")
print(f"Thread IDs: {thread_ids}")

thread_uid = thread_ids[0] if thread_ids else ""

for i in range(10):
    lr = login(f"mtest_{i}")
    if lr.status_code == 200 and lr.json()["user"]["uid"] == cand_uid:
        token1 = lr.json()["token"]
        ar = requests.post(f"{BASE}/match/session/enter", headers=auth(token1), json={"candidates": [uid0]})
        print(f"Candidate enter: {ar.status_code}")
        print(json.dumps(ar.json(), indent=2, ensure_ascii=False)[:300])

        if thread_uid:
            r = requests.post(f"{BASE}/chat/threads/{thread_uid}/messages", headers=auth(token1), json={"content": "hello from candidate"})
            print(f"Chat send: {r.status_code}")

            r = requests.get(f"{BASE}/chat/threads/{thread_uid}/messages", headers=auth(token1))
            print(f"Chat messages: {r.status_code}")
            try:
                print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:400])
            except:
                print(r.text[:400])
        break
else:
    print("Could not find candidate login in mtest_0-9")
