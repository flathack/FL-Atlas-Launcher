from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from app.i18n import Translator
from app.services.trade_route_service import TradeRoutePreviewData
from app.ui.widgets.trade_route_preview_widget import TradeRoutePreviewWidget


class TradeRoutePreviewDialog(QDialog):
    def __init__(self, preview_data: TradeRoutePreviewData, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.preview_data = preview_data
        self.translator = translator

        self.setWindowTitle(self.tr("trade_routes_preview_title", commodity=preview_data.commodity))
        self.resize(1500, 820)
        self.setModal(False)

        self.preview_widget = TradeRoutePreviewWidget(self)
        self.preview_widget.set_preview_data(preview_data)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self.preview_widget, 1)
        root.addWidget(buttons)

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)