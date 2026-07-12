"""Flask backend for Roomantic roommate matching app."""

import uuid
import datetime
import queue
import sqlite3
import threading
import json
import hashlib
import random
from typing import Dict, Set, Any

from flask import Flask, request, jsonify, Response, stream_with_context, render_template
from flask_cors import CORS

import db
from models import User, RoommateProfile, profile_to_dict, classify_persona
from matcher import rank_matches, best_pairings, match, normalize_persona
from auth import hash_password, verify_password, create_token, login_required

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
FORLOCAL_DB_PATH = "forlocal.db"

# In-memory SSE queues: user_uid -> [queue]
_SSE_QUEUES: Dict[str, list] = {}
_SSE_LOCK = threading.Lock()


def _add_sse_queue(user_uid: str, q: queue.Queue):
    with _SSE_LOCK:
        _SSE_QUEUES.setdefault(user_uid, []).append(q)


def _remove_sse_queue(user_uid: str, q: queue.Queue):
    with _SSE_LOCK:
        queues = _SSE_QUEUES.get(user_uid, [])
        if q in queues:
            queues.remove(q)
        if not queues:
            _SSE_QUEUES.pop(user_uid, None)


def broadcast_message(user_uid: str, event_type: str, data: dict):
    with _SSE_LOCK:
        queues = _SSE_QUEUES.get(user_uid, [])
        for q in list(queues):
            try:
                q.put({"event": event_type, "data": data}, block=False)
            except queue.Full:
                pass


