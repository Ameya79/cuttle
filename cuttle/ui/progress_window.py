"""Floating progress window implemented via PySide6.

Per TRD §6.9 and task card P2-06:
- Anchored to bottom-right corner of screen above Windows taskbar.
- Non-focus-stealing tool window with smooth dark aesthetic.
- Displays per-file rows with live percentage and progress bar.
- Individual and global 'Cancel' buttons.
- Automatically closes after all conversions in the batch finish.
- Headless testable via QT_QPA_PLATFORM=offscreen.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cuttle.worker.queue import EventType, QueueEvent

# Dark UI Design Tokens
BG_CARD = "#18181b"
BG_ROW = "#27272a"
BORDER_COLOR = "#3f3f46"
TEXT_PRIMARY = "#f4f4f5"
TEXT_MUTED = "#a1a1aa"
ACCENT_CYAN = "#38bdf8"
ACCENT_GREEN = "#22c55e"
ACCENT_RED = "#ef4444"


def get_or_create_app() -> QApplication:
    """Return existing QApplication or create a new instance."""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        if os.environ.get("QT_QPA_PLATFORM") is None and sys.platform != "win32":
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app


class JobRowWidget(QWidget):
    """Visual row for an individual file conversion."""

    cancel_requested = Signal(str)

    def __init__(
        self,
        job_id: str,
        src_path: str,
        dst_fmt: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self._src_name = Path(src_path).name
        self._dst_fmt = dst_fmt.upper()
        self._is_done = False

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Top row: filename and percent/status
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title_text = f"{self._src_name} ➔ {self._dst_fmt}"
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 12px;")

        self.lbl_status = QLabel("Queued")
        self.lbl_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

        self.btn_cancel = QToolButton()
        self.btn_cancel.setText("✕")
        self.btn_cancel.setToolTip("Cancel this file")
        self.btn_cancel.setStyleSheet(
            f"QToolButton {{ color: {TEXT_MUTED}; background: transparent; "
            f"border: none; font-size: 12px; }}"
            f"QToolButton:hover {{ color: {ACCENT_RED}; }}"
        )
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

        top_row.addWidget(self.lbl_title, 1)
        top_row.addWidget(self.lbl_status)
        top_row.addWidget(self.btn_cancel)
        layout.addLayout(top_row)

        # Bottom row: progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {BG_ROW}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background-color: {ACCENT_CYAN}; border-radius: 3px; }}"
        )
        layout.addWidget(self.progress_bar)

    def _on_cancel_clicked(self) -> None:
        if not self._is_done:
            self.cancel_requested.emit(self.job_id)

    def set_progress(self, pct: float | None, msg: str = "") -> None:
        """Update live progress bar and status text."""
        if self._is_done:
            return
        if pct is not None:
            int_pct = max(0, min(100, int(pct)))
            self.progress_bar.setValue(int_pct)
            status_text = f"{int_pct}%"
            if msg:
                status_text += f" ({msg})"
            self.lbl_status.setText(status_text)
            self.lbl_status.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px;")
        elif msg:
            self.lbl_status.setText(msg)

    def set_started(self) -> None:
        if not self._is_done:
            self.lbl_status.setText("Converting...")
            self.lbl_status.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px;")

    def set_done(self, status: str, error_msg: str | None = None) -> None:
        """Set final state (success, failed, cancelled)."""
        self._is_done = True
        self.btn_cancel.setVisible(False)

        if status == "success":
            self.progress_bar.setValue(100)
            self.progress_bar.setStyleSheet(
                f"QProgressBar {{ background-color: {BG_ROW}; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {ACCENT_GREEN}; border-radius: 3px; }}"
            )
            self.lbl_status.setText("Ready ✓")
            self.lbl_status.setStyleSheet(
                f"color: {ACCENT_GREEN}; font-weight: 600; font-size: 11px;"
            )

        elif status == "cancelled":
            self.lbl_status.setText("Cancelled")
            self.lbl_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

        else:
            self.progress_bar.setStyleSheet(
                f"QProgressBar {{ background-color: {BG_ROW}; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {ACCENT_RED}; border-radius: 3px; }}"
            )
            err_text = error_msg or "Failed"
            if len(err_text) > 30:
                err_text = err_text[:27] + "..."
            self.lbl_status.setText(err_text)
            self.lbl_status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 11px;")


class FloatingProgressWindow(QWidget):
    """Frameless floating card anchored to desktop bottom-right."""

    cancel_job_signal = Signal(str)
    cancel_batch_signal = Signal(str)

    def __init__(
        self,
        batch_id: str = "",
        *,
        on_cancel_job: Callable[[str], None] | None = None,
        on_cancel_batch: Callable[[str], None] | None = None,
        auto_close_ms: int = 3000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.batch_id = batch_id
        self._auto_close_ms = auto_close_ms
        self._rows: dict[str, JobRowWidget] = {}

        if on_cancel_job is not None:
            self.cancel_job_signal.connect(on_cancel_job)
        if on_cancel_batch is not None:
            self.cancel_batch_signal.connect(on_cancel_batch)

        self._init_window()
        self._init_ui()

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(340)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # Card container with dark styling and rounded borders
        self.card = QFrame()
        self.card.setObjectName("cardFrame")
        self.card.setStyleSheet(
            f"#cardFrame {{ "
            f"background-color: {BG_CARD}; "
            f"border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 12px; "
            f"}}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # Header: App Logo, Title, Item Count, and Cancel All Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
        if logo_path.is_file():
            lbl_icon = QLabel()
            pix = QPixmap(str(logo_path)).scaled(
                20,
                20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_icon.setPixmap(pix)
            lbl_icon.setFixedSize(20, 20)
            header_layout.addWidget(lbl_icon)

        self.lbl_header = QLabel("Cuttle Converting")
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.lbl_header.setFont(font)
        self.lbl_header.setStyleSheet(f"color: {TEXT_PRIMARY};")

        self.btn_cancel_all = QPushButton("Cancel All")
        self.btn_cancel_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_all.setStyleSheet(
            f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ color: {ACCENT_RED}; border-color: {ACCENT_RED}; }}"
        )
        self.btn_cancel_all.clicked.connect(self._on_cancel_all_clicked)

        header_layout.addWidget(self.lbl_header, 1)
        header_layout.addWidget(self.btn_cancel_all)
        card_layout.addLayout(header_layout)

        # Scrollable container for job rows
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setMaximumHeight(260)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch()

        self.scroll_area.setWidget(self.rows_container)
        card_layout.addWidget(self.scroll_area)

        outer_layout.addWidget(self.card)

    def position_bottom_right(self) -> None:
        """Position window at bottom-right corner of primary screen above taskbar."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()
        self.adjustSize()
        w = self.width()
        h = self.height()
        margin = 16

        x = avail.right() - w - margin
        y = avail.bottom() - h - margin
        self.move(QPoint(max(0, x), max(0, y)))

    def add_job(self, job_id: str, src_path: str, dst_fmt: str) -> JobRowWidget:
        """Add a new conversion row to the floating card."""
        if job_id in self._rows:
            return self._rows[job_id]

        row = JobRowWidget(job_id, src_path, dst_fmt, self.rows_container)
        row.cancel_requested.connect(self.cancel_job_signal.emit)

        # Insert before stretch
        idx = max(0, self.rows_layout.count() - 1)
        self.rows_layout.insertWidget(idx, row)
        self._rows[job_id] = row

        count = len(self._rows)
        self.lbl_header.setText(f"Cuttle Converting ({count})")
        self.position_bottom_right()
        return row

    def handle_event(self, event: QueueEvent) -> None:
        """Process real-time QueueEvent from JobQueue."""
        if not self.batch_id and event.batch_id:
            self.batch_id = event.batch_id

        # 1. Job Queued
        if event.event_type == EventType.JOB_QUEUED and event.job_id:
            self.add_job(event.job_id, event.src_path, event.dst_fmt)

        # 2. Job Started
        elif event.event_type == EventType.JOB_STARTED and event.job_id:
            if event.job_id not in self._rows:
                self.add_job(event.job_id, event.src_path, event.dst_fmt)
            self._rows[event.job_id].set_started()

        # 3. Progress
        elif event.event_type == EventType.JOB_PROGRESS and event.job_id:
            if event.job_id in self._rows:
                self._rows[event.job_id].set_progress(event.percent, event.message)

        # 4. Job Done
        elif event.event_type == EventType.JOB_DONE and event.job_id:
            if event.job_id in self._rows:
                self._rows[event.job_id].set_done(event.status or "success", event.error_msg)

        # 5. Batch Done
        elif event.event_type == EventType.BATCH_DONE:
            self.btn_cancel_all.setVisible(False)
            success_count = event.succeeded
            total_count = event.total
            self.lbl_header.setText(f"Completed ({success_count}/{total_count})")
            # Auto-close timer
            if self._auto_close_ms > 0:
                QTimer.singleShot(self._auto_close_ms, self.close)

    def _on_cancel_all_clicked(self) -> None:
        if self.batch_id:
            self.cancel_batch_signal.emit(self.batch_id)
        self.btn_cancel_all.setEnabled(False)
        self.btn_cancel_all.setText("Cancelling...")
