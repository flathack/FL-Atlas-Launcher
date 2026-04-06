"""Dialog showing a ship preview image and stats for a selected ship."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.services.cheat_service import ShipInfoRow
from app.services.ship_render_service import ShipRenderService

_SHIP_CLASS_KEYS = {
    1: "ship_class_light",
    2: "ship_class_heavy",
    3: "ship_class_super_heavy",
}


class _ShipPreviewRenderWorker(QObject):
    progress_changed = Signal(int)
    finished = Signal(object)

    def __init__(self, ship: ShipInfoRow, game_root: Path, render_service: ShipRenderService) -> None:
        super().__init__()
        self._ship = ship
        self._game_root = game_root
        self._render_service = render_service

    def run(self) -> None:
        _icon_path, preview_path = self._render_service.ensure_ship_assets(
            self._game_root,
            self._ship.nickname,
            self._ship.da_archetype,
            progress_callback=self.progress_changed.emit,
        )
        self.finished.emit(preview_path)


class ShipPreviewDialog(QDialog):
    """Shows a rendered preview image and key stats for a single ship."""

    def __init__(
        self,
        ship: ShipInfoRow,
        game_root: Path,
        render_service: ShipRenderService,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.ship = ship
        self.game_root = game_root
        self.render_service = render_service
        self._render_thread: QThread | None = None
        self._render_worker: _ShipPreviewRenderWorker | None = None
        self.setWindowTitle(translator.text("ship_preview_title", name=ship.display_name))
        self.setMinimumWidth(460)

        # ---- preview image ------------------------------------------------
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setWordWrap(True)
        self.generate_button = QPushButton(translator.text("ship_preview_generate"))
        self.generate_button.setProperty("variant", "primary")
        self.generate_button.setMinimumHeight(38)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self._refresh_preview()

        # ---- stats form ---------------------------------------------------
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        # Ship type
        type_key = f"ship_type_{ship.ship_type}" if ship.ship_type else "ship_type_unknown"
        type_text = translator.text(type_key) if ship.ship_type else translator.text("ship_type_unknown")
        form.addRow(translator.text("ship_preview_type"), QLabel(type_text))

        # Ship class
        class_key = _SHIP_CLASS_KEYS.get(ship.ship_class, "")
        class_text = translator.text(class_key) if class_key else "-"
        form.addRow(translator.text("ship_preview_class"), QLabel(class_text))

        # Armor
        form.addRow(translator.text("ship_preview_armor"), QLabel(f"{ship.armor:,}".replace(",", ".")))

        # Cargo
        form.addRow(translator.text("ship_preview_cargo"), QLabel(str(ship.cargo_capacity)))

        # Nanobots
        form.addRow(translator.text("ship_preview_nanobots"), QLabel(str(ship.nanobot_limit)))

        # Shield batteries
        form.addRow(translator.text("ship_preview_shield_batteries"), QLabel(str(ship.shield_battery_limit)))

        # Price
        form.addRow(translator.text("ship_preview_price"), QLabel(ship.price_display))

        # Locations
        if ship.locations:
            loc_text = "\n".join(ship.locations)
            loc_label = QLabel(loc_text)
            loc_label.setWordWrap(True)
            form.addRow(translator.text("ship_preview_locations"), loc_label)

        stats_widget = QWidget()
        stats_widget.setLayout(form)

        # ---- layout -------------------------------------------------------
        preview_panel = QVBoxLayout()
        preview_panel.addWidget(self.preview_label, 1)
        preview_panel.addWidget(self.progress_bar)
        preview_panel.addWidget(self.generate_button)

        body = QHBoxLayout()
        body.addLayout(preview_panel)
        body.addWidget(stats_widget, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        self.generate_button.clicked.connect(self._generate_preview)

        root = QVBoxLayout(self)
        root.addLayout(body)
        root.addWidget(button_box)

    def _refresh_preview(self) -> None:
        preview_path = self.render_service.preview_cache_path(self.ship.nickname)
        if preview_path.exists():
            pixmap = QPixmap(str(preview_path))
            if not pixmap.isNull():
                self.preview_label.setPixmap(pixmap)
                self.preview_label.setText("")
                return
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(self.translator.text("ship_preview_not_generated"))

    def _generate_preview(self) -> None:
        if self._render_thread is not None:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.generate_button.setEnabled(False)
        self.generate_button.setText(self.translator.text("ship_preview_generating"))
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(self.translator.text("ship_preview_generating"))

        self._render_thread = QThread(self)
        self._render_worker = _ShipPreviewRenderWorker(self.ship, self.game_root, self.render_service)
        self._render_worker.moveToThread(self._render_thread)
        self._render_thread.started.connect(self._render_worker.run)
        self._render_worker.progress_changed.connect(self.progress_bar.setValue)
        self._render_worker.finished.connect(self._on_preview_generated)
        self._render_worker.finished.connect(self._render_thread.quit)
        self._render_worker.finished.connect(self._render_worker.deleteLater)
        self._render_thread.finished.connect(self._render_thread.deleteLater)
        self._render_thread.finished.connect(self._clear_render_state)
        self._render_thread.start()

    def _on_preview_generated(self, preview_path: object) -> None:
        self.progress_bar.setValue(100)
        path = preview_path if isinstance(preview_path, Path) else None
        if path is not None and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview_label.setPixmap(pixmap)
                self.preview_label.setText("")
                return
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(self.translator.text("ship_preview_render_failed"))

    def _clear_render_state(self) -> None:
        self._render_thread = None
        self._render_worker = None
        self.generate_button.setEnabled(True)
        self.generate_button.setText(self.translator.text("ship_preview_generate"))
        self.progress_bar.setVisible(False)