def generate_uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _parse_ts(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _forlocal_conn() -> sqlite3.Connection:
    conn = db.get_connection(FORLOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS local_chat_snapshots ("
        "user_uid TEXT NOT NULL, "
        "thread_uid TEXT NOT NULL, "
        "messages_json TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, "
        "PRIMARY KEY(user_uid, thread_uid)"
        ")"
    )
    conn.commit()
    return conn


def _app_conn() -> sqlite3.Connection:
    conn = db.get_connection(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _schools_conn() -> sqlite3.Connection:
    conn = db.get_connection(db.SCHOOLS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_notices_tables(conn: sqlite3.Connection):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS global_notices ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "body TEXT NOT NULL, "
        "is_pinned INTEGER NOT NULL DEFAULT 0, "
        "is_collapsed INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS school_notices ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "school_id INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "body TEXT NOT NULL, "
        "is_pinned INTEGER NOT NULL DEFAULT 0, "
        "is_collapsed INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, "
        "FOREIGN KEY(school_id) REFERENCES schools(id) ON DELETE CASCADE)"
    )


def _notice_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "is_pinned": bool(row["is_pinned"]),
        "is_collapsed": bool(row["is_collapsed"]) if "is_collapsed" in row.keys() else False,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _seed_default_notices_if_empty(conn: sqlite3.Connection):
    _ensure_notices_tables(conn)
    # Legacy notices -> global_notices one-way migration
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notices ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL, "
        "is_pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    legacy_rows = conn.execute(
        "SELECT title, body, is_pinned, created_at, updated_at FROM notices ORDER BY id ASC"
    ).fetchall()
    for row in legacy_rows:
        dup = conn.execute(
            "SELECT 1 FROM global_notices WHERE title=? AND body=? LIMIT 1",
            (row["title"], row["body"]),
        ).fetchone()
        if dup:
            continue
        conn.execute(
            "INSERT INTO global_notices (title, body, is_pinned, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (row["title"], row["body"], row["is_pinned"], row["created_at"], row["updated_at"]),
        )

    count = conn.execute("SELECT COUNT(*) AS c FROM global_notices").fetchone()["c"]
    if int(count or 0) > 0:
        return
    defaults = [
        (
            "룸앤틱 베타 서비스 오픈",
            "룸앤틱 베타 서비스를 시작했습니다. 성향 기반으로 기숙사 룸메이트를 찾아보세요.",
            0,
            "2026-05-01T00:00:00Z",
            "2026-05-01T00:00:00Z",
        ),
        (
            "설문 기능 업데이트",
            "설문 수정과 유형 상세 비교 기능을 개선했습니다.",
            0,
            "2026-05-03T00:00:00Z",
            "2026-05-03T00:00:00Z",
        ),
        (
            "매칭 알고리즘 개선",
            "성향 분석 정확도와 우선순위 기반 매칭 로직을 업데이트했습니다.",
            0,
            "2026-05-08T00:00:00Z",
            "2026-05-08T00:00:00Z",
        ),
        (
            "실시간 알림 기능 안내",
            "중요 공지와 매칭 요청 알림을 실시간으로 받아볼 수 있습니다.",
            1,
            "2026-05-10T00:00:00Z",
            "2026-05-10T00:00:00Z",
        ),
    ]
    for title, body, pinned, created_at, updated_at in defaults:
        conn.execute(
            "INSERT INTO global_notices (title, body, is_pinned, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, body, pinned, created_at, updated_at),
        )
    conn.commit()


def _ensure_thread_leaves_table(conn: sqlite3.Connection):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chat_thread_leaves ("
        "thread_uid TEXT NOT NULL, "
        "user_uid TEXT NOT NULL, "
        "left_at TEXT NOT NULL, "
        "PRIMARY KEY(thread_uid, user_uid)"
        ")"
    )
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", ""))
    except Exception:
        return None


def _tier_from_score(score: float) -> str:
    if score >= 90:
        return "90-100"
    if score >= 80:
        return "80-90"
    if score >= 70:
        return "70-80"
    if score >= 60:
        return "60-80"
    return "under-70"


def _to_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except Exception:
        return None


def _get_school_row(school_name: str):
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM schools WHERE name=?", (school_name,)).fetchone()
    conn.close()
    return row


def _school_matching_phase(school_row, today: datetime.date | None = None) -> str:
    if not school_row:
        return "closed"
    if int(school_row["matching_enabled"] or 0) != 1:
        return "closed"
    today = today or datetime.date.today()
    pre_start = _to_date(school_row["pre_matching_start"]) or _to_date(school_row["recruitment_start"])
    pre_end = _to_date(school_row["pre_matching_end"])
    apply_start = _to_date(school_row["roommate_apply_start"])
    apply_end = _to_date(school_row["roommate_apply_end"]) or _to_date(school_row["recruitment_end"])
    life_start = _to_date(school_row["room_life_start"])
    life_end = _to_date(school_row["room_life_end"])
    if pre_start and pre_end and pre_start <= today <= pre_end:
        return "preliminary"
    if apply_start and apply_end and apply_start <= today <= apply_end:
        return "main"
    if life_start and life_end and life_start <= today <= life_end:
        return "life"
    if pre_start and not pre_end:
        return "preliminary"
    if apply_start and not apply_end:
        return "main"
    return "closed"


def _selection_limit(total_count: int, phase: str) -> int:
    if phase == "main":
        return 1
    if total_count <= 4:
        return min(2, total_count)
    return max(1, round(total_count * 0.4))


def _count_distinct_dorms(room_type_ids: list[int], school_id: int) -> int:
    if not room_type_ids:
        return 0
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    placeholders = ",".join(["?"] * len(room_type_ids))
    rows = conn.execute(
        f"SELECT COUNT(DISTINCT rt.dorm_id) AS cnt FROM dorm_room_types rt "
        f"WHERE rt.id IN ({placeholders}) AND rt.dorm_id IN (SELECT id FROM dormitories WHERE school_id=?)",
        (*room_type_ids, school_id),
    ).fetchall()
    conn.close()
    return int(rows[0]["cnt"]) if rows else 0


def _get_room_types_for_school(school_id: int):
    conn = _schools_conn()
    rows = conn.execute(
        "SELECT rt.id, rt.is_enabled, d.gender AS dorm_gender "
        "FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id "
        "WHERE d.school_id=?",
        (school_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _has_valid_survey_profile(profile: RoommateProfile | None) -> bool:
    if not profile:
        return False
    required_values = [
        profile.bedtime,
        profile.wake_time,
        profile.sleep_sensitivity,
        profile.noise_sensitivity,
        profile.desired_intimacy,
    ]
    return all(v is not None for v in required_values)


def _active_life_room_for_user(conn: sqlite3.Connection, user_uid: str):
    return conn.execute(
        "SELECT lr.* FROM life_rooms lr "
        "JOIN life_room_members lm ON lm.life_room_uid=lr.uid "
        "WHERE lm.user_uid=? AND lm.is_active=1 AND lr.status='active' "
        "ORDER BY lr.created_at DESC LIMIT 1",
        (user_uid,),
    ).fetchone()


def _get_school_row_by_id(school_id: int):
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM schools WHERE id=?", (school_id,)).fetchone()
    conn.close()
    return row


def _room_type_meta(room_type_id: int, school_id: int) -> dict | None:
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT rt.id, rt.capacity, rt.dorm_id, d.gender AS dorm_gender "
        "FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id "
        "WHERE rt.id=? AND d.school_id=? AND rt.is_enabled=1",
        (room_type_id, school_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _ensure_life_room_hall_votes_table(conn: sqlite3.Connection):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS life_room_hall_votes ("
        "life_room_uid TEXT NOT NULL, "
        "user_uid TEXT NOT NULL, "
        "room_type_id INTEGER NOT NULL, "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, "
        "PRIMARY KEY(life_room_uid, user_uid)"
        ")"
    )


def _school_colleges(conn: sqlite3.Connection, school_id: int) -> list[dict]:
    colleges = conn.execute(
        "SELECT id, name FROM colleges WHERE school_id=? ORDER BY id ASC",
        (school_id,),
    ).fetchall()
    result: list[dict] = []
    for c in colleges:
        departments = conn.execute(
            "SELECT id, name FROM departments WHERE college_id=? ORDER BY id ASC",
            (c["id"],),
        ).fetchall()
        result.append({
            "id": c["id"],
            "name": c["name"],
            "departments": [dict(d) for d in departments],
        })
    return result


def _find_or_create_life_room(
    conn: sqlite3.Connection,
    school_id: int,
    host_uid: str,
    member_uids: list[str],
    target_capacity: int = 2,
) -> str:
    member_key = ",".join(sorted(set(member_uids)))
    existing = conn.execute(
        "SELECT lr.uid FROM life_rooms lr "
        "JOIN life_room_members lm ON lm.life_room_uid=lr.uid "
        "WHERE lr.status='active' AND lm.user_uid IN ({}) "
        "GROUP BY lr.uid HAVING COUNT(DISTINCT lm.user_uid)=?".format(",".join(["?"] * len(member_uids))),
        (*member_uids, len(set(member_uids))),
    ).fetchone()
    if existing:
        return existing["uid"]
    now = _now()
    life_room_uid = generate_uid()
    conn.execute(
        "INSERT INTO life_rooms (uid, school_id, host_uid, status, target_capacity, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?)",
        (life_room_uid, school_id, host_uid, target_capacity, now, now),
    )
    for uid in sorted(set(member_uids)):
        conn.execute(
            "INSERT INTO life_room_members (uid, life_room_uid, user_uid, joined_at, is_active) VALUES (?, ?, ?, ?, 1)",
            (generate_uid(), life_room_uid, uid, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO life_room_presence (uid, life_room_uid, user_uid, status, updated_at) VALUES (?, ?, ?, ?, ?)",
            (generate_uid(), life_room_uid, uid, "out", now),
        )
    conn.execute(
        "INSERT INTO life_room_posts (uid, life_room_uid, author_uid, title, body, pinned, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (
            generate_uid(),
            life_room_uid,
            host_uid,
            "생활방 생성",
            f"생활방이 생성되었습니다. 현재 인원 {len(set(member_uids))}/{target_capacity}",
            now,
            now,
        ),
    )
    return life_room_uid


@app.route("/admin", methods=["GET"])
def admin_html():
    return render_template("admin.html")


@app.route("/api/notices", methods=["GET"])
def list_notices():
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(100, int(limit_raw)))
    except Exception:
        return jsonify({"error": "limit must be integer"}), 400
    conn = _app_conn()
    _ensure_notices_tables(conn)
    _seed_default_notices_if_empty(conn)
    school_id = request.args.get("school_id", type=int)
    rows = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at "
        "FROM global_notices "
        "ORDER BY is_pinned DESC, updated_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    school_rows = []
    if school_id:
        school_rows = conn.execute(
            "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at "
            "FROM school_notices WHERE school_id=? "
            "ORDER BY is_pinned DESC, updated_at DESC, id DESC LIMIT ?",
            (school_id, limit),
        ).fetchall()
    conn.close()
    merged = [_notice_to_dict(r) for r in rows]
    merged.extend(_notice_to_dict(r) for r in school_rows)
    merged.sort(key=lambda x: (1 if x["is_pinned"] else 0, x["updated_at"], x["id"]), reverse=True)
    return jsonify({"notices": merged[:limit]})


@app.route("/api/admin/notices", methods=["GET"])
def admin_list_notices():
    conn = _app_conn()
    _ensure_notices_tables(conn)
    _seed_default_notices_if_empty(conn)
    rows = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at "
        "FROM global_notices "
        "ORDER BY is_pinned DESC, updated_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify({"notices": [_notice_to_dict(r) for r in rows]})


@app.route("/api/admin/notices", methods=["POST"])
def admin_create_notice():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    is_pinned = bool(data.get("is_pinned", False))
    is_collapsed = bool(data.get("is_collapsed", False))
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not body:
        return jsonify({"error": "body is required"}), 400
    now = _now()
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute(
        "INSERT INTO global_notices (title, body, is_pinned, is_collapsed, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, body, 1 if is_pinned else 0, 1 if is_collapsed else 0, now, now),
    )
    notice_id = cur.lastrowid
    conn.commit()
    row = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at FROM global_notices WHERE id=?",
        (notice_id,),
    ).fetchone()
    conn.close()
    return jsonify({"notice": _notice_to_dict(row)}), 201


@app.route("/api/admin/notices/<int:notice_id>", methods=["PUT", "PATCH"])
def admin_update_notice(notice_id: int):
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    is_pinned = bool(data.get("is_pinned", False))
    is_collapsed = bool(data.get("is_collapsed", False))
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not body:
        return jsonify({"error": "body is required"}), 400
    now = _now()
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute(
        "UPDATE global_notices SET title=?, body=?, is_pinned=?, is_collapsed=?, updated_at=? WHERE id=?",
        (title, body, 1 if is_pinned else 0, 1 if is_collapsed else 0, now, notice_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "notice not found"}), 404
    row = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at FROM global_notices WHERE id=?",
        (notice_id,),
    ).fetchone()
    conn.close()
    return jsonify({"notice": _notice_to_dict(row)})


@app.route("/api/admin/notices/<int:notice_id>", methods=["DELETE"])
def admin_delete_notice(notice_id: int):
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute("DELETE FROM global_notices WHERE id=?", (notice_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "notice not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/schools/<int:school_id>/notices", methods=["GET"])
def admin_list_school_notices(school_id: int):
    conn = _app_conn()
    _ensure_notices_tables(conn)
    rows = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at FROM school_notices "
        "WHERE school_id=? ORDER BY is_pinned DESC, updated_at DESC, id DESC",
        (school_id,),
    ).fetchall()
    conn.close()
    return jsonify({"notices": [_notice_to_dict(r) for r in rows]})


@app.route("/api/admin/schools/<int:school_id>/notices", methods=["POST"])
def admin_create_school_notice(school_id: int):
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    is_pinned = bool(data.get("is_pinned", False))
    is_collapsed = bool(data.get("is_collapsed", False))
    if not title or not body:
        return jsonify({"error": "title and body are required"}), 400
    now = _now()
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute(
        "INSERT INTO school_notices (school_id, title, body, is_pinned, is_collapsed, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (school_id, title, body, 1 if is_pinned else 0, 1 if is_collapsed else 0, now, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at FROM school_notices WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return jsonify({"notice": _notice_to_dict(row)}), 201


@app.route("/api/admin/school-notices/<int:notice_id>", methods=["PUT", "PATCH"])
def admin_update_school_notice(notice_id: int):
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    is_pinned = bool(data.get("is_pinned", False))
    is_collapsed = bool(data.get("is_collapsed", False))
    if not title or not body:
        return jsonify({"error": "title and body are required"}), 400
    now = _now()
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute(
        "UPDATE school_notices SET title=?, body=?, is_pinned=?, is_collapsed=?, updated_at=? WHERE id=?",
        (title, body, 1 if is_pinned else 0, 1 if is_collapsed else 0, now, notice_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "notice not found"}), 404
    row = conn.execute(
        "SELECT id, title, body, is_pinned, is_collapsed, created_at, updated_at FROM school_notices WHERE id=?",
        (notice_id,),
    ).fetchone()
    conn.close()
    return jsonify({"notice": _notice_to_dict(row)})


@app.route("/api/admin/school-notices/<int:notice_id>", methods=["DELETE"])
def admin_delete_school_notice(notice_id: int):
    conn = _app_conn()
    _ensure_notices_tables(conn)
    cur = conn.execute("DELETE FROM school_notices WHERE id=?", (notice_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "notice not found"}), 404
    return jsonify({"ok": True})


# ??? Auth ????????????????????????????????????????????????????????????????

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    login_id = data.get("login_id", "").strip()
    student_id = data.get("student_id", "").strip()
    birth_year_raw = data.get("birth_year")
    password = data.get("password", "")
    name = data.get("name", "").strip()
    is_enrolled = data.get("is_enrolled", True)
    school_name = data.get("school_name", "").strip() or data.get("school", "").strip()
    college = data.get("college", "").strip()
    department = data.get("department", "").strip()
    region_name = data.get("region_name", "").strip() or data.get("region", "").strip()
    gender = data.get("gender", "").strip().lower()
    try:
        birth_year = int(birth_year_raw)
    except Exception:
        return jsonify({"error": "birth_year must be integer"}), 400
    if birth_year < 1900 or birth_year > datetime.date.today().year:
        return jsonify({"error": "birth_year out of range"}), 400

    # Frontend compatibility: student_id doubles as login_id
    if not login_id and student_id:
        login_id = student_id

    if not login_id or not password or not name:
        return jsonify({"error": "ID 혹은 비밀번호가 일치하지 않습니다"}), 400
    if gender not in ("male", "female"):
        return jsonify({"error": "남성 혹은 여성이어야 합니다"}), 400
    if bool(is_enrolled):
        if not school_name or not college or not department or not student_id:
            return jsonify({"error": "school_name, college, department, student_id are required for enrolled user"}), 400
        conn = _schools_conn()
        conn.row_factory = sqlite3.Row
        school_row = conn.execute("SELECT id FROM schools WHERE name=?", (school_name,)).fetchone()
        if not school_row:
            conn.close()
            return jsonify({"error": "school not found"}), 404
        college_row = conn.execute(
            "SELECT id FROM colleges WHERE school_id=? AND name=?",
            (school_row["id"], college),
        ).fetchone()
        if not college_row:
            conn.close()
            return jsonify({"error": "college not found for school"}), 400
        dept_row = conn.execute(
            "SELECT id FROM departments WHERE college_id=? AND name=?",
            (college_row["id"], department),
        ).fetchone()
        conn.close()
        if not dept_row:
            return jsonify({"error": "department not found for college"}), 400

    if db.get_user_by_login_id(login_id):
        return jsonify({"error": "이미 사용 중인 ID입니다"}), 409

    user = User(
        login_id=login_id,
        student_id=student_id,
        birth_year=birth_year,
        password_hash=hash_password(password),
        name=name,
        is_enrolled=1 if is_enrolled else 0,
        school_name=school_name,
        college=college,
        department=department,
        region_name=region_name,
        gender=gender,
    )
    db.save_user(user)
    token = create_token(user.uid, user.login_id, user.name, user.student_id)
    return jsonify({
        "token": token,
        "user": {
            "uid": user.uid,
            "login_id": user.login_id,
            "student_id": user.student_id,
            "birth_year": user.birth_year,
            "name": user.name,
            "school_name": user.school_name,
            "college": user.college,
            "department": user.department,
            "region_name": user.region_name,
            "is_enrolled": user.is_enrolled,
            "gender": user.gender,
        },
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    login_id = data.get("login_id", "").strip()
    password = data.get("password", "")

    user = db.get_user_by_login_id(login_id)
    if not user:
        return jsonify({"error": "ID 혹은 비밀번호가 일치하지 않습니다"}), 401

    # Backward compatibility:
    # - old clients sent raw password
    # - new clients send sha256(password)
    ok = verify_password(password, user.password_hash)
    if not ok:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        ok = verify_password(hashed_password, user.password_hash)
    if not ok:
        return jsonify({"error": "ID 혹은 비밀번호가 일치하지 않습니다"}), 401

    token = create_token(user.uid, user.login_id, user.name, user.student_id)
    return jsonify({
        "token": token,
        "user": {
            "uid": user.uid,
            "login_id": user.login_id,
            "student_id": user.student_id,
            "birth_year": user.birth_year,
            "name": user.name,
            "school_name": user.school_name,
            "college": user.college,
            "department": user.department,
            "region_name": user.region_name,
            "is_enrolled": user.is_enrolled,
            "gender": user.gender,
        },
    })


@app.route("/api/me", methods=["GET"])
@login_required
def me():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    life_room = _active_life_room_for_user(conn, payload["user_uid"])
    conn.close()
    return jsonify({
        "uid": user.uid,
        "login_id": user.login_id,
        "student_id": user.student_id,
        "birth_year": user.birth_year,
        "name": user.name,
        "is_enrolled": user.is_enrolled,
        "school_name": user.school_name,
        "college": user.college,
        "department": user.department,
        "region_name": user.region_name,
        "gender": user.gender,
        "has_active_life_room": life_room is not None,
        "life_room_uid": life_room["uid"] if life_room else None,
    })


@app.route("/api/schools", methods=["GET"])
def list_schools():
    include_hidden = request.args.get("include_hidden", "0") == "1"
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    schools = conn.execute("SELECT * FROM schools ORDER BY id ASC").fetchall()
    result = []
    for s in schools:
        is_hidden = bool(int(s["is_hidden"])) if "is_hidden" in s.keys() else False
        if is_hidden and not include_hidden:
            continue
        dorm_rows = conn.execute(
            "SELECT id, name, gender FROM dormitories WHERE school_id=? ORDER BY id ASC",
            (s["id"],),
        ).fetchall()
        dorms = []
        for d in dorm_rows:
            d_dict = dict(d)
            room_types = conn.execute(
                "SELECT id, capacity, is_enabled FROM dorm_room_types WHERE dorm_id=? ORDER BY capacity ASC",
                (d["id"],),
            ).fetchall()
            d_dict["room_types"] = [dict(rt) for rt in room_types]
            dorms.append(d_dict)
        colleges = _school_colleges(conn, s["id"])
        phase = _school_matching_phase(s)
        is_hidden = bool(int(s["is_hidden"])) if "is_hidden" in s.keys() else False
        result.append({
            "id": s["id"],
            "name": s["name"],
            "is_hidden": is_hidden,
            "recruitment_start": s["recruitment_start"],
            "recruitment_end": s["recruitment_end"],
            "pre_matching_start": s["pre_matching_start"] if "pre_matching_start" in s.keys() else None,
            "pre_matching_end": s["pre_matching_end"] if "pre_matching_end" in s.keys() else None,
            "roommate_apply_start": s["roommate_apply_start"] if "roommate_apply_start" in s.keys() else None,
            "roommate_apply_end": s["roommate_apply_end"] if "roommate_apply_end" in s.keys() else None,
            "room_life_start": s["room_life_start"] if "room_life_start" in s.keys() else None,
            "room_life_end": s["room_life_end"] if "room_life_end" in s.keys() else None,
            "matching_enabled": bool(s["matching_enabled"]),
            "matching_phase": phase,
            "dormitories": dorms,
            "colleges": colleges,
        })
    conn.close()
    return jsonify({"schools": result})


@app.route("/api/admin/schools", methods=["POST"])
def admin_create_school():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    recruitment_start = data.get("recruitment_start")
    recruitment_end = data.get("recruitment_end")
    conn = _schools_conn()
    try:
        conn.execute(
            "INSERT INTO schools (name, recruitment_start, recruitment_end, matching_enabled) VALUES (?, ?, ?, 1)",
            (name, recruitment_start, recruitment_end),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "school already exists"}), 409
    conn.close()
    return jsonify({"ok": True}), 201


@app.route("/api/admin/schools/<int:school_id>", methods=["PUT", "PATCH"])
def admin_update_school(school_id: int):
    data = request.get_json(force=True)
    conn = _schools_conn()
    row = conn.execute("SELECT id FROM schools WHERE id=?", (school_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "school not found"}), 404
    sets = []
    vals = []
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            conn.close()
            return jsonify({"error": "name is required"}), 400
        sets.append("name=?")
        vals.append(name)
    if "is_hidden" in data:
        sets.append("is_hidden=?")
        vals.append(1 if data["is_hidden"] else 0)
    if not sets:
        conn.close()
        return jsonify({"error": "no fields to update"}), 400
    vals.append(school_id)
    try:
        conn.execute(f"UPDATE schools SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "school name already exists"}), 409
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/schools/<int:school_id>/dorms", methods=["PUT"])
def admin_update_dorms(school_id: int):
    data = request.get_json(force=True)
    dorms = data.get("dorms", []) or []
    if not isinstance(dorms, list):
        return jsonify({"error": "dorms must be list"}), 400
    normalized: list[tuple[str, str, list[int]]] = []
    for d in dorms:
        name = (d.get("name") or "").strip()
        gender = (d.get("gender") or "").strip().lower()
        if not name:
            return jsonify({"error": "dorm name is required"}), 400
        if gender not in ("male", "female", "coed"):
            return jsonify({"error": "dorm gender must be male, female, or coed"}), 400
        room_types_raw = d.get("room_types", [2, 3, 4])
        capacities: list[int] = []
        if isinstance(room_types_raw, list):
            for rt in room_types_raw:
                if isinstance(rt, dict):
                    cap = int(rt.get("capacity", 0) or 0)
                    enabled = bool(rt.get("is_enabled", True))
                    if enabled and cap >= 2:
                        capacities.append(cap)
                else:
                    cap = int(rt or 0)
                    if cap >= 2:
                        capacities.append(cap)
        capacities = sorted(set(capacities)) or [2]
        normalized.append((name, gender, capacities))

    conn = _schools_conn()
    existing = conn.execute("SELECT id FROM schools WHERE id=?", (school_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "school not found"}), 404
    conn.execute("DELETE FROM dormitories WHERE school_id=?", (school_id,))
    for name, gender, capacities in normalized:
        cur = conn.execute(
            "INSERT INTO dormitories (school_id, name, gender) VALUES (?, ?, ?)",
            (school_id, name, gender),
        )
        dorm_id = cur.lastrowid
        for cap in capacities:
            conn.execute(
                "INSERT INTO dorm_room_types (dorm_id, capacity, is_enabled) VALUES (?, ?, 1)",
                (dorm_id, cap),
            )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/schools/<int:school_id>/schedule", methods=["PATCH"])
def admin_update_schedule(school_id: int):
    data = request.get_json(force=True)
    recruitment_start = data.get("recruitment_start")
    recruitment_end = data.get("recruitment_end")
    pre_matching_start = data.get("pre_matching_start")
    pre_matching_end = data.get("pre_matching_end")
    roommate_apply_start = data.get("roommate_apply_start")
    roommate_apply_end = data.get("roommate_apply_end")
    room_life_start = data.get("room_life_start")
    room_life_end = data.get("room_life_end")
    conn = _schools_conn()
    cur = conn.execute(
        "UPDATE schools SET recruitment_start=?, recruitment_end=?, "
        "pre_matching_start=?, pre_matching_end=?, roommate_apply_start=?, roommate_apply_end=?, "
        "room_life_start=?, room_life_end=? WHERE id=?",
        (
            recruitment_start,
            recruitment_end,
            pre_matching_start,
            pre_matching_end,
            roommate_apply_start,
            roommate_apply_end,
            room_life_start,
            room_life_end,
            school_id,
        ),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "school not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/dorms/<int:dorm_id>/room-types", methods=["PUT"])
def admin_update_dorm_room_types(dorm_id: int):
    data = request.get_json(force=True)
    room_types = data.get("room_types", []) or []
    if not isinstance(room_types, list):
        return jsonify({"error": "room_types must be list"}), 400
    parsed: list[tuple[int, int]] = []
    for item in room_types:
        if isinstance(item, dict):
            cap = int(item.get("capacity", 0) or 0)
            enabled = 1 if bool(item.get("is_enabled", True)) else 0
        else:
            cap = int(item or 0)
            enabled = 1
        if cap < 2:
            continue
        parsed.append((cap, enabled))
    parsed = list({(cap, enabled) for cap, enabled in parsed})
    if not parsed:
        return jsonify({"error": "at least one room type is required"}), 400
    conn = _schools_conn()
    exists = conn.execute("SELECT id FROM dormitories WHERE id=?", (dorm_id,)).fetchone()
    if not exists:
        conn.close()
        return jsonify({"error": "dorm not found"}), 404
    conn.execute("DELETE FROM dorm_room_types WHERE dorm_id=?", (dorm_id,))
    for cap, enabled in parsed:
        conn.execute(
            "INSERT INTO dorm_room_types (dorm_id, capacity, is_enabled) VALUES (?, ?, ?)",
            (dorm_id, cap, enabled),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/schools/<int:school_id>/colleges", methods=["PUT"])
def admin_update_colleges(school_id: int):
    data = request.get_json(force=True)
    colleges = data.get("colleges", []) or []
    if not isinstance(colleges, list):
        return jsonify({"error": "colleges must be list"}), 400

    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    existing = conn.execute("SELECT id FROM schools WHERE id=?", (school_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "school not found"}), 404

    conn.execute(
        "DELETE FROM departments WHERE college_id IN (SELECT id FROM colleges WHERE school_id=?)",
        (school_id,),
    )
    conn.execute("DELETE FROM colleges WHERE school_id=?", (school_id,))
    for c in colleges:
        college_name = (c.get("name") or "").strip()
        departments = c.get("departments", []) or []
        if not college_name:
            conn.close()
            return jsonify({"error": "college name is required"}), 400
        if not isinstance(departments, list):
            conn.close()
            return jsonify({"error": "departments must be list"}), 400
        cur = conn.execute(
            "INSERT INTO colleges (school_id, name) VALUES (?, ?)",
            (school_id, college_name),
        )
        college_id = cur.lastrowid
        for d in departments:
            dep_name = (d.get("name") or "").strip() if isinstance(d, dict) else str(d).strip()
            if not dep_name:
                conn.close()
                return jsonify({"error": "department name is required"}), 400
            conn.execute(
                "INSERT INTO departments (college_id, name) VALUES (?, ?)",
                (college_id, dep_name),
            )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/schools/<int:school_id>/matching", methods=["PATCH"])
def admin_toggle_matching(school_id: int):
    data = request.get_json(force=True)
    is_open = bool(data.get("is_open", True))
    conn = _schools_conn()
    cur = conn.execute(
        "UPDATE schools SET matching_enabled=? WHERE id=?",
        (1 if is_open else 0, school_id),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "school not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/matching/options", methods=["GET"])
@login_required
def matching_options():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.gender not in ("male", "female"):
        return jsonify({"error": "user gender is required"}), 400
    school = _get_school_row(user.school_name)
    if not school:
        return jsonify({"error": "school not found"}), 404
    phase = _school_matching_phase(school)
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    dorms = conn.execute(
        "SELECT id, name, gender FROM dormitories WHERE school_id=? ORDER BY id ASC",
        (school["id"],),
    ).fetchall()
    room_types = conn.execute(
        "SELECT rt.id, rt.dorm_id, rt.capacity, rt.is_enabled, d.name AS dorm_name, d.gender AS dorm_gender "
        "FROM dorm_room_types rt JOIN dormitories d ON d.id=rt.dorm_id "
        "WHERE d.school_id=? ORDER BY d.id ASC, rt.capacity ASC",
        (school["id"],),
    ).fetchall()
    conn.close()
    visible = [dict(d) for d in dorms if d["gender"] in ("coed", user.gender)]
    visible_room_types = [
        dict(r)
        for r in room_types
        if r["dorm_gender"] in ("coed", user.gender) and int(r["is_enabled"] or 0) == 1
    ]
    visible_dorm_count = len({r["dorm_id"] for r in visible_room_types})
    max_select = _selection_limit(visible_dorm_count, phase)
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    selected = []
    fixed_room_type_id = 0
    change_limit = 1
    change_used = 0
    needs_hall_confirmation = False
    has_interest_rooms = False
    if profile:
        fixed_ir = int(profile.fixed_interest_room_type_id or 0)
        ir_list = list(profile.interest_room_type_ids or [])
        if fixed_ir or ir_list:
            has_interest_rooms = True
        if phase == "main":
            fixed_room_type_id = int(profile.fixed_room_type_id or 0)
            selected = [fixed_room_type_id] if fixed_room_type_id else []
            change_used = int(profile.apply_change_count or 0)
            if not fixed_room_type_id:
                needs_hall_confirmation = True
        else:
            selected = list(profile.preferred_room_type_ids or [])
            change_used = int(profile.pre_change_count or 0)
    if not has_interest_rooms:
        needs_hall_confirmation = True
    return jsonify({
        "school_name": school["name"],
        "phase": phase,
        "user_gender": user.gender,
        "visible_dorms": visible,
        "visible_room_types": visible_room_types,
        "max_selectable": max_select,
        "selected_halls": selected,
        "selected_room_types": selected,
        "fixed_room_type_id": fixed_room_type_id,
        "change_limit": change_limit,
        "change_used": change_used,
        "change_remaining": max(0, change_limit - change_used),
        "needs_hall_confirmation": needs_hall_confirmation,
        "has_interest_rooms": has_interest_rooms,
    })


@app.route("/api/matching/preferences", methods=["POST"])
@login_required
def save_matching_preferences():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    school = _get_school_row(user.school_name)
    if not school:
        return jsonify({"error": "school not found"}), 404
    phase = _school_matching_phase(school)
    if phase == "closed":
        return jsonify({"error": "matching period is closed"}), 400
    if phase == "life":
        return jsonify({"error": "life phase does not accept matching preference changes"}), 400

    existing = db.get_profile_by_user_uid(payload["user_uid"])
    if not existing:
        return jsonify({"error": "profile not found"}), 404

    conn_chk = _app_conn()
    conn_chk.row_factory = sqlite3.Row
    if _active_life_room_for_user(conn_chk, payload["user_uid"]):
        conn_chk.close()
        return jsonify({"error": "cannot change preferences while life room is active"}), 400
    conn_chk.close()

    if existing.hall_confirmed_at:
        return jsonify({"error": "hall is confirmed and cannot be changed"}), 400

    data = request.get_json(force=True)
    room_type_ids = data.get("selected_room_type_ids")
    if room_type_ids is None:
        room_type_ids = data.get("selected_halls", []) or []
    if not isinstance(room_type_ids, list):
        return jsonify({"error": "selected_room_type_ids must be list"}), 400
    room_type_ids = [int(x) for x in room_type_ids if int(x or 0) > 0]

    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    room_types = conn.execute(
        "SELECT rt.id, rt.dorm_id, d.gender FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id WHERE d.school_id=? AND rt.is_enabled=1",
        (school["id"],),
    ).fetchall()
    conn.close()
    allowed_ids = {int(r["id"]) for r in room_types if r["gender"] in ("coed", user.gender)}
    if any(rt_id not in allowed_ids for rt_id in room_type_ids):
        return jsonify({"error": "contains invalid or gender-mismatched room type"}), 400
    selected_dorm_count = _count_distinct_dorms(room_type_ids, int(school["id"]))
    allowed_dorm_count = len({int(r["dorm_id"]) for r in room_types if r["gender"] in ("coed", user.gender)})
    max_sel = _selection_limit(allowed_dorm_count, phase)
    if phase != "main" and selected_dorm_count > max_sel:
        return jsonify({"error": f"관 기준으로 최대 {max_sel}개까지 선택 가능합니다 (선택한 관: {selected_dorm_count}개)"}), 400
    if len(room_type_ids) > max_sel:
        return jsonify({"error": f"at most {max_sel} room types can be selected"}), 400

    existing.matching_phase = phase
    if phase == "main":
        fixed_id = room_type_ids[0] if room_type_ids else 0
        prev_fixed = int(existing.fixed_room_type_id or 0)
        prev_interest_fixed = int(existing.fixed_interest_room_type_id or 0)
        is_initial = prev_fixed == 0 and prev_interest_fixed == 0
        changed = prev_fixed != fixed_id
        if (not is_initial) and changed:
            if int(existing.apply_change_count or 0) >= 1:
                return jsonify({"error": "no remaining changes", "needs_confirm": False}), 400
            confirm_change = str(data.get("confirm_change", "")).lower() == "true"
            if not confirm_change:
                return jsonify({"error": "change requires confirmation", "needs_confirm": True, "change_remaining": 1}), 409
            existing.apply_change_count = int(existing.apply_change_count or 0) + 1
            existing.apply_last_changed_at = _now()
        existing.fixed_room_type_id = fixed_id
        existing.preferred_room_type_ids = []
        existing.accepted_hall = ""
        existing.hope_halls = []
        existing.fixed_interest_room_type_id = fixed_id
        existing.interest_room_type_ids = []
    else:
        new_pref = list(sorted(set(room_type_ids)))
        prev_pref = list(sorted(set(existing.preferred_room_type_ids or [])))
        prev_interest = list(sorted(set(existing.interest_room_type_ids or [])))
        is_initial = not prev_pref and not prev_interest
        changed = prev_pref != new_pref
        if (not is_initial) and changed:
            if int(existing.pre_change_count or 0) >= 1:
                return jsonify({"error": "no remaining changes", "needs_confirm": False}), 400
            confirm_change = str(data.get("confirm_change", "")).lower() == "true"
            if not confirm_change:
                return jsonify({"error": "change requires confirmation", "needs_confirm": True, "change_remaining": 1}), 409
            existing.pre_change_count = int(existing.pre_change_count or 0) + 1
            existing.pre_last_changed_at = _now()
        existing.preferred_room_type_ids = new_pref
        existing.fixed_room_type_id = 0
        existing.interest_room_type_ids = list(new_pref)
        existing.fixed_interest_room_type_id = 0
    existing.dormitory_hall = existing.dormitory_hall or ""
    db.save_profile(existing)
    return jsonify({
        "ok": True,
        "phase": phase,
        "selected_room_type_ids": existing.preferred_room_type_ids if phase != "main" else [existing.fixed_room_type_id] if existing.fixed_room_type_id else [],
    })


@app.route("/api/profile/interest-rooms", methods=["GET"])
@login_required
def get_interest_rooms():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not profile:
        return jsonify({"error": "profile is required"}), 404
    if user.gender not in ("male", "female"):
        return jsonify({"error": "user gender is required"}), 400
    school = _get_school_row(user.school_name)
    if not school:
        return jsonify({"error": "school not found"}), 404
    phase = _school_matching_phase(school)
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    room_types = conn.execute(
        "SELECT rt.id, rt.dorm_id, rt.capacity, rt.is_enabled, d.name AS dorm_name, d.gender AS dorm_gender "
        "FROM dorm_room_types rt JOIN dormitories d ON d.id=rt.dorm_id "
        "WHERE d.school_id=? ORDER BY d.id ASC, rt.capacity ASC",
        (school["id"],),
    ).fetchall()
    conn.close()
    visible_room_types = [
        dict(r)
        for r in room_types
        if r["dorm_gender"] in ("coed", user.gender) and int(r["is_enabled"] or 0) == 1
    ]
    visible_dorm_count = len({r["dorm_id"] for r in visible_room_types})
    change_limit = 1
    if phase == "main":
        selected = [int(profile.fixed_interest_room_type_id or 0)] if int(profile.fixed_interest_room_type_id or 0) else []
        needs_hall_confirmation = not int(profile.fixed_interest_room_type_id or 0)
        change_used = int(profile.apply_change_count or 0)
    else:
        selected = list(profile.interest_room_type_ids or [])
        needs_hall_confirmation = False
        change_used = int(profile.pre_change_count or 0)
    change_remaining = max(0, change_limit - change_used)
    return jsonify({
        "visible_room_types": visible_room_types,
        "selected_interest_room_type_ids": selected,
        "phase": phase,
        "needs_hall_confirmation": needs_hall_confirmation,
        "change_limit": change_limit,
        "change_used": change_used,
        "change_remaining": change_remaining,
        "max_selectable": _selection_limit(visible_dorm_count, phase),
    })


@app.route("/api/profile/interest-rooms", methods=["PUT"])
@login_required
def save_interest_rooms():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not profile:
        return jsonify({"error": "profile is required"}), 404
    if not _has_valid_survey_profile(profile):
        return jsonify({"error": "설문 프로필이 필요합니다. 설문조사를 먼저 완료해주세요."}), 400
    if user.gender not in ("male", "female"):
        return jsonify({"error": "user gender is required"}), 400
    school = _get_school_row(user.school_name)
    if not school:
        return jsonify({"error": "school not found"}), 404
    phase = _school_matching_phase(school)
    has_existing = (phase == "main" and int(profile.fixed_interest_room_type_id or 0)) or \
                  (phase != "main" and bool(profile.interest_room_type_ids))
    if (phase == "closed" or phase == "life") and has_existing:
        return jsonify({"error": "cannot update interest rooms in this phase"}), 400

    conn_chk = _app_conn()
    conn_chk.row_factory = sqlite3.Row
    if _active_life_room_for_user(conn_chk, payload["user_uid"]):
        conn_chk.close()
        return jsonify({"error": "cannot change interest rooms while life room is active"}), 400
    conn_chk.close()

    if profile.hall_confirmed_at:
        return jsonify({"error": "hall is confirmed and cannot be changed"}), 400

    data = request.get_json(force=True)
    interest_room_type_ids = data.get("interest_room_type_ids")
    if not isinstance(interest_room_type_ids, list):
        return jsonify({"error": "interest_room_type_ids must be list"}), 400
    interest_room_type_ids = [int(x) for x in interest_room_type_ids if int(x or 0) > 0]
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    room_types = conn.execute(
        "SELECT rt.id, rt.dorm_id, d.gender FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id WHERE d.school_id=? AND rt.is_enabled=1",
        (school["id"],),
    ).fetchall()
    conn.close()
    allowed_ids = {int(r["id"]) for r in room_types if r["gender"] in ("coed", user.gender)}
    if any(rt_id not in allowed_ids for rt_id in interest_room_type_ids):
        return jsonify({"error": "contains invalid or gender-mismatched interest room type"}), 400
    selected_dorm_count = _count_distinct_dorms(interest_room_type_ids, int(school["id"]))
    allowed_dorm_count = len({int(r["dorm_id"]) for r in room_types if r["gender"] in ("coed", user.gender)})
    max_sel = _selection_limit(allowed_dorm_count, phase)
    if phase != "main" and selected_dorm_count > max_sel:
        return jsonify({"error": f"관 기준으로 최대 {max_sel}개까지 선택 가능합니다 (선택한 관: {selected_dorm_count}개)"}), 400
    if len(interest_room_type_ids) > max_sel:
        return jsonify({"error": f"at most {max_sel} interest room types can be selected"}), 400

    if phase == "main":
        fixed_interest = interest_room_type_ids[0] if interest_room_type_ids else 0
        prev_fixed = int(profile.fixed_interest_room_type_id or 0)
        prev_pref_fixed = int(profile.fixed_room_type_id or 0)
        is_initial = prev_fixed == 0 and prev_pref_fixed == 0
        changed = prev_fixed != fixed_interest
        if (not is_initial) and changed:
            if int(profile.apply_change_count or 0) >= 1:
                return jsonify({"error": "no remaining changes", "needs_confirm": False}), 400
            confirm_change = str(data.get("confirm_change", "")).lower() == "true"
            if not confirm_change:
                return jsonify({"error": "change requires confirmation", "needs_confirm": True, "change_remaining": 1}), 409
            profile.apply_change_count = int(profile.apply_change_count or 0) + 1
            profile.apply_last_changed_at = _now()
        profile.fixed_interest_room_type_id = fixed_interest
        profile.interest_room_type_ids = []
        profile.fixed_room_type_id = fixed_interest
        profile.preferred_room_type_ids = []
    else:
        new_interest = list(sorted(set(interest_room_type_ids)))
        prev_interest = list(sorted(set(profile.interest_room_type_ids or [])))
        prev_pref = list(sorted(set(profile.preferred_room_type_ids or [])))
        is_initial = not prev_interest and not prev_pref
        changed = prev_interest != new_interest
        if (not is_initial) and changed:
            if int(profile.pre_change_count or 0) >= 1:
                return jsonify({"error": "no remaining changes", "needs_confirm": False}), 400
            confirm_change = str(data.get("confirm_change", "")).lower() == "true"
            if not confirm_change:
                return jsonify({"error": "change requires confirmation", "needs_confirm": True, "change_remaining": 1}), 409
            profile.pre_change_count = int(profile.pre_change_count or 0) + 1
            profile.pre_last_changed_at = _now()
        profile.interest_room_type_ids = new_interest
        profile.fixed_interest_room_type_id = 0
        profile.preferred_room_type_ids = list(new_interest)
        profile.fixed_room_type_id = 0
    db.save_profile(profile)
    return jsonify({
        "ok": True,
        "interest_room_type_ids": profile.interest_room_type_ids if phase != "main" else [profile.fixed_interest_room_type_id] if profile.fixed_interest_room_type_id else [],
    })


# ??? Profile ?????????????????????????????????????????????????????????????

@app.route("/api/profile", methods=["GET"])
@login_required
def get_profile():
    payload = request.current_user
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not profile:
        return jsonify({"exists": False, "profile": None}), 200
    return jsonify(profile_to_dict(profile))


@app.route("/api/profile/public/<user_uid>", methods=["GET"])
@login_required
def get_public_profile(user_uid):
    payload = request.current_user
    profile = db.get_profile_by_user_uid(user_uid)
    if not profile:
        return jsonify({"error": "profile not found"}), 404
    # Allow only users with an existing relationship in thread/session.
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT 1 FROM chat_threads "
        "WHERE ((user_a=? AND user_b=?) OR (user_a=? AND user_b=?)) "
        "LIMIT 1",
        (payload["user_uid"], user_uid, user_uid, payload["user_uid"]),
    ).fetchone()
    conn.close()
    if not row and payload["user_uid"] != user_uid:
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"profile": profile_to_dict(profile)})


@app.route("/api/profile", methods=["POST"])
@login_required
def post_profile():
    payload = request.current_user
    data = request.get_json(force=True)
    user = db.get_user_by_uid(payload["user_uid"])
    if not user:
        return jsonify({"error": "User not found"}), 404

    existing = db.get_profile_by_user_uid(payload["user_uid"])
    uid = existing.uid if existing else None

    matching_phase = data.get("matching_phase", "preliminary")
    hope_halls = data.get("hope_halls", []) or []
    accepted_hall = data.get("accepted_hall", "") or ""
    room_capacity = int(data.get("room_capacity", 2) or 2)
    dormitory_hall = data.get("dormitory_hall", "") or ""
    conn = _schools_conn()
    conn.row_factory = sqlite3.Row
    school_row = conn.execute("SELECT id FROM schools WHERE name=?", (user.school_name,)).fetchone()
    if school_row:
        dorm_rows = conn.execute("SELECT name FROM dormitories WHERE school_id=?", (school_row["id"],)).fetchall()
        allowed_halls = {r["name"] for r in dorm_rows}
    else:
        allowed_halls = set()
    conn.close()
    if matching_phase not in ("preliminary", "main"):
        return jsonify({"error": "matching_phase must be preliminary or main"}), 400
    if room_capacity not in (2, 3, 4):
        return jsonify({"error": "room_capacity must be 2, 3, or 4"}), 400
    if matching_phase == "preliminary":
        if len(hope_halls) > 2:
            return jsonify({"error": "preliminary phase allows up to 2 hope_halls"}), 400
        if any(h not in allowed_halls for h in hope_halls):
            return jsonify({"error": "invalid dorm hall in hope_halls"}), 400
        accepted_hall = ""
    else:
        if accepted_hall and accepted_hall not in allowed_halls:
            return jsonify({"error": "invalid accepted_hall"}), 400
        hope_halls = []
        dormitory_hall = accepted_hall or dormitory_hall

    # ?대쫫/?숇쾲? User?먯꽌 ?먮룞 ?곕룞
    profile = RoommateProfile(
        uid=uid or generate_uid(),
        user_uid=payload["user_uid"],
        name=user.name,
        student_id=user.student_id,
        birth_year=user.birth_year or 2005,
        college=user.college or "",
        department=user.department or "",
        dorm_duration=data.get("dorm_duration", 1),
        home_visit_cycle=data.get("home_visit_cycle", 2),
        perfume=data.get("perfume", 0),
        indoor_scent_sensitivity=data.get("indoor_scent_sensitivity", 3),
        alcohol_tolerance=data.get("alcohol_tolerance", 2.5),
        alcohol_frequency=data.get("alcohol_frequency", 2),
        drunk_habit=data.get("drunk_habit", 0),
        gaming_hours_per_week=data.get("gaming_hours_per_week", 10),
        speaker_use=data.get("speaker_use", 0),
        exercise=data.get("exercise", 0),
        bedtime=data.get("bedtime", 23),
        wake_time=data.get("wake_time", 8),
        sleep_habit=data.get("sleep_habit", 0),
        sleep_sensitivity=data.get("sleep_sensitivity", 3),
        alarm_strength=data.get("alarm_strength", 3),
        sleep_light=data.get("sleep_light", 0),
        snoring=data.get("snoring", 0),
        shower_duration=data.get("shower_duration", 15),
        shower_time=data.get("shower_time", 22),
        shower_cycle=data.get("shower_cycle", 2),
        cleaning_cycle=data.get("cleaning_cycle", 7),
        ventilation=data.get("ventilation", 1.0),
        hairdryer_in_bathroom=data.get("hairdryer_in_bathroom", 1),
        toilet_paper_share=data.get("toilet_paper_share", 1),
        indoor_eating=data.get("indoor_eating", 0),
        smoking=data.get("smoking", 0),
        temperature_pref=data.get("temperature_pref", 3),
        indoor_call=data.get("indoor_call", 0),
        bug_handling=data.get("bug_handling", 3),
        laundry_cycle=data.get("laundry_cycle", 7),
        drying_rack=data.get("drying_rack", 1),
        fridge_use=data.get("fridge_use", 1),
        study_in_room=data.get("study_in_room", 0),
        noise_sensitivity=data.get("noise_sensitivity", 3),
        desired_intimacy=data.get("desired_intimacy", 3),
        meal_together=data.get("meal_together", 2),
        exercise_together=data.get("exercise_together", 1),
        friend_invite=data.get("friend_invite", 1),
        dormitory_hall=dormitory_hall,
        matching_phase=matching_phase,
        hope_halls=hope_halls,
        accepted_hall=accepted_hall,
        room_capacity=room_capacity,
        preferred_room_type_ids=data.get("preferred_room_type_ids") if data.get("preferred_room_type_ids") is not None else (existing.preferred_room_type_ids if existing and existing.preferred_room_type_ids else []),
        fixed_room_type_id=int(data.get("fixed_room_type_id", existing.fixed_room_type_id if existing else 0) or 0),
        interest_room_type_ids=data.get("interest_room_type_ids") if data.get("interest_room_type_ids") is not None else (existing.interest_room_type_ids if existing and existing.interest_room_type_ids else []),
        fixed_interest_room_type_id=int(data.get("fixed_interest_room_type_id", existing.fixed_interest_room_type_id if existing else 0) or 0),
        non_negotiable_items=data.get("non_negotiable_items", []),
        non_negotiable_weights=data.get("non_negotiable_weights", []),
    )
    db.save_profile(profile)
    return jsonify(profile_to_dict(profile))


@app.route("/api/persona", methods=["GET"])
@login_required
def get_persona():
    payload = request.current_user
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not profile:
        return jsonify({"error": "?꾨줈?꾩씠 ?놁뒿?덈떎."}), 404
    persona = normalize_persona(profile.persona or classify_persona(profile))
    return jsonify({"persona": persona})


# ??? Matching ????????????????????????????????????????????????????????????

@app.route("/api/match/top", methods=["GET"])
@login_required
def match_top():
    payload = request.current_user
    top_n = request.args.get("top_n", 5, type=int)
    exclude_blocked = request.args.get("exclude_blocked", "true").lower() == "true"

    target = db.get_profile_by_user_uid(payload["user_uid"])
    if not target:
        return jsonify({"error": "?ㅻЦ議곗궗瑜?癒쇱? ?묒꽦?댁＜?몄슂."}), 404

    pool = db.fetch_profiles()
    results = rank_matches(target, pool, top_n=top_n, exclude_blocked=exclude_blocked)
    return jsonify({"matches": [r.to_dict() for r in results]})


@app.route("/api/match/pairs", methods=["GET"])
@login_required
def match_pairs():
    exclude_blocked = request.args.get("exclude_blocked", "true").lower() == "true"
    profiles = db.fetch_profiles()
    if len(profiles) < 2:
        return jsonify({"error": "留ㅼ묶???꾨줈?꾩씠 遺議깊빀?덈떎."}), 400
    results = best_pairings(profiles, exclude_blocked=exclude_blocked)
    return jsonify({"pairs": [r.to_dict() for r in results]})


# ??? Match Requests ??????????????????????????????????????????????????????

MAX_ACTIVE_MATCHES = 6


def _count_active_matches(user_uid: str) -> int:
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    # ?닿? 蹂대궦 pending + accepted
    sent = conn.execute(
        "SELECT COUNT(*) FROM match_requests WHERE from_user=? AND status IN ('pending','accepted')",
        (user_uid,),
    ).fetchone()[0]
    # ?닿? 諛쏆? accepted
    received = conn.execute(
        "SELECT COUNT(*) FROM match_requests WHERE to_user=? AND status='accepted'",
        (user_uid,),
    ).fetchone()[0]
    conn.close()
    return sent + received


@app.route("/api/match/request", methods=["POST"])
@login_required
def create_match_request():
    payload = request.current_user
    data = request.get_json(force=True)
    to_user = data.get("to_user", "")
    if not to_user:
        return jsonify({"error": "????ъ슜?먭? ?꾩슂?⑸땲??"}), 400

    # 理쒕? 留ㅼ묶 ???쒗븳
    if _count_active_matches(payload["user_uid"]) >= MAX_ACTIVE_MATCHES:
        return jsonify({"error": "理쒕? 6媛쒖쓽 留ㅼ묶留?媛?ν빀?덈떎."}), 403

    conn = _app_conn()
    # 以묐났 寃??
    existing = conn.execute(
        "SELECT * FROM match_requests WHERE from_user=? AND to_user=?",
        (payload["user_uid"], to_user),
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "?대? ?붿껌???곹깭?낅땲??"}), 409

    uid = generate_uid()
    now = _now()
    conn.execute(
        "INSERT INTO match_requests (uid, from_user, to_user, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, payload["user_uid"], to_user, "pending", now, now),
    )
    conn.commit()
    conn.close()

    # ?ㅼ떆媛??몄떆 (SSE)
    broadcast_message(to_user, "match_request", {
        "from_user": payload["user_uid"],
        "from_name": payload.get("name", ""),
        "status": "pending",
    })

    return jsonify({"uid": uid, "status": "pending"}), 201


@app.route("/api/match/request/<uid>", methods=["PATCH"])
@login_required
def update_match_request(uid):
    payload = request.current_user
    data = request.get_json(force=True)
    status = data.get("status", "")
    if status not in ("accepted", "rejected"):
        return jsonify({"error": "status??accepted ?먮뒗 rejected留?媛?ν빀?덈떎."}), 400

    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM match_requests WHERE uid=?", (uid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "?붿껌??李얠쓣 ???놁뒿?덈떎."}), 404

    req = dict(row)
    if req["to_user"] != payload["user_uid"]:
        conn.close()
        return jsonify({"error": "沅뚰븳???놁뒿?덈떎."}), 403

    now = _now()
    conn.execute(
        "UPDATE match_requests SET status=?, updated_at=? WHERE uid=?",
        (status, now, uid),
    )

    if status == "accepted":
        # match_history 異붽?
        muid = generate_uid()
        conn.execute(
            "INSERT INTO match_history (uid, user_a, user_b, status, matched_at) VALUES (?, ?, ?, ?, ?)",
            (muid, req["from_user"], req["to_user"], "active", now),
        )
    conn.commit()
    conn.close()

    # ?뚮┝
    broadcast_message(req["from_user"], "match_response", {
        "request_uid": uid,
        "status": status,
    })

    return jsonify({"uid": uid, "status": status})


@app.route("/api/match/requests", methods=["GET"])
@login_required
def list_match_requests():
    payload = request.current_user
    direction = request.args.get("direction", "in")
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    if direction == "in":
        rows = conn.execute(
            "SELECT * FROM match_requests WHERE to_user=? ORDER BY created_at DESC",
            (payload["user_uid"],),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM match_requests WHERE from_user=? ORDER BY created_at DESC",
            (payload["user_uid"],),
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ??? Chat (SSE) ??????????????????????????????????????????????????????????

CHAT_RETENTION_DAYS = 7


def _cleanup_old_messages():
    """3???댁긽 ??梨꾪똿 硫붿떆吏瑜???젣?쒕떎."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=CHAT_RETENTION_DAYS)).isoformat() + "Z"
    conn = _app_conn()
    conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def _delete_message(uid: str):
    """?뱀젙 硫붿떆吏瑜?利됱떆 ??젣?쒕떎 (legacy - ?ъ슜 ????."""
    conn = _app_conn()
    conn.execute("DELETE FROM chat_messages WHERE uid=?", (uid,))
    conn.commit()
    conn.close()


def _expire_old_messages(days: int = CHAT_RETENTION_DAYS):
    """3???댁긽 ??硫붿떆吏瑜???젣?쒕떎."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat() + "Z"
    conn = _app_conn()
    conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()


@app.route("/api/chat/stream", methods=["GET"])
@login_required
def chat_stream():
    payload = request.current_user
    user_uid = payload["user_uid"]

    def event_stream():
        q: queue.Queue = queue.Queue(maxsize=100)
        _add_sse_queue(user_uid, q)
        try:
            # 珥덇린 ?곌껐 heartbeat
            yield f"event: connected\ndata: {jsonify({'user_uid': user_uid}).data.decode()}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    event = msg["event"]
                    data = msg["data"]
                    # 利됱떆 ??젣 ?쒓굅 - 硫붿떆吏??read ACK ?먮뒗 3??TTL濡???젣
                    # if event == "chat_message" and data.get("uid"):
                    #     _delete_message(data["uid"])
                    data_str = __import__("json").dumps(data, ensure_ascii=False)
                    yield f"event: {event}\ndata: {data_str}\n\n"
                except queue.Empty:
                    yield ":keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            _remove_sse_queue(user_uid, q)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat/send", methods=["POST"])
@login_required
def chat_send():
    payload = request.current_user
    data = request.get_json(force=True)
    receiver = data.get("receiver", "")
    content = data.get("content", "").strip()
    msg_type = data.get("type", "text")
    if not receiver or not content:
        return jsonify({"error": "receiver? content???꾩닔?낅땲??"}), 400

    # 二쇨린???ㅻ옒??硫붿떆吏 ?뺣━
    _cleanup_old_messages()

    uid = generate_uid()
    now = _now()
    conn = _app_conn()
    conn.execute(
        "INSERT INTO chat_messages (uid, sender, receiver, content, type, read, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, payload["user_uid"], receiver, content, msg_type, 0, now),
    )
    conn.commit()
    conn.close()

    # ?ㅼ떆媛??꾨떖
    broadcast_message(receiver, "chat_message", {
        "uid": uid,
        "sender": payload["user_uid"],
        "sender_name": payload.get("name", ""),
        "content": content,
        "type": msg_type,
        "created_at": now,
    })

    return jsonify({"uid": uid, "created_at": now}), 201


@app.route("/api/chat/messages", methods=["GET"])
@login_required
def chat_messages():
    payload = request.current_user
    other = request.args.get("with", "")
    limit = request.args.get("limit", 50, type=int)
    if not other:
        return jsonify({"error": "with ?뚮씪誘명꽣媛 ?꾩슂?⑸땲??"}), 400

    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?) "
        "ORDER BY created_at DESC LIMIT ?",
        (payload["user_uid"], other, other, payload["user_uid"], limit),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in reversed(rows)])


