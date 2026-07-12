"""Dummy dataset generator for Roomantic.

Creates users + profiles with 8 persona buckets (default 100 each),
using existing signup metadata distribution as baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import string
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import db
from auth import hash_password
from models import RoommateProfile

PERSONAS_8 = [
    "학습집중형",
    "섬세감성형",
    "야행성게이머형",
    "FM관리형",
    "생존형",
    "공동체형",
    "생활분리형",
    "수면민감형",
]

HALLS = ["자유관", "미래관", "진리관", "정의관"]

KOREAN_LAST_NAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권",
    "황", "안", "송", "류", "홍", "전", "고", "문", "양", "손", "배", "백", "허", "유", "남",
]

KOREAN_SYLLABLES = [
    "민", "서", "지", "하", "도", "윤", "준", "현", "우", "시", "연", "아", "은", "수", "태",
    "건", "주", "소", "채", "가", "유", "다", "재", "호", "진", "나", "린", "원", "영", "훈",
    "경", "빈", "규", "혁", "성", "빛", "율", "온", "환", "희", "단", "별", "라", "림", "찬",
    "솔", "하", "람", "결", "담", "선", "보", "미", "슬", "록", "원", "겸", "담", "후", "태",
]

DEFAULT_PASSWORD = "111111"

HANGUL_KEYBOARD_MAP = {
    "ㄱ": "r", "ㄲ": "R", "ㄴ": "s", "ㄷ": "e", "ㄸ": "E", "ㄹ": "f", "ㅁ": "a", "ㅂ": "q",
    "ㅃ": "Q", "ㅅ": "t", "ㅆ": "T", "ㅇ": "d", "ㅈ": "w", "ㅉ": "W", "ㅊ": "c", "ㅋ": "z",
    "ㅌ": "x", "ㅍ": "v", "ㅎ": "g", "ㅏ": "k", "ㅐ": "o", "ㅑ": "i", "ㅒ": "O", "ㅓ": "j",
    "ㅔ": "p", "ㅕ": "u", "ㅖ": "P", "ㅗ": "h", "ㅘ": "hk", "ㅙ": "ho", "ㅚ": "hl", "ㅛ": "y",
    "ㅜ": "n", "ㅝ": "nj", "ㅞ": "np", "ㅟ": "nl", "ㅠ": "b", "ㅡ": "m", "ㅢ": "ml", "ㅣ": "l",
}
CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
JONG_SPLIT = {
    "ㄳ": ("ㄱ", "ㅅ"), "ㄵ": ("ㄴ", "ㅈ"), "ㄶ": ("ㄴ", "ㅎ"), "ㄺ": ("ㄹ", "ㄱ"),
    "ㄻ": ("ㄹ", "ㅁ"), "ㄼ": ("ㄹ", "ㅂ"), "ㄽ": ("ㄹ", "ㅅ"), "ㄾ": ("ㄹ", "ㅌ"),
    "ㄿ": ("ㄹ", "ㅍ"), "ㅀ": ("ㄹ", "ㅎ"), "ㅄ": ("ㅂ", "ㅅ"),
}


@dataclass
class ExistingMeta:
    schools: list[str]
    colleges: list[str]
    departments: list[str]
    genders: list[str]
    birth_years: list[int]
    base_profiles: list[dict[str, Any]]
    college_dept_pairs: list[tuple[str, str]] = None


def _read_existing_meta(db_path: str) -> ExistingMeta:
    # 1. Fetch existing data from schools.db
    schools_from_db = []
    college_dept_pairs = []
    if os.path.exists(db.SCHOOLS_DB_PATH):
        try:
            s_conn = sqlite3.connect(db.SCHOOLS_DB_PATH)
            s_conn.row_factory = sqlite3.Row
            schools_from_db = [row["name"] for row in s_conn.execute("SELECT name FROM schools").fetchall()]
            pairs = s_conn.execute(
                "SELECT c.name as college, d.name as dept "
                "FROM departments d "
                "JOIN colleges c ON d.college_id = c.id"
            ).fetchall()
            college_dept_pairs = [(row["college"], row["dept"]) for row in pairs]
            s_conn.close()
        except Exception:
            pass

    default_pairs = [
        ("공과대학", "기계공학과"),
        ("공과대학", "전기전자과"),
        ("공과대학", "컴퓨터공학과"),
        ("공과대학", "화학공학과"),
        ("인문대학", "국어국문과"),
        ("인문대학", "영어영문과"),
        ("인문대학", "사학과"),
        ("인문대학", "철학과"),
        ("사회과학대학", "정치외교"),
        ("사회과학대학", "심리학과"),
        ("사회과학대학", "사회학과"),
        ("사회과학대학", "미디어학과"),
        ("자연과학대학", "수학과"),
        ("자연과학대학", "물리학과"),
        ("자연과학대학", "화학과"),
        ("자연과학대학", "생명과학과"),
        ("경영대학", "경영학과"),
        ("경영대학", "회계학과"),
        ("경영대학", "국제경영"),
        ("예술대학", "시각디자인"),
        ("예술대학", "패션디자인"),
        ("예술대학", "회화과"),
        ("체육대학", "체육학과"),
        ("체육대학", "스포츠과학과"),
        ("음악대학", "성악과"),
        ("음악대학", "피아노과"),
        ("음악대학", "작곡과"),
    ]

    if not college_dept_pairs:
        college_dept_pairs = default_pairs

    if not os.path.exists(db_path):
        return ExistingMeta(
            schools=schools_from_db or ["고려대학교"],
            colleges=[p[0] for p in college_dept_pairs],
            departments=[p[1] for p in college_dept_pairs],
            genders=[],
            birth_years=[],
            base_profiles=[],
            college_dept_pairs=college_dept_pairs
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT * FROM users").fetchall()
    profiles = conn.execute("SELECT * FROM profiles").fetchall()
    conn.close()

    schools = [u["school_name"] for u in users if (u["school_name"] or "").strip()]
    colleges = [u["college"] for u in users if (u["college"] or "").strip()]
    departments = [u["department"] for u in users if (u["department"] or "").strip()]
    genders = [u["gender"] for u in users if (u["gender"] or "").strip()]
    birth_years = [int(u["birth_year"]) for u in users if u["birth_year"] is not None]

    if not schools:
        schools = schools_from_db or ["고려대학교"]

    return ExistingMeta(
        schools=schools,
        colleges=colleges or [p[0] for p in college_dept_pairs],
        departments=departments or [p[1] for p in college_dept_pairs],
        genders=genders,
        birth_years=birth_years,
        base_profiles=[dict(r) for r in profiles],
        college_dept_pairs=college_dept_pairs,
    )


def _weighted_pick(values: list[Any], fallback: Any) -> Any:
    if not values:
        return fallback
    return random.choice(values)


def _unique_name(used: set[str]) -> str:
    for _ in range(4000):
        name = f"{random.choice(KOREAN_LAST_NAMES)}{random.choice(KOREAN_SYLLABLES)}{random.choice(KOREAN_SYLLABLES)}"
        if name not in used:
            used.add(name)
            return name
    while True:
        name = (
            f"{random.choice(KOREAN_LAST_NAMES)}"
            f"{random.choice(KOREAN_SYLLABLES)}{random.choice(KOREAN_SYLLABLES)}"
            f"{random.choice(string.ascii_uppercase)}"
        )
        if name not in used:
            used.add(name)
            return name


def _hangul_to_keyboard(text: str) -> str:
    """Return the characters produced by typing a Korean name with IME off."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            offset = code - 0xAC00
            cho = CHO[offset // 588]
            jung = JUNG[(offset % 588) // 28]
            jong = JONG[offset % 28]
            jamos = [cho, jung]
            if jong:
                jamos.extend(JONG_SPLIT.get(jong, (jong,)))
            out.extend(HANGUL_KEYBOARD_MAP.get(j, "") for j in jamos)
        else:
            out.append(ch if ch.isascii() and ch.isalnum() else "")
    return "".join(out)


def _login_id_from_name(name: str, used: set[str]) -> str:
    base = _hangul_to_keyboard(name).lower() or "dummy"
    login_id = base
    suffix = 2
    while login_id in used:
        login_id = f"{base}{suffix}"
        suffix += 1
    used.add(login_id)
    return login_id


def _room_type_catalog() -> dict[str, list[dict[str, Any]]]:
    if not os.path.exists(db.SCHOOLS_DB_PATH):
        db.init_schools_db()
    conn = sqlite3.connect(db.SCHOOLS_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT s.name AS school_name, rt.id, rt.capacity, rt.is_enabled, "
        "d.name AS dorm_name, d.gender AS dorm_gender "
        "FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id "
        "JOIN schools s ON s.id=d.school_id "
        "WHERE rt.is_enabled=1 "
        "ORDER BY s.id, d.id, rt.capacity"
    ).fetchall()
    conn.close()
    catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        catalog[row["school_name"]].append(dict(row))
    return catalog


def _select_room_type_policy(
    catalog: dict[str, list[dict[str, Any]]],
    school_name: str,
    gender: str,
    phase: str,
) -> tuple[list[int], int, int, str]:
    school_types = catalog.get(school_name) or next(iter(catalog.values()), [])
    visible = [
        rt for rt in school_types
        if rt.get("dorm_gender") in ("coed", gender) and int(rt.get("is_enabled") or 0) == 1
    ]
    if not visible:
        visible = [rt for rt in school_types if int(rt.get("is_enabled") or 0) == 1]
    if not visible:
        return [], 0, 2, ""

    capacity = random.choice([2, 3, 4])
    same_capacity = [rt for rt in visible if int(rt.get("capacity") or 0) == capacity] or visible
    if phase == "main":
        chosen = random.choice(same_capacity)
        return [], int(chosen["id"]), int(chosen["capacity"]), str(chosen.get("dorm_name") or "")

    max_selectable = min(2, len(same_capacity))
    count = random.randint(1, max_selectable)
    chosen_rows = random.sample(same_capacity, k=count)
    chosen_ids = sorted({int(rt["id"]) for rt in chosen_rows})
    first = chosen_rows[0]
    return chosen_ids, 0, int(first["capacity"]), str(first.get("dorm_name") or "")


def _persona_scores(p: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}

    s1 = 0
    if p["study_in_room"] == 1:
        s1 += 3
    if p["noise_sensitivity"] >= 4:
        s1 += 2
    if p["speaker_use"] == 0:
        s1 += 1
    if p["gaming_hours_per_week"] <= 5:
        s1 += 1
    if p["bedtime"] >= 22 or p["bedtime"] <= 1:
        s1 += 1
    if p["friend_invite"] == 0:
        s1 += 1
    if p["desired_intimacy"] <= 2:
        s1 += 1
    scores["학습집중형"] = (s1 / 10.0) * 100

    s2 = 0
    if p["indoor_scent_sensitivity"] >= 4:
        s2 += 2
    if p["indoor_eating"] == 1:
        s2 += 1
    if p["fridge_use"] == 1:
        s2 += 1
    if p["toilet_paper_share"] == 1:
        s2 += 1
    if p["ventilation"] >= 3:
        s2 += 1
    if p["temperature_pref"] != 3:
        s2 += 1
    if p["cleaning_cycle"] <= 7:
        s2 += 1
    scores["섬세감성형"] = (s2 / 8.0) * 100

    s3 = 0
    if p["gaming_hours_per_week"] >= 15:
        s3 += 3
    if 1 <= p["bedtime"] <= 5:
        s3 += 2
    if p["alarm_strength"] >= 4:
        s3 += 1
    if p["speaker_use"] == 1:
        s3 += 1
    if p["home_visit_cycle"] <= 1:
        s3 += 1
    scores["야행성게이머형"] = (s3 / 8.0) * 100

    s4 = 0
    if p["cleaning_cycle"] <= 3:
        s4 += 2
    if p["shower_cycle"] <= 1:
        s4 += 2
    if p["laundry_cycle"] <= 3:
        s4 += 1
    if p["hairdryer_in_bathroom"] == 1:
        s4 += 1
    if p["desired_intimacy"] >= 3:
        s4 += 1
    if p["shower_duration"] <= 15:
        s4 += 1
    scores["FM관리형"] = (s4 / 8.0) * 100

    s5 = 0
    if p["cleaning_cycle"] >= 14:
        s5 += 2
    if p["shower_cycle"] >= 3:
        s5 += 2
    if p["fridge_use"] == 0:
        s5 += 1
    if p["desired_intimacy"] <= 2:
        s5 += 1
    if p["study_in_room"] == 0:
        s5 += 1
    if p["noise_sensitivity"] <= 2:
        s5 += 1
    scores["생존형"] = (s5 / 8.0) * 100

    s6 = 0
    if p["desired_intimacy"] >= 4:
        s6 += 2
    if p["meal_together"] >= 2:
        s6 += 1
    if p["exercise_together"] >= 2:
        s6 += 1
    if p["friend_invite"] == 2:
        s6 += 2
    elif p["friend_invite"] == 1:
        s6 += 1
    scores["공동체형"] = (s6 / 6.0) * 100

    s7 = 0
    if p["desired_intimacy"] <= 2:
        s7 += 2
    if p["toilet_paper_share"] == 0:
        s7 += 1
    if p["indoor_call"] == 0:
        s7 += 1
    if p["friend_invite"] == 0:
        s7 += 1
    if p["meal_together"] <= 1:
        s7 += 1
    scores["생활분리형"] = (s7 / 6.0) * 100

    s8 = 0
    if p["sleep_sensitivity"] >= 4:
        s8 += 3
    if p["sleep_light"] == 1:
        s8 += 1
    if p["bedtime"] >= 22 or p["bedtime"] <= 1:
        s8 += 1
    if p["snoring"] == 0:
        s8 += 1
    if p["noise_sensitivity"] >= 4:
        s8 += 1
    scores["수면민감형"] = (s8 / 7.0) * 100

    return scores


def _top_persona(p: dict[str, Any]) -> str:
    scores = _persona_scores(p)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[0][0]


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def _base_profile_from_existing(existing: ExistingMeta) -> dict[str, Any]:
    if existing.base_profiles:
        row = random.choice(existing.base_profiles)
        p = dict(row)
        for k in ("non_negotiable_items", "non_negotiable_weights", "hope_halls"):
            if isinstance(p.get(k), str):
                try:
                    p[k] = json.loads(p[k])
                except Exception:
                    p[k] = []
        return p

    defaults = RoommateProfile()
    return defaults.__dict__.copy()


def _apply_persona_blueprint(p: dict[str, Any], persona: str) -> None:
    if persona == "학습집중형":
        p.update(
            study_in_room=1,
            noise_sensitivity=5,
            speaker_use=0,
            gaming_hours_per_week=5,
            bedtime=random.choice([22, 23, 0, 1]),
            friend_invite=0,
            desired_intimacy=random.choice([1, 2]),
        )
    elif persona == "섬세감성형":
        p.update(
            indoor_scent_sensitivity=5,
            indoor_eating=1,
            fridge_use=1,
            toilet_paper_share=1,
            ventilation=random.choice([3.0, 4.0, 5.0]),
            temperature_pref=random.choice([1, 2, 4, 5]),
            cleaning_cycle=random.choice([1, 3, 7]),
        )
    elif persona == "야행성게이머형":
        p.update(
            gaming_hours_per_week=random.choice([15, 20, 25, 30]),
            bedtime=random.choice([1, 2, 3, 4, 5]),
            alarm_strength=random.choice([4, 5]),
            speaker_use=1,
            home_visit_cycle=1,
        )
    elif persona == "FM관리형":
        p.update(
            cleaning_cycle=random.choice([1, 3]),
            shower_cycle=random.choice([0, 1]),
            laundry_cycle=random.choice([1, 3]),
            hairdryer_in_bathroom=1,
            desired_intimacy=random.choice([3, 4, 5]),
            shower_duration=random.choice([10, 15]),
        )
    elif persona == "생존형":
        p.update(
            cleaning_cycle=random.choice([14, 30]),
            shower_cycle=random.choice([3, 4]),
            fridge_use=0,
            desired_intimacy=random.choice([1, 2]),
            study_in_room=0,
            noise_sensitivity=random.choice([1, 2]),
        )
    elif persona == "공동체형":
        p.update(
            desired_intimacy=random.choice([4, 5]),
            meal_together=random.choice([2, 3]),
            exercise_together=random.choice([2, 3]),
            friend_invite=2,
        )
    elif persona == "생활분리형":
        p.update(
            desired_intimacy=random.choice([1, 2]),
            toilet_paper_share=0,
            indoor_call=0,
            friend_invite=0,
            meal_together=1,
        )
    elif persona == "수면민감형":
        p.update(
            sleep_sensitivity=random.choice([4, 5]),
            sleep_light=1,
            bedtime=random.choice([22, 23, 0, 1]),
            snoring=0,
            noise_sensitivity=random.choice([4, 5]),
        )


def _jitter_profile(p: dict[str, Any]) -> None:
    # Small perturbation so each record is close but not identical.
    p["birth_year"] = _clamp(int(p.get("birth_year", 2004)) + random.choice([-1, 0, 0, 1]), 1997, 2008)
    p["wake_time"] = (int(p.get("wake_time", 8)) + random.choice([-1, 0, 1])) % 24
    p["shower_time"] = (int(p.get("shower_time", 22)) + random.choice([-1, 0, 1])) % 24
    p["temperature_pref"] = _clamp(int(p.get("temperature_pref", 3)) + random.choice([-1, 0, 1]), 1, 5)
    p["bug_handling"] = _clamp(int(p.get("bug_handling", 3)) + random.choice([-1, 0, 1]), 1, 5)
    p["sleep_sensitivity"] = _clamp(int(p.get("sleep_sensitivity", 3)) + random.choice([-1, 0, 1]), 1, 5)
    p["alarm_strength"] = _clamp(int(p.get("alarm_strength", 3)) + random.choice([-1, 0, 1]), 1, 5)


def _normalize_profile_for_insert(
    p: dict[str, Any],
    user_uid: str,
    name: str,
    student_id: str,
    persona: str,
    school_name: str,
    gender: str,
    room_type_catalog: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    profile = RoommateProfile()
    out = profile.__dict__.copy()
    out.update(p)
    out["uid"] = str(uuid.uuid4())
    out["user_uid"] = user_uid
    out["name"] = name
    out["student_id"] = student_id
    out["persona"] = persona

    out["matching_phase"] = random.choice(["preliminary", "preliminary", "preliminary", "main"])
    if out["matching_phase"] == "main":
        hall = random.choice(HALLS)
        out["accepted_hall"] = hall
        out["hope_halls"] = []
        out["dormitory_hall"] = hall
    else:
        halls = random.sample(HALLS, k=random.choice([1, 2]))
        out["hope_halls"] = halls
        out["accepted_hall"] = ""
        out["dormitory_hall"] = halls[0]
        if not out["hope_halls"]:
            out["hope_halls"] = [random.choice(HALLS)]

    interest_ids, fixed_interest_id, capacity, policy_hall = _select_room_type_policy(
        room_type_catalog,
        school_name,
        gender,
        out["matching_phase"],
    )
    # Safety net: when catalog lookup fails, still keep profile match-pool eligible.
    if not interest_ids and not fixed_interest_id:
        fallback_rows = []
        for rows in room_type_catalog.values():
            fallback_rows.extend(rows)
        fallback_visible = [
            rt for rt in fallback_rows
            if rt.get("dorm_gender") in ("coed", gender) and int(rt.get("is_enabled") or 0) == 1
        ] or [rt for rt in fallback_rows if int(rt.get("is_enabled") or 0) == 1]
        if fallback_visible:
            fallback = random.choice(fallback_visible)
            if out["matching_phase"] == "main":
                fixed_interest_id = int(fallback["id"])
            else:
                interest_ids = [int(fallback["id"])]
            capacity = int(fallback.get("capacity") or capacity or 2)
            policy_hall = str(fallback.get("dorm_name") or policy_hall or "")
    if policy_hall:
        if out["matching_phase"] == "main":
            out["accepted_hall"] = policy_hall
            out["hope_halls"] = []
        else:
            out["hope_halls"] = list(dict.fromkeys([policy_hall] + list(out.get("hope_halls") or [])))[:2]
        out["dormitory_hall"] = policy_hall

    out["room_capacity"] = capacity
    if fixed_interest_id:
        out["fixed_interest_room_type_id"] = fixed_interest_id
        out["interest_room_type_ids"] = []
        out["fixed_room_type_id"] = fixed_interest_id
        out["preferred_room_type_ids"] = []
    else:
        out["interest_room_type_ids"] = interest_ids
        out["fixed_interest_room_type_id"] = 0
        out["preferred_room_type_ids"] = list(interest_ids)
        out["fixed_room_type_id"] = 0
    out["non_negotiable_items"] = out.get("non_negotiable_items") or []
    out["non_negotiable_weights"] = out.get("non_negotiable_weights") or []
    return out


def _clear_all_rows(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    table_names = [r[0] for r in rows]
    conn.execute("PRAGMA foreign_keys=OFF")
    for t in table_names:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()


def _insert_bulk(conn: sqlite3.Connection, users: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO users (uid, login_id, student_id, birth_year, password_hash, name, is_enrolled, school_name, college, department, region_name, gender) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                u["uid"],
                u["login_id"],
                u["student_id"],
                u["birth_year"],
                u["password_hash"],
                u["name"],
                u["is_enrolled"],
                u["school_name"],
                u["college"],
                u["department"],
                u["region_name"],
                u["gender"],
            )
            for u in users
        ],
    )

    cols = [c for c, _ in db.PROFILE_COLUMNS]
    qmarks = ", ".join(["?"] * len(cols))
    col_sql = ", ".join(cols)
    profile_rows = []
    for p in profiles:
        row = []
        for c in cols:
            v = p.get(c)
            if c in (
                "non_negotiable_items",
                "non_negotiable_weights",
                "hope_halls",
                "preferred_room_type_ids",
                "interest_room_type_ids",
            ):
                v = json.dumps(v if v is not None else [], ensure_ascii=False)
            row.append(v)
        profile_rows.append(tuple(row))
    conn.executemany(f"INSERT OR REPLACE INTO profiles ({col_sql}) VALUES ({qmarks})", profile_rows)
    conn.commit()


def generate_dummy_dataset(
    target_db_path: str,
    per_persona: int = 100,
    clear_first: bool = False,
    seed: int | None = None,
) -> dict[str, Any]:
    if seed is not None:
        random.seed(seed)

    db.init_db(target_db_path)
    existing = _read_existing_meta(target_db_path)

    users_to_insert: list[dict[str, Any]] = []
    profiles_to_insert: list[dict[str, Any]] = []
    name_used: set[str] = set()
    login_id_used: set[str] = set()
    stats: dict[str, int] = defaultdict(int)
    room_type_catalog = _room_type_catalog()

    seq = 0
    for persona in PERSONAS_8:
        made = 0
        attempts = 0
        while made < per_persona and attempts < per_persona * 10:
            attempts += 1
            seq += 1
            uid = str(uuid.uuid4())
            student_id = f"{random.randint(2019, 2026)}{random.randint(100000, 999999)}"
            name = _unique_name(name_used)
            login_id = _login_id_from_name(name, login_id_used)

            school_name = _weighted_pick(existing.schools, "고려대학교")
            if existing.college_dept_pairs:
                college, department = random.choice(existing.college_dept_pairs)
            else:
                college = _weighted_pick(existing.colleges, "공과대학")
                department = _weighted_pick(existing.departments, "컴퓨터공학과")
            gender = random.choice(["male", "female"])
            birth_year = int(_weighted_pick(existing.birth_years, random.randint(1999, 2006)))

            user_row = {
                "uid": uid,
                "login_id": login_id,
                "student_id": student_id,
                "birth_year": birth_year,
                "password_hash": hash_password(DEFAULT_PASSWORD),
                "name": name,
                "is_enrolled": 1,
                "school_name": school_name,
                "college": college,
                "department": department,
                "region_name": "",
                "gender": gender,
            }

            base = _base_profile_from_existing(existing)
            _jitter_profile(base)
            _apply_persona_blueprint(base, persona)
            normalized = _normalize_profile_for_insert(
                p=base,
                user_uid=uid,
                name=name,
                student_id=student_id,
                persona=persona,
                school_name=school_name,
                gender=gender,
                room_type_catalog=room_type_catalog,
            )

            if _top_persona(normalized) != persona:
                _apply_persona_blueprint(normalized, persona)
            if _top_persona(normalized) != persona:
                continue

            users_to_insert.append(user_row)
            profiles_to_insert.append(normalized)
            stats[persona] += 1
            made += 1

    conn = sqlite3.connect(target_db_path)
    if clear_first:
        _clear_all_rows(conn)
    _insert_bulk(conn, users_to_insert, profiles_to_insert)
    conn.close()

    credentials_path = Path(target_db_path).with_name("dummy_credentials.json")
    credentials = [
        {"name": u["name"], "login_id": u["login_id"], "password": DEFAULT_PASSWORD}
        for u in users_to_insert
    ]
    credentials_path.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "target_db_path": str(Path(target_db_path).resolve()),
        "inserted_users": len(users_to_insert),
        "inserted_profiles": len(profiles_to_insert),
        "per_persona": dict(stats),
        "default_password": DEFAULT_PASSWORD,
        "credentials_path": str(credentials_path.resolve()),
        "credential_samples": credentials[:10],
    }


def clear_database_rows(db_path: str) -> dict[str, Any]:
    if not os.path.exists(db_path):
        return {"ok": False, "error": "db file not found", "db_path": db_path}
    conn = sqlite3.connect(db_path)
    _clear_all_rows(conn)
    conn.close()
    return {"ok": True, "db_path": str(Path(db_path).resolve())}


def delete_database_file(db_path: str) -> dict[str, Any]:
    p = Path(db_path)
    if not p.exists():
        return {"ok": False, "error": "db file not found", "db_path": str(p)}
    p.unlink()
    return {"ok": True, "db_path": str(p.resolve())}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate 8-persona dummy users/profiles")
    parser.add_argument("--target-db", default="roommates_api.db", help="Target sqlite db path")
    parser.add_argument("--per-persona", type=int, default=100, help="Rows per persona (default: 100)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--clear-first", action="store_true", help="Delete all existing table rows before insert")
    parser.add_argument(
        "--mode",
        choices=["generate", "clear", "delete-file"],
        default="generate",
        help="Operation mode",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.mode == "generate":
        result = generate_dummy_dataset(
            target_db_path=args.target_db,
            per_persona=args.per_persona,
            clear_first=args.clear_first,
            seed=args.seed,
        )
    elif args.mode == "clear":
        result = clear_database_rows(args.target_db)
    else:
        result = delete_database_file(args.target_db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
