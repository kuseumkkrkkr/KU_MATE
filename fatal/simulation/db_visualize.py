"""DB visualization: generates an interactive HTML report for all databases."""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_API = os.path.join(_PROJECT_ROOT, "roommates_api.db")
DB_SCHOOLS = os.path.join(_PROJECT_ROOT, "schools.db")
DB_SIM = os.path.join(_PROJECT_ROOT, "roommates.db")
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_visualization.html")

_NUMERIC_PROFILE_COLS = [
    "home_visit_cycle", "indoor_scent_sensitivity",
    "alcohol_tolerance", "alcohol_frequency", "gaming_hours_per_week",
    "bedtime", "wake_time", "sleep_sensitivity", "alarm_strength",
    "shower_duration", "shower_time", "shower_cycle", "cleaning_cycle",
    "ventilation", "temperature_pref", "bug_handling", "laundry_cycle",
    "noise_sensitivity", "desired_intimacy", "meal_together",
    "exercise_together", "friend_invite",
]
_BOOL_PROFILE_COLS = [
    "perfume", "drunk_habit", "speaker_use", "exercise",
    "sleep_habit", "sleep_light", "snoring",
    "hairdryer_in_bathroom", "toilet_paper_share", "indoor_eating",
    "smoking", "indoor_call", "drying_rack", "fridge_use", "study_in_room",
]


def _connect(db_path: str) -> Optional[sqlite3.Connection]:
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_tables(conn: sqlite3.Connection) -> List[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type=? ORDER BY name", ("table",)
    ).fetchall() if not r[0].startswith("sqlite_")]


