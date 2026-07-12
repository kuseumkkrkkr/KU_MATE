import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class ApiService {
  static final ApiService _singleton = ApiService._internal();
  factory ApiService() => _singleton;
  ApiService._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: defaultTargetPlatform == TargetPlatform.android
            ? 'http://10.0.2.2:5000/api'
            : 'http://localhost:5000/api',
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 60),
        headers: {'Content-Type': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioException e, handler) {
          if (e.response?.statusCode == 401) {
            clearToken();
          }
          handler.next(e);
        },
      ),
    );
  }

  late final Dio _dio;

  Future<String?> getToken() async {
    final sp = await SharedPreferences.getInstance();
    return sp.getString('jwt_token');
  }

  Future<void> setToken(String token) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setString('jwt_token', token);
  }

  Future<void> clearToken() async {
    final sp = await SharedPreferences.getInstance();
    await sp.remove('jwt_token');
  }

  Future<Map<String, dynamic>> get(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    try {
      final res = await _dio.get(path, queryParameters: query);
      return res.data is Map ? res.data : {'data': res.data};
    } on DioException catch (e) {
      final msg = _extractError(e);
      throw ApiException(msg, statusCode: e.response?.statusCode);
    }
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final res = await _dio.post(path, data: data);
      return res.data is Map ? res.data : {'data': res.data};
    } on DioException catch (e) {
      final msg = _extractError(e);
      throw ApiException(msg, statusCode: e.response?.statusCode);
    }
  }

  Future<Map<String, dynamic>> patch(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final res = await _dio.patch(path, data: data);
      return res.data is Map ? res.data : {'data': res.data};
    } on DioException catch (e) {
      final msg = _extractError(e);
      throw ApiException(msg, statusCode: e.response?.statusCode);
    }
  }

  Future<Map<String, dynamic>> delete(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final res = await _dio.delete(path, data: data);
      return res.data is Map ? res.data : {'data': res.data};
    } on DioException catch (e) {
      final msg = _extractError(e);
      throw ApiException(msg, statusCode: e.response?.statusCode);
    }
  }

  Future<Map<String, dynamic>> put(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final res = await _dio.put(path, data: data);
      return res.data is Map ? res.data : {'data': res.data};
    } on DioException catch (e) {
      final msg = _extractError(e);
      throw ApiException(msg, statusCode: e.response?.statusCode);
    }
  }

  String _extractError(DioException e) {
    if (e.response?.data != null && e.response!.data is Map) {
      return e.response!.data['error']?.toString() ?? e.message ?? '요청 실패';
    }
    return e.message ?? '네트워크 오류';
  }

  // ── Auth ──
  Future<Map<String, dynamic>> register(Map<String, dynamic> body) =>
      post('/auth/register', data: body);
  Future<Map<String, dynamic>> login(Map<String, dynamic> body) =>
      post('/auth/login', data: body);
  Future<Map<String, dynamic>> getMe() => get('/me');

  // ── Profile ──
  Future<Map<String, dynamic>> getProfile() => get('/profile');
  Future<Map<String, dynamic>> saveProfile(Map<String, dynamic> body) =>
      post('/profile', data: body);

  // ── Persona ──
  Future<Map<String, dynamic>> getPersona() => get('/persona');
  Future<Map<String, dynamic>> getSchools({bool includeHidden = false}) =>
      get('/schools', query: includeHidden ? {'include_hidden': '1'} : null);
  Future<List<Map<String, dynamic>>> getNotices({int limit = 50}) async {
    final res = await get('/notices', query: {'limit': limit});
    final raw = res['notices'];
    if (raw is List) {
      return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<List<Map<String, dynamic>>> getAdminNotices() async {
    final res = await get('/admin/notices');
    final raw = res['notices'];
    if (raw is List) {
      return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> createNotice(Map<String, dynamic> body) =>
      post('/admin/notices', data: body);
  Future<Map<String, dynamic>> updateNotice(
    int noticeId,
    Map<String, dynamic> body,
  ) => put('/admin/notices/$noticeId', data: body);
  Future<Map<String, dynamic>> deleteNotice(int noticeId) =>
      delete('/admin/notices/$noticeId');
  Future<Map<String, dynamic>> createSchool(Map<String, dynamic> body) =>
      post('/admin/schools', data: body);
  Future<Map<String, dynamic>> updateSchoolDorms(
    int schoolId,
    List<Map<String, dynamic>> dorms,
  ) => put('/admin/schools/$schoolId/dorms', data: {'dorms': dorms});
  Future<Map<String, dynamic>> updateSchoolSchedule(
    int schoolId,
    Map<String, dynamic> body,
  ) => patch('/admin/schools/$schoolId/schedule', data: body);
  Future<Map<String, dynamic>> toggleSchoolMatching(
    int schoolId,
    bool isOpen,
  ) => patch('/admin/schools/$schoolId/matching', data: {'is_open': isOpen});
  Future<Map<String, dynamic>> getMatchingOptions() => get('/matching/options');
  Future<Map<String, dynamic>> saveMatchingPreferences(
    List<int> roomTypeIds, {
    bool? confirmChange,
  }) => post(
    '/matching/preferences',
    data: {
      'selected_room_type_ids': roomTypeIds,
      if (confirmChange != null) 'confirm_change': confirmChange,
    },
  );
  Future<Map<String, dynamic>> getInterestRooms() =>
      get('/profile/interest-rooms');
  Future<Map<String, dynamic>> saveInterestRooms(
    List<int> roomTypeIds, {
    bool? confirmChange,
  }) => put(
    '/profile/interest-rooms',
    data: {
      'interest_room_type_ids': roomTypeIds,
      if (confirmChange != null) 'confirm_change': confirmChange,
    },
  );
  Future<List<Map<String, dynamic>>> getSchoolNotices(int schoolId) async {
    final res = await get('/admin/schools/$schoolId/notices');
    final raw = res['notices'];
    if (raw is List) {
      return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> createSchoolNotice(
    int schoolId,
    Map<String, dynamic> body,
  ) => post('/admin/schools/$schoolId/notices', data: body);
  Future<Map<String, dynamic>> updateSchoolNotice(
    int noticeId,
    Map<String, dynamic> body,
  ) => put('/admin/school-notices/$noticeId', data: body);
  Future<Map<String, dynamic>> deleteSchoolNotice(int noticeId) =>
      delete('/admin/school-notices/$noticeId');
  Future<Map<String, dynamic>> updateDormRoomTypes(
    int dormId,
    List<Map<String, dynamic>> roomTypes,
  ) => put('/admin/dorms/$dormId/room-types', data: {'room_types': roomTypes});

  // ── Legacy Matches (kept for backward compat) ──
  Future<Map<String, dynamic>> getTopMatches() => get('/match/top');
  Future<List<dynamic>> getPairs() async {
    final res = await get('/match/pairs');
    return res['pairs'] ?? [];
  }

  // ── Match Requests (legacy) ──
  Future<Map<String, dynamic>> createMatchRequest(String targetUid) =>
      post('/match/request', data: {'to_user': targetUid});
  Future<Map<String, dynamic>> respondMatchRequest(
    String requestId,
    String status,
  ) => patch('/match/request/$requestId', data: {'status': status});
  Future<Map<String, dynamic>> getMatchRequests({String direction = 'in'}) =>
      get('/match/requests', query: {'direction': direction});

  // ── Pool & Session (new matching protocol) ──
  /// Refresh match pool. Returns up to 5 candidates with tier distribution.
  Future<Map<String, dynamic>> refreshPool() => post('/match/pool/refresh');

  /// Get current pool candidates.
  Future<Map<String, dynamic>> getPool() => get('/match/pool');

  /// Enter a match session with selected candidate(s).
  Future<Map<String, dynamic>> enterSession(List<String> candidateUids) =>
      post('/match/session/enter', data: {'candidates': candidateUids});

  /// Get active sessions for current user.
  Future<List<dynamic>> getActiveSessions() async {
    final res = await get('/match/session/active');
    return res['sessions'] ?? [];
  }

  Future<List<dynamic>> getSessionHistory() async {
    final res = await get('/match/session/history');
    return res['sessions'] ?? [];
  }

  Future<Map<String, dynamic>> deleteSessionHistory(String sessionId) =>
      delete('/match/session/history/$sessionId');

  Future<Map<String, dynamic>> getPublicProfile(String userUid) =>
      get('/profile/public/$userUid');

  /// Confirm match in a session (auto-closes other threads).
  Future<Map<String, dynamic>> confirmMatch(String sessionId) => post(
    '/match/confirm',
    data: {'session_id': sessionId, 'room_confirm_mode': 'delegate'},
  );
  Future<Map<String, dynamic>> confirmMatchV2(String sessionId) =>
      post('/match/confirm', data: {'session_id': sessionId});

  /// Cancel / leave a session.
  Future<Map<String, dynamic>> cancelSession(String sessionId) =>
      post('/match/session/$sessionId/cancel');
  Future<Map<String, dynamic>> rematch(String sessionId) =>
      post('/match/rematch', data: {'session_id': sessionId});

  /// Get cooldown status (rematch restriction).
  Future<Map<String, dynamic>> getCooldownStatus() => get('/match/cooldown');
  Future<Map<String, dynamic>> getCurrentLifeRoom() =>
      get('/life-room/current');
  Future<Map<String, dynamic>> addLifeRoomTodo(
    String lifeRoomUid,
    Map<String, dynamic> body,
  ) => post('/life-room/$lifeRoomUid/todos', data: body);
  Future<Map<String, dynamic>> toggleLifeRoomTodo(
    String lifeRoomUid,
    String todoUid,
  ) => post('/life-room/$lifeRoomUid/todos/$todoUid/toggle');
  Future<Map<String, dynamic>> addLifeRoomEvent(
    String lifeRoomUid,
    Map<String, dynamic> body,
  ) => post('/life-room/$lifeRoomUid/events', data: body);
  Future<Map<String, dynamic>> updateLifeRoomRule(
    String lifeRoomUid,
    String body,
  ) => post('/life-room/$lifeRoomUid/rules', data: {'body': body});
  Future<Map<String, dynamic>> updateLifeRoomPresence(
    String lifeRoomUid,
    String status,
  ) => post('/life-room/$lifeRoomUid/presence', data: {'status': status});
  Future<Map<String, dynamic>> createLifeRoomPost(
    String lifeRoomUid,
    Map<String, dynamic> body,
  ) => post('/life-room/$lifeRoomUid/posts', data: body);
  Future<Map<String, dynamic>> updateLifeRoomFillPolicy(
    String lifeRoomUid,
    String strategy, {
    String period = 'main',
  }) => post(
    '/life-room/$lifeRoomUid/fill-policy',
    data: {'period': period, 'strategy': strategy},
  );

  Future<Map<String, dynamic>> getLifeRoomStatus(String lifeRoomUid) =>
      get('/life-room/$lifeRoomUid/status');

  Future<Map<String, dynamic>> getLifeRoomMatchHistory(
    String lifeRoomUid,
  ) async {
    final res = await get('/life-room/$lifeRoomUid/match-history');
    return res;
  }

  Future<Map<String, dynamic>> createLifeRoomMatchHistory(
    String lifeRoomUid,
    Map<String, dynamic> body,
  ) => post('/life-room/$lifeRoomUid/match-history', data: body);

  Future<Map<String, dynamic>> deleteLifeRoomMatchHistory(
    String lifeRoomUid,
    String historyUid,
  ) => delete('/life-room/$lifeRoomUid/match-history/$historyUid');

  Future<List<Map<String, dynamic>>> getLifeRoomRecruitSessions(
    String lifeRoomUid,
  ) async {
    final res = await get('/life-room/$lifeRoomUid/recruit-sessions');
    final raw = res['sessions'];
    if (raw is List) {
      return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> createRecruitSession(
    String lifeRoomUid,
  ) => post('/life-room/$lifeRoomUid/recruit-sessions');

  Future<Map<String, dynamic>> updateRecruitSession(
    String lifeRoomUid,
    String sessionUid,
    String status,
  ) => patch(
    '/life-room/$lifeRoomUid/recruit-sessions/$sessionUid',
    data: {'status': status},
  );

  Future<Map<String, dynamic>> confirmLifeRoomHall(
    String lifeRoomUid,
    int roomTypeId,
  ) => post(
    '/life-room/$lifeRoomUid/hall-confirm',
    data: {'room_type_id': roomTypeId},
  );

  Future<Map<String, dynamic>> sendLifeRoomGroupMessage(
    String lifeRoomUid,
    String content,
  ) => post(
    '/life-room/$lifeRoomUid/group-chat',
    data: {'content': content},
  );

  Future<List<Map<String, dynamic>>> getLifeRoomGroupChat(
    String lifeRoomUid,
  ) async {
    final res = await get('/life-room/$lifeRoomUid/group-chat');
    final raw = res['messages'];
    if (raw is List) {
      return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> getFillSurvey(String lifeRoomUid) =>
      get('/life-room/$lifeRoomUid/fill-survey');

  Future<Map<String, dynamic>> closeLifeRoomPeriod(String lifeRoomUid) =>
      post('/life-room/$lifeRoomUid/auto-close');

  Future<Map<String, dynamic>> updateSchool(
    int schoolId,
    Map<String, dynamic> body,
  ) => put('/admin/schools/$schoolId', data: body);

  String get currentUserId {
    try {
      final parts = _dio.options.headers['Authorization']?.toString().split('.');
      if (parts != null && parts.length == 3) {
        final payload = jsonDecode(utf8.decode(base64Decode(base64Url.normalize(parts[1]))));
        return payload['sub']?.toString() ?? '';
      }
    } catch (_) {}
    return '';
  }

  // ── Chat Threads (new thread-based chat) ──
  /// Send message via thread (replaces direct receiver chat).
  Future<Map<String, dynamic>> sendThreadMessage(
    String threadId,
    String text,
  ) => post(
    '/chat/threads/$threadId/messages',
    data: {'content': text, 'type': 'text'},
  );

  /// Get messages in a thread.
  Future<List<dynamic>> getThreadMessages(
    String threadId, {
    int limit = 50,
    String? beforeCreatedAt,
    String? beforeUid,
  }) async {
    final query = <String, dynamic>{'limit': limit};
    if (beforeCreatedAt != null && beforeCreatedAt.isNotEmpty) {
      query['before_created_at'] = beforeCreatedAt;
    }
    if (beforeUid != null && beforeUid.isNotEmpty) {
      query['before_uid'] = beforeUid;
    }
    final res = await get('/chat/threads/$threadId/messages', query: query);
    if (res['data'] is List) return List<dynamic>.from(res['data']);
    if (res['messages'] is List) return List<dynamic>.from(res['messages']);
    return [];
  }

  /// Mark thread as read.
  Future<Map<String, dynamic>> markThreadRead(String threadId) =>
      post('/chat/threads/$threadId/read');
  Future<Map<String, dynamic>> leaveThread(String threadId, String reason) =>
      post('/chat/threads/$threadId/leave', data: {'reason': reason.trim()});
  Future<Map<String, dynamic>> getThreadMeta(String threadId) =>
      get('/chat/threads/$threadId/meta');
  Future<Map<String, dynamic>> openThreadSurvey(String threadId) =>
      post('/chat/threads/$threadId/survey/open');
  Future<Map<String, dynamic>> getOpenedSurveyProfile(String threadId) =>
      get('/chat/threads/$threadId/survey/opened-profile');
  Future<Map<String, dynamic>> decideThreadMatch(
    String threadId,
    String action, {
    String? reason,
  }) => post(
    '/chat/threads/$threadId/match-decision',
    data: {
      'action': action,
      if (reason != null && reason.trim().isNotEmpty) 'reason': reason.trim(),
    },
  );

  /// Get all active threads for current user.
  Future<List<dynamic>> getThreads() async {
    final res = await get('/chat/threads');
    return res['threads'] ?? [];
  }

  /// SSE chat stream with event-type routing support.
  /// Yields maps containing 'event' and 'payload' keys.
  Stream<Map<String, dynamic>> chatStream() async* {
    final token = await getToken();
    if (token == null) throw ApiException('Not authenticated');
    final client = Dio(
      BaseOptions(
        baseUrl: _dio.options.baseUrl,
        headers: {
          'Authorization': 'Bearer $token',
          'Accept': 'text/event-stream',
        },
        responseType: ResponseType.stream,
      ),
    );
    try {
      final response = await client.get('/chat/stream');
      final stream = response.data.stream as Stream<List<int>>;
      String? currentEvent;
      var buffer = '';
      await for (final chunk in stream.transform(utf8.decoder)) {
        buffer += chunk;
        final lines = buffer.split('\n');
        buffer = lines.removeLast();
        for (final line in lines) {
          final trimmed = line.trim();
          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.substring(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            final payload = trimmed.substring(6).trim();
            if (payload.isEmpty) continue;
            try {
              final json = jsonDecode(payload);
              yield {
                'event': currentEvent ?? 'message',
                'payload': json is Map<String, dynamic> ? json : {'data': json},
              };
            } catch (_) {}
          } else if (trimmed.isEmpty) {
            currentEvent = null;
          }
        }
      }
    } on DioException catch (e) {
      throw ApiException(_extractError(e), statusCode: e.response?.statusCode);
    }
  }

  Future<Map<String, dynamic>> ackMessage(String messageUid) =>
      post('/chat/ack', data: {'message_uid': messageUid});

  Future<List<dynamic>> getWebLocalThreadMessages(String threadId) async {
    final res = await get('/chat/local/threads/$threadId/messages');
    if (res['messages'] is List) return List<dynamic>.from(res['messages']);
    return [];
  }

  Future<Map<String, dynamic>> putWebLocalThreadMessages(
    String threadId,
    List<Map<String, dynamic>> messages,
  ) => put(
    '/chat/local/threads/$threadId/messages',
    data: {'messages': messages},
  );

  Future<Map<String, dynamic>> deleteWebLocalThreadMessages(String threadId) =>
      delete('/chat/local/threads/$threadId/messages');

  // ── Reviews ──
  Future<Map<String, dynamic>> submitReview(
    String revieweeUid,
    int rating,
    String text,
  ) => post(
    '/reviews',
    data: {'reviewee': revieweeUid, 'rating': rating, 'body': text},
  );
  Future<Map<String, dynamic>> getReviews(String revieweeUid) =>
      get('/reviews/$revieweeUid');
}
