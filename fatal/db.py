"""SQLite helpers for roommate data."""

from __future__ import annotations

import sqlite3
from typing import Iterable, List

from checklist import RoommateProfile

DB_PATH = "roommates.db"

_COLUMNS = [
    ("uid", "TEXT PRIMARY KEY"),
    ("persona", "TEXT"),
    ("name", "TEXT NOT NULL"),
    ("student_id", "TEXT NOT NULL"),
    ("birth_year", "INTEGER"),
    ("college", "TEXT"),
    ("department", "TEXT"),
    ("dorm_duration", "INTEGER"),
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
]


def init_db(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cols_sql = ", ".join([f"{name} {col_type}" for name, col_type in _COLUMNS])
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS roommates (
            {cols_sql},
            UNIQUE(student_id)
        )
        """
    )
    conn.commit()
    conn.close()


def save_profiles(profiles: Iterable[RoommateProfile], db_path: str = DB_PATH) -> None:
    """Insert or replace profiles in bulk."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    placeholders = ", ".join(["?"] * len(_COLUMNS))
    cols_only = ", ".join([c[0] for c in _COLUMNS])
    sql = f"INSERT OR REPLACE INTO roommates ({cols_only}) VALUES ({placeholders})"
    rows = []
    for p in profiles:
        d = p.__dict__
        rows.append(tuple(d[col] for col, _ in _COLUMNS))
    conn.executemany(sql, rows)
    conn.commit()
    conn.close()


def fetch_profiles(db_path: str = DB_PATH) -> List[RoommateProfile]:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cols = [c[0] for c in _COLUMNS]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM roommates").fetchall()
    conn.close()
    profiles = []
    for row in rows:
        data = dict(zip(cols, row))
        profiles.append(RoommateProfile(**data))
    return profiles


def delete_all(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM roommates")
    conn.commit()
    conn.close()