def _get_table_info(conn: sqlite3.Connection, table: str) -> List[Dict]:
    return [dict(r) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _get_row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _get_sample_rows(conn: sqlite3.Connection, table: str, limit: int = 5) -> List[Dict]:
    cols = [c["name"] for c in _get_table_info(conn, table)]
    rows = conn.execute(f"SELECT * FROM {table} LIMIT {limit}").fetchall()
    return [dict(zip(cols, row)) for row in rows]


def _profile_distributions(conn: sqlite3.Connection) -> Dict[str, Any]:
    if "profiles" not in _get_tables(conn):
        return {}
    rows = conn.execute("SELECT * FROM profiles").fetchall()
    if not rows:
        return {"total": 0}
    cols = [d[0] for d in conn.execute("SELECT * FROM profiles LIMIT 0").description]
    data: Dict[str, Any] = {"total": len(rows)}

    persona_col = [r[cols.index("persona")] for r in rows if "persona" in cols]
    if persona_col:
        data["persona_dist"] = dict(Counter(persona_col))

    gender_rows = [r for r in rows]
    if "college" in cols:
        data["college_dist"] = dict(Counter(r[cols.index("college")] for r in rows if r[cols.index("college")]))
    if "department" in cols:
        data["department_dist"] = dict(Counter(r[cols.index("department")] for r in rows if r[cols.index("department")]))

    numeric_stats = {}
    for col in _NUMERIC_PROFILE_COLS:
        if col not in cols:
            continue
        vals = [r[cols.index(col)] for r in rows if r[cols.index(col)] is not None]
        if not vals:
            continue
        numeric_stats[col] = {
            "min": min(vals), "max": max(vals),
            "mean": round(sum(vals) / len(vals), 2),
            "histogram": dict(Counter(vals)),
        }
    data["numeric_stats"] = numeric_stats

    bool_stats = {}
    for col in _BOOL_PROFILE_COLS:
        if col not in cols:
            continue
        vals = [r[cols.index(col)] for r in rows if r[cols.index(col)] is not None]
        if not vals:
            continue
        bool_stats[col] = {
            "true": sum(1 for v in vals if v),
            "false": sum(1 for v in vals if not v),
            "true_pct": round(sum(1 for v in vals if v) / len(vals) * 100, 1),
        }
    data["bool_stats"] = bool_stats

    return data


def _match_pool_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    if "match_pool_candidates" not in _get_tables(conn):
        return {}
    rows = conn.execute("SELECT * FROM match_pool_candidates").fetchall()
    if not rows:
        return {"total": 0}
    cols = [d[0] for d in conn.execute("SELECT * FROM match_pool_candidates LIMIT 0").description]
    tiers = dict(Counter(r[cols.index("tier")] for r in rows if "tier" in cols and r[cols.index("tier")]))
    return {"total": len(rows), "tiers": tiers}


def _session_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    if "match_sessions" not in _get_tables(conn):
        return {}
    rows = conn.execute("SELECT * FROM match_sessions").fetchall()
    if not rows:
        return {"total": 0}
    cols = [d[0] for d in conn.execute("SELECT * FROM match_sessions LIMIT 0").description]
    statuses = dict(Counter(r[cols.index("status")] for r in rows if "status" in cols and r[cols.index("status")]))
    return {"total": len(rows), "statuses": statuses}


def _chat_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    if "chat_messages" not in _get_tables(conn):
        return {}
    count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    threads = conn.execute("SELECT COUNT(*) FROM chat_threads").fetchone()[0] if "chat_threads" in _get_tables(conn) else 0
    return {"messages": count, "threads": threads}


def _schools_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for table in ["schools", "dormitories", "colleges", "departments", "dorm_room_types"]:
        if table in _get_tables(conn):
            result[table] = _get_row_count(conn, table)
    if "schools" in _get_tables(conn):
        rows = conn.execute("SELECT * FROM schools").fetchall()
        if rows:
            cols = [d[0] for d in conn.execute("SELECT * FROM schools LIMIT 0").description]
            result["school_details"] = [dict(zip(cols, r)) for r in rows]
    if "dormitories" in _get_tables(conn):
        rows = conn.execute("SELECT * FROM dormitories").fetchall()
        if rows:
            cols = [d[0] for d in conn.execute("SELECT * FROM dormitories LIMIT 0").description]
            result["dormitory_details"] = [dict(zip(cols, r)) for r in rows]
    if "dorm_room_types" in _get_tables(conn):
        rows = conn.execute("SELECT * FROM dorm_room_types").fetchall()
        if rows:
            cols = [d[0] for d in conn.execute("SELECT * FROM dorm_room_types LIMIT 0").description]
            result["room_type_details"] = [dict(zip(cols, r)) for r in rows]
    return result


def _table_overview(conn: sqlite3.Connection) -> List[Dict]:
    tables = _get_tables(conn)
    result = []
    for t in tables:
        info = _get_table_info(conn, t)
        count = _get_row_count(conn, t)
        sample = _get_sample_rows(conn, t, limit=3)
        result.append({
            "name": t,
            "columns": [f"{c['name']} ({c['type']})" for c in info],
            "row_count": count,
            "sample": sample,
        })
    return result


def _bar_chart_html(data: Dict, title: str, max_bars: int = 20) -> str:
    if not data:
        return f"<p><em>{title}: 데이터 없음</em></p>"
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_bars]
    max_val = max(v for _, v in sorted_items)
    bars = ""
    for k, v in sorted_items:
        pct = v / max_val * 100 if max_val > 0 else 0
        bars += (
            f'<div class="bar-row"><span class="bar-label">{k}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="bar-value">{v}</span></div>'
        )
    return f'<h4>{title}</h4><div class="bar-chart">{bars}</div>'


def _histogram_html(data: Dict, title: str) -> str:
    return _bar_chart_html(data, title, max_bars=30)


def _bool_pie_html(data: Dict, title: str) -> str:
    if not data:
        return f"<p><em>{title}: 데이터 없음</em></p>"
    t = data.get("true", 0)
    f = data.get("false", 0)
    pct = data.get("true_pct", 0)
    return (
        f'<div class="bool-stat">'
        f'<span class="bool-title">{title}</span>'
        f'<span class="bool-true">O {t} ({pct}%)</span>'
        f'<span class="bool-false">X {f}</span>'
        f"</div>"
    )


def _json_preview(data: Any, max_len: int = 2000) -> str:
    s = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if len(s) > max_len:
        s = s[:max_len] + "\n... (truncated)"
    return f'<pre class="json-preview">{s}</pre>'


