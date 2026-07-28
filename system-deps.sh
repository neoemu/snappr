#!/usr/bin/env bash
# Install the system-level packages Shottr-Linux needs to run its GUI (Qt6 /
# PySide6 xcb platform plugin, OpenGL, screen capture and global hotkeys).
# Detects the distro's package manager (apt / dnf / pacman / zypper) and
# installs the matching runtime libraries. Python deps are handled separately
# by run.sh / install.sh inside the virtualenv.
set -euo pipefail

ASSUME_YES=false
DRY_RUN=false

usage() {
    cat <<EOF
Usage: ./system-deps.sh [options]

Installs the system libraries required to run Shottr-Linux (Qt6/PySide6,
OpenGL, xcb). Uses sudo when not run as root.

Options:
  -y, --yes         Pass the "assume yes" flag to the package manager.
  -n, --dry-run     Only print the command that would be run.
  -h, --help        Show this help.
EOF
}

for arg in "$@"; do
    case "$arg" in
        -y|--yes)     ASSUME_YES=true ;;
        -n|--dry-run) DRY_RUN=true ;;
        -h|--help)    usage; exit 0 ;;
        *)
            echo "Unknown option: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# Run privileged commands with sudo unless we are already root.
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "This script needs root privileges (or sudo) to install packages." >&2
        exit 1
    fi
fi

run() {
    echo "+ $*"
    if [ "$DRY_RUN" = false ]; then
        "$@"
    fi
}

# Package lists per manager. Each covers: python3 + venv, OpenGL/EGL,
# xkbcommon, dbus, and the xcb-util plugins that Qt6's xcb platform needs.
if command -v apt-get >/dev/null 2>&1; then
    PKGS=(
        python3 python3-venv python3-pip
        libgl1 libegl1 libglib2.0-0 libdbus-1-3
        libxkbcommon0 libxkbcommon-x11-0
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
        libxcb-xkb1 libxcb-util1
    )
    YES_FLAG=(); [ "$ASSUME_YES" = true ] && YES_FLAG=(-y)
    run $SUDO apt-get update
    run $SUDO apt-get install "${YES_FLAG[@]}" "${PKGS[@]}"

elif command -v dnf >/dev/null 2>&1; then
    PKGS=(
        python3 python3-pip
        mesa-libGL mesa-libEGL glib2 dbus-libs
        libxkbcommon libxkbcommon-x11
        xcb-util-cursor xcb-util-image xcb-util-keysyms
        xcb-util-renderutil xcb-util-wm libxcb
    )
    YES_FLAG=(); [ "$ASSUME_YES" = true ] && YES_FLAG=(-y)
    run $SUDO dnf install "${YES_FLAG[@]}" "${PKGS[@]}"

elif command -v pacman >/dev/null 2>&1; then
    PKGS=(
        python
        libglvnd glib2 dbus
        libxkbcommon libxkbcommon-x11
        xcb-util-cursor xcb-util-image xcb-util-keysyms
        xcb-util-renderutil xcb-util-wm libxcb
    )
    if [ "$ASSUME_YES" = true ]; then
        run $SUDO pacman -S --needed --noconfirm "${PKGS[@]}"
    else
        run $SUDO pacman -S --needed "${PKGS[@]}"
    fi

elif command -v zypper >/dev/null 2>&1; then
    PKGS=(
        python3 python3-pip
        Mesa-libGL1 Mesa-libEGL1 glib2 libdbus-1-3
        libxkbcommon0 libxkbcommon-x11-0
        xcb-util-cursor xcb-util-image0 xcb-util-keysyms1
        xcb-util-renderutil0 xcb-util-wm0 libxcb1
    )
    YES_FLAG=(); [ "$ASSUME_YES" = true ] && YES_FLAG=(--non-interactive)
    run $SUDO zypper "${YES_FLAG[@]}" install "${PKGS[@]}"

else
    cat >&2 <<EOF
Could not detect a supported package manager (apt / dnf / pacman / zypper).

Install these manually, then run ./install.sh:
  - python3 + venv
  - OpenGL/EGL runtime (libGL, libEGL)
  - libxkbcommon (+ x11 variant)
  - the xcb-util plugins for Qt6: cursor, image, keysyms, renderutil, wm
EOF
    exit 1
fi

echo
echo "System dependencies installed. Next:"
echo "  ./install.sh      # set up the app (venv + launcher)"
echo "  ./run.sh          # or just run it directly"
