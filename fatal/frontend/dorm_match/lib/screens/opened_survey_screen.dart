import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'public_profile_screen.dart';

class OpenedSurveyScreen extends StatelessWidget {
  final String title;
  final String otherUid;
  final Map<String, dynamic> profile;
  final List<Map<String, dynamic>> reviews;

  const OpenedSurveyScreen({
    super.key,
    required this.title,
    required this.otherUid,
    required this.profile,
    required this.reviews,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('$title 설문/후기')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFBFDBFE)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '상대 설문지가 공개되었습니다.',
                  style: TextStyle(
                    color: Color(0xFF1E3A8A),
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => Get.to(
                      () => PublicProfileScreen(profile: profile, title: title),
                    ),
                    child: const Text('설문지 전체 보기'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            '받은 후기',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 8),
          if (reviews.isEmpty)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: const Text(
                '아직 등록된 후기가 없습니다.',
                style: TextStyle(color: Color(0xFF6B7280)),
              ),
            )
          else
            ...reviews.map((review) => _reviewCard(review)),
        ],
      ),
    );
  }

  Widget _reviewCard(Map<String, dynamic> review) {
    final rating = (review['rating'] as num?)?.toDouble() ?? 0;
    final body = (review['body']?.toString() ?? '').trim();
    final createdAt = review['created_at']?.toString() ?? '';
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
          Row(
            children: [
              Text(
                '평점 ${rating.toStringAsFixed(1)}',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF111827),
                ),
              ),
              const Spacer(),
              Text(
                createdAt,
                style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
              ),
            ],
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              body,
              style: const TextStyle(
                color: Color(0xFF1F2937),
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
          const SizedBox(height: 6),
          Text(
            '상대 UID: $otherUid',
            style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
          ),
        ],
      ),
    );
  }
}
