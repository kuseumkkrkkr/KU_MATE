"""PyQt debug manager for dummy generation and destructive DB reset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from PyQt5 import QtWidgets
except Exception as exc:  # pragma: no cover
    print("PyQt5 is required. Install with: pip install PyQt5")
    print(f"Import error: {exc}")
    raise

from dummy_db_generator import (
    clear_database_rows,
    delete_database_file,
    generate_dummy_dataset,
)


class DebugDbManager(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Roomantic Debug DB Manager")
        self.resize(760, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.db_path = QtWidgets.QLineEdit(str((Path(__file__).parent / "roommates_api.db").resolve()))
        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(self._browse_db)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.db_path)
        row.addWidget(browse)
        row_wrap = QtWidgets.QWidget()
        row_wrap.setLayout(row)
        form.addRow("Target DB", row_wrap)

        self.per_persona = QtWidgets.QSpinBox()
        self.per_persona.setRange(1, 10000)
        self.per_persona.setValue(100)
        form.addRow("Rows / Persona", self.per_persona)

        self.seed = QtWidgets.QLineEdit("")
        self.seed.setPlaceholderText("optional integer")
        form.addRow("Seed", self.seed)

        self.clear_before_generate = QtWidgets.QCheckBox("Clear all rows before generation")
        self.clear_before_generate.setChecked(True)
        form.addRow("", self.clear_before_generate)

        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        self.generate_btn = QtWidgets.QPushButton("Generate Dummy (8 personas)")
        self.generate_btn.clicked.connect(self._run_generate)
        self.clear_btn = QtWidgets.QPushButton("Clear ALL Rows (Destructive)")
        self.clear_btn.clicked.connect(self._run_clear)
        self.delete_btn = QtWidgets.QPushButton("Delete DB File (Destructive)")
        self.delete_btn.clicked.connect(self._run_delete_file)
        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self._append("Ready.")

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _browse_db(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Select sqlite DB path",
            self.db_path.text().strip() or str(Path(__file__).parent),
            "SQLite DB (*.db);;All Files (*)",
        )
        if path:
            self.db_path.setText(path)

    def _target_db(self) -> str:
        return self.db_path.text().strip()

    def _parse_seed(self) -> int | None:
        raw = self.seed.text().strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Seed", "Seed must be integer.")
            return None

    def _confirm(self, title: str, text: str) -> bool:
        button = QtWidgets.QMessageBox.question(
            self,
            title,
            text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return button == QtWidgets.QMessageBox.Yes

    def _run_generate(self) -> None:
        target = self._target_db()
        if not target:
            QtWidgets.QMessageBox.warning(self, "Missing DB path", "Please set target DB path.")
            return
        seed = self._parse_seed()
        if self.seed.text().strip() and seed is None:
            return

        if not self._confirm(
            "Generate Dummy Data",
            "Generate 8 personas dummy data now?\nThis may overwrite data when clear-first is enabled.",
        ):
            return

        try:
            result = generate_dummy_dataset(
                target_db_path=target,
                per_persona=int(self.per_persona.value()),
                clear_first=bool(self.clear_before_generate.isChecked()),
                seed=seed,
            )
            self._append("[GENERATE] success")
            self._append(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as exc:
            self._append(f"[GENERATE] error: {exc}")
            QtWidgets.QMessageBox.critical(self, "Generate Failed", str(exc))

    def _run_clear(self) -> None:
        target = self._target_db()
        if not target:
            QtWidgets.QMessageBox.warning(self, "Missing DB path", "Please set target DB path.")
            return
        if not self._confirm("Clear All Rows", "Delete ALL rows from ALL tables in target DB?"):
            return
        try:
            result = clear_database_rows(target)
            self._append("[CLEAR] done")
            self._append(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as exc:
            self._append(f"[CLEAR] error: {exc}")
            QtWidgets.QMessageBox.critical(self, "Clear Failed", str(exc))

    def _run_delete_file(self) -> None:
        target = self._target_db()
        if not target:
            QtWidgets.QMessageBox.warning(self, "Missing DB path", "Please set target DB path.")
            return
        if not self._confirm("Delete DB File", "Permanently delete selected DB file?"):
            return
        try:
            result = delete_database_file(target)
            self._append("[DELETE FILE] done")
            self._append(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as exc:
            self._append(f"[DELETE FILE] error: {exc}")
            QtWidgets.QMessageBox.critical(self, "Delete Failed", str(exc))


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    win = DebugDbManager()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
