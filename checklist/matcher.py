"""
matcher.py
룸메이트 매칭 엔진

가중 유클리드 거리 기반 매칭 +
하드 필터(흡연, 음주버릇) +
절대 불일치 패널티 적용
"""

import math
from dataclasses import dataclass
from checklist import RoommateProfile, profile_to_vector


# ──────────────────────────────────────────────
# 1. 가중치 정의 (벡터 순서와 동일하게 유지)
# ──────────────────────────────────────────────

WEIGHTS = [
    # 생활 패턴
    1.0,  # home_visit_cycle
    1.5,  # perfume
    2.0,  # indoor_scent_sensitivity  ← 냄새 민감도 중요
    1.0,  # alcohol_tolerance
    1.5,  # alcohol_frequency
    2.0,  # drunk_habit               ← 술버릇 중요
    1.0,  # gaming_hours_per_week
    2.0,  # speaker_use               ← 소리 민감도
    0.5,  # exercise

    # 취침 패턴
    3.0,  # bedtime                   ← 수면 시간 최우선
    3.0,  # wake_time
    2.0,  # sleep_habit
    2.5,  # sleep_sensitivity
    1.5,  # alarm_strength
    1.0,  # sleep_light
    3.0,  # snoring                   ← 코골이 매우 중요

    # 청결
    0.5,  # shower_duration
    1.0,  # shower_time
    1.5,  # shower_cycle
    2.0,  # cleaning_cycle
    1.0,  # ventilation
    0.5,  # hairdryer_in_bathroom
    0.5,  # toilet_paper_share
    2.0,  # indoor_eating
    3.0,  # smoking                   ← 흡연 절대 필터와 별도로 가중

    # 기타
    2.5,  # temperature_pref
    1.0,  # indoor_call
    0.5,  # bug_handling
    1.0,  # laundry_cycle
    0.5,  # drying_rack
    0.5,  # fridge_use
    1.0,  # study_in_room
    2.5,  # noise_sensitivity         ← 소음 중요

    # 친밀도
    2.0,  # desired_intimacy
    1.0,  # meal_together
    0.5,  # exercise_together
    1.5,  # friend_invite
]


