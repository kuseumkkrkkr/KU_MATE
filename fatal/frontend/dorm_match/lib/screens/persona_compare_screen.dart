import 'dart:ui';

import 'package:flutter/material.dart';

import '../models/profile.dart';
import '../utils/persona_scoring.dart';

class PersonaCompareScreen extends StatelessWidget {
  final Profile profile;
  final String personaName;

  const PersonaCompareScreen({
    super.key,
    required this.profile,
    required this.personaName,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final score = calculatePersonaScores(profile)[personaName] ?? 0.0;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(title: Text('$personaName 비교')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _GlassSurface(
                radius: 22,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${score.round()}% 일치',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: scheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        personaName,
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                          color: scheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '세부 항목 전체를 기준값과 내 응답으로 비교합니다.',
                        style: TextStyle(
                          fontSize: 14,
                          color: scheme.onSurface.withValues(alpha: 0.72),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _sectionTitle(context, '세부 항목 비교 (전체)'),
              _GlassSurface(child: _rows(context)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String text) {
    final onSurface = Theme.of(context).colorScheme.onSurface;
    return Padding(
      padding: const EdgeInsets.only(left: 2, bottom: 8),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w800,
          color: onSurface,
        ),
      ),
    );
  }

  Widget _rows(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final my = profile;
    final base = _idealProfile(personaName);

    final items = <_Item>[
      _Item('본가 방문 주기', '${base.homeVisitCycle}', '${my.homeVisitCycle}'),
      _Item('향수 사용', '${base.perfume}', '${my.perfume}'),
      _Item(
        '실내 향 민감도',
        '${base.indoorScentSensitivity}',
        '${my.indoorScentSensitivity}',
      ),
      _Item('주량', '${base.alcoholTolerance}', '${my.alcoholTolerance}'),
      _Item('음주 빈도', '${base.alcoholFrequency}', '${my.alcoholFrequency}'),
      _Item('주사', '${base.drunkHabit}', '${my.drunkHabit}'),
      _Item(
        '게임/컴퓨터 시간(주)',
        '${base.gamingHoursPerWeek}h',
        '${my.gamingHoursPerWeek}h',
      ),
      _Item('스피커 사용', '${base.speakerUse}', '${my.speakerUse}'),
      _Item('운동', '${base.exercise}', '${my.exercise}'),
      _Item('취침 시간', '${base.bedtime}시', '${my.bedtime}시'),
      _Item('기상 시간', '${base.wakeTime}시', '${my.wakeTime}시'),
      _Item('잠버릇', '${base.sleepHabit}', '${my.sleepHabit}'),
      _Item('수면 민감도', '${base.sleepSensitivity}', '${my.sleepSensitivity}'),
      _Item('알람 강도', '${base.alarmStrength}', '${my.alarmStrength}'),
      _Item('수면등 사용', '${base.sleepLight}', '${my.sleepLight}'),
      _Item('코골이', '${base.snoring}', '${my.snoring}'),
      _Item('샤워 주기', '${base.showerCycle}', '${my.showerCycle}'),
      _Item('샤워 시간(분)', '${base.showerDuration}', '${my.showerDuration}'),
      _Item('샤워 시각', '${base.showerTime}시', '${my.showerTime}시'),
      _Item('청소 주기', '${base.cleaningCycle}일', '${my.cleaningCycle}일'),
      _Item('환기 빈도', '${base.ventilation}', '${my.ventilation}'),
      _Item(
        '욕실 드라이기',
        '${base.hairdryerInBathroom}',
        '${my.hairdryerInBathroom}',
      ),
      _Item('휴지 공유', '${base.toiletPaperShare}', '${my.toiletPaperShare}'),
      _Item('실내 취식', '${base.indoorEating}', '${my.indoorEating}'),
      _Item('흡연', '${base.smoking}', '${my.smoking}'),
      _Item('온도 선호', '${base.temperaturePref}', '${my.temperaturePref}'),
      _Item('실내 통화', '${base.indoorCall}', '${my.indoorCall}'),
      _Item('벌레 대처', '${base.bugHandling}', '${my.bugHandling}'),
      _Item('빨래 주기', '${base.laundryCycle}일', '${my.laundryCycle}일'),
      _Item('건조대 사용', '${base.dryingRack}', '${my.dryingRack}'),
      _Item('냉장고 사용', '${base.fridgeUse}', '${my.fridgeUse}'),
      _Item('방 내 공부', '${base.studyInRoom}', '${my.studyInRoom}'),
      _Item('소음 민감도', '${base.noiseSensitivity}', '${my.noiseSensitivity}'),
      _Item('친밀도', '${base.desiredIntimacy}', '${my.desiredIntimacy}'),
      _Item('같이 식사', '${base.mealTogether}', '${my.mealTogether}'),
      _Item('같이 운동', '${base.exerciseTogether}', '${my.exerciseTogether}'),
      _Item('친구 초대', '${base.friendInvite}', '${my.friendInvite}'),
    ];

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Column(
        children: items.asMap().entries.map((entry) {
          final i = entry.key;
          final item = entry.value;

          return Column(
            children: [
              if (i > 0) const Divider(height: 1, color: Color(0xFFE5E7EB)),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                child: Row(
                  children: [
                    Expanded(
                      flex: 3,
                      child: Text(
                        item.label,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: scheme.onSurface,
                        ),
                      ),
                    ),
                    Expanded(
                      flex: 2,
                      child: Text(
                        item.base,
                        textAlign: TextAlign.end,
                        style: TextStyle(
                          fontSize: 13,
                          color: scheme.onSurface.withValues(alpha: 0.75),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: Text(
                        item.mine,
                        textAlign: TextAlign.end,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          color: scheme.primary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Profile _idealProfile(String persona) {
    final presets = <Profile>[
      Profile(
        studyInRoom: 1,
        noiseSensitivity: 5,
        speakerUse: 0,
        gamingHoursPerWeek: 0,
        bedtime: 23,
        friendInvite: 0,
        desiredIntimacy: 1,
      ),
      Profile(
        indoorScentSensitivity: 5,
        indoorEating: 1,
        fridgeUse: 1,
        toiletPaperShare: 1,
        ventilation: 2.0,
        temperaturePref: 2,
        cleaningCycle: 3,
      ),
      Profile(
        gamingHoursPerWeek: 56,
        bedtime: 2,
        alarmStrength: 5,
        speakerUse: 1,
        homeVisitCycle: 1,
      ),
      Profile(
        cleaningCycle: 1,
        showerCycle: 4,
        laundryCycle: 3,
        hairdryerInBathroom: 1,
        desiredIntimacy: 4,
        showerDuration: 10,
      ),
      Profile(
        cleaningCycle: 60,
        showerCycle: 0,
        fridgeUse: 0,
        desiredIntimacy: 1,
        studyInRoom: 0,
        noiseSensitivity: 1,
      ),
      Profile(
        desiredIntimacy: 5,
        mealTogether: 3,
        exerciseTogether: 3,
        friendInvite: 2,
      ),
      Profile(
        desiredIntimacy: 1,
        toiletPaperShare: 0,
        indoorCall: 0,
        friendInvite: 0,
        mealTogether: 1,
      ),
      Profile(
        sleepSensitivity: 5,
        sleepLight: 1,
        bedtime: 23,
        snoring: 0,
        noiseSensitivity: 5,
      ),
    ];

    return presets[persona.hashCode.abs() % presets.length];
  }
}

class _Item {
  final String label;
  final String base;
  final String mine;

  const _Item(this.label, this.base, this.mine);
}

class _GlassSurface extends StatelessWidget {
  final Widget child;
  final double radius;

  const _GlassSurface({required this.child, this.radius = 16});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.32),
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(
              color: scheme.primary.withValues(alpha: 0.22),
              width: 1.1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.white.withValues(alpha: 0.72),
                blurRadius: 0,
                spreadRadius: 0.6,
              ),
              const BoxShadow(
                color: Color(0x14000000),
                blurRadius: 10,
                offset: Offset(0, 4),
              ),
            ],
          ),
          foregroundDecoration: BoxDecoration(
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.72),
              width: 0.8,
            ),
          ),
          child: child,
        ),
      ),
    );
  }
}
