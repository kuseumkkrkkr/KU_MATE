import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/match_controller.dart';
import '../utils/match_ui_helper.dart';
import 'chat_threads_screen.dart';
import 'match_session_chats_screen.dart';
import 'match_detail_screen.dart';

class MatchScreen extends StatefulWidget {
  const MatchScreen({super.key});

  @override
  State<MatchScreen> createState() => _MatchScreenState();
}

class _MatchScreenState extends State<MatchScreen> with WidgetsBindingObserver {
  final _matchCtrl = Get.find<MatchController>();
  int _refreshToken = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refreshOnEntryWithRetry();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshOnEntryWithRetry();
    }
  }

  Future<void> _refreshOnEntryWithRetry() async {
    final token = ++_refreshToken;
    await _matchCtrl.loadMatchStartOnView();
    if (!mounted || token != _refreshToken) return;

    if (_matchCtrl.hasStartedSession || _matchCtrl.poolCandidates.isNotEmpty) {
      return;
    }

    for (var i = 0; i < 3; i++) {
      await Future<void>.delayed(const Duration(seconds: 5));
      if (!mounted || token != _refreshToken) return;

      await _matchCtrl.loadMatchStartOnView();
      if (!mounted || token != _refreshToken) return;
      if (_matchCtrl.hasStartedSession || _matchCtrl.poolCandidates.isNotEmpty) {
        return;
      }
    }

    if (mounted && token == _refreshToken) {
      Get.snackbar('안내', '매칭 후보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }
  }

  Future<void> _openCurrentMatchChats() async {
    await Future.wait([
      _matchCtrl.fetchActiveSessions(),
      _matchCtrl.fetchThreads(),
    ]);
    final sessions = List<Map<String, dynamic>>.from(_matchCtrl.activeSessions);
    if (sessions.isEmpty && _matchCtrl.chatThreads.isEmpty) {
      Get.snackbar('안내', '현재 진행 중인 매칭 채팅이 없습니다.');
      return;
    }
    sessions.sort((a, b) {
      final ad =
          DateTime.tryParse(a['created_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0);
      final bd =
          DateTime.tryParse(b['created_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0);
      return bd.compareTo(ad);
    });
    Map<String, dynamic>? target;
    for (final s in sessions) {
      if ((s['status']?.toString() ?? '') == 'active') {
        target = s;
        break;
      }
    }
    target ??= sessions.isNotEmpty ? sessions.first : null;
    final sessionId =
        target?['uid']?.toString() ?? target?['session_id']?.toString() ?? '';
    if (sessionId.isEmpty) {
      Get.to(() => const ChatThreadsScreen());
      return;
    }
    Get.to(() => MatchSessionChatsScreen(sessionId: sessionId));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('매칭 시작'),
        actions: [
          IconButton(
            tooltip: '현재 매칭 채팅',
            icon: const Icon(Icons.chat_bubble_outline),
            onPressed: _openCurrentMatchChats,
          ),
        ],
      ),
      body: Obx(
        () => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _statusPanel(),
            const SizedBox(height: 14),
            if (_matchCtrl.isInCooldown) _cooldownPanel(),
            if (_matchCtrl.isInCooldown) const SizedBox(height: 14),
            if (_matchCtrl.isLoading.value &&
                _matchCtrl.poolCandidates.isEmpty &&
                !_matchCtrl.hasStartedSession)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_matchCtrl.poolCandidates.isEmpty)
              _emptyPoolState()
            else
              ..._matchCtrl.poolCandidates.map(
                (c) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _poolCard(c),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _statusPanel() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D000000),
            blurRadius: 12,
            offset: Offset(0, 3),
          ),
        ],
      ),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          if (_matchCtrl.hasStartedSession)
            _badge(
              '매칭 진행 중',
              const Color(0xFFDBEAFE),
              const Color(0xFF1D4ED8),
            )
          else
            _badge(
              '매칭 후보 확인',
              const Color(0xFFF3F4F6),
              const Color(0xFF4B5563),
            ),
          if (_matchCtrl.canRematch)
            _badge('재매치 가능', const Color(0xFFFFF7ED), const Color(0xFF9A3412)),
          if (_matchCtrl.isInCooldown)
            _badge(
              '쿨다운 진행 중',
              const Color(0xFFEEF2FF),
              const Color(0xFF3730A3),
            ),
        ],
      ),
    );
  }

  Widget _badge(String text, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: fg),
      ),
    );
  }

  Widget _cooldownPanel() {
    final until = _matchCtrl.cooldownUntil.value;
    final remain = until?.difference(DateTime.now());
    final remainHours = remain == null ? 0 : remain.inHours;
    final retryAt = until == null ? '시간 정보 없음' : _formatLocalTime(until);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF2FF),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFC7D2FE)),
      ),
      child: Row(
        children: [
          const Icon(Icons.timer_outlined, color: Color(0xFF4338CA)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              remainHours > 0
                  ? '다시 매칭 가능 시간: $retryAt (약 $remainHours시간 후)'
                  : '다시 매칭 가능 시간: $retryAt',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: Color(0xFF312E81),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyPoolState() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 54),
      alignment: Alignment.center,
      child: Column(
        children: [
          Icon(Icons.group_off, size: 46, color: Colors.grey.shade300),
          const SizedBox(height: 10),
          const Text(
            '현재 매칭 후보가 비어 있습니다.',
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _poolCard(Map<String, dynamic> item) {
    final candidateType = item['candidate_type']?.toString() ?? 'individual';
    final isRoom = candidateType == 'room';
    final profile = (item['profile'] is Map<String, dynamic>)
        ? item['profile'] as Map<String, dynamic>
        : <String, dynamic>{};
    final memberNames = List<String>.from(item['member_names'] ?? const []);

    final displayName = isRoom
        ? (item['display_name']?.toString() ?? '${memberNames.join(', ')}의 방')
        : (profile['name']?.toString() ?? '상대 사용자');
    final summary = MatchUiHelper.summaryFrom(item);
    final status = _statusForCandidate(item);

    return GestureDetector(
      onTap: () async {
        final opened = await _openThreadForCandidate(item);
        if (opened || !mounted) return;
        Get.to(() => MatchDetailScreen(matchData: item));
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isRoom ? const Color(0xFF1E3A8A) : const Color(0xFFE5E7EB),
            width: isRoom ? 2 : 1,
          ),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0D000000),
              blurRadius: 10,
              offset: Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _avatar(displayName),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              displayName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          _statusChip(status),
                          const SizedBox(width: 8),
                          _candidateTypeChip(isRoom),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        summary.grade.label,
                        style: TextStyle(
                          color: summary.grade.foreground,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        summary.subtitle,
                        style: const TextStyle(
                          color: Color(0xFF6B7280),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _reasonBlock('잘 맞는 점', summary.strengths, const Color(0xFFEFF6FF)),
            const SizedBox(height: 8),
            _reasonBlock('미리 조율할 점', summary.cautions, const Color(0xFFFFF7ED)),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () =>
                    Get.to(() => MatchDetailScreen(matchData: item)),
                icon: const Icon(Icons.person_search_outlined, size: 18),
                label: const Text('프로필 보기'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(48),
                  side: const BorderSide(color: Color(0xFFBFDBFE)),
                  foregroundColor: const Color(0xFF1D4ED8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _candidateTypeChip(bool isRoom) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isRoom ? const Color(0xFFDBEAFE) : const Color(0xFFF3F4F6),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        MatchUiHelper.candidateLabel(isRoom),
        style: TextStyle(
          fontSize: 11,
          color: isRoom ? const Color(0xFF1D4ED8) : const Color(0xFF4B5563),
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  _CandidateStatus _statusForCandidate(Map<String, dynamic> item) {
    final targetUids = _candidateUidsFromItem(item);
    if (targetUids.isEmpty) {
      return const _CandidateStatus(
        label: '대기',
        fg: Color(0xFF4B5563),
        bg: Color(0xFFF3F4F6),
      );
    }

    final matchedThreads = _matchCtrl.chatThreads.where((t) {
      final otherUid = t['other_uid']?.toString() ?? '';
      return targetUids.contains(otherUid);
    }).toList();
    if (matchedThreads.isEmpty) {
      return const _CandidateStatus(
        label: '대기',
        fg: Color(0xFF4B5563),
        bg: Color(0xFFF3F4F6),
      );
    }

    for (final t in matchedThreads) {
      final reason = t['closed_reason']?.toString() ?? '';
      if (reason == 'already_matched') {
        return _CandidateStatus(
          label: '매칭 완료',
          fg: const Color(0xFF065F46),
          bg: const Color(0xFFD1FAE5),
          thread: t,
        );
      }
    }

    for (final t in matchedThreads) {
      final status = t['status']?.toString() ?? 'open';
      if (status == 'open') {
        return _CandidateStatus(
          label: '대화 중',
          fg: const Color(0xFF166534),
          bg: const Color(0xFFDCFCE7),
          thread: t,
        );
      }
    }

    for (final t in matchedThreads) {
      final reason = t['closed_reason']?.toString() ?? '';
      if (reason == 'rejected') {
        return _CandidateStatus(
          label: '거절',
          fg: const Color(0xFFB91C1C),
          bg: const Color(0xFFFEE2E2),
          thread: t,
        );
      }
    }

    final matchedSessionIds = matchedThreads
        .map((t) => t['session_id']?.toString() ?? '')
        .where((id) => id.isNotEmpty)
        .toSet();
    for (final s in _matchCtrl.activeSessions) {
      final sid = s['uid']?.toString() ?? s['session_id']?.toString() ?? '';
      if (sid.isEmpty || !matchedSessionIds.contains(sid)) {
        continue;
      }
      final decisionA = s['user_decision']?.toString() ?? '';
      final decisionB = s['candidate_decision']?.toString() ?? '';
      if (decisionA == 'hold' || decisionB == 'hold') {
        return const _CandidateStatus(
          label: '보류',
          fg: Color(0xFF92400E),
          bg: Color(0xFFFEF3C7),
        );
      }
    }

    return const _CandidateStatus(
      label: '대기',
      fg: Color(0xFF4B5563),
      bg: Color(0xFFF3F4F6),
    );
  }

  Future<bool> _openThreadForCandidate(Map<String, dynamic> item) async {
    final existing = _threadForCandidate(item);
    final existingId = existing?['thread_id']?.toString() ?? '';
    if (existingId.isNotEmpty) {
      final other = existing?['other_user']?.toString() ?? '상대 사용자';
      await Get.to(() => ChatRoomScreen(threadId: existingId, otherUser: other));
      if (mounted) {
        await _matchCtrl.loadMatchStartOnView();
      }
      return true;
    }

    final targetCandidateUids = _candidateUidsFromItem(item).toList();
    if (targetCandidateUids.isNotEmpty) {
      final sessionId = await _matchCtrl.enterSession(targetCandidateUids);
      if (sessionId != null) {
        await _matchCtrl.fetchThreads();
        final created = _threadForCandidate(item);
        final createdId = created?['thread_id']?.toString() ?? '';
        if (createdId.isNotEmpty) {
          final other = created?['other_user']?.toString() ?? '상대 사용자';
          await Get.to(
            () => ChatRoomScreen(threadId: createdId, otherUser: other),
          );
          if (mounted) {
            await _matchCtrl.loadMatchStartOnView();
          }
          return true;
        }
      }
    }
    return false;
  }

  Map<String, dynamic>? _threadForCandidate(Map<String, dynamic> item) {
    final uids = _candidateUidsFromItem(item);
    if (uids.isEmpty) return null;
    // Only reuse open threads. Closed(rejected/expired/...) threads should not
    // hijack card tap and block re-entry to detail flow.
    for (final t in _matchCtrl.chatThreads) {
      final status = t['status']?.toString() ?? 'open';
      if (status != 'open') continue;
      final otherUid = t['other_uid']?.toString() ?? '';
      if (uids.contains(otherUid)) {
        return t;
      }
    }
    return null;
  }

  Set<String> _candidateUidsFromItem(Map<String, dynamic> item) {
    final candidateType = item['candidate_type']?.toString() ?? 'individual';
    final profile = (item['profile'] is Map<String, dynamic>)
        ? item['profile'] as Map<String, dynamic>
        : const <String, dynamic>{};
    final userUid = item['user_uid']?.toString() ?? profile['user_uid']?.toString() ?? '';
    final candidateUids = List<String>.from(item['candidate_uids'] ?? const []);
    return <String>{
      if (candidateType == 'individual' && userUid.isNotEmpty) userUid,
      ...candidateUids.where((e) => e.trim().isNotEmpty).map((e) => e.trim()),
    };
  }

  Widget _statusChip(_CandidateStatus status) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: status.bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          fontSize: 11,
          color: status.fg,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  Widget _reasonBlock(String title, List<String> lines, Color background) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Color(0xFF374151),
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 4),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                '- $line',
                style: const TextStyle(
                  color: Color(0xFF4B5563),
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _avatar(String name) {
    final letter = name.isNotEmpty ? name.substring(0, 1) : '?';
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        color: const Color(0xFFDBEAFE),
        borderRadius: BorderRadius.circular(12),
      ),
      alignment: Alignment.center,
      child: Text(
        letter,
        style: const TextStyle(
          fontWeight: FontWeight.w800,
          color: Color(0xFF1E3A8A),
        ),
      ),
    );
  }

  String _formatLocalTime(DateTime value) {
    final local = value.toLocal();
    final month = local.month.toString().padLeft(2, '0');
    final day = local.day.toString().padLeft(2, '0');
    final hour = local.hour.toString().padLeft(2, '0');
    final minute = local.minute.toString().padLeft(2, '0');
    return '$month/$day $hour:$minute';
  }
}

class _CandidateStatus {
  final String label;
  final Color fg;
  final Color bg;
  final Map<String, dynamic>? thread;

  const _CandidateStatus({
    required this.label,
    required this.fg,
    required this.bg,
    this.thread,
  });
}


