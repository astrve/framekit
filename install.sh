#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  Swirrl v2.0.0 — Linux/macOS Installer"
echo "  ========================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.12+."
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMAJOR=$(echo "$PYVER" | cut -d. -f1)
PYMINOR=$(echo "$PYVER" | cut -d. -f2)

if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 12 ]; }; then
    echo "[ERROR] Python 3.12+ required, found $PYVER"
    exit 1
fi
echo "[OK] Python $PYVER"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Create venv if missing
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created."
else
    echo "[OK] Virtual environment exists."
fi

# Install
echo "[..] Installing Swirrl..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR" -q

if [ $? -ne 0 ]; then
    echo "[ERROR] Installation failed."
    exit 1
fi
echo "[OK] Swirrl installed."

# Verify
if "$VENV_DIR/bin/swirrl" --version &>/dev/null; then
    echo "[OK] $("$VENV_DIR/bin/swirrl" --version 2>&1)"
else
    echo "[WARN] swirrl not found. Try: $VENV_DIR/bin/swirrl --version"
fi

echo ""
echo "Optional dependencies:"
echo "  - MKVToolNix (mkvmerge)"
echo "  - FFmpeg"
echo "  - MediaInfo"
echo "  - rclone"
echo ""
read -r -p "Install optional dependencies now? [Y/n] " INSTALL_DEPS
INSTALL_DEPS=${INSTALL_DEPS:-Y}

if [[ ! "${INSTALL_DEPS}" =~ ^[Nn]$ ]]; then
    PKG_MANAGER=""
    if command -v brew &>/dev/null; then
        PKG_MANAGER="brew"
    elif command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt"
    fi

    if [[ -z "$PKG_MANAGER" ]]; then
        echo "[WARN] No supported package manager detected (brew/apt-get). Install deps manually."
    else
        echo "[..] Using package manager: $PKG_MANAGER"
        read -r -p "Install MKVToolNix? [Y/n] " INSTALL_MKV
        read -r -p "Install FFmpeg? [Y/n] " INSTALL_FFMPEG
        read -r -p "Install MediaInfo? [Y/n] " INSTALL_MEDIAINFO
        read -r -p "Install rclone? [Y/n] " INSTALL_RCLONE
        INSTALL_MKV=${INSTALL_MKV:-Y}
        INSTALL_FFMPEG=${INSTALL_FFMPEG:-Y}
        INSTALL_MEDIAINFO=${INSTALL_MEDIAINFO:-Y}
        INSTALL_RCLONE=${INSTALL_RCLONE:-Y}

        if [[ "$PKG_MANAGER" == "brew" ]]; then
            [[ ! "$INSTALL_MKV" =~ ^[Nn]$ ]] && brew install mkvtoolnix || true
            [[ ! "$INSTALL_FFMPEG" =~ ^[Nn]$ ]] && brew install ffmpeg || true
            [[ ! "$INSTALL_MEDIAINFO" =~ ^[Nn]$ ]] && brew install mediainfo || true
            [[ ! "$INSTALL_RCLONE" =~ ^[Nn]$ ]] && brew install rclone || true
        else
            [[ ! "$INSTALL_MKV" =~ ^[Nn]$ ]] && sudo apt-get install -y mkvtoolnix || true
            [[ ! "$INSTALL_FFMPEG" =~ ^[Nn]$ ]] && sudo apt-get install -y ffmpeg || true
            [[ ! "$INSTALL_MEDIAINFO" =~ ^[Nn]$ ]] && sudo apt-get install -y mediainfo || true
            [[ ! "$INSTALL_RCLONE" =~ ^[Nn]$ ]] && sudo apt-get install -y rclone || true
        fi
    fi
fi

echo ""
echo "Dependency check:"
command -v mkvmerge >/dev/null && echo "[OK] mkvmerge found" || echo "[WARN] mkvmerge not found"
command -v ffmpeg >/dev/null && echo "[OK] ffmpeg found" || echo "[WARN] ffmpeg not found"
command -v mediainfo >/dev/null && echo "[OK] mediainfo found" || echo "[WARN] mediainfo not found"
command -v rclone >/dev/null && echo "[OK] rclone found" || echo "[WARN] rclone not found"

echo ""
echo "  Installation complete!"
echo ""
echo "  Usage:"
echo "    $VENV_DIR/bin/swirrl --help"
echo "    $VENV_DIR/bin/swirrl --help"
echo ""
echo "  To add to PATH:"
echo "    echo 'export PATH=\"$VENV_DIR/bin:\$PATH\"' >> ~/.bashrc"
echo "    source ~/.bashrc"
echo ""
echo "  Then use: swirrl --help / swirrl --help"
echo ""
