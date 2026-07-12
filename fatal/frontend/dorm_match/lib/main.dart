import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'screens/splash_screen.dart';
import 'screens/main_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/admin_dashboard_screen.dart';
import 'screens/matching_split_screen.dart';
import 'screens/life_room_screen.dart';
import 'controllers/auth_controller.dart';
import 'controllers/match_controller.dart';

void main() {
  Get.put(AuthController());
  Get.lazyPut<MatchController>(() => MatchController(), fenix: true);
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  static const Color _primary = Color(0xFF2563EB);
  static const Color _surface = Colors.white;
  static const Color _scaffoldBg = Color(0xFFF8F9FE);
  static const Color _onSurface = Color(0xFF1C1C1E);

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      title: 'Roomantic',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        scaffoldBackgroundColor: _scaffoldBg,
        colorScheme: ColorScheme.fromSeed(
          seedColor: _primary,
          brightness: Brightness.light,
          surface: _surface,
          primary: _primary,
          onSurface: _onSurface,
        ),
        cardTheme: const CardThemeData(
          color: _surface,
          elevation: 0,
          margin: EdgeInsets.symmetric(horizontal: 20, vertical: 6),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(24)),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: _primary,
            foregroundColor: Colors.white,
            elevation: 0,
            padding: const EdgeInsets.symmetric(vertical: 18),
            shape: const RoundedRectangleBorder(
              borderRadius: BorderRadius.all(Radius.circular(16)),
            ),
            textStyle: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.2,
            ),
          ),
        ),
        textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
            foregroundColor: _primary,
            textStyle: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: _surface,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 18,
            vertical: 18,
          ),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: _primary, width: 1.8),
          ),
          hintStyle: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 15),
          labelStyle: const TextStyle(color: Color(0xFF6B7280), fontSize: 14),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: _scaffoldBg,
          elevation: 0,
          centerTitle: true,
          scrolledUnderElevation: 0,
          titleTextStyle: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: _onSurface,
            letterSpacing: -0.3,
          ),
          iconTheme: IconThemeData(color: _onSurface),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: _surface,
          selectedItemColor: _primary,
          unselectedItemColor: Color(0xFF9CA3AF),
          type: BottomNavigationBarType.fixed,
          elevation: 0,
          selectedLabelStyle: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
          unselectedLabelStyle: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
        ),
        tabBarTheme: const TabBarThemeData(
          dividerColor: Colors.transparent,
          labelColor: _primary,
          unselectedLabelColor: Color(0xFF9CA3AF),
          indicatorSize: TabBarIndicatorSize.tab,
          labelStyle: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          unselectedLabelStyle: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w500,
          ),
        ),
        sliderTheme: const SliderThemeData(
          activeTrackColor: _primary,
          thumbColor: _primary,
          overlayColor: Color(0x1F2563EB),
          inactiveTrackColor: Color(0xFFE5E7EB),
          trackHeight: 4,
        ),
        switchTheme: SwitchThemeData(
          thumbColor: WidgetStateProperty.resolveWith(
            (states) =>
                states.contains(WidgetState.selected) ? _primary : Colors.white,
          ),
          trackColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? const Color(0xFF2563EB).withValues(alpha: 0.3)
                : const Color(0xFFE5E7EB),
          ),
          trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
        ),
      ),
      home: const SplashScreen(),
      getPages: [
        GetPage(name: '/splash', page: () => const SplashScreen()),
        GetPage(name: '/login', page: () => const LoginScreen()),
        GetPage(name: '/register', page: () => const RegisterScreen()),
        GetPage(name: '/home', page: () => const MainScreen()),
        GetPage(name: '/admin', page: () => const AdminDashboardScreen()),
        GetPage(
          name: '/matching-split',
          page: () => const MatchingSplitScreen(),
        ),
        GetPage(name: '/life-room', page: () => const LifeRoomScreen()),
      ],
    );
  }
}
