"""Simple SQLite helpers."""

import os
import sqlite3
import json
from typing import List, Optional
from models import User, RoommateProfile, profile_to_dict, classify_persona

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)
DB_PATH = os.path.join(_PROJECT_ROOT, "roommates_api.db")
SCHOOLS_DB_PATH = os.path.join(_PROJECT_ROOT, "schools.db")
SQLITE_TIMEOUT_SECONDS = 10
SQLITE_BUSY_TIMEOUT_MS = 10000


USER_COLUMNS = [
    ("uid", "TEXT PRIMARY KEY"),
    ("login_id", "TEXT NOT NULL UNIQUE"),
    ("student_id", "TEXT"),
    ("birth_year", "INTEGER DEFAULT 2005"),
    ("password_hash", "TEXT NOT NULL"),
    ("name", "TEXT NOT NULL"),
    ("is_enrolled", "INTEGER NOT NULL DEFAULT 1"),
    ("school_name", "TEXT"),
    ("college", "TEXT"),
    ("department", "TEXT"),
    ("region_name", "TEXT"),
    ("gender", "TEXT"),
    ("is_suspended", "INTEGER DEFAULT 0"),
]

PROFILE_COLUMNS = [
    ("uid", "TEXT PRIMARY KEY"),
    ("user_uid", "TEXT NOT NULL UNIQUE"),
    ("persona", "TEXT"),
    ("name", "TEXT NOT NULL"),
    ("student_id", "TEXT NOT NULL"),
    ("birth_year", "INTEGER"),
    ("college", "TEXT"),
    ("department", "TEXT"),
    ("dorm_duration", "INTEGER"),
    ("dormitory_hall", "TEXT"),
    ("non_negotiable_items", "TEXT"),
    ("non_negotiable_weights", "TEXT"),
    ("home_visit_cycle", "INTEGER"),
    ("perfume", "INTEGER"),
    ("indoor_scent_sensitivity", "INTEGER"),
    ("alcohol_tolerance", "REAL"),
    ("alcohol_frequency", "INTEGER"),
    ("drunk_habit", "INTEGER"),
    ("gaming_hours_per_week", "INTEGER"),
    ("speaker_use", "INTEGER"),
    ("exercise", "INTEGER"),
    ("bedtime", "INTEGER"),
    ("wake_time", "INTEGER"),
    ("sleep_habit", "INTEGER"),
    ("sleep_sensitivity", "INTEGER"),
    ("alarm_strength", "INTEGER"),
    ("sleep_light", "INTEGER"),
    ("snoring", "INTEGER"),
    ("shower_duration", "INTEGER"),
    ("shower_time", "INTEGER"),
    ("shower_cycle", "INTEGER"),
    ("cleaning_cycle", "INTEGER"),
    ("ventilation", "REAL"),
    ("hairdryer_in_bathroom", "INTEGER"),
    ("toilet_paper_share", "INTEGER"),
    ("indoor_eating", "INTEGER"),
    ("smoking", "INTEGER"),
    ("temperature_pref", "INTEGER"),
    ("indoor_call", "INTEGER"),
    ("bug_handling", "INTEGER"),
    ("laundry_cycle", "INTEGER"),
    ("drying_rack", "INTEGER"),
    ("fridge_use", "INTEGER"),
    ("study_in_room", "INTEGER"),
    ("noise_sensitivity", "INTEGER"),
    ("desired_intimacy", "INTEGER"),
    ("meal_together", "INTEGER"),
    ("exercise_together", "INTEGER"),
    ("friend_invite", "INTEGER"),
    ("matching_phase", "TEXT DEFAULT 'preliminary'"),
    ("hope_halls", "TEXT"),
    ("accepted_hall", "TEXT"),
    ("room_capacity", "INTEGER DEFAULT 2"),
    ("preferred_room_type_ids", "TEXT"),
    ("fixed_room_type_id", "INTEGER DEFAULT 0"),
    ("interest_room_type_ids", "TEXT"),
    ("fixed_interest_room_type_id", "INTEGER DEFAULT 0"),
    ("pre_change_count", "INTEGER DEFAULT 0"),
    ("apply_change_count", "INTEGER DEFAULT 0"),
    ("pre_last_changed_at", "TEXT"),
    ("apply_last_changed_at", "TEXT"),
    ("hall_confirmed_at", "TEXT"),
]

