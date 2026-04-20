"""Minimal Qt GUI: open a screenshot, click-drag to define ROIs, pick the
current ROI label from a dropdown, save profile YAML.

Not covered by automated tests — run manually via `poker_rta calibrate`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import (
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from poker_rta.calibration.painter import CalibrationDoc, emit_profile
from poker_rta.calibration.preview import ROIPreview, extract_preview
from poker_rta.calibration.scripted_frames import (
    format_validation_report_html,
    load_scripted_corpus,
    run_scripted_validation,
)
from poker_rta.cv.cards import CardClassifier
from poker_rta.overlay.confidence import render_line
from poker_rta.profile.io import save_profile
from poker_rta.profile.model import REQUIRED_ROIS, PlatformProfile


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


def _ndarray_from_pixmap(pixmap: QPixmap) -> np.ndarray:
    """Convert a QPixmap to an (h, w, 3) uint8 numpy array (RGB)."""
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    width, height = img.width(), img.height()
    ptr = img.bits()
    ptr.setsize(height * width * 3)
    arr: np.ndarray = np.frombuffer(ptr, dtype=np.uint8)  # type: ignore[call-overload]
    return arr.reshape((height, width, 3)).copy()


def _null_interpret(crop: np.ndarray) -> tuple[str, float]:
    """Placeholder interpreter: reports crop mean as a proxy confidence."""
    if crop.size == 0:
        return ("(empty)", 0.0)
    mean_val = float(crop.mean()) / 255.0
    return (f"mean={mean_val:.2f}", mean_val)


class PreviewPanel(QWidget):
    """Scrollable list of ROI crops with interpretation text and confidence dot.

    Call :meth:`refresh` with the current screenshot pixmap and ROI dict to
    repopulate the panel.  The interpret callable defaults to
    :func:`_null_interpret`; callers may supply a richer one.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._rows: list[QWidget] = []

    def refresh(
        self,
        pixmap: QPixmap,
        rois: dict[str, tuple[int, int, int, int]],
        interpret: object = None,
    ) -> None:
        """Rebuild the panel from the current ROI definitions."""
        interp = interpret if callable(interpret) else _null_interpret

        # Remove old rows
        for row in self._rows:
            self._layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        if not rois:
            placeholder = QLabel("<i>No ROIs defined yet.</i>")
            self._layout.addWidget(placeholder)
            self._rows.append(placeholder)
            return

        image = _ndarray_from_pixmap(pixmap)
        for name, roi_tuple in sorted(rois.items()):
            preview: ROIPreview = extract_preview(name, image, roi_tuple, interp)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)

            # Thumbnail (crop scaled to 64 px wide)
            x, y, w, h = roi_tuple
            crop_px = pixmap.copy(x, y, w, h)
            if not crop_px.isNull() and crop_px.width() > 0:
                thumb = crop_px.scaledToWidth(64, Qt.TransformationMode.SmoothTransformation)
            else:
                thumb = QPixmap(64, 32)
                thumb.fill(Qt.GlobalColor.darkGray)
            thumb_label = QLabel()
            thumb_label.setPixmap(thumb)
            thumb_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            row_layout.addWidget(thumb_label)

            # Confidence line using render_line from overlay/confidence.py
            info_html = render_line(f"{name}: {preview.interpretation}", preview.confidence)
            info_label = QLabel(info_html)
            info_label.setTextFormat(Qt.TextFormat.RichText)
            row_layout.addWidget(info_label, 1)

            self._layout.addWidget(row)
            self._rows.append(row)


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

        self._pixmap = QPixmap(str(screenshot))
        self._canvas = CaptureCanvas(self._doc, self._label_input, self)
        self._canvas.set_pixmap(self._pixmap)

        save_btn = QPushButton("Save profile YAML…")
        save_btn.clicked.connect(self._save)

        preview_btn = QPushButton("Refresh preview")
        preview_btn.clicked.connect(self._refresh_preview)

        self._test_btn = QPushButton("Test calibration")
        self._test_btn.clicked.connect(self._run_test_calibration)
        self._test_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Label:"))
        controls.addWidget(self._label_input, 2)
        controls.addWidget(self._preset, 1)
        controls.addWidget(save_btn)
        controls.addWidget(preview_btn)
        controls.addWidget(self._test_btn)

        # Preview panel in a scroll area on the right side
        self._preview_panel = PreviewPanel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._preview_panel)
        scroll.setMinimumWidth(280)

        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.addLayout(controls)
        canvas_layout.addWidget(self._canvas)

        main_row = QHBoxLayout()
        main_row.addWidget(canvas_container, 3)
        main_row.addWidget(scroll, 1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(main_row)
        self.setCentralWidget(container)

    def _refresh_preview(self) -> None:
        """Repopulate the preview panel from the current ROI definitions."""
        self._preview_panel.refresh(self._pixmap, dict(self._doc.rois))
        # Unlock the Test-calibration button once every required ROI is drawn.
        self._test_btn.setEnabled(self._doc.rois.keys() >= REQUIRED_ROIS)

    def _run_test_calibration(self) -> None:
        """Run the scripted-hand validation against the current profile
        draft and show results in a modal. Today's corpus lives under
        `tests/fixtures/recordings/mock_script/`."""
        corpus_dir = Path(__file__).resolve().parents[3] / "tests/fixtures/recordings/mock_script"
        try:
            frames = load_scripted_corpus(corpus_dir)
            profile = PlatformProfile.model_validate(emit_profile(self._doc))
            templates_dir = Path(profile.card_templates_dir)
            if not templates_dir.exists():
                self._status_bar().showMessage(f"card templates missing at {templates_dir}", 5000)
                return
            classifier = CardClassifier(templates_dir=templates_dir)
            rows = run_scripted_validation(frames, profile, classifier)
        except Exception as exc:  # pragma: no cover - surfaced to user
            self._status_bar().showMessage(f"calibration test failed: {exc}", 5000)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Calibration test results")
        layout = QVBoxLayout(dialog)
        report = QLabel(format_validation_report_html(rows))
        report.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(report)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

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
