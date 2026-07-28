"""Settings dialog for save behavior and global capture hotkeys."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QKeySequenceEdit,
    QVBoxLayout,
    QWidget,
)

from .config import Config
from .hotkey import hotkey_to_display, hotkey_to_pynput


class SettingsDialog(QDialog):
    """Edit persistent Snappr settings."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Snappr — Settings")
        self.setMinimumWidth(560)

        save_group = QGroupBox("Saving")
        save_layout = QVBoxLayout(save_group)

        directory_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit(str(config.get("output_dir", "")))
        self.output_dir_edit.setPlaceholderText("Default screenshot folder")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_directory)
        directory_row.addWidget(self.output_dir_edit, 1)
        directory_row.addWidget(browse_button)

        directory_label = QLabel("Default folder")
        directory_label.setBuddy(self.output_dir_edit)
        directory_form = QFormLayout()
        directory_form.addRow(directory_label, directory_row)
        save_layout.addLayout(directory_form)

        self.save_directly_check = QCheckBox(
            "Save directly to this folder when clicking “Save PNG”"
        )
        self.save_directly_check.setChecked(bool(config.get("save_directly", False)))
        save_layout.addWidget(self.save_directly_check)

        save_hint = QLabel(
            "When disabled, Snappr keeps opening the file chooser with this "
            "folder selected."
        )
        save_hint.setWordWrap(True)
        save_layout.addWidget(save_hint)

        hotkey_group = QGroupBox("Global hotkeys")
        hotkey_layout = QFormLayout(hotkey_group)
        self.hotkey_edits: dict[str, QKeySequenceEdit] = {}
        hotkey_fields = (
            ("hotkey_region", "Region capture"),
            ("hotkey_fullscreen", "Fullscreen capture"),
            ("hotkey_scroll", "Scrolling capture"),
        )
        for key, label in hotkey_fields:
            edit = QKeySequenceEdit(
                QKeySequence(hotkey_to_display(str(config.get(key, ""))))
            )
            edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True)
            hotkey_layout.addRow(label, edit)
            self.hotkey_edits[key] = edit

        hotkey_hint = QLabel(
            "Click a field and press the desired key combination. Hotkeys are "
            "applied as soon as the settings are saved."
        )
        hotkey_hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(save_group)
        layout.addWidget(hotkey_group)
        layout.addWidget(hotkey_hint)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def _browse_directory(self) -> None:
        current = self.output_dir_edit.text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose default screenshot folder",
            current or str(Path.home()),
        )
        if selected:
            self.output_dir_edit.setText(selected)

    def _save(self) -> None:
        directory_text = self.output_dir_edit.text().strip()
        if not directory_text:
            QMessageBox.warning(self, "Invalid folder", "Choose a default folder.")
            return

        directory = Path(directory_text).expanduser()
        if not directory.is_absolute():
            directory = Path.home() / directory
        directory = directory.resolve()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Invalid folder",
                f"Snappr could not create or access this folder:\n{exc}",
            )
            return

        hotkeys: dict[str, str] = {}
        try:
            for key, edit in self.hotkey_edits.items():
                display = edit.keySequence().toString(
                    QKeySequence.SequenceFormat.PortableText
                )
                hotkeys[key] = hotkey_to_pynput(display)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid hotkey", str(exc))
            return

        if len(set(hotkeys.values())) != len(hotkeys):
            QMessageBox.warning(
                self,
                "Duplicate hotkeys",
                "Each capture action must use a different hotkey.",
            )
            return

        self._config.set("output_dir", str(directory))
        self._config.set("save_directly", self.save_directly_check.isChecked())
        for key, value in hotkeys.items():
            self._config.set(key, value)
        try:
            self._config.save()
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could not save settings",
                f"Snappr could not write its configuration:\n{exc}",
            )
            return
        self.accept()
