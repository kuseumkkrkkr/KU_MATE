"""Profile generator with lightweight realism and DB save helper."""

from __future__ import annotations

import random
import uuid
from typing import Iterable, List, Optional

from checklist import RoommateProfile
import db

# Persona presets define sleep timing, gaming preference, drinking freq
PERSONAS = {
    "올빼미형": {"bedtime_mu": 2, "wake_mu": 11, "gaming_w": [5, 20, 30, 25, 20], "alcohol_freq_w": [10, 20, 30, 25, 15]},
    "아침형": {"bedtime_mu": 23, "wake_mu": 6, "gaming_w": [30, 30, 20, 15, 5], "alcohol_freq_w": [30, 30, 20, 15, 5]},
    "중간형": {"bedtime_mu": 1, "wake_mu": 8, "gaming_w": [15, 30, 25, 20, 10], "alcohol_freq_w": [20, 25, 25, 20, 10]},
    "운동파": {"bedtime_mu": 24, "wake_mu": 7, "gaming_w": [30, 30, 20, 15, 5], "alcohol_freq_w": [25, 30, 25, 15, 5]},
    "집순이형": {"bedtime_mu": 3, "wake_mu": 11, "gaming_w": [5, 10, 20, 30, 35], "alcohol_freq_w": [20, 25, 25, 20, 10]},
}

COLLEGES = [
    "공과대학",
    "인문대학",
    "사회과학대학",
    "자연과학대학",
    "경영대학",
    "예술대학",
    "체육대학",
    "음악대학",
]

DEPARTMENTS = {
    "공과대학": ["기계공학과", "전기전자과", "컴퓨터공학과", "화학공학과"],
    "인문대학": ["국어국문과", "영어영문과", "사학과", "철학과"],
    "사회과학대학": ["정치외교", "심리학과", "사회학과", "미디어학과"],
    "자연과학대학": ["수학과", "물리학과", "화학과", "생명과학과"],
    "경영대학": ["경영학과", "회계학과", "국제경영"],
    "예술대학": ["시각디자인", "패션디자인", "회화과"],
    "체육대학": ["체육학과", "스포츠과학과"],
    "음악대학": ["성악과", "피아노과", "작곡과"],
}

FIRST_NAMES = ["민준", "서연", "지우", "하윤", "주원", "수아", "예준", "도윤", "지민", "서현", "윤호", "지호"]
LAST_NAMES = ["김", "이", "박", "정", "최", "조", "강", "윤", "임", "한"]


def _wchoice(population: list, weights: list):
    return random.choices(population, weights=weights, k=1)[0]


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _random_name() -> str:
    return random.choice(LAST_NAMES) + random.choice(FIRST_NAMES)


def _random_time(mu: int, sigma: float = 1.2) -> int:
    t = int(round(random.gauss(mu, sigma))) % 24
    return t if t >= 0 else t + 24


