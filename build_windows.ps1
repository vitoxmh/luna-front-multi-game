# build_windows.ps1 - Compila Luna como ejecutable Windows (carpeta dist/Luna)
# Requisitos: Python 3.10+ y `pip install -r requirements.txt pyinstaller`

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$DistName = "Luna"
$Dist = Join-Path $Root "dist\$DistName"

Write-Host "==> Compilando con PyInstaller (onedir)..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --onedir --windowed --name $DistName main.py

Write-Host "==> Copiando datos por defecto junto al ejecutable..." -ForegroundColor Cyan

$DataDirs = @(
    "assets",
    "layouts"
)
foreach ($d in $DataDirs) {
    $src = Join-Path $Root $d
    if (Test-Path -LiteralPath $src) {
        $dst = Join-Path $Dist $d
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
        Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
        Write-Host "  + $d"
    }
}

if (Test-Path -LiteralPath (Join-Path $Root "config.json.example")) {
    Copy-Item -Path (Join-Path $Root "config.json.example") -Destination (Join-Path $Dist "config.json.example") -Force
    Write-Host "  + config.json.example"
}

Write-Host ""
Write-Host "==> Listo! Ejecutable en: $Dist\$DistName.exe" -ForegroundColor Green
Write-Host "    (config.json, romslist/, roms/ e images/ de ROMs se generan en esa carpeta al primer arranque)"
Write-Host "    Las imagenes de plataforma/personalizadas NO se exportan: copialas tu mismo en $Dist\images\"