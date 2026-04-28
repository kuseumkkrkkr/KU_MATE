"""PyQt UI entry point: checklist input, bulk generator, matcher with detail view."""

from __future__ import annotations

import sys
from functools import partial
from typing import Dict, Any, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

import db
from checklist import RoommateProfile
import generator
import matcher


# ---------- Checklist input tab ----------
class ChecklistTab(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.field_widgets: Dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form_container = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_container)
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        form_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # Text fields
        self.field_widgets["name"] = QtWidgets.QLineEdit()
        self.field_widgets["student_id"] = QtWidgets.QLineEdit()
        form_layout.addRow("이름*", self.field_widgets["name"])
        form_layout.addRow("학번*", self.field_widgets["student_id"])

        # Persona / college / department
        self.persona_combo = QtWidgets.QComboBox()
        self.persona_combo.addItem("혼합(랜덤)", "")
        for p in generator.PERSONAS.keys():
            self.persona_combo.addItem(p, p)
        form_layout.addRow("유형", self.persona_combo)

        self.college_combo = QtWidgets.QComboBox()
        self.college_combo.addItems(generator.COLLEGES)
        self.college_combo.currentTextChanged.connect(self._update_departments)
        self.department_combo = QtWidgets.QComboBox()
        self._update_departments(generator.COLLEGES[0])
        form_layout.addRow("단과대", self.college_combo)
        form_layout.addRow("학과", self.department_combo)

        # helpers
        def add_spin(name, label, minimum, maximum, step=1, default=None):
            spin = QtWidgets.QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            if default is not None:
                spin.setValue(default)
            self.field_widgets[name] = spin
            form_layout.addRow(label, spin)

        def add_dspin(name, label, minimum, maximum, step=0.5, default=None):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setDecimals(1)
            if default is not None:
                spin.setValue(default)
            self.field_widgets[name] = spin
            form_layout.addRow(label, spin)

        def add_check(name, label, default=False):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(default)
            self.field_widgets[name] = cb
            form_layout.addRow(label, cb)

        # Basic info
        add_spin("birth_year", "출생연도", 1990, 2010, default=2000)
        add_spin("dorm_duration", "기숙사 거주학기", 1, 8, default=1)

        # 생활 습관
        add_spin("home_visit_cycle", "귀가 주기(1~4)", 1, 4, default=2)
        add_check("perfume", "향수 사용", False)
        add_spin("indoor_scent_sensitivity", "향 민감도(1~5)", 1, 5, default=3)
        add_dspin("alcohol_tolerance", "주량(1.0~5.0)", 1.0, 5.0, step=0.5, default=2.5)
        add_spin("alcohol_frequency", "음주 빈도(1~5)", 1, 5, default=2)
        add_check("drunk_habit", "주사 있음", False)
        add_spin("gaming_hours_per_week", "게임/스크린(시간)", 0, 40, step=5, default=10)
        add_check("speaker_use", "스피커 사용", False)
        add_check("exercise", "운동함", False)

        # 수면
        add_spin("bedtime", "취침 시각(0~23)", 0, 23, default=24)
        add_spin("wake_time", "기상 시각(0~23)", 0, 23, default=8)
        add_check("sleep_habit", "잠버릇 있음", False)
        add_spin("sleep_sensitivity", "수면 예민도(1~5)", 1, 5, default=3)
        add_spin("alarm_strength", "알람 세기(1~5)", 1, 5, default=3)
        add_check("sleep_light", "불 켜고 잠", False)
        add_check("snoring", "코골이", False)

        # 위생/욕실
        add_spin("shower_duration", "샤워 시간(5~30)", 5, 30, step=5, default=10)
        add_spin("shower_time", "샤워 시각(0~23)", 0, 23, default=22)
        add_spin("shower_cycle", "샤워 주기(1~5)", 1, 5, default=1)
        add_spin("cleaning_cycle", "청소 주기(1~30)", 1, 30, default=7)
        add_dspin("ventilation", "환기(0.5~5)", 0.5, 5.0, step=0.5, default=1.0)
        add_check("hairdryer_in_bathroom", "드라이기 비치", True)
        add_check("toilet_paper_share", "휴지 공유", True)
        add_check("indoor_eating", "방안 식사", False)
        add_check("smoking", "흡연", False)

        # 생활 편의
        add_spin("temperature_pref", "온도 선호(1~5)", 1, 5, default=3)
        add_check("indoor_call", "방안 통화", False)
        add_spin("bug_handling", "벌레 대응(1~5)", 1, 5, default=3)
        add_spin("laundry_cycle", "빨래 주기(1~14)", 1, 14, default=7)
        add_check("drying_rack", "건조대 사용", True)
        add_check("fridge_use", "냉장고 사용", True)
        add_check("study_in_room", "방공부", False)
        add_spin("noise_sensitivity", "소음 민감도(1~5)", 1, 5, default=3)

        # 교류
        add_spin("desired_intimacy", "친밀도 선호(1~5)", 1, 5, default=3)
        add_spin("meal_together", "밥 같이(1~3)", 1, 3, default=2)
        add_spin("exercise_together", "운동 같이(1~3)", 1, 3, default=1)
        add_spin("friend_invite", "친구 방문(1~5)", 1, 5, default=3)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        self.save_btn = QtWidgets.QPushButton("저장 (SQL)")
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        self.status = QtWidgets.QLabel("모든 항목을 입력해 주세요.")
        layout.addWidget(self.status)

    def _update_departments(self, college: str):
        self.department_combo.clear()
        self.department_combo.addItems(generator.DEPARTMENTS.get(college, []))

    def _collect_profile(self) -> Optional[RoommateProfile]:
        name = self.field_widgets["name"].text().strip()
        sid = self.field_widgets["student_id"].text().strip()
        if not name or not sid:
            QtWidgets.QMessageBox.warning(self, "입력 필요", "이름과 학번은 필수입니다.")
            return None
        data = {}
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QtWidgets.QLineEdit):
                data[key] = widget.text().strip()
            elif isinstance(widget, QtWidgets.QCheckBox):
                data[key] = 1 if widget.isChecked() else 0
            elif isinstance(widget, QtWidgets.QSpinBox):
                data[key] = int(widget.value())
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                data[key] = float(widget.value())
        data["college"] = self.college_combo.currentText()
        data["department"] = self.department_combo.currentText()
        persona = self.persona_combo.currentData() or None
        prof = RoommateProfile(**data, persona=persona)
        return prof

    def _save(self):
        profile = self._collect_profile()
        if profile is None:
            return
        db.save_profiles([profile])
        self.status.setText(f"저장 완료: {profile.name} / {profile.student_id}")
        self.parentWidget().parent().refresh_shared_data()


