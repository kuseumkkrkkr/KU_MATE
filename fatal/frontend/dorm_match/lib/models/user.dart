class User {
  String userUid;
  String loginId;
  String studentId;
  int birthYear;
  String name;
  String schoolName;
  String college;
  String department;
  String regionName;
  String gender;
  bool isEnrolled;
  bool hasActiveLifeRoom;
  String? lifeRoomUid;

  User({
    required this.userUid,
    this.loginId = '',
    this.studentId = '',
    this.birthYear = 2005,
    required this.name,
    this.schoolName = '',
    this.college = '',
    this.department = '',
    this.regionName = '',
    this.gender = '',
    this.isEnrolled = true,
    this.hasActiveLifeRoom = false,
    this.lifeRoomUid,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userUid: json['user_uid'] ?? json['uid'] ?? '',
      loginId: json['login_id'] ?? '',
      studentId: json['student_id'] ?? '',
      birthYear: json['birth_year'] ?? 2005,
      name: json['name'] ?? '',
      schoolName: json['school_name'] ?? '',
      college: json['college'] ?? '',
      department: json['department'] ?? '',
      regionName: json['region_name'] ?? '',
      gender: json['gender'] ?? '',
      isEnrolled: json['is_enrolled'] == 1 || json['is_enrolled'] == true,
      hasActiveLifeRoom: json['has_active_life_room'] == true,
      lifeRoomUid: json['life_room_uid'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_uid': userUid,
      'login_id': loginId,
      'student_id': studentId,
      'birth_year': birthYear,
      'name': name,
      'school_name': schoolName,
      'college': college,
      'department': department,
      'region_name': regionName,
      'gender': gender,
      'is_enrolled': isEnrolled,
      'has_active_life_room': hasActiveLifeRoom,
      'life_room_uid': lifeRoomUid,
    };
  }
}