@app.route("/api/chat/read", methods=["POST"])
@login_required
def chat_read():
    payload = request.current_user
    data = request.get_json(force=True)
    other = data.get("with", "")
    if not other:
        return jsonify({"error": "with ?뚮씪誘명꽣媛 ?꾩슂?⑸땲??"}), 400

    conn = _app_conn()
    conn.execute(
        "UPDATE chat_messages SET read=1 WHERE sender=? AND receiver=? AND read=0",
        (other, payload["user_uid"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# --- Pool / Session / Thread Matching Protocol ---

def _profile_hall_for_phase(profile: RoommateProfile) -> str:
    if profile.matching_phase == "main":
        return profile.accepted_hall or profile.dormitory_hall
    return profile.dormitory_hall


def _is_profile_compatible(target: RoommateProfile, other: RoommateProfile) -> bool:
    if target.user_uid == other.user_uid:
        return False
    if target.matching_phase != other.matching_phase:
        return False
    if target.matching_phase == "preliminary":
        if target.hope_halls and other.hope_halls:
            return bool(set(target.hope_halls) & set(other.hope_halls))
        return True
    return _profile_hall_for_phase(target) == _profile_hall_for_phase(other)


def _select_quota(results):
    quota = [(90.0, 100.1, 1), (80.0, 90.0, 2), (60.0, 80.0, 2)]
    picked = []
    used = set()

    def pick_band(lo: float, hi: float, count: int):
        band = [r for r in results if lo <= r.score < hi and r.profile_b.user_uid not in used]
        if not band or count <= 0:
            return []
        if len(band) <= count:
            return band
        return random.sample(band, count)

    for lo, hi, count in quota:
        chosen = pick_band(lo, hi, count)
        picked.extend(chosen)
        used.update(r.profile_b.user_uid for r in chosen)

    # Fallback cascade: 90 deficit -> 80, then 70, then 60.
    for lo, hi in [(80.0, 90.0), (70.0, 80.0), (60.0, 70.0)]:
        if len(picked) >= 5:
            break
        chosen = pick_band(lo, hi, 5 - len(picked))
        picked.extend(chosen)
        used.update(r.profile_b.user_uid for r in chosen)

    return picked[:5]


def _insert_system_message(conn: sqlite3.Connection, thread_uid: str, session_uid: str, sender: str, receiver: str, content: str):
    now = _now()
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=CHAT_RETENTION_DAYS)).isoformat() + "Z"
    conn.execute(
        "INSERT INTO chat_messages (uid, session_uid, thread_uid, sender, receiver, content, type, read, expires_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (generate_uid(), session_uid, thread_uid, sender, receiver, content, "system", 0, expires, now),
    )


def _broadcast_thread_state(conn: sqlite3.Connection, thread_uid: str, closed_reason: str, extra: dict | None = None):
    row = conn.execute("SELECT * FROM chat_threads WHERE uid=?", (thread_uid,)).fetchone()
    if not row:
        return
    payload = {
        "event_type": "thread_state",
        "thread_id": thread_uid,
        "session_id": row["session_uid"],
        "status": row["status"],
        "closed_reason": closed_reason,
    }
    if extra:
        payload.update(extra)
    broadcast_message(row["user_a"], "thread_state", payload)
    broadcast_message(row["user_b"], "thread_state", payload)


def _session_side_for_user(session_row: sqlite3.Row, user_uid: str) -> str | None:
    if user_uid == session_row["user_uid"]:
        return "user"
    room_members = [u.strip() for u in (session_row["room_member_uids"] or "").split(",") if u and u.strip()]
    if user_uid == session_row["candidate_uid"] or user_uid in room_members:
        return "candidate"
    return None


def _normalized_pair(user_a: str, user_b: str) -> tuple[str, str]:
    a = (user_a or "").strip()
    b = (user_b or "").strip()
    return (a, b) if a <= b else (b, a)


def _is_pair_blocked(conn: sqlite3.Connection, user_a: str, user_b: str) -> bool:
    a, b = _normalized_pair(user_a, user_b)
    row = conn.execute(
        "SELECT 1 FROM match_pair_blocks WHERE user_a=? AND user_b=?",
        (a, b),
    ).fetchone()
    return row is not None


def _block_pair(
    conn: sqlite3.Connection,
    user_a: str,
    user_b: str,
    blocked_by: str,
    reason: str,
    session_uid: str,
    created_at: str,
):
    a, b = _normalized_pair(user_a, user_b)
    conn.execute(
        "INSERT OR IGNORE INTO match_pair_blocks (uid, user_a, user_b, blocked_by, reason, source_session_uid, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (generate_uid(), a, b, blocked_by, reason, session_uid, created_at),
    )


def _record_decision_review(
    conn: sqlite3.Connection,
    reviewer: str,
    reviewee: str,
    session_uid: str,
    decision_type: str,
    reason: str,
    created_at: str,
):
    label = "매칭 성공 사유" if decision_type == "accept" else "매칭 거절 사유"
    rating = 5.0 if decision_type == "accept" else 1.0
    body = f"[{label}] {reason}".strip()
    conn.execute(
        "DELETE FROM reviews WHERE reviewer=? AND reviewee=? AND session_uid=? AND decision_type=?",
        (reviewer, reviewee, session_uid, decision_type),
    )
    conn.execute(
        "INSERT INTO reviews (uid, reviewer, reviewee, rating, body, session_uid, decision_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (generate_uid(), reviewer, reviewee, rating, body, session_uid, decision_type, created_at),
    )


def _decision_bundle(session: sqlite3.Row, side: str) -> dict:
    if side == "user":
        return {
            "my_decision": (session["user_decision"] or "").strip(),
            "other_decision": (session["candidate_decision"] or "").strip(),
            "my_reason": (session["user_reject_reason"] or "").strip(),
            "other_reason": (session["candidate_reject_reason"] or "").strip(),
        }
    return {
        "my_decision": (session["candidate_decision"] or "").strip(),
        "other_decision": (session["user_decision"] or "").strip(),
        "my_reason": (session["candidate_reject_reason"] or "").strip(),
        "other_reason": (session["user_reject_reason"] or "").strip(),
    }


def _has_blocking_match_state(conn: sqlite3.Connection, user_uid: str) -> tuple[bool, str | None]:
    rows = conn.execute(
        "SELECT uid, status, user_decision, candidate_decision FROM match_sessions "
        "WHERE (user_uid=? OR candidate_uid=? OR room_member_uids=? OR room_member_uids LIKE ? OR room_member_uids LIKE ? OR room_member_uids LIKE ?)",
        (user_uid, user_uid, user_uid, f"{user_uid},%", f"%,{user_uid},%", f"%,{user_uid}"),
    ).fetchall()
    for row in rows:
        if (row["status"] or "") == "active":
            open_thread = conn.execute(
                "SELECT 1 FROM chat_threads t "
                "WHERE t.session_uid=? AND t.status='open' AND (t.user_a=? OR t.user_b=?) "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM chat_thread_leaves l WHERE l.thread_uid=t.uid AND l.user_uid=?"
                ") "
                "LIMIT 1",
                (row["uid"], user_uid, user_uid, user_uid),
            ).fetchone()
            if not open_thread:
                continue
            if (row["user_decision"] or "") == "hold" or (row["candidate_decision"] or "") == "hold":
                return True, "on_hold"
            return True, "in_progress"
    return False, None


def _find_expandable_active_session(conn: sqlite3.Connection, user_uid: str) -> sqlite3.Row | None:
    rows = conn.execute(
        "SELECT s.*, COUNT(t.uid) AS thread_count "
        "FROM match_sessions s "
        "LEFT JOIN chat_threads t ON t.session_uid=s.uid "
        "WHERE (s.user_uid=? OR s.candidate_uid=? OR s.room_member_uids=? OR s.room_member_uids LIKE ? OR s.room_member_uids LIKE ? OR s.room_member_uids LIKE ?) "
        "AND s.status='active' "
        "GROUP BY s.uid "
        "HAVING thread_count < 5 "
        "ORDER BY s.created_at DESC "
        "LIMIT 1",
        (user_uid, user_uid, user_uid, f"{user_uid},%", f"%,{user_uid},%", f"%,{user_uid}"),
    ).fetchone()
    return rows


def _close_session_if_no_open_threads(conn: sqlite3.Connection, session_uid: str, now: str):
    open_row = conn.execute(
        "SELECT 1 FROM chat_threads WHERE session_uid=? AND status='open' LIMIT 1",
        (session_uid,),
    ).fetchone()
    if open_row:
        return
    # Session must remain active unless one of the explicit terminal conditions is met.
    # Rejected terminal state is allowed only when all 5 counterpart threads are rejected.
    counts = conn.execute(
        "SELECT "
        "COUNT(*) AS total_cnt, "
        "SUM(CASE WHEN status='closed' AND closed_reason='rejected' THEN 1 ELSE 0 END) AS rejected_cnt "
        "FROM chat_threads WHERE session_uid=?",
        (session_uid,),
    ).fetchone()
    total_cnt = int((counts["total_cnt"] if counts else 0) or 0)
    rejected_cnt = int((counts["rejected_cnt"] if counts else 0) or 0)

    if total_cnt >= 5 and rejected_cnt >= 5:
        conn.execute(
            "UPDATE match_sessions SET status='rejected', closed_at=?, last_activity_at=? WHERE uid=? AND status='active'",
            (now, now, session_uid),
        )
    else:
        conn.execute(
            "UPDATE match_sessions SET last_activity_at=? WHERE uid=?",
            (now, session_uid),
        )


def _is_session_member(session_row: sqlite3.Row, user_uid: str) -> bool:
    if user_uid in ((session_row["user_uid"] or ""), (session_row["candidate_uid"] or "")):
        return True
    members = [u.strip() for u in (session_row["room_member_uids"] or "").split(",") if u and u.strip()]
    return user_uid in members


def _delete_session_related_records(conn: sqlite3.Connection, session_id: str):
    thread_rows = conn.execute("SELECT uid FROM chat_threads WHERE session_uid=?", (session_id,)).fetchall()
    thread_ids = [r["uid"] for r in thread_rows]
    if thread_ids:
        placeholders = ",".join(["?"] * len(thread_ids))
        conn.execute(
            f"DELETE FROM chat_messages WHERE thread_uid IN ({placeholders})",
            tuple(thread_ids),
        )
        try:
            conn.execute(
                f"DELETE FROM chat_thread_leaves WHERE thread_uid IN ({placeholders})",
                tuple(thread_ids),
            )
        except Exception:
            pass
    conn.execute("DELETE FROM chat_threads WHERE session_uid=?", (session_id,))
    conn.execute("DELETE FROM match_history WHERE session_uid=?", (session_id,))
    conn.execute("DELETE FROM match_sessions WHERE uid=?", (session_id,))


def _chat_exchange_count(conn: sqlite3.Connection, thread_id: str) -> int:
    row = conn.execute(
        "SELECT chat_exchange_count FROM chat_threads WHERE uid=?",
        (thread_id,),
    ).fetchone()
    if not row:
        return 0

    cached = 0
    try:
        cached = int(row["chat_exchange_count"] or 0)
    except Exception:
        cached = 0

    actual_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM chat_messages "
        "WHERE thread_uid=? AND sender<>'system' AND type<>'system'",
        (thread_id,),
    ).fetchone()
    actual = int(actual_row["cnt"] or 0) if actual_row else 0

    return actual if actual > 0 else cached


