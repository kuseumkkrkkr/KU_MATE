# 기숙사 룸메이트 매칭 시스템 - 코드 분석 및 지침

## 📋 프로젝트 개요

**프로젝트명**: Roommate Toolkit  
**목적**: 기숙사 거주자의 생활습관을 기반으로 최적의 룸메이트 매칭을 수행하는 시스템  
**기술스택**: Python, PyQt5, SQLite  
**주요 기능**: 체크리스트 입력, 자동 프로필 생성, 호환성 계산 및 최적 페어링

---

## 🏗️ 시스템 아키텍처

```
사용자 입력 (main.py UI)
    ↓
데이터 모델 (checklist.py)
    ↓
데이터베이스 (db.py) ← → 자동 생성기 (generator.py)
    ↓
매칭 엔진 (matcher.py)
    ↓
매칭 결과 출력 (main.py UI)
```

---

## 📁 파일별 상세 분석

### 1️⃣ **checklist.py** - 프로필 데이터 모델

#### 주요 클래스: `RoommateProfile`
- **목적**: 룸메이트의 모든 정보를 저장하는 데이터 클래스
- **주요 필드** (45개):
  - 기본정보: `name`, `student_id`, `birth_year`, `college`, `department`
  - 생활습관: `home_visit_cycle`, `perfume`, `gaming_hours_per_week`, `speaker_use`
  - 수면습관: `bedtime`, `wake_time`, `sleep_sensitivity`, `snoring`, `alarm_strength`
  - 위생/욕실: `shower_duration`, `shower_cycle`, `cleaning_cycle`, `ventilation`
  - 생활편의: `temperature_pref`, `noise_sensitivity`, `study_in_room`
  - 친밀도: `desired_intimacy`, `meal_together`, `exercise_together`

#### 핵심 함수

**`_circular_distance(a, b, period=24)`**
- 순환 거리 계산 (시간 같은 주기적 데이터용)
- 예: 23시와 1시의 거리 = 2시간

**`profile_to_vector(p: RoommateProfile) → List[float]`**
- 프로필을 정규화된 수치 벡터로 변환
- 벡터 길이: 37개 요소
- 각 값 범위: 0~1 (정규화됨)
- 변환 규칙 예시:
  - `home_visit_cycle` → (값-1)/3 (1~4 범위 → 0~1)
  - `bedtime` → 순환거리/12 (시간 단위)
  - `shower_duration` → 매핑 테이블 (5/10/15/20/30 → 0/0.25/0.5/0.75/1.0)

**`profile_to_json()` / `profile_from_json()`**
- JSON 직렬화/역직렬화 함수

---

### 2️⃣ **db.py** - 데이터베이스 관리

#### 데이터베이스 스키마
- **테이블**: `roommates`
- **기본키**: `uid` (TEXT PRIMARY KEY)
- **제약조건**: `UNIQUE(student_id)` - 학번 중복 방지
- **칼럼 타입**:
  - TEXT: uid, persona, name, student_id, college, department
  - INTEGER: 대부분의 정수 필드
  - REAL: alcohol_tolerance, ventilation

#### 주요 함수

| 함수 | 설명 |
|------|------|
| `init_db(db_path)` | DB 및 테이블 자동 생성 |
| `save_profiles(profiles, db_path)` | 프로필 대량 저장/수정 (INSERT OR REPLACE) |
| `fetch_profiles(db_path)` | 저장된 모든 프로필 조회 |
| `delete_all(db_path)` | 모든 프로필 삭제 |

#### 설계 특징
- **자동 초기화**: 함수 실행 시 DB가 없으면 자동 생성
- **중복 처리**: INSERT OR REPLACE로 기존 학번 데이터 자동 갱신
- **타입 안정성**: 프로필 객체와 DB 칼럼 매핑 (asdict 활용)

---

### 3️⃣ **generator.py** - 프로필 자동 생성

#### 핵심 설정

**`PERSONAS` - 5가지 페르소나 프리셋**

| 타입 | 특징 | bedtime_mu | wake_mu | gaming_w | alcohol_freq_w |
|------|------|-----------|---------|----------|----------------|
| 올빼미형 | 야행성 | 2 | 11 | [5,20,30,25,20] | [10,20,30,25,15] |
| 아침형 | 조기 기상 | 23 | 6 | [30,30,20,15,5] | [30,30,20,15,5] |
| 중간형 | 보통 | 1 | 8 | [15,30,25,20,10] | [20,25,25,20,10] |
| 운동파 | 활동적 | 24 | 7 | [30,30,20,15,5] | [25,30,25,15,5] |
| 집순이형 | 실내활동 | 3 | 11 | [5,10,20,30,35] | [20,25,25,20,10] |

