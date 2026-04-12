from __future__ import annotations

import html
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCompleter,
    QComboBox,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.services.trade_route_service import (
    TradeRoutePlannerResult,
    TradeRoutePreviewObject,
    TradeRouteService,
    TradeRouteUniverseData,
    TradeRouteUniverseSystem,
    TradeRouteZone,
)


def _format_seconds(value: int | None) -> str:
    if value is None:
        return "-"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}:{seconds:02d}"


class _ZoneGraphicsItem(QGraphicsItem):
    def __init__(self, zone: TradeRouteZone, scale: float) -> None:
        super().__init__()
        self.zone = zone
        self._scale = max(float(scale), 1e-6)
        self.hw = max(1.0, float(zone.size[0]) * self._scale)
        self.hd = max(1.0, float(zone.size[1]) * self._scale)
        self.setPos(float(zone.position[0]) * self._scale, float(zone.position[1]) * self._scale)
        self.setZValue(-200)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        zone_name = zone.nickname.lower()
        if zone.zone_type == "death_zone" or "death" in zone_name or zone.damage > 0:
            self._pen = QPen(QColor(220, 50, 50, 200), 1.3, Qt.PenStyle.DashLine)
            self._brush = QBrush(QColor(220, 50, 50, 18))
        elif zone.zone_type == "nebula":
            self._pen = QPen(QColor(150, 80, 220, 170), 1.0, Qt.PenStyle.DashLine)
            self._brush = QBrush(QColor(120, 60, 200, 16))
        else:
            self._pen = QPen(QColor(180, 130, 60, 170), 1.0, Qt.PenStyle.DashLine)
            self._brush = QBrush(QColor(160, 120, 50, 16))

    def boundingRect(self) -> QRectF:
        return QRectF(-self.hw - 2, -self.hd - 2, self.hw * 2 + 4, self.hd * 2 + 4)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        _ = option
        _ = widget
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        painter.drawEllipse(QRectF(-self.hw, -self.hd, self.hw * 2, self.hd * 2))


