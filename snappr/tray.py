"""System tray icon and action menu."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_icon() -> QIcon:
    """Generate a simple 'S' icon at runtime (no asset file needed)."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(0, 174, 255))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Sans", 34, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return QIcon(pix)


def build_tray(controller) -> QSystemTrayIcon:
    """Create the tray icon wired to the controller's action slots."""
    tray = QSystemTrayIcon(make_icon())
    tray.setToolTip("Shottr-Linux")

    menu = QMenu()

    act_region = QAction("Capturar região", menu)
    act_full = QAction("Capturar tela cheia", menu)
    act_scroll = QAction("Captura em scroll", menu)
    act_quit = QAction("Sair", menu)

    act_region.triggered.connect(controller.start_region_capture)
    act_full.triggered.connect(controller.start_fullscreen_capture)
    act_scroll.triggered.connect(controller.start_scroll_capture)
    act_quit.triggered.connect(controller.quit)

    menu.addAction(act_region)
    menu.addAction(act_full)
    menu.addAction(act_scroll)
    menu.addSeparator()
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    return tray
