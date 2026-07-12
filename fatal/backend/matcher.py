import math
import random
from dataclasses import dataclass, asdict
from typing import List

from models import RoommateProfile, profile_to_vector, classify_persona

PERSONA_ALIAS = {
    "study_focused": "독서실형",
    "sensitive": "수면민감형",
    "night_owl": "야행성게이머형",
    "social": "공동체형",
    "학습집중형": "독서실형",
    "섬세감성형": "수면민감형",
    "FM관리형": "FM군대형",
}


def normalize_persona(key: str) -> str:
    return PERSONA_ALIAS.get(key, key)

# 기숙사 건물 목록
DORMITORY_HALLS = ["자유관", "정의관", "진리관", "미래관"]

# 매칭 티어 설정: (최소점수, 최대점수, 선택 인원)
# Target: 90-100:1, 80-90:2, 60-80:2 with downward substitution
TIER_CONFIG = [
    (90.0, 100.0, 1),   # Tier S: 1 candidate
    (80.0, 90.0, 2),    # Tier A: 2 candidates
    (60.0, 80.0, 2),    # Tier B: 2 candidates
]

# 기본 가중치 (37차원)
WEIGHTS = [
    1.0,  # home_visit_cycle
    1.5,  # perfume
    2.0,  # indoor_scent_sensitivity
    1.0,  # alcohol_tolerance
    1.5,  # alcohol_frequency
    2.0,  # drunk_habit
    1.0,  # gaming_hours_per_week
    2.0,  # speaker_use
    0.5,  # exercise
    3.0,  # bedtime
    3.0,  # wake_time
    2.0,  # sleep_habit
    2.5,  # sleep_sensitivity
    1.5,  # alarm_strength
    1.0,  # sleep_light
    3.0,  # snoring
    0.5,  # shower_duration
    1.0,  # shower_time
    1.5,  # shower_cycle
    2.0,  # cleaning_cycle
    1.0,  # ventilation
    0.5,  # hairdryer_in_bathroom
    0.5,  # toilet_paper_share
    2.0,  # indoor_eating
    3.0,  # smoking
    2.5,  # temperature_pref
    1.0,  # indoor_call
    0.5,  # bug_handling
    1.0,  # laundry_cycle
    0.5,  # drying_rack
    0.5,  # fridge_use
    1.0,  # study_in_room
    2.5,  # noise_sensitivity
    2.0,  # desired_intimacy
    1.0,  # meal_together
    0.5,  # exercise_together
    1.5,  # friend_invite
]

# 특성 인덱스 매핑 (non_negotiable weight 조정용)
FEATURE_INDEX = {
    "home_visit_cycle": 0,
    "perfume": 1,
    "indoor_scent_sensitivity": 2,
    "alcohol_tolerance": 3,
    "alcohol_frequency": 4,
    "drunk_habit": 5,
    "gaming_hours_per_week": 6,
    "speaker_use": 7,
    "exercise": 8,
    "bedtime": 9,
    "wake_time": 10,
    "sleep_habit": 11,
    "sleep_sensitivity": 12,
    "alarm_strength": 13,
    "sleep_light": 14,
    "snoring": 15,
    "shower_duration": 16,
    "shower_time": 17,
    "shower_cycle": 18,
    "cleaning_cycle": 19,
    "ventilation": 20,
    "hairdryer_in_bathroom": 21,
    "toilet_paper_share": 22,
    "indoor_eating": 23,
    "smoking": 24,
    "temperature_pref": 25,
    "indoor_call": 26,
    "bug_handling": 27,
    "laundry_cycle": 28,
    "drying_rack": 29,
    "fridge_use": 30,
    "study_in_room": 31,
    "noise_sensitivity": 32,
    "desired_intimacy": 33,
    "meal_together": 34,
    "exercise_together": 35,
    "friend_invite": 36,
}


def _apply_non_negotiable_weights(base_weights, items, weights):
    """non_negotiable 항목에 따라 가중치를 동적으로 조정한다."""
    w = list(base_weights)
    items = items or []
    weights = weights or []
    for item, imp in zip(items, weights):
        idx = FEATURE_INDEX.get(item)
        if idx is not None:
            # 중요도 1~5 → 1.5배 ~ 3.5배
            w[idx] *= (1 + imp * 0.5)
    return w


