"""Missing Tool guidance dialog implemented via PySide6.

Per task card P3-07:
- Shown when a user requests an Office conversion but LibreOffice is not installed.
- Explains requirement and provides a direct link to the official download page.
- Includes a 'Re-check' button that tests for installation and refreshes context menus.
"""

from __future__ import annotations

import webbrowser

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from cuttle.platform.windows.office_detect import detect_office

# Dark UI Design Tokens matching progress_window.py
BG_CARD = "#18181b"
BG_ROW = "#27272a"
BORDER_COLOR = "#3f3f46"
TEXT_PRIMARY = "#f4f4f5"
TEXT_MUTED = "#a1a1aa"
ACCENT_CYAN = "#38bdf8"
ACCENT_GREEN = "#22c55e"
ACCENT_RED = "#ef4444"

LIBREOFFICE_DOWNLOAD_URL = "https://www.libreoffice.org/download/download-libreoffice/"


class MissingToolDialog(QDialog):
    """Clean dark-mode dialog guiding the user to install a missing required tool."""

    def __init__(self, tool_name: str = "libreoffice", parent: QDialog | None = None) -> None:
        super().__init__(parent)
        self.tool_name = tool_name
        self.setWindowTitle("Cuttle — External Tool Required")
        self.setFixedSize(480, 260)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
            }}
            QPushButton {{
                background-color: {BG_ROW};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {BORDER_COLOR};
            }}
            QPushButton#primaryBtn {{
                background-color: {ACCENT_CYAN};
                color: #0f172a;
                border: none;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: #7dd3fc;
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title and body text configured per tool
        if self.tool_name in ("dwg", "dwg_addon"):
            title_text = "DWG Add-On Required for CAD Conversion"
            body_text = (
                "Converting AutoCAD DWG drawings to PDF or DXF requires an add-on "
                "(LibreDWG or ODA File Converter).\n\n"
                "Install LibreDWG or ODA File Converter to convert drawings offline "
                "with zero cloud uploads."
            )
            download_btn_text = "View DWG Add-On Guide"
        else:
            title_text = "LibreOffice Required for PDF Conversion"
            body_text = (
                "Converting Microsoft Office (DOCX, PPTX, XLSX) and OpenDocument files "
                "to PDF requires LibreOffice.\n\n"
                "LibreOffice is free and open-source. Once installed, Cuttle converts "
                "all your documents 100% offline without uploading them to any cloud server."
            )
            download_btn_text = "Download LibreOffice"

        title_label = QLabel(title_text)
        title_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        self.body_label = QLabel(body_text)
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(f"color: {TEXT_MUTED}; line-height: 1.4;")
        layout.addWidget(self.body_label)

        # Status feedback label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_download = QPushButton(download_btn_text)
        self.btn_download.setObjectName("primaryBtn")
        self.btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self.btn_download)

        self.btn_recheck = QPushButton("Re-check")
        self.btn_recheck.clicked.connect(self._on_recheck)
        btn_layout.addWidget(self.btn_recheck)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _on_download(self) -> None:
        """Open download portal or documentation guide in default web browser."""
        if self.tool_name in ("dwg", "dwg_addon"):
            webbrowser.open("https://github.com/Ameya79/cuttle/blob/main/docs/dwg-addon.md")
        else:
            webbrowser.open(LIBREOFFICE_DOWNLOAD_URL)

    def _on_recheck(self) -> None:
        """Inspect system again for required tool."""
        if self.tool_name in ("dwg", "dwg_addon"):
            from cuttle.adapters.dwg import get_available_dwg_tool

            detected = get_available_dwg_tool() is not None
            tool_display = "DWG Add-on"
        else:
            detected = detect_office().installed
            tool_display = "LibreOffice"

        if detected:
            self.status_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
            self.status_label.setText(
                f"{tool_display} detected successfully! Updating right-click menus..."
            )
            # Refresh context menus
            try:
                from cuttle.shell.registry_installer import install_context_menus

                install_context_menus()
            except Exception:
                pass
            self.btn_recheck.setEnabled(False)
            self.btn_download.setText("Ready")
            self.btn_download.setEnabled(False)
        else:
            self.status_label.setStyleSheet(f"color: {ACCENT_RED};")
            self.status_label.setText(
                f"{tool_display} not detected yet. Please complete the installation and retry."
            )


def show_missing_tool_dialog(tool_name: str = "libreoffice", blocking: bool = True) -> int:
    """Convenience launcher for the missing tool guidance dialog."""
    from cuttle.ui.progress_window import get_or_create_app

    get_or_create_app()
    dialog = MissingToolDialog(tool_name=tool_name)
    if blocking:
        return dialog.exec()
    dialog.show()
    return 0