def generate_profile(persona: Optional[str] = None, seed: Optional[int] = None) -> RoommateProfile:
    """Generate one profile; persona picks a preset distribution."""
    if seed is not None:
        random.seed(seed)

    if persona is None:
        persona = _wchoice(list(PERSONAS.keys()), weights=[25, 20, 35, 10, 10])
    tmpl = PERSONAS[persona]

    college = random.choice(COLLEGES)
    department = random.choice(DEPARTMENTS[college])
    birth_year = _wchoice([2002, 2003, 2004, 2005, 2006], weights=[15, 30, 30, 20, 5])
    dorm_dur = _wchoice([1, 2, 3, 4], weights=[40, 30, 20, 10])

    base_alcohol = _wchoice(
        [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        weights=[5, 10, 20, 25, 20, 10, 5, 3, 2],
    )
    alcohol_freq = _wchoice([1, 2, 3, 4, 5], weights=tmpl["alcohol_freq_w"])
    drunk_habit = _wchoice([0, 1], weights=[80, 20])

    gaming = _wchoice([5, 10, 15, 20, 25], weights=tmpl["gaming_w"])

    bedtime = _random_time(tmpl["bedtime_mu"])
    wake_time = _random_time(tmpl["wake_mu"])

    shower_cycle = _wchoice([1, 2, 3, 4, 5], weights=[55, 25, 5, 10, 5])
    shower_dur = _wchoice([5, 10, 15, 20, 30], weights=[5, 30, 35, 20, 10])
    shower_base = tmpl["bedtime_mu"] - 1 if tmpl["bedtime_mu"] > 12 else tmpl["wake_mu"] + 1
    shower_time = _random_time(shower_base, 1.5)

    cleaning_cycle = _wchoice([1, 3, 7, 14, 30], weights=[5, 15, 40, 30, 10])
    ventilation = _wchoice([0.5, 1, 2, 4, 5], weights=[10, 35, 35, 15, 5])

    temp_pref = _clamp(int(round(random.gauss(3, 1))), 1, 5)
    noise_sens = _clamp(int(round(random.gauss(3, 1))), 1, 5)
    sleep_sens = _clamp(int(round(random.gauss(3, 1.2))), 1, 5)
    alarm_str = _clamp(int(round(random.gauss(3, 1))), 1, 5)

    intimacy = _wchoice([1, 2, 3, 4, 5], weights=[5, 15, 35, 30, 15])
    meal_tog = _wchoice([1, 2, 3], weights=[20, 45, 35])
    ex_tog = _wchoice([1, 2, 3], weights=[40, 40, 20])
    friend_inv = _wchoice([1, 3, 5], weights=[20, 60, 20])

    return RoommateProfile(
        persona=persona,
        name=_random_name(),
        student_id=f"20{birth_year % 100:02d}{random.randint(10000, 99999)}",
        birth_year=birth_year,
        college=college,
        department=department,
        dorm_duration=dorm_dur,
        home_visit_cycle=_wchoice([1, 2, 3, 4], weights=[15, 35, 30, 20]),
        perfume=_wchoice([0, 1], weights=[60, 40]),
        indoor_scent_sensitivity=_clamp(int(round(random.gauss(2.5, 1))), 1, 5),
        alcohol_tolerance=base_alcohol,
        alcohol_frequency=alcohol_freq,
        drunk_habit=drunk_habit,
        gaming_hours_per_week=gaming,
        speaker_use=_wchoice([0, 1], weights=[70, 30]),
        exercise=_wchoice([0, 1], weights=[45, 55]),
        bedtime=bedtime,
        wake_time=wake_time,
        sleep_habit=_wchoice([0, 1], weights=[75, 25]),
        sleep_sensitivity=sleep_sens,
        alarm_strength=alarm_str,
        sleep_light=_wchoice([0, 1], weights=[70, 30]),
        snoring=_wchoice([0, 1], weights=[75, 25]),
        shower_duration=shower_dur,
        shower_time=shower_time,
        shower_cycle=shower_cycle,
        cleaning_cycle=cleaning_cycle,
        ventilation=ventilation,
        hairdryer_in_bathroom=_wchoice([0, 1], weights=[30, 70]),
        toilet_paper_share=_wchoice([0, 1], weights=[20, 80]),
        indoor_eating=_wchoice([0, 1], weights=[40, 60]),
        smoking=_wchoice([0, 1], weights=[85, 15]),
        temperature_pref=temp_pref,
        indoor_call=_wchoice([0, 1], weights=[40, 60]),
        bug_handling=_clamp(int(round(random.gauss(3, 1.2))), 1, 5),
        laundry_cycle=_wchoice([14, 7, 5, 3, 1], weights=[10, 35, 25, 20, 10]),
        drying_rack=_wchoice([0, 1], weights=[20, 80]),
        fridge_use=_wchoice([0, 1], weights=[15, 85]),
        study_in_room=_wchoice([0, 1], weights=[35, 65]),
        noise_sensitivity=noise_sens,
        desired_intimacy=intimacy,
        meal_together=meal_tog,
        exercise_together=ex_tog,
        friend_invite=friend_inv,
    )


def generate_profiles(n: int, persona: Optional[str] = None, seed: Optional[int] = None) -> List[RoommateProfile]:
    if seed is not None:
        random.seed(seed)
    return [generate_profile(persona=persona) for _ in range(n)]


def generate_and_store(n: int, persona: Optional[str] = None, seed: Optional[int] = None, db_path: str = db.DB_PATH) -> List[RoommateProfile]:
    profiles = generate_profiles(n, persona=persona, seed=seed)
    db.save_profiles(profiles, db_path=db_path)
    return profiles


if __name__ == "__main__":
    db.init_db()
    demo = generate_and_store(5, persona=None, seed=42)
    print(f"생성 및 저장 완료: {len(demo)}명 (db={db.DB_PATH})")
