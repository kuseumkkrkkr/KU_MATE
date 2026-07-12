import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../services/api_service.dart';
import 'match_screen.dart';
import 'match_history_detail_screen.dart';

class MatchHistoryScreen extends StatefulWidget {
  final int refreshToken;
  const MatchHistoryScreen({super.key, this.refreshToken = 0});

  @override
  State<MatchHistoryScreen> createState() => _MatchHistoryScreenState();
}

class _MatchHistoryScreenState extends State<MatchHistoryScreen> {
  final _api = ApiService();
  final _items = <Map<String, dynamic>>[];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchHistory();
  }

  @override
  void didUpdateWidget(covariant MatchHistoryScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshToken != widget.refreshToken) {
      _fetchHistory();
    }
  }

  Future<void> _fetchHistory() async {
    setState(() => _isLoading = true);
    try {
      final rows = await _api.getSessionHistory();
      final activeRows = await _api.getActiveSessions();
      final items = List<Map<String, dynamic>>.from(rows);
      final existingIds = items
          .map((e) => e['session_id']?.toString() ?? e['uid']?.toString() ?? '')
          .where((e) => e.isNotEmpty)
          .toSet();
      for (final raw in List<Map<String, dynamic>>.from(activeRows)) {
        final sessionId =
            raw['uid']?.toString() ?? raw['session_id']?.toString() ?? '';
        if (sessionId.isEmpty || existingIds.contains(sessionId)) continue;
        items.insert(0, {
          'session_id': sessionId,
          'candidate_type': raw['candidate_type'] ?? 'individual',
          'match_kind': 'dormitory',
          'created_at': raw['created_at'],
          'status': raw['status'] ?? 'active',
          'ui_status': (raw['status']?.toString() ?? '') == 'confirmed'
              ? 'match_success'
              : 'in_progress',
          'is_deletable': false,
          'threads': const [],
        });
      }
      _items
        ..clear()
        ..addAll(items);
    } catch (e) {
      Get.snackbar('오류', '매칭 이력을 불러오지 못했습니다: $e');
      _items.clear();
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<bool> _deleteHistoryItem(Map<String, dynamic> item) async {
    final sessionId = item['session_id']?.toString() ?? '';
    if (sessionId.isEmpty) return false;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('이력 삭제'),
        content: const Text('기간종료된 매칭 이력을 삭제할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (confirmed != true) return false;
    try {
      await _api.deleteSessionHistory(sessionId);
      _items.removeWhere((e) => e['session_id']?.toString() == sessionId);
      if (mounted) {
        setState(() {});
      }
      Get.snackbar('완료', '매칭 이력을 삭제했습니다.');
      return true;
    } catch (e) {
      Get.snackbar('오류', '매칭 이력 삭제에 실패했습니다: $e');
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('매칭')),
      body: RefreshIndicator(
        onRefresh: _fetchHistory,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            //_separatedNotice(),
            const SizedBox(height: 14),
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_items.isEmpty)
              _emptyState()
            else
              ..._items.map((item) {
                final isDeletable = item['is_deletable'] == true;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: isDeletable
                      ? Dismissible(
                          key: ValueKey(item['session_id']?.toString() ?? ''),
                          direction: DismissDirection.endToStart,
                          background: Container(
                            decoration: BoxDecoration(
                              color: const Color(0xFFDC2626),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.symmetric(horizontal: 20),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.delete_outline, color: Colors.white),
                                SizedBox(width: 6),
                                Text(
                                  '삭제',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          confirmDismiss: (_) => _deleteHistoryItem(item),
                          child: _historyCard(item),
                        )
                      : _historyCard(item),
                );
              }),
          ],
        ),
      ),
    );
  }

  Widget _emptyState() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 56),
      alignment: Alignment.center,
      child: Column(
        children: [
          Icon(Icons.inbox_outlined, size: 44, color: Colors.grey.shade300),
          const SizedBox(height: 10),
          const Text(
            '아직 시작된 매칭이 없습니다.',
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _historyCard(Map<String, dynamic> item) {
    final kind = _matchKindLabel(item['match_kind']?.toString());
    final createdAt = _formatDate(item['created_at']?.toString());
    final status = _statusLabel(item['ui_status']?.toString());
    final statusColor = _statusColor(status);
    final statusBg = _statusBackground(status);

    return InkWell(
      onTap: () {
        final uiStatus = item['ui_status']?.toString() ?? '';
        if (uiStatus == 'in_progress' || uiStatus == 'on_hold') {
          Get.to(() => const MatchScreen());
          return;
        }
        Get.to(() => MatchHistoryDetailScreen(session: item));
      },
      borderRadius: BorderRadius.circular(14),
      child: Container(
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
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: const Color(0xFFDBEAFE),
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Icon(
                _kindIcon(item['match_kind']?.toString()),
                color: Color(0xFF1D4ED8),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    kind,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF111827),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    createdAt,
                    style: const TextStyle(
                      color: Color(0xFF6B7280),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: statusBg,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                status,
                style: TextStyle(
                  color: statusColor,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
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

  IconData _kindIcon(String? raw) {
    switch (raw) {
      case 'one_room':
        return Icons.home_work_outlined;
      case 'share_house':
        return Icons.groups_2_outlined;
      case 'dormitory':
      default:
        return Icons.apartment_outlined;
    }
  }

  String _statusLabel(String? raw) {
    if (raw == 'match_success') return '매칭 성공';
    if (raw == 'on_hold') return '보류중';
    if (raw == 'rejected') return '거절됨';
    return raw == 'in_progress' ? '진행중' : '기간종료';
  }

  Color _statusColor(String status) {
    if (status == '매칭 성공') return const Color(0xFF065F46);
    if (status == '보류중') return const Color(0xFF92400E);
    if (status == '거절됨') return const Color(0xFFB91C1C);
    if (status == '진행중') return const Color(0xFF16A34A);
    return const Color(0xFF6B7280);
  }

  Color _statusBackground(String status) {
    if (status == '매칭 성공') return const Color(0xFFD1FAE5);
    if (status == '보류중') return const Color(0xFFFEF3C7);
    if (status == '거절됨') return const Color(0xFFFEE2E2);
    if (status == '진행중') return const Color(0xFFDCFCE7);
    return const Color(0xFFF3F4F6);
  }

  String _formatDate(String? iso) {
    final dt = DateTime.tryParse(iso ?? '');
    if (dt == null) return '-';
    return '${dt.year}.${_two(dt.month)}.${_two(dt.day)} ${_two(dt.hour)}:${_two(dt.minute)}';
  }

  String _two(int n) => n.toString().padLeft(2, '0');
}
