#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODELS_DIR="data/models"
VENV_DIR=".venv"

# ── Colors ──────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[✓]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[!]${NC} %s\n" "$1"; }
fail()  { printf "${RED}[✗]${NC} %s\n" "$1"; exit 1; }

# ── 1. Python ───────────────────────────────────────────
echo ""
echo "=== Diana Setup ==="
echo ""

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.10+ is required but not found. Install it from https://python.org"
fi
info "Found $PYTHON ($ver)"

# ── 2. ffmpeg ───────────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
    info "ffmpeg found"
else
    warn "ffmpeg not found — required for MP3 encoding"
    echo "    Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
    echo "    Continuing setup without it..."
    echo ""
fi

# ── 3. Virtual environment ──────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
    info "Virtual environment created"
else
    info "Virtual environment already exists"
fi

# Activate
source "$VENV_DIR/bin/activate"

# ── 4. Dependencies ─────────────────────────────────────
echo "Installing dependencies..."
pip install -q -r requirements.txt
info "Dependencies installed"

# ── 5. Model downloads ─────────────────────────────────
mkdir -p "$MODELS_DIR"

download() {
    local url="$1" dest="$2" label="$3"
    if [ -f "$dest" ]; then
        info "$label already downloaded"
    else
        echo "Downloading $label..."
        curl -L --progress-bar -o "$dest" "$url"
        info "$label downloaded"
    fi
}

echo ""
echo "--- Kokoro models (~340 MB) ---"
download \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx" \
    "$MODELS_DIR/kokoro-v1.0.onnx" \
    "kokoro-v1.0.onnx"

download \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" \
    "$MODELS_DIR/voices-v1.0.bin" \
    "voices-v1.0.bin"

echo ""
echo "--- Piper models (~60 MB) ---"
download \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
    "$MODELS_DIR/en_US-lessac-medium.onnx" \
    "en_US-lessac-medium.onnx"

download \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
    "$MODELS_DIR/en_US-lessac-medium.onnx.json" \
    "en_US-lessac-medium.onnx.json"

# ── 6. Config ───────────────────────────────────────────
if [ ! -f "config.yaml" ]; then
    cp config.example.yaml config.yaml
    info "config.yaml created from example"
else
    info "config.yaml already exists"
fi

# ── 7. Desktop launcher ────────────────────────────────
LAUNCHER="Diana.command"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
python run.py
LAUNCHER_EOF
chmod +x "$LAUNCHER"
info "Created $LAUNCHER (double-click to launch)"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start Diana:"
echo "  • Double-click Diana.command, or"
echo "  • Run: source .venv/bin/activate && python run.py"
echo ""
