from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
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


_MAX_TABLE_TEXT_LENGTH = 30


def _truncate_table_text(value: object, max_length: int = _MAX_TABLE_TEXT_LENGTH) -> str:
    text = str(value)
    return text if len(text) <= max_length else f"{text[:max_length - 1]}…"


class _RouteWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)

    def __init__(
        self,
        service: TradeRouteService,
        installation: Installation,
        cargo_capacity: int,
        max_jumps: int,
        player_reputation: dict[str, float],
    ) -> None:
        super().__init__()
        self._service = service
        self._installation = installation
        self._cargo_capacity = cargo_capacity
        self._max_jumps = max_jumps
        self._player_reputation = player_reputation

    def run(self) -> None:
        routes = self._service.best_routes_by_system(
            self._installation,
            cargo_capacity=self._cargo_capacity,
            max_jumps=self._max_jumps,
            player_reputation=self._player_reputation,
            progress_callback=self.progress.emit,
        )
        self.finished.emit(routes)


class TradeRouteDialog(QDialog):
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
        self._worker_thread: QThread | None = None

        self.setWindowTitle(self.tr("trade_routes_title", name=installation.name))
        self.resize(1240, 720)
        self.setModal(False)

        self.ship_combo = QComboBox()
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(0, 20)
        self.jump_spin.setValue(3)
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 9)
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
                self.tr("trade_routes_column_jumps"),
                self.tr("trade_routes_column_unit_profit"),
                self.tr("trade_routes_column_cargo"),
                self.tr("trade_routes_column_total_profit"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("trade_routes_search"))
        self.search_input.setClearButtonEnabled(True)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)

        self.loading_label = QLabel(self.tr("trade_routes_loading"))
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)

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
        form.addRow(self.tr("trade_routes_max_jumps"), self.jump_spin)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.search_input)
        root.addWidget(self.loading_label)
        root.addWidget(self.progress_bar)
        root.addWidget(self.table, 1)
        root.addWidget(self.path_label)
        root.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_routes)
        self.ship_combo.currentIndexChanged.connect(lambda _index: self._refresh_routes())
        self.jump_spin.valueChanged.connect(lambda _value: self._refresh_routes())
        self.table.currentCellChanged.connect(self._update_path_label)
        self.search_input.textChanged.connect(self._apply_filter)
        self.button_box.rejected.connect(self.close)

    def _load_ships(self) -> None:
        options = self.trade_route_service.ship_options(self.installation)
        self.ship_combo.clear()
        for option in options:
            self.ship_combo.addItem(option.label, option.cargo_capacity)

    def _refresh_routes(self) -> None:
        if self._worker_thread is not None:
            return
        cargo_capacity = int(self.ship_combo.currentData() or 0)
        max_jumps = int(self.jump_spin.value())
        self._set_loading(True)

        self._worker_thread = QThread(self)
        worker = _RouteWorker(
            self.trade_route_service,
            self.installation,
            cargo_capacity,
            max_jumps,
            self.player_reputation,
        )
        worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.finished.connect(self._on_routes_ready)
        worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(lambda: setattr(self, "_worker_thread", None))
        self._worker_thread._worker_ref = worker  # type: ignore[attr-defined]
        self._worker_thread.start()

    def _set_loading(self, loading: bool) -> None:
        self.loading_label.setVisible(loading)
        self.progress_bar.setVisible(loading)
        self.table.setVisible(not loading)
        self.refresh_button.setEnabled(not loading)
        self.ship_combo.setEnabled(not loading)
        self.jump_spin.setEnabled(not loading)

    def _on_routes_ready(self, routes: list[TradeRouteRow]) -> None:
        self._routes = routes
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
                f"{route.target_system} -> {route.sell_base}",
                route.commodity,
                str(route.jumps),
                f"{route.profit_per_unit:,}".replace(",", ".") + " $",
                f"{route.cargo_capacity:,}".replace(",", "."),
                f"{route.total_profit:,}".replace(",", ".") + " $",
            ]
            for offset, value in enumerate(values, start=1):
                full_text = str(value)
                item = QTableWidgetItem(_truncate_table_text(full_text))
                item.setToolTip(full_text)
                if offset in {5, 6, 7, 8}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, route)
                self.table.setItem(row_index, offset, item)

        self.table.resizeColumnsToContents()
        self._set_loading(False)
        self._apply_filter()
        self._update_path_label()

    def _update_path_label(self, *_args: object) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
                current_row = 0
            else:
                self.path_label.setText(self.tr("trade_routes_no_routes"))
                return
        item = self.table.item(current_row, 1)
        route = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(route, TradeRouteRow) or not route.path:
            self.path_label.setText(self.tr("trade_routes_path", path="-"))
            return
        self.path_label.setText(self.tr("trade_routes_path", path=" -> ".join(route.path)))

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

    def _apply_filter(self) -> None:
        text = self.search_input.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            match = any(
                text in (self.table.item(row, col).text().lower() if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not match)

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
