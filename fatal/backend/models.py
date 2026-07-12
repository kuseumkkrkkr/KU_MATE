"""Data models for roommate matching backend."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
import json
import math
import uuid


@dataclass
class User:
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    login_id: str = ""           # 로그인 ID
    student_id: str = ""         # 학번
    birth_year: int = 2005
    password_hash: str = ""
    name: str = ""
    is_enrolled: int = 1         # 0=일반, 1=대학생
    school_name: str = ""        # 학교명
    college: str = ""            # 단과대학
    department: str = ""         # 학과
    region_name: str = ""        # 지역명
    gender: str = ""             # male | female
    is_suspended: int = 0        # 1=이용 정지


@dataclass
class RoommateProfile:
    """Logical model for a roommate checklist entry."""

    # Storage metadata
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_uid: str = ""
    persona: Optional[str] = None

    # 기본 정보 (User에서 상속)
    name: str = ""
    student_id: str = ""
    birth_year: int = 2005
    college: str = ""
    department: str = ""
    dorm_duration: int = 1

    # New matching protocol fields
    dormitory_hall: str = ""
    matching_phase: str = 'preliminary'     # 'preliminary' | 'main'
    hope_halls: List[str] = field(default_factory=list)  # max 2 in preliminary
    accepted_hall: str = ''                  # 1 in main phase
    room_capacity: int = 2                   # 2, 3, or 4
    preferred_room_type_ids: List[int] = field(default_factory=list)
    fixed_room_type_id: int = 0
    interest_room_type_ids: List[int] = field(default_factory=list)
    fixed_interest_room_type_id: int = 0
    pre_change_count: int = 0
    apply_change_count: int = 0
    pre_last_changed_at: str = ""
    apply_last_changed_at: str = ""
    hall_confirmed_at: str = ""
    non_negotiable_items: List[str] = field(default_factory=list)
    non_negotiable_weights: List[int] = field(default_factory=list)

    # 
    home_visit_cycle: int = 2       # 洹媛 二쇨린 (?쒓컙/二?
    perfume: int = 0
    indoor_scent_sensitivity: int = 3
    alcohol_tolerance: float = 2.5
    alcohol_frequency: int = 2      # ?뚯＜ 鍮덈룄 (二??잛닔)
    drunk_habit: int = 0
    gaming_hours_per_week: int = 10 # 寃뚯엫/?ㅽ겕由?(二?
    speaker_use: int = 0
    exercise: int = 0

    # ?섎㈃ ?듦?
    bedtime: int = 23               # 痍⑥묠?쒓컙 (0-23, 誘몄젙 ??젣)
    wake_time: int = 8
    sleep_habit: int = 0
    sleep_sensitivity: int = 3      # ?섎㈃ ?덈???(?좉?)
    alarm_strength: int = 3         # ?뚮엺 ???ㅼ쓬?
    sleep_light: int = 0            # ?섎㈃??
    snoring: int = 0

    # 
    shower_duration: int = 15       # ?ㅼ썙?쒓컙 5遺꾨떒?? 10,15,20,30,31(30+)
    shower_time: int = 22
    shower_cycle: int = 2           # 0=?섎（2?뚯씠??1=?섎（2??2=?섎（1??3=2????4=3???뚮?留?
    cleaning_cycle: int = 7
    ventilation: float = 1.0
    hairdryer_in_bathroom: int = 1  # ?쒕씪?닿린 ?ㅻ궡?ъ슜
    toilet_paper_share: int = 1
    indoor_eating: int = 0
    smoking: int = 0

    # 
    temperature_pref: int = 3       # 1-5 ?붿쐞 <-> 異붿쐞
    indoor_call: int = 0
    bug_handling: int = 3           # 1-5 ?≪븘 -> 紐살옟??
    laundry_cycle: int = 7
    drying_rack: int = 1
    fridge_use: int = 1
    study_in_room: int = 0          # 湲깆궗??怨듬?
    noise_sensitivity: int = 3

    # 
    desired_intimacy: int = 3       # ?ν썑 猷몃ℓ???移쒕???
    meal_together: int = 2
    exercise_together: int = 1
    friend_invite: int = 1          # 0=X, 1=?ъ쟾?덈씫, 2=??긽


def _circular_distance(a: int, b: int, period: int = 24) -> float:
    diff = abs(a - b) % period
    return min(diff, period - diff)


def classify_persona(p: RoommateProfile) -> str:
    scores = {
        "독서실형": 0,
        "수면민감형": 0,
        "야행성게이머형": 0,
        "공동체형": 0,
    }
    if p.study_in_room:
        scores["독서실형"] += 2
    if p.noise_sensitivity >= 4 or p.indoor_scent_sensitivity >= 4:
        scores["수면민감형"] += 2
    if p.bedtime >= 1 or p.gaming_hours_per_week >= 15:
        scores["야행성게이머형"] += 2
    if p.desired_intimacy >= 4 or p.friend_invite >= 1:
        scores["공동체형"] += 2
    return max(scores, key=scores.get)


def profile_to_vector(p: RoommateProfile) -> List[float]:
    """Convert a profile to a normalized vector in fixed order."""
    v: List[float] = []

    # ???뚯＜/寃뚯엫
    v.append((p.home_visit_cycle) / 4)
    v.append(float(p.perfume))
    v.append((p.indoor_scent_sensitivity - 1) / 4)
    v.append((p.alcohol_tolerance - 1) / 4)
    v.append((p.alcohol_frequency) / 7)
    v.append(float(p.drunk_habit))
    v.append(min(p.gaming_hours_per_week / 40, 1.0))
    v.append(float(p.speaker_use))
    v.append(float(p.exercise))

    # ?섎㈃
    v.append(_circular_distance(p.bedtime % 24, 0) / 12)
    v.append(_circular_distance(p.wake_time, 0) / 12)
    v.append(float(p.sleep_habit))
    v.append((p.sleep_sensitivity - 1) / 4)
    v.append((p.alarm_strength - 1) / 4)
    v.append(float(p.sleep_light))
    v.append(float(p.snoring))

    # ?꾩깮/?뺤떎
    shower_dur_map = {10: 0, 15: 0.25, 20: 0.5, 30: 0.75, 31: 1.0}
    v.append(shower_dur_map.get(p.shower_duration, 0.25))
    v.append(_circular_distance(p.shower_time, 0) / 12)
    v.append(p.shower_cycle / 4)
    cleaning_map = {1: 0, 3: 0.25, 7: 0.5, 14: 0.75, 30: 1.0}
    v.append(cleaning_map.get(p.cleaning_cycle, 0.5))
    vent_map = {0.5: 0, 1: 0.25, 2: 0.5, 4: 0.75, 5: 1.0}
    v.append(vent_map.get(p.ventilation, 0.25))
    v.append(float(p.hairdryer_in_bathroom))
    v.append(float(p.toilet_paper_share))
    v.append(float(p.indoor_eating))
    v.append(float(p.smoking))

    # ?앺솢 ?몄쓽
    v.append((p.temperature_pref - 1) / 4)
    v.append(float(p.indoor_call))
    v.append((p.bug_handling - 1) / 4)
    laundry_map = {14: 0, 7: 0.25, 5: 0.5, 3: 0.75, 1: 1.0}
    v.append(laundry_map.get(p.laundry_cycle, 0.25))
    v.append(float(p.drying_rack))
    v.append(float(p.fridge_use))
    v.append(float(p.study_in_room))
    v.append((p.noise_sensitivity - 1) / 4)

    # 移쒕???援먮쪟
    v.append((p.desired_intimacy - 1) / 4)
    v.append((p.meal_together - 1) / 2)
    v.append((p.exercise_together - 1) / 2)
    v.append(p.friend_invite / 2)

    return v


def profile_to_json(p: RoommateProfile) -> str:
    return json.dumps(asdict(p), ensure_ascii=False)


def profile_from_json(s: str) -> RoommateProfile:
    d = json.loads(s)
    return RoommateProfile(**d)


def profile_to_dict(p: RoommateProfile) -> dict:
    return asdict(p)