def generate_html() -> str:
    sections = []

    api_conn = _connect(DB_API)
    schools_conn = _connect(DB_SCHOOLS)
    sim_conn = _connect(DB_SIM)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections.append(f"<h2>생성 시각: {now}</h2>")

    # --- roommates_api.db ---
    sections.append('<h2 id="api">roommates_api.db (API 메인 DB)</h2>')
    if api_conn:
        tables = _table_overview(api_conn)
        sections.append("<h3>테이블 개요</h3>")
        for t in tables:
            sections.append(
                f'<details class="table-detail"><summary>'
                f'<span class="table-name">{t["name"]}</span>'
                f' <span class="table-count">({t["row_count"]}행)</span></summary>'
                f'<p><strong>컬럼:</strong> {", ".join(t["columns"])}</p>'
                f'<p><strong>샘플 (최대 3행):</strong></p>'
                f'{_json_preview(t["sample"])}</details>'
            )

        profile_stats = _profile_distributions(api_conn)
        if profile_stats and profile_stats.get("total"):
            sections.append(f'<h3>프로필 통계 (총 {profile_stats["total"]}명)</h3>')
            if "persona_dist" in profile_stats:
                sections.append(_bar_chart_html(profile_stats["persona_dist"], "페르소나 분포"))
            if "college_dist" in profile_stats:
                sections.append(_bar_chart_html(profile_stats["college_dist"], "단과대 분포"))
            if "department_dist" in profile_stats:
                sections.append(_bar_chart_html(profile_stats["department_dist"], "학과 분포", max_bars=15))
            if "numeric_stats" in profile_stats:
                sections.append("<h4>수치 필드 분포</h4>")
                for col, stats in profile_stats["numeric_stats"].items():
                    sections.append(_histogram_html(stats["histogram"], f"{col} (평균 {stats['mean']}, 범위 {stats['min']}~{stats['max']})"))
            if "bool_stats" in profile_stats:
                sections.append("<h4>불리언 필드</h4><div class='bool-grid'>")
                for col, stats in profile_stats["bool_stats"].items():
                    sections.append(_bool_pie_html(stats, col))
                sections.append("</div>")

        pool_stats = _match_pool_stats(api_conn)
        if pool_stats:
            sections.append(f'<h3>매칭 풀 (총 {pool_stats.get("total", 0)}건)</h3>')
            if "tiers" in pool_stats:
                sections.append(_bar_chart_html(pool_stats["tiers"], "티어 분포"))

        sess_stats = _session_stats(api_conn)
        if sess_stats:
            sections.append(f'<h3>매칭 세션 (총 {sess_stats.get("total", 0)}건)</h3>')
            if "statuses" in sess_stats:
                sections.append(_bar_chart_html(sess_stats["statuses"], "상태 분포"))

        chat_stats = _chat_stats(api_conn)
        if chat_stats:
            sections.append(f'<h3>채팅 (메시지 {chat_stats.get("messages", 0)}건, 스레드 {chat_stats.get("threads", 0)}개)</h3>')
    else:
        sections.append("<p>DB 파일 없음</p>")

    # --- schools.db ---
    sections.append('<h2 id="schools">schools.db (학교 DB)</h2>')
    if schools_conn:
        schools = _schools_stats(schools_conn)
        sections.append("<h3>테이블 행 수</h3>")
        for k, v in schools.items():
            if not k.endswith("_details"):
                sections.append(f"<p><strong>{k}:</strong> {v}</p>")
        if "school_details" in schools:
            sections.append("<h3>학교 정보</h3>")
            sections.append(_json_preview(schools["school_details"]))
        if "dormitory_details" in schools:
            sections.append("<h3>기숙사 정보</h3>")
            sections.append(_json_preview(schools["dormitory_details"]))
        if "room_type_details" in schools:
            sections.append("<h3>방 유형 정보</h3>")
            sections.append(_json_preview(schools["room_type_details"]))
    else:
        sections.append("<p>DB 파일 없음</p>")

    # --- roommates.db (simulation) ---
    sections.append('<h2 id="sim">roommates.db (시뮬레이션 DB)</h2>')
    if sim_conn:
        sim_tables = _table_overview(sim_conn)
        for t in sim_tables:
            sections.append(
                f'<details class="table-detail"><summary>'
                f'<span class="table-name">{t["name"]}</span>'
                f' <span class="table-count">({t["row_count"]}행)</span></summary>'
                f'<p><strong>컬럼:</strong> {", ".join(t["columns"])}</p>'
                f'{_json_preview(t["sample"])}</details>'
            )
        sim_profile_stats = _profile_distributions(sim_conn)
        if sim_profile_stats and sim_profile_stats.get("total"):
            sections.append(f'<h3>시뮬레이션 프로필 (총 {sim_profile_stats["total"]}명)</h3>')
            if "persona_dist" in sim_profile_stats:
                sections.append(_bar_chart_html(sim_profile_stats["persona_dist"], "페르소나 분포"))
    else:
        sections.append("<p>DB 파일 없음</p>")

    if api_conn:
        api_conn.close()
    if schools_conn:
        schools_conn.close()
    if sim_conn:
        sim_conn.close()

    body = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DB Visualization - Roommate Matching</title>
