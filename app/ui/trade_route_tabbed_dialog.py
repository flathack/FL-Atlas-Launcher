from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.cheat_service import CheatService, ShipInfoRow
from app.services.ship_render_service import ShipRenderService
from app.services.trade_route_service import (
    TradeRouteLoopRow,
    TradeRouteRow,
    TradeRouteTravelSegment,
    TradeRouteService,
)
from app.ui.ship_handling_dialog import _IconLoaderWorker
from app.ui.ship_preview_dialog import ShipPreviewDialog
from app.ui.trade_route_preview_dialog import TradeRoutePreviewDialog
from app.ui.trade_route_round_trip_detail_dialog import TradeRouteRoundTripDetailDialog


_MAX_TABLE_TEXT_LENGTH = 30
_MAX_ROUND_TRIP_TEXT_LENGTH = 60
_SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def _truncate_table_text(value: object, max_length: int = _MAX_TABLE_TEXT_LENGTH) -> str:
    text = str(value)
    return text if len(text) <= max_length else f"{text[:max_length - 1]}…"


def _truncate_round_trip_text(value: object, max_length: int = _MAX_ROUND_TRIP_TEXT_LENGTH) -> str:
    text = str(value)
    return text if len(text) <= max_length else f"{text[:max_length - 1]}…"


def _format_money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}".replace(",", ".") + " $"


def _format_seconds(value: int | None) -> str:
    if value is None:
        return "-"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}:{seconds:02d}"


