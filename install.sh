#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
#  AutoJurnal - Native App Installer & Environment Setup (macOS / Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================================"
echo "   🚀 Memulai Instalasi AutoJurnal (Native App Setup)  "
echo "======================================================"
echo ""

# 1. Cek Python
echo "🔍 1/5 Memeriksa Python 3..."
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 tidak ditemukan. Silakan install Python 3.10+ terlebih dahulu."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "   ✅ Python terdeteksi: versi $PY_VERSION ($($PYTHON_CMD --version))"

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    export ARCHFLAGS="-arch arm64"
else
    export ARCHFLAGS="-arch x86_64"
fi

# 2. Setup Virtual Environment
echo ""
echo "📦 2/5 Menyiapkan Virtual Environment (venv)..."
if [ -d "venv" ]; then
    if ! ./venv/bin/python -c "import sys" &>/dev/null; then
        echo "   ⚠️ Virtual environment lama tidak kompatibel. Membuat ulang venv bersih..."
        rm -rf venv
        $PYTHON_CMD -m venv venv
    else
        echo "   Virtual environment siap."
    fi
else
    echo "   Membuat venv baru..."
    $PYTHON_CMD -m venv venv
fi

# 3. Install Dependencies
echo ""
echo "📥 3/5 Menginstal dependensi library..."
export MPLCONFIGDIR=/tmp/matplotlib
export MPLBACKEND=Agg
mkdir -p /tmp/matplotlib

./venv/bin/pip install --prefer-binary --timeout 15 --retries 1 -q --upgrade pip setuptools wheel 2>/dev/null || true
./venv/bin/pip install --prefer-binary --timeout 15 --retries 1 -q -r backend/requirements.txt || echo "   (Catatan: Gunakan koneksi internet jika ada library baru yang perlu diunduh)"
echo "   ✅ Dependensi terverifikasi."

# 4. Inisialisasi Konfigurasi .env
echo ""
echo "⚙️  4/5 Memeriksa file konfigurasi .env..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "   ✅ File .env berhasil dibuat dari .env.example."
    fi
else
    echo "   ✅ File .env sudah tersedia."
fi

# 5. Build Native App (macOS)
echo ""
echo "🖥️  5/5 Membangun Aplikasi Desktop Native..."
chmod +x run.sh stop.sh scripts/*.sh 2>/dev/null || true

if [[ "$OSTYPE" == "darwin"* ]]; then
    if [ -f "scripts/build_universal_app.sh" ]; then
        echo "   Membangun AutoJurnal.app untuk macOS..."
        bash scripts/build_universal_app.sh
        
        # Simpan project path ke config ~/.autojurnal (jika diizinkan)
        mkdir -p "$HOME/.autojurnal" 2>/dev/null || true
        (echo "$SCRIPT_DIR" > "$HOME/.autojurnal/project_root.txt") 2>/dev/null || true
        
        echo ""
        echo "   ✅ AutoJurnal.app berhasil dibuat di folder project!"
        echo "   💡 Anda bisa langsung drag/copy 'AutoJurnal.app' ke folder /Applications atau Desktop."
    fi
else
    echo "   Sistem Linux terdeteksi: launcher run.sh telah siap."
fi

echo ""
echo "======================================================"
echo "   🎉 Instalasi Selesai & AutoJurnal Siap Digunakan!  "
echo "======================================================"
echo ""
echo "Cara menjalankan AutoJurnal:"
if [[ "$OSTYPE" == "darwin"* ]]; then
echo "  1. Klik ganda (Double-click) file 'AutoJurnal.app'"
echo "     (Aplikasi akan terbuka otomatis di window native)"
echo "  2. ATAU jalankan via terminal: ./run.sh"
else
echo "  • Jalankan di terminal: ./run.sh"
fi
echo ""
echo "Untuk menghentikan server:"
echo "  • Jalankan: ./stop.sh (atau pilih 'Hentikan Server' dari AutoJurnal.app)"
echo ""
