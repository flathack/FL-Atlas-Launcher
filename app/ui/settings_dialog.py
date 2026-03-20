from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.installation import Installation
from app.services.ini_service import IniService


class SettingsDialog(QDialog):
    def __init__(self, installations: list[Installation], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Installationen verwalten")
        self.resize(760, 420)

        self._installations = deepcopy(installations)
        self._is_loading = False
        self.ini_service = IniService()

        self.installation_list = QListWidget()
        self.installation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.name_edit = QLineEdit()
        self.exe_path_edit = QLineEdit()
        self.perf_path_edit = QLineEdit()
        self.perf_path_edit.setPlaceholderText(str(self.ini_service.default_perf_options_path()))

        self.new_button = QPushButton("Neu")
        self.delete_button = QPushButton("Loeschen")
        self.browse_exe_button = QPushButton("EXE waehlen")
        self.browse_perf_button = QPushButton("PerfOptions.ini waehlen")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )

        self._build_ui()
        self._connect_signals()
        self._populate_installations()

    @property
    def installations(self) -> list[Installation]:
        return self._installations

    def _build_ui(self) -> None:
        list_column = QWidget()
        list_layout = QVBoxLayout(list_column)
        list_layout.addWidget(QLabel("Freelancer-Installationen"))
        list_layout.addWidget(self.installation_list)

        list_actions = QHBoxLayout()
        list_actions.addWidget(self.new_button)
        list_actions.addWidget(self.delete_button)
        list_layout.addLayout(list_actions)

        editor_column = QWidget()
        editor_layout = QVBoxLayout(editor_column)
        editor_layout.addWidget(QLabel("Details"))

        form_layout = QFormLayout()
        form_layout.addRow("Name", self.name_edit)
        form_layout.addRow("Freelancer.exe", self._with_button(self.exe_path_edit, self.browse_exe_button))
        form_layout.addRow(
            "PerfOptions.ini",
            self._with_button(self.perf_path_edit, self.browse_perf_button),
        )
        editor_layout.addLayout(form_layout)
        editor_layout.addStretch(1)
        editor_layout.addWidget(self.button_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_column)
        splitter.addWidget(editor_column)
        splitter.setSizes([280, 480])

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(splitter)

    def _with_button(self, line_edit: QLineEdit, button: QPushButton) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return wrapper

    def _connect_signals(self) -> None:
        self.installation_list.currentRowChanged.connect(self._load_current_installation_into_form)
        self.name_edit.textEdited.connect(self._save_form_to_current_item)
        self.exe_path_edit.textEdited.connect(self._save_form_to_current_item)
        self.perf_path_edit.textEdited.connect(self._save_form_to_current_item)
        self.new_button.clicked.connect(self._add_installation)
        self.delete_button.clicked.connect(self._delete_current_installation)
        self.browse_exe_button.clicked.connect(self._browse_executable)
        self.browse_perf_button.clicked.connect(self._browse_perf_options)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

    def _populate_installations(self) -> None:
        self.installation_list.clear()
        for installation in self._installations:
            self.installation_list.addItem(self._build_list_item(installation))

        if self._installations:
            self.installation_list.setCurrentRow(0)
        else:
            self._add_installation()

    def _build_list_item(self, installation: Installation) -> QListWidgetItem:
        item = QListWidgetItem(installation.name or "Neue Installation")
        item.setData(Qt.ItemDataRole.UserRole, installation.id)
        return item

    def _add_installation(self) -> None:
        installation = Installation.create(name="Neue Installation", exe_path="")
        self._installations.append(installation)
        self.installation_list.addItem(self._build_list_item(installation))
        self.installation_list.setCurrentRow(self.installation_list.count() - 1)
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def _delete_current_installation(self) -> None:
        row = self.installation_list.currentRow()
        if row < 0:
            return

        del self._installations[row]
        self.installation_list.takeItem(row)

        if self._installations:
            self.installation_list.setCurrentRow(max(0, row - 1))
        else:
            self.name_edit.clear()
            self.exe_path_edit.clear()
            self.perf_path_edit.clear()

    def _load_current_installation_into_form(self, row: int) -> None:
        self._is_loading = True
        try:
            if row < 0 or row >= len(self._installations):
                self.name_edit.clear()
                self.exe_path_edit.clear()
                self.perf_path_edit.clear()
                return

            installation = self._installations[row]
            self.name_edit.setText(installation.name)
            self.exe_path_edit.setText(installation.exe_path)
            self.perf_path_edit.setText(installation.perf_options_path)
        finally:
            self._is_loading = False

    def _save_form_to_current_item(self) -> None:
        if self._is_loading:
            return

        row = self.installation_list.currentRow()
        if row < 0 or row >= len(self._installations):
            return

        installation = self._installations[row]
        installation.name = self.name_edit.text().strip() or "Neue Installation"
        installation.exe_path = self.exe_path_edit.text().strip()
        installation.perf_options_path = self.perf_path_edit.text().strip()
        self.installation_list.item(row).setText(installation.name)

    def _browse_executable(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Freelancer.exe auswaehlen",
            self.exe_path_edit.text() or str(Path.home()),
            "Executable (*.exe)",
        )
        if not filename:
            return
        self.exe_path_edit.setText(filename)
        self._save_form_to_current_item()

    def _browse_perf_options(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "PerfOptions.ini auswaehlen",
            self.perf_path_edit.text() or str(Path.home()),
            "INI files (*.ini)",
        )
        if not filename:
            return
        self.perf_path_edit.setText(filename)
        self._save_form_to_current_item()

    def _on_accept(self) -> None:
        self._save_form_to_current_item()

        invalid_items = [
            installation.name
            for installation in self._installations
            if installation.exe_path and not Path(installation.exe_path).exists()
        ]
        if invalid_items:
            QMessageBox.warning(
                self,
                "Ungueltige Pfade",
                "Mindestens ein Eintrag verweist auf eine nicht vorhandene Freelancer.exe.",
            )
            return

        invalid_perf_paths = [
            installation.name
            for installation in self._installations
            if installation.perf_options_path and not Path(installation.perf_options_path).parent.exists()
        ]
        if invalid_perf_paths:
            QMessageBox.warning(
                self,
                "Ungueltige INI-Pfade",
                "Mindestens ein PerfOptions.ini-Pfad zeigt in einen nicht vorhandenen Ordner.",
            )
            return

        self.accept()