def _expire_chat_messages_and_sessions():
    now = datetime.datetime.utcnow()
    cutoff_3d = (now - datetime.timedelta(days=CHAT_RETENTION_DAYS)).isoformat() + "Z"
    cutoff_2d = (now - datetime.timedelta(days=2)).isoformat() + "Z"
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (cutoff_3d,))
    stale = conn.execute(
        "SELECT uid FROM match_sessions WHERE status='active' AND last_activity_at IS NOT NULL AND last_activity_at < ?",
        (cutoff_2d,),
    ).fetchall()
    for row in stale:
        now_str = _now()
        conn.execute(
            "UPDATE match_sessions SET status='expired', closed_at=?, last_activity_at=? WHERE uid=?",
            (now_str, now_str, row["uid"]),
        )
        thread_rows = conn.execute(
            "SELECT uid FROM chat_threads WHERE session_uid=? AND status='open'",
            (row["uid"],),
        ).fetchall()
        conn.execute(
            "UPDATE chat_threads SET status='closed', closed_reason='expired', closed_at=? WHERE session_uid=? AND status='open'",
            (now_str, row["uid"]),
        )
        for thread_row in thread_rows:
            _broadcast_thread_state(conn, thread_row["uid"], "expired")
    conn.commit()
    conn.close()