def prefilter_pool(target, pool, min_persona_compat=0.3):
    """기숙사 희망/확정 건물 + 페르소나 호환성 + 인원수 임계값으로 사전 필터링."""
    filtered = []
    for p in pool:
        if p.uid == target.uid:
            continue
        # 동일 기숙사 건물 필수 (legacy dormitory_hall or new hope_halls/accepted_hall)
        if not _hall_compatible(target, p):
            continue
        # 인원수 호환 (2-person rooms only match individuals; 3/4-person rooms allow teams)
        if target.room_capacity != p.room_capacity:
            continue
        # 페르소나 호환성 임계값
        pa = normalize_persona(target.persona or classify_persona(target))
        pb = normalize_persona(p.persona or classify_persona(p))
        compat = PERSONA_COMPATIBILITY.get(pa, {}).get(pb, 0.5)
        if compat < min_persona_compat:
            continue
        filtered.append(p)
    return filtered


def _hall_compatible(a: RoommateProfile, b: RoommateProfile) -> bool:
    """Check if two profiles are compatible by dormitory hall selection."""
    # Use accepted_hall if in main phase, otherwise use hope_halls overlap
    a_halls = _effective_halls(a)
    b_halls = _effective_halls(b)
    # Must share at least one hall
    return bool(set(a_halls) & set(b_halls))


def _effective_halls(p: RoommateProfile) -> list:
    """Return the effective hall list for a profile based on matching phase."""
    if p.matching_phase == 'main' and p.accepted_hall:
        return [p.accepted_hall]
    if p.hope_halls:
        return p.hope_halls
    # Legacy fallback
    if p.dormitory_hall:
        return [p.dormitory_hall]
    return DORMITORY_HALLS  # No preference = all halls


def select_by_tiers(results, tiers=None):
    """점수별 티어에서 랜덤 샘플링으로 최종 후보를 선정한다.
    Downward substitution: if a tier is empty, fill from next lower tier."""
    if tiers is None:
        tiers = TIER_CONFIG
    buckets = {i: [] for i in range(len(tiers))}
    for r in results:
        for i, (lo, hi, _) in enumerate(tiers):
            if lo <= r.score < hi:
                buckets[i].append(r)
                break
        else:
            # Below lowest tier - add to last bucket
            buckets[len(tiers) - 1].append(r)

    selected = []
    deficit = 0
    for i, (_, _, count) in enumerate(tiers):
        pool = buckets[i]
        needed = count + deficit
        if len(pool) <= needed:
            selected.extend(pool)
            deficit = needed - len(pool)
        else:
            selected.extend(random.sample(pool, needed))
            deficit = 0

    selected.sort(key=lambda r: r.score, reverse=True)
    return selected

PERSONA_COMPATIBILITY = {
    "독서실형":      {"독서실형": 1.0, "자취감성형": 0.8, "야행성게이머형": 0.1, """
                     "FM군대형": 0.7, "생존형": 0.4, "공동체형": 0.3, "생활분리형": 0.9, "수면민감형": 0.8},
    "자취감성형":    {"독서실형": 0.8, "자취감성형": 1.0, "야행성게이머형": 0.3, "FM군대형": 0.6, """
                     "생존형": 0.5, "공동체형": 0.7, "생활분리형": 0.7, "수면민감형": 0.7},
    "야행성게이머형": {"독서실형": 0.1, "자취감성형": 0.3, "야행성게이머형": 0.9, "FM군대형": 0.1, """
                     "생존형": 0.5, "공동체형": 0.6, "생활분리형": 0.4, "수면민감형": 0.1},
    "FM군대형":     {"독서실형": 0.7, "자취감성형": 0.6, "야행성게이머형": 0.1, "FM군대형": 0.8, """
                     "생존형": 0.4, "공동체형": 0.6, "생활분리형": 0.8, "수면민감형": 0.6},
    "생존형":       {"독서실형": 0.4, "자취감성형": 0.5, "야행성게이머형": 0.5, "FM군대형": 0.4, """
                     "생존형": 0.9, "공동체형": 0.5, "생활분리형": 0.7, "수면민감형": 0.5},
    "공동체형":     {"독서실형": 0.3, "자취감성형": 0.7, "야행성게이머형": 0.6, "FM군대형": 0.6, """
                     "생존형": 0.5, "공동체형": 0.9, "생활분리형": 0.2, "수면민감형": 0.4},
    "생활분리형":   {"독서실형": 0.9, "자취감성형": 0.7, "야행성게이머형": 0.4, "FM군대형": 0.8, """
                     "생존형": 0.7, "공동체형": 0.2, "생활분리형": 1.0, "수면민감형": 0.8},
    "수면민감형":   {"독서실형": 0.8, "자취감성형": 0.7, "야행성게이머형": 0.1, "FM군대형": 0.6, """
                     "생존형": 0.5, "공동체형": 0.4, "생활분리형": 0.8, "수면민감형": 1.0},
}


