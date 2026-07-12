import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../services/api_service.dart';
import 'match_history_screen.dart';

class LifeRoomScreen extends StatefulWidget {
  const LifeRoomScreen({super.key});

  @override
  State<LifeRoomScreen> createState() => _LifeRoomScreenState();
}

class _LifeRoomScreenState extends State<LifeRoomScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _api = ApiService();
  late final TabController _tabs;
  bool _loading = true;
  Map<String, dynamic>? _room;
  List<Map<String, dynamic>> _todos = const [];
  List<Map<String, dynamic>> _events = const [];
  List<Map<String, dynamic>> _posts = const [];
  List<Map<String, dynamic>> _presence = const [];
  Map<String, dynamic>? _rule;
  bool _isUnderstaffed = false;
  int _currentMemberCount = 0;
  int _targetCapacity = 2;
  String _fillStrategy = 'continue';
  bool _fixedHall = false;
  List<Map<String, dynamic>> _groupMessages = const [];
  List<Map<String, dynamic>> _matchHistory = const [];
  Map<String, dynamic>? _recruitSession;
  Map<String, dynamic>? _fillSurvey;
  bool _canCreateRecruitSession = true;
  bool _exitingForNoLifeRoom = false;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 8, vsync: this);
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getCurrentLifeRoom();
      final roomUid =
          (res['life_room'] is Map ? res['life_room']['uid'] : null)
              ?.toString() ??
          '';
      if (roomUid.isEmpty && !_exitingForNoLifeRoom && mounted) {
        _exitingForNoLifeRoom = true;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          Get.snackbar('안내', '생활 기간이 종료되어 매칭 화면으로 돌아갑니다.');
          if (Navigator.of(context).canPop()) {
            Navigator.of(context).pop();
          }
        });
      }
      setState(() {
        _room = res['life_room'] is Map<String, dynamic>
            ? Map<String, dynamic>.from(res['life_room'] as Map)
            : null;
        _todos = List<Map<String, dynamic>>.from(res['todos'] ?? const []);
        _events = List<Map<String, dynamic>>.from(res['events'] ?? const []);
        _posts = List<Map<String, dynamic>>.from(res['posts'] ?? const []);
        _presence = List<Map<String, dynamic>>.from(
          res['presence'] ?? const [],
        );
        _rule = res['rule'] is Map<String, dynamic>
            ? Map<String, dynamic>.from(res['rule'] as Map)
            : null;
        _isUnderstaffed = res['is_understaffed'] == true;
        _currentMemberCount = res['current_member_count'] ?? 0;
        _targetCapacity = res['target_capacity'] ?? 2;
        _fillStrategy = _room?['fill_strategy'] ?? 'continue';
        _fixedHall = _room?['fixed_hall'] == 1;
      });
      if (roomUid.isNotEmpty) {
        final statusRes = await _api.getLifeRoomStatus(roomUid);
        setState(() {
          _isUnderstaffed = statusRes['is_understaffed'] == true;
          _currentMemberCount =
              statusRes['current_member_count'] ?? _currentMemberCount;
          _targetCapacity = statusRes['target_capacity'] ?? _targetCapacity;
          _fillStrategy = statusRes['fill_strategy'] ?? _fillStrategy;
          _fixedHall = statusRes['fixed_hall'] == true;
          _recruitSession =
              statusRes['open_recruit_session'] is Map<String, dynamic>
              ? Map<String, dynamic>.from(
                  statusRes['open_recruit_session'] as Map,
                )
              : null;
          _canCreateRecruitSession =
              statusRes['can_create_recruit_session'] == true;
        });
        try {
          final historyRes = await _api.getLifeRoomMatchHistory(roomUid);
          setState(
            () => _matchHistory = List<Map<String, dynamic>>.from(
              historyRes['history'] ?? const [],
            ),
          );
        } catch (_) {}
        try {
          final chatRes = await _api.getLifeRoomGroupChat(roomUid);
          setState(
            () => _groupMessages = List<Map<String, dynamic>>.from(chatRes),
          );
        } catch (_) {}
        try {
          final surveyRes = await _api.getFillSurvey(roomUid);
          setState(
            () => _fillSurvey = surveyRes['survey'] is Map<String, dynamic>
                ? Map<String, dynamic>.from(surveyRes['survey'] as Map)
                : null,
          );
        } catch (_) {}
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  String get _roomUid => (_room?['uid'] ?? '').toString();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('룸메이트 생활방'),
        actions: [
          IconButton(
            tooltip: '매칭 이력 보기',
            onPressed: () {
              Get.to(
                () => MatchHistoryScreen(
                  refreshToken: DateTime.now().millisecondsSinceEpoch,
                ),
              );
            },
            icon: const Icon(Icons.history_rounded),
          ),
        ],
        bottom: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabs: const [
            Tab(text: '채팅'),
            Tab(text: '일정'),
            Tab(text: '할일'),
            Tab(text: '규칙'),
            Tab(text: '게시판'),
            Tab(text: '재실'),
            Tab(text: '관리'),
            Tab(text: '매칭기록'),
          ],
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _room == null
          ? const Center(child: Text('현재 생활방이 없습니다.'))
          : Column(
              children: [
                if (_isUnderstaffed)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    color: Colors.orange.shade100,
                    child: Text(
                      '현재 인원이 부족합니다 ($_currentMemberCount/$_targetCapacity)',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                Expanded(
                  child: TabBarView(
                    controller: _tabs,
                    children: [
                      _chatTab(),
                      _eventTab(),
                      _todoTab(),
                      _ruleTab(),
                      _postTab(),
                      _presenceTab(),
                      _managementTab(),
                      _matchHistoryTab(),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _chatTab() {
    final msgCtrl = TextEditingController();
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(12),
            children: _groupMessages.map((m) {
              final isMe = (m['sender'] ?? '') == _api.currentUserId;
              return Align(
                alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: isMe ? Colors.blue.shade100 : Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text((m['content'] ?? '').toString()),
                ),
              );
            }).toList(),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: msgCtrl,
                  decoration: const InputDecoration(labelText: '메시지'),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.send),
                onPressed: () async {
                  if (_roomUid.isEmpty || msgCtrl.text.trim().isEmpty) return;
                  await _api.sendLifeRoomGroupMessage(
                    _roomUid,
                    msgCtrl.text.trim(),
                  );
                  msgCtrl.clear();
                  _load();
                },
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _eventTab() {
    final title = TextEditingController();
    final start = TextEditingController();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: title,
                  decoration: const InputDecoration(labelText: '일정 제목'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: start,
                  decoration: const InputDecoration(labelText: '시작시각(ISO)'),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: () async {
                  if (_roomUid.isEmpty) return;
                  await _api.addLifeRoomEvent(_roomUid, {
                    'title': title.text.trim(),
                    'start_at': start.text.trim(),
                    'view_type': 'month',
                  });
                  title.clear();
                  start.clear();
                  _load();
                },
                child: const Text('추가'),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            children: _events
                .map(
                  (e) => ListTile(
                    title: Text((e['title'] ?? '').toString()),
                    subtitle: Text((e['start_at'] ?? '').toString()),
                  ),
                )
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _todoTab() {
    final ctrl = TextEditingController();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: ctrl,
                  decoration: const InputDecoration(labelText: '할일 추가'),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: () async {
                  if (_roomUid.isEmpty || ctrl.text.trim().isEmpty) return;
                  await _api.addLifeRoomTodo(_roomUid, {
                    'title': ctrl.text.trim(),
                  });
                  ctrl.clear();
                  _load();
                },
                child: const Text('추가'),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            children: _todos
                .map(
                  (t) => ListTile(
                    title: Text((t['title'] ?? '').toString()),
                    subtitle: Text((t['due_date'] ?? '').toString()),
                    trailing: Checkbox(
                      value: (t['done'] ?? 0) == 1,
                      onChanged: (_) async {
                        await _api.toggleLifeRoomTodo(
                          _roomUid,
                          (t['uid'] ?? '').toString(),
                        );
                        _load();
                      },
                    ),
                  ),
                )
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _ruleTab() {
    final ctrl = TextEditingController(text: (_rule?['body'] ?? '').toString());
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          TextField(
            controller: ctrl,
            maxLines: 6,
            decoration: const InputDecoration(
              labelText: '방 규칙 (생활기간 중 총 3회 변경)',
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerRight,
            child: ElevatedButton(
              onPressed: () async {
                if (_roomUid.isEmpty || ctrl.text.trim().isEmpty) return;
                await _api.updateLifeRoomRule(_roomUid, ctrl.text.trim());
                _load();
              },
              child: const Text('저장'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _postTab() {
    final title = TextEditingController();
    final body = TextEditingController();
    bool pinned = false;
    return StatefulBuilder(
      builder: (context, setStateLocal) {
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  TextField(
                    controller: title,
                    decoration: const InputDecoration(labelText: '제목'),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: body,
                    maxLines: 3,
                    decoration: const InputDecoration(labelText: '내용'),
                  ),
                  Row(
                    children: [
                      Checkbox(
                        value: pinned,
                        onChanged: (v) =>
                            setStateLocal(() => pinned = v ?? false),
                      ),
                      const Text('상단 고정(인당 최대 10회)'),
                      const Spacer(),
                      ElevatedButton(
                        onPressed: () async {
                          if (_roomUid.isEmpty) return;
                          await _api.createLifeRoomPost(_roomUid, {
                            'title': title.text.trim(),
                            'body': body.text.trim(),
                            'pinned': pinned,
                          });
                          title.clear();
                          body.clear();
                          setStateLocal(() => pinned = false);
                          _load();
                        },
                        child: const Text('작성'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                children: _posts
                    .map(
                      (p) => ListTile(
                        title: Text((p['title'] ?? '').toString()),
                        subtitle: Text((p['body'] ?? '').toString()),
                      ),
                    )
                    .toList(),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _presenceTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ElevatedButton(
                onPressed: () async {
                  await _api.updateLifeRoomPresence(_roomUid, 'in');
                  _load();
                },
                child: const Text('재실'),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: () async {
                  await _api.updateLifeRoomPresence(_roomUid, 'out');
                  _load();
                },
                child: const Text('퇴실'),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            children: _presence
                .map(
                  (p) => ListTile(
                    title: Text((p['user_uid'] ?? '').toString()),
                    subtitle: Text((p['status'] ?? '').toString()),
                  ),
                )
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _managementTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('충원 정책', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(
                value: 'continue',
                label: Text('계속 충원'),
                icon: Icon(Icons.autorenew),
              ),
              ButtonSegment(
                value: 'random',
                label: Text('랜덤 지정'),
                icon: Icon(Icons.shuffle),
              ),
            ],
            selected: {_fillStrategy},
            onSelectionChanged: (vals) async {
              final s = vals.first;
              await _api.updateLifeRoomFillPolicy(_roomUid, s);
              setState(() => _fillStrategy = s);
            },
          ),
          const SizedBox(height: 20),
          Text('관 확정', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (!_fixedHall)
            const Text('아직 모든 멤버가 관을 확정하지 않았습니다. 관을 확정하면 매칭 받기를 사용할 수 있습니다.')
          else
            const Text(
              '모든 멤버가 관을 확정했습니다.',
              style: TextStyle(
                color: Colors.green,
                fontWeight: FontWeight.w600,
              ),
            ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: () async {
              final rtId = await showDialog<int>(
                context: context,
                builder: (ctx) {
                  final ctrl = TextEditingController();
                  return AlertDialog(
                    title: const Text('방유형 ID 입력'),
                    content: TextField(
                      controller: ctrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'room_type_id',
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(ctx),
                        child: const Text('취소'),
                      ),
                      ElevatedButton(
                        onPressed: () =>
                            Navigator.pop(ctx, int.tryParse(ctrl.text.trim())),
                        child: const Text('확인'),
                      ),
                    ],
                  );
                },
              );
              if (rtId != null) {
                await _api.confirmLifeRoomHall(_roomUid, rtId);
                _load();
              }
            },
            child: const Text('관 확정하기'),
          ),
          const SizedBox(height: 20),
          Text('추가 매칭', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_recruitSession != null)
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('신청기간 진행 중 (ID: ${_recruitSession!['uid']})'),
                const SizedBox(height: 8),
                ElevatedButton(
                  onPressed: () async {
                    await _api.updateRecruitSession(
                      _roomUid,
                      _recruitSession!['uid'].toString(),
                      'closed',
                    );
                    _load();
                  },
                  child: const Text('신청기간 종료'),
                ),
              ],
            )
          else if (!_canCreateRecruitSession)
            const Text(
              '룸메이트 신청 기간이 아니어서 추가 매칭 세션을 생성할 수 없습니다.',
              style: TextStyle(color: Colors.grey),
            )
          else
            ElevatedButton(
              onPressed: () async {
                await _api.createRecruitSession(_roomUid);
                _load();
              },
              child: const Text('추가 매칭 세션 열기'),
            ),
          const SizedBox(height: 20),
          Text(
            '충원용 설문 (자동 생성)',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (_fillSurvey != null && _fillSurvey!.isNotEmpty)
            ..._fillSurvey!.entries.map(
              (e) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  '${e.key}: ${e.value}',
                  style: const TextStyle(fontSize: 13),
                ),
              ),
            )
          else
            const Text(
              '멤버 설문 데이터가 없습니다.',
              style: TextStyle(fontSize: 13, color: Colors.grey),
            ),
          const SizedBox(height: 20),
          Text('생활기간 종료', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          OutlinedButton(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
            onPressed: () async {
              final ok = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('생활기간 종료'),
                  content: const Text('생활방을 종료하시겠습니까? 이 작업은 되돌릴 수 없습니다.'),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx, false),
                      child: const Text('취소'),
                    ),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                      ),
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('종료'),
                    ),
                  ],
                ),
              );
              if (ok == true) {
                await _api.closeLifeRoomPeriod(_roomUid);
                _load();
              }
            },
            child: const Text('생활기간 종료'),
          ),
        ],
      ),
    );
  }

  Widget _matchHistoryTab() {
    return _matchHistory.isEmpty
        ? const Center(child: Text('매칭 기록이 없습니다.'))
        : ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: _matchHistory.length,
            separatorBuilder: (_, __) => const Divider(),
            itemBuilder: (_, i) {
              final h = _matchHistory[i];
              return ListTile(
                title: Text(
                  '${h['matched_with_type'] ?? ''} - ${h['matched_with_uid'] ?? ''}',
                ),
                subtitle: Text(
                  '상태: ${h['status'] ?? ''} | ${h['created_at'] ?? ''}',
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.grey),
                  onPressed: () async {
                    await _api.deleteLifeRoomMatchHistory(
                      _roomUid,
                      h['uid'].toString(),
                    );
                    _load();
                  },
                ),
              );
            },
          );
  }
}