@app.route("/api/match/pool/refresh", methods=["POST"])
@login_required
def refresh_pool():
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    target = db.get_profile_by_user_uid(payload["user_uid"])
    if not target:
        return jsonify({"error": "profile is required"}), 404
    if not _has_valid_survey_profile(target):
        return jsonify({"error": "설문 프로필이 필요합니다. 설문조사를 먼저 완료해주세요."}), 400
    user = db.get_user_by_uid(payload["user_uid"])
    school = _get_school_row(user.school_name) if user and user.school_name else None
    if school and _school_matching_phase(school) == "life":
        return jsonify({"error": "matching is disabled in life phase"}), 400

    all_profiles = db.fetch_profiles()
    pool = [p for p in all_profiles if _is_profile_compatible(target, p)]

    pool_conn = _app_conn()
    pool_conn.row_factory = sqlite3.Row
    user_rows = pool_conn.execute("SELECT uid, gender, is_suspended FROM users").fetchall()
    users_by_uid = {row["uid"]: row for row in user_rows}
    life_room_users = {
        row["user_uid"]
        for row in pool_conn.execute(
            "SELECT DISTINCT lm.user_uid FROM life_room_members lm "
            "JOIN life_rooms lr ON lr.uid=lm.life_room_uid "
            "WHERE lm.is_active=1 AND lr.status='active'"
        ).fetchall()
    }
    pool_conn.close()

    phase = _school_matching_phase(school) if school else "closed"

    def _candidate_eligible(p: RoommateProfile) -> bool:
        cand_user = users_by_uid.get(p.user_uid)
        if cand_user:
            if not cand_user["gender"] or cand_user["gender"] not in ("male", "female"):
                return False
            if int(cand_user["is_suspended"] or 0) == 1:
                return False
            if user and cand_user["gender"] != user.gender:
                return False
        else:
            return False
        if p.user_uid in life_room_users:
            return False
        candidate_interest = set(p.interest_room_type_ids or [])
        if p.fixed_interest_room_type_id:
            candidate_interest = {int(p.fixed_interest_room_type_id)}
        if not candidate_interest:
            return False
        if phase == "main":
            if not (p.fixed_interest_room_type_id or p.fixed_room_type_id):
                return False
        return True

    pool = [p for p in pool if _candidate_eligible(p)]

    target_pref = set(target.preferred_room_type_ids or [])
    if target.fixed_room_type_id:
        target_pref = {int(target.fixed_room_type_id)}
    filtered_pool: list[RoommateProfile] = []
    for p in pool:
        candidate_interest = set(p.interest_room_type_ids or [])
        if p.fixed_interest_room_type_id:
            candidate_interest = {int(p.fixed_interest_room_type_id)}
        if target_pref and candidate_interest and not (target_pref & candidate_interest):
            continue
        filtered_pool.append(p)
    results = [match(target, p) for p in filtered_pool]
    results = [r for r in results if not r.hard_block]
    results = [r for r in results if r.score >= 70.0]
    results.sort(key=lambda x: x.score, reverse=True)
    selected = _select_quota(results)

    now = _now()
    conn = _app_conn()
    conn.execute("DELETE FROM match_pool_candidates WHERE user_uid=?", (payload["user_uid"],))
    candidates = []
    for r in selected:
        candidate = {
            "candidate_type": "individual",
            "uid": r.profile_b.uid,
            "user_uid": r.profile_b.user_uid,
            "display_name": r.profile_b.name,
            "shared_score": r.score,
            "member_scores": [r.score],
            "member_names": [r.profile_b.name],
            "tier": _tier_from_score(r.score),
            "room_capacity": r.profile_b.room_capacity,
            "detail": r.detail,
            "border_style": "default",
            "profile": profile_to_dict(r.profile_b),
            "score": r.score,
        }
        candidates.append(candidate)
        conn.execute(
            "INSERT INTO match_pool_candidates (uid, user_uid, candidate_uid, candidate_type, display_name, shared_score, member_scores, member_names, tier, room_capacity, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                generate_uid(),
                payload["user_uid"],
                r.profile_b.user_uid,
                "individual",
                r.profile_b.name,
                r.score,
                json.dumps([r.score]),
                json.dumps([r.profile_b.name], ensure_ascii=False),
                _tier_from_score(r.score),
                r.profile_b.room_capacity,
                json.dumps(r.detail, ensure_ascii=False),
                now,
            ),
        )

    if target.room_capacity >= 3 and len(selected) >= 2:
        a, b = selected[0], selected[1]
        shared = round((a.score + b.score) / 2, 2)
        display_name = f"{a.profile_b.name}, {b.profile_b.name}의 방"
        room_payload = {
            "candidate_type": "room",
            "uid": f"room:{a.profile_b.user_uid}:{b.profile_b.user_uid}",
            "user_uid": "",
            "display_name": display_name,
            "shared_score": shared,
            "member_scores": [a.score, b.score],
            "member_names": [a.profile_b.name, b.profile_b.name],
            "tier": _tier_from_score(shared),
            "room_capacity": target.room_capacity,
            "detail": {
                k: round((a.detail.get(k, 0) + b.detail.get(k, 0)) / 2, 1)
                for k in set(a.detail.keys()) | set(b.detail.keys())
            },
            "border_style": "deep_blue",
            "members": [profile_to_dict(a.profile_b), profile_to_dict(b.profile_b)],
            "score": shared,
        }
        candidates.insert(0, room_payload)
        conn.execute(
            "INSERT INTO match_pool_candidates (uid, user_uid, candidate_uid, candidate_type, display_name, shared_score, member_scores, member_names, tier, room_capacity, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                generate_uid(),
                payload["user_uid"],
                f"{a.profile_b.user_uid},{b.profile_b.user_uid}",
                "room",
                display_name,
                shared,
                json.dumps([a.score, b.score]),
                json.dumps([a.profile_b.name, b.profile_b.name], ensure_ascii=False),
                _tier_from_score(shared),
                target.room_capacity,
                json.dumps(room_payload["detail"], ensure_ascii=False),
                now,
            ),
        )

    # Room-to-room candidate support: same hall + same room type + survey compatibility
    target_capacity = int(target.room_capacity or 2)
    target_room_type_id = int(target.fixed_room_type_id or 0) or None
    target_dorm_id = None
    if target_room_type_id:
        sconn = _schools_conn()
        sconn.row_factory = sqlite3.Row
        rt_row = sconn.execute(
            "SELECT dorm_id FROM dorm_room_types WHERE id=?",
            (target_room_type_id,),
        ).fetchone()
        if rt_row:
            target_dorm_id = int(rt_row["dorm_id"])
        sconn.close()

    min_room_members = 3 if target_capacity >= 5 else 2
    if target_capacity >= 4:
        room_rows = conn.execute(
            "SELECT lr.uid, lr.target_capacity, lr.fixed_hall, lr.fill_strategy, lr.room_type_id, "
            "COUNT(DISTINCT lrm.user_uid) AS member_count "
            "FROM life_rooms lr "
            "JOIN life_room_members lrm ON lrm.life_room_uid=lr.uid AND lrm.is_active=1 "
            "WHERE lr.status='active' "
            "GROUP BY lr.uid HAVING member_count >= ?",
            (min_room_members,),
        ).fetchall()
        for rr in room_rows:
            member_count = int(rr["member_count"] or 0)
            target_cap = int(rr["target_capacity"] or 2)
            if member_count >= target_cap:
                continue
            rr_room_type_id = int(rr["room_type_id"] or 0) or None
            if target_room_type_id and rr_room_type_id and rr_room_type_id != target_room_type_id:
                continue
            if target_dorm_id and rr_room_type_id:
                rr_sconn = _schools_conn()
                rr_sconn.row_factory = sqlite3.Row
                rr_rt = rr_sconn.execute("SELECT dorm_id FROM dorm_room_types WHERE id=?", (rr_room_type_id,)).fetchone()
                rr_sconn.close()
                if rr_rt and int(rr_rt["dorm_id"]) != target_dorm_id:
                    continue
            rr_member_rows = conn.execute(
                "SELECT user_uid FROM life_room_members WHERE life_room_uid=? AND is_active=1",
                (rr["uid"],),
            ).fetchall()
            rr_profiles = [db.get_profile_by_user_uid(m["user_uid"]) for m in rr_member_rows]
            rr_profiles = [p for p in rr_profiles if p is not None]
            if not rr_profiles:
                continue
            scores = [match(target, p) for p in rr_profiles]
            scores = [s for s in scores if not s.hard_block and s.score >= 70.0]
            if not scores:
                continue
            avg_score = round(sum(s.score for s in scores) / len(scores), 1)
            fill_rate = round((member_count / max(1, target_cap)) * 100, 1)
            member_names = [p.name for p in rr_profiles]
            member_scores = [round(s.score, 1) for s in scores]
            display_name = f"생활방 충원 {' '.join(member_names)} ({member_count}/{target_cap})"
            candidates.append({
                "candidate_type": "room",
                "uid": f"life:{rr['uid']}",
                "life_room_uid": rr["uid"],
                "display_name": display_name,
                "shared_score": avg_score,
                "member_scores": member_scores,
                "member_names": member_names,
                "tier": _tier_from_score(avg_score),
                "room_capacity": target_cap,
                "detail": {"fill_rate": fill_rate},
                "border_style": "deep_blue",
                "score": avg_score,
                "candidate_uids": [m["user_uid"] for m in rr_member_rows],
                "fill_rate": fill_rate,
            })

    conn.commit()

    target_interest = set(target.interest_room_type_ids or [])
    if target.fixed_interest_room_type_id:
        target_interest = {int(target.fixed_interest_room_type_id)}
    if target_interest and user:
        for p in filtered_pool:
            if p.user_uid == payload["user_uid"]:
                continue
            cand_interest = set(p.interest_room_type_ids or [])
            if p.fixed_interest_room_type_id:
                cand_interest = {int(p.fixed_interest_room_type_id)}
            if target_interest & cand_interest:
                cand_user = users_by_uid.get(p.user_uid)
                if cand_user and cand_user["gender"] == user.gender:
                    broadcast_message(p.user_uid, "interest_match", {
                        "matched_user_uid": payload["user_uid"],
                        "matched_user_name": target.name,
                        "overlapping_interest_room_type_ids": list(target_interest & cand_interest),
                    })

    conn.close()
    return jsonify({"candidates": candidates})


@app.route("/api/match/pool", methods=["GET"])
@login_required
def get_pool():
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM match_pool_candidates WHERE user_uid=? ORDER BY created_at DESC",
        (payload["user_uid"],),
    ).fetchall()
    conn.close()
    candidates = []
    for r in rows:
        member_scores = json.loads(r["member_scores"]) if r["member_scores"] else []
        member_names = json.loads(r["member_names"]) if r["member_names"] else []
        detail = json.loads(r["detail"]) if r["detail"] else {}
        candidate_type = r["candidate_type"] or "individual"
        candidate_uid = r["candidate_uid"] or ""
        candidate_uids = [u.strip() for u in candidate_uid.split(",") if u.strip()]
        item = {
            "candidate_type": candidate_type,
            "display_name": r["display_name"] or "",
            "shared_score": r["shared_score"] or 0,
            "member_scores": member_scores,
            "member_names": member_names,
            "tier": r["tier"],
            "room_capacity": r["room_capacity"] or 2,
            "detail": detail,
            "candidate_uids": candidate_uids,
            "border_style": "deep_blue" if (candidate_type == "room") else "default",
            "score": r["shared_score"] or 0,
            "profile": None,
            "members": [],
            "uid": "",
            "user_uid": "",
        }
        if candidate_type == "individual":
            p = db.get_profile_by_user_uid(r["candidate_uid"])
            if not p:
                continue
            item["uid"] = p.uid
            item["user_uid"] = p.user_uid
            item["profile"] = profile_to_dict(p)
            item["display_name"] = p.name
        else:
            item["uid"] = f"pool:{r['uid']}"
            members = []
            for uid in candidate_uids:
                p = db.get_profile_by_user_uid(uid.strip())
                if p:
                    members.append(profile_to_dict(p))
            item["members"] = members
        candidates.append(item)
    return jsonify({"candidates": candidates})


@app.route("/api/match/session/enter", methods=["POST"])
@login_required
def enter_session():
    payload = request.current_user
    my_profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not _has_valid_survey_profile(my_profile):
        return jsonify({"error": "survey profile is required before creating session"}), 400
    user = db.get_user_by_uid(payload["user_uid"])
    school = _get_school_row(user.school_name) if user and user.school_name else None
    if school and _school_matching_phase(school) == "life":
        return jsonify({"error": "matching is disabled in life phase"}), 400

    if my_profile:
        my_pref = set(my_profile.preferred_room_type_ids or [])
        if my_profile.fixed_room_type_id:
            my_pref = {int(my_profile.fixed_room_type_id)}
        my_interest = set(my_profile.interest_room_type_ids or [])
        if my_profile.fixed_interest_room_type_id:
            my_interest = {int(my_profile.fixed_interest_room_type_id)}
        if not my_interest:
            return jsonify({"error": "interest rooms must be set before creating session"}), 400
        if my_pref and not (my_pref <= my_interest):
            return jsonify({"error": "selected rooms must be a subset of interest rooms"}), 400
        if school:
            phase = _school_matching_phase(school)
            room_types = _get_room_types_for_school(int(school["id"]))
            allowed_ids = [int(r["id"]) for r in room_types
                           if int(r["is_enabled"] or 0) == 1 and r["dorm_gender"] in ("coed", user.gender)]
            max_sel = _selection_limit(len(allowed_ids), phase)
            selected_dorm_count = _count_distinct_dorms(list(my_pref), int(school["id"]))
            pref_dorm_ids = set()
            sconn = _schools_conn()
            sconn.row_factory = sqlite3.Row
            if my_pref:
                ph = ",".join(["?"] * len(my_pref))
                dorm_rows = sconn.execute(
                    f"SELECT DISTINCT d.id FROM dorm_room_types rt JOIN dormitories d ON d.id=rt.dorm_id WHERE rt.id IN ({ph})",
                    tuple(my_pref),
                ).fetchall()
                pref_dorm_ids = {int(r["id"]) for r in dorm_rows}
            sconn.close()
            if phase != "main" and selected_dorm_count > max_sel:
                return jsonify({"error": f"관 기준으로 최대 {max_sel}개까지 선택 가능합니다"}), 400
            if len(my_pref) > max_sel:
                return jsonify({"error": f"at most {max_sel} room types can be selected"}), 400

    data = request.get_json(force=True)
    candidates = data.get("candidates", [])
    if not candidates:
        return jsonify({"error": "candidate is required"}), 400

    candidate_uids = [str(c).strip() for c in candidates if str(c).strip()]
    if not candidate_uids:
        return jsonify({"error": "candidate is required"}), 400
    if len(candidate_uids) > 5:
        return jsonify({"error": "up to 5 candidates are allowed"}), 400

    uniq = []
    seen = set()
    for uid in candidate_uids:
        if uid not in seen:
            uniq.append(uid)
            seen.add(uid)
    candidate_uids = uniq

    now = _now()
    session_id = generate_uid()

    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    normalized_candidate_uids = []
    unresolved_candidate_uids = []
    for uid in candidate_uids:
        if db.get_user_by_uid(uid):
            normalized_uid = uid
        else:
            profile_row = conn.execute(
                "SELECT user_uid FROM profiles WHERE uid=? LIMIT 1",
                (uid,),
            ).fetchone()
            normalized_uid = profile_row["user_uid"] if profile_row else ""
        if normalized_uid:
            normalized_candidate_uids.append(normalized_uid)
        else:
            unresolved_candidate_uids.append(uid)

    if unresolved_candidate_uids:
        conn.close()
        return jsonify({"error": f"candidate not found: {unresolved_candidate_uids[0]}"}), 404

    uniq = []
    seen = set()
    for uid in normalized_candidate_uids:
        if uid not in seen:
            uniq.append(uid)
            seen.add(uid)
    candidate_uids = uniq

    if payload["user_uid"] in candidate_uids:
        conn.close()
        return jsonify({"error": "cannot create session with yourself"}), 400

    active_life_room = _active_life_room_for_user(conn, payload["user_uid"])
    if active_life_room:
        if int(active_life_room["fixed_hall"] or 0) != 1:
            conn.close()
            return jsonify({"error": "life room hall must be fixed before matching"}), 403
        conn.close()
        return jsonify({
            "error": "already_in_life_room",
            "message": "이미 생활방이 있습니다",
            "life_room_uid": active_life_room["uid"],
        }), 409
    row = conn.execute("SELECT cooldown_until FROM match_cooldowns WHERE user_uid=?", (payload["user_uid"],)).fetchone()
    if row and row["cooldown_until"]:
        t = _parse_ts(row["cooldown_until"])
        if t and datetime.datetime.utcnow() < t:
            conn.close()
            return jsonify({"error": "cooldown active", "cooldown_until": row["cooldown_until"]}), 403
    existing_threads_by_candidate: dict[str, sqlite3.Row] = {}
    for candidate_uid in candidate_uids:
        row = conn.execute(
            "SELECT uid, session_uid, created_at FROM chat_threads "
            "WHERE status='open' AND ((user_a=? AND user_b=?) OR (user_a=? AND user_b=?)) "
            "ORDER BY created_at DESC LIMIT 1",
            (payload["user_uid"], candidate_uid, candidate_uid, payload["user_uid"]),
        ).fetchone()
        if row:
            existing_threads_by_candidate[candidate_uid] = row

    if len(existing_threads_by_candidate) == len(candidate_uids):
        thread_ids = [existing_threads_by_candidate[uid]["uid"] for uid in candidate_uids]
        session_id = existing_threads_by_candidate[candidate_uids[0]]["session_uid"]
        conn.close()
        return jsonify({"session_id": session_id, "thread_ids": thread_ids, "reused": True}), 200

    if existing_threads_by_candidate:
        session_ids = {row["session_uid"] for row in existing_threads_by_candidate.values() if row["session_uid"]}
        if len(session_ids) == 1:
            reused_session_id = next(iter(session_ids))
            base_session = conn.execute(
                "SELECT * FROM match_sessions WHERE uid=?",
                (reused_session_id,),
            ).fetchone()
            if base_session and _is_session_member(base_session, payload["user_uid"]) and (base_session["status"] or "") == "active":
                thread_ids = []
                for candidate_uid in candidate_uids:
                    existing = existing_threads_by_candidate.get(candidate_uid)
                    if existing:
                        thread_ids.append(existing["uid"])
                        continue
                    thread_id = generate_uid()
                    thread_ids.append(thread_id)
                    conn.execute(
                        "INSERT INTO chat_threads (uid, session_uid, user_a, user_b, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (thread_id, reused_session_id, payload["user_uid"], candidate_uid, "open", now),
                    )
                conn.commit()
                conn.close()
                return jsonify({"session_id": reused_session_id, "thread_ids": thread_ids, "reused": True, "expanded": True}), 200

    expandable_session = _find_expandable_active_session(conn, payload["user_uid"])
    if expandable_session:
        existing_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM chat_threads WHERE session_uid=?",
            (expandable_session["uid"],),
        ).fetchone()
        remaining_slots = 5 - int((existing_count["cnt"] if existing_count else 0) or 0)
        missing_candidates = [
            uid for uid in candidate_uids
            if uid not in existing_threads_by_candidate and not _is_pair_blocked(conn, payload["user_uid"], uid)
        ]
        if len(missing_candidates) > remaining_slots:
            conn.close()
            return jsonify({"error": "up to 5 candidates are allowed per session"}), 400

        thread_ids = []
        for candidate_uid in candidate_uids:
            existing = existing_threads_by_candidate.get(candidate_uid)
            if existing:
                thread_ids.append(existing["uid"])
                continue
            if _is_pair_blocked(conn, payload["user_uid"], candidate_uid):
                conn.close()
                return jsonify({"error": "pair_blocked"}), 403
            thread_id = generate_uid()
            thread_ids.append(thread_id)
            conn.execute(
                "INSERT INTO chat_threads (uid, session_uid, user_a, user_b, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, expandable_session["uid"], payload["user_uid"], candidate_uid, "open", now),
            )
        session_members = [
            uid.strip()
            for uid in (expandable_session["room_member_uids"] or "").split(",")
            if uid and uid.strip()
        ]
        for candidate_uid in candidate_uids:
            if candidate_uid not in session_members:
                session_members.append(candidate_uid)
        conn.execute(
            "UPDATE match_sessions SET room_member_uids=?, last_activity_at=? WHERE uid=?",
            (",".join(session_members), now, expandable_session["uid"]),
        )
        conn.commit()
        conn.close()
        return jsonify({"session_id": expandable_session["uid"], "thread_ids": thread_ids, "reused": True, "expanded": True}), 200

    blocked, reason = _has_blocking_match_state(conn, payload["user_uid"])
    if blocked:
        conn.close()
        return jsonify({"error": reason or "blocked"}), 403

    candidate_type = "room" if len(candidate_uids) >= 2 else "individual"
    delegate_uid = candidate_uids[0] if candidate_uids else ""
    conn.execute(
        "INSERT INTO match_sessions (uid, user_uid, candidate_uid, candidate_type, room_member_uids, delegate_uid, status, user_confirmed, candidate_confirmed, last_activity_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, payload["user_uid"], candidate_uids[0], candidate_type, ",".join(candidate_uids), delegate_uid, "active", 0, 0, now, now),
    )

    thread_ids = []
    for candidate_uid in candidate_uids:
        existing = existing_threads_by_candidate.get(candidate_uid)
        if existing:
            thread_ids.append(existing["uid"])
            continue
        thread_id = generate_uid()
        thread_ids.append(thread_id)
        conn.execute(
            "INSERT INTO chat_threads (uid, session_uid, user_a, user_b, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (thread_id, session_id, payload["user_uid"], candidate_uid, "open", now),
        )
    conn.commit()
    conn.close()
    return jsonify({"session_id": session_id, "thread_ids": thread_ids}), 201