@dataclass
class MatchResult:
    profile_a: RoommateProfile
    profile_b: RoommateProfile
    score: float
    distance: float
    hard_block: bool
    block_reasons: list[str]
    detail: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "profile_a": profile_to_dict(self.profile_a),
            "profile_b": profile_to_dict(self.profile_b),
            "score": self.score,
            "distance": self.distance,
            "hard_block": self.hard_block,
            "block_reasons": self.block_reasons,
            "detail": self.detail,
        }


def profile_to_dict(p: RoommateProfile) -> dict:
    return asdict(p)


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


def _persona_bonus(a: RoommateProfile, b: RoommateProfile) -> float:
    pa = normalize_persona(a.persona or classify_persona(a))
    pb = normalize_persona(b.persona or classify_persona(b))
    compat = PERSONA_COMPATIBILITY.get(pa, {}).get(pb, 0.5)
    return compat


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
    # 양측 non_negotiable 가중치를 모두 반영한 평균 가중치 사용
    weights_a = _apply_non_negotiable_weights(WEIGHTS, a.non_negotiable_items, a.non_negotiable_weights)
    weights_b = _apply_non_negotiable_weights(WEIGHTS, b.non_negotiable_items, b.non_negotiable_weights)
    weights = [(wa + wb) / 2 for wa, wb in zip(weights_a, weights_b)]

    va = profile_to_vector(a)
    vb = profile_to_vector(b)
    dist = math.sqrt(sum(w * (x - y) ** 2 for w, x, y in zip(weights, va, vb)))
    max_dist = math.sqrt(sum(weights))
    score = (1 - dist / max_dist) * 100

    block_reasons = _hard_filters(a, b)
    if block_reasons:
        score = max(0.0, score - 30)

    compat = _persona_bonus(a, b)
    compat_adj = (compat - 0.5) * 20
    score = min(100.0, max(0.0, score + compat_adj))

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
    """Generate ranked match candidates with tier-based pool refresh."""
    # Handle team rematching: if target is a team entry, use its averaged profile
    filtered = prefilter_pool(target, pool)
    results = [match(target, p) for p in filtered]
    if exclude_blocked:
        results = [r for r in results if not r.hard_block]
    results.sort(key=lambda r: r.score, reverse=True)
    return select_by_tiers(results)[:top_n]


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
        a_id = r.profile_a.uid
        b_id = r.profile_b.uid
        if a_id not in matched and b_id not in matched:
            pairings.append(r)
            matched.add(a_id)
            matched.add(b_id)
        if len(matched) >= n:
            break
    return pairings


def _team_rematch_entry(pre_matched_pair: list[RoommateProfile]) -> RoommateProfile:
    """Create a virtual profile representing a pre-matched 2-person team.
    Averaged scores are used for matching into 3/4-person rooms."""
    if len(pre_matched_pair) != 2:
        raise ValueError("Team rematch requires exactly 2 pre-matched profiles")
    a, b = pre_matched_pair
    # Create averaged profile for team matching
    team = RoommateProfile(
        uid=f"team_{a.uid}_{b.uid}",
        user_uid=f"team_{a.user_uid}_{b.user_uid}",
        name=f"{a.name},{b.name}",
        persona=normalize_persona(a.persona or classify_persona(a)),
        matching_phase=a.matching_phase,
        hope_halls=list(set(a.hope_halls) & set(b.hope_halls)) or a.hope_halls,
        accepted_hall=a.accepted_hall or b.accepted_hall,
        room_capacity=max(a.room_capacity, b.room_capacity),
    )
    # Average all numeric lifestyle fields
    numeric_fields = [
        'birth_year', 'dorm_duration', 'home_visit_cycle', 'perfume',
        'indoor_scent_sensitivity', 'alcohol_tolerance', 'alcohol_frequency',
        'drunk_habit', 'gaming_hours_per_week', 'speaker_use', 'exercise',
        'bedtime', 'wake_time', 'sleep_habit', 'sleep_sensitivity',
        'alarm_strength', 'sleep_light', 'snoring', 'shower_duration',
        'shower_time', 'shower_cycle', 'cleaning_cycle', 'ventilation',
        'hairdryer_in_bathroom', 'toilet_paper_share', 'indoor_eating',
        'smoking', 'temperature_pref', 'indoor_call', 'bug_handling',
        'laundry_cycle', 'drying_rack', 'fridge_use', 'study_in_room',
        'noise_sensitivity', 'desired_intimacy', 'meal_together',
        'exercise_together', 'friend_invite',
    ]
    for field in numeric_fields:
        va = getattr(a, field, 0)
        vb = getattr(b, field, 0)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            setattr(team, field, (va + vb) / 2)
    return team
