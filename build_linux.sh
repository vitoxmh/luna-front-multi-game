#!/usr/bin/env bash
# build_linux.sh - Compila Luna como ejecutable Linux (carpeta dist/Luna)
# Uso (en Debian/Ubuntu):
#   sudo apt install -y python3-pip python3-venv
#   python3 -m venv venv && source venv/bin/activate
#   pip install -r requirements.txt pyinstaller
#   ./build_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_NAME="Luna"
DIST="$ROOT/dist/$DIST_NAME"

echo "==> Compilando con PyInstaller (onedir)..."
python3 -m PyInstaller --noconfirm --clean --onedir --windowed --name "$DIST_NAME" \
    --add-data "assets:assets" \
    --add-data "layouts:layouts" \
    main.py

echo "==> Copiando datos por defecto junto al ejecutable..."
cp -r "$ROOT/assets/." "$DIST/assets/" 2>/dev/null || true
cp -r "$ROOT/layouts/." "$DIST/layouts/" 2>/dev/null || true
if [ -f "$ROOT/config.json.example" ]; then cp "$ROOT/config.json.example" "$DIST/config.json.example"; fi
echo "  + assets, layouts, config.json.example"

echo ""
echo "==> Listo! Ejecutable en: $DIST/$DIST_NAME"
echo "    (config.json, romslist/, roms/ e images/ de ROMs se generan en esa carpeta al primer arranque)"
echo "    Las imagenes de plataforma/personalizadas NO se exportan: copialas tu mismo en $DIST/images/"