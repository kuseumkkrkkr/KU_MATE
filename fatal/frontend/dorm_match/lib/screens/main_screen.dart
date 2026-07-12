import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'chat_threads_screen.dart';
import 'home_screen.dart';
import 'life_room_screen.dart';
import 'match_history_screen.dart';
import 'profile_screen.dart';
import '../controllers/auth_controller.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;
  int _matchRefreshToken = 0;
  Worker? _authUserWorker;

  @override
  void initState() {
    super.initState();
    _pages[0] = _pageBuilders[0]();
    _authUserWorker = ever(Get.find<AuthController>().user, (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _authUserWorker?.dispose();
    super.dispose();
  }

  AuthController get _auth => Get.find<AuthController>();
  bool get _hasLifeRoom => _auth.user.value?.hasActiveLifeRoom == true;

  late final List<Widget Function()> _pageBuilders = [
    HomeScreen.new,
    ChatThreadsScreen.new,
    () => MatchHistoryScreen(refreshToken: _matchRefreshToken),
    ProfileScreen.new,
  ];
  late final List<Widget?> _pages = List<Widget?>.filled(
    _pageBuilders.length,
    null,
  );

  void _onTap(int index) {
    if (index == 2 && _hasLifeRoom) {
      Get.to(() => const LifeRoomScreen());
      return;
    }
    setState(() {
      _currentIndex = index;
      if (index == 2) {
        _matchRefreshToken++;
        _pages[index] = MatchHistoryScreen(refreshToken: _matchRefreshToken);
      } else {
        _pages[index] ??= _pageBuilders[index]();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    _pages[_currentIndex] ??= _pageBuilders[_currentIndex]();
    final children = _pages
        .map((p) => p ?? const SizedBox.shrink())
        .toList(growable: false);
    return Scaffold(
      body: IndexedStack(index: _currentIndex, children: children),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: _onTap,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF2563EB),
        unselectedItemColor: const Color(0xFF9CA3AF),
        items: [
          const BottomNavigationBarItem(
            icon: Icon(Icons.home_rounded),
            label: '홈',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.chat_bubble_outline),
            label: '채팅',
          ),
          BottomNavigationBarItem(
            icon: Icon(
              _hasLifeRoom ? Icons.apartment_rounded : Icons.favorite_rounded,
            ),
            label: _hasLifeRoom ? '생활관' : '매칭',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.person_rounded),
            label: '프로필',
          ),
        ],
      ),
    );
  }
}
