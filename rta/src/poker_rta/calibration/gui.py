"""Minimal Qt GUI: open a screenshot, click-drag to define ROIs, pick the
current ROI label from a dropdown, save profile YAML.

Not covered by automated tests — run manually via `poker_rta calibrate`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import (
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from poker_rta.calibration.painter import CalibrationDoc, emit_profile
from poker_rta.profile.io import save_profile
from poker_rta.profile.model import REQUIRED_ROIS


class CaptureCanvas(QLabel):
    def __init__(self, doc: CalibrationDoc, current_label: QLineEdit, parent: QWidget) -> None:
        super().__init__(parent)
        self._doc = doc
        self._label = current_label
        self._start: QPoint | None = None
        self._current_rect: QRect | None = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._start is not None:
            self._current_rect = QRect(self._start, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._start is not None and self._current_rect is not None:
            label = self._label.text().strip()
            if label:
                self._doc.rois[label] = (
                    self._current_rect.x(),
                    self._current_rect.y(),
                    self._current_rect.width(),
                    self._current_rect.height(),
                )
        self._start = None
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        for name, (x, y, w, h) in self._doc.rois.items():
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.drawRect(x, y, w, h)
            painter.drawText(x + 2, y - 4, name)
        if self._current_rect is not None:
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._current_rect)


class CalibrationWindow(QMainWindow):
    def __init__(self, screenshot: Path) -> None:
        super().__init__()
        self.setWindowTitle("poker_rta — calibration")
        self._doc = CalibrationDoc(
            name="new_profile",
            version="1.0",
            window_title="change me",
            card_templates_dir="templates/new_profile/cards",
            button_templates={},
        )
        self._label_input = QLineEdit()
        self._label_input.setPlaceholderText("ROI label (e.g. hero_card_1)")
        self._preset = QComboBox()
        self._preset.addItems(sorted(REQUIRED_ROIS))
        self._preset.currentTextChanged.connect(self._label_input.setText)

        self._canvas = CaptureCanvas(self._doc, self._label_input, self)
        pixmap = QPixmap(str(screenshot))
        self._canvas.set_pixmap(pixmap)

        save_btn = QPushButton("Save profile YAML…")
        save_btn.clicked.connect(self._save)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Label:"))
        controls.addWidget(self._label_input, 2)
        controls.addWidget(self._preset, 1)
        controls.addWidget(save_btn)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(controls)
        layout.addWidget(self._canvas)
        self.setCentralWidget(container)

    def _status_bar(self) -> QStatusBar:
        bar = self.statusBar()
        if bar is None:  # pragma: no cover
            bar = QStatusBar(self)
            self.setStatusBar(bar)
        return bar

    def _save(self) -> None:
        missing = REQUIRED_ROIS - self._doc.rois.keys()
        if missing:
            self._status_bar().showMessage(f"missing ROIs: {sorted(missing)}", 5000)
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Save profile", "profile.yaml", "YAML (*.yaml)"
        )
        if not target:
            return
        save_profile(emit_profile(self._doc), Path(target))
        self._status_bar().showMessage(f"saved {target}", 3000)


def run(screenshot: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    win = CalibrationWindow(screenshot)
    win.show()
    app.exec()