PROFILE_CHECKS = [
    "CREATE TRIGGER IF NOT EXISTS chk_fixed_room_type_nonneg "
    "AFTER UPDATE ON profiles "
    "WHEN NEW.fixed_room_type_id < 0 "
    "BEGIN SELECT RAISE(ABORT, 'fixed_room_type_id must be >= 0'); END",
    "CREATE TRIGGER IF NOT EXISTS chk_fixed_interest_room_type_nonneg "
    "AFTER UPDATE ON profiles "
    "WHEN NEW.fixed_interest_room_type_id < 0 "
    "BEGIN SELECT RAISE(ABORT, 'fixed_interest_room_type_id must be >= 0'); END",
]


def _ensure_table(conn: sqlite3.Connection, name: str, columns: List):
    col_defs = ", ".join(f"{c} {t}" for c, t in columns)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({col_defs})")


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: List):
    """Best-effort migration: add columns if they do not exist."""
    existing_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for col_name, col_type in columns:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schools_db(db_path: str = SCHOOLS_DB_PATH):
    conn = get_connection(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schools ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL UNIQUE, "
        "is_hidden INTEGER NOT NULL DEFAULT 0, "
        "recruitment_start TEXT, "
        "recruitment_end TEXT, "
        "pre_matching_start TEXT, "
        "pre_matching_end TEXT, "
        "roommate_apply_start TEXT, "
        "roommate_apply_end TEXT, "
        "room_life_start TEXT, "
        "room_life_end TEXT, "
        "matching_enabled INTEGER NOT NULL DEFAULT 1"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dormitories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "school_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "gender TEXT NOT NULL CHECK(gender IN ('male','female','coed')), "
        "UNIQUE(school_id, name), "
        "FOREIGN KEY(school_id) REFERENCES schools(id) ON DELETE CASCADE"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS colleges ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "school_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "UNIQUE(school_id, name), "
        "FOREIGN KEY(school_id) REFERENCES schools(id) ON DELETE CASCADE"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS departments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "college_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "UNIQUE(college_id, name), "
        "FOREIGN KEY(college_id) REFERENCES colleges(id) ON DELETE CASCADE"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dorm_room_types ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "dorm_id INTEGER NOT NULL, "
        "capacity INTEGER NOT NULL, "
        "is_enabled INTEGER NOT NULL DEFAULT 1, "
        "UNIQUE(dorm_id, capacity), "
        "FOREIGN KEY(dorm_id) REFERENCES dormitories(id) ON DELETE CASCADE"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS global_notices ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "body TEXT NOT NULL, "
        "is_pinned INTEGER NOT NULL DEFAULT 0, "
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
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, "
        "FOREIGN KEY(school_id) REFERENCES schools(id) ON DELETE CASCADE)"
    )
    _add_missing_columns(conn, "schools", [
        ("is_hidden", "INTEGER NOT NULL DEFAULT 0"),
        ("pre_matching_start", "TEXT"),
        ("pre_matching_end", "TEXT"),
        ("roommate_apply_start", "TEXT"),
        ("roommate_apply_end", "TEXT"),
        ("room_life_start", "TEXT"),
        ("room_life_end", "TEXT"),
    ])
    _add_missing_columns(conn, "global_notices", [
        ("is_collapsed", "INTEGER NOT NULL DEFAULT 0"),
    ])
    _add_missing_columns(conn, "school_notices", [
        ("is_collapsed", "INTEGER NOT NULL DEFAULT 0"),
    ])

    # 고려대학교 기본 데이터 보존 (SQL 명령어 기반)
    conn.execute(
        "INSERT OR IGNORE INTO schools (name, recruitment_start, recruitment_end, matching_enabled) VALUES (?, ?, ?, ?)",
        ("고려대학교", None, None, 1),
    )
    school_row = conn.execute("SELECT id FROM schools WHERE name=?", ("고려대학교",)).fetchone()
    if school_row:
        school_id = school_row[0]
        conn.execute(
            "INSERT OR REPLACE INTO dormitories (id, school_id, name, gender) VALUES ("
            "COALESCE((SELECT id FROM dormitories WHERE school_id=? AND name=?), NULL), ?, ?, ?)",
            (school_id, "자유관", school_id, "자유관", "male"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO dormitories (id, school_id, name, gender) VALUES ("
            "COALESCE((SELECT id FROM dormitories WHERE school_id=? AND name=?), NULL), ?, ?, ?)",
            (school_id, "미래관", school_id, "미래관", "coed"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO dormitories (id, school_id, name, gender) VALUES ("
            "COALESCE((SELECT id FROM dormitories WHERE school_id=? AND name=?), NULL), ?, ?, ?)",
            (school_id, "진리관", school_id, "진리관", "coed"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO dormitories (id, school_id, name, gender) VALUES ("
            "COALESCE((SELECT id FROM dormitories WHERE school_id=? AND name=?), NULL), ?, ?, ?)",
            (school_id, "정의관", school_id, "정의관", "female"),
        )

        dorm_room_type_defaults = {
            "자유관": [2, 4],
            "미래관": [2, 3, 4],
            "진리관": [2, 3, 4],
            "정의관": [2, 4],
        }
        for dorm_row in conn.execute(
            "SELECT id, name FROM dormitories WHERE school_id=?",
            (school_id,),
        ).fetchall():
            existing_caps = {
                r[0] for r in conn.execute(
                    "SELECT capacity FROM dorm_room_types WHERE dorm_id=?",
                    (dorm_row[0],),
                ).fetchall()
            }
            for cap in dorm_room_type_defaults.get(dorm_row[1], [2, 3, 4]):
                if cap not in existing_caps:
                    conn.execute(
                        "INSERT INTO dorm_room_types (dorm_id, capacity, is_enabled) VALUES (?, ?, 1)",
                        (dorm_row[0], cap),
                    )

        # 단과대학 및 학과 기본 데이터 보존
        default_colleges = {
            "공과대학": ["기계공학과", "전기전자과", "컴퓨터공학과", "화학공학과"],
            "인문대학": ["국어국문과", "영어영문과", "사학과", "철학과"],
            "사회과학대학": ["정치외교", "심리학과", "사회학과", "미디어학과"],
            "자연과학대학": ["수학과", "물리학과", "화학과", "생명과학과"],
            "경영대학": ["경영학과", "회계학과", "국제경영"],
            "예술대학": ["시각디자인", "패션디자인", "회화과"],
            "체육대학": ["체육학과", "스포츠과학과"],
            "음악대학": ["성악과", "피아노과", "작곡과"],
        }
        for college_name, departments in default_colleges.items():
            conn.execute(
                "INSERT OR IGNORE INTO colleges (school_id, name) VALUES (?, ?)",
                (school_id, college_name),
            )
            college_row = conn.execute(
                "SELECT id FROM colleges WHERE school_id=? AND name=?",
                (school_id, college_name),
            ).fetchone()
            if college_row:
                college_id = college_row[0]
                for dept_name in departments:
                    conn.execute(
                        "INSERT OR IGNORE INTO departments (college_id, name) VALUES (?, ?)",
                        (college_id, dept_name),
                    )

    conn.commit()
    conn.close()

def init_db(db_path: str = DB_PATH, drop_if_corrupt: bool = True):
    try:
        init_schools_db()
        conn = get_connection(db_path)
        _ensure_table(conn, "users", USER_COLUMNS)
        _ensure_table(conn, "profiles", PROFILE_COLUMNS)
        _add_missing_columns(conn, "users", USER_COLUMNS)
        _add_missing_columns(conn, "profiles", PROFILE_COLUMNS)

        for trig_sql in PROFILE_CHECKS:
            try:
                conn.execute(trig_sql)
            except Exception:
                pass

        # ???뚯씠釉? match_pool_candidates (? ?꾨낫)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_pool_candidates ("
            "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL, "
            "          candidate_uid TEXT, candidate_type TEXT DEFAULT 'individual', "
            "          display_name TEXT, shared_score REAL, member_scores TEXT, member_names TEXT, "
            "          tier TEXT, room_capacity INTEGER, detail TEXT, created_at TEXT)"
        )

        # ???뚯씠釉? match_sessions (留ㅼ묶 ?몄뀡)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_sessions ("
            "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL, "
            "          candidate_uid TEXT NOT NULL, candidate_type TEXT DEFAULT 'individual', "
            "          room_member_uids TEXT, delegate_uid TEXT, status TEXT, "
            "          user_confirmed INTEGER DEFAULT 0, candidate_confirmed INTEGER DEFAULT 0, "
            "          user_decision TEXT, candidate_decision TEXT, "
            "          user_reject_reason TEXT, candidate_reject_reason TEXT, "
            "          user_survey_opened INTEGER DEFAULT 0, candidate_survey_opened INTEGER DEFAULT 0, "
            "          last_activity_at TEXT, created_at TEXT, confirmed_at TEXT, closed_at TEXT)"
        )

        # ???뚯씠釉? match_session_members (?몄뀡 李멸???
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_session_members ("
            "          uid TEXT PRIMARY KEY, session_uid TEXT, user_uid TEXT, "
            "          role TEXT, joined_at TEXT)"
        )

        # ???뚯씠釉? chat_threads (梨꾪똿 ?ㅻ젅??
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chat_threads ("
            "          uid TEXT PRIMARY KEY, session_uid TEXT, "
            "          user_a TEXT, user_b TEXT, status TEXT, "
            "          closed_reason TEXT, chat_exchange_count INTEGER DEFAULT 0, "
            "          last_message_at TEXT, created_at TEXT, closed_at TEXT)"
        )

        # ???뚯씠釉? match_cooldowns (?щℓ移?荑⑤떎??
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_cooldowns ("
            "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL UNIQUE, "
            "          cooldown_until TEXT, reason TEXT, created_at TEXT)"
        )

        # ???뚯씠釉? system_events (?쒖뒪???대깽??濡쒓렇)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS system_events ("
            "          uid TEXT PRIMARY KEY, user_uid TEXT, event_type TEXT, "
            "          payload TEXT, created_at TEXT, expire_at TEXT)"
        )

        # ???뚯씠釉? pairings (?꾩껜 留ㅼ묶 寃곌낵)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pairings (uid TEXT PRIMARY KEY, pair_json TEXT, generated_at TEXT)"
        )

        # ???뚯씠釉? match_requests (?붿껌/?뱀씤)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_requests ("
            "          uid TEXT PRIMARY KEY, from_user TEXT, to_user TEXT, status TEXT, created_at TEXT, updated_at TEXT)"
        )

        # ???뚯씠釉? chat_messages
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chat_messages ("
            "          uid TEXT PRIMARY KEY, session_uid TEXT, thread_uid TEXT, "
            "          sender TEXT, receiver TEXT, content TEXT, type TEXT, read INTEGER, "
            "          delivered_at TEXT, expires_at TEXT, created_at TEXT)"
        )

        # ???뚯씠釉? reviews
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reviews ("
            "          uid TEXT PRIMARY KEY, reviewer TEXT, reviewee TEXT, rating REAL, body TEXT, "
            "          session_uid TEXT, decision_type TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_pair_blocks ("
            "          uid TEXT PRIMARY KEY, user_a TEXT NOT NULL, user_b TEXT NOT NULL, "
            "          blocked_by TEXT, reason TEXT, source_session_uid TEXT, created_at TEXT, "
            "          UNIQUE(user_a, user_b))"
        )

        # notices (admin editable announcements)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS notices ("
            "          id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "          title TEXT NOT NULL, "
            "          body TEXT NOT NULL, "
            "          is_pinned INTEGER NOT NULL DEFAULT 0, "
            "          created_at TEXT NOT NULL, "
            "          updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_rooms ("
            "          uid TEXT PRIMARY KEY, school_id INTEGER, host_uid TEXT NOT NULL, status TEXT NOT NULL, "
            "          room_type_id INTEGER, target_capacity INTEGER DEFAULT 2, fixed_hall INTEGER DEFAULT 0, "
            "          fill_strategy TEXT DEFAULT 'continue', pre_policy_change_count INTEGER DEFAULT 0, "
            "          apply_policy_change_count INTEGER DEFAULT 0, rules_change_count INTEGER DEFAULT 0, "
            "          created_at TEXT, updated_at TEXT, closed_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_members ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, user_uid TEXT NOT NULL, joined_at TEXT, "
            "          is_active INTEGER DEFAULT 1, UNIQUE(life_room_uid, user_uid))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_posts ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, author_uid TEXT NOT NULL, "
            "          title TEXT NOT NULL, body TEXT NOT NULL, pinned INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_rules ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, body TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_todos ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, assignee_uid TEXT, "
            "          title TEXT NOT NULL, due_date TEXT, done INTEGER DEFAULT 0, created_by TEXT NOT NULL, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_events ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, author_uid TEXT NOT NULL, "
            "          title TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT, view_type TEXT DEFAULT 'month', "
            "          created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_presence ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, user_uid TEXT NOT NULL, "
            "          status TEXT NOT NULL, updated_at TEXT, UNIQUE(life_room_uid, user_uid))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_notice_pins ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, user_uid TEXT NOT NULL, "
            "          post_uid TEXT NOT NULL, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_fill_policy ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, period TEXT NOT NULL, "
            "          strategy TEXT NOT NULL, changed_by TEXT NOT NULL, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_recruit_sessions ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT, closed_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS life_room_match_history ("
            "          uid TEXT PRIMARY KEY, life_room_uid TEXT NOT NULL, matched_with_type TEXT NOT NULL, "
            "          matched_with_uid TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT)"
        )

        # ???뚯씠釉? match_history
        conn.execute(
            "CREATE TABLE IF NOT EXISTS match_history ("
            "          uid TEXT PRIMARY KEY, session_uid TEXT, user_a TEXT, user_b TEXT, status TEXT, matched_at TEXT)"
        )

        _add_missing_columns(conn, "match_pool_candidates", [
            ("candidate_uid", "TEXT"),
            ("candidate_type", "TEXT DEFAULT 'individual'"),
            ("display_name", "TEXT"),
            ("shared_score", "REAL"),
            ("member_scores", "TEXT"),
            ("member_names", "TEXT"),
            ("detail", "TEXT"),
        ])
        _add_missing_columns(conn, "match_sessions", [
            ("user_uid", "TEXT"),
            ("candidate_uid", "TEXT"),
            ("candidate_type", "TEXT DEFAULT 'individual'"),
            ("room_member_uids", "TEXT"),
            ("delegate_uid", "TEXT"),
            ("user_confirmed", "INTEGER DEFAULT 0"),
            ("candidate_confirmed", "INTEGER DEFAULT 0"),
            ("user_decision", "TEXT"),
            ("candidate_decision", "TEXT"),
            ("user_reject_reason", "TEXT"),
            ("candidate_reject_reason", "TEXT"),
            ("user_survey_opened", "INTEGER DEFAULT 0"),
            ("candidate_survey_opened", "INTEGER DEFAULT 0"),
            ("last_activity_at", "TEXT"),
        ])
        _add_missing_columns(conn, "chat_threads", [
            ("closed_reason", "TEXT"),
            ("chat_exchange_count", "INTEGER DEFAULT 0"),
            ("last_message_at", "TEXT"),
        ])
        _add_missing_columns(conn, "chat_messages", [
            ("session_uid", "TEXT"),
            ("thread_uid", "TEXT"),
            ("delivered_at", "TEXT"),
            ("expires_at", "TEXT"),
        ])
        _add_missing_columns(conn, "match_cooldowns", [
            ("cooldown_until", "TEXT"),
            ("created_at", "TEXT"),
        ])
        _add_missing_columns(conn, "system_events", [
            ("user_uid", "TEXT"),
            ("expire_at", "TEXT"),
        ])
        _add_missing_columns(conn, "match_history", [
            ("session_uid", "TEXT"),
        ])
        _add_missing_columns(conn, "reviews", [
            ("session_uid", "TEXT"),
            ("decision_type", "TEXT"),
        ])
        _add_missing_columns(conn, "match_pair_blocks", [
            ("blocked_by", "TEXT"),
            ("reason", "TEXT"),
            ("source_session_uid", "TEXT"),
            ("created_at", "TEXT"),
        ])
        _add_missing_columns(conn, "notices", [
            ("is_pinned", "INTEGER NOT NULL DEFAULT 0"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
        ])

        conn.commit()
        conn.close()
    except Exception as e:
        if drop_if_corrupt:
            import os
            if os.path.exists(db_path):
                os.remove(db_path)
            conn = get_connection(db_path)
            _ensure_table(conn, "users", USER_COLUMNS)
            _ensure_table(conn, "profiles", PROFILE_COLUMNS)
            _add_missing_columns(conn, "users", USER_COLUMNS)
            _add_missing_columns(conn, "profiles", PROFILE_COLUMNS)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_pool_candidates ("
                "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL, "
                "          candidate_uid TEXT, candidate_type TEXT DEFAULT 'individual', "
                "          display_name TEXT, shared_score REAL, member_scores TEXT, member_names TEXT, "
                "          tier TEXT, room_capacity INTEGER, detail TEXT, created_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_sessions ("
                "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL, "
                "          candidate_uid TEXT NOT NULL, candidate_type TEXT DEFAULT 'individual', "
                "          room_member_uids TEXT, delegate_uid TEXT, status TEXT, "
                "          user_confirmed INTEGER DEFAULT 0, candidate_confirmed INTEGER DEFAULT 0, "
                "          user_decision TEXT, candidate_decision TEXT, "
                "          user_reject_reason TEXT, candidate_reject_reason TEXT, "
                "          user_survey_opened INTEGER DEFAULT 0, candidate_survey_opened INTEGER DEFAULT 0, "
                "          last_activity_at TEXT, created_at TEXT, confirmed_at TEXT, closed_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_session_members ("
                "          uid TEXT PRIMARY KEY, session_uid TEXT, user_uid TEXT, "
                "          role TEXT, joined_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS chat_threads ("
                "          uid TEXT PRIMARY KEY, session_uid TEXT, "
                "          user_a TEXT, user_b TEXT, status TEXT, "
                "          closed_reason TEXT, chat_exchange_count INTEGER DEFAULT 0, "
                "          last_message_at TEXT, created_at TEXT, closed_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_cooldowns ("
                "          uid TEXT PRIMARY KEY, user_uid TEXT NOT NULL UNIQUE, "
                "          cooldown_until TEXT, reason TEXT, created_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS system_events ("
                "          uid TEXT PRIMARY KEY, user_uid TEXT, event_type TEXT, "
                "          payload TEXT, created_at TEXT, expire_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS pairings (uid TEXT PRIMARY KEY, pair_json TEXT, generated_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_requests ("
                "          uid TEXT PRIMARY KEY, from_user TEXT, to_user TEXT, status TEXT, created_at TEXT, updated_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS chat_messages ("
                "          uid TEXT PRIMARY KEY, session_uid TEXT, thread_uid TEXT, "
                "          sender TEXT, receiver TEXT, content TEXT, type TEXT, read INTEGER, "
                "          delivered_at TEXT, expires_at TEXT, created_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reviews ("
                "          uid TEXT PRIMARY KEY, reviewer TEXT, reviewee TEXT, rating REAL, body TEXT, "
                "          session_uid TEXT, decision_type TEXT, created_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_pair_blocks ("
                "          uid TEXT PRIMARY KEY, user_a TEXT NOT NULL, user_b TEXT NOT NULL, "
                "          blocked_by TEXT, reason TEXT, source_session_uid TEXT, created_at TEXT, "
                "          UNIQUE(user_a, user_b))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_history ("
                "          uid TEXT PRIMARY KEY, session_uid TEXT, user_a TEXT, user_b TEXT, status TEXT, matched_at TEXT)"
            )
            conn.commit()
            conn.close()
        else:
            raise


def save_user(user: User, db_path: str = DB_PATH):
    conn = get_connection(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO users (uid, login_id, student_id, birth_year, password_hash, name, is_enrolled, school_name, college, department, region_name, gender) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user.uid,
            user.login_id,
            user.student_id,
            user.birth_year,
            user.password_hash,
            user.name,
            user.is_enrolled,
            user.school_name,
            user.college,
            user.department,
            user.region_name,
            user.gender,
        ),
    )
    conn.commit()
    conn.close()


