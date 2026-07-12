from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request


KOREAN_LAST_NAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오",
]

KOREAN_GIVEN_NAMES = [
    "민준", "서준", "예준", "도윤", "시우", "하준", "지호", "준우", "현우", "우진",
    "서연", "지우", "서윤", "하은", "지민", "채원", "수아", "지아", "다은", "예린",
    "유진", "소연", "가은", "태현", "건우", "주원", "민서", "은우", "유나", "아윤",
]

REGIONS = [
    "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "제주",
]
DEFAULT_PASSWORD = "111111"


@dataclass
class SchoolInfo:
    school_name: str
    college: str
    department: str


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = request.Request(url=url, data=data, headers=headers, method=method.upper())

        try:
            with request.urlopen(req, timeout=self.timeout) as res:
                status = int(res.status)
                raw = res.read().decode("utf-8")
                return status, json.loads(raw) if raw else {}
        except error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            body: dict[str, Any]
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"error": raw}
            return int(e.code), body
        except error.URLError as e:
            return 0, {"error": f"network error: {e.reason}"}


def random_name() -> str:
    return f"{random.choice(KOREAN_LAST_NAMES)}{random.choice(KOREAN_GIVEN_NAMES)}"


def random_login_id() -> str:
    ts = int(time.time() * 1000)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"load_{ts}_{suffix}"


def random_student_id() -> str:
    year = random.randint(2019, 2026)
    serial = random.randint(100000, 999999)
    return f"{year}{serial}"


def build_school_pool(api: ApiClient) -> list[SchoolInfo]:
    status, body = api.request("GET", "/api/schools")
    if status != 200:
        print(f"[warn] /api/schools 조회 실패: {status} {body}")
        return []

    schools = body.get("schools", [])
    pool: list[SchoolInfo] = []
    for school in schools:
        school_name = str(school.get("name", "")).strip()
        for college in school.get("colleges", []) or []:
            college_name = str(college.get("name", "")).strip()
            for dept in college.get("departments", []) or []:
                dept_name = str(dept.get("name", "")).strip()
                if school_name and college_name and dept_name:
                    pool.append(SchoolInfo(school_name, college_name, dept_name))
    return pool


def build_profile_payload() -> dict[str, Any]:
    bedtime = random.choice([21, 22, 23, 0, 1, 2, 3])
    return {
        "dorm_duration": random.choice([1, 2, 3, 4]),
        "home_visit_cycle": random.choice([1, 2, 3, 4]),
        "perfume": random.choice([0, 1]),
        "indoor_scent_sensitivity": random.randint(1, 5),
        "alcohol_tolerance": random.choice([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]),
        "alcohol_frequency": random.randint(0, 7),
        "drunk_habit": random.choice([0, 1]),
        "gaming_hours_per_week": random.choice([0, 2, 5, 8, 10, 15, 20, 25]),
        "speaker_use": random.choice([0, 1]),
        "exercise": random.choice([0, 1]),
        "bedtime": bedtime,
        "wake_time": random.randint(5, 10),
        "sleep_habit": random.choice([0, 1]),
        "sleep_sensitivity": random.randint(1, 5),
        "alarm_strength": random.randint(1, 5),
        "sleep_light": random.choice([0, 1]),
        "snoring": random.choice([0, 1]),
        "shower_duration": random.choice([10, 15, 20, 30]),
        "shower_time": random.randint(6, 24) % 24,
        "shower_cycle": random.choice([0, 1, 2, 3, 4]),
        "cleaning_cycle": random.choice([1, 3, 7, 14]),
        "ventilation": random.choice([0.5, 1.0, 2.0, 4.0]),
        "hairdryer_in_bathroom": random.choice([0, 1]),
        "toilet_paper_share": random.choice([0, 1]),
        "indoor_eating": random.choice([0, 1]),
        "smoking": random.choice([0, 1]),
        "temperature_pref": random.randint(1, 5),
        "indoor_call": random.choice([0, 1]),
        "bug_handling": random.randint(1, 5),
        "laundry_cycle": random.choice([1, 3, 5, 7, 14]),
        "drying_rack": random.choice([0, 1]),
        "fridge_use": random.choice([0, 1]),
        "study_in_room": random.choice([0, 1]),
        "noise_sensitivity": random.randint(1, 5),
        "desired_intimacy": random.randint(1, 5),
        "meal_together": random.randint(1, 3),
        "exercise_together": random.randint(1, 3),
        "friend_invite": random.choice([0, 1, 2]),
        "matching_phase": "preliminary",
        "hope_halls": [],
        "room_capacity": random.choice([2, 3, 4]),
    }


