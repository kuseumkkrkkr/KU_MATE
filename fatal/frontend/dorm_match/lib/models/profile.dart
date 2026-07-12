class Profile {
  String? uid;
  String userUid;
  String? persona;
  String name;
  String studentId;
  int birthYear;
  String college;
  String department;
  int dormDuration;
  int homeVisitCycle;
  int perfume;
  int indoorScentSensitivity;
  double alcoholTolerance;
  int alcoholFrequency;
  int drunkHabit;
  int gamingHoursPerWeek;
  int speakerUse;
  int exercise;
  int bedtime;
  int wakeTime;
  int sleepHabit;
  int sleepSensitivity;
  int alarmStrength;
  int sleepLight;
  int snoring;
  int showerDuration;
  int showerTime;
  int showerCycle;
  int cleaningCycle;
  double ventilation;
  int hairdryerInBathroom;
  int toiletPaperShare;
  int indoorEating;
  int smoking;
  int temperaturePref;
  int indoorCall;
  int bugHandling;
  int laundryCycle;
  int dryingRack;
  int fridgeUse;
  int studyInRoom;
  int noiseSensitivity;
  int desiredIntimacy;
  int mealTogether;
  int exerciseTogether;
  int friendInvite;
  // Legacy single hall field (kept for backward compat)
  String dormitoryHall;
  // New matching protocol fields
  String matchingPhase; // 'preliminary' | 'main'
  List<String> hopeHalls; // max 2 in preliminary
  String acceptedHall; // 1 in main phase
  int roomCapacity; // 2, 3, or 4
  List<int> preferredRoomTypeIds;
  int fixedRoomTypeId;
  List<int> interestRoomTypeIds;
  int fixedInterestRoomTypeId;
  int preChangeCount;
  int applyChangeCount;
  String preLastChangedAt;
  String applyLastChangedAt;
  List<String> nonNegotiableItems;
  List<int> nonNegotiableWeights;

  Profile({
    this.uid,
    this.userUid = '',
    this.persona,
    this.name = '',
    this.studentId = '',
    this.birthYear = 2005,
    this.college = '',
    this.department = '',
    this.dormDuration = 1,
    this.homeVisitCycle = 2,
    this.perfume = 0,
    this.indoorScentSensitivity = 3,
    this.alcoholTolerance = 2.5,
    this.alcoholFrequency = 2,
    this.drunkHabit = 0,
    this.gamingHoursPerWeek = 10,
    this.speakerUse = 0,
    this.exercise = 0,
    this.bedtime = 23,
    this.wakeTime = 8,
    this.sleepHabit = 0,
    this.sleepSensitivity = 3,
    this.alarmStrength = 3,
    this.sleepLight = 0,
    this.snoring = 0,
    this.showerDuration = 15,
    this.showerTime = 22,
    this.showerCycle = 2,
    this.cleaningCycle = 7,
    this.ventilation = 1.0,
    this.hairdryerInBathroom = 1,
    this.toiletPaperShare = 1,
    this.indoorEating = 0,
    this.smoking = 0,
    this.temperaturePref = 3,
    this.indoorCall = 0,
    this.bugHandling = 3,
    this.laundryCycle = 7,
    this.dryingRack = 1,
    this.fridgeUse = 1,
    this.studyInRoom = 0,
    this.noiseSensitivity = 3,
    this.desiredIntimacy = 3,
    this.mealTogether = 2,
    this.exerciseTogether = 1,
    this.friendInvite = 1,
    this.dormitoryHall = '',
    this.matchingPhase = 'preliminary',
    this.hopeHalls = const [],
    this.acceptedHall = '',
    this.roomCapacity = 2,
    this.preferredRoomTypeIds = const [],
    this.fixedRoomTypeId = 0,
    this.interestRoomTypeIds = const [],
    this.fixedInterestRoomTypeId = 0,
    this.preChangeCount = 0,
    this.applyChangeCount = 0,
    this.preLastChangedAt = '',
    this.applyLastChangedAt = '',
    this.nonNegotiableItems = const [],
    this.nonNegotiableWeights = const [],
  });

  factory Profile.fromJson(Map<String, dynamic> json) {
    return Profile(
      uid: json['uid'],
      userUid: json['user_uid'] ?? '',
      persona: json['persona'],
      name: json['name'] ?? '',
      studentId: json['student_id'] ?? '',
      birthYear: json['birth_year'] ?? 2005,
      college: json['college'] ?? '',
      department: json['department'] ?? '',
      dormDuration: json['dorm_duration'] ?? 1,
      homeVisitCycle: json['home_visit_cycle'] ?? 2,
      perfume: json['perfume'] ?? 0,
      indoorScentSensitivity: json['indoor_scent_sensitivity'] ?? 3,
      alcoholTolerance: (json['alcohol_tolerance'] ?? 2.5).toDouble(),
      alcoholFrequency: json['alcohol_frequency'] ?? 2,
      drunkHabit: json['drunk_habit'] ?? 0,
      gamingHoursPerWeek: json['gaming_hours_per_week'] ?? 10,
      speakerUse: json['speaker_use'] ?? 0,
      exercise: json['exercise'] ?? 0,
      bedtime: json['bedtime'] ?? 23,
      wakeTime: json['wake_time'] ?? 8,
      sleepHabit: json['sleep_habit'] ?? 0,
      sleepSensitivity: json['sleep_sensitivity'] ?? 3,
      alarmStrength: json['alarm_strength'] ?? 3,
      sleepLight: json['sleep_light'] ?? 0,
      snoring: json['snoring'] ?? 0,
      showerDuration: json['shower_duration'] ?? 15,
      showerTime: json['shower_time'] ?? 22,
      showerCycle: json['shower_cycle'] ?? 2,
      cleaningCycle: json['cleaning_cycle'] ?? 7,
      ventilation: (json['ventilation'] ?? 1.0).toDouble(),
      hairdryerInBathroom: json['hairdryer_in_bathroom'] ?? 1,
      toiletPaperShare: json['toilet_paper_share'] ?? 1,
      indoorEating: json['indoor_eating'] ?? 0,
      smoking: json['smoking'] ?? 0,
      temperaturePref: json['temperature_pref'] ?? 3,
      indoorCall: json['indoor_call'] ?? 0,
      bugHandling: json['bug_handling'] ?? 3,
      laundryCycle: json['laundry_cycle'] ?? 7,
      dryingRack: json['drying_rack'] ?? 1,
      fridgeUse: json['fridge_use'] ?? 1,
      studyInRoom: json['study_in_room'] ?? 0,
      noiseSensitivity: json['noise_sensitivity'] ?? 3,
      desiredIntimacy: json['desired_intimacy'] ?? 3,
      mealTogether: json['meal_together'] ?? 2,
      exerciseTogether: json['exercise_together'] ?? 1,
      friendInvite: json['friend_invite'] ?? 1,
      dormitoryHall: json['dormitory_hall'] ?? '',
      matchingPhase: json['matching_phase'] ?? 'preliminary',
      hopeHalls: (json['hope_halls'] as List<dynamic>?)?.cast<String>() ?? const [],
      acceptedHall: json['accepted_hall'] ?? '',
      roomCapacity: json['room_capacity'] ?? 2,
      preferredRoomTypeIds: (json['preferred_room_type_ids'] as List<dynamic>?)?.map((e) => e as int).toList() ?? const [],
      fixedRoomTypeId: json['fixed_room_type_id'] ?? 0,
      interestRoomTypeIds: (json['interest_room_type_ids'] as List<dynamic>?)?.map((e) => e as int).toList() ?? const [],
      fixedInterestRoomTypeId: json['fixed_interest_room_type_id'] ?? 0,
      preChangeCount: json['pre_change_count'] ?? 0,
      applyChangeCount: json['apply_change_count'] ?? 0,
      preLastChangedAt: json['pre_last_changed_at'] ?? '',
      applyLastChangedAt: json['apply_last_changed_at'] ?? '',
      nonNegotiableItems: (json['non_negotiable_items'] as List<dynamic>?)?.cast<String>() ?? const [],
      nonNegotiableWeights: (json['non_negotiable_weights'] as List<dynamic>?)?.cast<int>() ?? const [],
    );
  }

  Profile copy() {
    return Profile(
      uid: uid, userUid: userUid, persona: persona, name: name,
      studentId: studentId, birthYear: birthYear, college: college,
      department: department, dormDuration: dormDuration,
      homeVisitCycle: homeVisitCycle, perfume: perfume,
      indoorScentSensitivity: indoorScentSensitivity,
      alcoholTolerance: alcoholTolerance, alcoholFrequency: alcoholFrequency,
      drunkHabit: drunkHabit, gamingHoursPerWeek: gamingHoursPerWeek,
      speakerUse: speakerUse, exercise: exercise, bedtime: bedtime,
      wakeTime: wakeTime, sleepHabit: sleepHabit,
      sleepSensitivity: sleepSensitivity, alarmStrength: alarmStrength,
      sleepLight: sleepLight, snoring: snoring,
      showerDuration: showerDuration, showerTime: showerTime,
      showerCycle: showerCycle, cleaningCycle: cleaningCycle,
      ventilation: ventilation, hairdryerInBathroom: hairdryerInBathroom,
      toiletPaperShare: toiletPaperShare, indoorEating: indoorEating,
      smoking: smoking, temperaturePref: temperaturePref,
      indoorCall: indoorCall, bugHandling: bugHandling,
      laundryCycle: laundryCycle, dryingRack: dryingRack,
      fridgeUse: fridgeUse, studyInRoom: studyInRoom,
      noiseSensitivity: noiseSensitivity, desiredIntimacy: desiredIntimacy,
      mealTogether: mealTogether, exerciseTogether: exerciseTogether,
      friendInvite: friendInvite,
      dormitoryHall: dormitoryHall,
      matchingPhase: matchingPhase,
      hopeHalls: List<String>.from(hopeHalls),
      acceptedHall: acceptedHall,
      roomCapacity: roomCapacity,
      preferredRoomTypeIds: List<int>.from(preferredRoomTypeIds),
      fixedRoomTypeId: fixedRoomTypeId,
      interestRoomTypeIds: List<int>.from(interestRoomTypeIds),
      fixedInterestRoomTypeId: fixedInterestRoomTypeId,
      preChangeCount: preChangeCount,
      applyChangeCount: applyChangeCount,
      preLastChangedAt: preLastChangedAt,
      applyLastChangedAt: applyLastChangedAt,
      nonNegotiableItems: nonNegotiableItems,
      nonNegotiableWeights: nonNegotiableWeights,
    );
  }

  Map<String, dynamic> toJson() => {
        'birth_year': birthYear,
        'college': college,
        'department': department,
        'dorm_duration': dormDuration,
        'home_visit_cycle': homeVisitCycle,
        'perfume': perfume,
        'indoor_scent_sensitivity': indoorScentSensitivity,
        'alcohol_tolerance': alcoholTolerance,
        'alcohol_frequency': alcoholFrequency,
        'drunk_habit': drunkHabit,
        'gaming_hours_per_week': gamingHoursPerWeek,
        'speaker_use': speakerUse,
        'exercise': exercise,
        'bedtime': bedtime,
        'wake_time': wakeTime,
        'sleep_habit': sleepHabit,
        'sleep_sensitivity': sleepSensitivity,
        'alarm_strength': alarmStrength,
        'sleep_light': sleepLight,
        'snoring': snoring,
        'shower_duration': showerDuration,
        'shower_time': showerTime,
        'shower_cycle': showerCycle,
        'cleaning_cycle': cleaningCycle,
        'ventilation': ventilation,
        'hairdryer_in_bathroom': hairdryerInBathroom,
        'toilet_paper_share': toiletPaperShare,
        'indoor_eating': indoorEating,
        'smoking': smoking,
        'temperature_pref': temperaturePref,
        'indoor_call': indoorCall,
        'bug_handling': bugHandling,
        'laundry_cycle': laundryCycle,
        'drying_rack': dryingRack,
        'fridge_use': fridgeUse,
        'study_in_room': studyInRoom,
        'noise_sensitivity': noiseSensitivity,
        'desired_intimacy': desiredIntimacy,
        'meal_together': mealTogether,
        'exercise_together': exerciseTogether,
        'friend_invite': friendInvite,
        'dormitory_hall': dormitoryHall,
        'matching_phase': matchingPhase,
        'hope_halls': hopeHalls,
        'accepted_hall': acceptedHall,
        'room_capacity': roomCapacity,
        'preferred_room_type_ids': preferredRoomTypeIds,
        'fixed_room_type_id': fixedRoomTypeId,
        'interest_room_type_ids': interestRoomTypeIds,
        'fixed_interest_room_type_id': fixedInterestRoomTypeId,
        'pre_change_count': preChangeCount,
        'apply_change_count': applyChangeCount,
        'pre_last_changed_at': preLastChangedAt,
        'apply_last_changed_at': applyLastChangedAt,
        'non_negotiable_items': nonNegotiableItems,
        'non_negotiable_weights': nonNegotiableWeights,
      };
}