def get_user_by_login_id(login_id: str, db_path: str = DB_PATH) -> Optional[User]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE login_id = ? LIMIT 1", (login_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return User(**{k: row[k] for k in row.keys()})


def get_user_by_uid(uid: str, db_path: str = DB_PATH) -> Optional[User]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE uid = ? LIMIT 1", (uid,)).fetchone()
    conn.close()
    if row is None:
        return None
    return User(**{k: row[k] for k in row.keys()})


def save_profile(profile: RoommateProfile, db_path: str = DB_PATH):
    # ?섎Ⅴ?뚮굹 ?먮룞 遺꾨쪟
    if not profile.persona:
        profile.persona = classify_persona(profile)

    conn = get_connection(db_path)
    cols = [c for c, _ in PROFILE_COLUMNS]
    placeholders = ", ".join(["?"] * len(cols))
    # JSON 吏곷젹?붽? ?꾩슂??而щ읆 泥섎━
    values = []
    for c in cols:
        v = getattr(profile, c, None)
        if c in (
            "non_negotiable_items",
            "non_negotiable_weights",
            "hope_halls",
            "preferred_room_type_ids",
            "interest_room_type_ids",
        ) and v is not None:
            v = json.dumps(v, ensure_ascii=False)
        values.append(v)
    conn.execute(
        f"INSERT OR REPLACE INTO profiles ({', '.join(cols)}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    conn.close()


def get_profile_by_user_uid(user_uid: str, db_path: str = DB_PATH) -> Optional[RoommateProfile]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM profiles WHERE user_uid = ? LIMIT 1", (user_uid,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = {k: row[k] for k in row.keys()}
    # JSON ??쭅?ы솕
    for k in (
        "non_negotiable_items",
        "non_negotiable_weights",
        "hope_halls",
        "preferred_room_type_ids",
        "interest_room_type_ids",
    ):
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                d[k] = []
        elif d.get(k) is None:
            d[k] = []
    return RoommateProfile(**d)


def fetch_profiles(db_path: str = DB_PATH) -> List[RoommateProfile]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM profiles").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        for k in (
            "non_negotiable_items",
            "non_negotiable_weights",
            "hope_halls",
            "preferred_room_type_ids",
            "interest_room_type_ids",
        ):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    d[k] = []
        result.append(RoommateProfile(**d))
    return result


# --- 湲곗〈 student_id 湲곕컲 議고쉶 ?좎? ?명솚 ---

def get_user_by_student_id(student_id: str, db_path: str = DB_PATH) -> Optional[User]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE student_id = ? LIMIT 1", (student_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return User(**{k: row[k] for k in row.keys()})