def create_random_account(api: ApiClient, school_pool: list[SchoolInfo], create_profile: bool) -> bool:
    gender = random.choice(["male", "female"])
    enrolled = bool(school_pool)
    school = random.choice(school_pool) if enrolled else None

    login_id = random_login_id()
    password = DEFAULT_PASSWORD
    student_id = random_student_id() if enrolled else ""
    payload = {
        "login_id": login_id,
        "password": password,
        "name": random_name(),
        "birth_year": random.randint(1999, 2007),
        "student_id": student_id,
        "is_enrolled": enrolled,
        "school_name": school.school_name if school else "",
        "college": school.college if school else "",
        "department": school.department if school else "",
        "region_name": random.choice(REGIONS),
        "gender": gender,
    }

    status, body = api.request("POST", "/api/auth/register", payload=payload)
    if status != 201:
        print(f"[fail] register={status} login_id={login_id} body={body}")
        return False

    token = body.get("token", "")
    user = body.get("user", {})

    if create_profile and token:
        profile_payload = build_profile_payload()
        p_status, p_body = api.request("POST", "/api/profile", payload=profile_payload, token=token)
        if p_status != 200:
            print(f"[warn] profile={p_status} uid={user.get('uid')} body={p_body}")
        else:
            # Keep match pool eligible: set at least one interest room type.
            opt_status, opt_body = api.request("GET", "/api/matching/options", token=token)
            if opt_status == 200:
                visible_room_types = list((opt_body or {}).get("visible_room_types") or [])
                if visible_room_types:
                    room_type_id = int(visible_room_types[0]["id"])
                    ir_status, ir_body = api.request(
                        "PUT",
                        "/api/profile/interest-rooms",
                        payload={"interest_room_type_ids": [room_type_id]},
                        token=token,
                    )
                    if ir_status != 200:
                        print(f"[warn] interest-rooms={ir_status} uid={user.get('uid')} body={ir_body}")
                else:
                    print(f"[warn] no visible_room_types uid={user.get('uid')}")
            else:
                print(f"[warn] matching/options={opt_status} uid={user.get('uid')} body={opt_body}")

    print(
        f"[ok] uid={user.get('uid')} login_id={login_id} "
        f"name={user.get('name')} gender={gender} enrolled={enrolled}"
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="매칭 비율 테스트용 랜덤 계정/프로필 생성기",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="백엔드 URL")
    parser.add_argument("--interval", type=float, default=0.2, help="요청 간격(초)")
    parser.add_argument("--count", type=int, default=0, help="생성 개수(0이면 무한)")
    parser.add_argument("--seed", type=int, default=None, help="랜덤 시드")
    parser.add_argument(
        "--max-failures",
        type=int,
        default=50,
        help="연속 실패 허용 횟수(초과 시 종료)",
    )
    parser.add_argument("--no-profile", action="store_true", help="계정만 만들고 프로필은 생성하지 않음")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    api = ApiClient(base_url=args.base_url)
    school_pool = build_school_pool(api)
    print(f"[info] school pool size={len(school_pool)}")

    created = 0
    attempts = 0
    consecutive_failures = 0
    create_profile = not args.no_profile

    try:
        while args.count == 0 or created < args.count:
            attempts += 1
            if create_random_account(api, school_pool, create_profile=create_profile):
                created += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if args.max_failures > 0 and consecutive_failures >= args.max_failures:
                    print(f"[stop] too many consecutive failures: {consecutive_failures}")
                    break
            if args.interval > 0:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[stop] interrupted by user")

    print(f"[done] created={created}, attempts={attempts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