# ---------- Bulk generator tab ----------
class GeneratorTab(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)

        self.count_spin = QtWidgets.QSpinBox()
        self.count_spin.setRange(1, 500)
        self.count_spin.setValue(50)
        layout.addRow("몇 명 생성", self.count_spin)

        self.persona_combo = QtWidgets.QComboBox()
        self.persona_combo.addItem("혼합(랜덤)", "")
        for p in generator.PERSONAS.keys():
            self.persona_combo.addItem(p, p)
        layout.addRow("유형", self.persona_combo)

        self.seed_edit = QtWidgets.QLineEdit()
        self.seed_edit.setPlaceholderText("옵션: 숫자 시드")
        layout.addRow("Seed", self.seed_edit)

        self.run_btn = QtWidgets.QPushButton("생성 + SQL 저장")
        self.run_btn.clicked.connect(self._run)
        layout.addRow(self.run_btn)

        self.status = QtWidgets.QLabel("대량 생성으로 현실감 있는 분포를 만듭니다.")
        layout.addRow(self.status)

    def _run(self):
        persona = self.persona_combo.currentData() or None
        seed_text = self.seed_edit.text().strip()
        seed = int(seed_text) if seed_text else None
        n = int(self.count_spin.value())
        profiles = generator.generate_and_store(n, persona=persona, seed=seed)
        self.status.setText(f"{len(profiles)}명 저장 완료 (유형: {persona or '혼합'})")
        self.parentWidget().parent().refresh_shared_data()