**교육 데이터**
- 단과대: 8개 (공과, 인문, 사회, 자연, 경영, 예술, 체육, 음악)
- 각 단과대별 학과 4~5개 정의
- 한글 이름 조합 (성+이름) → 1000+ 조합

#### 주요 함수

**`_wchoice(population, weights)`**
- 가중치 기반 선택 (확률 샘플링)

**`_random_time(mu, sigma=1.2)`**
- 정규분포 기반 시간 생성
- mu: 평균값, sigma: 표준편차
- 범위 제약: 0~23 (순환)

**`_clamp(val, lo, hi)`**
- 값의 범위 제한

**`generate_profile(persona=None, seed=None)`**
- 단일 프로필 생성
- seed 설정 시 재현 가능한 결과

**`generate_and_store(n, persona=None, seed=None, db_path)`**
- n명 프로필 생성 및 DB 저장

#### 생성 로직

```python
# 사례: 주량 분포
base_alcohol = wchoice([1.0~5.0], weights=[5,10,20,25,20,10,5,3,2])
# 분포: 2.5 중심, 정규분포 형태

# 사례: 시간 생성
bedtime = _random_time(persona_bedtime_mu, sigma=1.2)
# 정규분포에서 샘플링, mod 24로 순환
```

---

### 4️⃣ **matcher.py** - 매칭 엔진

#### 가중치 벡터 (37개 요소)

매칭 점수 계산 시 각 차원에 가중치 적용:

```
향/음주/게임 (9개):    [1.0, 1.5, 2.0, 1.0, 1.5, 2.0, 1.0, 2.0, 0.5]
수면 (7개):          [3.0, 3.0, 2.0, 2.5, 1.5, 1.0, 3.0]
위생 (9개):          [0.5, 1.0, 1.5, 2.0, 1.0, 0.5, 0.5, 2.0, 3.0]
생활 (8개):          [2.5, 1.0, 0.5, 1.0, 0.5, 0.5, 1.0, 2.5]
교류 (4개):          [2.0, 1.0, 0.5, 1.5]
```

**가중치 해석**:
- 높은 값 (3.0): 중요도 높음 (수면, 흡연 등)
- 낮은 값 (0.5): 타협 가능 (샤워 시간, 버그 대응 등)

#### 주요 함수

**`_hard_filters(a, b) → list[str]`**
- 하드 불일치 조건 (호환 불가능):
  1. 흡연/비흡연 불일치
  2. 취침시간 차이 ≥ 5시간
  3. 코골이자 + 수면 예민자 (≥4)

**`_category_score(va, vb) → dict`**
- 5개 카테고리별 매칭 점수 계산:
  - 향/음주/게임, 수면, 위생, 생활, 교류
- 계산식: `(1 - 가중거리/최대가중거리) * 100`

**`match(a, b) → MatchResult`**
- 두 프로필의 호환도 계산
- **점수 범위**: 0~100
  - 90~100: 완벽한 매칭
  - 70~89: 전반적으로 좋음
  - 50~69: 조정 필요
  - 0~49: 주요 불일치 (하드블록 시 -30점 감점)

- **계산 과정**:
  ```
  1. profile_to_vector로 정규화된 벡터 생성 (2개)
  2. 가중치 유클리드 거리 계산
     dist = sqrt(sum(weight[i] * (a[i] - b[i])^2))
  3. 정규화: score = (1 - dist / max_dist) * 100
  4. 하드블록 시 -30점
  ```

**`rank_matches(target, pool, top_n=5, exclude_blocked=False)`**
- target 기준 pool에서 최고 점수 top_n 개 반환
- exclude_blocked=True 시 하드블록 제외

**`best_pairings(profiles, exclude_blocked=True)`**
- 모든 프로필을 최적 페어링 (그리디 알고리즘)
- 높은 점수 순서로 페어링, 이미 짝지어진 사람 제외

#### MatchResult 클래스
```python
@dataclass
class MatchResult:
    profile_a: RoommateProfile
    profile_b: RoommateProfile
    score: float              # 0~100
    distance: float           # 가중거리
    hard_block: bool         # 하드 필터 적용 여부
    block_reasons: list[str] # 불일치 사유
    detail: dict[str, float] # 카테고리별 점수
```

