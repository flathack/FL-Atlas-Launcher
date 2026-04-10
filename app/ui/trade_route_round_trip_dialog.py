from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal
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
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.trade_route_service import TradeRouteLoopRow, TradeRouteService
from app.ui.trade_route_round_trip_detail_dialog import TradeRouteRoundTripDetailDialog


_MAX_TABLE_TEXT_LENGTH = 60


def _truncate_table_text(value: object, max_length: int = _MAX_TABLE_TEXT_LENGTH) -> str:
    text = str(value)
    return text if len(text) <= max_length else f"{text[:max_length - 1]}…"


def _format_seconds(value: int | None) -> str:
    if value is None:
        return "-"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}:{seconds:02d}"


class _RoundTripWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)

    def __init__(
        self,
        service: TradeRouteService,
        installation: Installation,
        cargo_capacity: int,
        max_jumps: int,
        leg_count: int,
        player_reputation: dict[str, float],
    ) -> None:
        super().__init__()
        self._service = service
        self._installation = installation
        self._cargo_capacity = cargo_capacity
        self._max_jumps = max_jumps
        self._leg_count = leg_count
        self._player_reputation = player_reputation

    def run(self) -> None:
        loops = self._service.best_round_trips(
            self._installation,
            cargo_capacity=self._cargo_capacity,
            max_jumps=self._max_jumps,
            leg_count=self._leg_count,
            player_reputation=self._player_reputation,
            progress_callback=self.progress.emit,
        )
        self.finished.emit(loops)


class TradeRouteRoundTripDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        trade_route_service: TradeRouteService,
        translator: Translator,
        *,
        initial_cargo_capacity: int = 0,
        initial_max_jumps: int = 1,
        initial_leg_count: int = 4,
        player_reputation: dict[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.trade_route_service = trade_route_service
        self.translator = translator
        self._loops: list[TradeRouteLoopRow] = []
        self._detail_windows: list[TradeRouteRoundTripDetailDialog] = []
        self._worker_thread: QThread | None = None
        self._initial_cargo_capacity = max(0, int(initial_cargo_capacity))
        self._initial_max_jumps = max(0, int(initial_max_jumps))
        self._initial_leg_count = max(3, min(int(initial_leg_count), 6))
        self.player_reputation = dict(player_reputation or {})

        self.setWindowTitle(self.tr("trade_round_trip_title", name=installation.name))
        self.resize(1180, 700)
        self.setModal(False)

        self.ship_combo = QComboBox()
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(0, 20)
        self.jump_spin.setValue(self._initial_max_jumps)
        self.leg_spin = QSpinBox()
        self.leg_spin.setRange(3, 6)
        self.leg_spin.setValue(self._initial_leg_count)
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("trade_round_trip_column_start"),
                self.tr("trade_round_trip_column_route"),
                self.tr("trade_round_trip_column_goods"),
                self.tr("trade_round_trip_column_jumps"),
                self.tr("trade_round_trip_column_profit"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("trade_routes_search"))
        self.search_input.setClearButtonEnabled(True)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.hint_label = QLabel(self.tr("trade_round_trip_detail_hint"))
        self.hint_label.setWordWrap(True)

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
        self._refresh_loops()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        filters = QWidget()
        form = QFormLayout(filters)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.tr("trade_routes_ship"), self.ship_combo)
        form.addRow(self.tr("trade_routes_max_jumps"), self.jump_spin)
        form.addRow(self.tr("trade_round_trip_leg_count"), self.leg_spin)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.search_input)
        root.addWidget(self.loading_label)
        root.addWidget(self.progress_bar)
        root.addWidget(self.table, 1)
        root.addWidget(self.summary_label)
        root.addWidget(self.hint_label)
        root.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_loops)
        self.ship_combo.currentIndexChanged.connect(lambda _index: self._refresh_loops())
        self.jump_spin.valueChanged.connect(lambda _value: self._refresh_loops())
        self.leg_spin.valueChanged.connect(lambda _value: self._refresh_loops())
        self.table.currentCellChanged.connect(self._update_summary)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_detail_dialog())
        self.search_input.textChanged.connect(self._apply_filter)
        self.button_box.rejected.connect(self.close)

    def _load_ships(self) -> None:
        options = self.trade_route_service.ship_options(self.installation)
        self.ship_combo.clear()
        selected_index = -1
        for index, option in enumerate(options):
            self.ship_combo.addItem(option.label, option.cargo_capacity)
            if option.cargo_capacity == self._initial_cargo_capacity and selected_index < 0:
                selected_index = index
        if selected_index >= 0:
            self.ship_combo.setCurrentIndex(selected_index)

    def _refresh_loops(self) -> None:
        if self._worker_thread is not None:
            return
        cargo_capacity = int(self.ship_combo.currentData() or 0)
        max_jumps = int(self.jump_spin.value())
        leg_count = int(self.leg_spin.value())
        self._set_loading(True)

        self._worker_thread = QThread(self)
        worker = _RoundTripWorker(
            self.trade_route_service,
            self.installation,
            cargo_capacity,
            max_jumps,
            leg_count,
            self.player_reputation,
        )
        worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.finished.connect(self._on_loops_ready)
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
        self.leg_spin.setEnabled(not loading)

    def _on_loops_ready(self, loops: list[TradeRouteLoopRow]) -> None:
        self._loops = loops
        self.table.setRowCount(len(self._loops))
        for row_index, loop in enumerate(self._loops):
            values = [
                loop.start_system,
                loop.route_text,
                " | ".join(loop.commodities),
                str(loop.total_jumps),
                f"{loop.total_profit:,}".replace(",", ".") + " $",
            ]
            for column, value in enumerate(values):
                full_text = str(value)
                item = QTableWidgetItem(_truncate_table_text(full_text))
                item.setToolTip(full_text)
                if column in {3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, loop)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        self._set_loading(False)
        self._apply_filter()
        self._update_summary()

    def _update_summary(self, *_args: object) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
                current_row = 0
            else:
                self.summary_label.setText(self.tr("trade_round_trip_no_routes"))
                return
        item = self.table.item(current_row, 0)
        loop = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(loop, TradeRouteLoopRow):
            self.summary_label.setText(self.tr("trade_round_trip_no_routes"))
            return
        self.summary_label.setText(
            self.tr(
                "trade_round_trip_summary",
                legs=len(loop.legs),
                cargo=loop.cargo_capacity,
                jumps=loop.total_jumps,
                profit=f"{loop.total_profit:,}".replace(",", "."),
                time=_format_seconds(loop.travel_time_seconds),
                ppm=(f"{loop.profit_per_minute:,}".replace(",", ".") if loop.profit_per_minute is not None else "-"),
            )
        )

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

    def _open_detail_dialog(self) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            return
        item = self.table.item(current_row, 0)
        loop = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(loop, TradeRouteLoopRow):
            return

        dialog = TradeRouteRoundTripDetailDialog(
            self.installation,
            loop,
            self.trade_route_service,
            self.translator,
            parent=self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, current=dialog: self._forget_detail_dialog(current))
        self._detail_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_detail_dialog(self, dialog: TradeRouteRoundTripDetailDialog) -> None:
        self._detail_windows = [window for window in self._detail_windows if window is not dialog]
