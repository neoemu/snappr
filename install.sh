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
  --autostart       Start Shottr Linux automatically after login.
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
