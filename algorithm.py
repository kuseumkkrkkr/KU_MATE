import numpy as np
from typing import List, Dict

# -----------------------------
# 1. 설정값
# -----------------------------
W_BASE = 1.0
W_CRITICAL = 5.0
CRITICAL_MISMATCH_PENALTY = 0.5  # 유사도에 곱해짐

# -----------------------------
# 2. 유저 데이터 예시
# -----------------------------
users = [
    {
        "id": "A",
        "vector": np.array([2, 3, 3, 1, 5]),
        "critical": [0, 3]  # 절대 중요 항목 index
    },
    {
        "id": "B",
        "vector": np.array([5, 1, 1, 1, 5]),
        "critical": [0]
    },
    {
        "id": "C",
        "vector": np.array([2, 2, 3, 1, 4]),
        "critical": [3]
    },
    {
        "id": "D",
        "vector": np.array([2, 3, 3, 2, 5]),
        "critical": []
    }
]

# -----------------------------
# 3. 가중치 생성 함수
# -----------------------------
def get_weights(n: int, critical_indices: List[int]) -> np.ndarray:
    weights = np.ones(n) * W_BASE
    for i in critical_indices:
        weights[i] = W_CRITICAL
    return weights

# -----------------------------
# 4. 가중 코사인 유사도
# -----------------------------
def weighted_cosine_similarity(A, B, weights):
    numerator = np.sum(weights * A * B)
    denominator = np.sqrt(np.sum(weights * A**2)) * np.sqrt(np.sum(weights * B**2))
    
    if denominator == 0:
        return 0
    
    return numerator / denominator

# -----------------------------
# 5. critical mismatch 패널티
# -----------------------------
def apply_critical_penalty(A, B, crit_A, crit_B):
    mismatch = False
    
    for idx in set(crit_A + crit_B):
        if A[idx] != B[idx]:
            mismatch = True
            break
    
    return CRITICAL_MISMATCH_PENALTY if mismatch else 1.0

# -----------------------------
# 6. 매칭 점수 계산
# -----------------------------
def match_score(user1, user2):
    A = user1["vector"]
    B = user2["vector"]
    
    # 가중치는 두 사람 union 기준
    critical_union = list(set(user1["critical"] + user2["critical"]))
    weights = get_weights(len(A), critical_union)
    
    sim = weighted_cosine_similarity(A, B, weights)
    
    penalty = apply_critical_penalty(A, B, user1["critical"], user2["critical"])
    
    return sim * penalty

# -----------------------------
# 7. 전체 매칭
# -----------------------------
def find_matches(users: List[Dict], top_n=3):
    results = {}
    
    for i, u1 in enumerate(users):
        scores = []
        
        for j, u2 in enumerate(users):
            if i == j:
                continue
            
            score = match_score(u1, u2)
            scores.append((u2["id"], score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        results[u1["id"]] = scores[:top_n]
    
    return results

# -----------------------------
# 8. 실행
# -----------------------------
matches = find_matches(users)

for user_id, recs in matches.items():
    print(f"\nUser {user_id} 추천:")
    for target, score in recs:
        print(f"  -> {target} (score: {score:.4f})")