# ---------- Matcher tab ----------
FIELD_META = [
    ("home_visit_cycle", "귀가 주기", "int"),
    ("perfume", "향수", "bool"),
    ("indoor_scent_sensitivity", "향 민감도", "int"),
    ("alcohol_tolerance", "주량", "float"),
    ("alcohol_frequency", "음주 빈도", "int"),
    ("drunk_habit", "주사", "bool"),
    ("gaming_hours_per_week", "게임 시간", "int"),
    ("speaker_use", "스피커 사용", "bool"),
    ("exercise", "운동", "bool"),
    ("bedtime", "취침 시각", "int"),
    ("wake_time", "기상 시각", "int"),
    ("sleep_habit", "잠버릇", "bool"),
    ("sleep_sensitivity", "수면 예민", "int"),
    ("alarm_strength", "알람 세기", "int"),
    ("sleep_light", "불 켜고 잠", "bool"),
    ("snoring", "코골이", "bool"),
    ("shower_duration", "샤워 시간", "int"),
    ("shower_time", "샤워 시각", "int"),
    ("shower_cycle", "샤워 주기", "int"),
    ("cleaning_cycle", "청소 주기", "int"),
    ("ventilation", "환기", "float"),
    ("hairdryer_in_bathroom", "드라이기 비치", "bool"),
    ("toilet_paper_share", "휴지 공유", "bool"),
    ("indoor_eating", "방 식사", "bool"),
    ("smoking", "흡연", "bool"),
    ("temperature_pref", "온도 선호", "int"),
    ("indoor_call", "방 통화", "bool"),
    ("bug_handling", "벌레 대응", "int"),
    ("laundry_cycle", "빨래 주기", "int"),
    ("drying_rack", "건조대", "bool"),
    ("fridge_use", "냉장고", "bool"),
    ("study_in_room", "방 공부", "bool"),
    ("noise_sensitivity", "소음 민감", "int"),
    ("desired_intimacy", "친밀도", "int"),
    ("meal_together", "밥 함께", "int"),
    ("exercise_together", "운동 함께", "int"),
    ("friend_invite", "친구 방문", "int"),
]