---

### 5️⃣ **main.py** - PyQt5 GUI 애플리케이션

#### 3개 탭 구성

**탭1: 체크리스트 입력 (`ChecklistTab`)**
- 기능:
  - 40개 입력 필드 (텍스트, 스핀박스, 더블스핀박스, 체크박스)
  - 단과대 선택 시 자동으로 학과 갱신
  - 저장 버튼으로 DB에 저장
  - 입력 필드 동적 생성 (`add_spin`, `add_dspin`, `add_check`)

- 주요 입력 필드:
  ```
  필수: 이름(*), 학번(*)
  선택: 페르소나 유형, 단과대, 학과, 기타 40개 항목
  ```

- 유효성 검증: 이름과 학번 필수 입력 확인

**탭2: 자동 생성기 (`GeneratorTab`)**
- 기능:
  - 생성 인원 수 지정 (1~500명)
  - 페르소나 선택 (혼합/올빼미/아침/중간/운동/집순이)
  - Seed 값으로 재현성 보장
  - 한 번에 대량 생성 및 DB 저장

**탭3: 매칭 (`MatcherTab`)**
- 기능:
  - 목표 프로필 선택
  - 강한 불일치 제외 옵션
  - Top N 선택 (1~20)
  - "상위 매칭 계산" 또는 "전체 최적 페어링" 선택

- 상세보기 다이얼로그:
  - 2개 프로필 전체 항목 비교
  - 항목별 차이값 표시 (색상 코딩)
  - 40개 항목을 테이블 형식 표시

#### 주요 디자인 패턴

**동적 UI 생성**
```python
def add_spin(name, label, minimum, maximum, step=1, default=None):
    # 스핀박스 생성 및 필드에 저장
    spin = QtWidgets.QSpinBox()
    # ... 설정
    self.field_widgets[name] = spin
    form_layout.addRow(label, spin)
```

**데이터 수집**
```python
def _collect_profile(self) -> Optional[RoommateProfile]:
    # 모든 필드에서 값 추출
    for key, widget in self.field_widgets.items():
        if isinstance(widget, QtWidgets.QLineEdit):
            # 텍스트 추출
        elif isinstance(widget, QtWidgets.QCheckBox):
            # 체크 여부 추출 (1/0)
```

**상태 동기화**
```python
def refresh_shared_data(self):
    # 다른 탭에서 데이터 변경 시 호출
    self.matcher_tab.reload()
```

---

## 🔄 데이터 흐름

### 프로필 입력 → 저장 → 매칭 흐름

```
1. ChecklistTab에서 40개 항목 입력
   ↓
2. _collect_profile()로 RoommateProfile 생성
   ↓
3. db.save_profiles([profile])로 DB 저장
   ↓
4. refresh_shared_data()로 MatcherTab 갱신
   ↓
5. MatcherTab에서 profile_to_vector() 벡터화
   ↓
6. matcher.match()로 호환도 계산
   ↓
7. 결과 표시
```

### 자동 생성 흐름

```
1. GeneratorTab에서 개수, 페르소나, seed 입력
   ↓
2. generator.generate_and_store() 호출
   ↓
3. generate_profile() 호출 n회
   - 페르소나별 가중치로 샘플링
   - 정규분포로 시간 생성
   - 현실적인 분포 보장
   ↓
4. db.save_profiles()로 일괄 저장
   ↓
5. MatcherTab 자동 갱신
```

---

## ⚙️ 핵심 알고리즘

### 1. 벡터 정규화 (프로필 → 37차원 벡터)

```python
# 예시: 귀가주기 (1~4) → [0, 0.33, 0.67, 1.0]
normalized = (value - 1) / (max - min)

# 예시: 순환 거리 (취침시간)
# 23시와 1시 → 순환거리 2시간 / 12 = 0.167
circular_distance = min(abs(a - b), period - abs(a - b))
normalized = circular_distance / 12

# 예시: 매핑 테이블 (청소주기)
cleaning_map = {1: 0, 3: 0.25, 7: 0.5, 14: 0.75, 30: 1.0}
normalized = cleaning_map.get(value, 0.5)
```

### 2. 호환도 계산 (가중치 유클리드 거리)

