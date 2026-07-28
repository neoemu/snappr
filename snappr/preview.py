"""Preview window shown after a capture, with annotation tools + Save / Copy."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import icons, imageutil
from .annotate import AnnotationView, Tool
from .config import Config


def _color_icon(color: QColor, size: int = 18) -> QIcon:
    """A solid swatch icon used on the color button."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(color)
    painter.setPen(QColor(0, 0, 0, 60))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    painter.end()
    return QIcon(pix)


class PreviewWindow(QMainWindow):
    """Displays a captured image, lets the user annotate, save or copy it."""

    def __init__(self, rgb: np.ndarray, config: Config) -> None:
        super().__init__()
        self._rgb = np.ascontiguousarray(rgb)
        self._config = config
        self.setWindowTitle("Shottr — Preview")

        self._color = QColor(config.get("annot_color", "#FF3B30"))
        self._width = int(config.get("annot_width", 3))

        self.view = AnnotationView(self._rgb, self._color, self._width)

        self._build_toolbar()

        save_btn = QPushButton("Salvar PNG")
        copy_btn = QPushButton("Copiar")
        save_btn.clicked.connect(self._save)
        copy_btn.clicked.connect(self._copy)

        self.status = QLabel("")

        buttons = QHBoxLayout()
        buttons.addWidget(self.status)
        buttons.addStretch(1)
        buttons.addWidget(copy_btn)
        buttons.addWidget(save_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.view, 1)
        layout.addLayout(buttons)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Cap initial window size so very tall captures stay usable.
        h, w = self._rgb.shape[:2]
        self.resize(min(w + 60, 1000), min(h + 140, 900))

        if config.get("auto_copy"):
            self._copy()

    # --- toolbar ---------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar("Ferramentas")
        bar.setIconSize(QSize(18, 18))
        self.addToolBar(bar)

        group = QActionGroup(self)
        group.setExclusive(True)

        def add_tool(icon: QIcon, label: str, tool: Tool, checked: bool = False):
            act = bar.addAction(icon, label)
            act.setToolTip(label)
            act.setCheckable(True)
            act.setChecked(checked)
            act.triggered.connect(lambda: self.view.set_tool(tool))
            group.addAction(act)
            return act

        add_tool(icons.select_icon(), "Selecionar", Tool.SELECT, checked=True)
        add_tool(icons.rect_icon(), "Retângulo", Tool.RECT)
        add_tool(icons.arrow_icon(), "Seta", Tool.ARROW)
        add_tool(icons.text_icon(), "Texto", Tool.TEXT)

        bar.addSeparator()

        self._color_action = bar.addAction(_color_icon(self._color), "Cor")
        self._color_action.setToolTip("Cor da anotação")
        self._color_action.triggered.connect(self._pick_color)

        width_label = QLabel()
        width_label.setPixmap(icons.width_icon().pixmap(QSize(18, 18)))
        width_label.setToolTip("Espessura do traço")
        width_label.setContentsMargins(6, 0, 4, 0)
        bar.addWidget(width_label)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 40)
        self._width_spin.setValue(self._width)
        self._width_spin.setToolTip("Espessura do traço")
        self._width_spin.valueChanged.connect(self._on_width_changed)
        bar.addWidget(self._width_spin)

        bar.addSeparator()
        del_action = bar.addAction(icons.trash_icon(), "Apagar")
        del_action.setToolTip("Apagar seleção (Delete)")
        del_action.triggered.connect(self.view.delete_selected)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Cor da anotação")
        if not color.isValid():
            return
        self._color = color
        self.view.set_color(color)
        self._color_action.setIcon(_color_icon(color))

    def _on_width_changed(self, value: int) -> None:
        self._width = int(value)
        self.view.set_width(self._width)

    # --- actions ---------------------------------------------------------
    def _save(self) -> None:
        default = str(self._config.output_dir / imageutil.default_filename())
        path, _ = QFileDialog.getSaveFileName(self, "Salvar captura", default, "PNG (*.png)")
        if not path:
            return
        p = Path(path)
        imageutil.save_png(self.view.render_to_rgb(), p.parent, p.name)
        self.status.setText(f"Salvo em {p}")

    def _copy(self) -> None:
        ok = imageutil.copy_to_clipboard(self.view.render_to_rgb())
        self.status.setText("Copiado para a área de transferência" if ok else "Falha ao copiar")