def _format_volume(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _format_segment_text(translator: Translator, segment: TradeRouteTravelSegment) -> str:
    if segment.segment_type == "buy_start":
        return f"{segment.system}: {segment.station} -> {translator.text('trade_routes_detail_buy_start')} ({_format_seconds(segment.seconds)})"
    if segment.segment_type == "dock_sell":
        return f"{segment.system}: {translator.text('trade_routes_detail_dock_sell')} {segment.station} ({_format_seconds(segment.seconds)})"
    if segment.segment_type == "jump":
        return f"{translator.text('trade_routes_detail_jump')}: {segment.from_label} -> {segment.to_label} ({_format_seconds(segment.seconds)})"
    if segment.segment_type == "trade_lane":
        suffix = f" | {segment.distance} m" if segment.distance is not None else ""
        return f"{segment.system}: {translator.text('trade_routes_detail_trade_lane')} ({_format_seconds(segment.seconds)}){suffix}"
    suffix = f" | {segment.distance} m" if segment.distance is not None else ""
    return f"{segment.system}: {translator.text('trade_routes_detail_open_space')} ({_format_seconds(segment.seconds)}){suffix}"


def _segment_type_label(translator: Translator, segment: TradeRouteTravelSegment) -> str:
    if segment.segment_type == "buy_start":
        return translator.text("trade_routes_detail_buy_start")
    if segment.segment_type == "dock_sell":
        return translator.text("trade_routes_detail_dock_sell")
    if segment.segment_type == "jump":
        return translator.text("trade_routes_detail_jump")
    if segment.segment_type == "trade_lane":
        return translator.text("trade_routes_detail_trade_lane")
    return translator.text("trade_routes_detail_open_space")


def _segment_action_label(segment: TradeRouteTravelSegment) -> str:
    if segment.segment_type == "buy_start":
        return f"{segment.station}"
    if segment.segment_type == "dock_sell":
        return f"{segment.station}"
    if segment.segment_type == "jump":
        return f"{segment.from_label} -> {segment.to_label}"
    if segment.distance is not None:
        return f"{segment.distance:,}".replace(",", ".") + " m"
    return "-"


def _render_segment_table_html(
    translator: Translator,
    title: str,
    segments: list[TradeRouteTravelSegment],
) -> str:
    if not segments:
        return ""
    rows: list[str] = []
    for index, segment in enumerate(segments, start=1):
        rows.append(
            "<tr>"
            f"<td style='padding:6px 8px; color:#9fb2cf;'>{index}</td>"
            f"<td style='padding:6px 8px; font-weight:600; color:#dce7f7;'>{html.escape(_segment_type_label(translator, segment))}</td>"
            f"<td style='padding:6px 8px; color:#dce7f7;'>{html.escape(segment.system)}</td>"
            f"<td style='padding:6px 8px; color:#c7d6ea;'>{html.escape(_segment_action_label(segment))}</td>"
            f"<td style='padding:6px 8px; text-align:right; color:#8fe1b5; white-space:nowrap;'>{html.escape(_format_seconds(segment.seconds))}</td>"
            "</tr>"
        )
    return (
        f"<div style='margin-top:14px;'>"
        f"<div style='font-size:12px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#8db7ff; margin-bottom:6px;'>{html.escape(title)}</div>"
        "<table cellspacing='0' cellpadding='0' width='100%' style='border-collapse:collapse; background:#334766; border:1px solid #4a5f82; border-radius:8px;'>"
        "<thead>"
        "<tr>"
        f"<th align='left' style='padding:7px 8px; color:#9fb2cf; font-size:11px;'>{html.escape(translator.text('trade_routes_detail_step'))}</th>"
        f"<th align='left' style='padding:7px 8px; color:#9fb2cf; font-size:11px;'>{html.escape(translator.text('trade_routes_detail_type'))}</th>"
        f"<th align='left' style='padding:7px 8px; color:#9fb2cf; font-size:11px;'>{html.escape(translator.text('trade_routes_detail_system'))}</th>"
        f"<th align='left' style='padding:7px 8px; color:#9fb2cf; font-size:11px;'>{html.escape(translator.text('trade_routes_detail_action'))}</th>"
        f"<th align='right' style='padding:7px 8px; color:#9fb2cf; font-size:11px;'>{html.escape(translator.text('trade_routes_detail_segment_time'))}</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        + "".join(rows) +
        "</tbody></table></div>"
    )


def _format_route_details(
    translator: Translator,
    route: TradeRouteRow,
    outbound_segments: list[TradeRouteTravelSegment],
    return_segments: list[TradeRouteTravelSegment] | None,
) -> str:
    route_text = " -> ".join(route.path) if route.path else "-"
    profit_per_minute = f"{route.profit_per_minute:,}".replace(",", ".") if route.profit_per_minute is not None else "-"
    summary_cards = [
        (translator.text("trade_routes_column_time"), _format_seconds(route.travel_time_seconds), "#8fe1b5"),
        (translator.text("trade_routes_column_ppm"), profit_per_minute, "#ffd47a"),
        (translator.text("trade_routes_column_total_profit"), _format_money(route.total_profit), "#9fd0ff"),
    ]
    if route.return_travel_time_seconds > 0:
        summary_cards.append((translator.text("trade_routes_detail_return"), _format_seconds(route.return_travel_time_seconds), "#f8c78e"))

    card_html = "".join(
        "<td style='padding:0 10px 0 0;'>"
        "<div style='min-width:130px; background:#334766; border:1px solid #4a5f82; border-radius:8px; padding:10px 12px;'>"
        f"<div style='font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#9fb2cf; margin-bottom:4px;'>{html.escape(label)}</div>"
        f"<div style='font-size:18px; font-weight:700; color:{color};'>{html.escape(value)}</div>"
        "</div></td>"
        for label, value, color in summary_cards
    )

    route_chip = (
        "<div style='background:#334766; border:1px solid #4a5f82; border-radius:10px; padding:12px 14px; margin-bottom:12px;'>"
        f"<div style='font-size:12px; text-transform:uppercase; letter-spacing:0.08em; color:#9fb2cf; margin-bottom:6px;'>{html.escape(translator.text('trade_routes_detail_route_label'))}</div>"
        f"<div style='font-size:19px; font-weight:700; color:#eef4ff; line-height:1.35;'>{html.escape(route_text)}</div>"
        "</div>"
    )

    return (
        "<html><body style='font-family:Segoe UI; color:#dce7f7; margin:0;'>"
        + route_chip +
        f"<table cellspacing='0' cellpadding='0' style='margin-bottom:8px;'><tr>{card_html}</tr></table>"
        + _render_segment_table_html(translator, translator.text('trade_routes_detail_outbound'), outbound_segments)
        + _render_segment_table_html(translator, translator.text('trade_routes_detail_return_segments'), return_segments or [])
        + "</body></html>"
    )


class _SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        self_value = self.data(_SORT_ROLE)
        other_value = other.data(_SORT_ROLE)
        if self_value is None and other_value is None:
            return self.text().lower() < other.text().lower()
        if self_value is None:
            return False
        if other_value is None:
            return True
        try:
            return self_value < other_value
        except TypeError:
            return str(self_value).lower() < str(other_value).lower()


def _make_sortable_item(
    display_text: str,
    *,
    payload: object | None = None,
    sort_value: object | None = None,
    align_right: bool = False,
) -> QTableWidgetItem:
    item = _SortableTableWidgetItem(_truncate_round_trip_text(display_text, _MAX_ROUND_TRIP_TEXT_LENGTH))
    item.setToolTip(display_text)
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if payload is not None:
        item.setData(Qt.ItemDataRole.UserRole, payload)
    item.setData(_SORT_ROLE, sort_value if sort_value is not None else display_text.lower())
    return item


# ---------------------------------------------------------------------------
#  Workers
# ---------------------------------------------------------------------------

class _InnerSystemWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)

    def __init__(self, service: TradeRouteService, installation: Installation,
                 cargo_capacity: int, include_return_trip: bool, player_reputation: dict[str, float]) -> None:
        super().__init__()
        self._service = service
        self._installation = installation
        self._cargo_capacity = cargo_capacity
        self._include_return_trip = include_return_trip
        self._player_reputation = player_reputation

    def run(self) -> None:
        routes = self._service.best_inner_system_routes(
            self._installation,
            cargo_capacity=self._cargo_capacity,
            include_return_trip=self._include_return_trip,
            player_reputation=self._player_reputation,
            progress_callback=self.progress.emit,
        )
        self.finished.emit(routes)


