"""Roommate matching utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from checklist import RoommateProfile, profile_to_vector
import db

# Weight vector aligned with profile_to_vector order
WEIGHTS = [
    # 향/음주/게임
    1.0,  # home_visit_cycle
    1.5,  # perfume
    2.0,  # indoor_scent_sensitivity
    1.0,  # alcohol_tolerance
    1.5,  # alcohol_frequency
    2.0,  # drunk_habit
    1.0,  # gaming_hours_per_week
    2.0,  # speaker_use
    0.5,  # exercise
    # 수면
    3.0,  # bedtime
    3.0,  # wake_time
    2.0,  # sleep_habit
    2.5,  # sleep_sensitivity
    1.5,  # alarm_strength
    1.0,  # sleep_light
    3.0,  # snoring
    # 위생
    0.5,  # shower_duration
    1.0,  # shower_time
    1.5,  # shower_cycle
    2.0,  # cleaning_cycle
    1.0,  # ventilation
    0.5,  # hairdryer_in_bathroom
    0.5,  # toilet_paper_share
    2.0,  # indoor_eating
    3.0,  # smoking
    # 생활 편의
    2.5,  # temperature_pref
    1.0,  # indoor_call
    0.5,  # bug_handling
    1.0,  # laundry_cycle
    0.5,  # drying_rack
    0.5,  # fridge_use
    1.0,  # study_in_room
    2.5,  # noise_sensitivity
    # 교류
    2.0,  # desired_intimacy
    1.0,  # meal_together
    0.5,  # exercise_together
    1.5,  # friend_invite
]


@dataclass
class MatchResult:
    profile_a: RoommateProfile
    profile_b: RoommateProfile
    score: float  # 0~100 : 100은 완전 동일, 0은 완전 불일치(하드블록 감점 포함)
    distance: float
    hard_block: bool
    block_reasons: list[str]
    detail: dict[str, float]

    def __str__(self) -> str:
        bar_len = int(self.score / 5)
        bar = "■" * bar_len + "□" * (20 - bar_len)
        blocked = f" ⚠ {', '.join(self.block_reasons)}" if self.hard_block else ""
        lines = [
            f"{'-'*50}",
            f"  {self.profile_a.name}  ↔  {self.profile_b.name}",
            f"  [{bar}] {self.score:.1f} / 100{blocked}",
        ]
        for cat, sc in self.detail.items():
            lines.append(f"    {cat:<14}: {sc:.1f}")
        lines.append(f"{'-'*50}")
        return "\n".join(lines)


def _hard_filters(a: RoommateProfile, b: RoommateProfile) -> list[str]:
    reasons = []
    if a.smoking != b.smoking:
        reasons.append("흡연/비흡연 불일치")
    bed_diff = abs(a.bedtime - b.bedtime) % 24
    bed_diff = min(bed_diff, 24 - bed_diff)
    if bed_diff >= 5:
        reasons.append(f"취침시간 차이 {bed_diff}h")
    if (a.snoring and b.sleep_sensitivity >= 4) or (b.snoring and a.sleep_sensitivity >= 4):
        reasons.append("코골이+예민")
    return reasons


def _category_score(va: list[float], vb: list[float]) -> dict[str, float]:
    slices = {
        "향/음주/게임": (0, 9),
        "수면": (9, 16),
        "위생": (16, 25),
        "생활": (25, 33),
        "교류": (33, 37),
    }
    result = {}
    for name, (s, e) in slices.items():
        w = WEIGHTS[s:e]
        diffs = [abs(va[i] - vb[i]) * w[i - s] for i in range(s, e)]
        max_d = sum(w)
        d = sum(diffs)
        result[name] = round((1 - d / max_d) * 100, 1)
    return result


def match(a: RoommateProfile, b: RoommateProfile) -> MatchResult:
    """
    두 프로필의 호환도를 0~100 점수로 반환한다.

    점수 계산 방식
    - profile_to_vector가 만든 정규화 벡터 간 가중치 유클리드 거리(dist)를 구한다.
    - dist의 최대값으로 나눠 0~1 범위의 유사도로 바꾸고 0~100으로 스케일링.
      => score = (1 - dist / max_dist) * 100
    - 하드 블록 조건이 있을 경우 30점을 감점(최소 0).

    해석
    - 90~100: 매우 높은 유사도, 생활 패턴과 선호가 거의 일치.
    - 70~89: 전반적으로 잘 맞으며 일부 차이는 조정 가능.
    - 50~69: 생활 습관 차이가 있어 합의가 필요.
    - 0~49 : 주요 영역 불일치. 하드 블록이 있으면 30점 패널티가 반영됨.
    """
    va = profile_to_vector(a)
    vb = profile_to_vector(b)
    dist = math.sqrt(sum(w * (x - y) ** 2 for w, x, y in zip(WEIGHTS, va, vb)))
    max_dist = math.sqrt(sum(WEIGHTS))
    score = (1 - dist / max_dist) * 100

    block_reasons = _hard_filters(a, b)
    if block_reasons:
        score = max(0.0, score - 30)
    detail = _category_score(va, vb)

    return MatchResult(
        profile_a=a,
        profile_b=b,
        score=round(score, 2),
        distance=round(dist, 4),
        hard_block=bool(block_reasons),
        block_reasons=block_reasons,
        detail=detail,
    )


def rank_matches(target: RoommateProfile, pool: List[RoommateProfile], top_n: int = 5, exclude_blocked: bool = False) -> List[MatchResult]:
    results = [match(target, p) for p in pool if p is not target]
    if exclude_blocked:
        results = [r for r in results if not r.hard_block]
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]


def best_pairings(profiles: List[RoommateProfile], exclude_blocked: bool = True) -> List[MatchResult]:
    n = len(profiles)
    all_pairs: List[MatchResult] = []
    for i in range(n):
        for j in range(i + 1, n):
            r = match(profiles[i], profiles[j])
            if exclude_blocked and r.hard_block:
                continue
            all_pairs.append(r)

    all_pairs.sort(key=lambda r: r.score, reverse=True)

    matched = set()
    pairings: List[MatchResult] = []
    for r in all_pairs:
        a_id = id(r.profile_a)
        b_id = id(r.profile_b)
        if a_id not in matched and b_id not in matched:
            pairings.append(r)
            matched.add(a_id)
            matched.add(b_id)
        if len(matched) >= n:
            break
    return pairings


# DB convenience wrappers
def load_profiles(db_path: str = db.DB_PATH) -> List[RoommateProfile]:
    return db.fetch_profiles(db_path=db_path)


def best_pairings_from_db(db_path: str = db.DB_PATH, exclude_blocked: bool = True) -> List[MatchResult]:
    profiles = load_profiles(db_path)
    return best_pairings(profiles, exclude_blocked=exclude_blocked)


if __name__ == "__main__":
    db.init_db()
    profiles = db.fetch_profiles()
    if len(profiles) < 2:
        print("DB에 2명 이상이 필요합니다. generator.py를 먼저 실행하세요.")
    else:
        pairs = best_pairings(profiles)
        for r in pairs:
            print(r)
