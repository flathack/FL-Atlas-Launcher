from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.ini_service import IniService
from app.themes import THEMES, THEME_DISPLAY_NAMES


class SettingsDialog(QDialog):
    def __init__(
        self,
        installations: list[Installation],
        translator: Translator,
        current_language: str = "de",
        current_theme: str = "dark_blue",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.setWindowTitle(self.tr("settings_title"))
        self.resize(760, 480)

        self._installations = deepcopy(installations)
        self._is_loading = False
        self.ini_service = IniService()
        self._current_language = current_language
        self._current_theme = current_theme

        self.installation_list = QListWidget()
        self.installation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.name_edit = QLineEdit()
        self.exe_path_edit = QLineEdit()
        self.perf_path_edit = QLineEdit()
        self.perf_path_edit.setPlaceholderText(str(self.ini_service.default_perf_options_path()))

        self.new_button = QPushButton(self.tr("new"))
        self.delete_button = QPushButton(self.tr("delete"))
        self.browse_exe_button = QPushButton(self.tr("choose_exe"))
        self.browse_perf_button = QPushButton(self.tr("choose_perf"))

        self.language_combo = QComboBox()
        self.language_combo.addItem(self.tr("language_de"), "de")
        self.language_combo.addItem(self.tr("language_en"), "en")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self._current_language)))

        self.theme_combo = QComboBox()
        lang = self._current_language
        for theme_id in THEMES:
            display = THEME_DISPLAY_NAMES.get(theme_id, {}).get(lang, theme_id)
            self.theme_combo.addItem(display, theme_id)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self._current_theme)))

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )

        self._build_ui()
        self._connect_signals()
        self._populate_installations()

    @property
    def installations(self) -> list[Installation]:
        return self._installations

    @property
    def selected_language(self) -> str:
        return str(self.language_combo.currentData() or self._current_language)

    @property
    def selected_theme(self) -> str:
        return str(self.theme_combo.currentData() or self._current_theme)

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        tabs = QTabWidget()

        # --- Installations tab ---
        installations_tab = QWidget()
        list_column = QWidget()
        list_layout = QVBoxLayout(list_column)
        list_layout.addWidget(QLabel(self.tr("freelancer_installations")))
        list_layout.addWidget(self.installation_list)

        list_actions = QHBoxLayout()
        list_actions.addWidget(self.new_button)
        list_actions.addWidget(self.delete_button)
        list_layout.addLayout(list_actions)

        editor_column = QWidget()
        editor_layout = QVBoxLayout(editor_column)
        editor_layout.addWidget(QLabel(self.tr("details")))

        form_layout = QFormLayout()
        form_layout.addRow(self.tr("name"), self.name_edit)
        form_layout.addRow("Freelancer.exe", self._with_button(self.exe_path_edit, self.browse_exe_button))
        form_layout.addRow(
            "PerfOptions.ini",
            self._with_button(self.perf_path_edit, self.browse_perf_button),
        )
        editor_layout.addLayout(form_layout)
        editor_layout.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_column)
        splitter.addWidget(editor_column)
        splitter.setSizes([280, 480])

        inst_layout = QVBoxLayout(installations_tab)
        inst_layout.addWidget(splitter)

        tabs.addTab(installations_tab, self.tr("freelancer_installations"))

        # --- General settings tab ---
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setContentsMargins(24, 24, 24, 24)
        general_layout.setVerticalSpacing(16)
        general_layout.addRow(self.tr("language"), self.language_combo)
        general_layout.addRow(self.tr("settings_theme"), self.theme_combo)

        tabs.addTab(general_tab, self.tr("settings_general"))

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(tabs)
        root_layout.addWidget(self.button_box)

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
        item = QListWidgetItem(installation.name or self.tr("new_installation"))
        item.setData(Qt.ItemDataRole.UserRole, installation.id)
        return item

    def _add_installation(self) -> None:
        installation = Installation.create(name=self.tr("new_installation"), exe_path="")
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
        installation.name = self.name_edit.text().strip() or self.tr("new_installation")
        installation.exe_path = self.exe_path_edit.text().strip()
        installation.perf_options_path = self.perf_path_edit.text().strip()
        self.installation_list.item(row).setText(installation.name)

    def _browse_executable(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("choose_exe_dialog"),
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
            self.tr("choose_perf_dialog"),
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
                self.tr("invalid_paths_title"),
                self.tr("invalid_paths_message"),
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
                self.tr("invalid_ini_paths_title"),
                self.tr("invalid_ini_paths_message"),
            )
            return

        self.accept()