@app.route("/api/match/session/active", methods=["GET"])
@login_required
def get_active_sessions():
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    uid = payload["user_uid"]
    rows = conn.execute(
        "SELECT * FROM match_sessions "
        "WHERE (user_uid=? OR candidate_uid=? OR room_member_uids=? OR room_member_uids LIKE ? OR room_member_uids LIKE ? OR room_member_uids LIKE ?) "
        "AND status IN ('active','confirmed') ORDER BY created_at DESC",
        (uid, uid, uid, f"{uid},%", f"%,{uid},%", f"%,{uid}"),
    ).fetchall()
    conn.close()
    sessions = [dict(r) for r in rows]
    return jsonify({"sessions": sessions})


@app.route("/api/match/session/history", methods=["GET"])
@login_required
def get_session_history():
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    uid = payload["user_uid"]
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    six_month_cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=180)).isoformat() + "Z"
    old_rows = conn.execute(
        "SELECT * FROM match_sessions "
        "WHERE status IN ('rejected','cancelled','closed','expired') "
        "AND COALESCE(closed_at, created_at) < ?",
        (six_month_cutoff,),
    ).fetchall()
    for old in old_rows:
        _delete_session_related_records(conn, old["uid"])

    sessions = conn.execute(
        "SELECT * FROM match_sessions "
        "WHERE (user_uid=? OR candidate_uid=? OR room_member_uids=? OR room_member_uids LIKE ? OR room_member_uids LIKE ? OR room_member_uids LIKE ?) "
        "ORDER BY created_at DESC",
        (uid, uid, uid, f"{uid},%", f"%,{uid},%", f"%,{uid}"),
    ).fetchall()

    result = []
    for s in sessions:
        thread_rows = conn.execute(
            "SELECT * FROM chat_threads WHERE session_uid=? ORDER BY created_at DESC",
            (s["uid"],),
        ).fetchall()
        thread_items = []
        has_open_thread = False
        all_closed_as_rejected = True
        for t in thread_rows:
            other_uid = t["user_b"] if t["user_a"] == uid else t["user_a"]
            if other_uid == uid:
                continue
            chat_count = int(t["chat_exchange_count"] or 0)
            if chat_count <= 0:
                continue
            other = db.get_user_by_uid(other_uid)
            if (t["status"] or "open") == "open":
                has_open_thread = True
                all_closed_as_rejected = False
            elif (t["closed_reason"] or "") != "rejected":
                all_closed_as_rejected = False
            thread_items.append({
                "thread_id": t["uid"],
                "other_uid": other_uid,
                "other_user": other.name if other else other_uid,
                "status": t["status"] or "open",
                "closed_reason": t["closed_reason"],
                "chat_exchange_count": chat_count,
                "created_at": t["created_at"],
            })

        if not thread_items:
            continue

        if (s["status"] or "") == "confirmed":
            ui_status = "match_success"
        elif (s["status"] or "") == "rejected":
            ui_status = "rejected"
        elif (s["status"] or "") in ("expired", "cancelled"):
            ui_status = "expired"
        elif (s["status"] or "") == "active" and ((s["user_decision"] or "") == "hold" or (s["candidate_decision"] or "") == "hold"):
            ui_status = "on_hold"
        else:
            ui_status = "in_progress"
        result.append({
            "session_id": s["uid"],
            "candidate_type": s["candidate_type"] or "individual",
            "match_kind": "dormitory",
            "created_at": s["created_at"],
            "status": s["status"] or "",
            "ui_status": ui_status,
            "is_deletable": ui_status == "expired",
            "user_decision": s["user_decision"] or "",
            "candidate_decision": s["candidate_decision"] or "",
            "user_reason": s["user_reject_reason"] or "",
            "candidate_reason": s["candidate_reject_reason"] or "",
            "threads": thread_items,
        })

    me = db.get_user_by_uid(uid)
    my_school = _get_school_row(me.school_name) if me and me.school_name else None
    if my_school and _school_matching_phase(my_school) == "life":
        life = _active_life_room_for_user(conn, uid)
        if life:
            member_count = conn.execute(
                "SELECT COUNT(*) AS c FROM life_room_members WHERE life_room_uid=? AND is_active=1",
                (life["uid"],),
            ).fetchone()
            result.insert(0, {
                "session_id": f"life:{life['uid']}",
                "candidate_type": "room",
                "match_kind": "life_room",
                "created_at": life["created_at"],
                "status": life["status"],
                "ui_status": "life_room_active",
                "is_deletable": False,
                "member_count": int((member_count["c"] if member_count else 0) or 0),
                "life_room_uid": life["uid"],
                "threads": [],
            })

    conn.commit()
    conn.close()
    return jsonify({"sessions": result})


@app.route("/api/match/session/history/<session_id>", methods=["DELETE"])
@login_required
def delete_session_history(session_id: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    _ensure_thread_leaves_table(conn)
    session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session_id,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    if not _is_session_member(session, payload["user_uid"]):
        conn.close()
        return jsonify({"error": "forbidden"}), 403

    status = (session["status"] or "").strip()
    if status in ("active", "confirmed"):
        conn.close()
        return jsonify({"error": "only expired history can be deleted"}), 400

    _delete_session_related_records(conn, session_id)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "deleted_session_id": session_id})


@app.route("/api/match/confirm", methods=["POST"])
@login_required
def confirm_match():
    payload = request.current_user
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    _ = data.get("room_confirm_mode", "delegate")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    return _confirm_match_internal(payload["user_uid"], session_id)


def _confirm_match_internal(current_user_uid: str, session_id: str):
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    s = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session_id,)).fetchone()
    if not s:
        conn.close()
        return jsonify({"error": "session not found"}), 404

    room_members = [u.strip() for u in (s["room_member_uids"] or "").split(",") if u and u.strip()]
    delegate_uid = (s["delegate_uid"] or "").strip() if "delegate_uid" in s.keys() else ""
    if not delegate_uid and room_members:
        delegate_uid = room_members[0]
    effective_candidate_uid = delegate_uid or s["candidate_uid"]

    if current_user_uid == s["user_uid"]:
        conn.execute("UPDATE match_sessions SET user_confirmed=1, last_activity_at=? WHERE uid=?", (now, session_id))
    elif current_user_uid == effective_candidate_uid:
        conn.execute("UPDATE match_sessions SET candidate_confirmed=1, last_activity_at=? WHERE uid=?", (now, session_id))
    elif current_user_uid in room_members:
        conn.execute("UPDATE match_sessions SET last_activity_at=? WHERE uid=?", (now, session_id))
        conn.commit()
        conn.close()
        return jsonify({"session_id": session_id, "status": "waiting_delegate", "delegate_uid": effective_candidate_uid})
    else:
        conn.close()
        return jsonify({"error": "forbidden"}), 403

    s = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session_id,)).fetchone()
    if s["user_confirmed"] and s["candidate_confirmed"]:
        conn.execute("UPDATE match_sessions SET status='confirmed', confirmed_at=? WHERE uid=?", (now, session_id))
        conn.execute(
            "INSERT INTO match_history (uid, session_uid, user_a, user_b, status, matched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (generate_uid(), session_id, s["user_uid"], s["candidate_uid"], "active", now),
        )
        cooldown_until = (datetime.datetime.utcnow() + datetime.timedelta(hours=72)).isoformat() + "Z"
        counterpart_uids = [s["candidate_uid"]]
        if room_members:
            counterpart_uids = room_members
        notify_uids = [s["user_uid"], *counterpart_uids]
        host_user = db.get_user_by_uid(s["user_uid"])
        school_row = _get_school_row(host_user.school_name) if host_user and host_user.school_name else None
        if school_row:
            _find_or_create_life_room(
                conn=conn,
                school_id=int(school_row["id"]),
                host_uid=s["user_uid"],
                member_uids=notify_uids,
                target_capacity=max(2, len(notify_uids)),
            )

        for u in notify_uids:
            conn.execute(
                "INSERT OR REPLACE INTO match_cooldowns (uid, user_uid, cooldown_until, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (generate_uid(), u, cooldown_until, "matched", now),
            )

        others = conn.execute(
            "SELECT uid FROM match_sessions WHERE uid<>? AND status='active' AND (user_uid IN (?, ?) OR candidate_uid IN (?, ?))",
            (session_id, s["user_uid"], s["candidate_uid"], s["user_uid"], s["candidate_uid"]),
        ).fetchall()
        for u in notify_uids:
            conn.execute(
                "UPDATE profiles SET hall_confirmed_at=? WHERE user_uid=?",
                (now, u),
            )
        for row in others:
            conn.execute("UPDATE match_sessions SET status='closed', closed_at=? WHERE uid=?", (now, row["uid"]))
            thread_rows = conn.execute(
                "SELECT uid, user_a, user_b FROM chat_threads WHERE session_uid=? AND status='open'",
                (row["uid"],),
            ).fetchall()
            for t in thread_rows:
                conn.execute(
                    "UPDATE chat_threads SET status='closed', closed_reason='already_matched', closed_at=? WHERE uid=?",
                    (now, t["uid"]),
                )
                _insert_system_message(
                    conn=conn,
                    thread_uid=t["uid"],
                    session_uid=row["uid"],
                    sender="system",
                    receiver=t["user_a"],
                    content="사용자가 이미 매칭됨",
                )
                _insert_system_message(
                    conn=conn,
                    thread_uid=t["uid"],
                    session_uid=row["uid"],
                    sender="system",
                    receiver=t["user_b"],
                    content="사용자가 이미 매칭됨",
                )
                _broadcast_thread_state(conn, t["uid"], "already_matched")

        conn.commit()
        conn.close()
        for u in notify_uids:
            broadcast_message(u, "match_confirmed", {"session_id": session_id, "event_type": "match_confirmed"})
        return jsonify({"session_id": session_id, "status": "confirmed"})

    conn.commit()
    conn.close()
    return jsonify({"session_id": session_id, "status": "waiting"})


@app.route("/api/match/session/<session_id>/confirm", methods=["POST"])
@login_required
def confirm_session_compat(session_id):
    payload = request.current_user
    return _confirm_match_internal(payload["user_uid"], session_id)


@app.route("/api/match/session/<session_id>/cancel", methods=["POST"])
@login_required
def cancel_session_compat(session_id):
    payload = request.current_user
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    s = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session_id,)).fetchone()
    if not s:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    if payload["user_uid"] not in (s["user_uid"], s["candidate_uid"]):
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    conn.execute("UPDATE match_sessions SET status='cancelled', closed_at=? WHERE uid=?", (now, session_id))
    thread_rows = conn.execute(
        "SELECT uid FROM chat_threads WHERE session_uid=?",
        (session_id,),
    ).fetchall()
    conn.execute(
        "UPDATE chat_threads SET status='closed', closed_reason='cancelled', closed_at=? WHERE session_uid=?",
        (now, session_id),
    )
    for t in thread_rows:
        _broadcast_thread_state(conn, t["uid"], "cancelled")
    conn.commit()
    conn.close()
    return jsonify({"session_id": session_id, "status": "cancelled"})


@app.route("/api/match/rematch", methods=["POST"])
@login_required
def rematch():
    payload = request.current_user
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    s = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session_id,)).fetchone()
    if not s:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    if payload["user_uid"] not in (s["user_uid"], s["candidate_uid"]):
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    other = s["candidate_uid"] if payload["user_uid"] == s["user_uid"] else s["user_uid"]
    row = conn.execute("SELECT cooldown_until FROM match_cooldowns WHERE user_uid=?", (payload["user_uid"],)).fetchone()
    if row and row["cooldown_until"]:
        t = _parse_ts(row["cooldown_until"])
        if t and datetime.datetime.utcnow() < t:
            conn.close()
            broadcast_message(other, "rematch_attempt_blocked", {
                "event_type": "rematch_attempt_blocked",
                "session_id": session_id,
                "user_uid": payload["user_uid"],
                "cooldown_until": row["cooldown_until"],
            })
            return jsonify({"error": "cooldown active", "cooldown_until": row["cooldown_until"]}), 403

    conn.execute("UPDATE match_sessions SET status='closed', closed_at=? WHERE uid=?", (_now(), session_id))
    thread_rows = conn.execute(
        "SELECT uid FROM chat_threads WHERE session_uid=?",
        (session_id,),
    ).fetchall()
    conn.execute(
        "UPDATE chat_threads SET status='closed', closed_reason='rematch', closed_at=? WHERE session_uid=?",
        (_now(), session_id),
    )
    for t in thread_rows:
        _broadcast_thread_state(conn, t["uid"], "rematch")
    conn.commit()
    conn.close()
    broadcast_message(other, "rematch_notice", {
        "event_type": "rematch_notice",
        "session_id": session_id,
        "user_uid": payload["user_uid"],
    })
    return jsonify({"ok": True, "status": "closed"})


@app.route("/api/match/cooldown", methods=["GET"])
@login_required
def get_cooldown():
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT cooldown_until FROM match_cooldowns WHERE user_uid=?", (payload["user_uid"],)).fetchone()
    conn.close()
    if not row or not row["cooldown_until"]:
        return jsonify({"in_cooldown": False, "cooldown_until": None})
    t = _parse_ts(row["cooldown_until"])
    if t and datetime.datetime.utcnow() >= t:
        return jsonify({"in_cooldown": False, "cooldown_until": row["cooldown_until"]})
    return jsonify({"in_cooldown": True, "cooldown_until": row["cooldown_until"]})


@app.route("/api/chat/threads", methods=["GET"])
@login_required
def get_threads():
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    _ensure_thread_leaves_table(conn)
    rows = conn.execute(
        "SELECT t.* FROM chat_threads t "
        "WHERE (t.user_a=? OR t.user_b=?) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM chat_thread_leaves l WHERE l.thread_uid=t.uid AND l.user_uid=?"
        ") "
        "ORDER BY t.created_at DESC",
        (payload["user_uid"], payload["user_uid"], payload["user_uid"]),
    ).fetchall()
    conn.close()
    threads = []
    for r in rows:
        other_uid = r["user_b"] if r["user_a"] == payload["user_uid"] else r["user_a"]
        other = db.get_user_by_uid(other_uid)
        threads.append({
            "thread_id": r["uid"],
            "session_id": r["session_uid"],
            "other_uid": other_uid,
            "other_user": other.name if other else other_uid,
            "status": r["status"],
            "closed_reason": r["closed_reason"],
            "chat_exchange_count": int(r["chat_exchange_count"] or 0),
            "created_at": r["created_at"],
        })
    return jsonify({"threads": threads})


@app.route("/api/chat/threads/<thread_id>/meta", methods=["GET"])
@login_required
def get_thread_meta(thread_id):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    thread = conn.execute(
        "SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)",
        (thread_id, payload["user_uid"], payload["user_uid"]),
    ).fetchone()
    if not thread:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    session = conn.execute(
        "SELECT * FROM match_sessions WHERE uid=?",
        (thread["session_uid"],),
    ).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "session not found"}), 404

    side = _session_side_for_user(session, payload["user_uid"])
    if side is None:
        conn.close()
        return jsonify({"error": "forbidden"}), 403

    count = _chat_exchange_count(conn, thread_id)
    if side == "user":
        my_survey_opened = int(session["user_survey_opened"] or 0) == 1
        other_survey_opened = int(session["candidate_survey_opened"] or 0) == 1
    else:
        my_survey_opened = int(session["candidate_survey_opened"] or 0) == 1
        other_survey_opened = int(session["user_survey_opened"] or 0) == 1
    decisions = _decision_bundle(session, side)
    # In room sessions, decisions should be thread-scoped, not shared across
    # every peer in the same session.
    if (session["candidate_type"] or "") == "room":
        decisions = {
            "my_decision": "",
            "other_decision": "",
            "my_reason": "",
            "other_reason": "",
        }
        if (thread["closed_reason"] or "") == "rejected":
            me_left = conn.execute(
                "SELECT 1 FROM chat_thread_leaves WHERE thread_uid=? AND user_uid=? LIMIT 1",
                (thread_id, payload["user_uid"]),
            ).fetchone()
            if me_left:
                decisions["my_decision"] = "rejected"
            else:
                decisions["other_decision"] = "rejected"
    conn.close()

    return jsonify({
        "thread_id": thread_id,
        "session_id": session["uid"],
        "message_count": count,
        "survey_enabled": count >= 4,
        "matching_enabled": count >= 7,
        "my_survey_opened": my_survey_opened,
        "other_survey_opened": other_survey_opened,
        "my_decision": decisions["my_decision"],
        "other_decision": decisions["other_decision"],
        "my_reason": decisions["my_reason"],
        "other_reason": decisions["other_reason"],
        "session_status": session["status"] or "",
    })


@app.route("/api/chat/threads/<thread_id>/survey/open", methods=["POST"])
@login_required
def open_thread_survey(thread_id):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    thread = conn.execute(
        "SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)",
        (thread_id, payload["user_uid"], payload["user_uid"]),
    ).fetchone()
    if not thread:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (thread["session_uid"],)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    side = _session_side_for_user(session, payload["user_uid"])
    if side is None:
        conn.close()
        return jsonify({"error": "forbidden"}), 403

    count = _chat_exchange_count(conn, thread_id)
    if count < 4:
        conn.close()
        return jsonify({"error": "survey_locked", "required": 4, "message_count": count}), 403

    now = _now()
    if side == "user":
        conn.execute(
            "UPDATE match_sessions SET user_survey_opened=1, last_activity_at=? WHERE uid=?",
            (now, session["uid"]),
        )
    else:
        conn.execute(
            "UPDATE match_sessions SET candidate_survey_opened=1, last_activity_at=? WHERE uid=?",
            (now, session["uid"]),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "opened": True})


@app.route("/api/chat/threads/<thread_id>/survey/opened-profile", methods=["GET"])
@login_required
def get_opened_survey_profile(thread_id):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    thread = conn.execute(
        "SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)",
        (thread_id, payload["user_uid"], payload["user_uid"]),
    ).fetchone()
    if not thread:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (thread["session_uid"],)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    side = _session_side_for_user(session, payload["user_uid"])
    if side is None:
        conn.close()
        return jsonify({"error": "forbidden"}), 403

    if side == "user":
        if int(session["candidate_survey_opened"] or 0) != 1:
            conn.close()
            return jsonify({"error": "survey_not_opened"}), 403
    else:
        if int(session["user_survey_opened"] or 0) != 1:
            conn.close()
            return jsonify({"error": "survey_not_opened"}), 403

    other_uid = thread["user_b"] if thread["user_a"] == payload["user_uid"] else thread["user_a"]
    profile = db.get_profile_by_user_uid(other_uid)
    if not profile:
        conn.close()
        return jsonify({"error": "profile not found"}), 404
    reviews = conn.execute(
        "SELECT * FROM reviews WHERE reviewee=? ORDER BY created_at DESC",
        (other_uid,),
    ).fetchall()
    conn.close()
    return jsonify({
        "other_uid": other_uid,
        "profile": profile_to_dict(profile),
        "reviews": [dict(r) for r in reviews],
    })


