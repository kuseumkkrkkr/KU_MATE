# 기숙사 룸메이트 매칭 시스템 (Roomantic) - 전체 코드 분석

## 프로젝트 개요

**프로젝트명**: Roomantic  
**목적**: 기숙사 거주자의 생활습관을 기반으로 최적의 룸메이트 매칭을 수행하는 플랫폼  
**버전**: Beta (2026년 5월 오픈)  
**주요 기능**: 체크리스트 입력, 자동 프로필 생성, 호환성 계산, 티어 기반 매칭, 채팅, 방 공동체(Life Room), 관리자 대시보드

---

## 시스템 아키텍처 (3-Tier)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Flutter Frontend                                 │
│  lib/main.dart → GetX (Auth/Match/Profile Controller)                  │
│  Screens: Home, Match, Chat, Survey, Profile, LifeRoom, Admin, ...    │
│  Services: ApiService (Dio HTTP), ChatLocalStore, SSE Stream            │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP REST + SSE (port 5000)
┌──────────────────────────────▼──────────────────────────────────────────┐
│                        Flask Backend                                    │
│  backend/app.py (3650 lines, ~72KB) — 모든 API 엔드포인트               │
│  backend/auth.py — JWT 인증 (HS256, 7일 만료)                           │
│  backend/models.py — User, RoommateProfile 데이터클래스 + 벡터화         │
│  backend/matcher.py — 가중치 거리 매칭 + 티어 + 페르소나 + 팀 리매치    │
│  backend/db.py — SQLite (roommates_api.db + schools.db)                │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ SQLite
┌──────────────────────────────▼──────────────────────────────────────────┐
│  roommates_api.db: users, profiles, match_sessions, chat_threads, ...  │
│  schools.db: schools, dormitories, colleges, departments, room_types    │
└─────────────────────────────────────────────────────────────────────────┘

