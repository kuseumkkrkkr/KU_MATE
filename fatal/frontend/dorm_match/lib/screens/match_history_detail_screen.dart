import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../services/api_service.dart';
import 'chat_threads_screen.dart';
import 'match_session_chats_screen.dart';
import 'public_profile_screen.dart';

class MatchHistoryDetailScreen extends StatefulWidget {
  final Map<String, dynamic> session;

  const MatchHistoryDetailScreen({super.key, required this.session});

  @override
  State<MatchHistoryDetailScreen> createState() =>
      _MatchHistoryDetailScreenState();
}

class _MatchHistoryDetailScreenState extends State<MatchHistoryDetailScreen> {
  final _api = ApiService();
  bool _isFetchingProfile = false;

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final threads = List<Map<String, dynamic>>.from(
      session['threads'] ?? const [],
    );
    final rawStatus = (session['ui_status']?.toString() ?? '').trim();
    final inProgress = rawStatus == 'in_progress' || rawStatus == 'on_hold';
    final statusLabel = _statusLabel(rawStatus);

    return Scaffold(
      appBar: AppBar(title: const Text('매칭 상세')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _summaryCard(session, statusLabel),
          const SizedBox(height: 14),
          Row(
            children: [
              const Expanded(
                child: Text(
                  '매칭 상대',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF111827),
                  ),
                ),
              ),
              if (threads.isNotEmpty)
                OutlinedButton.icon(
                  onPressed: () => Get.to(
                    () => MatchSessionChatsScreen(
                      sessionId: session['session_id']?.toString() ?? '',
                    ),
                  ),
                  icon: const Icon(Icons.forum_outlined, size: 16),
                  label: const Text('채팅 보기'),
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (threads.isEmpty)
            _emptyMemberCard()
          else
            ...threads.map((t) => _memberCard(t, inProgress)),
        ],
      ),
    );
  }

  Widget _summaryCard(Map<String, dynamic> session, String statusLabel) {
    final kind = _matchKindLabel(session['match_kind']?.toString());
    final createdAt = _formatDate(session['created_at']?.toString());
    final active = statusLabel == '진행중' || statusLabel == '보류중';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D000000),
            blurRadius: 12,
            offset: Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _kv('매칭 종류', kind),
          _kv('일자', createdAt),
          Row(
            children: [
              const Expanded(
                child: Text(
                  '상태',
                  style: TextStyle(
                    color: Color(0xFF6B7280),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: active
                      ? const Color(0xFFDCFCE7)
                      : const Color(0xFFF3F4F6),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: active
                        ? const Color(0xFF16A34A)
                        : const Color(0xFF6B7280),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _emptyMemberCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: const Text(
        '연결된 상대 정보가 없습니다.',
        style: TextStyle(color: Color(0xFF6B7280)),
      ),
    );
  }

  Widget _memberCard(Map<String, dynamic> thread, bool inProgress) {
    final otherName = thread['other_user']?.toString() ?? '상대';
    final otherUid = thread['other_uid']?.toString() ?? '';
    final threadId = thread['thread_id']?.toString() ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            otherName,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 10),
          if (inProgress)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: threadId.isEmpty
                    ? null
                    : () => Get.to(
                        () => ChatRoomScreen(
                          threadId: threadId,
                          otherUser: otherName,
                        ),
                      ),
                icon: const Icon(Icons.chat_bubble_outline, size: 18),
                label: const Text('채팅 시작'),
              ),
            )
          else
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: (_isFetchingProfile || otherUid.isEmpty)
                    ? null
                    : () => _openPublicProfile(otherUid, otherName),
                icon: const Icon(Icons.description_outlined, size: 18),
                label: Text(_isFetchingProfile ? '조회 중...' : '상대 설문 조회'),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _openPublicProfile(String userUid, String name) async {
    setState(() => _isFetchingProfile = true);
    try {
      final res = await _api.getPublicProfile(userUid);
      final profile = (res['profile'] is Map<String, dynamic>)
          ? res['profile'] as Map<String, dynamic>
          : <String, dynamic>{};
      if (profile.isEmpty) {
        Get.snackbar('오류', '상대 설문 정보를 불러오지 못했습니다.');
        return;
      }
      Get.to(() => PublicProfileScreen(profile: profile, title: name));
    } catch (e) {
      Get.snackbar('오류', '상대 설문 조회에 실패했습니다: $e');
    } finally {
      if (mounted) {
        setState(() => _isFetchingProfile = false);
      }
    }
  }

  Widget _kv(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                color: Color(0xFF6B7280),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              color: Color(0xFF111827),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  String _matchKindLabel(String? raw) {
    switch (raw) {
      case 'one_room':
        return '자취방';
      case 'share_house':
        return '쉐어하우스';
      case 'dormitory':
      default:
        return '기숙사';
    }
  }

  String _statusLabel(String raw) {
    if (raw == 'match_success') return '매칭 성공';
    if (raw == 'on_hold') return '보류중';
    if (raw == 'rejected') return '거절됨';
    if (raw == 'in_progress') return '진행중';
    return '기간종료';
  }

  String _formatDate(String? iso) {
    final dt = DateTime.tryParse(iso ?? '');
    if (dt == null) return '-';
    return '${dt.year}.${_two(dt.month)}.${_two(dt.day)} ${_two(dt.hour)}:${_two(dt.minute)}';
  }

  String _two(int n) => n.toString().padLeft(2, '0');
}