class _TradeRouteWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)

    def __init__(self, service: TradeRouteService, installation: Installation,
                 cargo_capacity: int, max_jumps: int, include_return_trip: bool, player_reputation: dict[str, float]) -> None:
        super().__init__()
        self._service = service
        self._installation = installation
        self._cargo_capacity = cargo_capacity
        self._max_jumps = max_jumps
        self._include_return_trip = include_return_trip
        self._player_reputation = player_reputation

    def run(self) -> None:
        routes = self._service.best_routes_by_system(
            self._installation,
            cargo_capacity=self._cargo_capacity,
            max_jumps=self._max_jumps,
            include_return_trip=self._include_return_trip,
            player_reputation=self._player_reputation,
            progress_callback=self.progress.emit,
        )
        self.finished.emit(routes)


class _RoundTripWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)

    def __init__(self, service: TradeRouteService, installation: Installation,
                 cargo_capacity: int, max_jumps: int, leg_count: int,
                 player_reputation: dict[str, float]) -> None:
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


# ---------------------------------------------------------------------------
#  Shared eye icon helper
# ---------------------------------------------------------------------------

def _build_eye_icon() -> QIcon:
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


# ---------------------------------------------------------------------------
#  Mixin for cancel / loading boilerplate
# ---------------------------------------------------------------------------

class _LoadingMixin:
    """Shared loading-state helpers (mixed into each tab widget)."""

    _worker_thread: QThread | None
    progress_bar: QProgressBar
    loading_label: QLabel
    cancel_button: QPushButton

    def _init_loading_widgets(self, translator: Translator) -> None:
        self.loading_label = QLabel(translator.text("trade_routes_loading"))
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)
        self.cancel_button = QPushButton(translator.text("cancel"))
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_worker)  # type: ignore[attr-defined]

    def _cancel_worker(self) -> None:
        thread = self._worker_thread
        if thread is not None:
            thread.requestInterruption()
            thread.quit()
            thread.wait(3000)
            self._worker_thread = None
            self._set_loading(False)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
#  Tab 1 – Inner System Routes
# ---------------------------------------------------------------------------