[독립 레이어]
┌─────────────────────────────────────────────────────────────────────────┐
│  Root (PyQt5 Desktop)   │  Simulation Layer                            │
│  main.py + checklist.py │  simulation/main.py + generator.py           │
│  generator.py + matcher.py + db.py                                     │
│  → 단일 SQLite 파일 (roommates.db / simulation.db)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
fatal/
├── main.py                  # PyQt5 데스크탑 UI (체크리스트/생성기/매칭)
├── checklist.py             # RoommateProfile 데이터클래스 + 벡터화
├── generator.py             # 페르소나 기반 프로필 자동 생성
├── matcher.py               # 가중치 유클리드 거리 매칭
├── db.py                    # SQLite CRUD (단일 테이블)
├── CODE_ANALYSIS.md         # 이 파일
│
├── backend/
│   ├── app.py               # Flask API — 모든 엔드포인트 (3650줄)
│   ├── auth.py              # JWT 인증 + salted SHA-256 비밀번호
│   ├── models.py            # User, RoommateProfile + profile_to_vector()
│   ├── matcher.py           # 고급 매칭 엔진 (티어, 페르소나, non_negotiable)
│   └── db.py                # SQLite 스키마 관리 + CRUD (~714줄)
│
├── frontend/
│   └── dorm_match/lib/
│       ├── main.dart             # GetMaterialApp 진입점
│       ├── controllers/          # Auth, Match, Profile Controller (GetX)
│       ├── models/               # User, Profile (Dart)
│       ├── screens/              # 21개 화면 (Home, Match, Chat, Survey...)
│       ├── services/             # ApiService (Dio), ChatLocalStore
│       ├── utils/                 # persona_scoring, match_ui_helper
│       └── widgets/               # sleep_wake_range_slider
│
├── simulation/
│   ├── main.py              # PyQt5 UI (root/main.py의 미러)
│   ├── generator.py         # 시뮬레이션 전용 프로필 생성기
│   └── (db.py, matcher.py는 루트 모듈 재사용 또는 simulation.db 사용)
│
└── obsidian/                # 기획 문서 (Roomantic)
```

---

## 파트 1: 루트 레이어 (PyQt5 데스크탑)

### checklist.py — 프로필 데이터 모델

**주요 클래스**: `RoommateProfile` (dataclass, 45개 필드)

| 카테고리 | 필드 | 비고 |
|---------|------|------|
| 기본정보 | `name`, `student_id`, `birth_year`, `college`, `department` | |
| 생활습관 | `home_visit_cycle`, `perfume`, `gaming_hours_per_week`, `speaker_use` | |
| 수면 | `bedtime`, `wake_time`, `sleep_sensitivity`, `snoring`, `alarm_strength` | |
| 위생/욕실 | `shower_duration`, `shower_cycle`, `cleaning_cycle`, `ventilation` | |
| 생활편의 | `temperature_pref`, `noise_sensitivity`, `study_in_room` | |
| 친밀도 | `desired_intimacy`, `meal_together`, `exercise_together` | |

**핵심 함수**:

- `profile_to_vector(p) → List[float]` (37차원, 0~1 정규화)
  - 순환 거리: `_circular_distance(a, b, period=24)` — 시간 데이터용
  - 매핑 테이블: `shower_duration`, `cleaning_cycle`, `ventilation`, `laundry_cycle`
- `profile_to_json()` / `profile_from_json()` — JSON 직렬화

### db.py — 단순 SQLite CRUD

- 테이블: `roommates` (단일)
- 기본키: `uid` (TEXT)
- 제약조건: `UNIQUE(student_id)`
- 함수: `init_db()`, `save_profiles()`, `fetch_profiles()`, `delete_all()`
- INSERT OR REPLACE로 중복 시 자동 갱신

### generator.py — 프로필 자동 생성

**5가지 페르소나 프리셋**:

| 타입 | bedtime_mu | wake_mu | gaming_w | 특징 |
|------|-----------|---------|----------|------|
| 올빼미형 | 2 | 11 | [5,10,20,30,25] | 야행성 |
| 아침형 | 23 | 6 | [30,30,20,15,5] | 조기 기상 |
| 중간형 | 1 | 8 | [15,30,25,20,10] | 보통 |
| 운동파 | 24 | 7 | [30,30,20,15,5] | 활동적 |
| 집순이형 | 3 | 11 | [5,10,20,30,35] | 실내 |

- `_wchoice(population, weights)` — 가중치 랜덤 샘플링
- `_random_time(mu, sigma=1.2)` — 정규분포 기반 시간 생성
- `generate_profile(persona, seed)` / `generate_and_store(n, ...)`

### matcher.py — 기본 매칭 엔진

**가중치 벡터** (37차원, 합 ≈ 51.5):

```
향/음주/게임(9): [1.0,1.5,2.0,1.0,1.5,2.0,1.0,2.0,0.5]
수면(7):          [3.0,3.0,2.0,2.5,1.5,1.0,3.0]
위생(9):          [0.5,1.0,1.5,2.0,1.0,0.5,0.5,2.0,3.0]
생활(8):          [2.5,1.0,0.5,1.0,0.5,0.5,1.0,2.5]
교류(4):          [2.0,1.0,0.5,1.5]
```

**하드 필터** (`_hard_filters`):
1. 흡연/비흡연 불일치
2. 취침시간 차이 ≥ 5시간
3. 코골이자 + 수면예민자(≥4) 조합

**호환도 계산**:
```
dist = sqrt(sum(w[i] * (va[i] - vb[i])^2))
score = (1 - dist / sqrt(sum(w))) * 100
hard_block 시 -30점
```

**best_pairings()** — O(n² log n) 그리디 페어링

### main.py — PyQt5 GUI (3탭)

| 탭 | 클래스 | 기능 |
|----|--------|------|
| 체크리스트 | `ChecklistTab` | 40개 입력 필드, DB 저장 |
| 자동 생성기 | `GeneratorTab` | 1~500명 생성, 페르소나/seed 선택 |
| 매칭 | `MatcherTab` | 상위 매칭/전체 페어링 + 상세 다이얼로그 |

---

## 파트 2: 백엔드 레이어 (Flask API)

### auth.py — JWT 인증

| 함수 | 설명 |
|------|------|
| `hash_password(password)` | salt(16hex) + SHA-256, 포맷: `{salt}${hash}` |
| `verify_password(password, hash)` | salt 추출 후 해시 비교 |
| `create_token(user_uid, login_id, name)` | HS256 JWT, 7일 만료 |
| `decode_token(token)` | 만료/무효 토큰 에러 반환 |
| `login_required` | Bearer 토큰 검증 데코레이터, `request.current_user` 설정 |

**비고**: 
- `SECRET_KEY = "roomantic-secret-key-change-in-production"` — 하드코딩 (프로덕션 전 변경 필요)
- SHA-256은 GPU 브루트포스트에 취약 → bcrypt/argon2 권장

### models.py — 데이터 모델

**User 클래스**:
```python
@dataclass
class User:
    uid, login_id, student_id, birth_year, password_hash,
    name, is_enrolled, school_name, college, department,
    region_name, gender
