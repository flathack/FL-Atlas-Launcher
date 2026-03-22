from __future__ import annotations

import json
from pathlib import Path
import threading

from PySide6.QtCore import QFileInfo, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileIconProvider,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.app_config import AppConfig
from app.models.installation import Installation
from app.resource_utils import resource_path
from app.services.config_service import ConfigService
from app.services.ini_service import IniService
from app.services.launcher_service import LauncherService
from app.services.mpid_service import MpidService
from app.services.mpid_transfer_service import MpidTransferService
from app.services.resolution_service import ResolutionService
from app.ui.mpid_dialog import MpidDialog
from app.ui.settings_dialog import SettingsDialog


class SyncNotifier(QObject):
    result_ready = Signal(int, object)


class MainWindow(QMainWindow):
    SYNC_POLL_INTERVAL_MS = 15000

    def __init__(self, config_service: ConfigService, app_version: str) -> None:
        super().__init__()
        self.config_service = config_service
        self.app_version = app_version
        self.config = AppConfig.from_dict(config_service.config.to_dict())
        self.translator = Translator(self.config.language)
        self.icon_provider = QFileIconProvider()
        self.resolution_service = ResolutionService()
        self.ini_service = IniService()
        self.mpid_service = MpidService()
        self.transfer_service = MpidTransferService()
        self._is_loading_mpid_combo = False
        self._sync_state = ""
        self._sync_request_id = 0
        self._sync_worker_running = False
        self.sync_notifier = SyncNotifier()
        self.launcher_service = LauncherService(
            ini_service=self.ini_service,
            resolution_service=self.resolution_service,
        )

        self.setWindowTitle(self.tr("app_title", version=self.app_version))
        self.resize(860, 560)
        app_icon_path = resource_path("resources", "icons", "fl_atlas_launcher_icon.svg")
        if app_icon_path.exists():
            self.setWindowIcon(QIcon(str(app_icon_path)))

        self.installation_list = QListWidget()
        self.installation_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.installation_list.setFlow(QListWidget.Flow.LeftToRight)
        self.installation_list.setWrapping(True)
        self.installation_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.installation_list.setMovement(QListWidget.Movement.Static)
        self.installation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.installation_list.setUniformItemSizes(False)
        self.installation_list.setIconSize(QSize(48, 48))
        self.installation_list.setGridSize(QSize(190, 140))
        self.installation_list.setSpacing(12)
        self.installation_list.setWordWrap(True)
        self.installation_list.setTextElideMode(Qt.TextElideMode.ElideNone)

        self.mpid_combo = QComboBox()
        self.resolution_combo = QComboBox()
        self.launch_button = QPushButton(self.tr("start"))
        self.launch_button.setMinimumHeight(40)
        self.language_combo = QComboBox()
        self.language_combo.addItem(self.tr("language_de"), "de")
        self.language_combo.addItem(self.tr("language_en"), "en")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.config.language)))
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(self.SYNC_POLL_INTERVAL_MS)

        self._build_ui()
        self._connect_signals()
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._update_launch_state()
        self._refresh_sync_state(trigger_sync=True)
        self.sync_timer.start()

    def _build_ui(self) -> None:
        self.sync_status_dot = QLabel("●")
        self.sync_status_label = QLabel()

        toolbar = QToolBar(self.tr("toolbar_main"))
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        settings_action = QAction(self.tr("manage_installations"), self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        mpid_action = QAction(self.tr("manage_mpids"), self)
        mpid_action.triggered.connect(self._open_mpid_dialog)
        toolbar.addAction(mpid_action)

        refresh_action = QAction(self.tr("refresh"), self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(self.tr("language")))
        toolbar.addWidget(self.language_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(self.tr("sync_status")))
        toolbar.addWidget(self.sync_status_dot)
        toolbar.addWidget(self.sync_status_label)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        mpid_row = QWidget()
        mpid_layout = QHBoxLayout(mpid_row)
        mpid_layout.setContentsMargins(0, 0, 0, 0)
        mpid_layout.addWidget(QLabel(self.tr("multiplayer_id")))
        mpid_layout.addWidget(self.mpid_combo, 1)

        resolution_row = QWidget()
        resolution_layout = QHBoxLayout(resolution_row)
        resolution_layout.setContentsMargins(0, 0, 0, 0)
        resolution_layout.addWidget(QLabel(self.tr("resolution")))
        resolution_layout.addWidget(self.resolution_combo, 1)

        layout.addWidget(mpid_row)
        layout.addWidget(self.installation_list, 1)
        layout.addWidget(resolution_row)
        layout.addWidget(self.launch_button)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self.tr("config_status", path=self.config_service.config_path))

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _connect_signals(self) -> None:
        self.installation_list.currentRowChanged.connect(self._on_installation_changed)
        self.installation_list.itemDoubleClicked.connect(lambda _item: self._launch_selected_installation())
        self.mpid_combo.currentIndexChanged.connect(self._apply_selected_mpid_profile)
        self.launch_button.clicked.connect(self._launch_selected_installation)
        self.resolution_combo.currentTextChanged.connect(self._save_selected_resolution)
        self.language_combo.currentIndexChanged.connect(self._change_language)
        self.sync_timer.timeout.connect(self._refresh_sync_state)
        self.sync_notifier.result_ready.connect(self._apply_sync_result)

    def _populate_mpid_profiles(self) -> None:
        self._is_loading_mpid_combo = True
        try:
            self.mpid_combo.clear()

            current_profile_id = self.mpid_service.current_profile_id(self.config.mpid_profiles)
            has_registry_mpid = self.mpid_service.has_mpid_values()

            if has_registry_mpid and current_profile_id is None:
                self.mpid_combo.addItem(self.tr("registry_current_unsaved"), None)

            for profile in self.config.mpid_profiles:
                self.mpid_combo.addItem(profile.name, profile.id)

            if self.mpid_combo.count() == 0:
                self.mpid_combo.addItem(self.tr("no_mpid_profiles"), None)
                self.mpid_combo.setEnabled(False)
                return

            self.mpid_combo.setEnabled(True)

            if current_profile_id is not None:
                index = self.mpid_combo.findData(current_profile_id)
                if index >= 0:
                    self.mpid_combo.setCurrentIndex(index)
                    return

            self.mpid_combo.setCurrentIndex(0)
        finally:
            self._is_loading_mpid_combo = False

    def _populate_resolutions(self) -> None:
        unique_resolutions = self.resolution_service.available_resolutions()
        current_resolution = self.resolution_service.detect_current_resolution()
        self.resolution_combo.clear()
        self.resolution_combo.addItems(unique_resolutions)

        if self.config.selected_resolution in unique_resolutions:
            self.resolution_combo.setCurrentText(self.config.selected_resolution)
        elif current_resolution and current_resolution in unique_resolutions:
            self.resolution_combo.setCurrentText(current_resolution)
            self.config.selected_resolution = current_resolution
        elif unique_resolutions:
            self.resolution_combo.setCurrentText(unique_resolutions[0])
            self.config.selected_resolution = unique_resolutions[0]

    def _populate_installations(self) -> None:
        self.installation_list.clear()
        for installation in self.config.installations:
            item = QListWidgetItem(self._icon_for_installation(installation), installation.name)
            item.setData(Qt.ItemDataRole.UserRole, installation.id)
            item.setToolTip(installation.exe_path)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setSizeHint(QSize(190, 140))
            self.installation_list.addItem(item)

        if self.installation_list.count():
            self.installation_list.setCurrentRow(0)

    def _icon_for_installation(self, installation: Installation) -> QIcon:
        exe_path = Path(installation.exe_path)
        if exe_path.exists():
            return self.icon_provider.icon(QFileInfo(str(exe_path)))
        return self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)

    def _current_installation(self) -> Installation | None:
        row = self.installation_list.currentRow()
        if row < 0 or row >= len(self.config.installations):
            return None
        return self.config.installations[row]

    def _update_launch_state(self) -> None:
        self.launch_button.setEnabled(self._current_installation() is not None)

    def _on_installation_changed(self) -> None:
        self._update_launch_state()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config.installations, self.translator, self)
        if dialog.exec():
            self.config.installations = dialog.installations
            self._persist_config()
            self._populate_installations()
            self.statusBar().showMessage(self.tr("installations_saved"), 4000)

    def _open_mpid_dialog(self) -> None:
        dialog = MpidDialog(
            self.config.mpid_profiles,
            self.mpid_service,
            self.config.mpid_sync_path,
            self.translator,
            self,
        )
        if dialog.exec():
            self.config.mpid_profiles = dialog.profiles
            self.config.mpid_sync_path = dialog.sync_path
            self._persist_config()
            self.statusBar().showMessage(self.tr("mpid_profiles_saved"), 4000)
        self._populate_mpid_profiles()
        self._refresh_sync_state(trigger_sync=True)

    def _refresh_view(self) -> None:
        self.config = AppConfig.from_dict(self.config_service.load().to_dict())
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._refresh_sync_state(trigger_sync=True)
        self.statusBar().showMessage(self.tr("view_refreshed"), 3000)

    def _save_selected_resolution(self, resolution: str) -> None:
        self.config.selected_resolution = resolution
        self._persist_config()

    def _persist_config(self) -> None:
        self.config_service.save(self.config)

    def _apply_selected_mpid_profile(self) -> None:
        if self._is_loading_mpid_combo:
            return

        profile_id = self.mpid_combo.currentData()
        if not profile_id:
            return

        profile = next((item for item in self.config.mpid_profiles if item.id == profile_id), None)
        if profile is None:
            return

        try:
            self.mpid_service.apply_profile_values(profile.values)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("registry_error_title"),
                self.tr("registry_write_failed", error=error),
            )
            return

        self.statusBar().showMessage(self.tr("mpid_activated_status", name=profile.name), 4000)

    def _launch_selected_installation(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return

        if not self.resolution_combo.currentText():
            QMessageBox.warning(
                self,
                self.tr("no_resolution_title"),
                self.tr("no_resolution_message"),
            )
            return

        exe_path = Path(installation.exe_path)
        if not exe_path.exists():
            QMessageBox.warning(
                self,
                self.tr("file_missing_title"),
                self.tr("file_missing_message"),
            )
            return

        try:
            perf_path, backup_path = self.launcher_service.prepare_launch(
                installation,
                self.resolution_combo.currentText(),
            )
        except ValueError:
            QMessageBox.warning(
                self,
                self.tr("invalid_resolution_title"),
                self.tr("invalid_resolution_message"),
            )
            return
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("perfoptions_error_title"),
                self.tr("perfoptions_error_message", error=error),
            )
            return

        try:
            self.launcher_service.launch(installation)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("launch_failed_title"),
                self.tr("launch_failed_message", error=error),
            )
            return

        message = self.tr(
            "launch_status",
            name=installation.name,
            resolution=self.resolution_combo.currentText(),
            path=perf_path,
        )
        if backup_path is not None:
            message += self.tr("backup_suffix", name=backup_path.name)
        self.statusBar().showMessage(message, 8000)

    def _change_language(self) -> None:
        language = self.language_combo.currentData()
        if not language or language == self.config.language:
            return

        self.config.language = str(language)
        self.translator.set_language(self.config.language)
        self._persist_config()
        self._rebuild_translated_ui()

    def _rebuild_translated_ui(self) -> None:
        self.setWindowTitle(self.tr("app_title", version=self.app_version))
        self.launch_button.setText(self.tr("start"))
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(self.tr("language_de"), "de")
        self.language_combo.addItem(self.tr("language_en"), "en")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.config.language)))
        self.language_combo.blockSignals(False)
        central_widget = self.takeCentralWidget()
        if central_widget is not None:
            central_widget.deleteLater()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            toolbar.deleteLater()
        self._build_ui()
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._update_sync_indicator(self._sync_state or "unconfigured")

    def _refresh_sync_state(self, trigger_sync: bool = True) -> None:
        if self._sync_worker_running:
            return

        self._sync_worker_running = True
        self._sync_request_id += 1
        request_id = self._sync_request_id
        config_snapshot = AppConfig.from_dict(self.config.to_dict())
        self._update_sync_indicator("checking")

        worker = threading.Thread(
            target=self._run_sync_check,
            args=(request_id, config_snapshot, trigger_sync),
            daemon=True,
        )
        worker.start()

    def _run_sync_check(self, request_id: int, config_snapshot: AppConfig, trigger_sync: bool) -> None:
        sync_path = config_snapshot.mpid_sync_path.strip()
        if not sync_path:
            self.sync_notifier.result_ready.emit(request_id, {"state": "unconfigured"})
            return

        sync_dir = Path(sync_path)
        if not self._is_sync_directory_available(sync_dir):
            self.sync_notifier.result_ready.emit(request_id, {"state": "offline"})
            return

        if not trigger_sync:
            self.sync_notifier.result_ready.emit(request_id, {"state": "online"})
            return

        try:
            result = self.transfer_service.sync_profiles(sync_dir, config_snapshot.mpid_profiles)
            self.sync_notifier.result_ready.emit(
                request_id,
                {
                    "state": "online",
                    "profiles": result.profiles,
                    "imported": result.imported,
                    "updated": result.updated,
                },
            )
        except (OSError, ValueError, json.JSONDecodeError):
            self.sync_notifier.result_ready.emit(request_id, {"state": "offline"})

    def _apply_sync_result(self, request_id: int, payload: object) -> None:
        if request_id != self._sync_request_id:
            return

        self._sync_worker_running = False
        result = payload if isinstance(payload, dict) else {}
        state = str(result.get("state", "unconfigured"))
        previous_state = self._sync_state
        self._update_sync_indicator(state)

        if state == "online":
            profiles = result.get("profiles")
            if isinstance(profiles, list):
                self.config.mpid_profiles = profiles
                self._persist_config()
                self._populate_mpid_profiles()

            imported = int(result.get("imported", 0))
            updated = int(result.get("updated", 0))
            if previous_state == "offline":
                self.statusBar().showMessage(self.tr("sync_online_status"), 4000)
            elif imported or updated:
                self.statusBar().showMessage(
                    self.tr("sync_complete_status", imported=imported, updated=updated),
                    5000,
                )
            return

        if state == "offline" and previous_state != "offline":
            self.statusBar().showMessage(self.tr("sync_offline_status"), 4000)

    def _is_sync_directory_available(self, sync_dir: Path) -> bool:
        try:
            return sync_dir.exists() and sync_dir.is_dir()
        except OSError:
            return False

    def _update_sync_indicator(self, state: str) -> None:
        color_map = {
            "online": "#39d353",
            "offline": "#ff5f56",
            "checking": "#f2cc60",
            "unconfigured": "#9aa4b2",
        }
        text_map = {
            "online": self.tr("sync_status_online"),
            "offline": self.tr("sync_status_offline"),
            "checking": self.tr("sync_status_checking"),
            "unconfigured": self.tr("sync_status_unconfigured"),
        }
        color = color_map.get(state, color_map["unconfigured"])
        text = text_map.get(state, text_map["unconfigured"])
        self.sync_status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.sync_status_label.setText(text)
        self.sync_status_label.setToolTip(self.config.mpid_sync_path)
        self._sync_state = state
