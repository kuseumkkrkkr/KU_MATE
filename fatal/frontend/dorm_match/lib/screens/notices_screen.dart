import 'package:flutter/material.dart';

import '../services/api_service.dart';

class NoticesScreen extends StatefulWidget {
  const NoticesScreen({super.key});

  @override
  State<NoticesScreen> createState() => _NoticesScreenState();
}

class _NoticesScreenState extends State<NoticesScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _notices = const [];
  Set<int> _collapsedIds = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final notices = await _api.getNotices(limit: 100);
      if (!mounted) return;
      setState(() {
        _notices = notices;
        _collapsedIds = {
          for (var n in notices)
            if (n['is_collapsed'] == true) n['id'] as int
        };
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatDate(Map<String, dynamic> notice) {
    final raw = (notice['updated_at'] ?? notice['created_at'] ?? '').toString();
    if (raw.length >= 10) return raw.substring(0, 10);
    return raw;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('공지사항')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        ElevatedButton(onPressed: _load, child: const Text('다시 시도')),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _notices.isEmpty
                      ? ListView(
                          children: const [
                            SizedBox(height: 220),
                            Center(child: Text('등록된 공지가 없습니다.')),
                          ],
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(20),
                          itemCount: _notices.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 12),
                          itemBuilder: (ctx, i) {
                            final n = _notices[i];
                            final id = n['id'] as int?;
                            final isCollapsed = id != null && _collapsedIds.contains(id);
                            final body = (n['body'] ?? '').toString();
                            return Container(
                              padding: const EdgeInsets.all(18),
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
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Expanded(
                                        child: GestureDetector(
                                          onTap: () {
                                            if (id != null) {
                                              setState(() {
                                                if (isCollapsed) {
                                                  _collapsedIds.remove(id);
                                                } else {
                                                  _collapsedIds.add(id);
                                                }
                                              });
                                            }
                                          },
                                          child: Row(children: [
                                            Icon(
                                              isCollapsed ? Icons.expand_more : Icons.expand_less,
                                              size: 20,
                                              color: Colors.grey.shade600,
                                            ),
                                            const SizedBox(width: 4),
                                            Expanded(
                                              child: Text(
                                                (n['title'] ?? '').toString(),
                                                style: const TextStyle(
                                                  fontSize: 15,
                                                  fontWeight: FontWeight.w700,
                                                ),
                                              ),
                                            ),
                                          ]),
                                        ),
                                      ),
                                      Text(
                                        _formatDate(n),
                                        style: TextStyle(
                                          fontSize: 12,
                                          color: Colors.grey.shade500,
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (!isCollapsed) ...[
                                    const SizedBox(height: 10),
                                    Text(
                                      body,
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: Colors.grey.shade700,
                                        height: 1.4,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
