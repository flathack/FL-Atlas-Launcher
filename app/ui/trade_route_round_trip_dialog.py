from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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


class TradeRouteRoundTripDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        trade_route_service: TradeRouteService,
        translator: Translator,
        *,
        initial_cargo_capacity: int = 0,
        initial_max_jumps: int = 3,
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
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.hint_label = QLabel(self.tr("trade_round_trip_detail_hint"))
        self.hint_label.setWordWrap(True)

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
        cargo_capacity = int(self.ship_combo.currentData() or 0)
        self._loops = self.trade_route_service.best_round_trips(
            self.installation,
            cargo_capacity=cargo_capacity,
            max_jumps=int(self.jump_spin.value()),
            leg_count=int(self.leg_spin.value()),
            player_reputation=self.player_reputation,
        )
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
                item = QTableWidgetItem(value)
                if column in {3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, loop)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
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
            )
        )

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