```

**RoommateProfile 클래스** (루트 + 프로토콜 확장 필드):

| 필드 | 설명 |
|------|------|
| `matching_phase` | `'preliminary'` / `'main'` |
| `hope_halls` | List[str], 최대 2 (예비 매칭) |
| `accepted_hall` | str, 1개 (본 매칭) |
| `room_capacity` | 2, 3, 또는 4 |
| `preferred_room_type_ids` | List[int] |
| `fixed_room_type_id` | int |
| `interest_room_type_ids` | List[int] |
| `non_negotiable_items` | List[str] — 타협 불가 항목 |
| `non_negotiable_weights` | List[int] — 항목별 중요도 (1~5) |
| `pre_change_count`, `apply_change_count` | 정책 변경 카운트 |

**classify_persona(p) → str** (경량 페르소나 분류):
```python
scores = {"study_focused": 0, "sensitive": 0, "night_owl": 0, "social": 0}
# study_in_room → study_focused +=2
# noise_sensitivity ≥ 4 or indoor_scent_sensitivity ≥ 4 → sensitive +=2
# bedtime ≥ 1 or gaming ≥ 15 → night_owl +=2
# desired_intimacy ≥ 4 or friend_invite ≥ 1 → social +=2
return max(scores, key=scores.get)
```

**profile_to_vector(p)** — 루트와 동일한 37차원 벡터 (정규화 방식 일치)

### matcher.py — 고급 매칭 엔진

**루트와의 차이점**:

| 기능 | 루트 matcher.py | 백엔드 matcher.py |
|------|----------------|------------------|
| 가중치 | 고정 | `_apply_non_negotiable_weights()` 동적 조정 |
| 하드블록 페널티 | -30 | -30 (동일) |
| 페르소나 보너스 | 없음 | `_persona_bonus()` → ±10점 조정 |
| 매칭 결과 선택 | 단순 top N | `select_by_tiers()` — 티어별 랜덤 샘플링 |
| 사전 필터 | 없음 | `prefilter_pool()` — 건물/인원/페르소나 |
| 팀 리매치 | 없음 | `_team_rematch_entry()` — 2인팀 → 가상 프로필 |

**티어 설정**:

| 티어 | 점수 범위 | 선택 인원 |
|------|---------|----------|
| S | 90~100 | 1 |
| A | 80~90 | 2 |
| B | 60~80 | 2 |

하위 티어 부족 시 상위 티어에서 충원 (downward substitution)

**8가지 페르소나 호환성 매트릭스** (`PERSONA_COMPATIBILITY`):
- 독서실형, 자취감성형, 야행성게이머형, FM군대형, 생존형, 공동체형, 생활분리형, 수면민감형
- 범위: 0.1 (최악) ~ 1.0 (최적)
- 예: 독서실형 × 야행성게이머형 = 0.1, 생활분리형 × 독서실형 = 0.9

**non_negotiable 가중치 조정**:
```python
w[idx] *= (1 + importance * 0.5)  # 중요도 1~5 → 1.5배~3.5배
# 양측 가중치를 평균: (w_a + w_b) / 2
```

**prefilter_pool()** — 사전 필터:
1. 동일 프로필 제외
2. 기숙사 건물 호환 (`_hall_compatible`)
3. 인원수 일치 (`room_capacity`)
4. 페르소나 호환성 ≥ 0.3

**_team_rematch_entry()** — 2인 팀의 가상 프로필 생성:
- 모든 수치 필드 평균
- UID: `team_{a.uid}_{b.uid}`
- 희망 건물: 교집합

### db.py — 백엔드 SQLite 관리

**2개 DB 파일**:
- `roommates_api.db` — 메인 데이터
- `schools.db` — 학교/기숙사/단과대/학과 메타데이터

**스키마 (roommates_api.db)**:

| 테이블 | 용도 |
|--------|------|
| `users` | 사용자 계정 |
| `profiles` | 룸메이트 프로필 (57칼럼) |
| `match_pool_candidates` | 매칭 풀 후보 |
| `match_sessions` | 매칭 세션 (상태, 양측 확인) |
| `match_session_members` | 세션 멤버 |
| `chat_threads` | 채팅 스레드 |
| `chat_messages` | 채팅 메시지 |
| `chat_thread_leaves` | 스레드 퇴장 기록 |
| `match_cooldowns` | 리매치 쿨다운 |
| `match_requests` | 매칭 요청 (레거시) |
| `match_pair_blocks` | 차단된 페어 |
| `match_history` | 매칭 이력 |
| `reviews` | 리뷰/평가 |
| `pairings` | 전체 페어링 결과 |
| `system_events` | 시스템 이벤트 로그 |
| `notices` | 공지사항 (레거시) |
| `life_rooms` | 방 공동체 |
| `life_room_members` | 방 멤버 |
| `life_room_posts` | 게시글 |
| `life_room_rules` | 방 규칙 |
| `life_room_todos` | 할 일 |
| `life_room_events` | 일정 |
| `life_room_presence` | 재실 상태 |
| `life_room_notice_pins` | 공지 핀 |
| `life_room_fill_policy` | 충원 정책 |
| `life_room_recruit_sessions` | 모집 세션 |
| `life_room_match_history` | 방 매칭 이력 |

**스키마 (schools.db)**:

| 테이블 | 용도 |
|--------|------|
| `schools` | 학교 (이름, 일정, 매칭 활성 여부) |
| `dormitories` | 기숙사 (학교 FK, 성별 제한) |
| `colleges` | 단과대학 |
| `departments` | 학과 |
| `dorm_room_types` | 방 유형 (인원수, 활성 여부) |
| `global_notices` | 전역 공지 |
| `school_notices` | 학교별 공지 |

**초기 데이터**:
- 고려대학교 기본 등록
- 4개 기숙사: 자유관(male), 정의관(female), 진리관(coed), 미래관(coed)
- 8개 단과대 + 학과 (공과, 인문, 사회, 자연, 경영, 예술, 체육, 음악)

**특징**:
- `_add_missing_columns()` — 베스트 에포트 마이그레이션 (ALTER TABLE)
- `drop_if_corrupt=True` — 손상 시 DB 삭제 후 재생성
- WAL 모드, busy_timeout=10000ms

### app.py — Flask API (3650줄, 단일 파일)

**API 엔드포인트 카테고리**:

| 카테고리 | 주요 엔드포인트 |
|---------|---------------|
| 인증 | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me` |
| 프로필 | `GET /api/profile`, `POST /api/profile`, `GET /api/profile/public/{uid}` |
| 페르소나 | `GET /api/persona` |
| 매칭 (레거시) | `GET /api/match/top`, `GET /api/match/pairs` |
| 매칭 요청 | `POST /api/match/request`, `PATCH /api/match/request/{id}` |
| 매칭 풀 | `POST /api/match/pool/refresh`, `GET /api/match/pool` |
| 매칭 세션 | `POST /api/match/session/enter`, `GET /api/match/session/active` |
| 매칭 확인 | `POST /api/match/confirm`, `POST /api/match/rematch` |
| 매칭 옵션 | `GET /api/matching/options`, `POST /api/matching/preferences` |
| 채팅 | `GET /api/chat/threads`, `POST /api/chat/threads/{id}/messages` |
| 채팅 SSE | `GET /api/chat/stream` (Server-Sent Events) |
| 쿨다운 | `GET /api/match/cooldown` |
| 리뷰 | `POST /api/reviews`, `GET /api/reviews/{uid}` |
| 공지 | `GET /api/notices` |
| 학교 | `GET /api/schools` |
| Life Room | `GET /api/life-room/current`, todos/events/rules/presence/posts |
| 관리자 | `/api/admin/*` (공지/학교/기숙사/방유형/일정 관리) |
| 로컬 채팅 | `GET/PUT/DELETE /api/chat/local/threads/{id}/messages` |

