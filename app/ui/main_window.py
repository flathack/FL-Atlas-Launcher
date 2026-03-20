from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo, QSize, Qt
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

from app.models.app_config import AppConfig
from app.models.installation import Installation
from app.resource_utils import resource_path
from app.services.config_service import ConfigService
from app.services.ini_service import IniService
from app.services.launcher_service import LauncherService
from app.services.resolution_service import ResolutionService
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, config_service: ConfigService) -> None:
        super().__init__()
        self.config_service = config_service
        self.config = AppConfig.from_dict(config_service.config.to_dict())
        self.icon_provider = QFileIconProvider()
        self.resolution_service = ResolutionService()
        self.ini_service = IniService()
        self.launcher_service = LauncherService(
            ini_service=self.ini_service,
            resolution_service=self.resolution_service,
        )

        self.setWindowTitle("FL Atlas Launcher")
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
        self.installation_list.setUniformItemSizes(True)
        self.installation_list.setIconSize(QSize(48, 48))
        self.installation_list.setGridSize(QSize(160, 110))
        self.installation_list.setSpacing(12)
        self.installation_list.setWordWrap(True)

        self.resolution_combo = QComboBox()
        self.launch_button = QPushButton("Freelancer starten")
        self.launch_button.setMinimumHeight(40)

        self._build_ui()
        self._connect_signals()
        self._populate_resolutions()
        self._populate_installations()
        self._update_launch_state()

    def _build_ui(self) -> None:
        toolbar = QToolBar("Hauptaktionen")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        settings_action = QAction("Installationen verwalten", self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        refresh_action = QAction("Aktualisieren", self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        headline = QLabel("Freelancer starten")
        headline.setObjectName("headline")
        subline = QLabel(
            "Waehle eine Installation und eine Aufloesung. "
            "Vor dem Start wird die passende PerfOptions.ini automatisch aktualisiert."
        )
        subline.setWordWrap(True)
        subline.setObjectName("subline")

        resolution_row = QWidget()
        resolution_layout = QHBoxLayout(resolution_row)
        resolution_layout.setContentsMargins(0, 0, 0, 0)
        resolution_layout.addWidget(QLabel("Aufloesung"))
        resolution_layout.addWidget(self.resolution_combo, 1)

        layout.addWidget(headline)
        layout.addWidget(subline)
        layout.addWidget(self.installation_list, 1)
        layout.addWidget(resolution_row)
        layout.addWidget(self.launch_button)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Konfiguration: {self.config_service.config_path}")

    def _connect_signals(self) -> None:
        self.installation_list.currentRowChanged.connect(self._on_installation_changed)
        self.launch_button.clicked.connect(self._launch_selected_installation)
        self.resolution_combo.currentTextChanged.connect(self._save_selected_resolution)

    def _populate_resolutions(self) -> None:
        unique_resolutions = self.resolution_service.available_resolutions()
        current_resolution = self.resolution_service.detect_current_resolution()
        self.resolution_combo.clear()
        self.resolution_combo.addItems(unique_resolutions)

        if current_resolution and current_resolution in unique_resolutions:
            self.resolution_combo.setCurrentText(current_resolution)
            self.config.selected_resolution = current_resolution
        elif self.config.selected_resolution in unique_resolutions:
            self.resolution_combo.setCurrentText(self.config.selected_resolution)
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
        dialog = SettingsDialog(self.config.installations, self)
        if dialog.exec():
            self.config.installations = dialog.installations
            self._persist_config()
            self._populate_installations()
            self.statusBar().showMessage("Installationen gespeichert", 4000)

    def _refresh_view(self) -> None:
        self.config = AppConfig.from_dict(self.config_service.load().to_dict())
        self._populate_resolutions()
        self._populate_installations()
        self.statusBar().showMessage("Ansicht aktualisiert", 3000)

    def _save_selected_resolution(self, resolution: str) -> None:
        self.config.selected_resolution = resolution
        self._persist_config()

    def _persist_config(self) -> None:
        self.config_service.save(self.config)

    def _launch_selected_installation(self) -> None:
        installation = self._current_installation()
        if installation is None:
            return

        if not self.resolution_combo.currentText():
            QMessageBox.warning(
                self,
                "Keine Aufloesung",
                "Es ist aktuell keine gueltige Aufloesung ausgewaehlt.",
            )
            return

        exe_path = Path(installation.exe_path)
        if not exe_path.exists():
            QMessageBox.warning(
                self,
                "Datei nicht gefunden",
                "Die ausgewaehlte Freelancer.exe existiert nicht mehr.",
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
                "Ungueltige Aufloesung",
                "Die ausgewaehlte Aufloesung konnte nicht verarbeitet werden.",
            )
            return
        except OSError as error:
            QMessageBox.critical(
                self,
                "PerfOptions Fehler",
                f"Die PerfOptions.ini konnte nicht geschrieben werden:\n{error}",
            )
            return

        try:
            self.launcher_service.launch(installation)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Start fehlgeschlagen",
                f"Freelancer konnte nicht gestartet werden:\n{error}",
            )
            return

        message = (
            f"{installation.name} mit {self.resolution_combo.currentText()} gestartet. "
            f"PerfOptions: {perf_path}"
        )
        if backup_path is not None:
            message += f" | Backup: {backup_path.name}"
        self.statusBar().showMessage(message, 8000)
