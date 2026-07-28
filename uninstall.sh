#!/usr/bin/env bash
# Uninstall Snappr launchers/icon for the current user.
set -euo pipefail

APP_ID="snappr"
APP_NAME="Snappr"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_ROOT="$DATA_HOME/icons/hicolor"
ICON_DIR="$ICON_ROOT/scalable/apps"
AUTOSTART_DIR="$CONFIG_HOME/autostart"
APP_CONFIG_DIR="$CONFIG_HOME/$APP_ID"

DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
AUTOSTART_FILE="$AUTOSTART_DIR/$APP_ID.desktop"
ICON_TARGET="$ICON_DIR/$APP_ID.svg"

REMOVE_VENV=false
REMOVE_CONFIG=false

usage() {
    cat <<EOF
Usage: ./uninstall.sh [options]

Options:
  --remove-venv     Also remove the project virtualenv: .venv/
  --remove-config   Also remove user config: ~/.config/$APP_ID/
  --all             Remove launcher, icon, autostart, .venv/ and user config.
  -h, --help        Show this help.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --remove-venv)
            REMOVE_VENV=true
            ;;
        --remove-config)
            REMOVE_CONFIG=true
            ;;
        --all)
            REMOVE_VENV=true
            REMOVE_CONFIG=true
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

rm -f "$DESKTOP_FILE" "$AUTOSTART_FILE" "$ICON_TARGET"

for size in 16 22 24 32 48 64 128 256; do
    rm -f "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
done

if [ "$REMOVE_VENV" = true ]; then
    rm -rf "$VENV"
fi

if [ "$REMOVE_CONFIG" = true ]; then
    rm -rf "$APP_CONFIG_DIR"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$ICON_ROOT" >/dev/null 2>&1 || true
fi

echo "$APP_NAME uninstalled."
echo "Removed launcher/icon/autostart entries for the current user."
if [ "$REMOVE_VENV" = true ]; then
    echo "Removed: $VENV"
fi
if [ "$REMOVE_CONFIG" = true ]; then
    echo "Removed: $APP_CONFIG_DIR"
fi
