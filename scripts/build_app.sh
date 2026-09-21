#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/AutoJurnal.app"

echo "=== Building AutoJurnal.app for macOS (Intel & Apple Silicon) ==="

# 1. Generate AppIcon.icns
echo "1. Generating application icons..."
"$ROOT_DIR/venv/bin/python" "$SCRIPT_DIR/generate_icon.py"

# 2. Prepare bundle directory structure
echo "2. Creating bundle directory structure..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# 3. Copy Icon
cp "$SCRIPT_DIR/build/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
cp "$SCRIPT_DIR/build/app_icon_1024.png" "$APP_DIR/Contents/Resources/icon.png"

# 4. Create Info.plist
echo "3. Creating Info.plist..."
cat <<'EOF' > "$APP_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>AutoJurnal</string>
    <key>CFBundleExecutable</key>
    <string>AutoJurnal</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.autojurnal.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>AutoJurnal</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# 5. Create PkgInfo
echo "APPL????" > "$APP_DIR/Contents/PkgInfo"

# 6. Create Launcher Executable
echo "4. Creating executable launcher..."
cat <<'EOF' > "$APP_DIR/Contents/MacOS/AutoJurnal"
#!/usr/bin/env bash
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export MPLCONFIGDIR=/tmp/matplotlib
export MPLBACKEND=Agg
mkdir -p /tmp/matplotlib
mkdir -p "$HOME/.autojurnal"

APP_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Resolve Project Root
PROJECT_ROOT=""
CANDIDATE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [ -f "$CANDIDATE_ROOT/backend/main.py" ]; then
    PROJECT_ROOT="$CANDIDATE_ROOT"
elif [ -f "$HOME/.autojurnal/project_root.txt" ] && [ -f "$(cat "$HOME/.autojurnal/project_root.txt")/backend/main.py" ]; then
    PROJECT_ROOT="$(cat "$HOME/.autojurnal/project_root.txt")"
elif [ -f "$HOME/Documents/GitHub/autojurnal/backend/main.py" ]; then
    PROJECT_ROOT="$HOME/Documents/GitHub/autojurnal"
fi

if [ -z "$PROJECT_ROOT" ]; then
    SELECTED_DIR=$(osascript -e 'try
        POSIX path of (choose folder with prompt "Pilih folder project AutoJurnal:")
    on error
        ""
    end try')
    if [ -n "$SELECTED_DIR" ] && [ -f "$SELECTED_DIR/backend/main.py" ]; then
        PROJECT_ROOT="${SELECTED_DIR%/}"
        echo "$PROJECT_ROOT" > "$HOME/.autojurnal/project_root.txt"
    else
        osascript -e 'display alert "AutoJurnal Error" message "Folder backend/main.py tidak ditemukan. Pastikan memilih folder project AutoJurnal yang benar."'
        exit 1
    fi
fi

# Store project root for future moves
echo "$PROJECT_ROOT" > "$HOME/.autojurnal/project_root.txt"
cd "$PROJECT_ROOT"

# 2. Check if already running on port 8000
RUNNING_PID=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$RUNNING_PID" ]; then
    ACTION=$(osascript -e 'try
        button returned of (display dialog "AutoJurnal sedang aktif di port 8000.\n\nApa yang ingin Anda lakukan?" with title "AutoJurnal" buttons {"Batal", "Hentikan Server", "Buka di Browser"} default button "Buka di Browser" with icon note)
    on error
        "Batal"
    end try')
    
    if [ "$ACTION" = "Buka di Browser" ]; then
        open "http://localhost:8000"
        exit 0
    elif [ "$ACTION" = "Hentikan Server" ]; then
        for pid in $RUNNING_PID; do
            kill -9 "$pid" 2>/dev/null || true
        done
        osascript -e 'display notification "Server AutoJurnal telah dihentikan." with title "AutoJurnal"'
        exit 0
    else
        exit 0
    fi
fi

# 3. Virtual Environment Check / Setup
PYTHON_EXE=""
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_EXE="$PROJECT_ROOT/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    osascript -e 'display notification "Menyiapkan virtual environment pertama kali..." with title "AutoJurnal"'
    python3 -m venv "$PROJECT_ROOT/venv"
    "$PROJECT_ROOT/venv/bin/pip" install -q -r "$PROJECT_ROOT/backend/requirements.txt"
    PYTHON_EXE="$PROJECT_ROOT/venv/bin/python"
else
    osascript -e 'display alert "AutoJurnal Error" message "Python 3 tidak ditemukan di sistem macOS Anda. Silakan instal Python 3 terlebih dahulu."'
    exit 1
fi

# 4. Start Server
LOG_FILE="$HOME/.autojurnal/server.log"
echo "=== Starting AutoJurnal $(date) ===" > "$LOG_FILE"

osascript -e 'display notification "Memulai server AutoJurnal..." with title "AutoJurnal"'

nohup "$PYTHON_EXE" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$HOME/.autojurnal/server.pid"

# 5. Wait for server to become responsive
READY=0
for i in {1..30}; do
    if curl -s -m 1 http://127.0.0.1:8000 >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ $READY -eq 1 ]; then
    open "http://localhost:8000"
    osascript -e 'display notification "AutoJurnal berhasil dijalankan di http://localhost:8000" with title "AutoJurnal"'
else
    # Check if process is still alive
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        LAST_ERR=$(tail -n 6 "$LOG_FILE" | tr '"' "'")
        osascript -e "display alert \"Gagal Memulai AutoJurnal\" message \"Server berhenti tiba-tiba:\n\n$LAST_ERR\n\nLog lengkap: $LOG_FILE\""
    else
        open "http://localhost:8000"
        osascript -e 'display notification "Membuka browser..." with title "AutoJurnal"'
    fi
fi
EOF

chmod +x "$APP_DIR/Contents/MacOS/AutoJurnal"

# 7. Make a helper stop script and Desktop shortcut helper
cat <<'EOF' > "$ROOT_DIR/stop.sh"
#!/usr/bin/env bash
RUNNING_PID=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$RUNNING_PID" ]; then
    for pid in $RUNNING_PID; do
        kill -9 "$pid" 2>/dev/null || true
    done
    echo "✅ Server AutoJurnal di port 8000 telah dihentikan."
else
    echo "ℹ️ Tidak ada server AutoJurnal yang sedang berjalan di port 8000."
fi
EOF
chmod +x "$ROOT_DIR/stop.sh"

echo "✅ AutoJurnal.app successfully built at: $APP_DIR"