**SSE (Server-Sent Events)**:
- 인메모리 큐: `_SSE_QUEUES: Dict[str, list]` (user_uid → 큐 리스트)
- 스레드 세이프: `_SSE_LOCK = threading.Lock()`
- `broadcast_message()` — 사용자의 모든 SSE 큐에 이벤트 푸시
- 이벤트 타입: `message`, `match_confirmed`, `session_update`, 등

**학교 매칭 단계** (`_school_matching_phase`):
- `preliminary` — 예비 매칭 기간
- `main` — 본 매칭 신청 기간
- `life` — 방 공동체 운영 기간
- `closed` — 매칭 비활성

---

## 파트 3: 프론트엔드 레이어 (Flutter/Dart)

### 아키텍처

- **상태 관리**: GetX (`GetMaterialApp`, `Get.put`, `Get.lazyPut`)
- **HTTP 클라이언트**: Dio (싱글톤 `ApiService`)
- **인증**: JWT → `SharedPreferences` 저장
- **실시간**: SSE 스트림 → `MatchController.chatStream()`
- **로컬 저장**: `ChatLocalStore` (채팅 오프라인 캐시)

### main.dart

- `MyApp` 위젯: Material 3 테마, seedColor `#2563EB`
- 라우트:
  - `/splash`, `/login`, `/register`, `/home`
  - `/admin`, `/matching-split`, `/life-room`

