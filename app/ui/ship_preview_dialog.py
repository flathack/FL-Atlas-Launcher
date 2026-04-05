"""Dialog showing a ship preview image and stats for a selected ship."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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
        self.setWindowTitle(translator.text("ship_preview_title", name=ship.display_name))
        self.setMinimumWidth(460)

        # ---- preview image ------------------------------------------------
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_path = render_service.get_preview_path(game_root, ship.nickname, ship.da_archetype)
        if preview_path and preview_path.exists():
            pixmap = QPixmap(str(preview_path))
            preview_label.setPixmap(pixmap)
        else:
            preview_label.setText(translator.text("ship_preview_render_failed"))

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
        body = QHBoxLayout()
        body.addWidget(preview_label)
        body.addWidget(stats_widget, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)

        root = QVBoxLayout(self)
        root.addLayout(body)
        root.addWidget(button_box)
