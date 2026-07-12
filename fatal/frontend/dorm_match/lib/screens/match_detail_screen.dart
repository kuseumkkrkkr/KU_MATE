import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/match_controller.dart';
import '../utils/match_ui_helper.dart';
import 'chat_threads_screen.dart';

class MatchDetailScreen extends StatelessWidget {
  final Map<String, dynamic> matchData;

  const MatchDetailScreen({super.key, required this.matchData});

  @override
  Widget build(BuildContext context) {
    final ctrl = Get.find<MatchController>();
    final score = MatchUiHelper.scoreFrom(matchData);
    final isRoom =
        (matchData['candidate_type']?.toString() ?? 'individual') == 'room';
    final summary = MatchUiHelper.summaryFrom(matchData);

    final profile = (matchData['profile'] is Map<String, dynamic>)
        ? matchData['profile'] as Map<String, dynamic>
        : <String, dynamic>{};
    final memberNames = List<String>.from(
      matchData['member_names'] ?? const [],
    );
    final memberScores = List<double>.from(
      (matchData['member_scores'] as List<dynamic>? ?? const []).map(
        (e) => (e as num).toDouble(),
      ),
    );

    final displayName = isRoom
        ? (matchData['display_name']?.toString() ??
              '${memberNames.join(', ')}의 방')
        : (profile['name']?.toString() ?? '상대 사용자');

    return Scaffold(
      appBar: AppBar(title: const Text('매칭 상세')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isRoom
                    ? const Color(0xFF1E3A8A)
                    : const Color(0xFFE5E7EB),
                width: isRoom ? 2 : 1,
              ),
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
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        displayName,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    _gradeChip(summary.grade),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  summary.subtitle,
                  style: const TextStyle(
                    color: Color(0xFF374151),
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '종합 점수 ${score.toStringAsFixed(1)}점',
                  style: const TextStyle(
                    color: Color(0xFF6B7280),
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (isRoom && memberNames.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '구성원: ${memberNames.join(', ')}',
                      style: const TextStyle(
                        color: Color(0xFF6B7280),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                if (isRoom && memberScores.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      '개별 점수: ${memberScores.map((e) => e.toStringAsFixed(1)).join(' / ')}',
                      style: const TextStyle(
                        color: Color(0xFF6B7280),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _reasonCard(
            title: '잘 맞는 점',
            icon: Icons.thumb_up_alt_outlined,
            bg: const Color(0xFFEFF6FF),
            lines: summary.strengths,
          ),
          const SizedBox(height: 10),
          _reasonCard(
            title: '미리 조율할 점',
            icon: Icons.rule_outlined,
            bg: const Color(0xFFFFF7ED),
            lines: summary.cautions,
          ),
          const SizedBox(height: 14),
          if (ctrl.isInCooldown)
            Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFC7D2FE)),
              ),
              child: const Text(
                '쿨다운 중에는 새 채팅을 시작할 수 없어요. 리스트에서 후보를 둘러보며 다음 매칭을 준비해보세요.',
                style: TextStyle(
                  color: Color(0xFF312E81),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ElevatedButton.icon(
            onPressed: ctrl.isInCooldown
                ? null
                : () async {
                    final candidateUids = _extractCandidateUids(matchData);
                    if (candidateUids.isEmpty) {
                      Get.snackbar('오류', '채팅 대상을 찾지 못했습니다.');
                      return;
                    }
                    final sessionId = await ctrl.enterSession(candidateUids);
                    if (sessionId != null) {
                      Get.to(() => const ChatThreadsScreen());
                    }
                  },
            icon: const Icon(Icons.chat_bubble_outline),
            label: const Text('채팅 시작'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2563EB),
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(48),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _gradeChip(MatchUiGrade grade) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: grade.background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        grade.label,
        style: TextStyle(color: grade.foreground, fontWeight: FontWeight.w800),
      ),
    );
  }

  Widget _reasonCard({
    required String title,
    required IconData icon,
    required Color bg,
    required List<String> lines,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: const Color(0xFF374151)),
              const SizedBox(width: 6),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF374151),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text(
                '- $line',
                style: const TextStyle(
                  color: Color(0xFF4B5563),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<String> _extractCandidateUids(Map<String, dynamic> data) {
    final candidateType = data['candidate_type']?.toString() ?? 'individual';
    if (candidateType == 'room') {
      final uids = List<String>.from(data['candidate_uids'] ?? const []);
      if (uids.isNotEmpty) {
        return uids;
      }
      final members = List<Map<String, dynamic>>.from(
        data['members'] ?? const [],
      );
      return members
          .map((m) => (m['user_uid']?.toString() ?? '').trim())
          .where((e) => e.isNotEmpty)
          .toList();
    }

    final profile = (data['profile'] is Map<String, dynamic>)
        ? data['profile'] as Map<String, dynamic>
        : <String, dynamic>{};
    final uid =
        (profile['user_uid']?.toString() ?? data['user_uid']?.toString() ?? '')
            .trim();
    if (uid.isEmpty) return [];
    return [uid];
  }

}