### Controllers

| 컨트롤러 | 라인 | 역할 |
|---------|------|------|
| `AuthController` | 118 | 회원가입, 로그인, 로그아웃, 자동 로드 |
| `MatchController` | 1151 | 매칭 풀, 세션, 채팅, SSE, 쿨다운 |
| `ProfileController` | — | 프로필 CRUD |

**AuthController 특징**:
- 회원가입 시 비밀번호를 **클라이언트에서 SHA-256 해싱** 후 전송
  - 주의: 서버에서 salted 해시를 한 번 더 적용하므로 이중 해시 구조
- `_sha256()` — `crypto` 패키지 사용

**MatchController 특징** (가장 복잡한 컨트롤러, 1151줄):
- `_bootstrap()` — 프로필 확인 → 세션/스레드/쿨다운 로드 → 풀 생성 → SSE 연결
- 오프라인 메시지 큐: `_threadSendQueue`, `_pendingWatchdog` (5초 간격 타임아웃)
- 채팅 스트림 재연결: `_streamReconnectTimer`
- 스레드별 페이지네이션: `_threadOldestCreatedAt`, `_threadOldestUid`
- 메시지 송신 실패 타임아웃: 1분

### Models

| 모델 | 필드 수 | 특징 |
|------|---------|------|
| `User` | 12 | userUid, loginId, studentId, name, school, gender 등 |
| `Profile` | 65+ | RoommateProfile과 동일 + matchingPhase, hopeHalls, nonNegotiableItems 등 |