# ──────────────────────────────────────────────
# 2. 매칭 결과 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class MatchResult:
    profile_a: RoommateProfile
    profile_b: RoommateProfile
    score: float          # 0~100 (100 = 완벽 매칭)
    distance: float       # 가중 유클리드 거리 (낮을수록 좋음)
    hard_block: bool      # 하드 필터에 걸렸는지
    block_reasons: list[str]
    detail: dict[str, float]  # 카테고리별 점수

    def __str__(self) -> str:
        bar_len = int(self.score / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        blocked = f" ⛔ {', '.join(self.block_reasons)}" if self.hard_block else ""
        lines = [
            f"{'─'*50}",
            f"  {self.profile_a.name}  ↔  {self.profile_b.name}",
            f"  [{bar}] {self.score:.1f} / 100{blocked}",
            f"  카테고리별 점수:",
        ]
        for cat, sc in self.detail.items():
            lines.append(f"    {cat:<14}: {sc:.1f}")
        lines.append(f"{'─'*50}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 3. 하드 필터
# ──────────────────────────────────────────────

def _hard_filters(a: RoommateProfile, b: RoommateProfile) -> list[str]:
    """
    절대로 같이 살 수 없는 조건 체크.
    반환값이 빈 리스트면 통과.
    """
    reasons = []
    # 흡연/비흡연 불일치
    if a.smoking != b.smoking:
        reasons.append("흡연 불일치")
    # 코골이 + 잠귀 예민 조합
    if (a.snoring and b.sleep_sensitivity >= 4) or (b.snoring and a.sleep_sensitivity >= 4):
        reasons.append("코골이×잠귀예민")
    # 취침 시간 4시간 이상 차이
    bed_diff = abs(a.bedtime - b.bedtime) % 24
    bed_diff = min(bed_diff, 24 - bed_diff)
    if bed_diff >= 5:
        reasons.append(f"취침시간 {bed_diff}h 차이")
    return reasons


# ──────────────────────────────────────────────
# 4. 카테고리별 점수 계산
# ──────────────────────────────────────────────

def _category_score(va: list[float], vb: list[float]) -> dict[str, float]:
    """각 카테고리의 유사도 점수 (0~100)"""
    slices = {
        "생활패턴": (0, 9),
        "취침패턴": (9, 16),
        "청결":     (16, 25),
        "기타":     (25, 33),
        "친밀도":   (33, 37),
    }
    result = {}
    for name, (s, e) in slices.items():
        w = WEIGHTS[s:e]
        diffs = [abs(va[i] - vb[i]) * w[i - s] for i in range(s, e)]
        max_d = sum(w)
        d = sum(diffs)
        result[name] = round((1 - d / max_d) * 100, 1)
    return result


# ──────────────────────────────────────────────
# 5. 메인 매칭 함수
# ──────────────────────────────────────────────

def match(a: RoommateProfile, b: RoommateProfile) -> MatchResult:
    """두 프로필의 매칭 점수를 계산합니다."""
    va = profile_to_vector(a)
    vb = profile_to_vector(b)

    # 가중 유클리드 거리
    dist = math.sqrt(sum(w * (x - y) ** 2 for w, x, y in zip(WEIGHTS, va, vb)))
    max_dist = math.sqrt(sum(w for w in WEIGHTS))

    # 0~100 점수
    score = (1 - dist / max_dist) * 100

    block_reasons = _hard_filters(a, b)
    if block_reasons:
        score = max(0.0, score - 30)  # 하드 필터 패널티

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


def rank_matches(
    target: RoommateProfile,
    pool: list[RoommateProfile],
    top_n: int = 5,
    exclude_blocked: bool = False,
) -> list[MatchResult]:
    """
    한 명의 프로필과 전체 풀을 매칭하여 상위 N명을 반환합니다.

    Args:
        target:          기준 프로필
        pool:            매칭 대상 풀
        top_n:           상위 N명
        exclude_blocked: 하드 필터 걸린 쌍 제외 여부
    """
    results = [match(target, p) for p in pool if p is not target]
    if exclude_blocked:
        results = [r for r in results if not r.hard_block]
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]


def best_pairings(
    profiles: list[RoommateProfile],
    exclude_blocked: bool = True,
) -> list[MatchResult]:
    """
    전체 풀에서 최적 룸메이트 쌍을 탐욕적으로 배정합니다.
    (각 사람이 한 번씩만 배정)
    """
    n = len(profiles)
    # 모든 쌍의 점수 계산
    all_pairs: list[MatchResult] = []
    for i in range(n):
        for j in range(i + 1, n):
            r = match(profiles[i], profiles[j])
            if exclude_blocked and r.hard_block:
                continue
            all_pairs.append(r)

    all_pairs.sort(key=lambda r: r.score, reverse=True)

    matched = set()
    pairings = []
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


# ──────────────────────────────────────────────
# 실행 예시
# ──────────────────────────────────────────────

if __name__ == "__main__":
    from generator import generate_profiles

    print("=" * 52)
    print("  룸메이트 매칭 엔진 데모")
    print("=" * 52)

    # 10명 생성
    pool = generate_profiles(10, seed=7)
    target = pool[0]

    print(f"\n기준 프로필: {target.name}")
    print(f"  취침 {target.bedtime:02d}시 / 기상 {target.wake_time:02d}시")
    print(f"  소음민감도 {target.noise_sensitivity}/5 / 흡연 {'O' if target.smoking else 'X'}")
    print(f"  친밀도 희망 {target.desired_intimacy}/5\n")

    print("── 상위 5 매칭 결과 ──────────────────────────────")
    results = rank_matches(target, pool[1:], top_n=5)
    for r in results:
        print(r)

    print("\n── 전체 최적 룸메이트 쌍 배정 ───────────────────")
    pairings = best_pairings(pool)
    for i, r in enumerate(pairings, 1):
        status = "⛔" if r.hard_block else "✅"
        print(f"  {i}. {status} {r.profile_a.name} ↔ {r.profile_b.name}  {r.score:.1f}점")
