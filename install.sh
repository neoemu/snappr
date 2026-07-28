#!/usr/bin/env bash
# Install Snappr for the current user by creating a desktop launcher,
# installing the app icon, and optionally enabling autostart.
set -euo pipefail

APP_ID="snappr"
APP_NAME="Snappr"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$HERE/run.sh"
REQUIREMENTS="$HERE/requirements.txt"
VENV="$HERE/.venv"
ICON_SOURCE="$HERE/assets/$APP_ID.svg"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
AUTOSTART_DIR="$CONFIG_HOME/autostart"

DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
AUTOSTART_FILE="$AUTOSTART_DIR/$APP_ID.desktop"
ICON_TARGET="$ICON_DIR/$APP_ID.svg"

ENABLE_AUTOSTART=false
SKIP_DEPS=false

usage() {
    cat <<EOF
Usage: ./install.sh [options]

Options:
  --autostart       Start Snappr automatically after login.
  --skip-deps       Do not create/update the Python virtualenv.
  -h, --help        Show this help.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --autostart)
            ENABLE_AUTOSTART=true
            ;;
        --skip-deps)
            SKIP_DEPS=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ ! -f "$RUN_SCRIPT" ]; then
    echo "Missing run script: $RUN_SCRIPT" >&2
    exit 1
fi

if [ ! -f "$ICON_SOURCE" ]; then
    echo "Missing icon: $ICON_SOURCE" >&2
    exit 1
fi

chmod +x "$RUN_SCRIPT"

if [ "$SKIP_DEPS" = false ]; then
    if [ ! -d "$VENV" ]; then
        echo "Creating virtualenv in $VENV ..."
        python3 -m venv "$VENV"
    fi
    echo "Installing Python dependencies ..."
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r "$REQUIREMENTS"
fi

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
cp "$ICON_SOURCE" "$ICON_TARGET"

# Render fixed-size PNGs from the SVG so menus reliably pick up the icon.
if [ -x "$VENV/bin/python" ]; then
    "$VENV/bin/python" "$HERE/tools/render_icons.py" "$DATA_HOME/icons/hicolor" || true
fi

# gtk-update-icon-cache requires an index.theme in the user hicolor theme.
if [ ! -f "$DATA_HOME/icons/hicolor/index.theme" ]; then
    cat > "$DATA_HOME/icons/hicolor/index.theme" <<'THEME'
[Icon Theme]
Name=Hicolor
Comment=User fallback icon theme
Hidden=true
Directories=16x16/apps,22x22/apps,24x24/apps,32x32/apps,48x48/apps,64x64/apps,128x128/apps,256x256/apps,scalable/apps

[16x16/apps]
Size=16
Type=Fixed

[22x22/apps]
Size=22
Type=Fixed

[24x24/apps]
Size=24
Type=Fixed

[32x32/apps]
Size=32
Type=Fixed

[48x48/apps]
Size=48
Type=Fixed

[64x64/apps]
Size=64
Type=Fixed

[128x128/apps]
Size=128
Type=Fixed

[256x256/apps]
Size=256
Type=Fixed

[scalable/apps]
Size=128
Type=Scalable
MinSize=1
MaxSize=512
THEME
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Screenshot tool with scrolling capture
Exec=$RUN_SCRIPT
Path=$HERE
Icon=$APP_ID
Terminal=false
Categories=Graphics;Utility;
StartupNotify=false
EOF

chmod 644 "$DESKTOP_FILE" "$ICON_TARGET"

if [ "$ENABLE_AUTOSTART" = true ]; then
    mkdir -p "$AUTOSTART_DIR"
    cp "$DESKTOP_FILE" "$AUTOSTART_FILE"
    chmod 644 "$AUTOSTART_FILE"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "$APP_NAME installed."
echo "Launcher: $DESKTOP_FILE"
echo "Icon: $ICON_TARGET"
if [ "$ENABLE_AUTOSTART" = true ]; then
    echo "Autostart: $AUTOSTART_FILE"
fi
echo "Open it from the menu by searching for: $APP_NAME"
