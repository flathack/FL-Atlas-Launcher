from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGraphicsScene, QGraphicsView, QVBoxLayout

from app.i18n import Translator
from app.services.trade_route_service import TradeRoutePreviewData, TradeRoutePreviewObject


class TradeRoutePreviewDialog(QDialog):
    def __init__(self, preview_data: TradeRoutePreviewData, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.preview_data = preview_data
        self.translator = translator

        self.setWindowTitle(self.tr("trade_routes_preview_title", commodity=preview_data.commodity))
        self.resize(1500, 820)
        self.setModal(False)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setBackgroundBrush(QColor("#0b1020"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self.view, 1)
        root.addWidget(buttons)

        self._render_preview()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _render_preview(self) -> None:
        self.scene.clear()
        panel_width = 340.0
        panel_height = 620.0
        gap = 36.0
        left = 30.0
        top = 30.0

        panel_connections: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for index, system in enumerate(self.preview_data.systems):
            x = left + index * (panel_width + gap)
            panel_result = self._draw_system_panel(system, x, top, panel_width, panel_height)
            start_point = panel_result.get("start")
            end_point = panel_result.get("end")
            if isinstance(start_point, tuple) and isinstance(end_point, tuple):
                panel_connections.append((start_point, end_point))

        if len(panel_connections) > 1:
            pen = QPen(QColor("#ef4444"), 2, Qt.PenStyle.DashLine)
            for index in range(len(panel_connections) - 1):
                current_end = panel_connections[index][1]
                next_start = panel_connections[index + 1][0]
                self.scene.addLine(current_end[0], current_end[1], next_start[0], next_start[1], pen)

        bounds = self.scene.itemsBoundingRect()
        if not bounds.isNull():
            self.view.fitInView(bounds.adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_system_panel(self, system, left: float, top: float, width: float, height: float) -> dict[str, tuple[float, float] | None]:
        self.scene.addRect(left, top, width, height, QPen(QColor("#334155"), 1.5))
        title = self.scene.addText(system.display_name)
        title.setDefaultTextColor(QColor("#e2e8f0"))
        title.setPos(left + 10, top + 8)

        all_points = [obj.position for obj in system.objects]
        all_points.extend(point for edge in system.lane_edges for point in edge)
        if system.start_position is not None:
            all_points.append(system.start_position)
        if system.end_position is not None:
            all_points.append(system.end_position)
        if not all_points:
            all_points = [(0.0, 0.0)]

        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        inner_left = left + 18.0
        inner_top = top + 42.0
        inner_width = width - 36.0
        inner_height = height - 60.0

        def to_scene(point: tuple[float, float]) -> tuple[float, float]:
            dx = max(1.0, max_x - min_x)
            dy = max(1.0, max_y - min_y)
            scale = min(inner_width / dx, inner_height / dy)
            pad_x = (inner_width - dx * scale) * 0.5
            pad_y = (inner_height - dy * scale) * 0.5
            sx = inner_left + pad_x + (point[0] - min_x) * scale
            sy = inner_top + pad_y + (point[1] - min_y) * scale
            return sx, sy

        lane_pen = QPen(QColor("#38bdf8"), 1.2)
        for start_point, end_point in system.lane_edges:
            a = to_scene(start_point)
            b = to_scene(end_point)
            self.scene.addLine(a[0], a[1], b[0], b[1], lane_pen)

        for obj in system.objects:
            sx, sy = to_scene(obj.position)
            radius, fill, label_color, show_label = self._object_style(obj)
            self.scene.addEllipse(sx - radius, sy - radius, radius * 2, radius * 2, QPen(QColor("#cbd5e1"), 0.6), fill)
            if show_label:
                label_item = self.scene.addText(obj.label)
                label_item.setDefaultTextColor(label_color)
                label_item.setScale(0.72)
                label_item.setPos(sx + 4, sy - 6)

        route_points = [to_scene(point) for point in system.local_path]
        if len(route_points) >= 2:
            path_pen = QPen(QColor("#ef4444"), 2.4)
            for index in range(len(route_points) - 1):
                a = route_points[index]
                b = route_points[index + 1]
                self.scene.addLine(a[0], a[1], b[0], b[1], path_pen)

        start_scene = None
        end_scene = None
        if system.start_position is not None:
            start_scene = to_scene(system.start_position)
            self.scene.addEllipse(start_scene[0] - 4, start_scene[1] - 4, 8, 8, QPen(QColor("#22c55e"), 1.8), QColor("#22c55e"))
        if system.end_position is not None:
            end_scene = to_scene(system.end_position)
            self.scene.addEllipse(end_scene[0] - 4, end_scene[1] - 4, 8, 8, QPen(QColor("#ef4444"), 1.8), QColor("#ef4444"))
        return {"start": start_scene, "end": end_scene}

    def _object_style(self, obj: TradeRoutePreviewObject) -> tuple[float, QColor, QColor, bool]:
        archetype = obj.archetype.lower()
        if "trade_lane_ring" in archetype or "tradelane_ring" in archetype:
            return 1.8, QColor("#38bdf8"), QColor("#bae6fd"), False
        if any(token in archetype for token in ("jumpgate", "jump_gate", "jumphole", "jump_hole", "nomad_gate")):
            return 3.0, QColor("#f59e0b"), QColor("#fef3c7"), True
        if any(token in archetype for token in ("station", "base", "outpost", "dock_ring")):
            return 3.2, QColor("#a78bfa"), QColor("#ede9fe"), True
        if "planet" in archetype:
            return 3.2, QColor("#22c55e"), QColor("#dcfce7"), False
        if "sun" in archetype or "star" in archetype:
            return 3.8, QColor("#fbbf24"), QColor("#fef3c7"), False
        return 2.0, QColor("#94a3b8"), QColor("#e2e8f0"), False