- `Profile.fromJson()` / `toJson()` — snake_case ↔ camelCase 변환
- `Profile.copy()` — 전 필드 복사

### API Service

**ApiService** (Dio 싱글톤, 460줄):

| 기능 | 메서드 수 |
|------|----------|
| 인증 | 3 (register, login, getMe) |
| 프로필 | 2 (get, save) |
| 페르소나/학교/공지 | 4 |
| 관리자 | 10+ |
| 매칭 (레거시) | 5 |
| 풀/세션 | 7 |
| 채팅 | 8+ |
| SSE 스트림 | 1 (chatStream) |
| 리뷰 | 2 |
| Life Room | 8+ |

- baseUrl: Android → `10.0.2.2:5000`, iOS/Web → `localhost:5000`
- 인터셉터: 요청 시 JWT 자동 첨부, 401 응답 시 토큰 삭제
- SSE: `chatStream()` — Dio Stream + SSE 파서 (event/data 필드 파싱)

### screens/ (21개)

| 화면 | 파일 | 역할 |
|------|------|------|
| 스플래시 | `splash_screen.dart` | 자동 로그인 확인 |
| 로그인 | `login_screen.dart` | ID/비밀번호 입력 |
| 회원가입 | `register_screen.dart` | 기본 정보 입력 |
| 메인 | `main_screen.dart` | 바텀 네비게이션 (Home/Match/Chat/Profile) |
| 홈 | `home_screen.dart` | 대시보드 |
| 매칭 | `match_screen.dart` | 매칭 풀/세션/결과 |
| 매칭 분할 | `matching_split_screen.dart` | 예비/본 매칭 탭 |
| 매칭 상세 | `match_detail_screen.dart` | 프로필 비교 |
| 매칭 히스토리 | `match_history_screen.dart` | 과거 매칭 목록 |
| 매칭 히스토리 상세 | `match_history_detail_screen.dart` | 히스토리 상세 |
| 채팅 스레드 | `chat_threads_screen.dart` | 채팅 목록 |
| 채팅 세션 | `match_session_chats_screen.dart` | 세션별 채팅 |
| 설문조사 | `survey_screen.dart` | 룸메이트 체크리스트 |
| 열린 설문 | `opened_survey_screen.dart` | 상대방 설문 열람 |
| 페르소나 비교 | `persona_compare_screen.dart` | 유형별 비교 |
| 페르소나 상세 | `persona_detail_screen.dart` | 유형 상세 정보 |
| 프로필 | `profile_screen.dart` | 내 프로필 |
| 공개 프로필 | `public_profile_screen.dart` | 상대방 프로필 |
| Life Room | `life_room_screen.dart` | 방 공동체 (게시글, 할일, 일정, 규칙) |
| 공지 | `notices_screen.dart` | 공지사항 |
| 관리자 | `admin_dashboard_screen.dart` | 학교/기숙사/공지 관리 |

---

## 파트 4: 시뮬레이션 레이어

### 구조

```
simulation/
├── main.py        # PyQt5 UI (root/main.py와 거의 동일)
├── generator.py   # 시뮬레이션 전용 생성기
└── (db.py, matcher.py — simulation.db / simulation.matcher 사용)
```

- `simulation/main.py` — 루트 `main.py`와 동일한 UI + 3탭 구조
- 차이점: `import simulation.db as db`, `import simulation.generator as generator`
- `simulation.db`, `simulation.matcher` — 별도 DB/매칭 모듈 (루트와 독립)
- 목적: 대량 시뮬레이션 실행 (알고리즘 성능 검증용)

---

## 크로스 레이어 데이터 흐름

### 1. 회원가입 → 매칭 실행 흐름

