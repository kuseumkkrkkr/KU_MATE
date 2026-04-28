"""Roommate profile model and vectorization utilities."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
import json
import math
import uuid


@dataclass
class RoommateProfile:
    """Logical model for a roommate checklist entry."""

    # Storage metadata
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    persona: Optional[str] = None  # generator persona tag (optional)

    # 기본 인적 사항
    name: str = ""
    student_id: str = ""
    birth_year: int = 2000
    college: str = ""
    department: str = ""
    dorm_duration: int = 1

    # 생활 습관 (향/음주/운동/게임 등)
    home_visit_cycle: int = 2
    perfume: int = 0
    indoor_scent_sensitivity: int = 3
    alcohol_tolerance: float = 2.5
    alcohol_frequency: int = 2
    drunk_habit: int = 0
    gaming_hours_per_week: int = 10
    speaker_use: int = 0
    exercise: int = 0

    # 수면 습관
    bedtime: int = 24  # 24 means 'unspecified'
    wake_time: int = 8
    sleep_habit: int = 0
    sleep_sensitivity: int = 3
    alarm_strength: int = 3
    sleep_light: int = 0
    snoring: int = 0

    # 위생/욕실 사용
    shower_duration: int = 10
    shower_time: int = 22
    shower_cycle: int = 1
    cleaning_cycle: int = 7
    ventilation: float = 1.0
    hairdryer_in_bathroom: int = 1
    toilet_paper_share: int = 1
    indoor_eating: int = 0
    smoking: int = 0

    # 생활 편의
    temperature_pref: int = 3
    indoor_call: int = 0
    bug_handling: int = 3
    laundry_cycle: int = 7
    drying_rack: int = 1
    fridge_use: int = 1
    study_in_room: int = 0
    noise_sensitivity: int = 3

    # 친밀도/교류
    desired_intimacy: int = 3
    meal_together: int = 2
    exercise_together: int = 1
    friend_invite: int = 3


def _circular_distance(a: int, b: int, period: int = 24) -> float:
    """Circular distance useful for clock time comparisons."""
    diff = abs(a - b) % period
    return min(diff, period - diff)


def profile_to_vector(p: RoommateProfile) -> List[float]:
    """Convert a profile to a normalized vector in fixed order."""
    v: List[float] = []

    # 향/음주/게임
    v.append((p.home_visit_cycle - 1) / 3)
    v.append(float(p.perfume))
    v.append((p.indoor_scent_sensitivity - 1) / 4)
    v.append((p.alcohol_tolerance - 1) / 4)
    v.append((p.alcohol_frequency - 1) / 4)
    v.append(float(p.drunk_habit))
    v.append(p.gaming_hours_per_week / 25)
    v.append(float(p.speaker_use))
    v.append(float(p.exercise))

    # 수면
    v.append(_circular_distance(p.bedtime % 24, 0) / 12)
    v.append(_circular_distance(p.wake_time, 0) / 12)
    v.append(float(p.sleep_habit))
    v.append((p.sleep_sensitivity - 1) / 4)
    v.append((p.alarm_strength - 1) / 4)
    v.append(float(p.sleep_light))
    v.append(float(p.snoring))

    # 위생/욕실
    shower_dur_map = {5: 0, 10: 0.25, 15: 0.5, 20: 0.75, 30: 1.0}
    v.append(shower_dur_map.get(p.shower_duration, 0.25))
    v.append(_circular_distance(p.shower_time, 0) / 12)
    v.append((p.shower_cycle - 1) / 4)
    cleaning_map = {1: 0, 3: 0.25, 7: 0.5, 14: 0.75, 30: 1.0}
    v.append(cleaning_map.get(p.cleaning_cycle, 0.5))
    vent_map = {0.5: 0, 1: 0.25, 2: 0.5, 4: 0.75, 5: 1.0}
    v.append(vent_map.get(p.ventilation, 0.25))
    v.append(float(p.hairdryer_in_bathroom))
    v.append(float(p.toilet_paper_share))
    v.append(float(p.indoor_eating))
    v.append(float(p.smoking))

    # 생활 편의
    v.append((p.temperature_pref - 1) / 4)
    v.append(float(p.indoor_call))
    v.append((p.bug_handling - 1) / 4)
    laundry_map = {14: 0, 7: 0.25, 5: 0.5, 3: 0.75, 1: 1.0}
    v.append(laundry_map.get(p.laundry_cycle, 0.25))
    v.append(float(p.drying_rack))
    v.append(float(p.fridge_use))
    v.append(float(p.study_in_room))
    v.append((p.noise_sensitivity - 1) / 4)

    # 친밀도/교류
    v.append((p.desired_intimacy - 1) / 4)
    v.append((p.meal_together - 1) / 2)
    v.append((p.exercise_together - 1) / 2)
    v.append((p.friend_invite - 1) / 4)

    return v


def profile_to_json(p: RoommateProfile) -> str:
    return json.dumps(asdict(p), ensure_ascii=False, indent=2)


def profile_from_json(s: str) -> RoommateProfile:
    d = json.loads(s)
    return RoommateProfile(**d)


if __name__ == "__main__":
    demo = RoommateProfile(name="테스트", student_id="2021123456")
    vec = profile_to_vector(demo)
    print(f"프로필: {demo.name}")
    print(f"벡터 길이: {len(vec)}")
    print(f"앞 10개 값: {[round(v, 3) for v in vec[:10]]}")

    js = profile_to_json(demo)
    restored = profile_from_json(js)
    print("JSON 직렬화/역직렬화 확인:", restored.name == demo.name)
