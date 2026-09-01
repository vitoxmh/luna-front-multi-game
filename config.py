"""
config.py - Gestión de configuración del frontend arcade.

Lee, escribe y valida la configuración desde config.json.
Crea la configuración por defecto si no existe.
"""

import json
import os
import sys
from pathlib import Path

from paths import BASE_PATH as _BASE


# Ruta base del proyecto (funciona tanto en desarrollo como empaquetado)
BASE_PATH = _BASE
CONFIG_PATH = BASE_PATH / "config.json"


def get_relative_path(path: str) -> Path:
    """Convierte una ruta relativa a ruta absoluta basada en la ubicación del proyecto."""
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return BASE_PATH / path_obj


def load_configuration() -> dict:
    """
    Carga la configuración desde config.json.
    Si no existe, crea una configuración por defecto.
    """
    if not CONFIG_PATH.exists():
        print(f"[INFO] No se encontró config.json en {BASE_PATH}")
        print("[INFO] Creando configuración por defecto...")
        config = _default_configuration()
        save_configuration(config)
        return config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            config = json.load(file)
        print(f"[OK] Configuración cargada desde {CONFIG_PATH}")
        return config
    except json.JSONDecodeError as e:
        print(f"[ERROR] Error al leer config.json: {e}")
        print("[INFO] Usando configuración por defecto...")
        return _default_configuration()
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        return _default_configuration()


def save_configuration(config: dict) -> bool:
    """Guarda la configuración en config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
        print(f"[OK] Configuración guardada en {CONFIG_PATH}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar la configuración: {e}")
        return False


def validate_configuration(config: dict) -> list:
    """
    Valida la configuración y retorna una lista de advertencias.
    """
    warnings = []

    emulators = config.get("emulators", {})
    if not emulators:
        warnings.append("No hay emuladores configurados en config.json")

    for emu_id, emu_config in emulators.items():
        executable = emu_config.get("executable", "")
        if not executable:
            warnings.append(f"El emulador '{emu_id}' no tiene ejecutable configurado")

        rom_paths = emu_config.get("rom_paths", "")
        if isinstance(rom_paths, str) and rom_paths:
            full_path = get_relative_path(rom_paths)
            if not full_path.exists():
                warnings.append(
                    f"La ruta de ROMs para '{emu_id}' no existe: {full_path}"
                )
        elif isinstance(rom_paths, dict):
            for cat_id, cat_config in rom_paths.items():
                if isinstance(cat_config, str):
                    path = cat_config
                else:
                    path = cat_config.get("path", "")
                if path:
                    full_path = get_relative_path(path)
                    if not full_path.exists():
                        warnings.append(
                            f"La ruta de ROMs para '{emu_id}/{cat_id}' no existe: {full_path}"
                        )

    return warnings


CONTROLS_PATH = BASE_PATH / "controls.json"

DEFAULT_CONTROLS = {
    "device": "keyboard",
    "keyboard": {
        "up": ["Up", "W"],
        "down": ["Down", "S"],
        "left": ["Left"],
        "right": ["Right"],
        "select": ["Return", "Space"],
        "back": ["Escape"],
        "close": ["Escape"],
        "fullscreen": ["F11"],
        "config": ["Shift"],
        "clear_search": ["Backspace"],
    },
    "gamepad": {
        "up": ["AxisLeftY-", "ButtonDPadUp"],
        "down": ["AxisLeftY+", "ButtonDPadDown"],
        "left": ["AxisLeftX-", "ButtonDPadLeft"],
        "right": ["AxisLeftX+", "ButtonDPadRight"],
        "select": ["ButtonCross", "ButtonA"],
        "back": ["ButtonCircle", "ButtonB"],
        "fullscreen": ["ButtonStart", "ButtonOptions"],
        "config": ["ButtonBack", "ButtonShare"],
    },
    "gamepad_deadzone": 0.5,
}


def load_controls() -> dict:
    """Carga la configuracion de controles desde controls.json."""
    if not CONTROLS_PATH.exists():
        print(f"[INFO] No se encontro controls.json, creando por defecto...")
        save_controls(DEFAULT_CONTROLS)
        return json.loads(json.dumps(DEFAULT_CONTROLS))
    try:
        with open(CONTROLS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Error al leer controls.json: {e}")
        return json.loads(json.dumps(DEFAULT_CONTROLS))


def save_controls(controls: dict) -> bool:
    """Guarda la configuracion de controles en controls.json."""
    try:
        with open(CONTROLS_PATH, "w", encoding="utf-8") as f:
            json.dump(controls, f, indent=4, ensure_ascii=False)
        print(f"[OK] Controles guardados en {CONTROLS_PATH}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudieron guardar los controles: {e}")
        return False


def _default_configuration() -> dict:
    """Retorna una configuración por defecto mínima para empezar."""
    return {
        "app_name": "Mi Arcade Frontend",
        "theme": "dark",
        "fullscreen": True,
        "resolution": [1920, 1080],
        "emulators": {
            "mame": {
                "name": "MAME (Arcade)",
                "executable": "mame",
                "launch_args": "-rompath {romdir} {romname} -nowindow",
                "extensions": [".zip"],
                "rom_paths": "roms/mame",
                "wheel_img": "images/mame/wheel/mame.png",
                "icon": "arcade",
            },
            "retroarch": {
                "name": "RetroArch (Multi-Sistema)",
                "executable": "retroarch",
                "launch_args": "-L {core} --fullscreen {rompath}",
                "extensions": [".nes", ".sfc", ".smc", ".gb", ".gba", ".gen", ".n64"],
                "rom_paths": {
                    "nes": {
                        "name": "NES / Famicom",
                        "core": "fceumm",
                        "path": "roms/retroarch/nes",
                        "wheel_img": "images/retroarch/nes/wheel/nes.png",
                    },
                    "snes": {
                        "name": "SNES / Super Famicom",
                        "core": "snes9x",
                        "path": "roms/retroarch/snes",
                        "wheel_img": "images/retroarch/snes/wheel/snes.png",
                    },
                    "genesis": {
                        "name": "Genesis / Mega Drive",
                        "core": "genesis_plus_gx",
                        "path": "roms/retroarch/genesis",
                        "wheel_img": "images/retroarch/genesis/wheel/genesis.png",
                    },
                },
                "icon": "multi",
            },
        },
        "colors": {
            "background": "#0a0a0f",
            "text": "#ffffff",
            "selected": "#ff6600",
            "accent": "#00ccff",
            "active_category": "#ffcc00",
            "borders": "#333333",
        },
    }