@app.route("/api/chat/threads/<thread_id>/match-decision", methods=["POST"])
@login_required
def decide_thread_match(thread_id):
    payload = request.current_user
    data = request.get_json(force=True) or {}
    action = (data.get("action") or "").strip().lower()
    reason = (data.get("reason") or "").strip()
    if action not in ("accept", "reject", "hold"):
        return jsonify({"error": "action must be one of accept/reject/hold"}), 400
    if action in ("accept", "reject") and len(reason) < 5:
        return jsonify({"error": f"{action} reason must be at least 5 characters"}), 400

    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    _ensure_thread_leaves_table(conn)
    thread = conn.execute(
        "SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)",
        (thread_id, payload["user_uid"], payload["user_uid"]),
    ).fetchone()
    if not thread:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    other_uid = thread["user_b"] if thread["user_a"] == payload["user_uid"] else thread["user_a"]
    session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (thread["session_uid"],)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "session not found"}), 404
    side = _session_side_for_user(session, payload["user_uid"])
    if side is None:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    if (session["status"] or "") not in ("active", "confirmed"):
        conn.close()
        return jsonify({"error": "session_closed"}), 403

    count = _chat_exchange_count(conn, thread_id)
    if count < 7:
        conn.close()
        return jsonify({"error": "matching_locked", "required": 7, "message_count": count}), 403

    is_room_session = (session["candidate_type"] or "") == "room"

    if side == "user":
        my_decision_col = "user_decision"
        my_reason_col = "user_reject_reason"
        other_decision = (session["candidate_decision"] or "").strip()
    else:
        my_decision_col = "candidate_decision"
        my_reason_col = "candidate_reject_reason"
        other_decision = (session["user_decision"] or "").strip()

    if action == "hold":
        conn.execute(
            f"UPDATE match_sessions SET {my_decision_col}='hold', {my_reason_col}=NULL, last_activity_at=? WHERE uid=?",
            (now, session["uid"]),
        )
        session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session["uid"],)).fetchone()
        decision_payload = _decision_bundle(session, side)
        decision_payload.update({
            "event_type": "match_decision",
            "thread_id": thread_id,
            "session_id": session["uid"],
            "actor_uid": payload["user_uid"],
            "action": "hold",
            "session_status": session["status"] or "",
        })
        broadcast_message(other_uid, "match_decision", decision_payload)
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": "on_hold"})

    if action == "reject":
        # For room sessions, reject is per-thread and must not mark all peers.
        if is_room_session:
            conn.execute(
                "UPDATE match_sessions SET last_activity_at=? WHERE uid=?",
                (now, session["uid"]),
            )
        else:
            conn.execute(
                f"UPDATE match_sessions SET {my_decision_col}='rejected', {my_reason_col}=?, last_activity_at=? WHERE uid=?",
                (reason, now, session["uid"]),
            )
        conn.execute(
            "UPDATE chat_threads SET status='closed', closed_reason='rejected', closed_at=? WHERE uid=?",
            (now, thread_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO chat_thread_leaves (thread_uid, user_uid, left_at) VALUES (?, ?, ?)",
            (thread_id, payload["user_uid"], now),
        )
        _record_decision_review(
            conn=conn,
            reviewer=payload["user_uid"],
            reviewee=other_uid,
            session_uid=session["uid"],
            decision_type="reject",
            reason=reason,
            created_at=now,
        )
        _broadcast_thread_state(
            conn,
            thread_id,
            "rejected",
            {"rejected_by": payload["user_uid"], "reject_reason": reason},
        )

        _close_session_if_no_open_threads(conn, session["uid"], now)
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": "rejected", "left_thread": True})

    conn.execute(
        f"UPDATE match_sessions SET {my_decision_col}='accepted', {my_reason_col}=?, last_activity_at=? WHERE uid=?",
        (reason, now, session["uid"]),
    )
    _record_decision_review(
        conn=conn,
        reviewer=payload["user_uid"],
        reviewee=other_uid,
        session_uid=session["uid"],
        decision_type="accept",
        reason=reason,
        created_at=now,
    )
    matched = other_decision == "accepted"
    if matched:
        conn.execute(
            "UPDATE match_sessions SET status='confirmed', confirmed_at=?, last_activity_at=? WHERE uid=?",
            (now, now, session["uid"]),
        )
        conn.execute(
            "INSERT INTO match_history (uid, session_uid, user_a, user_b, status, matched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (generate_uid(), session["uid"], session["user_uid"], session["candidate_uid"], "active", now),
        )
        counterpart_uids = [session["candidate_uid"]]
        room_members = [u.strip() for u in (session["room_member_uids"] or "").split(",") if u and u.strip()]
        if room_members:
            counterpart_uids = room_members
        notify_uids = [session["user_uid"], *counterpart_uids]
        host_user = db.get_user_by_uid(session["user_uid"])
        school_row = _get_school_row(host_user.school_name) if host_user and host_user.school_name else None
        if school_row:
            _find_or_create_life_room(
                conn=conn,
                school_id=int(school_row["id"]),
                host_uid=session["user_uid"],
                member_uids=notify_uids,
                target_capacity=max(2, len(notify_uids)),
            )
        cooldown_until = (datetime.datetime.utcnow() + datetime.timedelta(hours=72)).isoformat() + "Z"
        for u in notify_uids:
            conn.execute(
                "INSERT OR REPLACE INTO match_cooldowns (uid, user_uid, cooldown_until, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (generate_uid(), u, cooldown_until, "matched", now),
            )
        other_sessions = conn.execute(
            "SELECT uid FROM match_sessions WHERE uid<>? AND status='active' "
            "AND (user_uid IN (?, ?) OR candidate_uid IN (?, ?) OR room_member_uids LIKE ? OR room_member_uids LIKE ?)",
            (
                session["uid"],
                session["user_uid"],
                session["candidate_uid"],
                session["user_uid"],
                session["candidate_uid"],
                f"%{session['user_uid']}%",
                f"%{session['candidate_uid']}%",
            ),
        ).fetchall()
        for other_session in other_sessions:
            conn.execute(
                "UPDATE match_sessions SET status='closed', closed_at=?, last_activity_at=? WHERE uid=?",
                (now, now, other_session["uid"]),
            )
            open_threads = conn.execute(
                "SELECT uid, user_a, user_b FROM chat_threads WHERE session_uid=? AND status='open'",
                (other_session["uid"],),
            ).fetchall()
            for open_thread in open_threads:
                conn.execute(
                    "UPDATE chat_threads SET status='closed', closed_reason='already_matched', closed_at=? WHERE uid=?",
                    (now, open_thread["uid"]),
                )
                _insert_system_message(
                    conn=conn,
                    thread_uid=open_thread["uid"],
                    session_uid=other_session["uid"],
                    sender="system",
                    receiver=open_thread["user_a"],
                    content="사용자가 이미 매칭됨",
                )
                _insert_system_message(
                    conn=conn,
                    thread_uid=open_thread["uid"],
                    session_uid=other_session["uid"],
                    sender="system",
                    receiver=open_thread["user_b"],
                    content="사용자가 이미 매칭됨",
                )
                _broadcast_thread_state(conn, open_thread["uid"], "already_matched")
    session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (session["uid"],)).fetchone()
    decision_payload = _decision_bundle(session, side)
    decision_payload.update({
        "event_type": "match_decision",
        "thread_id": thread_id,
        "session_id": session["uid"],
        "actor_uid": payload["user_uid"],
        "action": action,
        "session_status": session["status"] or "",
    })
    broadcast_message(other_uid, "match_decision", decision_payload)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": "confirmed" if matched else "waiting"})


@app.route("/api/chat/threads/<thread_id>/messages", methods=["POST"])
@login_required
def send_thread_message(thread_id):
    payload = request.current_user
    data = request.get_json(force=True)
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400
    msg_type = data.get("type", "text")
    now = _now()
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=CHAT_RETENTION_DAYS)).isoformat() + "Z"

    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    t = conn.execute("SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)", (thread_id, payload["user_uid"], payload["user_uid"])).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    if t["status"] != "open":
        conn.close()
        return jsonify({"error": "thread is closed"}), 403
    receiver = t["user_b"] if t["user_a"] == payload["user_uid"] else t["user_a"]
    uid = generate_uid()
    conn.execute(
        "INSERT INTO chat_messages (uid, session_uid, thread_uid, sender, receiver, content, type, read, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, t["session_uid"], thread_id, payload["user_uid"], receiver, content, msg_type, 0, expires, now),
    )
    conn.execute(
        "UPDATE chat_threads SET last_message_at=?, chat_exchange_count=COALESCE(chat_exchange_count, 0)+1 WHERE uid=?",
        (now, thread_id),
    )
    conn.execute("UPDATE match_sessions SET last_activity_at=? WHERE uid=?", (now, t["session_uid"]))
    conn.commit()
    conn.close()

    broadcast_message(receiver, "chat_message", {
        "event_type": "chat_message",
        "uid": uid,
        "thread_id": thread_id,
        "session_id": t["session_uid"],
        "sender": payload["user_uid"],
        "content": content,
        "type": msg_type,
        "created_at": now,
        "expire_at": expires,
    })
    return jsonify({"uid": uid, "created_at": now, "expire_at": expires}), 201


@app.route("/api/chat/threads/<thread_id>/messages", methods=["GET"])
@login_required
def get_thread_messages(thread_id):
    payload = request.current_user
    _expire_chat_messages_and_sessions()
    limit = request.args.get("limit", 50, type=int)
    before_created_at = (request.args.get("before_created_at") or "").strip()
    before_uid = (request.args.get("before_uid") or "").strip()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    t = conn.execute("SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)", (thread_id, payload["user_uid"], payload["user_uid"])).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    if before_created_at:
        cursor_uid = before_uid or "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"
        rows = conn.execute(
            "SELECT * FROM chat_messages "
            "WHERE thread_uid=? "
            "AND (created_at < ? OR (created_at = ? AND uid < ?)) "
            "ORDER BY created_at DESC, uid DESC "
            "LIMIT ?",
            (thread_id, before_created_at, before_created_at, cursor_uid, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM chat_messages "
            "WHERE thread_uid=? "
            "ORDER BY created_at DESC, uid DESC "
            "LIMIT ?",
            (thread_id, limit),
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in reversed(rows)])


