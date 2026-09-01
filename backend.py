"""
backend.py - Backend Python del Frontend Arcade.

Capa de servicios usada directamente por la interfaz nativa PySide6:
escaneo de ROMs, lanzamiento de emuladores, scraping y configuracion.
"""

import json
import subprocess
from PySide6.QtCore import QObject, Slot, Signal, QTimer
from PySide6.QtWidgets import QApplication
from config import load_configuration, save_configuration, get_relative_path
from scanner import (
    scan_roms, SystemInfo, save_scan, load_scan, absolute_path
)
from launcher import launch_rom, check_emulators
from scraper import scraper, GameInfo


class Backend(QObject):
    """
    Backend de servicios para la interfaz nativa PySide6.
    """

    # Señal para enviar datos al frontend
    data_sent = Signal(str)
    # Señal emitida cuando el emulador se cierra
    emulator_closed = Signal()
    # Señal emitida con el state del emulador (True=activo, False=inactivo)
    emulator_state = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = load_configuration()
        self.roms = {}
        self._system_list = []
        self.window = None
        self._emulator_process = None

        # Timer para monitorear el proceso del emulador
        self._emulator_timer = QTimer(self)
        self._emulator_timer.setInterval(500)
        self._emulator_timer.timeout.connect(self._check_emulator)

    @Slot(result=str)
    def get_config(self) -> str:
        """Retorna la configuración completa como JSON."""
        return json.dumps(self.config, ensure_ascii=False, indent=2)

    @Slot(result=str)
    def get_base_path(self) -> str:
        """Retorna la path base del proyecto."""
        import paths
        return str(paths.base_path())

    @Slot(str, result=bool)
    def file_exists(self, path: str) -> bool:
        """Verifica si un archivo existe en disco."""
        import os
        return os.path.isfile(path)

    @Slot(str, result=str)
    def scan(self, mode: str = "") -> str:
        """
        Escanea todas las ROMs y retorna el result como JSON.
        Por defecto carga desde romslist/*.json (cache).
        Si falta algún emulador o mode='rescan', re-escanea desde disco.
        """
        from scanner import get_statistics, find_category_background

        if mode == "rescan":
            print("[SCAN] Re-escaneo forzado desde disco...")
            self.roms = scan_roms(self.config)
            save_scan(self.roms)
        else:
            self.roms = load_scan()
            if self.roms is None:
                print("[SCAN] No hay cache, escaneando disco...")
                self.roms = scan_roms(self.config)
                save_scan(self.roms)
            else:
                # Descartar emuladores cacheados que ya no esten en config.json
                # (evita plataformas fantasma de configs viejos/borrados).
                valid = set(self.config.get("emulators", {}).keys())
                stale = set(self.roms.keys()) - valid
                if stale:
                    print(f"[SCAN] Descartando emuladores fuera del config: {sorted(stale)}")
                    self.roms = {k: v for k, v in self.roms.items() if k in valid}
                # Verificar que no falte ningún emulador del config
                emu_config = set(self.config.get("emulators", {}).keys())
                emu_cache = set(self.roms.keys())
                missing = emu_config - emu_cache
                if missing:
                    print(f"[SCAN] Faltan emuladores en cache: {missing}, re-escaneando...")
                    self.roms = scan_roms(self.config)
                    save_scan(self.roms)

        self._system_list = []

        categories = []
        for emu_id, systems in self.roms.items():
            emu_config = self.config.get("emulators", {}).get(emu_id, {})
            rom_paths = emu_config.get("rom_paths", {})
            es_subcats = isinstance(rom_paths, dict)
            for system in systems:
                # Fondo de plataforma: config explicita (emu o subcategory)
                # o busqueda automatica en images/<...>/fondo/
                category_id = ""
                bg_config = emu_config.get("bg_image", "")
                if es_subcats and system.id.startswith(emu_id + "_"):
                    category_id = system.id[len(emu_id) + 1:]
                    cc = rom_paths.get(category_id, {})
                    if isinstance(cc, dict):
                        bg_config = cc.get("bg_image", "") or bg_config
                bg_image = bg_config or find_category_background(emu_id, category_id)

                category = {
                    "id": system.id,
                    "name": system.name,
                    "emulator": system.emulator,
                    "wheel_img": system.wheel_img,
                    "bg_image": bg_image,
                    "total_roms": len(system.roms),
                    "roms": [
                        {
                            "name": rom.name,
                            "file_path": rom.file_path,
                            "emulator": rom.emulator,
                            "category": rom.category,
                            "extension": rom.extension,
                            "size_kb": rom.size_kb,
                            "image": absolute_path(rom.image),
                            "marquee": absolute_path(rom.marquee),
                            "snap": absolute_path(rom.snap),
                            "core": rom.core,
                        }
                        for rom in system.roms
                    ],
                }
                categories.append(category)
                self._system_list.append(system)

        stats = get_statistics(self.roms)

        result = {
            "categories": categories,
            "stats": stats,
            "total_roms": sum(
                s.get("total_roms", 0) for s in stats.values()
            ),
        }

        return json.dumps(result, ensure_ascii=False)

    @Slot(str, str, result=str)
    def launch_rom(self, file_path: str, emulator: str = "") -> str:
        """
        Lanza la ROM con el archivo especificado.
        Si se indica 'emulador', solo coincide la ROM de ese emulador
        (evita lanzar MAME cuando el mismo zip existe en varias plataformas).
        Pausa el video y monitorea el proceso del emulador.
        Retorna JSON con el result.
        """
        # Buscar la ROM por archivo (y emulador si se especificó)
        for system in self._system_list:
            for rom in system.roms:
                if rom.file_path == file_path and (
                    not emulator or rom.emulator == emulator
                ):
                    # Monitor donde corre el front, para lanzar el emulador
                    # en esa misma pantalla (no separada).
                    screen_rect = None
                    win = self.window
                    if win is not None:
                        try:
                            scr = win.screen() or QApplication.primaryScreen()
                            if scr is not None:
                                g = scr.geometry()
                                screen_rect = (g.x(), g.y(), g.width(), g.height())
                        except Exception:
                            screen_rect = None

                    proc = launch_rom(rom, self.config, screen_rect=screen_rect)
                    if proc is not None:
                        self._emulator_process = proc
                        self._emulator_timer.start()
                        self.emulator_state.emit(True)

                    return json.dumps({
                        "success": proc is not None,
                        "rom": rom.name,
                        "emulator": rom.emulator,
                    })

        return json.dumps({"success": False, "error": "ROM no encontrada"})

    @Slot(result=str)
    def check_emulators(self) -> str:
        """Verifica qué emuladores están instalados."""
        state = check_emulators(self.config)
        # Convertir a serializable
        result = {}
        for emu_id, info in state.items():
            result[emu_id] = {
                "name": info["name"],
                "available": info["available"],
                "path": info["path"],
            }
        return json.dumps(result, ensure_ascii=False)

    @Slot(str, str, result=str)
    def scrape_game(self, rom_name: str, emulator: str) -> str:
        """
        Obtiene información scrapeada de un juego.
        Retorna JSON con: original_name, year, players, genre, manufacturer.
        """
        try:
            info = scraper.get_info(rom_name, emulator)
            return json.dumps({
                "name": rom_name,
                "original_name": info.original_name,
                "year": info.year,
                "players": info.players,
                "genre": info.genre,
                "manufacturer": info.manufacturer,
                "source": info.source,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "original_name": rom_name,
                "year": 0,
                "players": 0,
                "genre": "",
                "manufacturer": "",
                "source": "error",
                "error": str(e),
            })

    @Slot(str, result=str)
    def save_config(self, config_json: str) -> str:
        """Guarda la configuración desde el frontend."""
        try:
            new_config = json.loads(config_json)
            success = save_configuration(new_config)
            if success:
                self.config = new_config
            return json.dumps({"success": success})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def get_ui_config(self) -> str:
        """Retorna la configuración UI (ui_config.json) como JSON."""
        import paths
        ui_config_path = paths.base_path() / "ui_config.json"
        if ui_config_path.exists():
            try:
                with open(ui_config_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return json.dumps({
            "colors": { "background": "#000000", "text": "#ffffff", "selected": "#ff6600", "accent": "#00ccff", "text_dim": "#888888", "border": "#222222" },
            "wheel": { "visible_items": 13, "radio": 320, "angular_separation": 8, "central_scale": 1.4, "min_scale": 0.3, "item_width": 300, "item_height": 70 },
            "background": { "blur": 12, "brightness": 0.25, "scale": 1.15, "use_snap": True, "images": [], "active_image": -1 },
            "snap": { "max_height": 180 },
            "info_panel": { "width": 320 },
            "video": { "x": 30, "y": 90, "w": 490, "h": 368, "fixed": False }
        })

    @Slot(str, result=str)
    def save_ui_config(self, config_json: str) -> str:
        """Guarda la configuración UI en ui_config.json."""
        import paths
        ui_config_path = paths.base_path() / "ui_config.json"
        try:
            config = json.loads(config_json)
            with open(ui_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"[OK] UI Configuración guardada en {ui_config_path}")
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def get_controls(self) -> str:
        """Retorna la configuracion de controls (controls.json) como JSON."""
        import paths
        controls_path = paths.base_path() / "controls.json"
        if controls_path.exists():
            try:
                with open(controls_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        from config import DEFAULT_CONTROLS
        return json.dumps(DEFAULT_CONTROLS)

    @Slot(str, result=str)
    def save_controls(self, controls_json: str) -> str:
        """Guarda la configuracion de controls en controls.json."""
        import paths
        controls_path = paths.base_path() / "controls.json"
        try:
            controls = json.loads(controls_json)
            with open(controls_path, "w", encoding="utf-8") as f:
                json.dump(controls, f, indent=4, ensure_ascii=False)
            print(f"[OK] Controles guardados en {controls_path}")
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot()
    def quit(self):
        """Cierra la aplicación."""
        if self.window:
            self.window.close()

    @Slot(str, result=str)
    def get_category_icon(self, category_id: str) -> str:
        """Returns an emoji/icon for each category."""
        icons = {
            "arcade": "🕹️",
            "multi": "🎮",
            "nintendo": "🍄",
            "playstation": "💿",
            "sega": "🔵",
            "default": "🎯",
        }
        # Buscar en la configuración
        for emu_id, emu_config in self.config.get("emulators", {}).items():
            if emu_id in category_id or category_id.startswith(emu_id):
                icon_key = emu_config.get("icon", "default")
                return icons.get(icon_key, "🎯")
        return "🎯"

    def _check_emulator(self):
        """Called by QTimer - checks if the emulator process is still running."""
        if self._emulator_process is None:
            self._emulator_timer.stop()
            return

        ret = self._emulator_process.poll()
        if ret is not None:
            # Emulador cerrado
            print(f"[OK] Emulador cerrado (código: {ret})")
            self._emulator_process = None
            self._emulator_timer.stop()
            self.emulator_state.emit(False)
            self.emulator_closed.emit()