class _SolarGraphicsItem(QGraphicsEllipseItem):
    def __init__(self, system_nick: str, obj: TradeRoutePreviewObject, scale: float) -> None:
        self.system_nick = system_nick
        self.obj = obj
        self._scale = max(float(scale), 1e-6)
        self._hovered = False
        self.label: QGraphicsTextItem | None = None
        self._label_default_visible = obj.object_type not in {"trade_lane", "buoy"}

        color, base_radius, z_value, font_size = self._style_for_object(obj)
        if obj.object_type in {"planet", "sun"} and obj.radius > 0:
            base_radius = max(base_radius, float(obj.radius) * self._scale)

        super().__init__(-base_radius, -base_radius, base_radius * 2, base_radius * 2)
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
        self.setZValue(z_value)
        self.setPos(float(obj.position[0]) * self._scale, float(obj.position[1]) * self._scale)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)

        if self._label_default_visible:
            self.label = QGraphicsTextItem(obj.name, self)
            self.label.setDefaultTextColor(QColor("#d9e5f4"))
            self.label.setFont(QFont("Sans", font_size))
            self.label.setPos(base_radius + 2.0, -5.0)
            self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    @staticmethod
    def _style_for_object(obj: TradeRoutePreviewObject) -> tuple[QColor, float, float, float]:
        mapping = {
            "sun": (QColor(255, 215, 40), 9.0, 3.0, 8.0),
            "planet": (QColor(60, 130, 220), 7.0, 2.0, 7.0),
            "station": (QColor(80, 210, 100), 3.5, 1.0, 6.0),
            "dock": (QColor(255, 150, 80), 2.5, 1.0, 6.0),
            "jump_gate": (QColor(210, 90, 210), 4.0, 1.0, 6.0),
            "jump_hole": (QColor(160, 80, 220), 4.0, 1.0, 6.0),
            "trade_lane": (QColor(70, 140, 255), 1.2, -1.0, 5.0),
            "depot": (QColor(16, 185, 129), 2.8, 0.0, 5.5),
            "weapons_platform": (QColor(249, 115, 22), 2.8, 0.0, 5.5),
            "mining": (QColor(20, 184, 166), 2.5, 0.0, 5.5),
            "surprise": (QColor(244, 63, 94), 2.4, 0.0, 5.0),
            "buoy": (QColor(255, 200, 60), 1.5, 0.0, 5.0),
        }
        return mapping.get(obj.object_type, (QColor(190, 190, 190), 2.8, 0.0, 5.5))

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if self._hovered:
            rect = self.rect()
            painter.save()
            painter.setPen(QPen(QColor(255, 215, 96, 230), max(1.8, rect.width() * 0.06)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(-2.0, -2.0, 2.0, 2.0))
            painter.restore()


class _UniverseSystemGraphicsItem(_SolarGraphicsItem):
    def __init__(self, system: TradeRouteUniverseSystem, position: tuple[float, float]) -> None:
        fake_obj = TradeRoutePreviewObject(
            nickname=system.nickname,
            name=system.display_name,
            label=system.display_name,
            archetype="",
            position=position,
            object_type="station" if any(obj.object_type in {"station", "dock", "depot"} for obj in system.objects) else "planet",
        )
        super().__init__(system.nickname, fake_obj, 1.0)
        self.system = system
        self.setRect(-6.0, -6.0, 12.0, 12.0)
        self.setBrush(QBrush(QColor(100, 180, 255)))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setZValue(5)
        self.setPos(float(position[0]), float(position[1]))
        if self.label is not None:
            self.label.setPlainText(system.display_name)
            self.label.setFont(QFont("Sans", 7, QFont.Weight.Bold))
            self.label.setPos(-self.label.boundingRect().width() * 0.5, -18.0)


class _ViewerGraphicsView(QGraphicsView):
    system_requested = Signal(str)
    object_requested = Signal(str, str)
    view_resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setBackgroundBrush(QBrush(QColor("#101018")))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._panning = False
        self._pan_start = QPointF()
        self._pressed_item: object | None = None
        self._drag_moved = False

    @property
    def map_scene(self) -> QGraphicsScene:
        return self._scene

    def wheelEvent(self, event) -> None:
        steps = float(event.angleDelta().y()) / 120.0
        self.scale(math.pow(1.08, steps), math.pow(1.08, steps))

    def mousePressEvent(self, event) -> None:
        if event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton}:
            self._panning = True
            self._pan_start = event.position()
            self._pressed_item = self._pick_interactive_item(event.pos()) if event.button() == Qt.MouseButton.LeftButton else None
            self._drag_moved = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            if (event.position() - self._pan_start).manhattanLength() > 3.0:
                self._drag_moved = True
            previous = self.mapToScene(self._pan_start.toPoint())
            self._pan_start = event.position()
            current = self.mapToScene(self._pan_start.toPoint())
            center = self.mapToScene(self.viewport().rect().center())
            self.centerOn(center - (current - previous))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton} and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if event.button() == Qt.MouseButton.LeftButton and not self._drag_moved:
                item = self._pressed_item
                if isinstance(item, _UniverseSystemGraphicsItem):
                    self.system_requested.emit(item.system.nickname)
                elif isinstance(item, _SolarGraphicsItem):
                    self.object_requested.emit(item.system_nick, item.obj.nickname)
            self._pressed_item = None
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view_resized.emit()

    def fit_rect(self, rect: QRectF) -> None:
        if rect.isNull():
            return
        self.resetTransform()
        self.centerOn(rect.center())
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _pick_interactive_item(self, view_pos) -> object | None:
        scene_pos = self.mapToScene(view_pos)
        for item in self._scene.items(scene_pos):
            if isinstance(item, QGraphicsTextItem):
                continue
            if isinstance(item, (_UniverseSystemGraphicsItem, _SolarGraphicsItem)):
                return item
        return None


