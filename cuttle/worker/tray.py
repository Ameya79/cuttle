"""System tray icon and menu for Cuttle worker daemon.

Provides background presence in the Windows taskbar notification area:
- Real-time conversion status display ("Cuttle: Idle", "Cuttle: 2 converting")
- "Open Output Folder" action
- "Settings..." action
- "Quit Cuttle" action
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


def create_fallback_icon() -> QIcon:
    """Create a minimal programmatic octopus-cyan icon if no .ico file is present."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#38bdf8"))  # Cyan accent
        painter.setPen(QColor("#0284c7"))
        painter.drawEllipse(4, 4, 24, 24)
    finally:
        painter.end()
    return QIcon(pixmap)


class CuttleTrayIcon(QSystemTrayIcon):
    """System tray icon with context menu and conversion status updates."""

    quit_requested = Signal()
    settings_requested = Signal()
    open_output_requested = Signal()

    def __init__(self, icon_path: Path | str | None = None) -> None:
        super().__init__()

        # Setup icon
        resolved_icon = None
        if icon_path and Path(icon_path).is_file():
            resolved_icon = Path(icon_path)
        else:
            default_assets = Path(__file__).resolve().parent.parent.parent / "assets"
            for candidate in ("cuttle.ico", "logo.png"):
                c_path = default_assets / candidate
                if c_path.is_file():
                    resolved_icon = c_path
                    break

        if resolved_icon:
            self.setIcon(QIcon(str(resolved_icon)))
        else:
            self.setIcon(create_fallback_icon())

        self.setToolTip("Cuttle: Idle")

        # Setup context menu
        self.menu = QMenu()

        self.action_header = self.menu.addAction("Cuttle: Idle")
        self.action_header.setEnabled(False)

        self.menu.addSeparator()

        self.action_open_output = self.menu.addAction("Open Output Folder")
        self.action_open_output.triggered.connect(self.open_output_requested.emit)

        self.action_settings = self.menu.addAction("Settings...")
        self.action_settings.triggered.connect(self.settings_requested.emit)

        self.menu.addSeparator()

        self.action_quit = self.menu.addAction("Quit Cuttle")
        self.action_quit.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(self.menu)

    def update_status(self, active_jobs: int, queued_jobs: int = 0) -> None:
        """Update tray menu label and tooltip with live conversion progress."""
        if active_jobs == 0 and queued_jobs == 0:
            text = "Cuttle: Idle"
        else:
            parts: list[str] = []
            if active_jobs > 0:
                parts.append(f"{active_jobs} converting")
            if queued_jobs > 0:
                parts.append(f"{queued_jobs} queued")
            text = f"Cuttle: {', '.join(parts)}"

        self.action_header.setText(text)
        self.setToolTip(text)

    def show_notification(self, title: str, message: str) -> None:
        """Display a system tray bubble notification."""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
