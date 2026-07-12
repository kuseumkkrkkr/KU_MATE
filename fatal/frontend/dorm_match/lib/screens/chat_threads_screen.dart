import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../controllers/match_controller.dart';
import '../services/api_service.dart';
import 'opened_survey_screen.dart';

enum ChatSortMode { byMatch, byDate, byName }

class ChatThreadsScreen extends StatefulWidget {
  const ChatThreadsScreen({super.key});

  @override
  State<ChatThreadsScreen> createState() => _ChatThreadsScreenState();
}

class _ChatThreadsScreenState extends State<ChatThreadsScreen> {
  final ctrl = Get.isRegistered<MatchController>()
      ? Get.find<MatchController>()
      : Get.put(MatchController());
  final _api = ApiService();
  ChatSortMode _sortMode = ChatSortMode.byMatch;
  final Map<String, int> _sessionOrder = {};
  final Map<String, Map<String, dynamic>> _sessionMeta = {};

  @override
  void initState() {
    super.initState();
    ctrl.fetchThreads();
    _loadSessionOrder();
  }

  Future<void> _loadSessionOrder() async {
    try {
      final rows = await _api.getSessionHistory();
      final sessions = List<Map<String, dynamic>>.from(rows);
      final order = <String, int>{};
      final meta = <String, Map<String, dynamic>>{};
      for (var i = 0; i < sessions.length; i++) {
        final id = sessions[i]['session_id']?.toString() ?? '';
        if (id.isNotEmpty) {
          order[id] = i;
          meta[id] = sessions[i];
        }
      }
      if (mounted) {
        setState(() {
          _sessionOrder
            ..clear()
            ..addAll(order);
          _sessionMeta
            ..clear()
            ..addAll(meta);
        });
      }
    } catch (_) {}
  }