```
Step 1: 두 프로필을 벡터로 변환
  va = [0.5, 1.0, 0.25, ..., 0.8] (길이 37)
  vb = [0.3, 0.5, 0.75, ..., 0.6]

Step 2: 가중치 유클리드 거리 계산
  dist = sqrt(sum(w[i] * (va[i] - vb[i])^2 for i in range(37)))
  
  예시 (처음 3개):
  = sqrt(1.0*(0.5-0.3)^2 + 1.5*(1.0-0.5)^2 + 2.0*(0.25-0.75)^2)
  = sqrt(1.0*0.04 + 1.5*0.25 + 2.0*0.25)
  = sqrt(0.04 + 0.375 + 0.5)
  = sqrt(0.915) ≈ 0.957

Step 3: 최대 거리로 정규화
  max_dist = sqrt(sum(weights)) = sqrt(51.5) ≈ 7.177
  
Step 4: 점수로 변환
  score = (1 - dist / max_dist) * 100
  = (1 - 0.957 / 7.177) * 100
  ≈ 86.7 점
```

### 3. 그리디 페어링 알고리즘

```python
def best_pairings(profiles):
    # 모든 가능한 쌍 생성 (N choose 2)
    all_pairs = []
    for i in range(n):
        for j in range(i+1, n):
            r = match(profiles[i], profiles[j])
            all_pairs.append(r)
    
    # 점수 내림차순 정렬
    all_pairs.sort(key=lambda r: r.score, reverse=True)
    
    # 그리디: 이미 배정된 사람은 제외
    matched = set()
    pairings = []
    for r in all_pairs:
        a_id = id(r.profile_a)
        b_id = id(r.profile_b)
        if a_id not in matched and b_id not in matched:
            pairings.append(r)
            matched.add(a_id)
            matched.add(b_id)
    
    return pairings
```

**시간복잡도**: O(n² log n) (모든 쌍 생성 + 정렬)  
**공간복잡도**: O(n²)  
**최적성**: 완전 최적이 아니지만, 실시간 계산 가능

---

## 🎯 주요 지침 및 권장사항

### ✅ 코드 구조 - 좋은 점

1. **모듈화**: 각 파일이 명확한 책임을 가짐
   - checklist.py: 데이터 모델만
   - db.py: 데이터베이스 전용
   - generator.py: 프로필 생성 전용
   - matcher.py: 매칭 로직 전용
   - main.py: UI/오케스트레이션만

2. **데이터 설계**: dataclass 활용으로 타입 안정성 확보

3. **알고리즘 분리**: 벡터화, 거리 계산, 필터링이 명확히 분리됨

4. **GUI 패턴**: 탭 구조로 기능별 분리

### ⚠️ 개선 권장사항

#### 1. **타입 힌팅 강화**
```python
# 현재
def _wchoice(population: list, weights: list):

# 권장
def _wchoice(population: List[Union[int, float]], weights: List[float]) -> Union[int, float]:
```

#### 2. **매직 넘버 상수화**
```python
# 현재
noise_sens = _clamp(int(round(random.gauss(3, 1))), 1, 5)

# 권장
NOISE_SENSITIVITY_MEAN = 3
NOISE_SENSITIVITY_STD = 1.0
NOISE_SENSITIVITY_MIN = 1
NOISE_SENSITIVITY_MAX = 5

noise_sens = _clamp(
    int(round(random.gauss(NOISE_SENSITIVITY_MEAN, NOISE_SENSITIVITY_STD))),
    NOISE_SENSITIVITY_MIN, NOISE_SENSITIVITY_MAX
)
```

#### 3. **예외 처리 추가**
```python
# 현재 - 예외 처리 없음
conn.execute(sql, rows)

# 권장
try:
    conn.execute(sql, rows)
except sqlite3.IntegrityError as e:
    logger.error(f"Duplicate student_id: {e}")
    raise ValueError("학번 중복") from e
```

#### 4. **설정 파일 외부화**
```python
# 권장: config.py 생성
CONFIG = {
    "DB_PATH": "roommates.db",
    "DEFAULT_GENERATION_COUNT": 50,
    "MAX_GENERATION_COUNT": 500,
    "WINDOW_WIDTH": 900,
    "WINDOW_HEIGHT": 700,
    "MATCHING_TOP_N_MAX": 20,
    "MATCHING_PENALTY_HARD_BLOCK": 30,
}
```

#### 5. **로깅 시스템**
```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"저장 완료: {profile.name}")
logger.debug(f"벡터 생성: {len(vec)} 차원")
logger.warning(f"학번 중복 발견: {student_id}")
```