class UniverseViewerTab(QWidget):
    def __init__(
        self,
        installation: Installation,
        service: TradeRouteService,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = installation
        self.service = service
        self.translator = translator
        self.universe_data = self.service.build_universe_map_data(installation)
        self.system_lookup = {system.nickname: system for system in self.universe_data.systems}
        self.route_point_lookup = {point.id: point for point in self.universe_data.route_points}
        self.current_system = self.universe_data.systems[0].nickname if self.universe_data.systems else ""
        self.selected_object_id = ""
        self.route_result: TradeRoutePlannerResult | None = None
        self._mode = "universe"
        self._sector_key = "sirius"
        self._sector_defs = self._build_sector_defs()
        self._multiverse_detected = any(system.map_positions for system in self.universe_data.systems)

        self.universe_button = QPushButton(self.tr("universe_viewer_mode_universe"))
        self.system_button = QPushButton(self.tr("universe_viewer_mode_system"))
        self.sector_combo = QComboBox()
        self.system_combo = QComboBox()
        self.route_start_combo = QComboBox()
        self.route_end_combo = QComboBox()
        self.route_summary = QTextBrowser()
        self.find_route_button = QPushButton(self.tr("universe_viewer_find_route"))
        self.clear_route_button = QPushButton(self.tr("universe_viewer_clear_route"))
        self.view = _ViewerGraphicsView(self)

        self._build_ui()
        self._populate_sectors()
        self._populate_systems()
        self._populate_route_points()
        self._connect_signals()
        self._refresh_route_summary()
        self._refresh_scene()
        QTimer.singleShot(0, self._fit_view_to_scene)

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def start(self) -> None:
        QTimer.singleShot(0, self._fit_view_to_scene)
        QTimer.singleShot(40, self._fit_view_to_scene)
        return None

    def shutdown(self) -> None:
        return None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_view_to_scene)
        QTimer.singleShot(40, self._fit_view_to_scene)

    def _build_ui(self) -> None:
        self.universe_button.setCheckable(True)
        self.system_button.setCheckable(True)
        self.universe_button.setChecked(True)

        route_box = QGroupBox(self.tr("universe_viewer_route_group"))
        route_layout = QVBoxLayout(route_box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.universe_button)
        mode_row.addWidget(self.system_button)
        route_layout.addLayout(mode_row)

        view_form = QFormLayout()
        view_form.addRow(self.tr("universe_viewer_sector_label"), self.sector_combo)
        view_form.addRow(self.tr("universe_viewer_system_label"), self.system_combo)
        route_layout.addLayout(view_form)

        route_form = QFormLayout()
        route_form.addRow(self.tr("universe_viewer_route_start"), self.route_start_combo)
        route_form.addRow(self.tr("universe_viewer_route_end"), self.route_end_combo)
        route_layout.addLayout(route_form)
        route_button_row = QHBoxLayout()
        route_button_row.addWidget(self.find_route_button)
        route_button_row.addWidget(self.clear_route_button)
        route_layout.addLayout(route_button_row)
        self.route_summary.setMinimumHeight(220)
        route_layout.addWidget(self.route_summary)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(route_box)
        left_layout.addStretch(1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1040])

        root = QVBoxLayout(self)
        root.addWidget(splitter, 1)

    def _connect_signals(self) -> None:
        self.universe_button.clicked.connect(lambda: self._set_mode("universe"))
        self.system_button.clicked.connect(lambda: self._set_mode("system"))
        self.sector_combo.currentIndexChanged.connect(self._on_sector_changed)
        self.system_combo.currentIndexChanged.connect(self._on_system_changed)
        self.view.system_requested.connect(self._on_canvas_system_requested)
        self.view.object_requested.connect(self._on_canvas_object_requested)
        self.view.view_resized.connect(self._on_view_resized)
        self.find_route_button.clicked.connect(self._find_route)
        self.clear_route_button.clicked.connect(self._clear_route)

    def _populate_sectors(self) -> None:
        self.sector_combo.clear()
        for key, label in self._sector_defs:
            self.sector_combo.addItem(label, key)
        index = self.sector_combo.findData(self._sector_key)
        if index >= 0:
            self.sector_combo.setCurrentIndex(index)

    def _populate_systems(self) -> None:
        self.system_combo.clear()
        for system in self.universe_data.systems:
            self.system_combo.addItem(system.display_name, system.nickname)
        index = self.system_combo.findData(self.current_system)
        if index >= 0:
            self.system_combo.setCurrentIndex(index)

    def _populate_route_points(self) -> None:
        for combo in (self.route_start_combo, self.route_end_combo):
            combo.clear()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            for point in self.universe_data.route_points:
                combo.addItem(point.label, point.id)
            completer = combo.completer()
            if completer is not None:
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self.universe_button.setChecked(mode == "universe")
        self.system_button.setChecked(mode == "system")
        self.sector_combo.setEnabled(mode == "universe")
        self._refresh_scene()

    def _on_sector_changed(self, _index: int) -> None:
        self._sector_key = str(self.sector_combo.currentData() or "sirius")
        self._refresh_scene()

    def _on_system_changed(self, _index: int) -> None:
        nickname = self.system_combo.currentData()
        if not nickname:
            return
        self.current_system = str(nickname)
        self.selected_object_id = ""
        self._refresh_scene()

    def _on_canvas_system_requested(self, system_nickname: str) -> None:
        index = self.system_combo.findData(system_nickname)
        if index >= 0:
            self.system_combo.setCurrentIndex(index)
        self._set_mode("system")

    def _on_canvas_object_requested(self, system_nickname: str, object_nickname: str) -> None:
        if system_nickname != self.current_system:
            index = self.system_combo.findData(system_nickname)
            if index >= 0:
                self.system_combo.setCurrentIndex(index)
        self.selected_object_id = f"{system_nickname}|{object_nickname}"
        self._set_mode("system")

    def _resolve_point_id(self, combo: QComboBox) -> str:
        text = combo.currentText().strip()
        index = combo.findText(text, Qt.MatchFlag.MatchExactly)
        if index >= 0:
            data = combo.itemData(index)
            return str(data) if data else ""
        data = combo.currentData()
        return str(data) if data else ""

    def _find_route(self) -> None:
        start_id = self._resolve_point_id(self.route_start_combo)
        end_id = self._resolve_point_id(self.route_end_combo)
        if not start_id or not end_id or start_id == end_id:
            self.route_result = None
            self._refresh_route_summary(self.tr("universe_viewer_route_invalid"))
            self._refresh_scene()
            return
        self.route_result = self.service.find_fastest_route(self.installation, start_id, end_id)
        if self.route_result is None:
            self._refresh_route_summary(self.tr("universe_viewer_route_none"))
            self._refresh_scene()
            return
        if self.current_system not in self.route_result.system_nicknames and self.route_result.system_nicknames:
            index = self.system_combo.findData(self.route_result.system_nicknames[0])
            if index >= 0:
                self.system_combo.setCurrentIndex(index)
        self._refresh_route_summary()
        self._refresh_scene()

    def _clear_route(self) -> None:
        self.route_result = None
        self._refresh_route_summary()
        self._refresh_scene()

    def _refresh_route_summary(self, message: str | None = None) -> None:
        if message:
            self.route_summary.setText(message)
            return
        if self.route_result is None:
            self.route_summary.setText(self.tr("universe_viewer_route_hint"))
            return
        system_path = " -> ".join(self.route_result.system_names)
        rows = "".join(
            "<tr>"
            f"<td style='padding:4px 6px; color:#9fb2cf;'>{html.escape(self._segment_label(step.segment_type))}</td>"
            f"<td style='padding:4px 6px; color:#eef4ff;'>{html.escape(step.system)}</td>"
            f"<td style='padding:4px 6px; color:#dbeafe;'>{html.escape(step.from_label)} -> {html.escape(step.to_label)}</td>"
            f"<td style='padding:4px 6px; text-align:right; color:#8fe1b5;'>{html.escape(_format_seconds(step.seconds))}</td>"
            "</tr>"
            for step in self.route_result.steps
        )
        self.route_summary.setHtml(
            "<div style='font-family:Segoe UI;'>"
            f"<div style='color:#8db7ff; font-size:11px; text-transform:uppercase; letter-spacing:0.08em;'>{html.escape(self.tr('universe_viewer_route_fastest'))}</div>"
            f"<div style='color:#eef4ff; font-size:18px; font-weight:700; margin:4px 0 8px 0;'>{html.escape(_format_seconds(self.route_result.total_seconds))}</div>"
            f"<div style='color:#cbd5e1; margin-bottom:10px;'>{html.escape(system_path)}</div>"
            f"<table cellspacing='0' cellpadding='0' style='width:100%;'>{rows}</table></div>"
        )

    def _refresh_scene(self) -> None:
        scene = self.view.map_scene
        scene.clear()
        if self._mode == "universe":
            self._build_universe_scene(scene)
        else:
            self._build_system_scene(scene)
        self._fit_view_to_scene()

    def _fit_view_to_scene(self) -> None:
        if self._mode == "universe":
            bounds = self.view.map_scene.itemsBoundingRect()
            if not bounds.isNull():
                target = bounds.adjusted(-24, -24, 24, 24)
                self.view.map_scene.setSceneRect(target)
                self.view.fit_rect(target)
        else:
            target = self.view.map_scene.sceneRect()
            if not target.isNull():
                self.view.fit_rect(target)

    def _on_view_resized(self) -> None:
        if self._mode == "universe":
            self._fit_view_to_scene()

    def _build_universe_scene(self, scene: QGraphicsScene) -> None:
        systems = [system for system in self.universe_data.systems if self._universe_system_visible(system, self._sector_key)]
        if not systems:
            systems = list(self.universe_data.systems)
        if self._sector_key == "galaxy":
            positions = self._build_galaxy_positions(systems)
        else:
            positions = {system.nickname: self._universe_system_position(system, self._sector_key) for system in systems}
        if not positions:
            return
        min_x = min(point[0] for point in positions.values())
        max_x = max(point[0] for point in positions.values())
        min_y = min(point[1] for point in positions.values())
        max_y = max(point[1] for point in positions.values())
        width = 1400.0
        height = 980.0
        padding = 90.0
        range_x = max(1.0, max_x - min_x)
        range_y = max(1.0, max_y - min_y)
        scale = min((width - padding * 2) / range_x, (height - padding * 2) / range_y)
        offset_x = (width - range_x * scale) * 0.5
        offset_y = (height - range_y * scale) * 0.5

        def map_point(point: tuple[float, float]) -> tuple[float, float]:
            return (
                offset_x + (point[0] - min_x) * scale,
                offset_y + (point[1] - min_y) * scale,
            )

        mapped = {nick: map_point(point) for nick, point in positions.items()}
        route_edges = {
            tuple(sorted((a, b)))
            for a, b in zip(
                self.route_result.system_nicknames if self.route_result else [],
                self.route_result.system_nicknames[1:] if self.route_result else [],
            )
        }

        for connection in self.universe_data.connections:
            start = mapped.get(connection.from_system_nickname)
            end = mapped.get(connection.to_system_nickname)
            if start is None or end is None:
                continue
            is_route = tuple(sorted((connection.from_system_nickname, connection.to_system_nickname))) in route_edges
            color = QColor("#f59e0b" if connection.connection_type == "jump_gate" else "#a78bfa")
            pen = QPen(color, 3.0 if is_route else 1.4)
            if connection.connection_type == "jump_hole":
                pen.setStyle(Qt.PenStyle.DashLine)
            line = scene.addLine(start[0], start[1], end[0], end[1], pen)
            line.setZValue(-2)

        for system in systems:
            scene.addItem(_UniverseSystemGraphicsItem(system, mapped[system.nickname]))

    def _build_system_scene(self, scene: QGraphicsScene) -> None:
        system = self.system_lookup.get(self.current_system)
        if system is None:
            return
        navmap_scale = max(float(system.navmap_scale or 1.0), 0.1)
        half_extent = 120000.0 / navmap_scale
        scene_scale = 1000.0 / (half_extent * 2.0)
        grid_rect = QRectF(-half_extent * scene_scale, -half_extent * scene_scale, half_extent * 2.0 * scene_scale, half_extent * 2.0 * scene_scale)
        pad = grid_rect.width() / 8.0
        scene.setSceneRect(grid_rect.adjusted(-pad, -pad, pad, pad))

        grid_pen = QPen(QColor(132, 177, 255, 46), 1.0)
        grid_pen.setCosmetic(True)
        cell = grid_rect.width() / 8.0
        labels = list("ABCDEFGH")
        for index in range(9):
            x = grid_rect.left() + index * cell
            y = grid_rect.top() + index * cell
            scene.addLine(x, grid_rect.top(), x, grid_rect.bottom(), grid_pen)
            scene.addLine(grid_rect.left(), y, grid_rect.right(), y, grid_pen)
        for index in range(8):
            col = scene.addText(labels[index])
            col.setDefaultTextColor(QColor("#dce7ff"))
            col.setPos(grid_rect.left() + index * cell + cell * 0.45, grid_rect.top() - 26.0)
            row = scene.addText(str(index + 1))
            row.setDefaultTextColor(QColor("#dce7ff"))
            row.setPos(grid_rect.left() - 22.0, grid_rect.top() + index * cell + cell * 0.45)

        for zone in system.zones:
            scene.addItem(_ZoneGraphicsItem(zone, scene_scale))

        lane_pen = QPen(QColor("#38bdf8"), 1.3)
        lane_pen.setCosmetic(True)
        for chain in system.trade_lanes:
            scaled_points = [(float(point[0]) * scene_scale, float(point[1]) * scene_scale) for point in chain]
            for first, second in zip(scaled_points, scaled_points[1:]):
                scene.addLine(first[0], first[1], second[0], second[1], lane_pen)

        route_points = list(self.route_result.local_paths_by_system.get(system.nickname, []) if self.route_result else [])
        if len(route_points) >= 2:
            route_pen = QPen(QColor("#ef4444"), 2.4)
            route_pen.setCosmetic(True)
            scaled_route = [(float(point[0]) * scene_scale, float(point[1]) * scene_scale) for point in route_points]
            for first, second in zip(scaled_route, scaled_route[1:]):
                scene.addLine(first[0], first[1], second[0], second[1], route_pen)

        for obj in system.objects:
            item = _SolarGraphicsItem(system.nickname, obj, scene_scale)
            if f"{system.nickname}|{obj.nickname}" == self.selected_object_id:
                item.setPen(QPen(QColor("#fff3bf"), 1.6))
            scene.addItem(item)

    def _build_sector_defs(self) -> list[tuple[str, str]]:
        map_names: set[str] = set()
        map_label_ids: dict[str, list[str]] = {}
        for system in self.universe_data.systems:
            for entry in system.map_positions:
                map_name = str(entry.get("map", "")).strip().lower()
                if map_name:
                    map_names.add(map_name)
                    ids = map_label_ids.setdefault(map_name, [])
                    for label_id in list(entry.get("label_ids", []) or []):
                        text = str(label_id or "").strip()
                        if text and text not in ids:
                            ids.append(text)

        defs: list[tuple[str, str]] = []
        sirius_source = "sector01" if "sector01" in map_names else "universe"
        sirius_ids = list(map_label_ids.get("sector01", []))
        sirius_label = self.tr("universe_viewer_sector_sirius")
        if sirius_source != "universe" and sirius_ids:
            sirius_label = f"{sirius_label} ({sirius_ids[0]})"
        defs.append(("sirius", sirius_label))

        for map_name in sorted((name for name in map_names if name != "sector01"), key=str.lower):
            display = self._pretty_sector_name(map_name)
            ids = list(map_label_ids.get(map_name, []))
            if ids:
                display = f"{display} ({ids[0]})"
            defs.append((map_name, display))
        if len(defs) > 1:
            defs.append(("galaxy", self.tr("universe_viewer_sector_galaxy")))
        return defs

    @staticmethod
    def _pretty_sector_name(map_name: str) -> str:
        name = str(map_name or "").strip()
        if name.lower().startswith("sector") and name[6:].isdigit():
            return f"Sector {name[6:]}"
        return name.replace("_", " ").title() or map_name

    @staticmethod
    def _universe_system_position(system: TradeRouteUniverseSystem, sector_key: str) -> tuple[float, float]:
        if sector_key in {"", "sirius"}:
            source_map = "sector01" if any(str(entry.get("map", "")).strip().lower() == "sector01" for entry in system.map_positions) else "universe"
        elif sector_key == "galaxy":
            return system.universe_position
        else:
            source_map = sector_key
        for entry in system.map_positions:
            if str(entry.get("map", "")).strip().lower() == source_map:
                pos = entry.get("pos")
                if isinstance(pos, tuple):
                    return pos
                if isinstance(pos, list) and len(pos) >= 2:
                    return (float(pos[0]), float(pos[1]))
        return system.universe_position

    @staticmethod
    def _pretty_sector_sort_key(name: str) -> tuple[int, int, str]:
        text = str(name or "").strip().lower()
        if text.startswith("sector") and text[6:].isdigit():
            return (0, int(text[6:]), text)
        return (1, 0, text)

    def _universe_system_visible(self, system: TradeRouteUniverseSystem, sector_key: str) -> bool:
        if sector_key in {"", "galaxy"}:
            return True
        source_map = "sector01" if sector_key == "sirius" else sector_key
        available_maps = {
            str(entry.get("map", "")).strip().lower()
            for entry in system.map_positions
            if str(entry.get("map", "")).strip()
        }
        if source_map != "universe":
            return source_map in available_maps
        if self._multiverse_detected:
            has_explicit_maps = any(map_name != "universe" for map_name in available_maps)
            return ("sector01" in available_maps) if has_explicit_maps else True
        if not available_maps:
            return source_map == "universe"
        return source_map in available_maps

    def _build_galaxy_positions(self, systems: list[TradeRouteUniverseSystem]) -> dict[str, tuple[float, float]]:
        sector_order: list[str] = []
        for key_name, _label in self._sector_defs:
            if key_name == "galaxy":
                continue
            source_map = "sector01" if key_name == "sirius" else key_name
            if source_map not in sector_order:
                sector_order.append(source_map)
        if not sector_order:
            sector_order = ["universe"]

        by_sector: dict[str, list[tuple[str, tuple[float, float]]]] = {key: [] for key in sector_order}
        for system in systems:
            pos_map: dict[str, tuple[float, float]] = {}
            for entry in system.map_positions:
                map_name = str(entry.get("map", "")).strip().lower()
                pos = entry.get("pos")
                if map_name and isinstance(pos, tuple):
                    pos_map[map_name] = (float(pos[0]), float(pos[1]))
                elif map_name and isinstance(pos, list) and len(pos) >= 2:
                    pos_map[map_name] = (float(pos[0]), float(pos[1]))
            chosen_sector = ""
            chosen_pos: tuple[float, float] | None = None
            for source_map in sector_order:
                if source_map in pos_map:
                    chosen_sector = source_map
                    chosen_pos = pos_map[source_map]
                    break
            if chosen_pos is None:
                chosen_sector = "universe"
                chosen_pos = system.universe_position
            by_sector.setdefault(chosen_sector, []).append((system.nickname, chosen_pos))

        sector_center: dict[str, tuple[float, float]] = {}
        max_half_span = 1.0
        for source_map, rows in by_sector.items():
            if not rows:
                continue
            xs = [point[1][0] for point in rows]
            ys = [point[1][1] for point in rows]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            center_x = (min_x + max_x) * 0.5
            center_y = (min_y + max_y) * 0.5
            half_span_x = max(1.0, (max_x - min_x) * 0.5)
            half_span_y = max(1.0, (max_y - min_y) * 0.5)
            local_radius = math.hypot(half_span_x, half_span_y)
            sector_center[source_map] = (center_x, center_y)
            max_half_span = max(max_half_span, local_radius)

        sirius_source = "sector01" if "sector01" in sector_order else "universe"
        center_sector = sirius_source if sirius_source in sector_center else ""
        ring_sectors = [name for name in sector_order if name in sector_center and name != center_sector]
        ring_sectors.sort(key=self._pretty_sector_sort_key)
        ring_count = len(ring_sectors)
        if ring_count <= 1:
            circle_radius = 0.0
        else:
            min_gap = max_half_span * 1.25
            min_chord = max_half_span * 2.6 + min_gap
            circle_radius = max(min_chord / (2.0 * math.sin(math.pi / ring_count)), max_half_span * 2.0)

        sector_offset: dict[str, tuple[float, float]] = {}
        if center_sector:
            base_x, base_y = sector_center[center_sector]
            sector_offset[center_sector] = (-base_x, -base_y)
        for index, source_map in enumerate(ring_sectors):
            angle = (2.0 * math.pi * index / max(1, ring_count)) - (math.pi * 0.5)
            target_x = math.cos(angle) * circle_radius
            target_y = math.sin(angle) * circle_radius
            base_x, base_y = sector_center[source_map]
            sector_offset[source_map] = (target_x - base_x, target_y - base_y)

        result: dict[str, tuple[float, float]] = {}
        for system in systems:
            pos_map: dict[str, tuple[float, float]] = {}
            for entry in system.map_positions:
                map_name = str(entry.get("map", "")).strip().lower()
                pos = entry.get("pos")
                if map_name and isinstance(pos, tuple):
                    pos_map[map_name] = (float(pos[0]), float(pos[1]))
                elif map_name and isinstance(pos, list) and len(pos) >= 2:
                    pos_map[map_name] = (float(pos[0]), float(pos[1]))
            source_choice = ""
            base_pos: tuple[float, float] | None = None
            for source_map in sector_order:
                if source_map in pos_map:
                    source_choice = source_map
                    base_pos = pos_map[source_map]
                    break
            if base_pos is None:
                source_choice = "universe"
                base_pos = system.universe_position
            offset_x, offset_y = sector_offset.get(source_choice, (0.0, 0.0))
            result[system.nickname] = (float(base_pos[0]) + float(offset_x), float(base_pos[1]) + float(offset_y))
        return result

    def _type_label(self, object_type: str) -> str:
        return {
            "sun": self.tr("universe_type_sun"),
            "planet": self.tr("universe_type_planet"),
            "station": self.tr("universe_type_station"),
            "dock": self.tr("universe_type_dock"),
            "trade_lane": self.tr("universe_type_trade_lane"),
            "jump_gate": self.tr("universe_type_jump_gate"),
            "jump_hole": self.tr("universe_type_jump_hole"),
            "depot": self.tr("universe_type_depot"),
            "weapons_platform": self.tr("universe_type_weapons_platform"),
            "buoy": self.tr("universe_type_buoy"),
            "mining": self.tr("universe_type_mining"),
            "surprise": self.tr("universe_type_surprise"),
        }.get(object_type, object_type.replace("_", " ").title())

    def _segment_label(self, segment_type: str) -> str:
        return {
            "jump": self.tr("trade_routes_detail_jump"),
            "trade_lane": self.tr("trade_routes_detail_trade_lane"),
            "open_space": self.tr("trade_routes_detail_open_space"),
        }.get(segment_type, segment_type.replace("_", " ").title())