  List<Map<String, dynamic>> _sortedThreads(List<Map<String, dynamic>> source) {
    final list = List<Map<String, dynamic>>.from(source);
    DateTime parseDate(Map<String, dynamic> t) {
      return DateTime.tryParse(t['created_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0);
    }

    switch (_sortMode) {
      case ChatSortMode.byDate:
        list.sort((a, b) => parseDate(b).compareTo(parseDate(a)));
        return list;
      case ChatSortMode.byName:
        list.sort((a, b) {
          final an = (a['other_user']?.toString() ?? '').toLowerCase();
          final bn = (b['other_user']?.toString() ?? '').toLowerCase();
          final c = an.compareTo(bn);
          if (c != 0) return c;
          return parseDate(b).compareTo(parseDate(a));
        });
        return list;
      case ChatSortMode.byMatch:
        list.sort((a, b) {
          final as = a['session_id']?.toString() ?? '';
          final bs = b['session_id']?.toString() ?? '';
          final ao = _sessionOrder[as] ?? 1 << 30;
          final bo = _sessionOrder[bs] ?? 1 << 30;
          if (ao != bo) return ao.compareTo(bo);
          return parseDate(b).compareTo(parseDate(a));
        });
        return list;
    }
  }

  List<Map<String, dynamic>> _buildListEntries(
    List<Map<String, dynamic>> sorted,
  ) {
    if (_sortMode != ChatSortMode.byMatch) {
      return sorted.map((t) => {'__type': 'thread', 'data': t}).toList();
    }
    final entries = <Map<String, dynamic>>[];
    String lastSession = '';
    for (final t in sorted) {
      final sid = t['session_id']?.toString() ?? '';
      if (sid != lastSession) {
        entries.add({
          '__type': 'divider',
          'session_id': sid,
          'label': _matchDividerLabel(sid),
        });
        lastSession = sid;
      }
      entries.add({'__type': 'thread', 'data': t});
    }
    return entries;
  }

  String _matchDividerLabel(String sessionId) {
    final m = _sessionMeta[sessionId] ?? const <String, dynamic>{};
    final kindRaw = m['match_kind']?.toString();
    final dateRaw = m['created_at']?.toString() ?? '';
    String kind;
    switch (kindRaw) {
      case 'one_room':
        kind = '자취방';
        break;
      case 'share_house':
        kind = '쉐어하우스';
        break;
      case 'dormitory':
      default:
        kind = '기숙사';
        break;
    }
    final d = DateTime.tryParse(dateRaw);
    final dateText = d == null
        ? '-'
        : '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
    return '$kind · $dateText';
  }

  String _sortLabel(ChatSortMode mode) {
    switch (mode) {
      case ChatSortMode.byMatch:
        return '매칭순';
      case ChatSortMode.byDate:
        return '날짜순';
      case ChatSortMode.byName:
        return '이름순';
    }
  }

  Widget _sortMenuRow(
    String text, {
    required bool selected,
    bool topRounded = false,
  }) {
    return Container(
      height: 56,
      alignment: Alignment.centerLeft,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFFD4D4D8) : const Color(0xFFF3F4F6),
        borderRadius: topRounded
            ? const BorderRadius.vertical(top: Radius.circular(14))
            : BorderRadius.zero,
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: Color(0xFF1F2937),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('채팅'),
        actions: [
          PopupMenuButton<ChatSortMode>(
            initialValue: _sortMode,
            tooltip: '정렬',
            onSelected: (mode) => setState(() => _sortMode = mode),
            color: const Color(0xFFF3F4F6),
            elevation: 8,
            offset: const Offset(0, 46),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
            constraints: const BoxConstraints(minWidth: 220, maxWidth: 220),
            itemBuilder: (context) => [
              PopupMenuItem(
                value: ChatSortMode.byMatch,
                padding: EdgeInsets.zero,
                child: _sortMenuRow(
                  _sortLabel(ChatSortMode.byMatch),
                  selected: _sortMode == ChatSortMode.byMatch,
                  topRounded: true,
                ),
              ),
              PopupMenuItem(
                value: ChatSortMode.byDate,
                padding: EdgeInsets.zero,
                child: _sortMenuRow(
                  _sortLabel(ChatSortMode.byDate),
                  selected: _sortMode == ChatSortMode.byDate,
                ),
              ),
              PopupMenuItem(
                value: ChatSortMode.byName,
                padding: EdgeInsets.zero,
                child: _sortMenuRow(
                  _sortLabel(ChatSortMode.byName),
                  selected: _sortMode == ChatSortMode.byName,
                ),
              ),
            ],
            child: Container(
              margin: const EdgeInsets.only(right: 12),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFF3F4F6),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _sortLabel(_sortMode),
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF111827),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Icon(
                    Icons.expand_more_rounded,
                    size: 18,
                    color: Color(0xFF4B5563),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      body: Obx(() {
        if (ctrl.chatThreads.isEmpty) {
          return _emptyState();
        }
        final sorted = _sortedThreads(
          List<Map<String, dynamic>>.from(ctrl.chatThreads),
        );
        final entries = _buildListEntries(sorted);
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: entries.length,
          itemBuilder: (_, i) {
            final e = entries[i];
            final type = e['__type']?.toString() ?? 'thread';
            if (type == 'divider') {
              return Padding(
                padding: EdgeInsets.only(top: i == 0 ? 0 : 12, bottom: 8),
                child: Row(
                  children: [
                    const Expanded(child: Divider(height: 1)),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Text(
                        e['label']?.toString() ?? '매칭 · 날짜',
                        style: const TextStyle(
                          color: Color(0xFF6B7280),
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    const Expanded(child: Divider(height: 1)),
                  ],
                ),
              );
            }
            final thread = Map<String, dynamic>.from(
              e['data'] as Map<String, dynamic>,
            );
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _threadCard(thread),
            );
          },
        );
      }),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.chat_bubble_outline,
            size: 48,
            color: Colors.grey.shade300,
          ),
          const SizedBox(height: 12),
          const Text(
            '생성된 채팅방이 없습니다.',
            style: TextStyle(
              color: Color(0xFF9CA3AF),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            '매칭 카드에서 채팅을 시작해 주세요.',
            style: TextStyle(color: Color(0xFFB0B5BD), fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _threadCard(Map<String, dynamic> t) {
    final other = t['other_user']?.toString() ?? '상대방 없음';
    final status = t['status']?.toString() ?? 'open';
    final isClosed = status != 'open';
    final closedReason = t['closed_reason']?.toString() ?? '';
    final isStopped = closedReason == 'left';

    return GestureDetector(
      onTap: () => Get.to(
        () => ChatRoomScreen(
          threadId: t['thread_id']?.toString() ?? '',
          otherUser: other,
        ),
      ),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0D000000),
              blurRadius: 12,
              offset: Offset(0, 4),
            ),
          ],
        ),
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: isClosed
                    ? Colors.grey.shade200
                    : const Color(0xFFDBEAFE),
                borderRadius: BorderRadius.circular(14),
              ),
              alignment: Alignment.center,
              child: Text(
                other.isNotEmpty ? other.substring(0, 1) : '?',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: isClosed
                      ? Colors.grey.shade500
                      : const Color(0xFF1E40AF),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    other,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: isClosed
                          ? Colors.grey.shade400
                          : const Color(0xFF1F2937),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: isClosed
                          ? const Color(0xFFF3F4F6)
                          : const Color(0xFFDCFCE7),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      isClosed ? _closedLabel(closedReason) : '진행 중',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: isClosed
                            ? Colors.grey.shade500
                            : const Color(0xFF16A34A),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              isStopped ? Icons.info_outline : Icons.arrow_forward_ios,
              size: 16,
              color: Colors.grey.shade400,
            ),
          ],
        ),
      ),
    );
  }

  String _closedLabel(String reason) {
    if (reason == 'already_matched') return '상대가 이미 매칭됨';
    if (reason == 'no_response') return '무응답으로 종료';
    if (reason == 'cancelled') return '취소됨';
    if (reason == 'rematch') return '리매치 종료';
    if (reason == 'rejected') return '매칭 거절로 종료';
    if (reason == 'left') return '상대 중단';
    return '종료됨';
  }
}

class ChatRoomScreen extends StatefulWidget {
  final String threadId;
  final String otherUser;

  const ChatRoomScreen({
    super.key,
    required this.threadId,
    required this.otherUser,
  });

  @override
  State<ChatRoomScreen> createState() => _ChatRoomScreenState();
}

class _ChatRoomScreenState extends State<ChatRoomScreen> {
  static const String _weeklyKey = 'quick_functions_weekly_selected';
  static const String _monthlyMemoKey = 'quick_functions_monthly_memo';
  static const String _quickSharePrefix =
      '\u2063\u2063\u2063\u2063::ROOMANTIC::';

  final ctrl = Get.find<MatchController>();
  final _api = ApiService();
  final textCtrl = TextEditingController();
  final scrollCtrl = ScrollController();

