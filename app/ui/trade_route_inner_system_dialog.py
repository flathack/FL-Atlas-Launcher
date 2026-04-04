from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.trade_route_service import TradeRouteRow, TradeRouteService
from app.ui.trade_route_preview_dialog import TradeRoutePreviewDialog


class TradeRouteInnerSystemDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        trade_route_service: TradeRouteService,
        translator: Translator,
        *,
        player_reputation: dict[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.trade_route_service = trade_route_service
        self.translator = translator
        self.player_reputation = dict(player_reputation or {})
        self._routes: list[TradeRouteRow] = []
        self._preview_windows: list[TradeRoutePreviewDialog] = []

        self.setWindowTitle(self.tr("trade_inner_system_title", name=installation.name))
        self.resize(1240, 720)
        self.setModal(False)

        self.ship_combo = QComboBox()
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 8)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("trade_routes_column_preview"),
                self.tr("trade_routes_column_source"),
                self.tr("trade_routes_column_buy"),
                self.tr("trade_routes_column_sell"),
                self.tr("trade_routes_column_commodity"),
                self.tr("trade_routes_column_unit_profit"),
                self.tr("trade_routes_column_cargo"),
                self.tr("trade_routes_column_total_profit"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        self._build_ui()
        self._connect_signals()
        self._load_ships()
        self._refresh_routes()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        filters = QWidget()
        form = QFormLayout(filters)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.tr("trade_routes_ship"), self.ship_combo)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.table, 1)
        root.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_routes)
        self.ship_combo.currentIndexChanged.connect(lambda _index: self._refresh_routes())
        self.button_box.rejected.connect(self.close)

    def _load_ships(self) -> None:
        options = self.trade_route_service.ship_options(self.installation)
        self.ship_combo.clear()
        for option in options:
            self.ship_combo.addItem(option.label, option.cargo_capacity)

    def _refresh_routes(self) -> None:
        cargo_capacity = int(self.ship_combo.currentData() or 0)
        self._routes = self.trade_route_service.best_inner_system_routes(
            self.installation,
            cargo_capacity=cargo_capacity,
            player_reputation=self.player_reputation,
        )
        self.table.setRowCount(len(self._routes))
        eye_icon = self._build_eye_icon()
        for row_index, route in enumerate(self._routes):
            button = QToolButton(self.table)
            button.setIcon(eye_icon)
            button.setToolTip(self.tr("trade_routes_preview_open"))
            button.clicked.connect(lambda _checked=False, current_route=route: self._open_preview(current_route))
            self.table.setCellWidget(row_index, 0, button)

            values = [
                route.source_system,
                route.buy_base,
                route.sell_base,
                route.commodity,
                f"{route.profit_per_unit:,}".replace(",", ".") + " $",
                f"{route.cargo_capacity:,}".replace(",", "."),
                f"{route.total_profit:,}".replace(",", ".") + " $",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if offset in {5, 6, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, route)
                self.table.setItem(row_index, offset, item)

        self.table.resizeColumnsToContents()

    def _open_preview(self, route: TradeRouteRow) -> None:
        preview_data = self.trade_route_service.build_route_preview(self.installation, route)
        dialog = TradeRoutePreviewDialog(preview_data, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, current=dialog: self._forget_preview_window(current))
        self._preview_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_preview_window(self, dialog: TradeRoutePreviewDialog) -> None:
        self._preview_windows = [window for window in self._preview_windows if window is not dialog]

    def _build_eye_icon(self) -> QIcon:
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#cbd5e1"), 1.6))
        painter.drawEllipse(3, 6, 14, 8)
        painter.setBrush(QColor("#38bdf8"))
        painter.drawEllipse(8, 8, 4, 4)
        painter.end()
        return QIcon(pixmap)
