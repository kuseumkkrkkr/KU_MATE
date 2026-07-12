from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _load_room_type_catalog(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT rt.id, rt.capacity, rt.is_enabled, d.gender AS dorm_gender "
        "FROM dorm_room_types rt "
        "JOIN dormitories d ON d.id=rt.dorm_id "
        "WHERE rt.is_enabled=1"
    ).fetchall()
    catalog = [dict(r) for r in rows]
    return catalog


def _pick_room_type_id(catalog: list[dict], gender: str) -> int | None:
    visible = [r for r in catalog if r.get("dorm_gender") in ("coed", gender)]
    target = visible[0] if visible else (catalog[0] if catalog else None)
    return int(target["id"]) if target else None


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    root_dir = base_dir.parent
    app_db_path = root_dir / "roommates_api.db"
    schools_db_path = root_dir / "schools.db"

    app_conn = sqlite3.connect(str(app_db_path))
    app_conn.row_factory = sqlite3.Row
    schools_conn = sqlite3.connect(str(schools_db_path))
    schools_conn.row_factory = sqlite3.Row

    catalog = _load_room_type_catalog(schools_conn)
    if not catalog:
        print(json.dumps({"ok": False, "error": "no enabled dorm_room_types"}, ensure_ascii=False))
        return 1

    rows = app_conn.execute(
        "SELECT p.user_uid, p.matching_phase, p.interest_room_type_ids, p.fixed_interest_room_type_id, "
        "p.preferred_room_type_ids, p.fixed_room_type_id, u.gender "
        "FROM profiles p JOIN users u ON u.uid=p.user_uid "
        "WHERE (p.interest_room_type_ids IS NULL OR trim(p.interest_room_type_ids)='' OR p.interest_room_type_ids='[]') "
        "AND coalesce(p.fixed_interest_room_type_id, 0)=0"
    ).fetchall()

    updated = 0
    skipped = 0
    for r in rows:
        room_type_id = _pick_room_type_id(catalog, str(r["gender"] or ""))
        if not room_type_id:
            skipped += 1
            continue
        phase = (r["matching_phase"] or "preliminary").strip().lower()
        if phase == "main":
            app_conn.execute(
                "UPDATE profiles SET fixed_interest_room_type_id=?, fixed_room_type_id=?, "
                "interest_room_type_ids='[]', preferred_room_type_ids='[]' WHERE user_uid=?",
                (room_type_id, room_type_id, r["user_uid"]),
            )
        else:
            ids_json = json.dumps([room_type_id], ensure_ascii=False)
            app_conn.execute(
                "UPDATE profiles SET interest_room_type_ids=?, preferred_room_type_ids=?, "
                "fixed_interest_room_type_id=0, fixed_room_type_id=0 WHERE user_uid=?",
                (ids_json, ids_json, r["user_uid"]),
            )
        updated += 1

    app_conn.commit()
    remain = app_conn.execute(
        "SELECT count(*) AS c FROM profiles "
        "WHERE (interest_room_type_ids IS NULL OR trim(interest_room_type_ids)='' OR interest_room_type_ids='[]') "
        "AND coalesce(fixed_interest_room_type_id, 0)=0"
    ).fetchone()["c"]

    print(
        json.dumps(
            {
                "ok": True,
                "updated": updated,
                "skipped": skipped,
                "remaining_missing_interest": int(remain or 0),
            },
            ensure_ascii=False,
        )
    )
    schools_conn.close()
    app_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
