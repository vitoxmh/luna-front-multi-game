"""
paths.py - Rutas base centralizadas para desarrollo y binario empaquetado.

- En desarrollo: BASE_PATH apunta a la raiz del proyecto (donde esta este archivo).
- Empaquetado con PyInstaller:
    * Los datos que vienen dentro del bundle (solo lectura) se resuelven
      desde sys._MEIPASS (carpeta temporal de onefile / carpeta dist en onedir).
    * Los datos editables/generados en runtime (config.json, ui_config.json,
      controles.json, game_cache.json, romslist, imagenes/roms personalizadas)
      viven en el directorio del ejecutable/dist para que persistan.
"""
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# Raiz del codigo/source (o bundle extraido en modo frozen).
_SOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

# Directorio de datos persistentes: junto al ejecutable/dist cuando esta
# empaquetado; la raiz del proyecto en desarrollo.
if _is_frozen():
    _DATA_DIR = Path(getattr(sys, "executable", Path(__file__).resolve().parent)).resolve().parent
else:
    _DATA_DIR = Path(__file__).resolve().parent


def base_path() -> Path:
    """Carpeta del proyecto en dev, o junto al ejecutable cuando esta empaquetado.

    Usa esta funcion para datos persistentes y editables (config, roms,
    imagenes, cache). En dev coincide con BASE_PATH / DATADIR.
    """
    return _DATA_DIR


def resource_path(rel: str) -> Path:
    """Resuelve una ruta de recurso incluido en el bundle (solo lectura).

    En dev devuelve _DATA_DIR/rel; empaquetado busca primero dentro del
    bundle (_MEIPASS/rel) y si no existe cae al directorio de datos.
    """
    p = _SOURCE_DIR / Path(rel)
    if _is_frozen() and not p.exists():
        p = _DATA_DIR / Path(rel)
    return p


# Backwards-compatible constantes
BASE_PATH = base_path()
DATADIR = _DATA_DIR