```
1. [Flutter] RegisterScreen → AuthController.register()
   ↓ SHA-256 해시된 비밀번호 + 사용자 정보
2. [Flutter] ApiService.post('/api/auth/register')
   ↓ HTTP POST
3. [Flask] app.py → hash_password(salted SHA-256) → db.save_user()
   ↓ JWT 토큰 발급
4. [Flutter] AuthController → SharedPreferences에 토큰 저장
   ↓
5. [Flutter] SurveyScreen → ProfileController → ApiService.post('/api/profile')
   ↓ HTTP POST (40개 라이프스타일 필드 + matching protocol 필드)
6. [Flask] app.py → classify_persona() → db.save_profile()
   ↓
7. [Flutter] MatchScreen → MatchController → ApiService.refreshPool()
   ↓ HTTP POST
8. [Flask] app.py → fetch_profiles() → prefilter_pool() → rank_matches()
   ↓ select_by_tiers() 결과
9. [Flutter] MatchController.poolCandidates 갱신 → UI 표시
```

### 2. 매칭 세션 진입 → 채팅 → 확정

```
1. [Flutter] 후보 선택 → ApiService.enterSession(candidateUids)
   ↓
2. [Flask] match_sessions 생성 → chat_threads 생성
   ↓ broadcast_message (SSE)
3. [Flutter] SSE chatStream() → 새 스레드 감지 → ChatScreen 열기
   ↓
4. [Flutter] 메시지 전송 → ApiService.sendThreadMessage()
   ↓
5. [Flask] chat_messages 저장 → broadcast_message (SSE)
   ↓
6. [Flutter] SSE → 실시간 메시지 수신
   ↓ 브라우저/알림
7. [Flutter] 매칭 확정 → ApiService.confirmMatch(sessionId)
   ↓
8. [Flask] 양측 확인 후 match_sessions.confirmed → 쿨다운 설정
   ↓ broadcast → 양측 SSE 알림
```

### 3. Life Room 흐름

```
1. [Flutter] LifeRoomScreen → ApiService.getCurrentLifeRoom()
   ↓
2. [Flask] life_rooms + life_room_members 조회
   ↓
3. [Flutter] 게시글/할일/일정/규칙/재실상태 표시
   ↓
4. [Flutter] CRUD 상호작용 → 각 API 엔드포인트 호출
   ↓
5. [Flask] life_room_posts/todos/events/rules/presence 업데이트
```

---

## 핵심 알고리즘 비교 (루트 vs 백엔드)

| 항목 | 루트 matcher.py | 백엔드 matcher.py |
|------|----------------|------------------|
| 벡터 차원 | 37 | 37 (동일) |
| 정규화 | 0~1 (동일 방식) | 0~1 (동일) |
| 가중치 | 고정 37개 | 동적 (non_negotiable 반영) |
| 거리 계산 | 가중치 유클리드 | 가중치 유클리드 (평균 가중치) |
| 페르소나 | 없음 | 보너스 ±10점 (8×8 매트릭스) |
| 하드블록 | -30 | -30 (동일) |
| 결과 선택 | top N | 티어 기반 샘플링 (S/A/B) |
| 사전 필터 | 없음 | 건물/인원/페르소나 |
| 팀 매칭 | 없음 | _team_rematch_entry (2→1 가상 프로필) |

---

## 보안 분석

| 항목 | 현재 상태 | 권장 사항 |
|------|----------|----------|
| JWT 시크릿 | 하드코딩 `"roomantic-secret-key..."` | 환경변수/시크릿 매니저 |
| 비밀번호 해시 | 서버: salted SHA-256 | bcrypt/argon2 (적응형) |
| 클라이언트 해시 | SHA-256 (단방향) | HTTPS에서 불필요; 이중 해시 구조 주의 |
| CORS | `origins: "*"` | 프로덕션 도메인으로 제한 |
| SQL 인젝션 | 파라미터화 쿼리 사용 | 양호 |
| SSE 인증 | Bearer 토큰 | 양호 |

---

## 주요 개선 권장사항

### 1. app.py 분리 (최우선)