  bool _isLoadingOlder = false;
  bool _isRestoringMessages = false;
  bool _isMetaLoading = false;
  bool _isSubmittingDecision = false;
  int _serverExchangeCount = 0;
  bool _surveyEnabled = false;
  bool _matchingEnabled = false;
  bool _mySurveyOpened = false;
  bool _otherSurveyOpened = false;
  String _myDecision = '';
  String _otherDecision = '';
  String _myReason = '';
  String _otherReason = '';
  String _sessionStatus = '';

  @override
  void initState() {
    super.initState();
    scrollCtrl.addListener(_onScroll);
    _restoreMessages(markRead: true);
    _loadThreadMeta();
  }

  @override
  void reassemble() {
    super.reassemble();
    _restoreMessages(markRead: false);
  }

  @override
  void dispose() {
    scrollCtrl.removeListener(_onScroll);
    textCtrl.dispose();
    scrollCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!scrollCtrl.hasClients || _isLoadingOlder) return;
    if (scrollCtrl.position.pixels <= 80) {
      _loadOlder();
    }
  }

  Future<void> _loadOlder() async {
    if (_isLoadingOlder) return;

    final oldMax = scrollCtrl.hasClients
        ? scrollCtrl.position.maxScrollExtent
        : 0.0;
    final oldOffset = scrollCtrl.hasClients ? scrollCtrl.position.pixels : 0.0;

    setState(() {
      _isLoadingOlder = true;
    });

    final loaded = await ctrl.fetchOlderThreadMessages(
      widget.threadId,
      limit: 30,
    );
    if (!mounted) return;

    setState(() {
      _isLoadingOlder = false;
    });

    if (!loaded) return;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!scrollCtrl.hasClients) return;
      final newMax = scrollCtrl.position.maxScrollExtent;
      final delta = newMax - oldMax;
      final nextOffset = (oldOffset + delta).clamp(
        scrollCtrl.position.minScrollExtent,
        scrollCtrl.position.maxScrollExtent,
      );
      scrollCtrl.jumpTo(nextOffset);
    });
  }

  void _jumpToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!scrollCtrl.hasClients) return;
      scrollCtrl.jumpTo(scrollCtrl.position.maxScrollExtent);
    });
  }

  Future<void> _restoreMessages({required bool markRead}) async {
    if (_isRestoringMessages) return;
    if (mounted) {
      setState(() {
        _isRestoringMessages = true;
      });
    } else {
      _isRestoringMessages = true;
    }

    try {
      await ctrl.openThreadMessages(widget.threadId, limit: 30);
      await _loadThreadMeta();
      if (!mounted) return;
      _jumpToBottom();
      if (markRead && !ctrl.isThreadClosed(widget.threadId)) {
        ctrl.markThreadRead(widget.threadId);
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRestoringMessages = false;
        });
      } else {
        _isRestoringMessages = false;
      }
    }
  }

  Future<void> _loadThreadMeta() async {
    if (_isMetaLoading) return;
    setState(() => _isMetaLoading = true);
    try {
      final res = await _api.getThreadMeta(widget.threadId);
      if (!mounted) return;
      setState(() {
        _serverExchangeCount = (res['message_count'] as num?)?.toInt() ?? 0;
        _surveyEnabled = res['survey_enabled'] == true;
        _matchingEnabled = res['matching_enabled'] == true;
        _mySurveyOpened = res['my_survey_opened'] == true;
        _otherSurveyOpened = res['other_survey_opened'] == true;
        _myDecision = (res['my_decision']?.toString() ?? '').trim();
        _otherDecision = (res['other_decision']?.toString() ?? '').trim();
        _myReason = (res['my_reason']?.toString() ?? '').trim();
        _otherReason = (res['other_reason']?.toString() ?? '').trim();
        _sessionStatus = (res['session_status']?.toString() ?? '').trim();
      });
    } catch (_) {
    } finally {
      if (mounted) {
        setState(() => _isMetaLoading = false);
      } else {
        _isMetaLoading = false;
      }
    }
  }

  Future<void> _send() async {
    if (ctrl.isThreadClosed(widget.threadId)) return;
    final text = textCtrl.text.trim();
    if (text.isEmpty) return;

    final quickType = _commandToQuickShareType(text);
    final content = quickType == null
        ? text
        : await _buildQuickShareMessage(quickType);
    if (content.isEmpty) return;

    final ok = await ctrl.sendThreadMessage(widget.threadId, content);
    if (!mounted || !ok) return;

    textCtrl.clear();
    _loadThreadMeta();
    _jumpToBottom();
  }

  Future<void> _sendQuickShare(_QuickShareType type) async {
    if (ctrl.isThreadClosed(widget.threadId)) return;

    final content = await _buildQuickShareMessage(type);
    if (content.isEmpty) return;

    final ok = await ctrl.sendThreadMessage(widget.threadId, content);
    if (!mounted || !ok) return;
    _loadThreadMeta();
    _jumpToBottom();
  }

  _QuickShareType? _commandToQuickShareType(String text) {
    final normalized = text.replaceAll(RegExp(r'\s+'), '').toLowerCase();
    if (normalized == '나의일정' || normalized == '내일정') {
      return _QuickShareType.schedule;
    }
    if (normalized == '나의달력' || normalized == '내달력') {
      return _QuickShareType.calendar;
    }
    if (normalized == '나의설문지' || normalized == '내설문지') {
      return _QuickShareType.survey;
    }
    return null;
  }

  Future<String> _buildQuickShareMessage(_QuickShareType type) async {
    final payload = await _buildQuickSharePayload(type);
    if (payload == null) return '';
    return _encodeQuickSharePayload(payload);
  }

  Future<Map<String, dynamic>?> _buildQuickSharePayload(
    _QuickShareType type,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final createdAt = DateTime.now().toIso8601String();

    if (type == _QuickShareType.schedule) {
      final raw = prefs.getString(_weeklyKey);
      final selected = <int>{};
      if (raw != null) {
        try {
          final decoded = jsonDecode(raw);
          if (decoded is List) {
            for (final value in decoded) {
              if (value is int && value >= 0 && value < 168) {
                selected.add(value);
              }
            }
          }
        } catch (_) {}
      }

      if (selected.isEmpty) {
        return <String, dynamic>{
          'v': 1,
          'type': 'schedule',
          'title': '나의 일정',
          'summary': <String>['등록된 주간 가능 시간이 없어요.'],
          'details': <String>['등록된 주간 가능 시간이 없어요.'],
          'created_at': createdAt,
        };
      }

      final dayLabels = <String>[
        'Mon',
        'Tue',
        'Wed',
        'Thu',
        'Fri',
        'Sat',
        'Sun',
      ];
      final lines = <String>[];
      for (var day = 0; day < 7; day++) {
        final hours =
            selected
                .where((slot) => slot ~/ 24 == day)
                .map((slot) => slot % 24)
                .toList()
              ..sort();
        if (hours.isEmpty) continue;
        lines.add('${dayLabels[day]} ${_formatHourRanges(hours).join(', ')}');
      }

      if (lines.isEmpty) {
        return <String, dynamic>{
          'v': 1,
          'type': 'schedule',
          'title': '나의 일정',
          'summary': <String>['등록된 주간 가능 시간이 없어요.'],
          'details': <String>['등록된 주간 가능 시간이 없어요.'],
          'created_at': createdAt,
        };
      }

      return <String, dynamic>{
        'v': 1,
        'type': 'schedule',
        'title': '나의 일정',
        'summary': lines.take(3).toList(),
        'details': lines,
        'created_at': createdAt,
      };
    }

    if (type == _QuickShareType.survey) {
      try {
        final res = await _api.getProfile();
        final profile = (res['profile'] is Map)
            ? Map<String, dynamic>.from(res['profile'] as Map)
            : <String, dynamic>{};

        final name = (profile['name']?.toString() ?? '').trim();
        final persona = (profile['persona']?.toString() ?? '').trim();
        final hall = (profile['accepted_hall']?.toString() ?? '').trim();
        final fallbackHall = (profile['dormitory_hall']?.toString() ?? '')
            .trim();
        final roomCapacity = (profile['room_capacity'] as num?)?.toInt();
        final college = (profile['college']?.toString() ?? '').trim();
        final department = (profile['department']?.toString() ?? '').trim();

        final lines = <String>[
          if (name.isNotEmpty) '$name 사용자의 설문 요약',
          if (persona.isNotEmpty) '페르소나: $persona',
          if (college.isNotEmpty || department.isNotEmpty)
            '전공: ${[college, department].where((e) => e.isNotEmpty).join(' / ')}',
          if ((hall.isNotEmpty || fallbackHall.isNotEmpty) ||
              roomCapacity != null)
            '배정 정보: ${[hall.isNotEmpty ? hall : fallbackHall, roomCapacity == null ? '' : '$roomCapacity인실'].where((e) => e.isNotEmpty).join(' / ')}',
        ];

        return <String, dynamic>{
          'v': 1,
          'type': 'survey',
          'title': '나의 설문지',
          'summary': lines.isEmpty
              ? <String>['설문지를 공개했습니다.']
              : lines.take(3).toList(),
          'details': lines.isEmpty
              ? <String>['상대방이 아래 페이지에서 설문 전체를 확인할 수 있어요.']
              : lines,
          'created_at': createdAt,
        };
      } catch (_) {
        return <String, dynamic>{
          'v': 1,
          'type': 'survey',
          'title': '나의 설문지',
          'summary': <String>['설문지를 공개했습니다.'],
          'details': <String>['상대방이 아래 페이지에서 설문 전체를 확인할 수 있어요.'],
          'created_at': createdAt,
        };
      }
    }

    final raw = prefs.getString(_monthlyMemoKey);
    final memos = <DateTime, String>{};
    if (raw != null) {
      try {
        final decoded = jsonDecode(raw);
        if (decoded is Map) {
          for (final entry in decoded.entries) {
            final key = entry.key.toString();
            final text = entry.value?.toString().trim() ?? '';
            if (text.isEmpty) continue;
            final date = DateTime.tryParse(key);
            if (date == null) continue;
            memos[DateUtils.dateOnly(date)] = text;
          }
        }
      } catch (_) {}
    }

    if (memos.isEmpty) {
      return <String, dynamic>{
        'v': 1,
        'type': 'calendar',
        'title': '나의 달력',
        'summary': <String>['등록된 월간 일정이 없어요.'],
        'details': <String>['등록된 월간 일정이 없어요.'],
        'created_at': createdAt,
      };
    }

    final dates = memos.keys.toList()..sort();
    final today = DateUtils.dateOnly(DateTime.now());
    final upcoming = dates.where((d) => !d.isBefore(today)).take(5).toList();
    final picked = upcoming.isNotEmpty
        ? upcoming
        : dates.reversed.take(5).toList().reversed.toList();
    final lines = picked
        .map((date) => '${_formatDate(date)} ${memos[date] ?? ''}')
        .toList();

    return <String, dynamic>{
      'v': 1,
      'type': 'calendar',
      'title': '나의 달력',
      'summary': lines.take(3).toList(),
      'details': lines,
      'created_at': createdAt,
    };
  }

  String _encodeQuickSharePayload(Map<String, dynamic> payload) {
    return '$_quickSharePrefix${jsonEncode(payload)}';
  }

  List<String> _formatHourRanges(List<int> hours) {
    if (hours.isEmpty) return const <String>[];
    final ranges = <String>[];
    var start = hours.first;
    var prev = hours.first;

    for (var i = 1; i < hours.length; i++) {
      final hour = hours[i];
      if (hour == prev + 1) {
        prev = hour;
        continue;
      }
      ranges.add(_rangeLabel(start, prev + 1));
      start = hour;
      prev = hour;
    }
    ranges.add(_rangeLabel(start, prev + 1));
    return ranges;
  }

  String _rangeLabel(int start, int endExclusive) {
    return '${start.toString().padLeft(2, '0')}:00-${endExclusive.toString().padLeft(2, '0')}:00';
  }

  String _formatDate(DateTime day) {
    return '${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
  }

  Future<void> _retry(String localUid) async {
    await ctrl.retryThreadMessage(widget.threadId, localUid);
    _jumpToBottom();
  }

  Future<void> _confirmLeave() async {
    final reason = await _promptReason(
      title: '나가기 사유 입력',
      hint: '채팅방을 나가면 거절 처리되며 다시 매칭할 수 없습니다.\n최소 5자 이상 작성해 주세요',
      confirmLabel: '거절 후 나가기',
    );
    if (reason == null) return;
    if (!mounted) return;

    final shouldLeave = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('채팅방 나가기'),
        content: const Text(
          '채팅방을 나가면 즉시 거절로 처리되며 상대에게 전달됩니다.\n'
          '이 상대와는 다시 매칭할 수 없습니다. 계속할까요?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('거절 후 나가기'),
          ),
        ],
      ),
    );
    if (shouldLeave != true) return;

    final ok = await ctrl.leaveThread(widget.threadId, reason);
    if (!ok || !mounted) return;
    await ctrl.fetchActiveSessions();
    await ctrl.fetchPool();
    if (!mounted) return;
    Get.snackbar('완료', '매칭이 거절되었습니다.');
    Navigator.of(context).maybePop();
  }

  int _effectiveMessageCount(List<Map<String, dynamic>> messages) {
    final localCount = messages.where((m) {
      final sender = m['sender']?.toString() ?? '';
      final type = m['type']?.toString() ?? '';
      return sender != 'system' && type != 'system';
    }).length;
    return localCount > _serverExchangeCount
        ? localCount
        : _serverExchangeCount;
  }

  Future<void> _openMySurvey() async {
    final msgs = List<Map<String, dynamic>>.from(
      ctrl.threadMessages[widget.threadId] ?? const [],
    );
    final count = _effectiveMessageCount(msgs);
    if (!_mySurveyOpened && count < 4 && !_surveyEnabled) {
      Get.snackbar('안내', '설문지 공개는 채팅 4회 이상 후 가능합니다.');
      return;
    }
    try {
      final alreadyOpened = _mySurveyOpened;
      await _api.openThreadSurvey(widget.threadId);
      if (!alreadyOpened) {
        await _sendQuickShare(_QuickShareType.survey);
      }
      await _loadThreadMeta();
      if (!mounted) return;
      Get.snackbar('완료', '설문지를 공개했습니다.');
    } catch (e) {
      if (!mounted) return;
      Get.snackbar('오류', '설문지 공개에 실패했습니다: $e');
    }
  }

  Future<void> _openOtherSurveyAndReviews() async {
    try {
      final res = await _api.getOpenedSurveyProfile(widget.threadId);
      if (!mounted) return;
      final profile = (res['profile'] is Map<String, dynamic>)
          ? Map<String, dynamic>.from(res['profile'])
          : <String, dynamic>{};
      if (profile.isEmpty) {
        Get.snackbar('오류', '상대 설문 정보를 찾을 수 없습니다.');
        return;
      }
      final reviews = List<Map<String, dynamic>>.from(
        res['reviews'] ?? const <Map<String, dynamic>>[],
      );
      final title = profile['name']?.toString() ?? widget.otherUser;
      Get.to(
        () => OpenedSurveyScreen(
          title: title,
          otherUid: (res['other_uid']?.toString() ?? '').trim(),
          profile: profile,
          reviews: reviews,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      Get.snackbar('오류', '상대 설문/후기 조회에 실패했습니다: $e');
    }
  }

  Future<void> _submitDecision(String action) async {
    if (_isSubmittingDecision) return;
    final msgs = List<Map<String, dynamic>>.from(
      ctrl.threadMessages[widget.threadId] ?? const [],
    );
    final count = _effectiveMessageCount(msgs);
    if (count < 7 && !_matchingEnabled) {
      Get.snackbar('안내', '매칭 옵션은 채팅 7회 이상 후 활성화됩니다.');
      return;
    }

    String? reason;
    if (action == 'reject' || action == 'accept') {
      final isReject = action == 'reject';
      final inputReason = await _promptReason(
        title: isReject ? '거절 사유 입력' : '수락 사유 입력',
        hint: '최소 5자 이상 작성해 주세요',
        confirmLabel: isReject ? '거절' : '수락',
      );
      if (inputReason == null || inputReason.length < 5) return;
      reason = inputReason;
    }

    setState(() => _isSubmittingDecision = true);
    try {
      final res = await _api.decideThreadMatch(
        widget.threadId,
        action,
        reason: reason,
      );
      await ctrl.fetchThreads();
      await ctrl.fetchActiveSessions();
      await ctrl.fetchPool();
      await _loadThreadMeta();
      if (!mounted) return;

      final status = (res['status']?.toString() ?? '').trim();
      if (action == 'reject') {
        Get.snackbar('완료', '매칭이 거절되었습니다.');
        Navigator.of(context).maybePop();
        return;
      }
      if (status == 'confirmed') {
        Get.snackbar('완료', '매칭이 확정되었습니다.');
      } else if (status == 'on_hold') {
        Get.snackbar('완료', '매칭이 보류되었습니다.');
      } else {
        Get.snackbar('완료', '처리를 완료했습니다.');
      }
    } catch (e) {
      if (!mounted) return;
      Get.snackbar('오류', '요청 처리에 실패했습니다: $e');
    } finally {
      if (mounted) {
        setState(() => _isSubmittingDecision = false);
      } else {
        _isSubmittingDecision = false;
      }
    }
  }

  Future<void> _openActionSheet() async {
    await _loadThreadMeta();
    if (!mounted) return;
    final msgs = List<Map<String, dynamic>>.from(
      ctrl.threadMessages[widget.threadId] ?? const [],
    );
    final messageCount = _effectiveMessageCount(msgs);
    final remainToMatch = (7 - messageCount) > 0 ? 7 - messageCount : 0;
    final surveyEnabled =
        _mySurveyOpened || _surveyEnabled || messageCount >= 4;
    final matchingEnabled = _matchingEnabled || messageCount >= 7;
    final isClosed = ctrl.isThreadClosed(widget.threadId);
    final canSubmitDecision =
        !isClosed &&
        !_isSubmittingDecision &&
        (_sessionStatus.isEmpty || _sessionStatus == 'active') &&
        matchingEnabled;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) {
        return SafeArea(
          child: Container(
            margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFF8FAFC), Color(0xFFF1F5F9)],
              ),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x1A0F172A),
                  blurRadius: 28,
                  offset: Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 42,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFCBD5E1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                ),
                Row(
                  children: [
                    Expanded(
                      child: _sheetOutlinedButton(
                        label: '일정',
                        onTap: isClosed
                            ? null
                            : () {
                                Navigator.of(ctx).pop();
                                _sendQuickShare(_QuickShareType.schedule);
                              },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _sheetOutlinedButton(
                        label: '달력',
                        onTap: isClosed
                            ? null
                            : () {
                                Navigator.of(ctx).pop();
                                _sendQuickShare(_QuickShareType.calendar);
                              },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _sheetOutlinedButton(
                        label: _mySurveyOpened ? '설문지(공개됨)' : '설문지',
                        onTap: isClosed || !surveyEnabled
                            ? null
                            : () {
                                Navigator.of(ctx).pop();
                                _openMySurvey();
                              },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_otherSurveyOpened)
                  GestureDetector(
                    onTap: () {
                      Navigator.of(ctx).pop();
                      _openOtherSurveyAndReviews();
                    },
                    child: Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE0ECFF),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: const Color(0xFFBFDBFE),
                          width: 1.2,
                        ),
                      ),
                      child: const Row(
                        children: [
                          Icon(
                            Icons.fact_check_outlined,
                            size: 18,
                            color: Color(0xFF1D4ED8),
                          ),
                          SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              '상대가 설문지를 공개했어요',
                              style: TextStyle(
                                color: Color(0xFF1E3A8A),
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          Icon(
                            Icons.arrow_forward_ios,
                            size: 14,
                            color: Color(0xFF1E3A8A),
                          ),
                        ],
                      ),
                    ),
                  ),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.94),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: const Color(0xFFD5DDE8)),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x120F172A),
                        blurRadius: 16,
                        offset: Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              '매칭 옵션',
                              style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF0F172A),
                              ),
                            ),
                          ),
                          if (!matchingEnabled)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 5,
                              ),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFFF7ED),
                                borderRadius: BorderRadius.circular(999),
                                border: Border.all(
                                  color: const Color(0xFFFED7AA),
                                ),
                              ),
                              child: Text(
                                '채팅 $remainToMatch회 더 필요',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: Color(0xFF9A3412),
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        '옵션을 선택하면 상대와 즉시 공유됩니다.',
                        style: TextStyle(
                          fontSize: 12,
                          color: Color(0xFF64748B),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _sheetFilledButton(
                              label: '확정',
                              enabled: canSubmitDecision,
                              onTap: () {
                                Navigator.of(ctx).pop();
                                _submitDecision('accept');
                              },
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _sheetOutlinedButton(
                              label: '거절',
                              onTap: canSubmitDecision
                                  ? () {
                                      Navigator.of(ctx).pop();
                                      _submitDecision('reject');
                                    }
                                  : null,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _sheetOutlinedButton(
                              label: '보류',
                              onTap: canSubmitDecision
                                  ? () {
                                      Navigator.of(ctx).pop();
                                      _submitDecision('hold');
                                    }
                                  : null,
                            ),
                          ),
                        ],
                      ),
                      if (_myDecision.isNotEmpty ||
                          _otherDecision.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        Text(
                          "내 결정: ${_myDecision.isEmpty ? '없음' : _myDecision} / 상대 결정: ${_otherDecision.isEmpty ? '없음' : _otherDecision}",
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF6B7280),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (_myReason.isNotEmpty ||
                            _otherReason.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            "내 사유: ${_myReason.isEmpty ? '없음' : _myReason}",
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF6B7280),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            "상대 사유: ${_otherReason.isEmpty ? '없음' : _otherReason}",
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF6B7280),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<String?> _promptReason({
    required String title,
    required String hint,
    required String confirmLabel,
  }) async {
    final reasonCtrl = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: reasonCtrl,
          autofocus: true,
          maxLines: 3,
          decoration: InputDecoration(hintText: hint),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () {
              final value = reasonCtrl.text.trim();
              if (value.length < 5) {
                Get.snackbar('안내', '사유는 5자 이상 필요합니다.');
                return;
              }
              Navigator.of(ctx).pop(value);
            },
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
    reasonCtrl.dispose();
    return result;
  }

  Widget _sheetOutlinedButton({
    required String label,
    required VoidCallback? onTap,
  }) {
    final enabled = onTap != null;
    return SizedBox(
      height: 52,
      child: OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          side: BorderSide(
            color: enabled ? const Color(0xFFCBD5E1) : const Color(0xFFE2E8F0),
            width: 1.3,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          foregroundColor: enabled
              ? const Color(0xFF2563EB)
              : const Color(0xFF94A3B8),
          backgroundColor: enabled ? Colors.white : const Color(0xFFF8FAFC),
          overlayColor: const Color(0x1A2563EB),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
        child: Text(label, overflow: TextOverflow.ellipsis),
      ),
    );
  }

  Widget _sheetFilledButton({
    required String label,
    required bool enabled,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      height: 52,
      child: ElevatedButton(
        onPressed: enabled ? onTap : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF2563EB),
          foregroundColor: Colors.white,
          disabledBackgroundColor: const Color(0xFFBFDBFE),
          disabledForegroundColor: const Color(0xFFEFF6FF),
          elevation: 0,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
          overlayColor: const Color(0x1AFFFFFF),
        ),
        child: Text(label),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final isClosed = ctrl.isThreadClosed(widget.threadId);
      final closedReason = ctrl.threadClosedReason(widget.threadId);
      final isStopped = closedReason == 'left';
      final msgs = List<Map<String, dynamic>>.from(
        ctrl.threadMessages[widget.threadId] ?? const [],
      );
      return Scaffold(
        appBar: AppBar(
          title: Text(widget.otherUser),
          actions: [
            IconButton(
              tooltip: '채팅방 나가기',
              icon: const Icon(Icons.exit_to_app),
              onPressed: _confirmLeave,
            ),
          ],
        ),
        body: Column(
          children: [
            if (isClosed)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                color: const Color(0xFFF3F4F6),
                child: Text(
                  isStopped ? '상대가 대화를 중단했습니다.' : _closedLabel(closedReason),
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF4B5563),
                  ),
                ),
              ),
            Expanded(
              child: Builder(
                builder: (_) {
                  final _ = ctrl.threadMessages.length;
                  if (msgs.isEmpty) {
                    if (_isRestoringMessages) {
                      return const Center(
                        child: SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      );
                    }
                    return Center(
                      child: Text(
                        '메시지를 시작해보세요',
                        style: TextStyle(
                          color: Colors.grey.shade400,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    );
                  }
                  return Column(
                    children: [
                      if (_isLoadingOlder)
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                      Expanded(
                        child: ListView.builder(
                          controller: scrollCtrl,
                          padding: const EdgeInsets.all(16),
                          itemCount: msgs.length,
                          itemBuilder: (_, i) => _messageBubble(msgs, i),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border(top: BorderSide(color: Colors.grey.shade200)),
              ),
              child: SafeArea(
                child: Row(
                  children: [
                    IconButton(
                      onPressed: isClosed ? null : _openActionSheet,
                      tooltip: '옵션',
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                    Expanded(
                      child: TextField(
                        controller: textCtrl,
                        enabled: !isClosed,
                        decoration: InputDecoration(
                          hintText: isClosed ? '종료된 채팅입니다' : '메시지 입력...',
                          filled: true,
                          fillColor: const Color(0xFFF3F4F6),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 10,
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(24),
                            borderSide: BorderSide.none,
                          ),
                        ),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: isClosed ? null : _send,
                      tooltip: '보내기',
                      icon: const Icon(Icons.send),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      );
    });
  }

  Widget _messageBubble(List<Map<String, dynamic>> all, int index) {
    final m = all[index];
    final sender = m['sender']?.toString() ?? '';
    final isSystem =
        (m['type']?.toString() ?? '') == 'system' || sender == 'system';
    final content = m['content']?.toString() ?? '';
    final localStatus = m['local_status']?.toString() ?? '';
    final localUid = m['uid']?.toString() ?? '';
    final isSending = localStatus == 'sending';
    final isFailed = localStatus == 'failed';
    final isMe =
        !isSystem &&
        (sender == ctrl.currentUserUid ||
            ((isSending || isFailed) && localUid.startsWith('local-pending-')));

    final label = _timeLabel(m['created_at']?.toString());
    final nextLabel = (index + 1 < all.length)
        ? _timeLabel(all[index + 1]['created_at']?.toString())
        : null;
    final showLeftTime =
        !isSystem &&
        !isSending &&
        !isFailed &&
        label != null &&
        label != nextLabel;

    if (isSystem) {
      return Center(
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0xFFF3F4F6),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            content,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF6B7280),
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      );
    }

    final quickShare = _tryParseQuickShareMessage(content);

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: isMe
            ? CrossAxisAlignment.end
            : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 280),
                child: quickShare == null
                    ? Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: isMe
                              ? const Color(0xFF2563EB)
                              : const Color(0xFFF3F4F6),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          content,
                          style: TextStyle(
                            fontSize: 14,
                            color: isMe
                                ? Colors.white
                                : const Color(0xFF1F2937),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      )
                    : _quickShareCard(data: quickShare, isMe: isMe),
              ),
            ],
          ),
          if (showLeftTime)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                label,
                style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
              ),
            ),
          _buildStatusLine(
            isSending: isSending,
            isFailed: isFailed,
            localUid: localUid,
          ),
        ],
      ),
    );
  }

  Widget _buildStatusLine({
    required bool isSending,
    required bool isFailed,
    required String localUid,
  }) {
    if (!isSending && !isFailed) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 2, left: 4, right: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            isFailed ? '전송 실패' : '전송중',
            style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
          ),
          if (isFailed)
            SizedBox(
              width: 22,
              height: 22,
              child: IconButton(
                padding: EdgeInsets.zero,
                splashRadius: 14,
                iconSize: 14,
                onPressed: localUid.isEmpty ? null : () => _retry(localUid),
                icon: const Icon(Icons.refresh),
              ),
            ),
        ],
      ),
    );
  }

  _QuickShareCardData? _tryParseQuickShareMessage(String content) {
    if (!content.startsWith(_quickSharePrefix)) return null;

    final raw = content.substring(_quickSharePrefix.length);
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return null;
      final map = Map<String, dynamic>.from(decoded);

      final type = map['type']?.toString() ?? '';
      final title = map['title']?.toString() ?? '';
      final summary = (map['summary'] is List)
          ? (map['summary'] as List).map((e) => e.toString()).toList()
          : <String>[];
      final details = (map['details'] is List)
          ? (map['details'] as List).map((e) => e.toString()).toList()
          : <String>[];

      if (type.isEmpty || title.isEmpty) return null;
      return _QuickShareCardData(
        type: type,
        title: title,
        summary: summary,
        details: details,
      );
    } catch (_) {
      return null;
    }
  }

  Widget _quickShareCard({
    required _QuickShareCardData data,
    required bool isMe,
  }) {
    final isSchedule = data.type == 'schedule';
    final isSurvey = data.type == 'survey';
    return GestureDetector(
      onTap: () => _openQuickShareDetail(data),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isMe ? const Color(0xFF1D4ED8) : const Color(0xFFEEF2FF),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isMe ? const Color(0xFF3B82F6) : const Color(0xFFC7D2FE),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isSchedule
                      ? Icons.schedule
                      : (isSurvey ? Icons.fact_check : Icons.calendar_month),
                  size: 16,
                  color: isMe ? Colors.white : const Color(0xFF3730A3),
                ),
                const SizedBox(width: 6),
                Text(
                  data.title,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: isMe ? Colors.white : const Color(0xFF3730A3),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...data.summary
                .take(3)
                .map(
                  (line) => Padding(
                    padding: const EdgeInsets.only(bottom: 3),
                    child: Text(
                      line,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: isMe ? Colors.white : const Color(0xFF1E1B4B),
                      ),
                    ),
                  ),
                ),
            const SizedBox(height: 2),
            Text(
              '눌러서 상세보기',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: isMe ? const Color(0xFFDBEAFE) : const Color(0xFF6366F1),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openQuickShareDetail(_QuickShareCardData data) async {
    if (!mounted) return;

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                data.title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              if (data.details.isEmpty)
                const Text('표시할 상세 정보가 없어요.')
              else
                ...data.details.map(
                  (line) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      line,
                      style: const TextStyle(
                        fontSize: 14,
                        color: Color(0xFF1F2937),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  String? _timeLabel(String? createdAtRaw) {
    if (createdAtRaw == null || createdAtRaw.isEmpty) return null;
    final parsed = DateTime.tryParse(createdAtRaw);
    if (parsed == null) return null;

    final local = parsed.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);

    if (diff.inHours >= 24) {
      return '${local.year.toString().padLeft(4, '0')}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')}';
    }
    return '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }

  String _closedLabel(String reason) {
    if (reason == 'already_matched') return '상대가 이미 매칭됐습니다.';
    if (reason == 'no_response') return '2일 무응답으로 종료되었습니다.';
    if (reason == 'cancelled') return '취소로 종료되었습니다.';
    if (reason == 'rematch') return '리매치로 종료되었습니다.';
    if (reason == 'rejected') return '매칭 거절로 종료되었습니다.';
    if (reason == 'left') return '상대가 대화를 중단했습니다.';
    return '채팅이 종료되었습니다.';
  }
}

enum _QuickShareType { schedule, calendar, survey }

class _QuickShareCardData {
  final String type;
  final String title;
  final List<String> summary;
  final List<String> details;

  const _QuickShareCardData({
    required this.type,
    required this.title,
    required this.summary,
    required this.details,
  });
}

// TEMP_MARKER
