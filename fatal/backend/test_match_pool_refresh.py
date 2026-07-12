import json
import os

from app import app, db


def _reset_db():
    for path in [db.DB_PATH, "roommates_api.db", "roommates.db", "forlocal.db"]:
        if os.path.exists(path):
            os.remove(path)
    db.init_db(drop_if_corrupt=True)


def _post(client, path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(path, data=json.dumps(data), headers=headers)


def _put(client, path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.put(path, data=json.dumps(data), headers=headers)


def _get(client, path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=headers)


def _school_context(client):
    res = _get(client, "/api/schools")
    assert res.status_code == 200, f"/api/schools failed: {res.status_code} {res.data}"
    schools = list((res.get_json() or {}).get("schools") or [])
    assert schools, "at least one school must exist"
    school = schools[0]
    colleges = list(school.get("colleges") or [])
    assert colleges, "school must have colleges"
    departments = list((colleges[0] or {}).get("departments") or [])
    assert departments, "college must have departments"
    return {
        "school_name": school["name"],
        "college": colleges[0]["name"],
        "department": departments[0]["name"],
    }


def _register_and_login(client, login_id: str, name: str, student_id: str, school_ctx: dict):
    register_payload = {
        "login_id": login_id,
        "password": "123456",
        "name": name,
        "student_id": student_id,
        "birth_year": 2002,
        "is_enrolled": True,
        "gender": "male",
        "school_name": school_ctx["school_name"],
        "college": school_ctx["college"],
        "department": school_ctx["department"],
        "region_name": "seoul",
    }
    reg = _post(client, "/api/auth/register", register_payload)
    assert reg.status_code == 201, f"register failed: {reg.status_code} {reg.data}"

    login = _post(client, "/api/auth/login", {"login_id": login_id, "password": "123456"})
    assert login.status_code == 200, f"login failed: {login.status_code} {login.data}"
    token = login.get_json()["token"]

    me = _get(client, "/api/me", token)
    assert me.status_code == 200, f"me failed: {me.status_code} {me.data}"
    return token, me.get_json()["uid"]


def _create_profile(client, token: str, bedtime: int, wake_time: int):
    payload = {
        "matching_phase": "preliminary",
        "room_capacity": 2,
        "bedtime": bedtime,
        "wake_time": wake_time,
        "sleep_sensitivity": 3,
        "noise_sensitivity": 3,
        "desired_intimacy": 3,
        "smoking": 0,
        "gaming_hours_per_week": 8,
        "study_in_room": 0,
    }
    res = _post(client, "/api/profile", payload, token)
    assert res.status_code == 200, f"profile create failed: {res.status_code} {res.data}"


def _set_interest_room_type(client, token: str):
    options = _get(client, "/api/matching/options", token)
    assert options.status_code == 200, f"matching/options failed: {options.status_code} {options.data}"
    visible_room_types = list((options.get_json() or {}).get("visible_room_types") or [])
    assert visible_room_types, "visible_room_types must not be empty"
    room_type_id = int(visible_room_types[0]["id"])
    put_res = _put(client, "/api/profile/interest-rooms", {"interest_room_type_ids": [room_type_id]}, token)
    assert put_res.status_code == 200, f"interest-rooms failed: {put_res.status_code} {put_res.data}"


def test_refresh_pool_creates_candidates():
    _reset_db()
    client = app.test_client()
    school_ctx = _school_context(client)

    token_a, uid_a = _register_and_login(client, "pool_a", "pool_a", "20230001", school_ctx)
    token_b, uid_b = _register_and_login(client, "pool_b", "pool_b", "20230002", school_ctx)

    _create_profile(client, token_a, bedtime=23, wake_time=8)
    _create_profile(client, token_b, bedtime=23, wake_time=8)

    _set_interest_room_type(client, token_a)
    _set_interest_room_type(client, token_b)

    refresh = _post(client, "/api/match/pool/refresh", {}, token_a)
    assert refresh.status_code == 200, f"pool/refresh failed: {refresh.status_code} {refresh.data}"
    candidates = list((refresh.get_json() or {}).get("candidates") or [])
    assert candidates, "refresh should produce at least one candidate"

    individual_user_uids = {
        c.get("user_uid")
        for c in candidates
        if (c.get("candidate_type") or "individual") == "individual"
    }
    assert uid_b in individual_user_uids, f"target candidate {uid_b} missing: {candidates}"

    pool = _get(client, "/api/match/pool", token_a)
    assert pool.status_code == 200, f"pool failed: {pool.status_code} {pool.data}"
    persisted = list((pool.get_json() or {}).get("candidates") or [])
    assert persisted, "pool should persist generated candidates"

    persisted_individual_uids = {
        c.get("user_uid")
        for c in persisted
        if (c.get("candidate_type") or "individual") == "individual"
    }
    assert uid_b in persisted_individual_uids, f"persisted candidate {uid_b} missing: {persisted}"


def test_refresh_pool_returns_empty_when_candidate_interest_room_missing():
    _reset_db()
    client = app.test_client()
    school_ctx = _school_context(client)

    token_a, _ = _register_and_login(client, "pool_c", "pool_c", "20230101", school_ctx)
    token_b, uid_b = _register_and_login(client, "pool_d", "pool_d", "20230102", school_ctx)

    _create_profile(client, token_a, bedtime=23, wake_time=8)
    _create_profile(client, token_b, bedtime=23, wake_time=8)

    _set_interest_room_type(client, token_a)

    refresh = _post(client, "/api/match/pool/refresh", {}, token_a)
    assert refresh.status_code == 200, f"pool/refresh failed: {refresh.status_code} {refresh.data}"
    candidates = list((refresh.get_json() or {}).get("candidates") or [])
    assert not candidates, f"candidates should be empty when candidate interest room is missing: {candidates}"

    _set_interest_room_type(client, token_b)
    refresh_after_fix = _post(client, "/api/match/pool/refresh", {}, token_a)
    assert refresh_after_fix.status_code == 200, (
        f"pool/refresh after fix failed: {refresh_after_fix.status_code} {refresh_after_fix.data}"
    )
    candidates_after_fix = list((refresh_after_fix.get_json() or {}).get("candidates") or [])
    assert candidates_after_fix, "candidates should be created after setting candidate interest room"
    uids = {
        c.get("user_uid")
        for c in candidates_after_fix
        if (c.get("candidate_type") or "individual") == "individual"
    }
    assert uid_b in uids, f"expected candidate {uid_b} after fix: {candidates_after_fix}"