`app.py`는 3650줄 단일 파일. 블루프린트로 분리 권장:
```
backend/
├── app.py              # Flask 앱 팩토리
├── blueprints/
│   ├── auth_bp.py
│   ├── profile_bp.py
│   ├── match_bp.py
│   ├── chat_bp.py
│   ├── life_room_bp.py
│   └── admin_bp.py
```

### 2. 타입 힌팅 강화

```python
# 현재
def _wchoice(population: list, weights: list):

# 권장
def _wchoice(population: List[Union[int, float]], weights: List[float]) -> Union[int, float]:
```

### 3. 매직 넘버 상수화

```python
MISMATCH_PENALTY = 30
PERSONA_BONUS_SCALE = 20
MIN_PERSONA_COMPAT = 0.3
HARD_FILTER_BED_DIFF = 5
```

### 4. 예외 처리 + 로깅

```python
import logging
logger = logging.getLogger(__name__)

try:
    conn.execute(sql, rows)
except sqlite3.IntegrityError as e:
    logger.error(f"중복: {e}")
    raise ValueError("학번 중복") from e
```

### 5. 설정 파일 외부화

```python
# config.py
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-key")
DB_PATH = os.environ.get("DB_PATH", "roommates_api.db")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
```

### 6. 프론트엔드 아키텍처 개선

- `MatchController` 1151줄 → 서비스 분리 (ChatService, PoolService, SessionService)
- 비밀번호 클라이언트 해싱 제거 (HTTPS에 위임)
- 무효화된 토큰 블랙리스트 구현

### 7. 캐싱 최적화

```python
@dataclass
class RoommateProfile:
    _vector_cache: Optional[List[float]] = field(default=None, init=False, repr=False)
    
    def get_vector(self) -> List[float]:
        if self._vector_cache is None:
            self._vector_cache = profile_to_vector(self)
        return self._vector_cache
```

### 8. 테스트 코드 작성

```python
# tests/test_matcher.py
def test_perfect_match():
    p = RoommateProfile(bedtime=23, wake_time=8, ...)
    result = matcher.match(p, p)
    assert result.score >= 99.0

def test_hard_block_smoking():
    a = RoommateProfile(smoking=1, ...)
    b = RoommateProfile(smoking=0, ...)
    result = matcher.match(a, b)
    assert result.hard_block == True

def test_non_negotiable_amplification():
    # non_negotiable 설정 시 해당 가중치 1.5~3.5배 증폭 확인
    ...
```

### 9. 성능 분석

| 시나리오 | 현재 | 개선안 |
|---------|------|-------|
| 1000명 전체 페어링 | ~500ms (O(n² log n)) | 병렬 처리, 벡터 캐싱 |
| 풀 리프래시 | 전체 프로필 스캔 | 인덱싱, ANN (Approximate Nearest Neighbor) |
| SSE 연결 | 스레드 당 큐 | Redis Pub/Sub |
| DB 마이그레이션 | 수동 ALTER TABLE | Alembic |

### 10. 배포 준비

- [ ] JWT SECRET_KEY 환경변수화
- [ ] CORS origins 제한
- [ ] bcrypt 비밀번호 해시
- [ ] HTTPS 강제
- [ ] rate limiting (Flask-Limiter)
- [ ] DB 백업 자동화
- [ ] 헬스체크 엔드포인트 (`/api/health`)

---

## 데이터 검증 체크리스트

- [ ] 벡터 모든 값 [0, 1] 범위
- [ ] 가중치 합 = 51.5 (기본)
- [ ] 최대 거리 = sqrt(51.5) ≈ 7.177
- [ ] 점수 [0, 100] 범위 (페르소나 보너스 후에도)
- [ ] hard_block 3조건 정확 작동
- [ ] 동일 프로필 매칭 ≈ 100점
- [ ] 페어링 수 = floor(n/2)
- [ ] 티어 분포: S=1, A=2, B=2 (총 5명)
- [ ] non_negotiable 미설정 시 루트와 동일 결과

---

**문서 작성일**: 2026년 6월 29일  
**버전**: 2.0 (전체 3-tier 분석)