class DetailDialog(QtWidgets.QDialog):
    def __init__(self, a: RoommateProfile, b: RoommateProfile, result: matcher.MatchResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{a.name} ↔ {b.name} 상세 비교")
        self.resize(650, 720)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel(f"총점 {result.score:.1f} / 100   (거리 {result.distance})"))
        table = QtWidgets.QTableWidget(len(FIELD_META), 4)
        table.setHorizontalHeaderLabels(["항목", a.name, b.name, "차이(상대-기준)"])
        for row, (attr, label, ftype) in enumerate(FIELD_META):
            va = getattr(a, attr)
            vb = getattr(b, attr)
            diff = None
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                diff = vb - va

            def fmt(val):
                if ftype == "bool":
                    return "O" if val else "X"
                if ftype == "float":
                    return f"{val:.1f}"
                return str(val)

            table.setItem(row, 0, QtWidgets.QTableWidgetItem(label))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(fmt(va)))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(fmt(vb)))

            diff_item = QtWidgets.QTableWidgetItem("")
            if diff is not None and diff != 0:
                sign = "+" if diff > 0 else "-"
                diff_item.setText(f"{sign}{abs(diff):.1f}" if ftype == "float" else f"{sign}{abs(diff)}")
                color = QtGui.QColor(0, 150, 0) if diff > 0 else QtGui.QColor(200, 0, 0)
                diff_item.setForeground(QtGui.QBrush(color))
            table.setItem(row, 3, diff_item)

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        close_btn = QtWidgets.QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class MatcherTab(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.profiles: List[RoommateProfile] = []
        self.last_results: List[matcher.MatchResult] = []
        self._build_ui()
        self.reload()

    def _build_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)

        top_bar = QtWidgets.QHBoxLayout()
        self.target_combo = QtWidgets.QComboBox()
        self.reload_btn = QtWidgets.QPushButton("새로고침")
        self.reload_btn.clicked.connect(self.reload)
        top_bar.addWidget(QtWidgets.QLabel("대상 선택"))
        top_bar.addWidget(self.target_combo)
        top_bar.addWidget(self.reload_btn)
        vbox.addLayout(top_bar)

        opts = QtWidgets.QHBoxLayout()
        self.exclude_blocked = QtWidgets.QCheckBox("강한 불일치 제외")
        self.exclude_blocked.setChecked(True)
        self.topn_spin = QtWidgets.QSpinBox()
        self.topn_spin.setRange(1, 20)
        self.topn_spin.setValue(5)
        opts.addWidget(self.exclude_blocked)
        opts.addWidget(QtWidgets.QLabel("Top N"))
        opts.addWidget(self.topn_spin)
        vbox.addLayout(opts)

        self.calc_btn = QtWidgets.QPushButton("상위 매칭 계산")
        self.calc_btn.clicked.connect(self._calc_top)
        vbox.addWidget(self.calc_btn)

        self.best_pair_btn = QtWidgets.QPushButton("전체 최적 페어링")
        self.best_pair_btn.clicked.connect(self._calc_pairs)
        vbox.addWidget(self.best_pair_btn)

        self.list_area = QtWidgets.QScrollArea()
        self.list_area.setWidgetResizable(True)
        self.list_container = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_container)
        self.list_layout.addStretch()
        self.list_area.setWidget(self.list_container)
        vbox.addWidget(self.list_area)

        self.output = QtWidgets.QTextEdit()
        self.output.setReadOnly(True)
        vbox.addWidget(self.output)

    def reload(self):
        self.profiles = db.fetch_profiles()
        self.target_combo.clear()
        for p in self.profiles:
            self.target_combo.addItem(f"{p.name} ({p.student_id})", p.uid)
        self.output.setText(f"불러온 프로필: {len(self.profiles)}명")
        self._render_results([])

    def _find_profile_by_uid(self, uid: str) -> Optional[RoommateProfile]:
        for p in self.profiles:
            if p.uid == uid:
                return p
        return None

    def _calc_top(self):
        uid = self.target_combo.currentData()
        target = self._find_profile_by_uid(uid)
        if not target:
            QtWidgets.QMessageBox.warning(self, "선택 필요", "대상 프로필을 선택하세요.")
            return
        pool = [p for p in self.profiles if p.uid != uid]
        res = matcher.rank_matches(target, pool, top_n=self.topn_spin.value(), exclude_blocked=self.exclude_blocked.isChecked())
        self.last_results = res
        self._render_results(res, target=target)
        self.output.setText(f"{target.name} 기준 상위 {len(res)}명 목록이 준비되었습니다.")

    def _calc_pairs(self):
        res = matcher.best_pairings(self.profiles, exclude_blocked=self.exclude_blocked.isChecked())
        lines = [f"최적 페어링 {len(res)}쌍 (총 {len(self.profiles)}명)"]
        for i, r in enumerate(res, 1):
            status = "⚠" if r.hard_block else "✓"
            lines.append(f"{i}. {status} {r.profile_a.name} ↔ {r.profile_b.name}  {r.score:.1f}")
        self.output.setText("\n".join(lines))
        self._render_results([])

    def _render_results(self, results: List[matcher.MatchResult], target: Optional[RoommateProfile] = None):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not results:
            return
        for r in results:
            row = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(row)
            status = "⚠" if r.hard_block else "✓"
            h.addWidget(QtWidgets.QLabel(f"{status} {r.profile_b.name} ({r.score:.1f})"))
            btn = QtWidgets.QPushButton("상세보기")
            btn.clicked.connect(partial(self._show_detail, r, target or r.profile_a))
            h.addWidget(btn)
            h.addStretch()
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

    def _show_detail(self, result: matcher.MatchResult, target: RoommateProfile):
        dlg = DetailDialog(target, result.profile_b, result, self)
        dlg.exec_()


# ---------- Main ----------
class MainWindow(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Roommate Toolkit")
        self.setMinimumSize(900, 700)
        db.init_db()

        self.checklist_tab = ChecklistTab(self)
        self.generator_tab = GeneratorTab(self)
        self.matcher_tab = MatcherTab(self)

        self.addTab(self.checklist_tab, "체크리스트 입력")
        self.addTab(self.generator_tab, "자동 생성기")
        self.addTab(self.matcher_tab, "매칭")

    def refresh_shared_data(self):
        self.matcher_tab.reload()


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
