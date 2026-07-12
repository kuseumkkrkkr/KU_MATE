import json
import os

from app import app, db


def _reset_db():
    for path in [db.DB_PATH, 'roommates_api.db', 'roommates.db', 'forlocal.db']:
      if os.path.exists(path):
        os.remove(path)
    db.init_db(drop_if_corrupt=True)


def _post(client, path, data, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return client.post(path, data=json.dumps(data), headers=headers)


def _get(client, path, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return client.get(path, headers=headers)


def _register_and_login(client, login_id: str, name: str, gender: str, birth_year: int):
    register_payload = {
        'login_id': login_id,
        'password': '123456',
        'name': name,
        'student_id': f'S{login_id[-4:]}',
        'birth_year': birth_year,
        'is_enrolled': False,
        'gender': gender,
        'region_name': 'seoul',
    }
    reg = _post(client, '/api/auth/register', register_payload)
    assert reg.status_code == 201, f'register failed: {reg.status_code} {reg.data}'

    login = _post(client, '/api/auth/login', {'login_id': login_id, 'password': '123456'})
    assert login.status_code == 200, f'login failed: {login.status_code} {login.data}'
    token = login.get_json()['token']

    me = _get(client, '/api/me', token)
    assert me.status_code == 200, f'me failed: {me.status_code} {me.data}'
    user_uid = me.get_json()['uid']
    return token, user_uid


def test_chat_roundtrip_and_reuse():
    _reset_db()
    client = app.test_client()

    token_a, uid_a = _register_and_login(client, 'chat_a', 'chat_a', 'male', 2002)
    token_b, uid_b = _register_and_login(client, 'chat_b', 'chat_b', 'female', 2003)

    enter = _post(client, '/api/match/session/enter', {'candidates': [uid_b]}, token_a)
    assert enter.status_code == 201, f'enter_session failed: {enter.status_code} {enter.data}'
    enter_body = enter.get_json()
    thread_ids = list(enter_body.get('thread_ids') or [])
    assert len(thread_ids) == 1, f'unexpected thread_ids: {enter_body}'
    thread_id = thread_ids[0]

    send_1 = _post(client, f'/api/chat/threads/{thread_id}/messages', {'content': 'hello-1', 'type': 'text'}, token_a)
    assert send_1.status_code == 201, f'send_1 failed: {send_1.status_code} {send_1.data}'

    send_2 = _post(client, f'/api/chat/threads/{thread_id}/messages', {'content': 'hello-2', 'type': 'text'}, token_b)
    assert send_2.status_code == 201, f'send_2 failed: {send_2.status_code} {send_2.data}'

    send_3 = _post(client, f'/api/chat/threads/{thread_id}/messages', {'content': 'hello-3', 'type': 'text'}, token_a)
    assert send_3.status_code == 201, f'send_3 failed: {send_3.status_code} {send_3.data}'

    inbox_a = _get(client, f'/api/chat/threads/{thread_id}/messages', token_a)
    inbox_b = _get(client, f'/api/chat/threads/{thread_id}/messages', token_b)
    assert inbox_a.status_code == 200, f'inbox_a failed: {inbox_a.status_code} {inbox_a.data}'
    assert inbox_b.status_code == 200, f'inbox_b failed: {inbox_b.status_code} {inbox_b.data}'

    msgs_a = inbox_a.get_json()
    msgs_b = inbox_b.get_json()
    assert isinstance(msgs_a, list) and isinstance(msgs_b, list), 'messages endpoint must return list'
    assert len(msgs_a) == 3 and len(msgs_b) == 3, f'unexpected message counts: {len(msgs_a)}, {len(msgs_b)}'

    contents = [m.get('content') for m in msgs_a]
    assert contents == ['hello-1', 'hello-2', 'hello-3'], f'unexpected contents: {contents}'
    assert any(m.get('sender') == uid_a for m in msgs_b), 'user A message missing in user B inbox'
    assert any(m.get('sender') == uid_b for m in msgs_a), 'user B message missing in user A inbox'

    reused = _post(client, '/api/match/session/enter', {'candidates': [uid_b]}, token_a)
    assert reused.status_code == 200, f'reuse enter failed: {reused.status_code} {reused.data}'
    reused_body = reused.get_json()
    assert reused_body.get('reused') is True, f'expected reused=true: {reused_body}'
    assert reused_body.get('thread_ids') == [thread_id], f'expected same thread id: {reused_body}'


def test_active_session_allows_async_expansion_until_five_threads():
    _reset_db()
    client = app.test_client()

    token_owner, owner_uid = _register_and_login(client, 'owner_u', 'owner', 'male', 2001)
    candidates = []
    for idx in range(1, 6):
        token, uid = _register_and_login(
            client,
            f'cand_{idx}',
            f'cand_{idx}',
            'female' if idx % 2 == 0 else 'male',
            2000 + idx,
        )
        candidates.append((token, uid))

    five_uids = [uid for _, uid in candidates]
    enter_first = _post(client, '/api/match/session/enter', {'candidates': [five_uids[0]]}, token_owner)
    assert enter_first.status_code == 201, f'enter_first failed: {enter_first.status_code} {enter_first.data}'
    first_body = enter_first.get_json()
    thread_ids = list(first_body.get('thread_ids') or [])
    assert len(thread_ids) == 1, f'expected one thread: {first_body}'

    first_thread = thread_ids[0]
    send_first = _post(client, f'/api/chat/threads/{first_thread}/messages', {'content': 'active chat', 'type': 'text'}, token_owner)
    assert send_first.status_code == 201, f'send_first failed: {send_first.status_code} {send_first.data}'

    active = _get(client, '/api/match/session/active', token_owner)
    assert active.status_code == 200, f'active failed: {active.status_code} {active.data}'
    active_rows = list(active.get_json().get('sessions') or [])
    assert len(active_rows) == 1, f'owner should have one active session: {active_rows}'

    enter_more = _post(client, '/api/match/session/enter', {'candidates': five_uids[1:]}, token_owner)
    assert enter_more.status_code == 200, (
        f'owner should be able to open another async chat in the same session: '
        f'{enter_more.status_code} {enter_more.data}'
    )
    more_body = enter_more.get_json()
    assert more_body.get('session_id') == first_body.get('session_id'), f'extra chats should reuse same session: {more_body}'
    more_thread_ids = list(more_body.get('thread_ids') or [])
    assert len(more_thread_ids) == 4, f'expected four more threads: {more_body}'
    thread_ids.extend(more_thread_ids)

    for tid in thread_ids[:4]:
        leave_each = _post(
            client,
            f'/api/chat/threads/{tid}/leave',
            {'reason': f'close all {tid[:8]}'},
            token_owner,
        )
        assert leave_each.status_code == 200, f'leave_each failed: {leave_each.status_code} {leave_each.data}'

    active_after = _get(client, '/api/match/session/active', token_owner)
    assert active_after.status_code == 200, f'active_after failed: {active_after.status_code} {active_after.data}'
    active_rows_after = list(active_after.get_json().get('sessions') or [])
    assert len(active_rows_after) == 1, f'one remaining open thread should keep session active: {active_rows_after}'

    enter_reuse_remaining = _post(client, '/api/match/session/enter', {'candidates': [five_uids[4]]}, token_owner)
    assert enter_reuse_remaining.status_code == 200, f'remaining thread reuse should pass: {enter_reuse_remaining.status_code} {enter_reuse_remaining.data}'
    assert enter_reuse_remaining.get_json().get('thread_ids') == [thread_ids[4]], f'expected same remaining thread: {enter_reuse_remaining.get_json()}'


if __name__ == '__main__':
    test_chat_roundtrip_and_reuse()
    test_active_session_allows_async_expansion_until_five_threads()
    print('chat roundtrip test passed')
