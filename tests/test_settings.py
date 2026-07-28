"""Tests for persistent settings, hotkey conversion and direct saving."""
import json
import os

import numpy as np
import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - Qt not installed
        pytest.skip("PySide6 not available")
    return QApplication.instance() or QApplication([])


def test_hotkey_display_and_pynput_formats_round_trip():
    from snappr.hotkey import hotkey_to_display, hotkey_to_pynput

    assert hotkey_to_display("<ctrl>+<shift>+a") == "Ctrl+Shift+A"
    assert hotkey_to_pynput("Ctrl+Shift+A") == "<ctrl>+<shift>+a"
    assert hotkey_to_pynput("Alt+F8") == "<alt>+<f8>"
    assert hotkey_to_pynput("Ctrl+Print") == "<ctrl>+<print_screen>"


def test_settings_dialog_persists_save_and_hotkey_options(
    qapp, tmp_path, monkeypatch
):
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QDialog

    from snappr import config as config_module
    from snappr.config import Config
    from snappr.settings import SettingsDialog

    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.json")

    cfg = Config({"auto_copy": False})
    dialog = SettingsDialog(cfg)
    output_dir = tmp_path / "captures"
    dialog.output_dir_edit.setText(str(output_dir))
    dialog.save_directly_check.setChecked(True)
    shortcuts = {
        "hotkey_region": "Ctrl+Alt+R",
        "hotkey_fullscreen": "Ctrl+Alt+F",
        "hotkey_scroll": "Ctrl+Alt+S",
    }
    for key, shortcut in shortcuts.items():
        dialog.hotkey_edits[key].setKeySequence(QKeySequence(shortcut))

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert output_dir.is_dir()
    assert cfg.get("save_directly") is True
    persisted = json.loads(config_module.CONFIG_PATH.read_text(encoding="utf-8"))
    assert persisted["output_dir"] == str(output_dir)
    assert persisted["hotkey_region"] == "<ctrl>+<alt>+r"
    assert persisted["hotkey_fullscreen"] == "<ctrl>+<alt>+f"
    assert persisted["hotkey_scroll"] == "<ctrl>+<alt>+s"


def test_direct_save_skips_file_dialog(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from snappr.config import Config
    from snappr.preview import PreviewWindow

    cfg = Config(
        {
            "output_dir": str(tmp_path),
            "save_directly": True,
            "auto_copy": False,
        }
    )
    window = PreviewWindow(np.zeros((40, 60, 3), dtype=np.uint8), cfg)

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError("The file chooser must not open in direct-save mode")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", unexpected_dialog)
    window._save()

    saved = list(tmp_path.glob("Snappr_*.png"))
    assert len(saved) == 1
    assert window.status.text() == f"Saved to {saved[0]}"
    window.close()


def test_hotkey_manager_restart_replaces_listener(monkeypatch):
    from snappr import hotkey as hotkey_module

    class FakeListener:
        instances = []

        def __init__(self, bindings):
            self.bindings = bindings
            self.started = False
            self.stopped = False
            self.instances.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    class FakeKeyboard:
        GlobalHotKeys = FakeListener

    monkeypatch.setattr(hotkey_module, "keyboard", FakeKeyboard)
    manager = hotkey_module.HotkeyManager({"first": lambda: None})
    assert manager.start()
    first = FakeListener.instances[-1]

    assert manager.restart({"second": lambda: None})
    second = FakeListener.instances[-1]
    assert first.stopped
    assert second.started
    assert set(second.bindings) == {"second"}
