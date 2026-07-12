import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/match_controller.dart';
import '../services/api_service.dart';
import 'match_screen.dart';

class MatchingSplitScreen extends StatefulWidget {
  const MatchingSplitScreen({super.key});

  @override
  State<MatchingSplitScreen> createState() => _MatchingSplitScreenState();
}

class _MatchingSplitScreenState extends State<MatchingSplitScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  bool _saving = false;
  String _phase = 'closed';
  int _maxSelectable = 0;
  int _changeLimit = 1;
  int _changeUsed = 0;
  int _changeRemaining = 1;
  bool _editMode = false;
  bool _hasExistingSelection = false;
  List<Map<String, dynamic>> _roomTypes = const [];
  final List<int> _selected = [];
  List<int> _savedSelected = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  bool get _isLocked => _hasExistingSelection && _changeRemaining <= 0;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final matchCtrl = Get.isRegistered<MatchController>()
          ? Get.find<MatchController>()
          : Get.put(MatchController());
      await Future.wait([
        matchCtrl.fetchActiveSessions(),
        matchCtrl.fetchThreads(),
      ]);
      if (!mounted) return;
      if (matchCtrl.hasStartedSession) {
        Get.off(() => const MatchScreen());
        return;
      }

      final res = await _api.getMatchingOptions();
      setState(() {
        _phase = (res['phase'] ?? 'closed').toString();
        _maxSelectable = (res['max_selectable'] ?? 0) as int;
        _changeLimit = (res['change_limit'] ?? 1) as int;
        _changeUsed = (res['change_used'] ?? 0) as int;
        _changeRemaining = (res['change_remaining'] ?? 1) as int;
        _roomTypes = List<Map<String, dynamic>>.from(
          res['visible_room_types'] ?? const [],
        );
        _selected
          ..clear()
          ..addAll(List<int>.from(res['selected_room_types'] ?? const []));
        _savedSelected = List<int>.from(_selected);
        _hasExistingSelection = _selected.isNotEmpty;
        _editMode = false;
      });
      if (_phase == 'life' && mounted) {
        Get.snackbar('안내', '생활 기간에는 새 매칭을 시작할 수 없습니다.');
      }
    } catch (e) {
      Get.snackbar('오류', '매칭 정보를 불러오지 못했습니다. $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _start() async {
    if (_selected.isEmpty) {
      Get.snackbar('알림', '선호 관을 선택해주세요.');
      return;
    }
    setState(() => _saving = true);
    try {
      final hasChange = _hasExistingSelection &&
          !_listsEqual(_selected, _savedSelected);
      await _api.saveMatchingPreferences(
        _selected,
        confirmChange: hasChange ? true : null,
      );
      if (!mounted) return;
      Get.off(() => const MatchScreen());
    } catch (e) {
      final msg = e.toString();
      if (msg.contains('needs_confirm') || msg.contains('409')) {
        final doChange = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('선호 관 변경'),
            content: Text(
                '선호 관을 변경하면 변경 가능 횟수가 1회 차감됩니다.\n남은 변경 횟수: $_changeRemaining회\n\n변경하시겠습니까?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('취소'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('변경'),
              ),
            ],
          ),
        );
        if (doChange == true) {
          try {
            await _api.saveMatchingPreferences(_selected,
                confirmChange: true);
            if (!mounted) return;
            Get.off(() => const MatchScreen());
          } catch (e2) {
            Get.snackbar('오류', '저장 실패: $e2');
          }
        }
      } else {
        Get.snackbar('오류', '저장 실패: $e');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  bool _listsEqual(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    final sa = List<int>.from(a)..sort();
    final sb = List<int>.from(b)..sort();
    for (var i = 0; i < sa.length; i++) {
      if (sa[i] != sb[i]) return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('매칭 시작')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _phase == 'preliminary'
                        ? '예비 매칭 기간'
                        : _phase == 'main'
                            ? '룸메이트 신청 기간'
                            : _phase == 'life'
                                ? '룸메이트 생활 기간'
                                : '매칭 기간 외',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '선택 가능 최대 $_maxSelectable개',
                          style:
                              const TextStyle(color: Color(0xFF6B7280)),
                        ),
                      ),
                      if (_hasExistingSelection && !_isLocked)
                        GestureDetector(
                          onTap: () {
                            if (_editMode) {
                              setState(() {
                                _selected
                                  ..clear()
                                  ..addAll(_savedSelected);
                                _editMode = false;
                              });
                            } else {
                              setState(() => _editMode = true);
                            }
                          },
                          child: Row(
                            children: [
                              Icon(
                                _editMode ? Icons.close_rounded : Icons.edit_rounded,
                                size: 18,
                                color: const Color(0xFF2563EB),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                _editMode ? '취소' : '변경 ($_changeUsed/$_changeLimit)',
                                style: const TextStyle(
                                  color: Color(0xFF2563EB),
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Expanded(
                    child: ListView.separated(
                      itemCount: _roomTypes.length,
                      separatorBuilder: (_, __) =>
                          const SizedBox(height: 12),
                      itemBuilder: (_, i) {
                        final rt = _roomTypes[i];
                        final id = (rt['id'] ?? 0) as int;
                        final dormName =
                            (rt['dorm_name'] ?? '').toString();
                        final capacity = (rt['capacity'] ?? 2) as int;
                        final name = '$dormName ${capacity}인실';
                        final selected = _selected.contains(id);
                        final genderText =
                            rt['dorm_gender'] == 'male'
                                ? '남'
                                : rt['dorm_gender'] == 'female'
                                    ? '여'
                                    : '남여';
                        final isUnselectedDisabled =
                            _hasExistingSelection && !_editMode && !selected;

                        return GestureDetector(
                          onTap: isUnselectedDisabled
                              ? null
                              : () {
                                  setState(() {
                                    if (selected) {
                                      _selected.remove(id);
                                      return;
                                    }
                                    if (_selected.length >=
                                        _maxSelectable) {
                                      Get.snackbar(
                                        '알림',
                                        '최대 $_maxSelectable개까지 선택 가능합니다.',
                                      );
                                      return;
                                    }
                                    _selected.add(id);
                                  });
                                },
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 180),
                            curve: Curves.easeOut,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 14,
                            ),
                            decoration: BoxDecoration(
                              color: isUnselectedDisabled
                                  ? const Color(0xFFF3F4F6)
                                  : Colors.white,
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(
                                color: selected
                                    ? const Color(0xFF2563EB)
                                    : const Color(0xFFE5E7EB),
                                width: selected ? 2 : 1,
                              ),
                              boxShadow: selected &&
                                      !isUnselectedDisabled
                                  ? const [
                                      BoxShadow(
                                        color: Color(0x332563EB),
                                        blurRadius: 14,
                                        offset: Offset(0, 6),
                                      ),
                                    ]
                                  : const [],
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        name,
                                        style: TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w700,
                                          color: isUnselectedDisabled
                                              ? const Color(0xFF9CA3AF)
                                              : selected
                                                  ? const Color(
                                                      0xFF1D4ED8)
                                                  : const Color(
                                                      0xFF111827),
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '$genderText 기숙사',
                                        style: TextStyle(
                                          fontSize: 13,
                                          color: isUnselectedDisabled
                                              ? const Color(0xFFD1D5DB)
                                              : const Color(
                                                  0xFF6B7280),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                if (selected)
                                  const Icon(
                                    Icons.check_circle_rounded,
                                    color: Color(0xFF2563EB),
                                  )
                                else if (isUnselectedDisabled)
                                  const Icon(
                                    Icons.radio_button_unchecked_rounded,
                                    color: Color(0xFFD1D5DB),
                                  )
                                else
                                  const Icon(
                                    Icons.radio_button_unchecked_rounded,
                                    color: Color(0xFF9CA3AF),
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: (_phase == 'closed' ||
                              _phase == 'life' ||
                              _saving)
                          ? null
                          : _editMode
                              ? _start
                              : () => Get.off(() => const MatchScreen()),
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2),
                            )
                          : Text(_editMode ? '변경하기' : '매칭 시작'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