class _InnerSystemTab(QWidget, _LoadingMixin):
    ship_changed = Signal(str)

    def __init__(self, installation: Installation, service: TradeRouteService,
                 translator: Translator, player_reputation: dict[str, float],
                 selected_ship: str = "",
                 cheat_service: CheatService | None = None,
                 ship_render_service: ShipRenderService | None = None,
                 game_root: Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.installation = installation
        self.trade_route_service = service
        self.translator = translator
        self.player_reputation = player_reputation
        self._selected_ship = selected_ship
        self._cheat_service = cheat_service
        self._ship_render_service = ship_render_service
        self._game_root = game_root
        self._ship_info_map: dict[str, ShipInfoRow] = {}
        self._routes: list[TradeRouteRow] = []
        self._preview_windows: list[TradeRoutePreviewDialog] = []
        self._worker_thread: QThread | None = None
        self._icon_thread: QThread | None = None

        self.ship_combo = QComboBox()
        self.ship_info_button = QToolButton()
        self.ship_info_button.setText("🔍")
        self.ship_info_button.setToolTip(self.tr("ship_preview_button_tooltip"))
        self.return_trip_checkbox = QCheckBox(self.tr("trade_routes_include_return"))
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 14)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels([
            self.tr("trade_routes_column_preview"),
            self.tr("trade_routes_column_source"),
            self.tr("trade_routes_column_buy"),
            self.tr("trade_routes_column_sell"),
            self.tr("trade_routes_column_commodity"),
            self.tr("trade_routes_column_buy_price"),
            self.tr("trade_routes_column_sell_price"),
            self.tr("trade_routes_column_volume"),
            self.tr("trade_routes_column_units"),
            self.tr("trade_routes_column_jumps"),
            self.tr("trade_routes_column_unit_profit"),
            self.tr("trade_routes_column_total_profit"),
            self.tr("trade_routes_column_time"),
            self.tr("trade_routes_column_ppm"),
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("trade_routes_search"))
        self.search_input.setClearButtonEnabled(True)
        self.details_label = QTextBrowser()
        self.details_label.setOpenExternalLinks(False)
        self.details_label.setReadOnly(True)
        self.details_label.setMinimumHeight(240)
        self.details_label.setStyleSheet(
            "QTextBrowser { background-color: #3c4f71; border: 1px solid #4a5f82; border-radius: 10px; padding: 8px; }"
        )

        self._init_loading_widgets(translator)
        self._started = False
        self._build_ui()
        self._connect_signals()
        self._load_ships()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._refresh_routes()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        filters = QWidget()
        form = QFormLayout(filters)
        form.setContentsMargins(0, 0, 0, 0)
        ship_row = QHBoxLayout()
        ship_row.addWidget(self.ship_combo, 1)
        ship_row.addWidget(self.ship_info_button)
        form.addRow(self.tr("trade_routes_ship"), ship_row)
        form.addRow("", self.return_trip_checkbox)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        loading_row = QHBoxLayout()
        loading_row.addWidget(self.progress_bar, 1)
        loading_row.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.search_input)
        root.addWidget(self.loading_label)
        root.addLayout(loading_row)
        root.addWidget(self.table, 1)
        root.addWidget(self.details_label)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_routes)
        self.ship_combo.currentIndexChanged.connect(lambda _: self._on_ship_combo_changed())
        self.ship_info_button.clicked.connect(self._open_ship_preview)
        self.return_trip_checkbox.toggled.connect(lambda _: self._refresh_routes())
        self.table.currentCellChanged.connect(self._update_details_label)
        self.search_input.textChanged.connect(self._apply_filter)

    def _load_ships(self) -> None:
        self._stop_icon_loader()
        options = self.trade_route_service.ship_options(self.installation)
        if self._cheat_service:
            rows = self._cheat_service.ship_info_rows(self.installation)
            self._ship_info_map = {r.nickname: r for r in rows}
        self.ship_combo.clear()
        selected_index = 0
        icon_jobs: list[tuple[int, str, str]] = []
        for i, option in enumerate(options):
            self.ship_combo.addItem(option.label, (option.nickname, option.cargo_capacity))
            info = self._ship_info_map.get(option.nickname)
            if info and info.da_archetype:
                icon_jobs.append((i, option.nickname, info.da_archetype))
            if option.nickname == self._selected_ship:
                selected_index = i
        if options:
            self.ship_combo.setCurrentIndex(selected_index)
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

    def _on_icon_ready(self, index: int, icon_path: str) -> None:
        if index < self.ship_combo.count():
            self.ship_combo.setItemIcon(index, QIcon(icon_path))

    def _open_ship_preview(self) -> None:
        data = self.ship_combo.currentData()
        if not data:
            return
        nickname = data[0]
        info = self._ship_info_map.get(nickname)
        if not info or not self._ship_render_service or not self._game_root:
            return
        dialog = ShipPreviewDialog(info, self._game_root, self._ship_render_service, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()

    def _on_ship_combo_changed(self) -> None:
        data = self.ship_combo.currentData()
        if data:
            self.ship_changed.emit(data[0])
        self._refresh_routes()

    def _refresh_routes(self) -> None:
        if not self._started or self._worker_thread is not None:
            return
        data = self.ship_combo.currentData()
        cargo_capacity = int(data[1]) if data else 0
        self._set_loading(True)
        self._worker_thread = QThread(self)
        worker = _InnerSystemWorker(self.trade_route_service, self.installation,
                                    cargo_capacity, self.return_trip_checkbox.isChecked(), self.player_reputation)
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
        self.cancel_button.setVisible(loading)
        self.table.setVisible(not loading)
        self.refresh_button.setEnabled(not loading)
        self.ship_combo.setEnabled(not loading)

    def _on_routes_ready(self, routes: list[TradeRouteRow]) -> None:
        self._routes = routes
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._routes))
        eye_icon = _build_eye_icon()
        for row_index, route in enumerate(self._routes):
            button = QToolButton(self.table)
            button.setIcon(eye_icon)
            button.setToolTip(self.tr("trade_routes_preview_open"))
            button.clicked.connect(lambda _c=False, r=route: self._open_preview(r))
            self.table.setCellWidget(row_index, 0, button)
            values = [
                route.source_system,
                route.buy_base,
                route.sell_base,
                route.commodity,
                _format_money(route.buy_price),
                _format_money(route.sell_price),
                _format_volume(route.commodity_volume),
                f"{route.cargo_units:,}".replace(",", "."),
                str(route.jumps),
                _format_money(route.profit_per_unit),
                _format_money(route.total_profit),
                _format_seconds(route.travel_time_seconds),
                f"{route.profit_per_minute:,}".replace(",", ".") if route.profit_per_minute is not None else "-",
            ]
            sort_values = [
                route.source_system.lower(),
                route.buy_base.lower(),
                route.sell_base.lower(),
                route.commodity.lower(),
                route.buy_price,
                route.sell_price,
                route.commodity_volume,
                route.cargo_units,
                route.jumps,
                route.profit_per_unit,
                route.total_profit,
                route.travel_time_seconds if route.travel_time_seconds is not None else float("inf"),
                route.profit_per_minute if route.profit_per_minute is not None else -1,
            ]
            for offset, (value, sort_value) in enumerate(zip(values, sort_values), start=1):
                full_text = str(value)
                item = _SortableTableWidgetItem(_truncate_table_text(full_text))
                item.setToolTip(full_text)
                if offset in {5, 6, 7, 8, 9, 10, 11, 12, 13}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, route)
                item.setData(_SORT_ROLE, sort_value)
                self.table.setItem(row_index, offset, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(13, Qt.SortOrder.DescendingOrder)
        self._set_loading(False)
        self._apply_filter()
        self._update_details_label()

    def _update_details_label(self, *_args: object) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
                current_row = 0
            else:
                self.details_label.setText(self.tr("trade_routes_no_routes"))
                return
        item = self.table.item(current_row, 1)
        route = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(route, TradeRouteRow):
            self.details_label.setText(self.tr("trade_routes_no_routes"))
            return
        outbound_segments, return_segments = self.trade_route_service.build_route_travel_breakdown(self.installation, route)
        self.details_label.setText(_format_route_details(self.translator, route, outbound_segments, return_segments))

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

    def _open_preview(self, route: TradeRouteRow) -> None:
        preview_data = self.trade_route_service.build_route_preview(self.installation, route)
        dialog = TradeRoutePreviewDialog(preview_data, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _o=None, d=dialog: self._forget_preview(d))
        self._preview_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_preview(self, dialog: TradeRoutePreviewDialog) -> None:
        self._preview_windows = [w for w in self._preview_windows if w is not dialog]

    def shutdown(self) -> None:
        self._cancel_worker()
        self._stop_icon_loader()
        for dialog in list(self._preview_windows):
            try:
                dialog.close()
            except RuntimeError:
                pass
        self._preview_windows.clear()


# ---------------------------------------------------------------------------
#  Tab 2 – Trade Routes (cross-system)
# ---------------------------------------------------------------------------

class _TradeRoutesTab(QWidget, _LoadingMixin):
    ship_changed = Signal(str)

    def __init__(self, installation: Installation, service: TradeRouteService,
                 translator: Translator, player_reputation: dict[str, float],
                 selected_ship: str = "",
                 cheat_service: CheatService | None = None,
                 ship_render_service: ShipRenderService | None = None,
                 game_root: Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.installation = installation
        self.trade_route_service = service
        self.translator = translator
        self.player_reputation = player_reputation
        self._selected_ship = selected_ship
        self._cheat_service = cheat_service
        self._ship_render_service = ship_render_service
        self._game_root = game_root
        self._ship_info_map: dict[str, ShipInfoRow] = {}
        self._routes: list[TradeRouteRow] = []
        self._preview_windows: list[TradeRoutePreviewDialog] = []
        self._worker_thread: QThread | None = None
        self._icon_thread: QThread | None = None

        self.ship_combo = QComboBox()
        self.ship_info_button = QToolButton()
        self.ship_info_button.setText("🔍")
        self.ship_info_button.setToolTip(self.tr("ship_preview_button_tooltip"))
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(0, 20)
        self.jump_spin.setValue(3)
        self.return_trip_checkbox = QCheckBox(self.tr("trade_routes_include_return"))
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 14)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels([
            self.tr("trade_routes_column_preview"),
            self.tr("trade_routes_column_source"),
            self.tr("trade_routes_column_buy"),
            self.tr("trade_routes_column_sell"),
            self.tr("trade_routes_column_commodity"),
            self.tr("trade_routes_column_buy_price"),
            self.tr("trade_routes_column_sell_price"),
            self.tr("trade_routes_column_volume"),
            self.tr("trade_routes_column_units"),
            self.tr("trade_routes_column_jumps"),
            self.tr("trade_routes_column_unit_profit"),
            self.tr("trade_routes_column_total_profit"),
            self.tr("trade_routes_column_time"),
            self.tr("trade_routes_column_ppm"),
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("trade_routes_search"))
        self.search_input.setClearButtonEnabled(True)
        self.path_label = QTextBrowser()
        self.path_label.setOpenExternalLinks(False)
        self.path_label.setReadOnly(True)
        self.path_label.setMinimumHeight(240)
        self.path_label.setStyleSheet(
            "QTextBrowser { background-color: #3c4f71; border: 1px solid #4a5f82; border-radius: 10px; padding: 8px; }"
        )

        self._init_loading_widgets(translator)
        self._started = False
        self._build_ui()
        self._connect_signals()
        self._load_ships()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._refresh_routes()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        filters = QWidget()
        form = QFormLayout(filters)
        form.setContentsMargins(0, 0, 0, 0)
        ship_row = QHBoxLayout()
        ship_row.addWidget(self.ship_combo, 1)
        ship_row.addWidget(self.ship_info_button)
        form.addRow(self.tr("trade_routes_ship"), ship_row)
        form.addRow(self.tr("trade_routes_max_jumps"), self.jump_spin)
        form.addRow("", self.return_trip_checkbox)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        loading_row = QHBoxLayout()
        loading_row.addWidget(self.progress_bar, 1)
        loading_row.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.search_input)
        root.addWidget(self.loading_label)
        root.addLayout(loading_row)
        root.addWidget(self.table, 1)
        root.addWidget(self.path_label)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_routes)
        self.ship_combo.currentIndexChanged.connect(lambda _: self._on_ship_combo_changed())
        self.ship_info_button.clicked.connect(self._open_ship_preview)
        self.jump_spin.valueChanged.connect(lambda _: self._refresh_routes())
        self.return_trip_checkbox.toggled.connect(lambda _: self._refresh_routes())
        self.table.currentCellChanged.connect(self._update_path_label)
        self.search_input.textChanged.connect(self._apply_filter)

    def _load_ships(self) -> None:
        self._stop_icon_loader()
        options = self.trade_route_service.ship_options(self.installation)
        if self._cheat_service:
            rows = self._cheat_service.ship_info_rows(self.installation)
            self._ship_info_map = {r.nickname: r for r in rows}
        self.ship_combo.clear()
        selected_index = 0
        icon_jobs: list[tuple[int, str, str]] = []
        for i, option in enumerate(options):
            self.ship_combo.addItem(option.label, (option.nickname, option.cargo_capacity))
            info = self._ship_info_map.get(option.nickname)
            if info and info.da_archetype:
                icon_jobs.append((i, option.nickname, info.da_archetype))
            if option.nickname == self._selected_ship:
                selected_index = i
        if options:
            self.ship_combo.setCurrentIndex(selected_index)
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

    def _on_icon_ready(self, index: int, icon_path: str) -> None:
        if index < self.ship_combo.count():
            self.ship_combo.setItemIcon(index, QIcon(icon_path))

    def _open_ship_preview(self) -> None:
        data = self.ship_combo.currentData()
        if not data:
            return
        nickname = data[0]
        info = self._ship_info_map.get(nickname)
        if not info or not self._ship_render_service or not self._game_root:
            return
        dialog = ShipPreviewDialog(info, self._game_root, self._ship_render_service, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()

    def _on_ship_combo_changed(self) -> None:
        data = self.ship_combo.currentData()
        if data:
            self.ship_changed.emit(data[0])
        self._refresh_routes()

    def _refresh_routes(self) -> None:
        if not self._started or self._worker_thread is not None:
            return
        data = self.ship_combo.currentData()
        cargo_capacity = int(data[1]) if data else 0
        max_jumps = int(self.jump_spin.value())
        self._set_loading(True)
        self._worker_thread = QThread(self)
        worker = _TradeRouteWorker(self.trade_route_service, self.installation,
                                   cargo_capacity, max_jumps, self.return_trip_checkbox.isChecked(), self.player_reputation)
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
        self.cancel_button.setVisible(loading)
        self.table.setVisible(not loading)
        self.refresh_button.setEnabled(not loading)
        self.ship_combo.setEnabled(not loading)
        self.jump_spin.setEnabled(not loading)

    def _on_routes_ready(self, routes: list[TradeRouteRow]) -> None:
        self._routes = routes
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._routes))
        eye_icon = _build_eye_icon()
        for row_index, route in enumerate(self._routes):
            button = QToolButton(self.table)
            button.setIcon(eye_icon)
            button.setToolTip(self.tr("trade_routes_preview_open"))
            button.clicked.connect(lambda _c=False, r=route: self._open_preview(r))
            self.table.setCellWidget(row_index, 0, button)
            values = [
                route.source_system,
                route.buy_base,
                f"{route.target_system} -> {route.sell_base}",
                route.commodity,
                _format_money(route.buy_price),
                _format_money(route.sell_price),
                _format_volume(route.commodity_volume),
                f"{route.cargo_units:,}".replace(",", "."),
                str(route.jumps),
                _format_money(route.profit_per_unit),
                _format_money(route.total_profit),
                _format_seconds(route.travel_time_seconds),
                f"{route.profit_per_minute:,}".replace(",", ".") if route.profit_per_minute is not None else "-",
            ]
            sort_values = [
                route.source_system.lower(),
                route.buy_base.lower(),
                f"{route.target_system} -> {route.sell_base}".lower(),
                route.commodity.lower(),
                route.buy_price,
                route.sell_price,
                route.commodity_volume,
                route.cargo_units,
                route.jumps,
                route.profit_per_unit,
                route.total_profit,
                route.travel_time_seconds if route.travel_time_seconds is not None else float("inf"),
                route.profit_per_minute if route.profit_per_minute is not None else -1,
            ]
            for offset, (value, sort_value) in enumerate(zip(values, sort_values), start=1):
                full_text = str(value)
                item = _SortableTableWidgetItem(_truncate_table_text(full_text))
                item.setToolTip(full_text)
                if offset in {5, 6, 7, 8, 9, 10, 11, 12, 13}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, route)
                item.setData(_SORT_ROLE, sort_value)
                self.table.setItem(row_index, offset, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(13, Qt.SortOrder.DescendingOrder)
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
        outbound_segments, return_segments = self.trade_route_service.build_route_travel_breakdown(self.installation, route)
        self.path_label.setText(_format_route_details(self.translator, route, outbound_segments, return_segments))

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

    def _open_preview(self, route: TradeRouteRow) -> None:
        preview_data = self.trade_route_service.build_route_preview(self.installation, route)
        dialog = TradeRoutePreviewDialog(preview_data, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _o=None, d=dialog: self._forget_preview(d))
        self._preview_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_preview(self, dialog: TradeRoutePreviewDialog) -> None:
        self._preview_windows = [w for w in self._preview_windows if w is not dialog]

    def shutdown(self) -> None:
        self._cancel_worker()
        self._stop_icon_loader()
        for dialog in list(self._preview_windows):
            try:
                dialog.close()
            except RuntimeError:
                pass
        self._preview_windows.clear()


# ---------------------------------------------------------------------------
#  Tab 3 – Round Trip
# ---------------------------------------------------------------------------

class _RoundTripTab(QWidget, _LoadingMixin):
    ship_changed = Signal(str)

    def __init__(self, installation: Installation, service: TradeRouteService,
                 translator: Translator, player_reputation: dict[str, float],
                 selected_ship: str = "",
                 cheat_service: CheatService | None = None,
                 ship_render_service: ShipRenderService | None = None,
                 game_root: Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.installation = installation
        self.trade_route_service = service
        self.translator = translator
        self.player_reputation = player_reputation
        self._selected_ship = selected_ship
        self._cheat_service = cheat_service
        self._ship_render_service = ship_render_service
        self._game_root = game_root
        self._ship_info_map: dict[str, ShipInfoRow] = {}
        self._loops: list[TradeRouteLoopRow] = []
        self._detail_windows: list[TradeRouteRoundTripDetailDialog] = []
        self._worker_thread: QThread | None = None
        self._icon_thread: QThread | None = None

        self.ship_combo = QComboBox()
        self.ship_info_button = QToolButton()
        self.ship_info_button.setText("🔍")
        self.ship_info_button.setToolTip(self.tr("ship_preview_button_tooltip"))
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(0, 20)
        self.jump_spin.setValue(1)
        self.leg_spin = QSpinBox()
        self.leg_spin.setRange(3, 6)
        self.leg_spin.setValue(4)
        self.refresh_button = QPushButton(self.tr("refresh"))

        self.table = QTableWidget(0, 7)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels([
            self.tr("trade_round_trip_column_start"),
            self.tr("trade_round_trip_column_route"),
            self.tr("trade_round_trip_column_goods"),
            self.tr("trade_round_trip_column_jumps"),
            self.tr("trade_round_trip_column_profit"),
            self.tr("trade_round_trip_column_time"),
            self.tr("trade_round_trip_column_ppm"),
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("trade_routes_search"))
        self.search_input.setClearButtonEnabled(True)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.hint_label = QLabel(self.tr("trade_round_trip_detail_hint"))
        self.hint_label.setWordWrap(True)

        self._init_loading_widgets(translator)
        self._started = False
        self._build_ui()
        self._connect_signals()
        self._load_ships()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._refresh_loops()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_ui(self) -> None:
        filters = QWidget()
        form = QFormLayout(filters)
        form.setContentsMargins(0, 0, 0, 0)
        ship_row = QHBoxLayout()
        ship_row.addWidget(self.ship_combo, 1)
        ship_row.addWidget(self.ship_info_button)
        form.addRow(self.tr("trade_routes_ship"), ship_row)
        form.addRow(self.tr("trade_routes_max_jumps"), self.jump_spin)
        form.addRow(self.tr("trade_round_trip_leg_count"), self.leg_spin)

        controls = QHBoxLayout()
        controls.addWidget(filters, 1)
        controls.addWidget(self.refresh_button)

        loading_row = QHBoxLayout()
        loading_row.addWidget(self.progress_bar, 1)
        loading_row.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.search_input)
        root.addWidget(self.loading_label)
        root.addLayout(loading_row)
        root.addWidget(self.table, 1)
        root.addWidget(self.summary_label)
        root.addWidget(self.hint_label)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_loops)
        self.ship_combo.currentIndexChanged.connect(lambda _: self._on_ship_combo_changed())
        self.ship_info_button.clicked.connect(self._open_ship_preview)
        self.jump_spin.valueChanged.connect(lambda _: self._refresh_loops())
        self.leg_spin.valueChanged.connect(lambda _: self._refresh_loops())
        self.table.currentCellChanged.connect(self._update_summary)
        self.table.itemDoubleClicked.connect(lambda _: self._open_detail_dialog())
        self.search_input.textChanged.connect(self._apply_filter)

    def _load_ships(self) -> None:
        self._stop_icon_loader()
        options = self.trade_route_service.ship_options(self.installation)
        if self._cheat_service:
            rows = self._cheat_service.ship_info_rows(self.installation)
            self._ship_info_map = {r.nickname: r for r in rows}
        self.ship_combo.clear()
        selected_index = 0
        icon_jobs: list[tuple[int, str, str]] = []
        for i, option in enumerate(options):
            self.ship_combo.addItem(option.label, (option.nickname, option.cargo_capacity))
            info = self._ship_info_map.get(option.nickname)
            if info and info.da_archetype:
                icon_jobs.append((i, option.nickname, info.da_archetype))
            if option.nickname == self._selected_ship:
                selected_index = i
        if options:
            self.ship_combo.setCurrentIndex(selected_index)
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

    def _on_icon_ready(self, index: int, icon_path: str) -> None:
        if index < self.ship_combo.count():
            self.ship_combo.setItemIcon(index, QIcon(icon_path))

    def _open_ship_preview(self) -> None:
        data = self.ship_combo.currentData()
        if not data:
            return
        nickname = data[0]
        info = self._ship_info_map.get(nickname)
        if not info or not self._ship_render_service or not self._game_root:
            return
        dialog = ShipPreviewDialog(info, self._game_root, self._ship_render_service, self.translator, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()

    def _on_ship_combo_changed(self) -> None:
        data = self.ship_combo.currentData()
        if data:
            self.ship_changed.emit(data[0])
        self._refresh_loops()

    def _refresh_loops(self) -> None:
        if not self._started or self._worker_thread is not None:
            return
        data = self.ship_combo.currentData()
        cargo_capacity = int(data[1]) if data else 0
        max_jumps = int(self.jump_spin.value())
        leg_count = int(self.leg_spin.value())
        self._set_loading(True)
        self._worker_thread = QThread(self)
        worker = _RoundTripWorker(self.trade_route_service, self.installation,
                                  cargo_capacity, max_jumps, leg_count, self.player_reputation)
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
        self.cancel_button.setVisible(loading)
        self.table.setVisible(not loading)
        self.refresh_button.setEnabled(not loading)
        self.ship_combo.setEnabled(not loading)
        self.jump_spin.setEnabled(not loading)
        self.leg_spin.setEnabled(not loading)

    def _on_loops_ready(self, loops: list[TradeRouteLoopRow]) -> None:
        self._loops = loops
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._loops))
        for row_index, loop in enumerate(self._loops):
            values = [
                loop.start_system,
                loop.route_text,
                " | ".join(loop.commodities),
                str(loop.total_jumps),
                _format_money(loop.total_profit),
                _format_seconds(loop.travel_time_seconds),
                f"{loop.profit_per_minute:,}".replace(",", ".") if loop.profit_per_minute is not None else "-",
            ]
            sort_values = [
                loop.start_system.lower(),
                loop.route_text.lower(),
                " | ".join(loop.commodities).lower(),
                loop.total_jumps,
                loop.total_profit,
                loop.travel_time_seconds if loop.travel_time_seconds is not None else float("inf"),
                loop.profit_per_minute if loop.profit_per_minute is not None else -1,
            ]
            for column, (value, sort_value) in enumerate(zip(values, sort_values)):
                full_text = str(value)
                item = _SortableTableWidgetItem(_truncate_round_trip_text(full_text))
                item.setToolTip(full_text)
                if column in {3, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, loop)
                item.setData(_SORT_ROLE, sort_value)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(6, Qt.SortOrder.DescendingOrder)
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
        self.summary_label.setText(self.tr(
            "trade_round_trip_summary",
            legs=len(loop.legs), cargo=loop.cargo_capacity,
            jumps=loop.total_jumps,
            profit=f"{loop.total_profit:,}".replace(",", "."),
            time=_format_seconds(loop.travel_time_seconds),
            ppm=(f"{loop.profit_per_minute:,}".replace(",", ".") if loop.profit_per_minute is not None else "-"),
        ))

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
            self.installation, loop, self.trade_route_service, self.translator, parent=self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _o=None, d=dialog: self._forget_detail(d))
        self._detail_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_detail(self, dialog: TradeRouteRoundTripDetailDialog) -> None:
        self._detail_windows = [w for w in self._detail_windows if w is not dialog]

    def shutdown(self) -> None:
        self._cancel_worker()
        self._stop_icon_loader()
        for dialog in list(self._detail_windows):
            try:
                dialog.close()
            except RuntimeError:
                pass
        self._detail_windows.clear()


