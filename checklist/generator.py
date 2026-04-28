"""
generator.py
현실적인 룸메이트 프로필 생성기
실제 대학교 기숙사 통계를 반영한 가중치 기반 랜덤 생성
"""

import random
from checklist import RoommateProfile


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _wchoice(population: list, weights: list):
    return random.choices(population, weights=weights, k=1)[0]


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


# ──────────────────────────────────────────────
# 페르소나 템플릿
# ──────────────────────────────────────────────

PERSONAS = {
    "올빼미형": {
        "bedtime_mu": 2,   "wake_mu": 11,
        "gaming_w": [5, 20, 30, 25, 20],
        "alcohol_freq_w": [10, 20, 30, 25, 15],
    },
    "아침형": {
        "bedtime_mu": 23,  "wake_mu": 6,
        "gaming_w": [30, 30, 20, 15, 5],
        "alcohol_freq_w": [30, 30, 20, 15, 5],
    },
    "평균형": {
        "bedtime_mu": 1,   "wake_mu": 8,
        "gaming_w": [15, 30, 25, 20, 10],
        "alcohol_freq_w": [20, 25, 25, 20, 10],
    },
    "운동형": {
        "bedtime_mu": 24,  "wake_mu": 7,
        "gaming_w": [30, 30, 20, 15, 5],
        "alcohol_freq_w": [25, 30, 25, 15, 5],
    },
    "게이머형": {
        "bedtime_mu": 3,   "wake_mu": 11,
        "gaming_w": [5, 10, 20, 30, 35],
        "alcohol_freq_w": [20, 25, 25, 20, 10],
    },
}

COLLEGES = ["공과대학", "인문대학", "사회과학대학", "자연과학대학",
            "경영대학", "사범대학", "의과대학", "예술대학"]

DEPARTMENTS = {
    "공과대학": ["컴퓨터공학과", "전기전자공학과", "기계공학과", "화학공학과"],
    "인문대학": ["국어국문학과", "영어영문학과", "철학과", "사학과"],
    "사회과학대학": ["사회학과", "심리학과", "정치외교학과", "경제학과"],
    "자연과학대학": ["수학과", "물리학과", "화학과", "생물학과"],
    "경영대학": ["경영학과", "회계학과", "국제통상학과"],
    "사범대학": ["교육학과", "수학교육과", "영어교육과"],
    "의과대학": ["의학과", "간호학과"],
    "예술대학": ["음악학과", "미술학과", "체육학과"],
}

FIRST_NAMES = ["지훈", "민준", "서연", "지유", "하은", "준서", "수아", "예진",
               "도현", "채원", "태양", "수민", "지원", "현준", "나연", "유진"]
LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]


def _random_name() -> str:
    return random.choice(LAST_NAMES) + random.choice(FIRST_NAMES)


def _random_time(mu: int, sigma: float = 1.2) -> int:
    """정규분포로 시간 생성, 0-23 범위 클램프"""
    t = int(round(random.gauss(mu, sigma))) % 24
    return t if t >= 0 else t + 24


# ──────────────────────────────────────────────
# 핵심 생성 함수
# ──────────────────────────────────────────────