<style>
:root {{
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --text: #c9d1d9; --text2: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --red: #f85149; --yellow: #d29922;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; padding:24px; line-height:1.6; }}
h1 {{ text-align:center; margin-bottom:8px; color:var(--accent); }}
h2 {{ color:var(--accent); border-bottom:2px solid var(--border); padding-bottom:8px; margin:32px 0 16px; }}
h3 {{ color:var(--text); margin:16px 0 8px; }}
h4 {{ color:var(--text2); margin:12px 0 6px; }}
nav {{ text-align:center; margin-bottom:24px; }}
nav a {{ color:var(--accent); margin:0 12px; text-decoration:none; }}
nav a:hover {{ text-decoration:underline; }}
.table-detail {{ background:var(--card); border:1px solid var(--border); border-radius:8px; margin:8px 0; padding:12px 16px; }}
.table-detail summary {{ cursor:pointer; font-size:15px; padding:4px 0; }}
.table-name {{ font-weight:700; color:var(--green); }}
.table-count {{ color:var(--text2); font-size:13px; }}
.json-preview {{ background:#0d1117; border:1px solid var(--border); border-radius:6px; padding:12px; overflow-x:auto; font-size:12px; font-family:'Cascadia Code',Consolas,monospace; color:var(--text2); max-height:300px; overflow-y:auto; margin:8px 0; }}
.bar-chart {{ margin:8px 0; }}
.bar-row {{ display:flex; align-items:center; margin:3px 0; }}
.bar-label {{ width:140px; font-size:13px; text-align:right; padding-right:8px; color:var(--text2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bar-track {{ flex:1; background:var(--border); border-radius:4px; height:18px; position:relative; }}
.bar-fill {{ background:var(--accent); border-radius:4px; height:100%; min-width:2px; transition:width 0.3s; }}
.bar-value {{ width:50px; text-align:right; font-size:13px; color:var(--text2); padding-left:8px; }}
.bool-grid {{ display:flex; flex-wrap:wrap; gap:8px; }}
.bool-stat {{ background:var(--card); border:1px solid var(--border); border-radius:6px; padding:8px 12px; display:flex; flex-direction:column; align-items:center; min-width:120px; }}
.bool-title {{ font-weight:600; font-size:13px; margin-bottom:4px; }}
.bool-true {{ color:var(--green); font-size:13px; }}
.bool-false {{ color:var(--red); font-size:13px; }}
</style>
</head>
<body>
<h1>Roommate Matching DB Visualization</h1>
<nav>
  <a href="#api">roommates_api.db</a>
  <a href="#schools">schools.db</a>
  <a href="#sim">roommates.db (simulation)</a>
</nav>
{body}
</body>
</html>"""


def visualize():
    html = generate_html()
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {OUTPUT_HTML}")
    print(f"File size: {os.path.getsize(OUTPUT_HTML):,} bytes")
    print(f"Open in browser: file:///{OUTPUT_HTML.replace(os.sep, '/')}")


if __name__ == "__main__":
    visualize()
