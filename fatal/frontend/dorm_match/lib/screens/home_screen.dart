import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../controllers/auth_controller.dart';
import '../controllers/match_controller.dart';
import '../controllers/profile_controller.dart';
import '../services/api_service.dart';
import '../utils/persona_scoring.dart';
import 'survey_screen.dart';
import 'matching_split_screen.dart';
import 'life_room_screen.dart';
import 'login_screen.dart';
import 'persona_detail_screen.dart';
import 'notices_screen.dart';
import 'chat_threads_screen.dart';
import 'match_screen.dart';
import 'match_history_detail_screen.dart';
import 'interest_rooms_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _auth = Get.find<AuthController>();
  final _profileCtrl = Get.put(ProfileController());
  final _api = ApiService();
  List<Map<String, dynamic>> _noticePreview = const [];
  bool _noticeLoading = true;
  bool _needsHallConfirmation = false;
  bool _hasInterestRooms = true;
  bool _showTutorial = false;
  static const _tutorialKey = 'tutorial_shown';

  @override
  void initState() {
    super.initState();
    _profileCtrl.fetchProfile();
    _loadNoticePreview();
    _checkHallConfirmation();
    _checkTutorial();
  }

  Future<void> _checkTutorial() async {
    final prefs = await SharedPreferences.getInstance();
    final shown = prefs.getBool(_tutorialKey) ?? false;
    if (!shown && mounted) {
      setState(() => _showTutorial = true);
    }
  }

  Future<void> _dismissTutorial() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_tutorialKey, true);
    setState(() => _showTutorial = false);
  }

  Future<void> _checkHallConfirmation() async {
    try {
      final res = await _api.getMatchingOptions();
      if (mounted) {
        setState(() {
          _needsHallConfirmation = res['needs_hall_confirmation'] == true;
          _hasInterestRooms = res['has_interest_rooms'] == true;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadNoticePreview() async {
    setState(() => _noticeLoading = true);
    try {
      final notices = await _api.getNotices(limit: 3);
      if (!mounted) return;
      setState(() => _noticePreview = notices);
    } catch (_) {
      if (!mounted) return;
      setState(() => _noticePreview = const []);
    } finally {
      if (mounted) setState(() => _noticeLoading = false);
    }
  }

  String _noticeDate(Map<String, dynamic> notice) {
    final raw = (notice['updated_at'] ?? notice['created_at'] ?? '').toString();
    if (raw.length >= 10) return raw.substring(0, 10);
    return raw;
  }

  Future<bool> _ensureSurveySaved() async {
    if (_profileCtrl.profile.value == null) {
      await _profileCtrl.fetchProfile();
    }
    if (_profileCtrl.profile.value == null) {
      Get.snackbar('오류', '설문조사를 먼저 작성해 주세요.');
      return false;
    }
    return true;
  }

  Future<void> _openMatchingSplitIfStarted() async {
    if (!_hasInterestRooms) {
      Get.snackbar('안내', '관심관을 설정해주세요. 관심관이 설정되지 않으면 매칭이 오지 않아요');
      return;
    }
    final hasSurvey = await _ensureSurveySaved();
    if (!hasSurvey) return;
    final matchCtrl = Get.isRegistered<MatchController>()
        ? Get.find<MatchController>()
        : Get.put(MatchController());
    await Future.wait([
      matchCtrl.fetchActiveSessions(),
      matchCtrl.fetchThreads(),
      matchCtrl.fetchCooldown(),
    ]);
    try {
      final life = await _api.getCurrentLifeRoom();
      if (life['life_room'] != null) {
        Get.to(() => const LifeRoomScreen());
        return;
      }
    } catch (_) {}

    if (matchCtrl.hasStartedSession) {
      Get.to(() => const MatchScreen());
      return;
    }

    if (matchCtrl.isInCooldown) {
      try {
        final rows = await _api.getSessionHistory();
        final items = List<Map<String, dynamic>>.from(rows);
        final successRows = items.where(
          (s) => (s['ui_status']?.toString() ?? '') == 'match_success',
        );
        final latest = successRows.isNotEmpty ? successRows.first : null;
        if (latest != null) {
          Get.to(() => MatchHistoryDetailScreen(session: latest));
          return;
        }
      } catch (_) {}
      Get.snackbar('안내', '재매칭 대기 시간이 남아 있습니다.');
      return;
    }

    try {
      final res = await _api.getMatchingOptions();
      final phase = (res['phase'] ?? 'closed').toString();
      if (phase == 'closed') {
        Get.snackbar('오류', '매칭 기간이 아닙니다.');
        return;
      }
      if (phase == 'life') {
        try {
          final life = await _api.getCurrentLifeRoom();
          if (life['life_room'] != null) {
            Get.to(() => const LifeRoomScreen());
            return;
          }
        } catch (_) {}
        Get.snackbar('안내', '현재 생활 기간입니다. 생활방에서 기능을 이용하세요.');
        return;
      }
      Get.to(() => const MatchingSplitScreen());
    } catch (_) {
      Get.snackbar('오류', '매칭 기간이 아닙니다.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = _auth.user.value;

    return Stack(
      children: [
        Scaffold(
          body: SafeArea(
            child: CustomScrollView(
          slivers: [
            // Top bar
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 20, 24, 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${user?.name ?? '사용자'}님 안녕하세요',
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF1C1C1E),
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          '오늘도 좋은 룸메이트를 찾아보세요',
                          style: TextStyle(
                            fontSize: 14,
                            color: Color(0xFF9CA3AF),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                    Row(
                      children: [
                        IconButton(
                          onPressed: () => Get.to(() => const NoticesScreen()),
                          icon: const Icon(
                            Icons.notifications_none_rounded,
                            color: Color(0xFF6B7280),
                          ),
                        ),
                        IconButton(
                          onPressed: () =>
                              Get.to(() => const ChatThreadsScreen()),
                          icon: const Icon(
                            Icons.chat_bubble_outline,
                            color: Color(0xFF6B7280),
                          ),
                        ),
                        IconButton(
                          onPressed: () {
                            _auth.logout();
                            Get.offAll(() => const LoginScreen());
                          },
                          icon: const Icon(
                            Icons.logout_rounded,
                            color: Color(0xFF9CA3AF),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // Hero card
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 16,
                ),
                child: Container(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF2563EB), Color(0xFF1D4ED8)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0x3F2563EB),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              (user?.name ?? 'U').substring(0, 1),
                              style: const TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  user?.name ?? '사용자',
                                  style: const TextStyle(
                                    fontSize: 20,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  user?.isEnrolled == true
                                      ? (user?.studentId ?? '')
                                      : (user?.regionName ?? ''),
                                  style: TextStyle(
                                    fontSize: 14,
                                    color: Colors.white.withValues(alpha: 0.8),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      Obx(() {
                        if (_profileCtrl.isLoading.value) {
                          return const Center(
                            child: CircularProgressIndicator(
                              color: Colors.white,
                            ),
                          );
                        }
                        if (_profileCtrl.profile.value == null) {
                          return _heroButton(
                            icon: Icons.warning_amber_rounded,
                            label: '설문조사를 먼저 작성해 주세요',
                            subLabel: '탭해서 설문지 작성하기',
                            onTap: () => Get.to(() => const SurveyScreen()),
                            bgColor: Colors.white.withValues(alpha: 0.15),
                          );
                        }
                        return Column(
                          children: [
                            _heroButton(
                              icon: Icons.check_circle_rounded,
                              label: '설문조사 완료',
                              subLabel: '나의 유형 보기',
                              onTap: () {
                                final profile = _profileCtrl.profile.value;
                                if (profile != null) {
                                  Get.to(
                                    () => PersonaDetailScreen(profile: profile),
                                  );
                                }
                              },
                              bgColor: Colors.white.withValues(alpha: 0.15),
                            ),
                            const SizedBox(height: 10),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Obx(
                                () => Text(
                                  _profileCtrl.profile.value != null
                                      ? '나의 유형: ${calculateTopPersona(_profileCtrl.profile.value!)}'
                                      : '유형 분석 중...',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.white.withValues(alpha: 0.9),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        );
                      }),
                    ],
                  ),
                ),
              ),
            ),

            if (_needsHallConfirmation)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 4, 24, 0),
                  child: GestureDetector(
                    onTap: () async {
                      final hasSurvey = await _ensureSurveySaved();
                      if (!hasSurvey) return;
                      Get.to(() => const InterestRoomsScreen())?.then((_) {
                        _checkHallConfirmation();
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEE2E2),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.error_outline, color: Color(0xFFDC2626), size: 22),
                          SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              '관심관을 설정해주세요. 관심관이 설정되지 않으면 매칭이 오지 않아요',
                              style: TextStyle(
                                fontSize: 13,
                                color: Color(0xFF991B1B),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          Icon(Icons.arrow_forward_ios, color: Color(0xFFDC2626), size: 14),
                        ],
                      ),
                    ),
                  ),
                ),
              ),

            // 기숙사 찾기 버튼
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 4, 24, 8),
                child: GestureDetector(
                  onTap: _openMatchingSplitIfStarted,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      vertical: 16,
                      horizontal: 20,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFF7C3AED),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0x3F7C3AED),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.apartment, color: Colors.white, size: 24),
                        SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '기숙사 찾기',
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              SizedBox(height: 2),
                              Text(
                                '나와 맞는 기숙사 룸메이트를 찾아보세요',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFFD8B4FE),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.arrow_forward_ios,
                          color: Colors.white,
                          size: 14,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            // 관심관 설정하기 버튼
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
                child: GestureDetector(
                  onTap: () async {
                    final hasSurvey = await _ensureSurveySaved();
                    if (!hasSurvey) return;
                    Get.to(() => const InterestRoomsScreen());
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      vertical: 14,
                      horizontal: 20,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF59E0B),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: const Color(0xFFFCD34D)),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x2DF59E0B),
                          blurRadius: 12,
                          offset: Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.meeting_room_rounded, color: Colors.white, size: 22),
                        SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '관심관 설정하기',
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              SizedBox(height: 2),
                              Text(
                                '내가 매칭 받을 관을 등록하세요',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFFFDE68A),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.arrow_forward_ios,
                          color: Colors.white,
                          size: 14,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            // Quick actions
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
                child: Row(
                  children: [
                    Expanded(
                      child: _quickActionCard(
                        icon: Icons.people_alt_rounded,
                        label: '쉐어하우스 찾기',
                        color: const Color(0xFF2563EB),
                        onTap: () async {
                          final hasSurvey = await _ensureSurveySaved();
                          if (!hasSurvey) return;
                          Get.snackbar('안내', '쉐어하우스 찾기 메뉴는 현재 비활성화되어 있습니다.');
                        },
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _quickActionCard(
                        icon: Icons.apartment_rounded,
                        label: '자취방 찾기',
                        color: const Color(0xFF059669),
                        onTap: () async {
                          final hasSurvey = await _ensureSurveySaved();
                          if (!hasSurvey) return;
                          Get.snackbar(
                            '준비 중',
                            '자취방 찾기 기능은 곧 업데이트됩니다.',
                            snackPosition: SnackPosition.TOP,
                            backgroundColor: const Color(0xFFE3F2FD),
                            colorText: const Color(0xFF1565C0),
                            margin: const EdgeInsets.all(16),
                            borderRadius: 16,
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // 나의 설문지

            // 공지사항 최근 3개 미리보기
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      '공지사항',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF1C1C1E),
                      ),
                    ),
                    TextButton(
                      onPressed: () => Get.to(() => const NoticesScreen()),
                      child: const Text('전체보기'),
                    ),
                  ],
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: _noticeLoading
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: 20),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    : _noticePreview.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.only(bottom: 16),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Text('등록된 공지사항이 없습니다.'),
                        ),
                      )
                    : Column(
                        children: _noticePreview.map((n) {
                          return GestureDetector(
                            onTap: () => Get.to(() => const NoticesScreen()),
                            child: Container(
                              margin: const EdgeInsets.only(bottom: 10),
                              padding: const EdgeInsets.all(16),
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
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    width: 40,
                                    height: 40,
                                    decoration: BoxDecoration(
                                      color: const Color(
                                        0xFF2563EB,
                                      ).withValues(alpha: 0.08),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: const Icon(
                                      Icons.campaign_outlined,
                                      color: Color(0xFF2563EB),
                                      size: 22,
                                    ),
                                  ),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          (n['title'] ?? '').toString(),
                                          style: const TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w700,
                                            color: Color(0xFF1C1C1E),
                                          ),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          (n['body'] ?? '').toString(),
                                          style: TextStyle(
                                            fontSize: 13,
                                            color: Colors.grey.shade600,
                                            height: 1.4,
                                          ),
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          _noticeDate(n),
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: Colors.grey.shade400,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const Icon(
                                    Icons.arrow_forward_ios,
                                    size: 14,
                                    color: Color(0xFFD1D5DB),
                                  ),
                                ],
                              ),
                            ),
                          );
                        }).toList(),
                      ),
              ),
            ),

            const SliverToBoxAdapter(child: SizedBox(height: 40)),
          ],
        ),
      ),
    ),
    if (_showTutorial) _buildTutorialOverlay(),
    ],
    );
  }

  Widget _buildTutorialOverlay() {
    return Positioned.fill(
      child: Container(
        color: Colors.black54,
        child: Center(
          child: Material(
            color: Colors.transparent,
            child: Container(
              width: 320,
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '시작하기',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 20),
                  GestureDetector(
                    onTap: () async {
                      final hasSurvey = await _ensureSurveySaved();
                      if (!hasSurvey) return;
                      Get.to(() => const SurveyScreen())?.then((_) {
                        _profileCtrl.fetchProfile();
                      });
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7C3AED),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Center(
                        child: Text(
                          '설문 작성하기',
                          style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  GestureDetector(
                    onTap: () async {
                      final hasSurvey = await _ensureSurveySaved();
                      if (!hasSurvey) return;
                      Get.to(() => const InterestRoomsScreen())?.then((_) {
                        _checkHallConfirmation();
                      });
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7C3AED),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Center(
                        child: Text(
                          '관심관 설정하기',
                          style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: _dismissTutorial,
                    child: const Text(
                      '닫기',
                      style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 14),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _heroButton({
    required IconData icon,
    required String label,
    required String subLabel,
    required VoidCallback onTap,
    required Color bgColor,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            Icon(icon, color: Colors.white, size: 22),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  Text(
                    subLabel,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withValues(alpha: 0.7),
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 14),
          ],
        ),
      ),
    );
  }

  Widget _quickActionCard({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 22),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: const Color(0x0D000000),
              blurRadius: 16,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(icon, color: color, size: 26),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}
