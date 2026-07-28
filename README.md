# Snappr

Screenshot tool for Linux (X11) inspired by [Shottr](https://shottr.cc/),
focused on **scrolling capture**: it stitches multiple frames of a fixed
region while the content scrolls, producing a single tall image.

## Features (MVP)
- **Region** capture (rectangular selection).
- **Fullscreen** capture (all monitors).
- **Scrolling capture**: select a region and the app scrolls automatically,
  stitching the frames into one image.
- **Annotation tools**: rectangle, arrow and text, with configurable color and
  stroke width.
- **Save** to PNG and **copy** to the clipboard.
- **System tray** icon + configurable **global hotkeys**.

## Requirements
- Linux running an **X11** session (tested on Linux Mint / Cinnamon).
- Python 3.10+.
- `xclip` (optional, clipboard copy fallback).

## System dependencies (fresh machine)
On a clean machine, first install the Qt6/PySide6 runtime libraries
(OpenGL/EGL, `libxkbcommon`, `xcb-util` plugins) and `python3`+venv:

```bash
./system-deps.sh          # detects apt/dnf/pacman/zypper and installs; uses sudo
./system-deps.sh -y       # install without confirmation
./system-deps.sh -n       # dry-run: only show what would be installed
```

If the distro is not detected, the script prints the package list to install
manually. **Python** dependencies are handled separately by `run.sh` /
`install.sh` inside the virtualenv.

## Running
```bash
./run.sh
```
On first run the script creates a virtualenv in `.venv/` and installs the
dependencies from `requirements.txt`. The app lives in the system tray.

Manual alternative:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Install to the menu
To install the launcher and icon in the current user's menu:

```bash
./install.sh
```

To also start automatically after login:

```bash
./install.sh --autostart
```

To remove the launcher, autostart and icon:

```bash
./uninstall.sh
```

To also remove `.venv/` and `~/.config/snappr/`:

```bash
./uninstall.sh --all
```

## Default hotkeys
- `Ctrl+Shift+A` — capture region
- `Ctrl+Shift+S` — scrolling capture
- `Ctrl+Shift+F` — capture fullscreen

Configurable in `~/.config/snappr/config.json`.

## Using automatic scrolling capture
1. Trigger scrolling capture (hotkey or tray menu).
2. Select the **region** containing the scrollable content (keep the selection
   inside the area that will scroll, without including fixed scrollbars).
3. The app moves the mouse to the center of the region, scrolls automatically
   and captures each step.
4. The capture finishes by itself when the view stops changing, usually at the
   end of the page.
5. During the capture, press `Enter`, `Space` or `Ctrl+Enter` to finish
   manually; press `Esc` to cancel.

## Tests
```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

## Known limitations
- **X11 only** (Wayland is not supported in this MVP).
- Fixed headers/footers or scrollbars inside the region can confuse the
  stitching. Select only the content area.
- No OCR or pin-on-screen yet (planned for future versions).

## Architecture
- `snappr/capture.py` — capture via `mss`.
- `snappr/stitch.py` — vertical stitching (template matching with OpenCV).
- `snappr/scroll_capture.py` — orchestrates the scroll session.
- `snappr/overlay.py` — region selection overlay.
- `snappr/preview.py` — result window.
- `snappr/tray.py` / `snappr/hotkey.py` — tray and global hotkeys.
- `snappr/app.py` — controller wiring everything together.