def generate_profile(
    persona: str | None = None,
    seed: int | None = None,
) -> RoommateProfile:
    """
    현실적인 룸메이트 프로필 하나를 생성합니다.

    Args:
        persona: "올빼미형" | "아침형" | "평균형" | "운동형" | "게이머형"
                 None이면 가중치 기반 랜덤 선택
        seed:    재현성을 위한 랜덤 시드

    Returns:
        RoommateProfile 인스턴스
    """
    if seed is not None:
        random.seed(seed)

    if persona is None:
        persona = _wchoice(
            list(PERSONAS.keys()),
            weights=[25, 20, 35, 10, 10],
        )
    tmpl = PERSONAS[persona]

    college = random.choice(COLLEGES)
    department = random.choice(DEPARTMENTS[college])
    birth_year = _wchoice(
        [2002, 2003, 2004, 2005, 2006],
        weights=[15, 30, 30, 20, 5],
    )

    # 기숙사 경력: 1~4학기
    dorm_dur = _wchoice([1, 2, 3, 4], weights=[40, 30, 20, 10])

    # 음주 관련 (의대/체육 등 페르소나 보정)
    base_alcohol = _wchoice(
        [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        weights=[5, 10, 20, 25, 20, 10, 5, 3, 2],
    )
    alcohol_freq = _wchoice(
        [1, 2, 3, 4, 5],
        weights=tmpl["alcohol_freq_w"],
    )
    drunk_habit = _wchoice([0, 1], weights=[80, 20])

    # 게임
    gaming = _wchoice([5, 10, 15, 20, 25], weights=tmpl["gaming_w"])

    # 취침/기상
    bedtime = _random_time(tmpl["bedtime_mu"])
    wake_time = _random_time(tmpl["wake_mu"])

    # 청결 주기 — 샤워
    shower_cycle = _wchoice([1, 2, 3, 4, 5], weights=[55, 25, 5, 10, 5])
    shower_dur = _wchoice([5, 10, 15, 20, 30], weights=[5, 30, 35, 20, 10])
    # 샤워 시간: 아침형이면 아침, 올빼미형이면 밤
    shower_base = tmpl["bedtime_mu"] - 1 if tmpl["bedtime_mu"] > 12 else tmpl["wake_mu"] + 1
    shower_time = _random_time(shower_base, 1.5)

    # 청소 주기
    cleaning_cycle = _wchoice([1, 3, 7, 14, 30], weights=[5, 15, 40, 30, 10])

    # 환기
    ventilation = _wchoice([0.5, 1, 2, 4, 5], weights=[10, 35, 35, 15, 5])

    # 온도 민감도: 정규분포
    temp_pref = _clamp(int(round(random.gauss(3, 1))), 1, 5)

    # 소음 민감도
    noise_sens = _clamp(int(round(random.gauss(3, 1))), 1, 5)

    # 잠귀 & 알람
    sleep_sens = _clamp(int(round(random.gauss(3, 1.2))), 1, 5)
    alarm_str = _clamp(int(round(random.gauss(3, 1))), 1, 5)

    # 친밀도
    intimacy = _wchoice([1, 2, 3, 4, 5], weights=[5, 15, 35, 30, 15])
    meal_tog = _wchoice([1, 2, 3], weights=[20, 45, 35])
    ex_tog = _wchoice([1, 2, 3], weights=[40, 40, 20])
    friend_inv = _wchoice([1, 3, 5], weights=[20, 60, 20])

    return RoommateProfile(
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


def generate_profiles(n: int, seed: int | None = None) -> list[RoommateProfile]:
    """n명의 프로필을 생성합니다."""
    if seed is not None:
        random.seed(seed)
    return [generate_profile() for _ in range(n)]


# ──────────────────────────────────────────────
# 실행 예시
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("룸메이트 프로필 생성기")
    print("=" * 50)

    for persona in ["올빼미형", "아침형", "운동형", "게이머형"]:
        p = generate_profile(persona=persona, seed=42)
        print(f"\n[{persona}]")
        print(f"  이름: {p.name}  학번: {p.student_id}  학과: {p.department}")
        print(f"  취침: {p.bedtime:02d}시  기상: {p.wake_time:02d}시")
        print(f"  주량: {p.alcohol_tolerance}  음주빈도: {p.alcohol_frequency}/5")
        print(f"  게임: 주{p.gaming_hours_per_week}시간  소음민감: {p.noise_sensitivity}/5")
        print(f"  청소주기: {p.cleaning_cycle}일  흡연: {'O' if p.smoking else 'X'}")

    print("\n무작위 5명 생성:")
    profiles = generate_profiles(5, seed=99)
    for p in profiles:
        print(f"  {p.name} | 취침{p.bedtime:02d}시 기상{p.wake_time:02d}시 | "
              f"소음{p.noise_sensitivity}/5 | 친밀도{p.desired_intimacy}/5")
