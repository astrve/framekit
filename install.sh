#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  Framekit v2.0.0 — Linux/macOS Installer"
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
echo "[..] Installing Framekit..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR" -q

if [ $? -ne 0 ]; then
    echo "[ERROR] Installation failed."
    exit 1
fi
echo "[OK] Framekit installed."

# Verify
if "$VENV_DIR/bin/framekit" --version &>/dev/null; then
    echo "[OK] $("$VENV_DIR/bin/framekit" --version 2>&1)"
else
    echo "[WARN] framekit not found. Try: $VENV_DIR/bin/framekit --version"
fi

echo ""
echo "  Installation complete!"
echo ""
echo "  Usage:"
echo "    $VENV_DIR/bin/framekit --help"
echo "    $VENV_DIR/bin/fk --help"
echo ""
echo "  To add to PATH:"
echo "    echo 'export PATH=\"$VENV_DIR/bin:\$PATH\"' >> ~/.bashrc"
echo "    source ~/.bashrc"
echo ""
echo "  Then use: framekit --help / fk --help"
echo ""
