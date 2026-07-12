import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/api_service.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  List<Map<String, dynamic>> _schools = const [];
  final Set<int> _collapsedSchoolIds = <int>{};
  final _nameCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _restoreUiState();
    _load();
  }

  Future<void> _restoreUiState() async {
    final sp = await SharedPreferences.getInstance();
    final raw = sp.getStringList('admin_collapsed_school_ids') ?? const [];
    final ids = raw.map((e) => int.tryParse(e) ?? 0).where((e) => e > 0).toSet();
    if (!mounted) return;
    setState(() {
      _collapsedSchoolIds
        ..clear()
        ..addAll(ids);
    });
  }

  Future<void> _persistCollapsedState() async {
    final sp = await SharedPreferences.getInstance();
    await sp.setStringList(
      'admin_collapsed_school_ids',
      _collapsedSchoolIds.map((e) => e.toString()).toList(),
    );
  }
  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getSchools(includeHidden: true);
      setState(() => _schools = List<Map<String, dynamic>>.from(res['schools'] ?? const []));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addSchool() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    await _api.createSchool({'name': _nameCtrl.text.trim()});
    _nameCtrl.clear();
    await _load();
  }

  Future<void> _renameSchool(Map<String, dynamic> school) async {
    final ctrl = TextEditingController(text: (school['name'] ?? '').toString());
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('학교명 변경'),
        content: TextField(controller: ctrl, decoration: const InputDecoration(labelText: '학교명')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('취소')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text('저장')),
        ],
      ),
    );
    if (result != null && result.isNotEmpty) {
      await _api.updateSchool(school['id'] as int, {'name': result});
      _load();
    }
  }

  Future<void> _toggleSchoolHidden(Map<String, dynamic> school) async {
    final isHidden = school['is_hidden'] == true;
    await _api.updateSchool(school['id'] as int, {'is_hidden': !isHidden});
    _load();
  }

  Future<void> _editDorms(Map<String, dynamic> school) async {

    final dorms = List<Map<String, dynamic>>.from(school['dormitories'] ?? const []);
    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${school['name']} 기숙사 편집'),
        content: SizedBox(
          width: 420,
          child: StatefulBuilder(
            builder: (context, setModalState) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  ...dorms.map((d) => Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              initialValue: (d['name'] ?? '').toString(),
                              onChanged: (v) => d['name'] = v,
                              decoration: const InputDecoration(labelText: '관 이름'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          SizedBox(
                            width: 130,
                            child: TextFormField(
                              initialValue: (() {
                                final roomTypes = List<Map<String, dynamic>>.from(d['room_types'] ?? const []);
                                if (roomTypes.isEmpty) return '2,3,4';
                                return roomTypes
                                    .where((rt) => (rt['is_enabled'] ?? 1) == 1)
                                    .map((rt) => (rt['capacity'] ?? '').toString())
                                    .join(',');
                              })(),
                              decoration: const InputDecoration(labelText: '인실(예:2,3,4)'),
                              onChanged: (v) {
                                final parsed = v
                                    .split(',')
                                    .map((e) => int.tryParse(e.trim()) ?? 0)
                                    .where((e) => e >= 2)
                                    .toSet()
                                    .toList()
                                  ..sort();
                                d['room_types'] = parsed.map((cap) => {'capacity': cap, 'is_enabled': true}).toList();
                              },
                            ),
                          ),
                          const SizedBox(width: 8),
                          DropdownButton<String>(
                            value: (d['gender'] ?? 'coed').toString(),
                            items: const [
                              DropdownMenuItem(value: 'male', child: Text('남')),
                              DropdownMenuItem(value: 'female', child: Text('여')),
                              DropdownMenuItem(value: 'coed', child: Text('남여')),
                            ],
                            onChanged: (v) => setModalState(() => d['gender'] = v ?? 'coed'),
                          ),
                        ],
                      )),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      onPressed: () => setModalState(() => dorms.add({'name': '', 'gender': 'coed'})),
                      child: const Text('관 추가'),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('취소')),
          ElevatedButton(
            onPressed: () async {
              await _api.updateSchoolDorms(school['id'] as int, dorms);
              if (!ctx.mounted) return;
              Navigator.pop(ctx);
              _load();
            },
            child: const Text('저장'),
          ),
        ],
      ),
    );
  }

  Future<void> _editSchedule(Map<String, dynamic> school) async {
    final startCtrl = TextEditingController(text: (school['recruitment_start'] ?? '').toString());
    final endCtrl = TextEditingController(text: (school['recruitment_end'] ?? '').toString());
    final preStartCtrl = TextEditingController(text: (school['pre_matching_start'] ?? '').toString());
    final preEndCtrl = TextEditingController(text: (school['pre_matching_end'] ?? '').toString());
    final applyStartCtrl = TextEditingController(text: (school['roommate_apply_start'] ?? '').toString());
    final applyEndCtrl = TextEditingController(text: (school['roommate_apply_end'] ?? '').toString());
    final lifeStartCtrl = TextEditingController(text: (school['room_life_start'] ?? '').toString());
    final lifeEndCtrl = TextEditingController(text: (school['room_life_end'] ?? '').toString());
    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${school['name']} 모집 일정'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: startCtrl, decoration: const InputDecoration(labelText: '모집 시작일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: endCtrl, decoration: const InputDecoration(labelText: '모집 마감일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: preStartCtrl, decoration: const InputDecoration(labelText: '예비매칭 시작일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: preEndCtrl, decoration: const InputDecoration(labelText: '예비매칭 종료일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: applyStartCtrl, decoration: const InputDecoration(labelText: '룸메신청 시작일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: applyEndCtrl, decoration: const InputDecoration(labelText: '룸메신청 종료일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: lifeStartCtrl, decoration: const InputDecoration(labelText: '생활방 시작일 (YYYY-MM-DD)')),
            const SizedBox(height: 8),
            TextField(controller: lifeEndCtrl, decoration: const InputDecoration(labelText: '생활방 종료일 (YYYY-MM-DD)')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('취소')),
          ElevatedButton(
            onPressed: () async {
              await _api.updateSchoolSchedule(
                school['id'] as int,
                {
                  'recruitment_start': startCtrl.text.trim(),
                  'recruitment_end': endCtrl.text.trim(),
                  'pre_matching_start': preStartCtrl.text.trim(),
                  'pre_matching_end': preEndCtrl.text.trim(),
                  'roommate_apply_start': applyStartCtrl.text.trim(),
                  'roommate_apply_end': applyEndCtrl.text.trim(),
                  'room_life_start': lifeStartCtrl.text.trim(),
                  'room_life_end': lifeEndCtrl.text.trim(),
                },
              );
              if (!ctx.mounted) return;
              Navigator.pop(ctx);
              _load();
            },
            child: const Text('저장'),
          ),
        ],
      ),
    );
  }

  Future<void> _openNoticesEditor() async {
    List<Map<String, dynamic>> notices = const [];
    List<Map<String, dynamic>> schoolNotices = const [];
    String? loadError;
    int noticeTab = 0;
    int? selectedSchoolId = _schools.isNotEmpty ? (_schools.first['id'] as int) : null;
    try {
      notices = await _api.getAdminNotices();
      if (selectedSchoolId != null) {
        final sid = selectedSchoolId;
        if (sid != null) {
          schoolNotices = await _api.getSchoolNotices(sid);
        }
      }
    } catch (e) {
      loadError = e.toString();
    }

    final titleCtrl = TextEditingController();
    final bodyCtrl = TextEditingController();
    bool pinned = false;
    bool collapsed = false;
    int? editingId;
    bool saving = false;
    bool noticeListOpen = true;

    Future<void> refresh(StateSetter setModalState) async {
      try {
        final list = await _api.getAdminNotices();
        final listSchool = selectedSchoolId == null
            ? <Map<String, dynamic>>[]
            : await _api.getSchoolNotices(selectedSchoolId!);
        setModalState(() {
          notices = list;
          schoolNotices = listSchool;
          loadError = null;
        });
      } catch (e) {
        setModalState(() => loadError = e.toString());
      }
    }

    void bind(Map<String, dynamic> n, StateSetter setModalState) {
      setModalState(() {
        editingId = n['id'] as int;
        titleCtrl.text = (n['title'] ?? '').toString();
        bodyCtrl.text = (n['body'] ?? '').toString();
        pinned = n['is_pinned'] == true;
        collapsed = n['is_collapsed'] == true;
      });
    }

    void clearEditor(StateSetter setModalState) {
      setModalState(() {
        editingId = null;
        titleCtrl.clear();
        bodyCtrl.clear();
        pinned = false;
        collapsed = false;
      });
    }

    if (!mounted) return;
    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('공지함 편집'),
        content: SizedBox(
          width: 760,
          child: StatefulBuilder(
            builder: (context, setModalState) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      ChoiceChip(
                        label: const Text('글로벌 공지'),
                        selected: noticeTab == 0,
                        onSelected: (_) => setModalState(() => noticeTab = 0),
                      ),
                      const SizedBox(width: 8),
                      ChoiceChip(
                        label: const Text('학교별 공지'),
                        selected: noticeTab == 1,
                        onSelected: (_) => setModalState(() => noticeTab = 1),
                      ),
                      if (noticeTab == 1) ...[
                        const SizedBox(width: 8),
                        Expanded(
                          child: DropdownButton<int>(
                            isExpanded: true,
                            value: selectedSchoolId,
                            items: _schools
                                .map((s) => DropdownMenuItem<int>(
                                      value: s['id'] as int,
                                      child: Text((s['name'] ?? '').toString()),
                                    ))
                                .toList(),
                            onChanged: (v) async {
                              if (v == null) return;
                              setModalState(() => selectedSchoolId = v);
                              await refresh(setModalState);
                            },
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Text('공지 목록'),
                      const Spacer(),
                      IconButton(
                        tooltip: noticeListOpen ? '목록 닫기' : '목록 열기',
                        onPressed: () => setModalState(() => noticeListOpen = !noticeListOpen),
                        icon: Icon(noticeListOpen ? Icons.expand_less : Icons.expand_more),
                      ),
                      TextButton(
                        onPressed: () => clearEditor(setModalState),
                        child: const Text('새 공지'),
                      ),
                      TextButton(
                        onPressed: () => refresh(setModalState),
                        child: const Text('새로고침'),
                      ),
                    ],
                  ),
                  if (noticeListOpen)
                    Container(
                      constraints: const BoxConstraints(maxHeight: 230),
                      decoration: BoxDecoration(
                        border: Border.all(color: const Color(0xFFE5E7EB)),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: loadError != null
                          ? Center(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Text(loadError!, textAlign: TextAlign.center),
                              ),
                            )
                          : notices.isEmpty
                              && schoolNotices.isEmpty
                              ? const Center(child: Text('등록된 공지가 없습니다.'))
                              : ListView.builder(
                                  itemCount: noticeTab == 0 ? notices.length : schoolNotices.length,
                                  itemBuilder: (_, i) {
                                    final n = (noticeTab == 0 ? notices : schoolNotices)[i];
                                    final selected = editingId == n['id'];
                                    return ListTile(
                                    selected: selected,
                                    title: Text((n['title'] ?? '').toString()),
                                    subtitle: Text(
                                      (n['updated_at'] ?? '').toString(),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    leading: n['is_pinned'] == true
                                        ? const Icon(Icons.push_pin, size: 18)
                                        : const SizedBox(width: 18),
                                    onTap: () => bind(n, setModalState),
                                    trailing: IconButton(
                                      tooltip: '삭제',
                                      icon: const Icon(Icons.delete_outline),
                                      onPressed: () async {
                                        final id = n['id'] as int;
                                        if (noticeTab == 0) {
                                          await _api.deleteNotice(id);
                                        } else {
                                          await _api.deleteSchoolNotice(id);
                                        }
                                        await refresh(setModalState);
                                        if (editingId == id) clearEditor(setModalState);
                                      },
                                    ),
                                    );
                                  },
                                ),
                    ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: titleCtrl,
                    decoration: const InputDecoration(labelText: '제목'),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: bodyCtrl,
                    minLines: 4,
                    maxLines: 8,
                    decoration: const InputDecoration(labelText: '내용'),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Checkbox(
                        value: pinned,
                        onChanged: (v) => setModalState(() => pinned = v ?? false),
                      ),
                      const Text('상단 고정'),
                      const SizedBox(width: 16),
                      Checkbox(
                        value: collapsed,
                        onChanged: (v) => setModalState(() => collapsed = v ?? false),
                      ),
                      const Text('접힘(기본)'),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('닫기')),
          StatefulBuilder(
            builder: (context, setActionState) {
              return ElevatedButton(
                onPressed: saving
                    ? null
                    : () async {
                        final title = titleCtrl.text.trim();
                        final body = bodyCtrl.text.trim();
                        if (title.isEmpty || body.isEmpty) return;
                        setActionState(() => saving = true);
                        try {
                          if (editingId == null) {
                            if (noticeTab == 0) {
                              await _api.createNotice({
                                'title': title,
                                'body': body,
                                'is_pinned': pinned,
                              });
                            } else if (selectedSchoolId != null) {
                              await _api.createSchoolNotice(selectedSchoolId!, {
                                'title': title,
                                'body': body,
                                'is_pinned': pinned,
                              });
                            }
                          } else {
                            if (noticeTab == 0) {
                              await _api.updateNotice(editingId!, {
                                'title': title,
                                'body': body,
                                'is_pinned': pinned,
                              });
                            } else {
                              await _api.updateSchoolNotice(editingId!, {
                                'title': title,
                                'body': body,
                                'is_pinned': pinned,
                              });
                            }
                          }
                          if (!ctx.mounted) return;
                          Navigator.pop(ctx);
                          if (mounted) _openNoticesEditor();
                        } finally {
                          if (context.mounted) {
                            setActionState(() => saving = false);
                          }
                        }
                      },
                child: Text(editingId == null ? '공지 등록' : '공지 저장'),
              );
            },
          ),
        ],
      ),
    );
    titleCtrl.dispose();
    bodyCtrl.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('관리자 대시보드')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('별도 URL(/admin)에서 학교/기숙사/매칭 일정을 관리하는 화면입니다.'),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: _openNoticesEditor,
                      icon: const Icon(Icons.campaign_outlined),
                      label: const Text('공지함 편집'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _nameCtrl,
                          decoration: const InputDecoration(labelText: '학교명 추가'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(onPressed: _addSchool, child: const Text('추가')),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Expanded(
                    child: ListView.builder(
                      itemCount: _schools.length,
                      itemBuilder: (_, i) {
                        final s = _schools[i];
                        final schoolId = s['id'] as int;
                        final collapsed = _collapsedSchoolIds.contains(schoolId);
                        return Card(
                          child: Column(
                            children: [
                              ListTile(
                                title: Text(
                                  (s['name'] ?? '').toString(),
                                  style: TextStyle(
                                    color: (s['is_hidden'] == true) ? Colors.grey : null,
                                  ),
                                ),
                                subtitle: Text(
                                  '매칭 상태: ${s['matching_phase']}'
                                  '${s['is_hidden'] == true ? ' (숨김)' : ''}',
                                ),
                                leading: IconButton(
                                  icon: Icon(collapsed ? Icons.expand_more : Icons.expand_less),
                                  onPressed: () {
                                    setState(() {
                                      if (collapsed) {
                                        _collapsedSchoolIds.remove(schoolId);
                                      } else {
                                        _collapsedSchoolIds.add(schoolId);
                                      }
                                    });
                                    _persistCollapsedState();
                                  },
                                ),
                                trailing: Switch(
                                  value: (s['matching_enabled'] ?? true) == true,
                                  onChanged: (v) async {
                                    await _api.toggleSchoolMatching(s['id'] as int, v);
                                    _load();
                                  },
                                ),
                              ),
                              if (!collapsed)
                                Padding(
                                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                                  child: Row(
                                    children: [
                                      TextButton(onPressed: () => _editDorms(s), child: const Text('기숙사/인실 편집')),
                                      TextButton(onPressed: () => _editSchedule(s), child: const Text('기간 편집')),
                                      TextButton(onPressed: () => _renameSchool(s), child: const Text('이름 변경')),
                                      TextButton(
                                        onPressed: () => _toggleSchoolHidden(s),
                                        child: Text(s['is_hidden'] == true ? '숨김 해제' : '숨기기'),
                                      ),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}


