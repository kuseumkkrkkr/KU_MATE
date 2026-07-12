# API Schema Snapshot (v2026-06)

## Matching Options
GET `/api/matching/options`
- `phase`: `preliminary|main|life|closed`
- `visible_room_types[]`: `{id,dorm_id,capacity,dorm_name,dorm_gender,is_enabled}`
- `selected_room_types[]`: int
- `selected_interest_room_types[]`: int
- `change_limit`: int (default 1)
- `change_used`: int

POST `/api/matching/preferences`
- request: `{selected_room_type_ids:int[], interest_room_type_ids:int[]}`
- response: `{ok, phase, selected_room_type_ids, interest_room_type_ids}`

## Notices
GET `/api/notices?limit=&school_id=`
- returns merged `global_notices + school_notices`

Admin:
- global: `/api/admin/notices`
- school: `/api/admin/schools/{school_id}/notices`, `/api/admin/school-notices/{notice_id}`

## Life Room
GET `/api/life-room/current`
- `{life_room,members,todos,posts,rule,presence}`

POST `/api/life-room/{uid}/todos`
POST `/api/life-room/{uid}/rules`
POST `/api/life-room/{uid}/presence`
POST `/api/life-room/{uid}/posts`
POST `/api/life-room/{uid}/fill-policy`

## Admin School Schedule
PATCH `/api/admin/schools/{school_id}/schedule`
- `pre_matching_start/end`
- `roommate_apply_start/end`
- `room_life_start/end`

## Guard Rules
- `phase=life` 에서는 매칭 시작/선호 변경 차단
- 선호 변경은 `최초 저장 제외 + 실제 값 변경 시` 카운트 증가
- 활성 생활방 존재 시 세션 진입 차단(`이미 생활방이 있습니다`)
