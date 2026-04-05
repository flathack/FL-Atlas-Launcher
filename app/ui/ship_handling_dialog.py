from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSize, QThread, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.cheat_service import CheatService, ShipInfoRow
from app.services.ship_render_service import ShipRenderService
from app.ui.ship_preview_dialog import ShipPreviewDialog


class _IconLoaderWorker(QObject):
    """Renders ship icons in a background thread, emitting one signal per icon."""
    icon_ready = Signal(int, str)  # (row_index, icon_path)
    finished = Signal()

    def __init__(
        self,
        items: list[tuple[int, str, str]],
        game_root: Path,
        render_service: ShipRenderService,
    ) -> None:
        super().__init__()
        self._items = items  # [(row, nickname, da_archetype), ...]
        self._game_root = game_root
        self._render_service = render_service

    def run(self) -> None:
        for row, nickname, da_archetype in self._items:
            if QThread.currentThread().isInterruptionRequested():
                break
            path = self._render_service.get_icon_path(self._game_root, nickname, da_archetype)
            if path and path.exists():
                self.icon_ready.emit(row, str(path))
        self.finished.emit()


class ShipInfoDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        cheat_service: CheatService,
        translator: Translator,
        ship_render_service: ShipRenderService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.cheat_service = cheat_service
        self.translator = translator
        self._ship_render_service = ship_render_service
        self._game_root: Path | None = None
        self._ship_rows: list[ShipInfoRow] = []
        self._icon_thread: QThread | None = None
        try:
            self._game_root = cheat_service.resolve_game_root(installation)
        except OSError:
            pass

        self.setWindowTitle(self.tr("ship_info_title", name=installation.name))
        self.resize(980, 640)

        self.info_label = QLabel(self.tr("ship_info_hint"))
        self.info_label.setWordWrap(True)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("ship_info_search_placeholder"))

        self.table = QTableWidget(0, 5)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QSize(32, 32))
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("ship_column_name"),
                self.tr("ship_info_column_armor"),
                self.tr("ship_info_column_cargo"),
                self.tr("ship_info_column_location"),
                self.tr("ship_info_column_price"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)

        self.reload_button = QPushButton(self.tr("refresh"))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        self._build_ui()
        self._connect_signals()
        self._load_profiles()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.addWidget(self.info_label)
        root_layout.addWidget(self.search_edit)
        root_layout.addWidget(self.table, 1)
        root_layout.addWidget(self.reload_button)
        root_layout.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.reload_button.clicked.connect(self._load_profiles)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.table.itemDoubleClicked.connect(lambda _: self._open_ship_preview())
        self.button_box.rejected.connect(self.reject)

    def _load_profiles(self) -> None:
        self._stop_icon_loader()
        self._ship_rows = self.cheat_service.ship_info_rows(self.installation)
        profiles = self._ship_rows

        self.table.setRowCount(len(profiles))
        icon_jobs: list[tuple[int, str, str]] = []
        for row, profile in enumerate(profiles):
            item = QTableWidgetItem(self._display_text(profile))
            item.setData(Qt.ItemDataRole.UserRole, profile.nickname)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)
            if profile.da_archetype:
                icon_jobs.append((row, profile.nickname, profile.da_archetype))

            armor_item = QTableWidgetItem(f"{profile.armor:,}".replace(",", "."))
            armor_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            armor_item.setFlags(armor_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, armor_item)

            cargo_item = QTableWidgetItem(str(profile.cargo_capacity))
            cargo_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cargo_item.setFlags(cargo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, cargo_item)

            locations_item = QTableWidgetItem("\n".join(profile.locations))
            locations_item.setFlags(locations_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, locations_item)

            price_item = QTableWidgetItem(profile.price_display)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setFlags(price_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, price_item)

        self._apply_filter(self.search_edit.text())
        self.table.resizeRowsToContents()
        self._start_icon_loader(icon_jobs)

    def _start_icon_loader(self, jobs: list[tuple[int, str, str]]) -> None:
        if not jobs or not self._ship_render_service or not self._game_root:
            return
        thread = QThread(self)
        worker = _IconLoaderWorker(jobs, self._game_root, self._ship_render_service)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.icon_ready.connect(self._on_icon_ready)
        worker.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, '_icon_thread', None))
        thread._worker_ref = worker  # type: ignore[attr-defined]
        self._icon_thread = thread
        thread.start()

    def _stop_icon_loader(self) -> None:
        if self._icon_thread is not None:
            self._icon_thread.requestInterruption()
            self._icon_thread.quit()
            self._icon_thread.wait(2000)
            self._icon_thread = None

    def _on_icon_ready(self, row: int, icon_path: str) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            item.setIcon(QIcon(icon_path))

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        for row in range(self.table.rowCount()):
            ship_item = self.table.item(row, 0)
            location_item = self.table.item(row, 3)
            display_text = ship_item.text().lower() if ship_item is not None else ""
            nickname = str(ship_item.data(Qt.ItemDataRole.UserRole) or "").lower() if ship_item is not None else ""
            locations = location_item.text().lower() if location_item is not None else ""
            self.table.setRowHidden(
                row,
                bool(query and query not in display_text and query not in nickname and query not in locations),
            )

    def _ship_icon(self, profile: ShipInfoRow) -> QIcon | None:
        """Synchronous icon lookup — only returns cached icons."""
        if not self._ship_render_service or not self._game_root or not profile.da_archetype:
            return None
        icon_path = self._ship_render_service._icon_dir / f"{profile.nickname}.png"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return None

    def _open_ship_preview(self) -> None:
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self._ship_rows):
            return
        ship = self._ship_rows[current_row]
        if not self._ship_render_service or not self._game_root:
            return
        dialog = ShipPreviewDialog(ship, self._game_root, self._ship_render_service, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()

    def _display_text(self, profile: object) -> str:
        display_name = str(getattr(profile, "display_name", "") or "").strip()
        nickname = str(getattr(profile, "nickname", "") or "").strip()
        if not display_name or display_name.lower() == nickname.lower():
            return nickname
        return f"{display_name} ({nickname})"


class ShipHandlingDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        cheat_service: CheatService,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.cheat_service = cheat_service
        self.translator = translator

        self.setWindowTitle(self.tr("ship_handling_title", name=installation.name))
        self.resize(980, 640)

        self.info_label = QLabel(self.tr("ship_handling_hint"))
        self.info_label.setWordWrap(True)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("ship_handling_search_placeholder"))

        self.table = QTableWidget(0, 2)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("ship_column_name"),
                self.tr("ship_column_target"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.apply_button = QPushButton(self.tr("apply_ship_handling"))
        self.reset_button = QPushButton(self.tr("reset_ship_handling"))
        self.reload_button = QPushButton(self.tr("refresh"))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        self._build_ui()
        self._connect_signals()
        self._load_profiles()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        action_row = QHBoxLayout()
        action_row.addWidget(self.apply_button)
        action_row.addWidget(self.reset_button)
        action_row.addWidget(self.reload_button)
        action_row.addStretch(1)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(self.info_label)
        root_layout.addWidget(self.search_edit)
        root_layout.addWidget(self.table, 1)
        root_layout.addLayout(action_row)
        root_layout.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.apply_button.clicked.connect(self._apply_mappings)
        self.reset_button.clicked.connect(self._reset_mappings)
        self.reload_button.clicked.connect(self._load_profiles)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.button_box.rejected.connect(self.reject)

    def _load_profiles(self) -> None:
        profiles = self.cheat_service.ship_handling_profiles(self.installation)
        mappings = self.cheat_service.ship_handling_mappings(self.installation)
        ship_options = [
            (profile.nickname, self._display_text(profile))
            for profile in profiles
        ]

        self.table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            item = QTableWidgetItem(self._display_text(profile))
            item.setData(Qt.ItemDataRole.UserRole, profile.nickname)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)

            combo = QComboBox()
            combo.setEditable(False)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(28)
            combo.addItem("", "")
            for nickname, display_text in ship_options:
                combo.addItem(display_text, nickname)
            selected_nickname = mappings.get(profile.nickname, "")
            current_index = max(0, combo.findData(selected_nickname))
            combo.setCurrentIndex(current_index)
            self.table.setCellWidget(row, 1, combo)

        self._apply_filter(self.search_edit.text())
        self.table.resizeRowsToContents()

    def _collect_mappings(self) -> dict[str, str]:
        mappings: dict[str, str] = {}
        for row in range(self.table.rowCount()):
            nickname_item = self.table.item(row, 0)
            target_combo = self.table.cellWidget(row, 1)
            if nickname_item is None or not isinstance(target_combo, QComboBox):
                continue
            nickname = str(nickname_item.data(Qt.ItemDataRole.UserRole) or "").strip()
            target = str(target_combo.currentData() or "").strip()
            if nickname and target:
                mappings[nickname] = target
        return mappings

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        for row in range(self.table.rowCount()):
            nickname_item = self.table.item(row, 0)
            display_text = nickname_item.text().lower() if nickname_item is not None else ""
            nickname = str(nickname_item.data(Qt.ItemDataRole.UserRole) or "").lower() if nickname_item is not None else ""
            self.table.setRowHidden(row, bool(query and query not in display_text and query not in nickname))

    def _display_text(self, profile: object) -> str:
        display_name = str(getattr(profile, "display_name", "") or "").strip()
        nickname = str(getattr(profile, "nickname", "") or "").strip()
        if not display_name or display_name.lower() == nickname.lower():
            return nickname
        return f"{display_name} ({nickname})"

    def _apply_mappings(self) -> None:
        try:
            result = self.cheat_service.apply_ship_handling(self.installation, self._collect_mappings())
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.tr("ship_handling_apply_error_title"),
                self.tr("ship_handling_apply_error_message", error=error),
            )
            return

        QMessageBox.information(
            self,
            self.tr("ship_handling_apply_done_title"),
            self.tr("ship_handling_done_message", count=result.changed),
        )
        self._load_profiles()

    def _reset_mappings(self) -> None:
        try:
            restored = self.cheat_service.reset_ship_handling(self.installation)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("ship_handling_apply_error_title"),
                self.tr("ship_handling_apply_error_message", error=error),
            )
            return

        if not restored:
            QMessageBox.information(
                self,
                self.tr("ship_handling_apply_done_title"),
                self.tr("ship_handling_nothing_to_reset"),
            )
            return

        QMessageBox.information(
            self,
            self.tr("ship_handling_apply_done_title"),
            self.tr("ship_handling_reset_done"),
        )
        self._load_profiles()