@app.route("/api/chat/threads/<thread_id>/read", methods=["POST"])
@login_required
def mark_thread_read(thread_id):
    payload = request.current_user
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    t = conn.execute("SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)", (thread_id, payload["user_uid"], payload["user_uid"])).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "thread not found"}), 404
    conn.execute(
        "UPDATE chat_messages SET read=1, delivered_at=? WHERE thread_uid=? AND receiver=? AND read=0",
        (now, thread_id, payload["user_uid"]),
    )
    conn.execute(
        "DELETE FROM chat_messages WHERE thread_uid=? AND receiver=? AND delivered_at IS NOT NULL",
        (thread_id, payload["user_uid"]),
    )
    conn.execute("UPDATE match_sessions SET last_activity_at=? WHERE uid=?", (now, t["session_uid"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/chat/threads/<thread_id>/leave", methods=["POST"])
@login_required
def leave_thread(thread_id):
    payload = request.current_user
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if len(reason) < 5:
        return jsonify({"error": "reason must be at least 5 characters"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    _ensure_thread_leaves_table(conn)
    t = conn.execute(
        "SELECT * FROM chat_threads WHERE uid=? AND (user_a=? OR user_b=?)",
        (thread_id, payload["user_uid"], payload["user_uid"]),
    ).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "thread not found"}), 404

    if t["status"] == "open":
        session = conn.execute("SELECT * FROM match_sessions WHERE uid=?", (t["session_uid"],)).fetchone()
        if session:
            side = _session_side_for_user(session, payload["user_uid"])
            if side == "user":
                my_decision_col = "user_decision"
                my_reason_col = "user_reject_reason"
            elif side == "candidate":
                my_decision_col = "candidate_decision"
                my_reason_col = "candidate_reject_reason"
            else:
                my_decision_col = ""
                my_reason_col = ""
            if my_decision_col:
                if (session["candidate_type"] or "") == "room":
                    conn.execute(
                        "UPDATE match_sessions SET last_activity_at=? WHERE uid=?",
                        (now, session["uid"]),
                    )
                else:
                    conn.execute(
                        f"UPDATE match_sessions SET {my_decision_col}='rejected', {my_reason_col}=?, last_activity_at=? WHERE uid=?",
                        (reason, now, session["uid"]),
                    )
        conn.execute(
            "UPDATE chat_threads SET status='closed', closed_reason='rejected', closed_at=? WHERE uid=?",
            (now, thread_id),
        )
        other_uid = t["user_b"] if t["user_a"] == payload["user_uid"] else t["user_a"]
        _record_decision_review(
            conn=conn,
            reviewer=payload["user_uid"],
            reviewee=other_uid,
            session_uid=t["session_uid"],
            decision_type="reject",
            reason=reason,
            created_at=now,
        )
        _broadcast_thread_state(
            conn,
            thread_id,
            "rejected",
            {
                "left_by": payload["user_uid"],
                "rejected_by": payload["user_uid"],
                "reject_reason": reason,
            },
        )
        _close_session_if_no_open_threads(conn, t["session_uid"], now)
    conn.execute(
        "INSERT OR REPLACE INTO chat_thread_leaves (thread_uid, user_uid, left_at) VALUES (?, ?, ?)",
        (thread_id, payload["user_uid"], now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "treated_as": "rejected"})


@app.route("/api/chat/ack", methods=["POST"])
@login_required
def chat_ack():
    # Deprecated: immediate ACK-delete is disabled.
    # Messages are deleted only when /api/chat/threads/{thread_id}/read is called.
    return jsonify({"ok": True})


@app.route("/api/chat/local/threads/<thread_id>/messages", methods=["GET"])
@login_required
def get_local_thread_messages(thread_id):
    payload = request.current_user
    conn = _forlocal_conn()
    row = conn.execute(
        "SELECT messages_json FROM local_chat_snapshots WHERE user_uid=? AND thread_uid=?",
        (payload["user_uid"], thread_id),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"messages": []})
    try:
        messages = json.loads(row["messages_json"] or "[]")
        if not isinstance(messages, list):
            messages = []
    except Exception:
        messages = []
    return jsonify({"messages": messages})


@app.route("/api/chat/local/threads/<thread_id>/messages", methods=["PUT"])
@login_required
def put_local_thread_messages(thread_id):
    payload = request.current_user
    data = request.get_json(force=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        return jsonify({"error": "messages must be list"}), 400
    now = _now()
    conn = _forlocal_conn()
    conn.execute(
        "INSERT INTO local_chat_snapshots (user_uid, thread_uid, messages_json, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_uid, thread_uid) DO UPDATE SET messages_json=excluded.messages_json, updated_at=excluded.updated_at",
        (payload["user_uid"], thread_id, json.dumps(messages, ensure_ascii=False), now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated_at": now})


@app.route("/api/chat/local/threads/<thread_id>/messages", methods=["DELETE"])
@login_required
def delete_local_thread_messages(thread_id):
    payload = request.current_user
    conn = _forlocal_conn()
    conn.execute(
        "DELETE FROM local_chat_snapshots WHERE user_uid=? AND thread_uid=?",
        (payload["user_uid"], thread_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/life-room/current", methods=["GET"])
@login_required
def get_current_life_room():
    payload = request.current_user
    user = db.get_user_by_uid(payload["user_uid"])
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT lr.* FROM life_rooms lr "
        "JOIN life_room_members lm ON lm.life_room_uid=lr.uid "
        "WHERE lm.user_uid=? AND lm.is_active=1 AND lr.status='active' "
        "ORDER BY lr.created_at DESC LIMIT 1",
        (payload["user_uid"],),
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"life_room": None})
    if row["school_id"] and user and user.school_name:
        school_conn = _schools_conn()
        school_conn.row_factory = sqlite3.Row
        school_row = school_conn.execute("SELECT * FROM schools WHERE id=?", (row["school_id"],)).fetchone()
        school_conn.close()
        if school_row:
            phase = _school_matching_phase(school_row)
            if phase == "closed":
                now = _now()
                conn.execute("UPDATE life_rooms SET status='closed', closed_at=?, updated_at=? WHERE uid=?", (now, now, row["uid"]))
                conn.execute("UPDATE life_room_members SET is_active=0 WHERE life_room_uid=?", (row["uid"],))
                conn.execute("DELETE FROM life_room_match_history WHERE life_room_uid=?", (row["uid"],))
                conn.execute("UPDATE life_room_recruit_sessions SET status='closed', closed_at=? WHERE life_room_uid=? AND status='open'", (now, row["uid"]))
                member_rows = conn.execute(
                    "SELECT user_uid FROM life_room_members WHERE life_room_uid=?",
                    (row["uid"],),
                ).fetchall()
                for m in member_rows:
                    conn.execute(
                        "UPDATE profiles SET hall_confirmed_at=NULL WHERE user_uid=?",
                        (m["user_uid"],),
                    )
                conn.commit()
                conn.close()
                return jsonify({"life_room": None, "period_expired": True})
    member_count = conn.execute(
        "SELECT COUNT(*) AS c FROM life_room_members WHERE life_room_uid=? AND is_active=1",
        (row["uid"],),
    ).fetchone()
    target_cap = int(row["target_capacity"] or 2)
    current_count = int(member_count["c"]) if member_count else 0
    is_understaffed = current_count < target_cap
    members = conn.execute(
        "SELECT user_uid, joined_at FROM life_room_members WHERE life_room_uid=? AND is_active=1 ORDER BY joined_at ASC",
        (row["uid"],),
    ).fetchall()
    todos = conn.execute(
        "SELECT * FROM life_room_todos WHERE life_room_uid=? ORDER BY created_at DESC LIMIT 50",
        (row["uid"],),
    ).fetchall()
    events = conn.execute(
        "SELECT * FROM life_room_events WHERE life_room_uid=? ORDER BY start_at ASC LIMIT 100",
        (row["uid"],),
    ).fetchall()
    posts = conn.execute(
        "SELECT * FROM life_room_posts WHERE life_room_uid=? ORDER BY pinned DESC, updated_at DESC LIMIT 50",
        (row["uid"],),
    ).fetchall()
    latest_rule = conn.execute(
        "SELECT * FROM life_room_rules WHERE life_room_uid=? ORDER BY created_at DESC LIMIT 1",
        (row["uid"],),
    ).fetchone()
    presence = conn.execute(
        "SELECT user_uid, status, updated_at FROM life_room_presence WHERE life_room_uid=?",
        (row["uid"],),
    ).fetchall()
    conn.close()
    return jsonify({
        "life_room": dict(row),
        "members": [dict(m) for m in members],
        "todos": [dict(t) for t in todos],
        "events": [dict(e) for e in events],
        "posts": [dict(p) for p in posts],
        "rule": dict(latest_rule) if latest_rule else None,
        "presence": [dict(p) for p in presence],
        "is_understaffed": is_understaffed,
        "current_member_count": current_count,
        "target_capacity": target_cap,
    })


@app.route("/api/life-room/<life_room_uid>/todos", methods=["POST"])
@login_required
def add_life_room_todo(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    assignee_uid = (data.get("assignee_uid") or "").strip() or None
    due_date = (data.get("due_date") or "").strip() or None
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_todos (uid, life_room_uid, assignee_uid, title, due_date, done, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
        (uid, life_room_uid, assignee_uid, title, due_date, payload["user_uid"], now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM life_room_todos WHERE uid=?", (uid,)).fetchone()
    conn.close()
    return jsonify({"todo": dict(row)}), 201


@app.route("/api/life-room/<life_room_uid>/events", methods=["POST"])
@login_required
def create_life_room_event(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    start_at = (data.get("start_at") or "").strip()
    end_at = (data.get("end_at") or "").strip() or None
    view_type = (data.get("view_type") or "month").strip().lower()
    if not title or not start_at:
        return jsonify({"error": "title and start_at are required"}), 400
    if view_type not in ("month", "week"):
        return jsonify({"error": "view_type must be month or week"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_events (uid, life_room_uid, author_uid, title, start_at, end_at, view_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, life_room_uid, payload["user_uid"], title, start_at, end_at, view_type, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM life_room_events WHERE uid=?", (uid,)).fetchone()
    conn.close()
    return jsonify({"event": dict(row)}), 201


@app.route("/api/life-room/<life_room_uid>/todos/<todo_uid>/toggle", methods=["POST"])
@login_required
def toggle_life_room_todo(life_room_uid: str, todo_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    row = conn.execute("SELECT done FROM life_room_todos WHERE uid=? AND life_room_uid=?", (todo_uid, life_room_uid)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "todo not found"}), 404
    next_done = 0 if int(row["done"] or 0) == 1 else 1
    conn.execute("UPDATE life_room_todos SET done=? WHERE uid=?", (next_done, todo_uid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "done": bool(next_done)})


@app.route("/api/life-room/<life_room_uid>/rules", methods=["POST"])
@login_required
def update_life_room_rules(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body is required"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    if int(room["rules_change_count"] or 0) >= 3:
        conn.close()
        return jsonify({"error": "rules change limit exceeded"}), 400
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_rules (uid, life_room_uid, body, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, life_room_uid, body, payload["user_uid"], now),
    )
    conn.execute(
        "UPDATE life_rooms SET rules_change_count=rules_change_count+1, updated_at=? WHERE uid=?",
        (now, life_room_uid),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "rule_uid": uid})


@app.route("/api/life-room/<life_room_uid>/presence", methods=["POST"])
@login_required
def update_life_room_presence(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    status = (data.get("status") or "").strip().lower()
    if status not in ("in", "out"):
        return jsonify({"error": "status must be in or out"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    conn.execute(
        "INSERT OR REPLACE INTO life_room_presence (uid, life_room_uid, user_uid, status, updated_at) VALUES (?, ?, ?, ?, ?)",
        (generate_uid(), life_room_uid, payload["user_uid"], status, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/life-room/<life_room_uid>/posts", methods=["POST"])
@login_required
def create_life_room_post(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    pinned = bool(data.get("pinned", False))
    if not title or not body:
        return jsonify({"error": "title and body are required"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    if pinned:
        pin_count = conn.execute(
            "SELECT COUNT(*) AS c FROM life_room_posts WHERE life_room_uid=? AND author_uid=? AND pinned=1",
            (life_room_uid, payload["user_uid"]),
        ).fetchone()["c"]
        if int(pin_count or 0) >= 10:
            conn.close()
            return jsonify({"error": "pin limit exceeded"}), 400
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_posts (uid, life_room_uid, author_uid, title, body, pinned, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, life_room_uid, payload["user_uid"], title, body, 1 if pinned else 0, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM life_room_posts WHERE uid=?", (uid,)).fetchone()
    conn.close()
    return jsonify({"post": dict(row)}), 201


@app.route("/api/life-room/<life_room_uid>/fill-policy", methods=["POST"])
@login_required
def update_life_room_fill_policy(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    period = (data.get("period") or "").strip().lower()
    strategy = (data.get("strategy") or "").strip().lower()
    if period not in ("preliminary", "main"):
        return jsonify({"error": "period must be preliminary or main"}), 400
    if strategy not in ("continue", "random"):
        return jsonify({"error": "strategy must be continue or random"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    count_col = "pre_policy_change_count" if period == "preliminary" else "apply_policy_change_count"
    if int(room[count_col] or 0) >= 1:
        conn.close()
        return jsonify({"error": "policy change limit exceeded"}), 400
    conn.execute(
        f"UPDATE life_rooms SET fill_strategy=?, {count_col}={count_col}+1, updated_at=? WHERE uid=?",
        (strategy, now, life_room_uid),
    )
    conn.execute(
        "INSERT INTO life_room_fill_policy (uid, life_room_uid, period, strategy, changed_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (generate_uid(), life_room_uid, period, strategy, payload["user_uid"], now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "strategy": strategy})


@app.route("/api/life-room/<life_room_uid>/match-history", methods=["GET"])
@login_required
def list_life_room_match_history(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    rows = conn.execute(
        "SELECT * FROM life_room_match_history WHERE life_room_uid=? ORDER BY created_at DESC",
        (life_room_uid,),
    ).fetchall()
    conn.close()
    return jsonify({"history": [dict(r) for r in rows]})


@app.route("/api/life-room/<life_room_uid>/match-history", methods=["POST"])
@login_required
def create_life_room_match_history(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    matched_with_type = (data.get("matched_with_type") or "").strip()
    matched_with_uid = (data.get("matched_with_uid") or "").strip()
    status = (data.get("status") or "active").strip()
    if not matched_with_type or not matched_with_uid:
        return jsonify({"error": "matched_with_type and matched_with_uid are required"}), 400
    now = _now()
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_match_history (uid, life_room_uid, matched_with_type, matched_with_uid, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, life_room_uid, matched_with_type, matched_with_uid, status, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"uid": uid, "ok": True}), 201


@app.route("/api/life-room/<life_room_uid>/match-history/<history_uid>", methods=["DELETE"])
@login_required
def delete_life_room_match_history(life_room_uid: str, history_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    cur = conn.execute("DELETE FROM life_room_match_history WHERE uid=? AND life_room_uid=?", (history_uid, life_room_uid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "history not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/life-room/<life_room_uid>/recruit-sessions", methods=["GET"])
@login_required
def list_recruit_sessions(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    rows = conn.execute(
        "SELECT * FROM life_room_recruit_sessions WHERE life_room_uid=? ORDER BY created_at DESC",
        (life_room_uid,),
    ).fetchall()
    conn.close()
    return jsonify({"sessions": [dict(r) for r in rows]})


@app.route("/api/life-room/<life_room_uid>/recruit-sessions", methods=["POST"])
@login_required
def create_recruit_session(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    school = _get_school_row_by_id(int(room["school_id"] or 0))
    if _school_matching_phase(school) != "main":
        conn.close()
        return jsonify({"error": "recruit session can be created only during roommate apply period"}), 403
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    if room["host_uid"] != payload["user_uid"]:
        conn.close()
        return jsonify({"error": "only host can create recruit session"}), 403
    open_session = conn.execute(
        "SELECT uid FROM life_room_recruit_sessions WHERE life_room_uid=? AND status='open'",
        (life_room_uid,),
    ).fetchone()
    if open_session:
        conn.close()
        return jsonify({"error": "recruit session already open"}), 409
    now = _now()
    uid = generate_uid()
    conn.execute(
        "INSERT INTO life_room_recruit_sessions (uid, life_room_uid, status, created_at) VALUES (?, ?, 'open', ?)",
        (uid, life_room_uid, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"uid": uid, "ok": True}), 201


@app.route("/api/life-room/<life_room_uid>/recruit-sessions/<session_uid>", methods=["PATCH"])
@login_required
def update_recruit_session(life_room_uid: str, session_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    new_status = (data.get("status") or "").strip()
    if new_status not in ("open", "closed", "cancelled"):
        return jsonify({"error": "status must be open, closed, or cancelled"}), 400
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    now = _now()
    cur = conn.execute(
        "UPDATE life_room_recruit_sessions SET status=?, closed_at=? WHERE uid=? AND life_room_uid=?",
        (new_status, now if new_status != "open" else None, session_uid, life_room_uid),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "session not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/life-room/<life_room_uid>/hall-confirm", methods=["POST"])
@login_required
def confirm_life_room_hall(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    room_type_id = data.get("room_type_id")
    if not room_type_id:
        return jsonify({"error": "room_type_id is required"}), 400
    room_type_id = int(room_type_id)
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    _ensure_life_room_hall_votes_table(conn)
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    now = _now()
    room_meta = _room_type_meta(room_type_id, int(room["school_id"] or 0))
    if not room_meta:
        conn.close()
        return jsonify({"error": "invalid room_type_id for this school"}), 400
    if int(room_meta["capacity"] or 0) != int(room["target_capacity"] or 0):
        conn.close()
        return jsonify({"error": "room_type capacity must match life room target capacity"}), 400

    conn.execute(
        "INSERT INTO life_room_hall_votes (life_room_uid, user_uid, room_type_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(life_room_uid, user_uid) DO UPDATE SET room_type_id=excluded.room_type_id, updated_at=excluded.updated_at",
        (life_room_uid, payload["user_uid"], room_type_id, now, now),
    )
    profile = db.get_profile_by_user_uid(payload["user_uid"])
    if not profile:
        conn.close()
        return jsonify({"error": "profile not found"}), 404
    conn.execute(
        "UPDATE profiles SET fixed_room_type_id=?, fixed_interest_room_type_id=?, hall_confirmed_at=? WHERE user_uid=?",
        (room_type_id, room_type_id, now, payload["user_uid"]),
    )

    all_members_confirmed = False
    all_same_hall = False
    fixed_room_type_id = None
    member_rows = conn.execute(
        "SELECT user_uid FROM life_room_members WHERE life_room_uid=? AND is_active=1",
        (life_room_uid,),
    ).fetchall()
    active_member_uids = [m["user_uid"] for m in member_rows]
    if active_member_uids:
        placeholders = ",".join(["?"] * len(active_member_uids))
        vote_rows = conn.execute(
            f"SELECT user_uid, room_type_id FROM life_room_hall_votes "
            f"WHERE life_room_uid=? AND user_uid IN ({placeholders})",
            (life_room_uid, *active_member_uids),
        ).fetchall()
        if len(vote_rows) == len(active_member_uids):
            all_members_confirmed = True
            dorm_ids = set()
            room_type_ids = set()
            for vr in vote_rows:
                meta = _room_type_meta(int(vr["room_type_id"]), int(room["school_id"] or 0))
                if not meta:
                    all_members_confirmed = False
                    break
                if int(meta["capacity"] or 0) != int(room["target_capacity"] or 0):
                    all_members_confirmed = False
                    break
                dorm_ids.add(int(meta["dorm_id"]))
                room_type_ids.add(int(vr["room_type_id"]))
            all_same_hall = all_members_confirmed and len(dorm_ids) == 1
            if all_same_hall and len(room_type_ids) == 1:
                fixed_room_type_id = next(iter(room_type_ids))

    if all_members_confirmed and all_same_hall:
        conn.execute(
            "UPDATE life_rooms SET fixed_hall=1, room_type_id=?, updated_at=? WHERE uid=?",
            (fixed_room_type_id, now, life_room_uid),
        )
    else:
        conn.execute(
            "UPDATE life_rooms SET fixed_hall=0, room_type_id=NULL, updated_at=? WHERE uid=?",
            (now, life_room_uid),
        )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "all_members_confirmed": all_members_confirmed,
        "all_same_hall": all_same_hall,
        "fixed_hall": all_members_confirmed and all_same_hall,
    })


@app.route("/api/life-room/<life_room_uid>/group-chat", methods=["POST"])
@login_required
def send_life_room_group_message(life_room_uid: str):
    payload = request.current_user
    data = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    member_rows = conn.execute(
        "SELECT user_uid FROM life_room_members WHERE life_room_uid=? AND is_active=1 AND user_uid<>?",
        (life_room_uid, payload["user_uid"]),
    ).fetchall()
    now = _now()
    msg_uid = generate_uid()
    conn.execute(
        "INSERT INTO chat_messages (uid, session_uid, thread_uid, sender, receiver, content, type, read, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (msg_uid, life_room_uid, life_room_uid, payload["user_uid"], "group", content, "group", 0, now),
    )
    conn.commit()
    for m in member_rows:
        broadcast_message(m["user_uid"], "life_room_group_message", {
            "life_room_uid": life_room_uid,
            "sender_uid": payload["user_uid"],
            "content": content,
            "created_at": now,
        })
    conn.close()
    return jsonify({"uid": msg_uid, "ok": True}), 201


@app.route("/api/life-room/<life_room_uid>/group-chat", methods=["GET"])
@login_required
def get_life_room_group_messages(life_room_uid: str):
    payload = request.current_user
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(200, int(limit_raw)))
    except Exception:
        limit = 50
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_uid=? AND type='group' ORDER BY created_at ASC LIMIT ?",
        (life_room_uid, limit),
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})


def _compute_fill_survey(life_room_uid: str) -> dict:
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member_rows = conn.execute(
        "SELECT user_uid FROM life_room_members WHERE life_room_uid=? AND is_active=1",
        (life_room_uid,),
    ).fetchall()
    conn.close()
    if not member_rows:
        return {}
    survey_fields = [
        "bedtime", "wake_time", "sleep_habit", "sleep_sensitivity", "alarm_strength", "sleep_light",
        "snoring", "noise_sensitivity", "gaming_hours_per_week", "speaker_use", "exercise",
        "shower_duration", "shower_time", "shower_cycle", "cleaning_cycle", "ventilation",
        "hairdryer_in_bathroom", "toilet_paper_share", "indoor_eating", "smoking", "temperature_pref",
        "indoor_call", "bug_handling", "laundry_cycle", "drying_rack", "fridge_use", "study_in_room",
        "perfume", "indoor_scent_sensitivity", "alcohol_tolerance", "alcohol_frequency", "drunk_habit",
        "desired_intimacy", "meal_together", "exercise_together", "friend_invite", "home_visit_cycle",
    ]
    sums = {}
    counts = {}
    for m in member_rows:
        p = db.get_profile_by_user_uid(m["user_uid"])
        if not p:
            continue
        for f in survey_fields:
            v = getattr(p, f, None)
            if v is not None:
                try:
                    fv = float(v)
                    sums[f] = sums.get(f, 0.0) + fv
                    counts[f] = counts.get(f, 0) + 1
                except (ValueError, TypeError):
                    pass
    result = {}
    for f in survey_fields:
        if f in counts and counts[f] > 0:
            result[f] = round(sums[f] / counts[f])
    return result


@app.route("/api/life-room/<life_room_uid>/fill-survey", methods=["GET"])
@login_required
def get_fill_survey(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    conn.close()
    survey = _compute_fill_survey(life_room_uid)
    return jsonify({"survey": survey})


@app.route("/api/life-room/<life_room_uid>/status", methods=["GET"])
@login_required
def get_life_room_status(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    member_count = conn.execute(
        "SELECT COUNT(*) AS c FROM life_room_members WHERE life_room_uid=? AND is_active=1",
        (life_room_uid,),
    ).fetchone()
    target_cap = int(room["target_capacity"] or 2)
    current_count = int(member_count["c"]) if member_count else 0
    is_understaffed = current_count < target_cap
    all_hall_confirmed = bool(int(room["fixed_hall"] or 0))
    school = _get_school_row_by_id(int(room["school_id"] or 0))
    can_create_recruit_session = _school_matching_phase(school) == "main"
    recruit_session = conn.execute(
        "SELECT uid, status, created_at FROM life_room_recruit_sessions WHERE life_room_uid=? AND status='open' LIMIT 1",
        (life_room_uid,),
    ).fetchone()
    conn.close()
    return jsonify({
        "uid": life_room_uid,
        "status": room["status"],
        "target_capacity": target_cap,
        "current_member_count": current_count,
        "is_understaffed": is_understaffed,
        "fill_strategy": room["fill_strategy"],
        "fixed_hall": all_hall_confirmed,
        "can_create_recruit_session": can_create_recruit_session,
        "open_recruit_session": dict(recruit_session) if recruit_session else None,
    })


@app.route("/api/life-room/<life_room_uid>/auto-close", methods=["POST"])
@login_required
def close_life_room_period(life_room_uid: str):
    payload = request.current_user
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    room = conn.execute("SELECT * FROM life_rooms WHERE uid=?", (life_room_uid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "life room not found"}), 404
    member = conn.execute(
        "SELECT 1 FROM life_room_members WHERE life_room_uid=? AND user_uid=? AND is_active=1",
        (life_room_uid, payload["user_uid"]),
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    now = _now()
    conn.execute("UPDATE life_rooms SET status='closed', closed_at=?, updated_at=? WHERE uid=?", (now, now, life_room_uid))
    conn.execute("UPDATE life_room_members SET is_active=0 WHERE life_room_uid=?", (life_room_uid,))
    conn.execute("DELETE FROM life_room_match_history WHERE life_room_uid=?", (life_room_uid,))
    conn.execute("UPDATE life_room_recruit_sessions SET status='closed', closed_at=? WHERE life_room_uid=? AND status='open'", (now, life_room_uid))
    member_rows = conn.execute(
        "SELECT user_uid FROM life_room_members WHERE life_room_uid=?",
        (life_room_uid,),
    ).fetchall()
    for m in member_rows:
        conn.execute(
            "UPDATE profiles SET hall_confirmed_at=NULL WHERE user_uid=?",
            (m["user_uid"],),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ??? Reviews ?????????????????????????????????????????????????????????????

@app.route("/api/reviews", methods=["POST"])
@login_required
def create_review():
    payload = request.current_user
    data = request.get_json(force=True)
    reviewee = data.get("reviewee", "")
    rating = data.get("rating")
    body = data.get("body", "").strip()
    if not reviewee or rating is None:
        return jsonify({"error": "reviewee? rating? ?꾩닔?낅땲??"}), 400

    uid = generate_uid()
    now = _now()
    conn = _app_conn()
    conn.execute(
        "INSERT INTO reviews (uid, reviewer, reviewee, rating, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, payload["user_uid"], reviewee, rating, body, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"uid": uid}), 201


@app.route("/api/reviews/<reviewee>", methods=["GET"])
@login_required
def list_reviews(reviewee):
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reviews WHERE reviewee=? ORDER BY created_at DESC",
        (reviewee,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ??? Stats ???????????????????????????????????????????????????????????????

@app.route("/api/stats", methods=["GET"])
def stats():
    conn = _app_conn()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    conn.close()
    return jsonify({"users": user_count, "profiles": profile_count})


# ??? Init ????????????????????????????????????????????????????????????????

if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
