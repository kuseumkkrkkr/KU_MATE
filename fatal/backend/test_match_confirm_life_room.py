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
    school = (res.get_json() or {}).get("schools", [])[0]
    college = (school.get("colleges") or [])[0]
    department = (college.get("departments") or [])[0]
    return {
        "school_name": school["name"],
        "college": college["name"],
        "department": department["name"],
    }


def _register_login_profile(client, login_id: str, school_ctx: dict):
    reg = _post(
        client,
        "/api/auth/register",
        {
            "login_id": login_id,
            "password": "123456",
            "name": login_id,
            "student_id": f"S{login_id}",
            "birth_year": 2002,
            "is_enrolled": True,
            "gender": "male",
            "school_name": school_ctx["school_name"],
            "college": school_ctx["college"],
            "department": school_ctx["department"],
        },
    )
    assert reg.status_code == 201, f"register failed: {reg.status_code} {reg.data}"
    login = _post(client, "/api/auth/login", {"login_id": login_id, "password": "123456"})
    assert login.status_code == 200, f"login failed: {login.status_code} {login.data}"
    token = login.get_json()["token"]
    me = _get(client, "/api/me", token)
    assert me.status_code == 200, f"me failed: {me.status_code} {me.data}"
    uid = me.get_json()["uid"]

    profile = _post(
        client,
        "/api/profile",
        {
            "matching_phase": "preliminary",
            "room_capacity": 2,
            "bedtime": 23,
            "wake_time": 8,
            "sleep_sensitivity": 3,
            "noise_sensitivity": 3,
            "desired_intimacy": 3,
            "smoking": 0,
        },
        token,
    )
    assert profile.status_code == 200, f"profile failed: {profile.status_code} {profile.data}"
    options = _get(client, "/api/matching/options", token)
    assert options.status_code == 200, f"matching/options failed: {options.status_code} {options.data}"
    room_type_id = int(options.get_json()["visible_room_types"][0]["id"])
    set_interest = _put(client, "/api/profile/interest-rooms", {"interest_room_type_ids": [room_type_id]}, token)
    assert set_interest.status_code == 200, f"interest-rooms failed: {set_interest.status_code} {set_interest.data}"
    return token, uid


def test_match_confirm_creates_life_room_for_both_users():
    _reset_db()
    client = app.test_client()
    school_ctx = _school_context(client)

    token_a, uid_a = _register_login_profile(client, "life_a", school_ctx)
    token_b, uid_b = _register_login_profile(client, "life_b", school_ctx)

    enter = _post(client, "/api/match/session/enter", {"candidates": [uid_b]}, token_a)
    assert enter.status_code == 201, f"enter_session failed: {enter.status_code} {enter.data}"
    session_id = enter.get_json()["session_id"]

    confirm_a = _post(client, "/api/match/confirm", {"session_id": session_id}, token_a)
    assert confirm_a.status_code == 200, f"confirm_a failed: {confirm_a.status_code} {confirm_a.data}"
    assert confirm_a.get_json().get("status") == "waiting"

    confirm_b = _post(client, "/api/match/confirm", {"session_id": session_id}, token_b)
    assert confirm_b.status_code == 200, f"confirm_b failed: {confirm_b.status_code} {confirm_b.data}"
    assert confirm_b.get_json().get("status") == "confirmed"

    life_a = _get(client, "/api/life-room/current", token_a)
    life_b = _get(client, "/api/life-room/current", token_b)
    assert life_a.status_code == 200 and life_b.status_code == 200
    room_a = (life_a.get_json() or {}).get("life_room")
    room_b = (life_b.get_json() or {}).get("life_room")
    assert room_a is not None, f"life room missing for user A: {life_a.get_json()}"
    assert room_b is not None, f"life room missing for user B: {life_b.get_json()}"
    assert room_a["uid"] == room_b["uid"], "both users must be linked to the same life room"
    assert room_a["status"] == "active", f"life room should be active: {room_a}"

