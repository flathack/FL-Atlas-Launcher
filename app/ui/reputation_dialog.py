from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QGridLayout,
)

from app.i18n import Translator
from app.services.trade_route_service import TradeRouteFactionOption


class ReputationDialog(QDialog):
    def __init__(
        self,
        factions: list[TradeRouteFactionOption],
        current_values: dict[str, float],
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.factions = factions
        self.translator = translator
        self._sliders: dict[str, QSlider] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._current_values = {
            str(nickname).strip().lower(): max(-1.0, min(1.0, float(value)))
            for nickname, value in current_values.items()
        }

        self.setWindowTitle(self.tr("reputation_dialog_title"))
        self.resize(760, 720)
        self.setModal(True)

        self.hint_label = QLabel(self.tr("reputation_dialog_hint"))
        self.hint_label.setWordWrap(True)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.slider_grid = QGridLayout(self.scroll_content)
        self.slider_grid.setContentsMargins(12, 12, 12, 12)
        self.slider_grid.setHorizontalSpacing(16)
        self.slider_grid.setVerticalSpacing(10)
        self.scroll_area.setWidget(self.scroll_content)

        self.reset_button = QPushButton(self.tr("reputation_dialog_reset"))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        self._build_rows()
        self._connect_signals()

        controls = QHBoxLayout()
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        controls.addWidget(self.button_box)

        root = QVBoxLayout(self)
        root.addWidget(self.hint_label)
        root.addWidget(self.scroll_area, 1)
        root.addLayout(controls)

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_rows(self) -> None:
        for row_index, faction in enumerate(self.factions):
            title = QLabel(faction.display_name)
            title.setToolTip(faction.nickname)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-100, 100)
            slider.setSingleStep(1)
            slider.setPageStep(10)
            slider.setValue(int(round(self._current_values.get(faction.nickname.lower(), 0.0) * 100)))
            value_label = QLabel(self._format_value(slider.value()))
            value_label.setMinimumWidth(44)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            slider.valueChanged.connect(lambda value, nickname=faction.nickname.lower(): self._on_slider_changed(nickname, value))

            self._sliders[faction.nickname.lower()] = slider
            self._value_labels[faction.nickname.lower()] = value_label

            self.slider_grid.addWidget(title, row_index, 0)
            self.slider_grid.addWidget(slider, row_index, 1)
            self.slider_grid.addWidget(value_label, row_index, 2)

        self.slider_grid.setColumnStretch(1, 1)

    def _connect_signals(self) -> None:
        self.reset_button.clicked.connect(self._reset_values)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _on_slider_changed(self, nickname: str, value: int) -> None:
        label = self._value_labels.get(nickname)
        if label is not None:
            label.setText(self._format_value(value))

    def _reset_values(self) -> None:
        for slider in self._sliders.values():
            slider.setValue(0)

    def values(self) -> dict[str, float]:
        return {
            nickname: slider.value() / 100.0
            for nickname, slider in self._sliders.items()
        }

    def _format_value(self, slider_value: int) -> str:
        return f"{slider_value / 100.0:+.2f}"