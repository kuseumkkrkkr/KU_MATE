import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/match_controller.dart';
import 'chat_threads_screen.dart';

class MatchSessionChatsScreen extends StatefulWidget {
  final String sessionId;

  const MatchSessionChatsScreen({super.key, required this.sessionId});

  @override
  State<MatchSessionChatsScreen> createState() =>
      _MatchSessionChatsScreenState();
}

class _MatchSessionChatsScreenState extends State<MatchSessionChatsScreen> {
  late final MatchController ctrl;

  @override
  void initState() {
    super.initState();
    ctrl = Get.isRegistered<MatchController>()
        ? Get.find<MatchController>()
        : Get.put(MatchController());
    ctrl.fetchThreads();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('이 매칭의 채팅')),
      body: Obx(() {
        final threads = ctrl.chatThreads.where((t) {
          final sid = t['session_id']?.toString() ?? '';
          return sid == widget.sessionId;
        }).toList();
        if (threads.isEmpty) {
          return const Center(
            child: Text(
              '이 매칭에 연결된 채팅이 없습니다.',
              style: TextStyle(
                color: Color(0xFF6B7280),
                fontWeight: FontWeight.w600,
              ),
            ),
          );
        }
        return ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: threads.length,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (_, i) {
            final t = threads[i];
            final other = t['other_user']?.toString() ?? '상대방 없음';
            final threadId = t['thread_id']?.toString() ?? '';
            final status = t['status']?.toString() ?? 'open';
            final isClosed = status != 'open';

            return GestureDetector(
              onTap: threadId.isEmpty
                  ? null
                  : () => Get.to(
                      () =>
                          ChatRoomScreen(threadId: threadId, otherUser: other),
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
                      child: Text(
                        other,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: isClosed
                              ? Colors.grey.shade400
                              : const Color(0xFF1F2937),
                        ),
                      ),
                    ),
                    const Icon(
                      Icons.arrow_forward_ios,
                      size: 16,
                      color: Color(0xFF9CA3AF),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      }),
    );
  }
}
