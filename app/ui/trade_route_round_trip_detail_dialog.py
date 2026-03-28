from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.trade_route_service import TradeRouteLoopRow, TradeRouteRow, TradeRouteService
from app.ui.widgets.trade_route_preview_widget import TradeRoutePreviewWidget


class TradeRouteRoundTripDetailDialog(QDialog):
    def __init__(
        self,
        installation: Installation,
        loop: TradeRouteLoopRow,
        trade_route_service: TradeRouteService,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.loop = loop
        self.trade_route_service = trade_route_service
        self.translator = translator

        self.setWindowTitle(self.tr("trade_round_trip_detail_title", route=loop.route_text))
        self.resize(1480, 880)
        self.setModal(False)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        self.leg_table = QTableWidget(0, 8)
        self.leg_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.leg_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.leg_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.leg_table.setHorizontalHeaderLabels(
            [
                self.tr("trade_round_trip_detail_column_leg"),
                self.tr("trade_round_trip_detail_column_commodity"),
                self.tr("trade_round_trip_detail_column_buy_at"),
                self.tr("trade_round_trip_detail_column_sell_at"),
                self.tr("trade_round_trip_detail_column_buy_price"),
                self.tr("trade_round_trip_detail_column_sell_price"),
                self.tr("trade_round_trip_detail_column_jumps"),
                self.tr("trade_round_trip_detail_column_profit"),
            ]
        )
        self.leg_table.horizontalHeader().setStretchLastSection(True)

        self.details_group = QGroupBox(self.tr("trade_round_trip_detail_group"))
        details_layout = QGridLayout(self.details_group)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setHorizontalSpacing(12)
        details_layout.setVerticalSpacing(8)

        self.buy_value = QLabel("-")
        self.sell_value = QLabel("-")
        self.commodity_value = QLabel("-")
        self.jumps_value = QLabel("-")
        self.path_value = QLabel("-")
        self.path_value.setWordWrap(True)

        details_layout.addWidget(QLabel(self.tr("trade_round_trip_detail_buy_label")), 0, 0)
        details_layout.addWidget(self.buy_value, 0, 1)
        details_layout.addWidget(QLabel(self.tr("trade_round_trip_detail_sell_label")), 1, 0)
        details_layout.addWidget(self.sell_value, 1, 1)
        details_layout.addWidget(QLabel(self.tr("trade_round_trip_detail_commodity_label")), 2, 0)
        details_layout.addWidget(self.commodity_value, 2, 1)
        details_layout.addWidget(QLabel(self.tr("trade_round_trip_detail_jumps_label")), 3, 0)
        details_layout.addWidget(self.jumps_value, 3, 1)
        details_layout.addWidget(QLabel(self.tr("trade_round_trip_detail_path_label")), 4, 0)
        details_layout.addWidget(self.path_value, 4, 1)

        self.preview_widget = TradeRoutePreviewWidget(self)
        self.preview_widget.setMinimumHeight(360)

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.details_group)
        right_layout.addWidget(self.preview_widget, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.leg_table)
        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)

        root = QVBoxLayout(self)
        root.addWidget(self.summary_label)
        root.addWidget(splitter, 1)
        root.addWidget(buttons)

        self._connect_signals()
        self._populate_legs()
        self._update_summary()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _connect_signals(self) -> None:
        self.leg_table.currentCellChanged.connect(self._update_details)

    def _populate_legs(self) -> None:
        self.leg_table.setRowCount(len(self.loop.legs))
        for row_index, leg in enumerate(self.loop.legs):
            values = [
                self.tr("trade_round_trip_detail_leg_name", index=row_index + 1, source=leg.source_system, target=leg.target_system),
                leg.commodity,
                f"{leg.source_system} -> {leg.buy_base}",
                f"{leg.target_system} -> {leg.sell_base}",
                f"{leg.buy_price:,}".replace(",", ".") + " $",
                f"{leg.sell_price:,}".replace(",", ".") + " $",
                str(leg.jumps),
                f"{leg.total_profit:,}".replace(",", ".") + " $",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {4, 5, 6, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, leg)
                self.leg_table.setItem(row_index, column, item)
        self.leg_table.resizeColumnsToContents()
        if self.leg_table.rowCount() > 0:
            self.leg_table.selectRow(0)

    def _update_summary(self) -> None:
        self.summary_label.setText(
            self.tr(
                "trade_round_trip_detail_summary",
                route=self.loop.route_text,
                legs=len(self.loop.legs),
                cargo=self.loop.cargo_capacity,
                jumps=self.loop.total_jumps,
                profit=f"{self.loop.total_profit:,}".replace(",", "."),
            )
        )

    def _update_details(self, *_args: object) -> None:
        leg = self._current_leg()
        if leg is None:
            self.buy_value.setText("-")
            self.sell_value.setText("-")
            self.commodity_value.setText("-")
            self.jumps_value.setText("-")
            self.path_value.setText("-")
            self.preview_widget.set_preview_data(None)
            return

        self.buy_value.setText(self.tr("trade_round_trip_detail_buy_value", system=leg.source_system, base=leg.buy_base, price=f"{leg.buy_price:,}".replace(",", ".")))
        self.sell_value.setText(self.tr("trade_round_trip_detail_sell_value", system=leg.target_system, base=leg.sell_base, price=f"{leg.sell_price:,}".replace(",", ".")))
        self.commodity_value.setText(self.tr("trade_round_trip_detail_commodity_value", commodity=leg.commodity, unit=f"{leg.profit_per_unit:,}".replace(",", "."), total=f"{leg.total_profit:,}".replace(",", ".")))
        self.jumps_value.setText(self.tr("trade_round_trip_detail_jumps_value", jumps=leg.jumps, cargo=leg.cargo_capacity))
        self.path_value.setText(self.tr("trade_round_trip_detail_path_value", path=" -> ".join(leg.path) if leg.path else leg.source_system))

        try:
            preview_data = self.trade_route_service.build_route_preview(self.installation, leg)
        except OSError as error:
            self.preview_widget.set_preview_data(None)
            QMessageBox.warning(
                self,
                self.tr("trade_round_trip_detail_preview_error_title"),
                self.tr("trade_round_trip_detail_preview_error_message", error=error),
            )
            return
        self.preview_widget.set_preview_data(preview_data)

    def _current_leg(self) -> TradeRouteRow | None:
        current_row = self.leg_table.currentRow()
        if current_row < 0:
            return None
        item = self.leg_table.item(current_row, 0)
        leg = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return leg if isinstance(leg, TradeRouteRow) else None