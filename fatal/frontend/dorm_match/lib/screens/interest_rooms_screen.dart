import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../services/api_service.dart';
import 'matching_split_screen.dart';

class InterestRoomsScreen extends StatefulWidget {
  const InterestRoomsScreen({super.key});

  @override
  State<InterestRoomsScreen> createState() => _InterestRoomsScreenState();
}

class _InterestRoomsScreenState extends State<InterestRoomsScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  bool _saving = false;
  String _phase = 'closed';
  int _maxSelectable = 0;
  int _changeLimit = 1;
  int _changeUsed = 0;
  int _changeRemaining = 1;
  bool _needsConfirmation = false;
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
      final res = await _api.getInterestRooms();
      setState(() {
        _phase = (res['phase'] ?? 'closed').toString();
        _maxSelectable = (res['max_selectable'] ?? 0) as int;
        _changeLimit = (res['change_limit'] ?? 1) as int;
        _changeUsed = (res['change_used'] ?? 0) as int;
        _changeRemaining = (res['change_remaining'] ?? 1) as int;
        _needsConfirmation = res['needs_hall_confirmation'] == true;
        _roomTypes = List<Map<String, dynamic>>.from(
          res['visible_room_types'] ?? const [],
        );
        _selected
          ..clear()
          ..addAll(
            List<int>.from(res['selected_interest_room_type_ids'] ?? const []),
          );
        _savedSelected = List<int>.from(_selected);
        _hasExistingSelection = _selected.isNotEmpty;
        _editMode = false;
      });
    } catch (e) {
      Get.snackbar('오류', '관심관 정보를 불러오지 못했습니다. $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    if (_selected.isEmpty) {
      Get.snackbar('알림', '관심관을 1개 이상 선택해주세요.');
      return;
    }
    setState(() => _saving = true);
    try {
      final hasChange = _hasExistingSelection &&
          !_listsEqual(_selected, _savedSelected);
      await _api.saveInterestRooms(
        _selected,
        confirmChange: hasChange ? true : null,
      );
      if (!mounted) return;
      Get.snackbar('저장 완료', '관심관이 저장되었습니다.');
      _load();
    } catch (e) {
      final msg = e.toString();
      if (msg.contains('needs_confirm') || msg.contains('409')) {
        final doChange = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('관심관 변경'),
            content: Text(
                '관심관을 변경하면 변경 가능 횟수가 1회 차감됩니다.\n남은 변경 횟수: $_changeRemaining회\n\n변경하시겠습니까?'),
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
            await _api.saveInterestRooms(_selected, confirmChange: true);
            if (!mounted) return;
            Get.snackbar('저장 완료', '관심관이 저장되었습니다.');
            _load();
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
      appBar: AppBar(title: const Text('관심관 설정')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_needsConfirmation)
                    Container(
                      padding: const EdgeInsets.all(12),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEE2E2),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.error_outline,
                              color: Color(0xFFDC2626), size: 20),
                          SizedBox(width: 8),
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
                        ],
                      ),
                    ),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEF3C7),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: const Color(0xFFFCD34D)),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.info_outline,
                            color: Color(0xFFD97706), size: 20),
                        SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            '관심관은 단순 즐겨찾기가 아닙니다. 등록한 관을 기준으로 매칭 대상이 결정되며, 해당 관에서 생성된 세션의 후보로 노출됩니다.',
                            style: TextStyle(
                              fontSize: 13,
                              color: Color(0xFF92400E),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_phase == 'main')
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        '현재 룸메이트 신청 기간입니다. 관심관 1개만 선택 가능합니다.',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '선택 가능 최대 $_maxSelectable개',
                          style: const TextStyle(
                              color: Color(0xFF6B7280), fontSize: 13),
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
                                color: const Color(0xFFF59E0B),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                _editMode ? '취소' : '변경 ($_changeUsed/$_changeLimit)',
                                style: const TextStyle(
                                  color: Color(0xFFF59E0B),
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: ListView.separated(
                      itemCount: _roomTypes.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) {
                        final rt = _roomTypes[i];
                        final id = (rt['id'] ?? 0) as int;
                        final dormName = (rt['dorm_name'] ?? '').toString();
                        final capacity = (rt['capacity'] ?? 2) as int;
                        final name = '$dormName ${capacity}인실';
                        final selected = _selected.contains(id);
                        final genderText = rt['dorm_gender'] == 'male'
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
                                    if (_phase == 'main') {
                                      _selected
                                        ..clear()
                                        ..add(id);
                                    } else {
                                      if (_selected.length >=
                                          _maxSelectable) {
                                        Get.snackbar(
                                          '알림',
                                          '최대 $_maxSelectable개까지 선택 가능합니다.',
                                        );
                                        return;
                                      }
                                      _selected.add(id);
                                    }
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
                                    ? const Color(0xFFF59E0B)
                                    : const Color(0xFFE5E7EB),
                                width: selected ? 2 : 1,
                              ),
                              boxShadow: selected && !isUnselectedDisabled
                                  ? const [
                                      BoxShadow(
                                        color: Color(0x33F59E0B),
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
                                                  ? const Color(0xFFB45309)
                                                  : const Color(0xFF111827),
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '$genderText 기숙사',
                                        style: TextStyle(
                                          fontSize: 13,
                                          color: isUnselectedDisabled
                                              ? const Color(0xFFD1D5DB)
                                              : const Color(0xFF6B7280),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                if (selected)
                                  const Icon(
                                    Icons.check_circle_rounded,
                                    color: Color(0xFFF59E0B),
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
                      onPressed: (_phase == 'closed' && _hasExistingSelection) || _saving
                          ? null
                          : _editMode
                              ? _save
                              : _hasExistingSelection
                                  ? () =>
                                      Get.to(() => const MatchingSplitScreen())
                                  : _save,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFF59E0B),
                        foregroundColor: Colors.white,
                      ),
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Text(
                              _editMode
                                  ? '변경하기'
                                  : _hasExistingSelection
                                      ? '매칭하러 가기'
                                      : '관심관 저장',
                            ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