#### 6. **캐싱 최적화**
```python
# 현재: 매칭 계산 시마다 벡터화
# 권장: 프로필당 벡터를 캐싱
@dataclass
class RoommateProfile:
    # ...필드들...
    _vector_cache: Optional[List[float]] = field(default=None, init=False, repr=False)
    
    def get_vector(self) -> List[float]:
        if self._vector_cache is None:
            self._vector_cache = profile_to_vector(self)
        return self._vector_cache
```

#### 7. **테스트 코드 작성**
```python
# tests/test_matcher.py
def test_perfect_match():
    """완벽한 프로필은 점수 100 가까워야 함"""
    p = RoommateProfile(...)
    result = matcher.match(p, p)
    assert result.score >= 99.0

def test_hard_block_smoking():
    """흡연/비흡연 차이는 hard_block"""
    a = RoommateProfile(smoking=1, ...)
    b = RoommateProfile(smoking=0, ...)
    result = matcher.match(a, b)
    assert result.hard_block == True
    assert "흡연/비흡연" in result.block_reasons
```

#### 8. **입력 검증 강화**
```python
# 현재: 기본 검증만
if not name or not sid:
    QtWidgets.QMessageBox.warning(...)

# 권장: 상세 검증
def validate_profile_input(data: dict) -> tuple[bool, str]:
    """
    프로필 입력 검증
    
    Returns:
        (is_valid, error_message)
    """
    if not data.get("name"):
        return False, "이름은 필수입니다."
    if not data.get("student_id"):
        return False, "학번은 필수입니다."
    if len(data.get("student_id", "")) != 10:
        return False, "학번은 10자리여야 합니다 (예: 2021123456)"
    if data.get("birth_year") not in range(1990, 2015):
        return False, "유효하지 않은 출생연도입니다."
    return True, ""
```

#### 9. **성능 최적화 고려**

| 시나리오 | 현재 성능 | 개선방안 |
|---------|---------|--------|
| 1000명 매칭 | ~500ms | 병렬 처리 (multiprocessing) |
| 같은 사람 재매칭 | 벡터 재계산 | 캐싱 |
| 실시간 추천 | DB 조회 + 전체 계산 | 인덱싱, 근처 이웃 검색 |

#### 10. **에러 처리 및 안정성**
```python
# 권장: 안전한 프로필 로드
try:
    profiles = db.fetch_profiles()
    if len(profiles) < 2:
        QtWidgets.QMessageBox.information(self, "정보", "2명 이상 필요합니다.")
        return
except sqlite3.DatabaseError as e:
    QtWidgets.QMessageBox.critical(self, "오류", f"DB 오류: {e}")
    logger.exception("Database error occurred")
    return
```

---

## 📊 데이터 검증 체크리스트

프로필 생성 시 확인사항:

- [ ] 벡터의 모든 값이 [0, 1] 범위인가?
- [ ] 가중치 합이 일정한가? (51.5)
- [ ] 최대 거리는 sqrt(51.5) ≈ 7.177인가?
- [ ] 점수가 [0, 100] 범위인가?
- [ ] hard_block 조건 3가지가 정확히 작동하는가?
- [ ] 같은 프로필 간 매칭은 거의 100점인가?
- [ ] 페어링 개수 = floor(n/2)인가?

---

## 🚀 향후 확장 가능성

1. **추천 엔진**: KNN (K-Nearest Neighbors) 기반 추천
2. **시각화**: 매칭 점수 분포 그래프
3. **포괄성**: 불일치 이유 설명 (XAI)
4. **동적 가중치**: 사용자 피드백 기반 가중치 학습
5. **다국어**: 영어, 중국어 지원
6. **모바일**: 앱 버전
7. **고급 필터링**: 다중 조건 검색
8. **통계**: 페르소나별 분포, 점수 통계

---

## 📝 개발 시 체크리스트

### 코드 추가 시
- [ ] 타입 힌팅 추가
- [ ] docstring 작성
- [ ] 상수화 검토
- [ ] 에러 처리 추가
- [ ] 로깅 추가

### 기능 추가 시
- [ ] 기존 모듈과의 의존성 확인
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 실행
- [ ] 성능 영향 분석

### 배포 전
- [ ] 모든 테스트 통과 확인
- [ ] 코드 리뷰 완료
- [ ] 문서 최신화
- [ ] 백업 생성

---

**문서 작성일**: 2026년 4월 29일  
**작성자**: Code Analysis Agent  
**버전**: 1.0
