from __future__ import annotations

import json
from pathlib import Path
import subprocess
import threading

from PySide6.QtCore import QFileInfo, QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileIconProvider,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.app_config import AppConfig
from app.models.installation import Installation
from app.resource_utils import resource_path
from app.services.cheat_service import CheatService
from app.services.config_service import ConfigService
from app.services.ini_service import IniService
from app.services.launcher_service import LauncherService
from app.services.mpid_service import MpidService
from app.services.mpid_transfer_service import MpidTransferService
from app.services.process_service import ProcessService
from app.services.resolution_service import ResolutionService
from app.services.trade_route_service import TradeRouteService
from app.ui.mpid_dialog import MpidDialog
from app.ui.reputation_dialog import ReputationDialog
from app.ui.ship_handling_dialog import ShipHandlingDialog, ShipInfoDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.trade_route_dialog import TradeRouteDialog
from app.ui.trade_route_round_trip_dialog import TradeRouteRoundTripDialog


class SyncNotifier(QObject):
    result_ready = Signal(int, object)


class ProcessNotifier(QObject):
    result_ready = Signal(object)


class MainWindow(QMainWindow):
    SYNC_POLL_INTERVAL_MS = 15000
    PROCESS_POLL_INTERVAL_MS = 2500
    HELP_WIKI_URL = "https://github.com/flathack/FL-Atlas-Launcher/wiki"

    def __init__(self, config_service: ConfigService, app_version: str, *, show_cheat_features: bool = True) -> None:
        super().__init__()
        self.config_service = config_service
        self.app_version = app_version
        self.show_cheat_features = bool(show_cheat_features)
        self.config = AppConfig.from_dict(config_service.config.to_dict())
        self.translator = Translator(self.config.language)
        self.icon_provider = QFileIconProvider()
        self.resolution_service = ResolutionService()
        self.ini_service = IniService()
        self.mpid_service = MpidService()
        self.transfer_service = MpidTransferService()
        self.process_service = ProcessService()
        self._is_loading_mpid_combo = False
        self._persistent_signals_connected = False
        self._is_loading_cheat_controls = False
        self._sync_state = ""
        self._sync_request_id = 0
        self._sync_worker_running = False
        self._process_worker_running = False
        self._running_processes: dict[str, list[int]] = {}
        self._trade_route_windows: list[TradeRouteDialog] = []
        self._round_trip_windows: list[TradeRouteRoundTripDialog] = []
        self.sync_notifier = SyncNotifier()
        self.process_notifier = ProcessNotifier()
        self._cheat_service: CheatService | None = None
        self._trade_route_service: TradeRouteService | None = None
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
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(self.SYNC_POLL_INTERVAL_MS)
        self.process_timer = QTimer(self)
        self.process_timer.setInterval(self.PROCESS_POLL_INTERVAL_MS)

        self._build_ui()
        self._connect_signals()
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._update_launch_state()
        self._refresh_sync_state(trigger_sync=True)
        self._refresh_process_state()
        self.sync_timer.start()
        self.process_timer.start()

    def _build_ui(self) -> None:
        self.language_combo = QComboBox()
        self.language_combo.addItem(self.tr("language_de"), "de")
        self.language_combo.addItem(self.tr("language_en"), "en")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.config.language)))
        self.language_combo.setMinimumWidth(90)
        self.language_combo.setMaximumWidth(110)
        self.language_combo.setToolTip(self.tr("language"))
        self.language_combo.activated.connect(lambda _index: self._change_language())
        self.sync_status_dot = QLabel(chr(0x25CF))
        self.sync_status_dot.setToolTip(self.tr("sync_status"))
        self.sync_status_label = QLabel()
        self.sync_status_label.setMinimumWidth(56)
        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setToolTip(self.tr("help"))
        self.help_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.help_button.setMinimumSize(QSize(30, 30))
        if self.show_cheat_features:
            self.cheater_mode_label = QLabel(self.tr("cheater_mode"))
            self.cheater_mode_switch = QCheckBox()
            self.cheater_mode_switch.setCursor(Qt.CursorShape.PointingHandCursor)
            self.cheater_mode_switch.setMinimumWidth(70)
            self._apply_cheater_switch_style(False)

        help_menu = QMenu(self.help_button)
        help_wiki_action = help_menu.addAction(self.tr("help_open_wiki"))
        help_wiki_action.triggered.connect(self._open_help_wiki)
        self.help_button.setMenu(help_menu)

        toolbar = QToolBar(self.tr("toolbar_main"))
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(toolbar)

        settings_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), self.tr("manage_installations"), self)
        settings_action.setToolTip(self.tr("manage_installations"))
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        mpid_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), self.tr("manage_mpids"), self)
        mpid_action.setToolTip(self.tr("manage_mpids"))
        mpid_action.triggered.connect(self._open_mpid_dialog)
        toolbar.addAction(mpid_action)

        refresh_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), self.tr("refresh"), self)
        refresh_action.setToolTip(self.tr("refresh"))
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)
        ship_info_icon_path = resource_path("resources", "icons", "fl_atlas_launcher_icon.svg")
        ship_info_icon = QIcon(str(ship_info_icon_path)) if ship_info_icon_path.exists() else self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView)
        self.ship_info_action = QAction(ship_info_icon, self.tr("ship_info_open"), self)
        self.ship_info_action.setToolTip(self.tr("ship_info_open"))
        self.ship_info_action.triggered.connect(self._open_ship_info_dialog)
        toolbar.addAction(self.ship_info_action)

        self.trade_routes_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), self.tr("trade_routes_open"), self)
        self.trade_routes_action.setToolTip(self.tr("trade_routes_open"))
        self.trade_routes_action.triggered.connect(self._open_trade_routes_dialog)
        toolbar.addAction(self.trade_routes_action)

        self.reputation_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton), self.tr("reputation_open"), self)
        self.reputation_action.setToolTip(self.tr("reputation_open"))
        self.reputation_action.triggered.connect(self._open_reputation_dialog)
        toolbar.addAction(self.reputation_action)

        self.round_trip_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight), self.tr("trade_round_trip_open"), self)
        self.round_trip_action.setToolTip(self.tr("trade_round_trip_open"))
        self.round_trip_action.triggered.connect(self._open_round_trip_dialog)
        toolbar.addAction(self.round_trip_action)
        toolbar.addSeparator()
        toolbar.addWidget(self.language_combo)
        toolbar.addSeparator()
        toolbar.addWidget(self.sync_status_dot)
        toolbar.addWidget(self.sync_status_label)
        if self.show_cheat_features:
            toolbar.addSeparator()
            toolbar.addWidget(self.cheater_mode_label)
            toolbar.addWidget(self.cheater_mode_switch)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self.help_button)

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

        content_row = QWidget()
        content_layout = QHBoxLayout(content_row)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)
        content_layout.addWidget(self.installation_list, 1)
        if self.show_cheat_features:
            self.cheat_panel = self._build_cheat_panel()
            content_layout.addWidget(self.cheat_panel)

        layout.addWidget(mpid_row)
        layout.addWidget(content_row, 1)
        layout.addWidget(resolution_row)
        layout.addWidget(self.launch_button)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self.tr("config_status", path=self.config_service.config_path))
        self._update_cheat_panel_visibility()

    def _build_cheat_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(310)
        panel.setMaximumWidth(370)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel(self.tr("cheat_panel_title"))
        title_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        self.cheat_installation_label = QLabel(self.tr("cheat_no_installation"))
        self.cheat_installation_label.setWordWrap(True)
        hint_label = QLabel(self.tr("cheat_panel_hint"))
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #94a3b8;")
        self.bini_hint_label = QLabel(self.tr("bini_convert_hint"))
        self.bini_hint_label.setWordWrap(True)
        self.bini_hint_label.setStyleSheet("color: #94a3b8;")

        self.bini_toggle = QCheckBox(self.tr("bini_convert"))

        cruise_label = QLabel(self.tr("cruise_charge_group"))
        cruise_label.setStyleSheet("font-weight: 600;")
        self.cruise_charge_value_label = QLabel()
        self.cruise_charge_slider = QSlider(Qt.Orientation.Horizontal)
        self.cruise_charge_slider.setRange(1, 50)
        self.cruise_charge_slider.setSingleStep(1)
        self.cruise_charge_slider.setPageStep(1)

        jump_timing_label = QLabel(self.tr("jump_timing_group"))
        jump_timing_label.setStyleSheet("font-weight: 600;")
        self.jump_timing_toggle = QCheckBox(self.tr("jump_timing_enable"))
        self.jump_timing_value_label = QLabel()
        self.jump_timing_slider = QSlider(Qt.Orientation.Horizontal)
        self.jump_timing_slider.setRange(1, 10)
        self.jump_timing_slider.setSingleStep(1)
        self.jump_timing_slider.setPageStep(1)

        reveal_label = QLabel(self.tr("reveal_group"))
        reveal_label.setStyleSheet("font-weight: 600;")
        self.reveal_toggle = QCheckBox(self.tr("reveal_apply"))

        self.ship_handling_button = QPushButton(self.tr("ship_handling_open"))
        self.ship_handling_reset_button = QPushButton(self.tr("ship_handling_reset_sidebar"))
        self.ship_handling_button.setMinimumHeight(34)
        self.ship_handling_reset_button.setMinimumHeight(34)

        bini_section = self._build_cheat_section()
        bini_layout = QVBoxLayout(bini_section)
        bini_layout.setContentsMargins(12, 12, 12, 12)
        bini_layout.setSpacing(8)
        bini_layout.addWidget(self.bini_toggle)
        bini_layout.addWidget(self.bini_hint_label)

        values_section = self._build_cheat_section()
        values_layout = QGridLayout(values_section)
        values_layout.setContentsMargins(12, 12, 12, 12)
        values_layout.setHorizontalSpacing(8)
        values_layout.setVerticalSpacing(8)
        values_layout.addWidget(cruise_label, 0, 0)
        values_layout.addWidget(self.cruise_charge_value_label, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        values_layout.addWidget(self.cruise_charge_slider, 1, 0, 1, 2)
        values_layout.addWidget(jump_timing_label, 2, 0)
        values_layout.addWidget(self.jump_timing_toggle, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        values_layout.addWidget(self.jump_timing_value_label, 3, 0, 1, 2)
        values_layout.addWidget(self.jump_timing_slider, 4, 0, 1, 2)
        values_layout.addWidget(reveal_label, 5, 0)
        values_layout.addWidget(self.reveal_toggle, 5, 1, alignment=Qt.AlignmentFlag.AlignRight)

        tools_section = self._build_cheat_section()
        tools_layout = QVBoxLayout(tools_section)
        tools_layout.setContentsMargins(12, 12, 12, 12)
        tools_layout.setSpacing(8)
        tools_header = QLabel(self.tr("cheat_tools_title"))
        tools_header.setStyleSheet("font-weight: 600;")
        tools_layout.addWidget(tools_header)
        tools_layout.addWidget(self.ship_handling_button)
        tools_layout.addWidget(self.ship_handling_reset_button)

        self.mod_controls_widget = QWidget()
        mod_layout = QVBoxLayout(self.mod_controls_widget)
        mod_layout.setContentsMargins(0, 0, 0, 0)
        mod_layout.setSpacing(10)
        mod_layout.addWidget(bini_section)
        mod_layout.addWidget(values_section)
        mod_layout.addWidget(tools_section)

        layout.addWidget(title_label)
        layout.addWidget(self.cheat_installation_label)
        layout.addWidget(hint_label)
        layout.addWidget(self.mod_controls_widget)
        layout.addStretch(1)
        return panel

    def _build_cheat_section(self) -> QFrame:
        section = QFrame()
        section.setFrameShape(QFrame.Shape.StyledPanel)
        section.setStyleSheet(
            "QFrame { background-color: #111827; border: 1px solid #233045; border-radius: 12px; }"
            "QLabel { border: none; background: transparent; }"
        )
        return section

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _get_cheat_service(self) -> CheatService:
        if self._cheat_service is None:
            self._cheat_service = CheatService(self.config_service.config_path.parent / "mod_backups")
        return self._cheat_service

    def _get_trade_route_service(self) -> TradeRouteService:
        if self._trade_route_service is None:
            self._trade_route_service = TradeRouteService(self._get_cheat_service())
        return self._trade_route_service

    def _connect_signals(self) -> None:
        self.installation_list.currentRowChanged.connect(self._on_installation_changed)
        self.installation_list.itemDoubleClicked.connect(lambda _item: self._launch_selected_installation())
        self.installation_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.installation_list.customContextMenuRequested.connect(self._open_installation_context_menu)
        self.mpid_combo.currentIndexChanged.connect(self._apply_selected_mpid_profile)
        self.launch_button.clicked.connect(self._launch_selected_installation)
        self.resolution_combo.currentTextChanged.connect(self._save_selected_resolution)
        if self.show_cheat_features:
            self.cheater_mode_switch.toggled.connect(self._toggle_cheater_mode)
            self.bini_toggle.toggled.connect(self._toggle_bini_conversion)
            self.cruise_charge_slider.valueChanged.connect(self._apply_cruise_charge_time)
            self.jump_timing_toggle.toggled.connect(self._toggle_jump_timing)
            self.jump_timing_slider.valueChanged.connect(self._apply_jump_timing)
            self.reveal_toggle.toggled.connect(self._toggle_reveal_everything)
            self.ship_handling_button.clicked.connect(self._open_ship_handling_dialog)
            self.ship_handling_reset_button.clicked.connect(self._reset_ship_handling)
        if not self._persistent_signals_connected:
            self.sync_timer.timeout.connect(lambda: self._refresh_sync_state(trigger_sync=False))
            self.process_timer.timeout.connect(self._refresh_process_state)
            self.sync_notifier.result_ready.connect(self._apply_sync_result)
            self.process_notifier.result_ready.connect(self._apply_process_state)
            self._persistent_signals_connected = True

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
        base_icon: QIcon
        if exe_path.exists():
            base_icon = self.icon_provider.icon(QFileInfo(str(exe_path)))
        else:
            base_icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)

        if self._is_installation_running(installation):
            return self._with_running_badge(base_icon)
        return base_icon

    def _current_installation(self) -> Installation | None:
        row = self.installation_list.currentRow()
        if row < 0 or row >= len(self.config.installations):
            return None
        return self.config.installations[row]

    def _update_launch_state(self) -> None:
        has_installation = self._current_installation() is not None
        self.launch_button.setEnabled(has_installation)
        if self.show_cheat_features:
            self.cheater_mode_switch.setEnabled(has_installation)
        self.trade_routes_action.setEnabled(has_installation)
        self.reputation_action.setEnabled(has_installation)
        self.round_trip_action.setEnabled(has_installation)
        self._update_cheat_panel_state(has_installation)
        self._update_cheat_panel_visibility()

    def _on_installation_changed(self) -> None:
        self._update_launch_state()
        self._sync_cheat_panel_to_installation()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config.installations, self.translator, self)
        if dialog.exec():
            self.config.installations = dialog.installations
            self._persist_config()
            self._populate_installations()
            self._refresh_process_state()
            self.statusBar().showMessage(self.tr("installations_saved"), 4000)

    def _open_mpid_dialog(self) -> None:
        dialog = MpidDialog(
            self.config.mpid_profiles,
            self.mpid_service,
            self.config.mpid_sync_path,
            self.translator,
            self,
        )
        previous_sync_path = self.config.mpid_sync_path
        if dialog.exec():
            self.config.mpid_profiles = dialog.profiles
            self.config.mpid_sync_path = dialog.sync_path
            self._persist_config()
            self.statusBar().showMessage(self.tr("mpid_profiles_saved"), 4000)
        elif dialog.sync_path != previous_sync_path:
            self.config.mpid_sync_path = dialog.sync_path
            self._persist_config()
        self._populate_mpid_profiles()
        self._refresh_sync_state(trigger_sync=False)

    def _refresh_view(self) -> None:
        self.config = AppConfig.from_dict(self.config_service.load().to_dict())
        self.translator.set_language(self.config.language)
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._refresh_sync_state(trigger_sync=False)
        self._update_cheat_panel_visibility()
        self._refresh_process_state()
        self._sync_cheat_panel_to_installation()
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
            perf_path = self.launcher_service.prepare_launch(
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
        self.statusBar().showMessage(message, 8000)
        self._refresh_process_state()

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
        central_widget = self.takeCentralWidget()
        if central_widget is not None:
            central_widget.deleteLater()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            toolbar.deleteLater()
        self._build_ui()
        self._connect_signals()
        self._populate_mpid_profiles()
        self._populate_resolutions()
        self._populate_installations()
        self._update_sync_indicator(self._sync_state or "unconfigured")
        self._sync_cheat_panel_to_installation()
        self._refresh_process_state()

    def _apply_cheater_switch_style(self, enabled: bool) -> None:
        if not self.show_cheat_features or not hasattr(self, "cheater_mode_switch"):
            return
        self.cheater_mode_switch.setText("ON" if enabled else "OFF")
        self.cheater_mode_switch.setStyleSheet(
            """
            QCheckBox {
                color: #f8fafc;
                font-weight: 700;
                padding: 4px 10px 4px 38px;
                border-radius: 14px;
                background-color: #7f8c8d;
                min-height: 28px;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 11px;
                margin-left: 4px;
                background: #ffffff;
            }
            QCheckBox:checked {
                background-color: #129a74;
            }
            QCheckBox:disabled {
                background-color: #c7ced6;
                color: #eef2f6;
            }
            """
        )

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

    def _toggle_cheater_mode(self, enabled: bool) -> None:
        if not self.show_cheat_features:
            return
        if self._is_loading_cheat_controls:
            return
        installation = self._current_installation()
        if installation is None:
            return
        installation.cheater_mode_enabled = enabled
        self._apply_cheater_switch_style(enabled)
        self._persist_config()
        self._update_cheat_panel_visibility()

    def _update_cheat_panel_visibility(self) -> None:
        if not self.show_cheat_features or not hasattr(self, "cheat_panel"):
            return
        installation = self._current_installation()
        self.cheat_panel.setVisible(bool(installation and installation.cheater_mode_enabled))

    def _update_cheat_panel_state(self, has_installation: bool) -> None:
        if not self.show_cheat_features:
            return
        self.bini_toggle.setEnabled(has_installation)
        self.mod_controls_widget.setEnabled(has_installation)

    def _sync_cheat_panel_to_installation(self) -> None:
        if not self.show_cheat_features:
            return
        self._is_loading_cheat_controls = True
        installation = self._current_installation()
        if installation is None:
            self._apply_cheater_switch_style(False)
            self.cheater_mode_switch.setChecked(False)
            self.cheat_installation_label.setText(self.tr("cheat_no_installation"))
            self.cruise_charge_value_label.setText(self.tr("cruise_charge_value", value="0.1"))
            self.cruise_charge_slider.setValue(1)
            self.jump_timing_toggle.setChecked(False)
            self.jump_timing_value_label.setText(self.tr("jump_timing_value", value="0.1"))
            self.jump_timing_slider.setValue(1)
            self.jump_timing_slider.setEnabled(False)
            self.bini_toggle.setChecked(False)
            self.bini_toggle.setEnabled(False)
            self.reveal_toggle.setChecked(False)
            self.bini_hint_label.setVisible(True)
            self.mod_controls_widget.setVisible(False)
            self._is_loading_cheat_controls = False
            self._update_cheat_panel_visibility()
            return

        self.cheater_mode_switch.setChecked(installation.cheater_mode_enabled)
        self._apply_cheater_switch_style(installation.cheater_mode_enabled)
        self.cheat_installation_label.setText(
            self.tr("cheat_selected_installation", name=installation.name)
        )
        try:
            cheat_service = self._get_cheat_service()
            cruise_charge = cheat_service.get_cruise_charge_time(installation)
            jump_timing = cheat_service.get_jump_timing_value(installation)
            jump_timing_enabled = cheat_service.has_backup(installation, "jump_timing")
            bini_pending = cheat_service.has_unconverted_bini_files(installation)
            reveal_enabled = cheat_service.has_backup(installation, "reveal_everything")
        except OSError:
            cruise_charge = None
            jump_timing = None
            jump_timing_enabled = False
            bini_pending = True
            reveal_enabled = False

        slider_value = max(1, min(50, int(round((cruise_charge if cruise_charge is not None else 0.1) * 10))))
        self.cruise_charge_slider.setValue(slider_value)
        self.cruise_charge_value_label.setText(
            self.tr("cruise_charge_value", value=f"{slider_value / 10:.1f}")
        )
        jump_slider_value = max(1, min(10, int(round((jump_timing if jump_timing is not None else 0.1) * 10))))
        self.jump_timing_toggle.setChecked(jump_timing_enabled)
        self.jump_timing_slider.setEnabled(jump_timing_enabled)
        self.jump_timing_slider.setValue(jump_slider_value)
        self.jump_timing_value_label.setText(
            self.tr("jump_timing_value", value=f"{jump_slider_value / 10:.1f}")
        )
        self.bini_toggle.setChecked(not bini_pending)
        self.bini_toggle.setEnabled(bini_pending)
        self.bini_hint_label.setVisible(bini_pending)
        self.mod_controls_widget.setVisible(not bini_pending)
        self.reveal_toggle.setChecked(reveal_enabled)
        self._is_loading_cheat_controls = False
        self._update_cheat_panel_visibility()

    def _refresh_process_state(self) -> None:
        if self._process_worker_running:
            return

        exe_paths = [
            installation.exe_path
            for installation in self.config.installations
            if installation.exe_path.strip() and Path(installation.exe_path).exists()
        ]
        if not exe_paths:
            if self._running_processes:
                self._running_processes = {}
                self._apply_process_icons()
            return

        self._process_worker_running = True
        worker = threading.Thread(
            target=self._run_process_check,
            args=(exe_paths,),
            daemon=True,
        )
        worker.start()

    def _run_process_check(self, exe_paths: list[str]) -> None:
        try:
            running = self.process_service.running_processes_by_path(exe_paths)
        except (OSError, ValueError, json.JSONDecodeError):
            running = {}
        self.process_notifier.result_ready.emit(running)

    def _apply_process_state(self, running: object) -> None:
        self._process_worker_running = False
        if not isinstance(running, dict):
            return
        normalized_state = {
            key: [process.process_id for process in value]
            for key, value in running.items()
            if isinstance(value, list)
        }
        if normalized_state == self._running_processes:
            return
        self._running_processes = normalized_state
        self._apply_process_icons()

    def _apply_process_icons(self) -> None:
        for row, installation in enumerate(self.config.installations):
            item = self.installation_list.item(row)
            if item is None:
                continue
            item.setIcon(self._icon_for_installation(installation))
            tooltip = installation.exe_path
            process_count = len(self._process_ids_for_installation(installation))
            if process_count:
                tooltip = f"{tooltip}\n{self.tr('running_suffix', count=process_count)}"
            item.setToolTip(tooltip)

    def _process_ids_for_installation(self, installation: Installation) -> list[int]:
        normalized_path = self._normalize_exe_path(installation.exe_path)
        return self._running_processes.get(normalized_path, [])

    def _is_installation_running(self, installation: Installation) -> bool:
        return bool(self._process_ids_for_installation(installation))

    def _normalize_exe_path(self, exe_path: str) -> str:
        if not exe_path.strip():
            return ""
        try:
            return str(Path(exe_path).expanduser().resolve()).lower()
        except OSError:
            return str(Path(exe_path).expanduser()).lower()

    def _with_running_badge(self, icon: QIcon) -> QIcon:
        pixmap = icon.pixmap(QSize(64, 64))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor("#39d353"))
        painter.setPen(QPen(QColor("#f8fafc"), 3))
        painter.drawEllipse(42, 42, 18, 18)
        painter.end()
        return QIcon(pixmap)

    def _open_installation_context_menu(self, position) -> None:
        item = self.installation_list.itemAt(position)
        if item is None:
            return
        self.installation_list.setCurrentItem(item)
        installation = self._current_installation()
        if installation is None:
            return

        menu = QMenu(self.installation_list)
        launch_action = menu.addAction(self.tr("start"))
        launch_action.triggered.connect(self._launch_selected_installation)
        explorer_action = menu.addAction(self.tr("show_in_explorer"))
        explorer_action.triggered.connect(self._show_selected_installation_in_explorer)
        if self._is_installation_running(installation):
            stop_action = menu.addAction(self.tr("stop_process"))
            stop_action.triggered.connect(self._stop_selected_installation_processes)
        menu.exec(self.installation_list.mapToGlobal(position))

    def _show_selected_installation_in_explorer(self) -> None:
        installation = self._current_installation()
        if installation is None:
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
            subprocess.Popen(
                ["explorer.exe", f"/select,{exe_path}"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("show_in_explorer_failed_title"),
                self.tr("show_in_explorer_failed_message", error=error),
            )

    def _stop_selected_installation_processes(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        try:
            stopped = self.process_service.terminate_processes(installation.exe_path)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("process_stop_failed_title"),
                self.tr("process_stop_failed_message", error=error),
            )
            return
        self._refresh_process_state()
        self.statusBar().showMessage(
            self.tr("process_stop_status", name=installation.name, count=stopped),
            5000,
        )

    def _toggle_bini_conversion(self, checked: bool) -> None:
        if self._is_loading_cheat_controls or not checked:
            return
        installation = self._current_installation()
        if installation is None:
            return
        try:
            result = self._get_cheat_service().convert_bini_files(installation)
        except (OSError, ValueError) as error:
            self._is_loading_cheat_controls = True
            self.bini_toggle.setChecked(False)
            self._is_loading_cheat_controls = False
            QMessageBox.critical(
                self,
                self.tr("bini_convert_done_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return
        QMessageBox.information(
            self,
            self.tr("bini_convert_done_title"),
            self.tr("bini_convert_done_message", converted=result.converted),
        )
        self._sync_cheat_panel_to_installation()

    def _apply_cruise_charge_time(self, slider_value: int) -> None:
        self.cruise_charge_value_label.setText(
            self.tr("cruise_charge_value", value=f"{slider_value / 10:.1f}")
        )
        if self._is_loading_cheat_controls:
            return
        installation = self._current_installation()
        if installation is None:
            return
        try:
            value = self._get_cheat_service().set_cruise_charge_time(
                installation,
                slider_value / 10,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.tr("cruise_charge_done_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return
        self.statusBar().showMessage(
            self.tr("cruise_charge_done_message", value=f"{value:.1f}"),
            3000,
        )

    def _toggle_jump_timing(self, checked: bool) -> None:
        self.jump_timing_slider.setEnabled(checked)
        if self._is_loading_cheat_controls:
            return

        installation = self._current_installation()
        if installation is None:
            return

        try:
            if checked:
                value = self._get_cheat_service().set_jump_timing(installation, self.jump_timing_slider.value() / 10)
                self.statusBar().showMessage(
                    self.tr("jump_timing_done_message", value=f"{value:.1f}"),
                    3000,
                )
            else:
                restored = self._get_cheat_service().reset_jump_timing(installation)
                message = self.tr("jump_timing_reset_done") if restored else self.tr("jump_timing_reset_missing")
                self.statusBar().showMessage(message, 3000)
                self._sync_cheat_panel_to_installation()
        except (OSError, ValueError) as error:
            self._is_loading_cheat_controls = True
            self.jump_timing_toggle.setChecked(not checked)
            self.jump_timing_slider.setEnabled(not checked)
            self._is_loading_cheat_controls = False
            QMessageBox.critical(
                self,
                self.tr("jump_timing_done_title"),
                self.tr("mod_file_missing_message", error=error),
            )

    def _apply_jump_timing(self, slider_value: int) -> None:
        self.jump_timing_value_label.setText(
            self.tr("jump_timing_value", value=f"{slider_value / 10:.1f}")
        )
        if self._is_loading_cheat_controls or not self.jump_timing_toggle.isChecked():
            return

        installation = self._current_installation()
        if installation is None:
            return

        try:
            value = self._get_cheat_service().set_jump_timing(installation, slider_value / 10)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.tr("jump_timing_done_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return

        self.statusBar().showMessage(
            self.tr("jump_timing_done_message", value=f"{value:.1f}"),
            3000,
        )

    def _toggle_reveal_everything(self, checked: bool) -> None:
        if self._is_loading_cheat_controls:
            return
        installation = self._current_installation()
        if installation is None:
            return
        try:
            if checked:
                result = self._get_cheat_service().apply_reveal_everything(installation)
                self.statusBar().showMessage(
                    self.tr("reveal_done_message", count=result.changed_files),
                    4000,
                )
            else:
                restored = self._get_cheat_service().reset_reveal_everything(installation)
                message = self.tr("reveal_reset_done") if restored else self.tr("reveal_reset_missing")
                self.statusBar().showMessage(message, 4000)
        except (OSError, ValueError) as error:
            self._is_loading_cheat_controls = True
            self.reveal_toggle.setChecked(not checked)
            self._is_loading_cheat_controls = False
            QMessageBox.critical(
                self,
                self.tr("reveal_done_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return

    def _open_ship_info_dialog(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        try:
            dialog = ShipInfoDialog(installation, self._get_cheat_service(), self.translator, self)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("ship_info_error_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return
        dialog.exec()

    def _open_ship_handling_dialog(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        try:
            dialog = ShipHandlingDialog(installation, self._get_cheat_service(), self.translator, self)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("ship_handling_apply_error_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return
        dialog.exec()

    def _open_trade_routes_dialog(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        try:
            dialog = TradeRouteDialog(
                installation,
                self._get_trade_route_service(),
                self.translator,
                player_reputation=self._reputation_values_for_installation(installation.id),
                parent=self,
            )
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("trade_routes_error_title"),
                self.tr("mod_file_missing_message", error=error),
            )
            return
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, current=dialog: self._forget_trade_route_window(current))
        self._trade_route_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_trade_route_window(self, dialog: TradeRouteDialog) -> None:
        self._trade_route_windows = [window for window in self._trade_route_windows if window is not dialog]

    def _open_round_trip_dialog(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return

        dialog = TradeRouteRoundTripDialog(
            installation,
            self._get_trade_route_service(),
            self.translator,
            player_reputation=self._reputation_values_for_installation(installation.id),
            parent=self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, current=dialog: self._forget_round_trip_window(current))
        self._round_trip_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_round_trip_window(self, dialog: TradeRouteRoundTripDialog) -> None:
        self._round_trip_windows = [window for window in self._round_trip_windows if window is not dialog]

    def _open_reputation_dialog(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        factions = self._get_trade_route_service().faction_options(installation)
        if not factions:
            QMessageBox.information(self, self.tr("reputation_dialog_title"), self.tr("reputation_dialog_empty"))
            return
        dialog = ReputationDialog(
            factions,
            self._reputation_values_for_installation(installation.id),
            self.translator,
            self,
        )
        if not dialog.exec():
            return
        self._save_reputation_values_for_installation(installation.id, dialog.values())
        self.statusBar().showMessage(self.tr("reputation_saved_status", name=installation.name), 4000)

    def _reputation_values_for_installation(self, installation_id: str) -> dict[str, float]:
        values = self.config.faction_reputations.get(installation_id, {})
        if not isinstance(values, dict):
            return {}
        result: dict[str, float] = {}
        for nickname, reputation in values.items():
            try:
                result[str(nickname).strip().lower()] = max(-1.0, min(1.0, float(reputation)))
            except (TypeError, ValueError):
                continue
        return result

    def _save_reputation_values_for_installation(self, installation_id: str, values: dict[str, float]) -> None:
        self.config.faction_reputations[installation_id] = {
            str(nickname).strip().lower(): max(-1.0, min(1.0, float(reputation)))
            for nickname, reputation in values.items()
        }
        self._persist_config()

    def _reset_ship_handling(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return
        try:
            restored = self._get_cheat_service().reset_ship_handling(installation)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("ship_handling_apply_error_title"),
                self.tr("ship_handling_apply_error_message", error=error),
            )
            return
        message = self.tr("ship_handling_reset_sidebar_done") if restored else self.tr("ship_handling_reset_sidebar_missing")
        QMessageBox.information(self, self.tr("ship_handling_apply_done_title"), message)
        self._sync_cheat_panel_to_installation()

    def _open_help_wiki(self) -> None:
        QDesktopServices.openUrl(QUrl(self.HELP_WIKI_URL))