# ---------------------------------------------------------------------------
#  Main tabbed dialog
# ---------------------------------------------------------------------------

class TradeRouteTabbedDialog(QDialog):
    ship_changed = Signal(str)

    def __init__(
        self,
        installation: Installation,
        trade_route_service: TradeRouteService,
        translator: Translator,
        *,
        player_reputation: dict[str, float] | None = None,
        selected_ship: str = "",
        initial_tab: int = 0,
        cheat_service: CheatService | None = None,
        ship_render_service: ShipRenderService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.setWindowTitle(translator.text("trade_routes_title", name=installation.name))
        self.resize(1280, 740)
        self.setModal(False)

        reputation = dict(player_reputation or {})

        # Resolve game root once for all tabs
        game_root: Path | None = None
        if cheat_service:
            try:
                game_root = cheat_service.resolve_game_root(installation)
            except OSError:
                pass

        tab_kwargs: dict = dict(
            cheat_service=cheat_service,
            ship_render_service=ship_render_service,
            game_root=game_root,
        )

        self.tabs = QTabWidget()
        self._inner_tab = _InnerSystemTab(installation, trade_route_service, translator, reputation, selected_ship, parent=self, **tab_kwargs)
        self._routes_tab = _TradeRoutesTab(installation, trade_route_service, translator, reputation, selected_ship, parent=self, **tab_kwargs)
        self._round_trip_tab = _RoundTripTab(installation, trade_route_service, translator, reputation, selected_ship, parent=self, **tab_kwargs)

        self._inner_tab.ship_changed.connect(self._on_ship_changed)
        self._routes_tab.ship_changed.connect(self._on_ship_changed)
        self._round_trip_tab.ship_changed.connect(self._on_ship_changed)

        self.tabs.addTab(self._inner_tab, translator.text("trade_inner_system_open"))
        self.tabs.addTab(self._routes_tab, translator.text("trade_routes_open"))
        self.tabs.addTab(self._round_trip_tab, translator.text("trade_round_trip_open"))

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.close)

        root = QVBoxLayout(self)
        root.addWidget(self.tabs, 1)
        root.addWidget(self.button_box)

        self.tabs.setCurrentIndex(max(0, min(initial_tab, 2)))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # Start only the initially visible tab
        self._on_tab_changed(self.tabs.currentIndex())

    def closeEvent(self, event: QCloseEvent) -> None:
        for tab in (self._inner_tab, self._routes_tab, self._round_trip_tab):
            try:
                tab.shutdown()
            except RuntimeError:
                pass
        super().closeEvent(event)

    def _on_tab_changed(self, index: int) -> None:
        tab = self.tabs.widget(index)
        if hasattr(tab, "start"):
            tab.start()

    def _on_ship_changed(self, nickname: str) -> None:
        self.ship_changed.emit(nickname)
