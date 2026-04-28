"""
roommate_checklist.py
룸메이트 체크리스트 데이터 구조 정의 및 벡터화 로직
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import math


# ──────────────────────────────────────────────
# 1. 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class RoommateProfile:
    """룸메이트 체크리스트 전체 프로필"""

    # ── 개인정보 (매칭 제외) ──────────────────
    name: str = ""
    student_id: str = ""          # 학번 (OUT: 매칭 미사용)
    birth_year: int = 2000        # 생년 (강제고정, OUT)
    college: str = ""             # 단과대
    department: str = ""          # 소속학과
    dorm_duration: int = 1        # 기숙사 거주기간(학기수, OUT)

    # ── 생활 패턴 ────────────────────────────
    home_visit_cycle: int = 2     # 본가 가는 주기: 1=1주, 2=2주, 3=3주, 4=한달이상
    perfume: int = 0              # 향수: 0=X, 1=O
    indoor_scent_sensitivity: int = 3   # 실내향 민감도 1-5
    alcohol_tolerance: float = 2.5      # 주량 1-5 (0.5단위)
    alcohol_frequency: int = 2          # 음주빈도 1=한달 2=2주 3=1주 4=3일 5=1일
    drunk_habit: int = 0                # 술버릇: 0=X, 1=O
    gaming_hours_per_week: int = 10     # 게임/디스코드 주당 시간: 5,10,15,20,25
    speaker_use: int = 0                # 스피커: 0=이어폰, 1=스피커
    exercise: int = 0                   # 운동: 0=X, 1=O

    # ── 취침 패턴 ────────────────────────────
    # 취침/기상 시간: 실제 시각(0-23)으로 저장
    bedtime: int = 24              # 취침 시간 (24=자정)
    wake_time: int = 8             # 기상 시간
    sleep_habit: int = 0           # 잠버릇: 0=X, 1=O
    sleep_sensitivity: int = 3     # 잠귀 1-5 (1=둔감, 5=예민)
    alarm_strength: int = 3        # 알람 크기 1-5 (1=약, 5=강)
    sleep_light: int = 0           # 수면등: 0=X, 1=O
    snoring: int = 0               # 코골이/이갈이/잠꼬대: 0=X, 1=O

    # ── 청결 ─────────────────────────────────
    # 샤워 시간(분): 5,10,15,20,30
    shower_duration: int = 10
    # 샤워 시각: 실제 시각(0-23)
    shower_time: int = 22
    # 샤워 주기: 1=매일1회, 2=매일2회, 3=매일3회, 4=2일에1번, 5=3일에1번
    shower_cycle: int = 1
    # 청소 주기: 1=1일, 3=3일, 7=1주, 14=2주, 30=한달
    cleaning_cycle: int = 7
    # 환기 (하루 횟수): 0.5, 1, 2, 4, 5
    ventilation: float = 1.0
    hairdryer_in_bathroom: int = 1  # 드라이기 화장실 사용: 0=X, 1=O
    toilet_paper_share: int = 1     # 휴지 공동: 0=각자, 1=공동
    indoor_eating: int = 0          # 실내 취식: 0=X, 1=O
    smoking: int = 0                # 흡연: 0=X, 1=O

    # ── 기타 ─────────────────────────────────
    temperature_pref: int = 3       # 온도 1=더위탐 ~ 5=추위탐
    indoor_call: int = 0            # 실내 통화: 0=X, 1=O
    bug_handling: int = 3           # 벌레 처리 1=잘잡음 ~ 5=못잡음
    laundry_cycle: int = 7          # 빨래 주기(일): 14=2주,7=1주,5=5일,3=3일,1=1일
    drying_rack: int = 1            # 건조대 사용: 0=X, 1=O
    fridge_use: int = 1             # 냉장고 사용: 0=X, 1=O
    study_in_room: int = 0          # 방에서 공부: 0=X, 1=O
    noise_sensitivity: int = 3      # 소음 민감도 1-5

    # ── 친밀도 ────────────────────────────────
    desired_intimacy: int = 3       # 룸메와 희망 친밀도 1-5
    meal_together: int = 2          # 학식 같이: 1=x, 2=종종, 3=자주 (내부 1-5 → 표시용)
    exercise_together: int = 1      # 운동 같이: 1=x, 2=종종, 3=자주
    friend_invite: int = 3          # 친구 초대: 1=항상가능, 3=사전허락, 5=X


# ──────────────────────────────────────────────
# 2. 벡터화 함수
# ──────────────────────────────────────────────

def _circular_distance(a: int, b: int, period: int = 24) -> float:
    """원형 거리 (시간 비교용)"""
    diff = abs(a - b) % period
    return min(diff, period - diff)


def profile_to_vector(p: RoommateProfile) -> list[float]:
    """
    프로필을 정규화된 벡터로 변환 (매칭에 사용되는 항목만)
    모든 값을 0~1 범위로 정규화
    """
    v = []

    # 생활 패턴
    v.append((p.home_visit_cycle - 1) / 3)          # 1-4 → 0-1
    v.append(p.perfume)                              # 0/1
    v.append((p.indoor_scent_sensitivity - 1) / 4)  # 1-5
    v.append((p.alcohol_tolerance - 1) / 4)         # 1-5
    v.append((p.alcohol_frequency - 1) / 4)         # 1-5
    v.append(p.drunk_habit)
    v.append(p.gaming_hours_per_week / 25)           # 5-25
    v.append(p.speaker_use)
    v.append(p.exercise)

    # 취침 패턴 (원형 → 선형화 후 정규화)
    v.append(_circular_distance(p.bedtime % 24, 0) / 12)
    v.append(_circular_distance(p.wake_time, 0) / 12)
    v.append(p.sleep_habit)
    v.append((p.sleep_sensitivity - 1) / 4)
    v.append((p.alarm_strength - 1) / 4)
    v.append(p.sleep_light)
    v.append(p.snoring)

    # 청결
    shower_dur_map = {5: 0, 10: 0.25, 15: 0.5, 20: 0.75, 30: 1.0}
    v.append(shower_dur_map.get(p.shower_duration, 0.25))
    v.append(_circular_distance(p.shower_time, 0) / 12)
    v.append((p.shower_cycle - 1) / 4)              # 1-5
    cleaning_map = {1: 0, 3: 0.25, 7: 0.5, 14: 0.75, 30: 1.0}
    v.append(cleaning_map.get(p.cleaning_cycle, 0.5))
    vent_map = {0.5: 0, 1: 0.25, 2: 0.5, 4: 0.75, 5: 1.0}
    v.append(vent_map.get(p.ventilation, 0.25))
    v.append(p.hairdryer_in_bathroom)
    v.append(p.toilet_paper_share)
    v.append(p.indoor_eating)
    v.append(p.smoking)

    # 기타
    v.append((p.temperature_pref - 1) / 4)
    v.append(p.indoor_call)
    v.append((p.bug_handling - 1) / 4)
    laundry_map = {14: 0, 7: 0.25, 5: 0.5, 3: 0.75, 1: 1.0}
    v.append(laundry_map.get(p.laundry_cycle, 0.25))
    v.append(p.drying_rack)
    v.append(p.fridge_use)
    v.append(p.study_in_room)
    v.append((p.noise_sensitivity - 1) / 4)

    # 친밀도
    v.append((p.desired_intimacy - 1) / 4)
    v.append((p.meal_together - 1) / 2)
    v.append((p.exercise_together - 1) / 2)
    v.append((p.friend_invite - 1) / 4)

    return v


# ──────────────────────────────────────────────
# 3. JSON 직렬화/역직렬화
# ──────────────────────────────────────────────

def profile_to_json(p: RoommateProfile) -> str:
    return json.dumps(asdict(p), ensure_ascii=False, indent=2)


def profile_from_json(s: str) -> RoommateProfile:
    d = json.loads(s)
    return RoommateProfile(**d)


# ──────────────────────────────────────────────
# 4. 간단한 사용 예시
# ──────────────────────────────────────────────

if __name__ == "__main__":
    p = RoommateProfile(name="홍길동", student_id="2021123456")
    vec = profile_to_vector(p)
    print(f"프로필 이름: {p.name}")
    print(f"벡터 길이:   {len(vec)}")
    print(f"벡터 (앞 10개): {[round(v, 3) for v in vec[:10]]}")
    print()
    js = profile_to_json(p)
    p2 = profile_from_json(js)
    print(f"JSON 직렬화 → 역직렬화 확인: {p2.name}")
