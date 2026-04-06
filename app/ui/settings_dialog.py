from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
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
from app.services.exe_icon_service import ExeIconService
from app.services.ini_service import IniService
from app.services.path_mapping_service import PathMappingService
from app.themes import THEMES, THEME_DISPLAY_NAMES

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency in some environments
    yaml = None


class SettingsDialog(QDialog):
    LAUNCH_METHODS = ("auto", "windows", "wine", "bottles", "steam", "lutris")

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
        self.path_mapping_service = PathMappingService()
        self.exe_icon_service = ExeIconService()
        self._current_language = current_language
        self._current_theme = current_theme

        self.installation_list = QListWidget()
        self.installation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.name_edit = QLineEdit()
        self.exe_path_edit = QLineEdit()
        self.perf_path_edit = QLineEdit()
        self.launch_method_combo = QComboBox()
        self.prefix_path_edit = QLineEdit()
        self.runner_target_edit = QLineEdit()
        self.launch_arguments_edit = QLineEdit()
        self.method_help_label = QLabel()
        self.method_help_label.setWordWrap(True)
        self.perf_path_edit.setPlaceholderText(str(self.ini_service.default_perf_options_path()))

        self.new_button = QPushButton(self.tr("new"))
        self.delete_button = QPushButton(self.tr("delete"))
        self.browse_exe_button = QPushButton(self.tr("choose_exe"))
        self.detect_bottles_button = QPushButton(self.tr("detect_bottles"))
        self.detect_lutris_button = QPushButton(self.tr("detect_lutris"))
        self.browse_perf_button = QPushButton(self.tr("choose_perf"))
        self.browse_prefix_button = QPushButton(self.tr("choose_prefix"))

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
        fallback = kwargs.pop("fallback", None)
        text = self.translator.text(key, **kwargs)
        if text == key and fallback is not None:
            return str(fallback)
        return text

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
        self.name_label = QLabel(self.tr("name"))
        self.launch_method_label = QLabel(self.tr("launch_method"))
        self.exe_label = QLabel("Freelancer.exe")
        self.prefix_label = QLabel(self.tr("prefix_path"))
        self.runner_target_label = QLabel(self.tr("runner_target"))
        self.launch_arguments_label = QLabel(self.tr("launch_arguments"))
        self.perf_label = QLabel("PerfOptions.ini")

        form_layout.addRow(self.name_label, self.name_edit)
        for method in self.LAUNCH_METHODS:
            self.launch_method_combo.addItem(self.tr(f"launch_method_{method}"), method)
        form_layout.addRow(self.launch_method_label, self.launch_method_combo)
        form_layout.addRow(
            self.exe_label,
            self._with_buttons(
                self.exe_path_edit,
                self.browse_exe_button,
                self.detect_bottles_button,
                self.detect_lutris_button,
            ),
        )
        form_layout.addRow(self.prefix_label, self._with_button(self.prefix_path_edit, self.browse_prefix_button))
        form_layout.addRow(self.runner_target_label, self.runner_target_edit)
        form_layout.addRow(self.launch_arguments_label, self.launch_arguments_edit)
        form_layout.addRow(
            self.perf_label,
            self._with_button(self.perf_path_edit, self.browse_perf_button),
        )
        editor_layout.addLayout(form_layout)
        editor_layout.addWidget(self.method_help_label)
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
        return self._with_buttons(line_edit, button)

    def _with_buttons(self, line_edit: QLineEdit, *buttons: QPushButton) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        for button in buttons:
            layout.addWidget(button)
        return wrapper

    def _connect_signals(self) -> None:
        self.installation_list.currentRowChanged.connect(self._load_current_installation_into_form)
        self.name_edit.textEdited.connect(self._save_form_to_current_item)
        self.launch_method_combo.currentIndexChanged.connect(self._on_launch_method_changed)
        self.exe_path_edit.textEdited.connect(self._save_form_to_current_item)
        self.prefix_path_edit.textEdited.connect(self._save_form_to_current_item)
        self.runner_target_edit.textEdited.connect(self._save_form_to_current_item)
        self.launch_arguments_edit.textEdited.connect(self._save_form_to_current_item)
        self.perf_path_edit.textEdited.connect(self._save_form_to_current_item)
        self.new_button.clicked.connect(self._add_installation)
        self.delete_button.clicked.connect(self._delete_current_installation)
        self.browse_exe_button.clicked.connect(self._browse_executable)
        self.detect_bottles_button.clicked.connect(self._detect_bottles_installation)
        self.detect_lutris_button.clicked.connect(self._detect_lutris_installation)
        self.browse_prefix_button.clicked.connect(self._browse_prefix_path)
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
        item = QListWidgetItem(self._icon_for_installation(installation), installation.name or self.tr("new_installation"))
        item.setData(Qt.ItemDataRole.UserRole, installation.id)
        return item

    def _icon_for_installation(self, installation: Installation) -> QIcon:
        resolved_path = self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)
        icon = None
        if resolved_path is not None:
            icon = self.exe_icon_service.icon_for_executable(resolved_path)
        if installation.launch_method.strip().lower() == "lutris":
            icon = icon or self.exe_icon_service.icon_for_lutris_slug(installation.runner_target)
        if icon is not None:
            return icon
        return self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)

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
            self.launch_method_combo.setCurrentIndex(0)
            self.exe_path_edit.clear()
            self.prefix_path_edit.clear()
            self.runner_target_edit.clear()
            self.launch_arguments_edit.clear()
            self.perf_path_edit.clear()

    def _load_current_installation_into_form(self, row: int) -> None:
        self._is_loading = True
        try:
            if row < 0 or row >= len(self._installations):
                self.name_edit.clear()
                self.launch_method_combo.setCurrentIndex(0)
                self.exe_path_edit.clear()
                self.prefix_path_edit.clear()
                self.runner_target_edit.clear()
                self.launch_arguments_edit.clear()
                self.perf_path_edit.clear()
                return

            installation = self._installations[row]
            self.name_edit.setText(installation.name)
            self.launch_method_combo.setCurrentIndex(max(0, self.launch_method_combo.findData(installation.launch_method)))
            self.exe_path_edit.setText(installation.exe_path)
            self.prefix_path_edit.setText(installation.prefix_path)
            self.runner_target_edit.setText(installation.runner_target)
            self.launch_arguments_edit.setText(installation.launch_arguments)
            self.perf_path_edit.setText(installation.perf_options_path)
            self.perf_path_edit.setPlaceholderText(str(self.ini_service.default_perf_options_path(installation)))
            self._sync_method_specific_ui()
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
        installation.launch_method = str(self.launch_method_combo.currentData() or "auto")
        installation.exe_path = self.exe_path_edit.text().strip()
        installation.prefix_path = self.prefix_path_edit.text().strip()
        installation.runner_target = self.runner_target_edit.text().strip()
        installation.launch_arguments = self.launch_arguments_edit.text().strip()
        installation.perf_options_path = self.perf_path_edit.text().strip()
        self.installation_list.item(row).setText(installation.name)
        self.installation_list.item(row).setIcon(self._icon_for_installation(installation))
        self.perf_path_edit.setPlaceholderText(str(self.ini_service.default_perf_options_path(installation)))

    def _on_launch_method_changed(self) -> None:
        self._sync_method_specific_ui()
        self._auto_fill_method_specific_fields()
        self._save_form_to_current_item()

    def _sync_method_specific_ui(self) -> None:
        method = str(self.launch_method_combo.currentData() or "auto")

        self.prefix_label.setText(self.tr(f"prefix_path_{method}", fallback=self.tr("prefix_path")))
        self.runner_target_label.setText(self.tr(f"runner_target_{method}", fallback=self.tr("runner_target")))
        self.method_help_label.setText(self.tr(f"launch_method_help_{method}", fallback=""))
        self.prefix_path_edit.setPlaceholderText(
            self.tr(f"prefix_path_placeholder_{method}", fallback=self.tr("prefix_path_placeholder_default", fallback=""))
        )
        self.runner_target_edit.setPlaceholderText(
            self.tr(
                f"runner_target_placeholder_{method}",
                fallback=self.tr("runner_target_placeholder_default", fallback=""),
            )
        )
        self.launch_arguments_edit.setPlaceholderText(self.tr("launch_arguments_placeholder"))
        uses_prefix = method in {"wine", "bottles"}
        uses_runner_target = method in {"bottles", "steam", "lutris"}
        self.detect_bottles_button.setEnabled(method == "bottles")
        self.detect_lutris_button.setEnabled(method == "lutris")
        self.prefix_path_edit.setEnabled(uses_prefix)
        self.browse_prefix_button.setEnabled(uses_prefix)
        self.runner_target_edit.setEnabled(uses_runner_target)

    def _auto_fill_method_specific_fields(self) -> None:
        method = str(self.launch_method_combo.currentData() or "auto")
        if method == "bottles":
            self._auto_fill_bottles_fields()

    def _auto_fill_bottles_fields(self) -> None:
        exe_text = self.exe_path_edit.text().strip()
        prefix_text = self.prefix_path_edit.text().strip()

        bottle_root = self._detect_bottle_root(exe_text) or self._detect_bottle_root(prefix_text)
        if bottle_root is None:
            return

        if not prefix_text:
            self.prefix_path_edit.setText(str(bottle_root))

        if not self.runner_target_edit.text().strip():
            bottle_name = self._read_bottle_name(bottle_root)
            if bottle_name:
                self.runner_target_edit.setText(bottle_name)

    def _detect_bottle_root(self, selected_path: str) -> Path | None:
        if not selected_path.strip():
            return None

        candidate = Path(selected_path).expanduser()
        parts = candidate.parts
        try:
            bottle_index = parts.index("bottles")
        except ValueError:
            bottle_index = -1

        if bottle_index >= 0 and bottle_index + 1 < len(parts):
            bottle_root = Path(*parts[: bottle_index + 2])
            if (bottle_root / "bottle.yml").exists():
                return bottle_root

        search_root = candidate if candidate.is_dir() else candidate.parent
        for current in [search_root, *search_root.parents]:
            if (current / "bottle.yml").exists():
                return current
        return None

    def _read_bottle_name(self, bottle_root: Path) -> str:
        bottle_file = bottle_root / "bottle.yml"
        if not bottle_file.exists():
            return ""
        try:
            for raw_line in bottle_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("Name:"):
                    return line.split(":", 1)[1].strip().strip("'\"")
        except OSError:
            return ""
        return ""

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
        self._auto_fill_method_specific_fields()
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

    def _browse_prefix_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("choose_prefix_dialog"),
            self.prefix_path_edit.text() or str(Path.home()),
        )
        if not directory:
            return
        self.prefix_path_edit.setText(directory)
        self._auto_fill_method_specific_fields()
        self._save_form_to_current_item()

    def _detect_bottles_installation(self) -> None:
        candidates = self._find_bottles_freelancer_candidates()
        if not candidates:
            QMessageBox.information(
                self,
                self.tr("detect_bottles_none_title"),
                self.tr("detect_bottles_none_message"),
            )
            return

        selected = candidates[0]
        if len(candidates) > 1:
            labels = [item["label"] for item in candidates]
            chosen_label, accepted = QInputDialog.getItem(
                self,
                self.tr("detect_bottles_select_title"),
                self.tr("detect_bottles_select_message"),
                labels,
                0,
                False,
            )
            if not accepted:
                return
            selected = next(item for item in candidates if item["label"] == chosen_label)

        self.launch_method_combo.setCurrentIndex(max(0, self.launch_method_combo.findData("bottles")))
        self.exe_path_edit.setText(selected["exe_path"])
        self.prefix_path_edit.setText(selected["prefix_path"])
        self.runner_target_edit.setText(selected["runner_target"])

        current_name = self.name_edit.text().strip()
        if not current_name or current_name == self.tr("new_installation"):
            self.name_edit.setText(selected["suggested_name"])

        if not self.perf_path_edit.text().strip():
            self.perf_path_edit.setPlaceholderText(
                str(self.path_mapping_service.default_perf_options_path(self._current_prefix_text()))
            )

        self._sync_method_specific_ui()
        self._save_form_to_current_item()

    def _detect_lutris_installation(self) -> None:
        candidates = self._find_lutris_freelancer_candidates()
        if not candidates:
            QMessageBox.information(
                self,
                self.tr("detect_lutris_none_title"),
                self.tr("detect_lutris_none_message"),
            )
            return

        selected = candidates[0]
        if len(candidates) > 1:
            labels = [item["label"] for item in candidates]
            chosen_label, accepted = QInputDialog.getItem(
                self,
                self.tr("detect_lutris_select_title"),
                self.tr("detect_lutris_select_message"),
                labels,
                0,
                False,
            )
            if not accepted:
                return
            selected = next(item for item in candidates if item["label"] == chosen_label)

        self.launch_method_combo.setCurrentIndex(max(0, self.launch_method_combo.findData("lutris")))
        self.runner_target_edit.setText(selected["runner_target"])

        if selected["exe_path"]:
            self.exe_path_edit.setText(selected["exe_path"])
        if selected["prefix_path"]:
            self.prefix_path_edit.setText(selected["prefix_path"])

        current_name = self.name_edit.text().strip()
        if not current_name or current_name == self.tr("new_installation"):
            self.name_edit.setText(selected["suggested_name"])

        if selected["prefix_path"] and not self.perf_path_edit.text().strip():
            self.perf_path_edit.setPlaceholderText(
                str(self.path_mapping_service.default_perf_options_path(selected["prefix_path"]))
            )

        if selected.get("needs_manual_exe") == "1":
            QMessageBox.information(
                self,
                self.tr("detect_lutris_partial_title"),
                self.tr("detect_lutris_partial_message", name=selected["suggested_name"]),
            )

        self._sync_method_specific_ui()
        self._save_form_to_current_item()

    def _find_bottles_freelancer_candidates(self) -> list[dict[str, str]]:
        bottles_root = Path.home() / ".var" / "app" / "com.usebottles.bottles" / "data" / "bottles" / "bottles"
        if not bottles_root.exists():
            return []

        candidates: list[dict[str, str]] = []
        for bottle_root in sorted(path for path in bottles_root.iterdir() if path.is_dir()):
            bottle_name = self._read_bottle_name(bottle_root) or bottle_root.name
            for exe_path in sorted(bottle_root.glob("drive_c/**/Freelancer.exe")):
                suggested_name = exe_path.parents[1].name if len(exe_path.parents) >= 2 else bottle_name
                relative_exe = exe_path.relative_to(bottle_root)
                candidates.append(
                    {
                        "label": f"{bottle_name} | {relative_exe}",
                        "exe_path": str(exe_path),
                        "prefix_path": str(bottle_root),
                        "runner_target": bottle_name,
                        "suggested_name": suggested_name,
                    }
                )
        return candidates

    def _find_lutris_freelancer_candidates(self) -> list[dict[str, str]]:
        raw_games = self._load_lutris_games_json()
        candidates: list[dict[str, str]] = []
        for game in raw_games:
            slug = str(game.get("slug") or "").strip()
            name = str(game.get("name") or "").strip()
            runner = str(game.get("runner") or "").strip().lower()
            if runner != "wine":
                continue
            haystack = f"{slug} {name}".lower()
            if "freelancer" not in haystack and "crossfire" not in haystack:
                continue

            details = self._load_lutris_yaml_details(slug)
            exe_path = details.get("exe_path", "")
            prefix_path = details.get("prefix_path", "")
            if not exe_path and prefix_path:
                exe_path = self._discover_freelancer_exe(Path(prefix_path))

            label_bits = [name or slug, slug]
            if exe_path:
                label_bits.append(Path(exe_path).name)
            elif prefix_path:
                label_bits.append(prefix_path)

            candidates.append(
                {
                    "label": " | ".join(bit for bit in label_bits if bit),
                    "runner_target": slug or str(game.get("id") or "").strip(),
                    "suggested_name": name or slug or self.tr("new_installation"),
                    "exe_path": exe_path,
                    "prefix_path": prefix_path,
                    "needs_manual_exe": "1" if not exe_path else "0",
                }
            )
        return candidates

    def _load_lutris_games_json(self) -> list[dict]:
        try:
            completed = subprocess.run(
                ["lutris", "--list-games", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return []

        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    def _load_lutris_yaml_details(self, slug: str) -> dict[str, str]:
        if yaml is None:
            return {"exe_path": "", "prefix_path": ""}

        games_dir = Path.home() / ".local" / "share" / "lutris" / "games"
        if not games_dir.exists():
            return {"exe_path": "", "prefix_path": ""}

        for config_path in sorted(games_dir.glob("*.yml")):
            try:
                data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue

            yaml_slug = str(data.get("game_slug") or data.get("slug") or "").strip()
            if yaml_slug != slug:
                continue

            game_section = data.get("game") or {}
            exe_path = str(game_section.get("exe") or "").strip()
            prefix_path = str(game_section.get("prefix") or "").strip()
            return {"exe_path": exe_path, "prefix_path": prefix_path}

        return {"exe_path": "", "prefix_path": ""}

    def _discover_freelancer_exe(self, root: Path) -> str:
        if not root.exists():
            return ""
        preferred = [
            root / "drive_c" / "Freelancer Crossfire" / "EXE" / "Freelancer.exe",
            root / "drive_c" / "Games" / "Freelancer HD Edition" / "EXE" / "Freelancer.exe",
            root / "drive_c" / "Program Files (x86)" / "Microsoft Games" / "Freelancer" / "EXE" / "Freelancer.exe",
        ]
        for candidate in preferred:
            if candidate.exists():
                return str(candidate)
        matches = sorted(root.glob("drive_c/**/Freelancer.exe"))
        return str(matches[0]) if matches else ""

    def _current_prefix_text(self) -> str:
        return self.prefix_path_edit.text().strip()

    def _on_accept(self) -> None:
        self._save_form_to_current_item()

        invalid_items = [
            installation.name
            for installation in self._installations
            if installation.exe_path
            and (
                (resolved_path := self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)) is None
                or not resolved_path.exists()
            )
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
            if installation.perf_options_path
            and (
                (
                    resolved_path := self.path_mapping_service.resolve_path(
                        installation.perf_options_path,
                        installation.prefix_path,
                    )
                ) is None
                or not resolved_path.parent.exists()
            )
        ]
        if invalid_perf_paths:
            QMessageBox.warning(
                self,
                self.tr("invalid_ini_paths_title"),
                self.tr("invalid_ini_paths_message"),
            )
            return

        self.accept()
