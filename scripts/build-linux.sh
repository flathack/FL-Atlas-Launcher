#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-linux-build"
DIST_DIR="${ROOT_DIR}/dist-linux"
BUILD_DIR="${ROOT_DIR}/build-linux"

echo "[1/5] Preparing virtual environment"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

echo "[2/5] Installing runtime and build dependencies"
python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/requirements.txt" PyInstaller PyYAML

echo "[3/5] Cleaning previous build artifacts"
rm -rf "${DIST_DIR}" "${BUILD_DIR}"

echo "[4/5] Building Linux bundle"
pyinstaller \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${BUILD_DIR}" \
  "${ROOT_DIR}/FL-Atlas-Launcher.spec"

echo "[5/5] Writing convenience launcher files"
APP_DIR="${DIST_DIR}/FL-Atlas-Launcher"
cat > "${APP_DIR}/launch.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/FL-Atlas-Launcher" "$@"
EOF
chmod +x "${APP_DIR}/launch.sh"

cat > "${APP_DIR}/FL-Atlas-Launcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=FL Atlas Launcher
Comment=Freelancer launcher for Linux
Exec=launch.sh
Icon=fl_atlas_launcher_icon_512
Terminal=false
Categories=Game;Utility;
StartupWMClass=FL-Atlas-Launcher
EOF

cp "${ROOT_DIR}/app/resources/icons/fl_atlas_launcher_icon_512.png" "${APP_DIR}/fl_atlas_launcher_icon_512.png"

echo
echo "Linux build completed:"
echo "  ${APP_DIR}"
