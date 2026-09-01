"""
main.py - Punto de entrada del Frontend Arcade (100% Python nativo).

Interfaz construida integramente con widgets PySide6, sin HTML/CSS/JS:
  - WheelWidget (QPainter custom) para carousel 3D estilo Hyperspin
  - BackgroundWidget con blur/brightness nativo
  - QMediaPlayer + QVideoSink: los frames se pintan en un widget normal
  - ConfigDialog nativo con sliders y color pickers
  - SplashScreen animado mientras carga y genera los file_paths base

Atajos:
  F11    = Pantalla completa
  Shift  = Configuracion
  Ctrl+L = Editor de layout en vivo
  Ctrl+P = Posiciones (rueda / info / video)
  ESC    = Volver / Salir
"""

import sys
import os
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QPushButton, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QTimer, QUrl, Signal, Slot, QSize, QPoint, QRect, QEvent,
    QObject, QRunnable, QThreadPool, QFileSystemWatcher
)
from PySide6.QtGui import QFont, QColor, QPalette, QPixmap, QImage, QPainter

from backend import Backend
from widgets.wheel_widget import WheelWidget, WheelItem
from widgets.bg_widget import BackgroundWidget
from widgets.config_dialog import ConfigDialog
from widgets.controls_dialog import ControlsDialog
from widgets.layout_editor import LayoutEditor
from widgets.posiciones_admin import PosicionesAdmin
from widgets.focus_nav import DpadNav
from widgets.splash import SplashScreen
from scraper import scraper
from config import load_controls, save_controls, DEFAULT_CONTROLS
from i18n import tr, set_language, current_language, language_changed

try:
    from PySide6.QtMultimedia import (
        QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame, QMediaDevices,
    )
    HAS_VIDEO = True
except ImportError:
    HAS_VIDEO = False

from gamepad_manager import GamepadManager, GAMEPAD_BUTTON_NAMES


from paths import BASE_PATH

# Backend de video uniforme en Windows y Linux (PySide6 incluye FFmpeg)
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")


def load_layout():
    layout_path = BASE_PATH / "layouts" / "layout.json"
    if layout_path.exists():
        with open(layout_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


LAYOUT = load_layout()


class _ScrapeSignals(QObject):
    info_ready = Signal(str, dict)


class ScrapeWorker(QRunnable):
    """Obtiene la info del juego (year/genre/manufacturer) fuera del hilo GUI."""

    def __init__(self, file_path, name, emulator):
        super().__init__()
        self.file_path = file_path
        self.name = name
        self.emulator = emulator
        self.signals = _ScrapeSignals()

    def run(self):
        try:
            info = scraper.get_info(self.name, self.emulator)
            data = {
                "original_name": info.original_name,
                "year": info.year,
                "genre": info.genre,
                "manufacturer": info.manufacturer,
                "players": info.players,
                "source": info.source,
            }
        except Exception as e:
            print(f"[Scrape] Error: {e}")
            return
        self.signals.info_ready.emit(self.file_path, data)


class _ScanSignals(QObject):
    done = Signal(str)


class ScanWorker(QRunnable):
    """Escanea/genera los file_paths base de ROMs fuera del hilo GUI
    para que el splash siga animado durante el escaneo."""

    def __init__(self, backend, mode=""):
        super().__init__()
        self.backend = backend
        self.mode = mode
        self.signals = _ScanSignals()

    def run(self):
        try:
            raw = self.backend.scan(self.mode)
        except Exception as e:
            print(f"[Scan] Error: {e}")
            raw = ""
        self.signals.done.emit(raw)


class InfoPanel(QWidget):
    """Panel izquierdo: muestra info del item seleccionado (categoria o ROM)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 15, 10)
        layout.setSpacing(8)

        # Logo / imagen
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo.setStyleSheet("background: transparent;")
        layout.addWidget(self.lbl_logo)

        # Nombre
        self.lbl_name = QLabel("")
        self.lbl_name.setWordWrap(True)
        layout.addWidget(self.lbl_name)

        # Stats
        self.lbl_stats = QLabel("")
        layout.addWidget(self.lbl_stats)

        # Emulador
        self.lbl_emulator = QLabel("")
        layout.addWidget(self.lbl_emulator)

        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        layout.addWidget(line)

        # Snap area
        self.lbl_snap = QLabel("SIN SNAP")
        self.lbl_snap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_snap)

        # Datos actuales para poder retraducir en vivo
        self._current_cat = None
        self._current_rom = None
        # Info adicional (year, genre, etc), bajo el video
        self.lbl_info = QLabel("")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        layout.addStretch()

        self.apply(LAYOUT.get("info_panel", {}))

    def apply(self, cfg):
        """Aplica estilos/sizes desde la section info_panel de layout.json."""
        cfg = cfg or {}
        self.setFixedWidth(cfg.get("width", 350))
        self.setStyleSheet(f"background: {cfg.get('background_gradient', 'transparent')};")

        self.lbl_logo.setFixedHeight(cfg.get("logo_height", 80))
        self._logo_max_h = cfg.get("logo_max_height", 70)

        self.lbl_name.setStyleSheet(
            f"color: {cfg.get('name_color', '#fff')}; "
            f"font-size: {cfg.get('name_font_size', 22)}px; font-weight: bold; "
            "text-transform: uppercase; background: transparent;"
        )
        self.lbl_stats.setStyleSheet(
            f"color: {cfg.get('stats_color', '#00ccff')}; "
            f"font-size: {cfg.get('stats_font_size', 14)}px; font-weight: bold; background: transparent;"
        )
        self.lbl_emulator.setStyleSheet(
            f"color: {cfg.get('emulator_color', '#888')}; "
            f"font-size: {cfg.get('emulator_font_size', 12)}px; background: transparent;"
        )
        self.lbl_info.setStyleSheet(
            f"color: {cfg.get('info_color', '#ccc')}; "
            f"font-size: {cfg.get('info_font_size', 12)}px; background: transparent;"
        )
        snap_h = cfg.get("snap_height", 200)
        self.lbl_snap.setFixedHeight(snap_h)
        self.lbl_snap.setStyleSheet(
            f"color: #555; font-size: 14px; "
            f"border: {cfg.get('snap_border', '1px solid rgba(255,140,0,0.3)')}; "
            f"background: {cfg.get('snap_bg', '#050508')}; "
            f"border-radius: {cfg.get('snap_radius', 6)}px;"
        )

    def set_category(self, cat):
        self._current_cat = cat
        self._current_rom = None
        self.lbl_name.setText(cat.get("name", ""))
        total = cat.get("total_roms", 0)
        self.lbl_stats.setText(tr("{n} ROMs", n=total))
        emu = cat.get("emulator", "")
        self.lbl_emulator.setText(tr("Emulador: {nombre}", nombre=emu.capitalize()) if emu else "")
        self.lbl_info.setText("")
        # En plataformas no se muestra snap
        self.lbl_snap.clear()
        self.lbl_snap.hide()
        self._set_logo(cat.get("wheel_img", ""))

    def set_rom(self, rom):
        self._current_cat = None
        self._current_rom = rom
        self.lbl_name.setText(rom.get("name", ""))
        size = rom.get("size_kb", 0)
        ext = rom.get("extension", "")
        if size > 1024:
            size_str = f"{size / 1024:.1f} MB"
        else:
            size_str = f"{size} KB"
        self.lbl_stats.setText(tr("Tamanio: {s} | Formato: .{e}", s=size_str, e=ext))

        # Scrape info
        info_parts = []
        for key, label in [
            ("year", "Ano"),
            ("genre", "Genero"),
            ("manufacturer", "Fabricante"),
        ]:
            val = rom.get(key, "")
            if val:
                info_parts.append(f"{tr(label)}: {val}")
        players = rom.get("players", 0)
        if isinstance(players, int) and players > 1:
            info_parts.append(tr("Jugadores: {n}", n=players))
        source = rom.get("source", "")
        text = "\n".join(info_parts) if info_parts else ""
        if text and source:
            text += f"\n[{source}]"
        self.lbl_info.setText(text)
        # Juegos arcade: priorizar el marquee (banner) sobre la wheel
        self._set_logo(rom.get("marquee", "") or rom.get("image", ""))

    def retranslate(self):
        """Re-aplica los textos segun el idioma actual."""
        if self._current_cat is not None:
            self.set_category(self._current_cat)
        elif self._current_rom is not None:
            self.set_rom(self._current_rom)
        elif self.lbl_snap.text() == tr("SIN SNAP") and not self._current_rom:
            self.lbl_snap.setText(tr("SIN SNAP"))

    def _set_logo(self, path):
        if not path:
            self.lbl_logo.clear()
            return
        path = path if os.path.isabs(path) else str(BASE_PATH / path)
        if not os.path.isfile(path):
            self.lbl_logo.clear()
            return
        img = QImage(path)
        if img.isNull():
            return
        scaled = img.scaledToHeight(getattr(self, "_logo_max_h", 70), Qt.SmoothTransformation)
        self.lbl_logo.setPixmap(QPixmap.fromImage(scaled))


class BottomBar(QWidget):
    """Barra inferior con hints de navegacion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.lbl = QLabel("Shift Config")
        # Texto de info alineado a la derecha
        layout.addStretch()
        layout.addWidget(self.lbl)
        self._mode = "categorias"
        self._controls = None

        self.apply(LAYOUT.get("bottom_bar", {}))

    def apply(self, cfg):
        """Aplica estilos desde la section bottom_bar de layout.json."""
        cfg = cfg or {}
        self.setFixedHeight(cfg.get("height", 40))
        self.setStyleSheet(
            f"background: {cfg.get('background', 'rgba(0,0,0,0.7)')}; "
            f"border-top: {cfg.get('border', '1px solid #1a1a1a')};"
        )
        self.lbl.setStyleSheet(
            f"color: {cfg.get('hint_color', '#777')}; "
            f"font-size: {cfg.get('hint_font_size', 12)}px; background: transparent;"
        )

    def set_mode(self, mode, controls=None):
        self._mode = mode
        self._controls = controls
        self._update_hint()

    def _update_hint(self):
        kb = (self._controls or {}).get("keyboard", {})
        nav = "/".join(kb.get("up", ["↑"]))
        sel = "/".join(kb.get("select", ["ENTER"]))
        esc = "/".join(kb.get("back", ["ESC"]))
        cfg = "/".join(kb.get("config", ["Shift"]))
        if self._mode == "categorias":
            self.lbl.setText(tr(
                "{nav} Navegar | {sel} Seleccionar | {esc} Salir | Shift Controles | {cfg} Config",
                nav=nav, sel=sel, esc=esc, cfg=cfg,
            ))
        else:
            self.lbl.setText(tr(
                "{nav} Navegar | {sel} Jugar | {esc} Volver | Shift Controles | Escribir para buscar",
                nav=nav, sel=sel, esc=esc,
            ))

    def retranslate(self):
        self._update_hint()


class TopBar(QWidget):
    """Barra superior con titulo e info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_title = QLabel("ARCADE")
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        self.lbl_info = QLabel("")
        layout.addWidget(self.lbl_info)

        self.apply(LAYOUT.get("top_bar", {}))

    def apply(self, cfg):
        """Aplica estilos desde la section top_bar de layout.json."""
        cfg = cfg or {}
        self.setFixedHeight(cfg.get("height", 55))
        self.setStyleSheet(
            f"background: {cfg.get('background', 'rgba(0,0,0,0.7)')}; "
            f"border-bottom: {cfg.get('border', '1px solid #1a1a1a')};"
        )
        self.lbl_title.setStyleSheet(
            f"color: {cfg.get('title_color', '#ff6600')}; "
            f"font-size: {cfg.get('title_font_size', 18)}px; font-weight: bold; background: transparent;"
        )
        self.lbl_info.setStyleSheet(
            f"color: {cfg.get('info_color', '#00ccff')}; "
            f"font-size: {cfg.get('info_font_size', 12)}px; background: transparent;"
        )


if HAS_VIDEO:
    class WidgetVideo(QWidget):
        """Muestra el video pintando los frames del QVideoSink en un widget
        normal (sin ventana nativa): las imagenes con Z y la transparencia
        se componen siempre correctamente."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._frame = QVideoFrame()
            self.setStyleSheet("background: black;")

        def setFrame(self, frame):
            if frame.isValid():
                self._frame = frame
                self.update()

        def paintEvent(self, ev):
            p = QPainter(self)
            p.fillRect(self.rect(), Qt.black)
            f = self._frame
            if not f.isValid():
                return
            img = f.toImage()
            if img.isNull():
                return
            scaled_img = img.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (self.width() - scaled_img.width()) // 2
            y = (self.height() - scaled_img.height()) // 2
            p.drawImage(x, y, scaled_img)


class VentanaArcade(QMainWindow):
    """Ventana principal con layout nativo PySide6."""

    def __init__(self, splash=None):
        super().__init__()
        self._splash = splash
        wcfg = LAYOUT.get("window", {})
        self.setWindowTitle(tr("Luna"))
        self.setMinimumSize(wcfg.get("min_width", 1024), wcfg.get("min_height", 600))
        self._config_open = False
        self._emulator_active = False

        # Backend Python
        self._splash_msg("Cargando configuracion...", 18)
        self.backend = Backend()
        self.backend.window = self
        self.backend.emulator_state.connect(self._on_emulator_state)
        self.backend.emulator_closed.connect(self._on_emulator_closed)

        # Datos
        self._categories = []
        self._current_roms = []
        self._mode = "categorias"
        self._current_category = None

        # Busqueda
        self._search_buffer = ""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(2000)
        self._search_timer.timeout.connect(self._clear_search)

        # Scraping async de info de juegos
        self._scrape_pool = QThreadPool(self)
        self._scrape_pool.setMaxThreadCount(1)

        # Escaneo de ROMs async (bajo el splash)
        self._scan_pool = QThreadPool(self)
        self._scan_pool.setMaxThreadCount(1)

        # Navegacion por teclado/gamepad en los dialogs (flechas/Enter/ESC)
        self._nav = DpadNav(QApplication.instance())

        # Build UI
        self._splash_msg("Preparando interfaz...", 38)
        self._build_ui()

        # Config dialog
        self._config_dialog = ConfigDialog(self)
        self._config_dialog.config_changed.connect(self._on_config_live)
        self._config_dialog.config_saved.connect(self._on_config_save)
        self._config_dialog.config_closed.connect(self._on_config_closed)
        self._config_dialog.quit_signal.connect(self.quit)
        self._config_dialog.controls_requested.connect(self._open_controls_from_config)
        self._nav.register(self._config_dialog)

        # Cargar YA la config UI guardada: evita que el bloque de resolucion
        # base (mas abajo) pise ui_config.json con values por defecto, y da
        # acceso a imagen de fondo / ajuste desde el arranque
        self._splash_msg("Aplicando configuracion...", 55)
        try:
            cfg = json.loads(self.backend.get_ui_config())
            self._config_dialog.load_config(cfg)
            self._apply_background_config(cfg.get("background") or {})
            # Idioma guardado en ui_config.json ("language": "es"|"en")
            lang = cfg.get("language", "es")
            set_language(lang)
            self._config_dialog.set_language_combo(lang)
            self._on_language_changed(lang)
        except Exception as e:
            print(f"[Config] Error al cargar al inicio: {e}")

        # Editor de layout en vivo (Ctrl+L)
        self._layout_editor = None

        # Administrador de posiciones (Ctrl+P)
        self._pos_admin = None
        # Sistema (plataforma) activo: id de la categoria en mode roms
        self._current_system = None
        # Ultima plataforma seleccionada (para restaurarla al volver atras)
        self._last_category_id = None
        # Ultima ROM seleccionada por plataforma (file_path) al salir de ella
        self._last_rom_ids = {}

        # Controles configurables
        self._controls = load_controls()
        self._key_map = self._build_key_map()
        self._gamepad_active = False
        self._gamepad = None
        self._gamepad_axes = {"x": 0.0, "y": 0.0}
        self._gamepad_deadzone = self._controls.get("gamepad_deadzone", 0.5)
        self._controls_dialog = None
        self._controls_open = False
        # Gamepad via pygame - instancia unica compartida
        self._gamepad_manager = GamepadManager(self)
        self._gamepad_manager.gamepad_connected.connect(self._on_gp_connected)
        self._gamepad_manager.gamepad_disconnected.connect(self._on_gp_disconnected)
        self._gamepad_manager.button_pressed.connect(self._on_gp_button)
        self._gamepad_manager.axis_changed.connect(self._on_gp_axis)
        self._gamepad_manager.hat_changed.connect(self._on_gp_hat)
        self._gamepad_manager.start()

        # Video player nativo
        self._media_player = None
        self._video_widget = None
        self._video_z = 0
        if HAS_VIDEO:
            self._video_widget = WidgetVideo(self)
            self._video_widget.hide()
            self._media_player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._setup_audio_device()
            self._media_player.setAudioOutput(self._audio_output)
            self._video_sink = QVideoSink()
            self._media_player.setVideoSink(self._video_sink)
            self._video_sink.videoFrameChanged.connect(self._on_video_frame)
            self._media_player.mediaStatusChanged.connect(self._on_media_status)

        # Pantalla completa
        cfg = self.backend.config
        # En Linux (X11/Wayland) un showFullScreen() pedido antes de que la
        # ventana quede mapeada puede perderse. _fullscreen_disabled solo se
        # activa si el usuario sale de fullscreen con F11; si el config lo
        # pide, _ensure_fullscreen lo reitera hasta que el WM lo confirme.
        # OJO: no usar showFullScreen() aqui porque mostraria la ventana
        # principal bajo el splash (y sin WM de startx quedaria encima).
        # Se deja el estado pedido y _close_splash la hace visible al final.
        self._fullscreen_disabled = not bool(cfg.get("fullscreen", True))
        if self._fullscreen_disabled:
            res = cfg.get("resolution", [1920, 1080])
            self.resize(res[0], res[1])
        else:
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)

        # Resolucion base: las coordenadas guardadas son relativas a ella y se
        # reescalan solas si la app corre en una pantalla de otro tamyear
        try:
            dlg_cfg = self._config_dialog.config()
        except Exception:
            dlg_cfg = {}
        base = dlg_cfg.get("base_resolution")
        if not (isinstance(base, list) and len(base) == 2):
            scr = QApplication.primaryScreen()
            size = scr.size() if scr else QSize(1920, 1080)
            base = [int(size.width()), int(size.height())]
            try:
                new_config = {**dlg_cfg, "base_resolution": base}
                self.backend.save_ui_config(json.dumps(new_config))
                self._config_dialog.load_config(new_config)
                print(f"[Escala] Resolucion base fijada en {base[0]}x{base[1]}")
            except Exception as e:
                print(f"[Escala] No se pudo guardar la resolucion base: {e}")
        self._resolucion_base = base
        # Reaplicar el layout ya con la resolucion base definitiva: al
        # construir la UI el base aun no estaba fijado y se usaron por
        # defecto; aqui se recalcula todo para la pantalla real.
        try:
            self._apply_layout(self._read_combined_layout())
            self._apply_video_config(self._effective_video())
        except Exception as e:
            print(f"[Escala] No se pudo reaplicar el layout: {e}")

        # Cargar datos
        QTimer.singleShot(200, self._init_data)

        # Al cambiar el idioma, retraducir la interfaz en vivo
        language_changed().connect(self._on_language_changed)

    def _on_language_changed(self, lang):
        """Retraduce la interfaz cuando cambia el idioma."""
        try:
            self.setWindowTitle(tr("Luna"))
        except Exception:
            pass
        for widget in (self.top_bar, self.bottom_bar, self.info_panel):
            rt = getattr(widget, "retranslate", None)
            if rt is not None:
                try:
                    rt()
                except Exception:
                    pass
        for dlg in (self._config_dialog, self._pos_admin, self._layout_editor, self._controls_dialog):
            if dlg is not None:
                rt = getattr(dlg, "retranslate", None)
                if rt is not None:
                    try:
                        rt()
                    except Exception:
                        pass
        # Persistir el idioma en ui_config.json
        try:
            ucfg = json.loads(self.backend.get_ui_config())
            if ucfg.get("language") != lang:
                ucfg["language"] = lang
                self.backend.save_ui_config(json.dumps(ucfg))
        except Exception:
            pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self._central = central
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        self.top_bar = TopBar()
        main_layout.addWidget(self.top_bar)

        # Contenido central
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Background (detras de todo) - parametros desde layout.json
        self.bg = BackgroundWidget(central)
        self._apply_background(LAYOUT.get("background", {}))

        # Panel info (izquierda)
        self.info_panel = InfoPanel()
        content_layout.addWidget(self.info_panel)
        # Realinear el video cuando el panel cambie de tamano/layout
        self.info_panel.installEventFilter(self)

        # Wheel (derecha) - parametros desde layout.json
        self.wheel = WheelWidget()
        self._apply_wheel(LAYOUT.get("wheel", {}))
        self.wheel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.wheel.selection_changed.connect(self._on_selection_changed)
        self.wheel.selection_enter.connect(self._on_enter)
        content_layout.addWidget(self.wheel, 1)

        main_layout.addWidget(content, 1)

        # Bottom bar
        self.bottom_bar = BottomBar()
        main_layout.addWidget(self.bottom_bar)

        # El fondo debe quedar SIEMPRE detras de la interfaz (rueda, paneles).
        # En Linux/X11 un widget translucido (WA_TranslucentBackground) puede
        # terminar por encima de sus hermanos; forzar el apilado lo evita.
        self.bg.lower()

        # Hot-reload de layout.json (para el editor en vivo)
        self._watch_layout()
        # Aplicar el layout inicial (global o de la plataforma por defecto)
        self._reload_layout()

    def _window_covers_screen(self):
        """True si la ventana ya ocupa realmente el monitor completo.

        No se usa isFullScreen() como prueba porque en sesiones startx sin
        window manager (o con WM que no implementa EWMH) Qt marca el estado
        como fullscreen aunque la ventana no se haya estirado de verdad.
        """
        if not self.isVisible():
            return False
        scr = self.screen() or QApplication.primaryScreen()
        if scr is None:
            return False
        geo = scr.geometry()
        if geo.width() <= 0 or geo.height() <= 0:
            return False
        return self.width() >= geo.width() and self.height() >= geo.height()

    def _ensure_fullscreen(self, attempts=12):
        """Reaplica pantalla completa hasta que la ventana la confirme.

        En Linux (X11/Wayland) el fullscreen pedido antes de que la ventana
        quede mapeada se pierde. Ademas, bajo startx sin window manager el
        estado _NET_WM_STATE_FULLSCREEN se ignora: se reintenta y, si la
        ventana sigue sin cubrir el monitor, se estira manualmente.
        """
        if getattr(self, "_fullscreen_disabled", False):
            return
        if getattr(self, "_fullscreen_fallback_active", False):
            return
        if self._window_covers_screen():
            return
        if attempts <= 0:
            self._apply_fullscreen_fallback()
            return
        self.showFullScreen()
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)
        QTimer.singleShot(150, lambda: self._ensure_fullscreen(attempts - 1))

    def _apply_fullscreen_fallback(self):
        """Simula pantalla completa sin soporte del window manager.

        En sesiones startx sin WM (o con WM minimo), el fullscreen por
        protocolo no se aplica: la ventana se estira exactamente a la
        geometria completa del monitor y se quita el borde de ventana.
        """
        if getattr(self, "_fullscreen_fallback_active", False):
            return
        scr = self.screen() or QApplication.primaryScreen()
        if scr is None:
            return
        geo = scr.geometry()
        if geo.width() <= 0 or geo.height() <= 0:
            return
        self._fullscreen_fallback_active = True
        if getattr(self, "_saved_released_geometry", None) is None:
            self._saved_released_geometry = QRect(self.geometry())
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setGeometry(geo)
        self.move(geo.x(), geo.y())
        self.show()
        self.raise_()
        self.activateWindow()
        print("[Fullscreen] WM sin fullscreen (startx): ventana estirada a la pantalla")

    def showEvent(self, event):
        super().showEvent(event)
        # Reafirmar tras el map de la ventana (y en cualquier re-show).
        if not getattr(self, "_fullscreen_disabled", False):
            QTimer.singleShot(0, self._ensure_fullscreen)

    def _apply_background(self, c):
        """Aplica la section background de layout.json al BackgroundWidget."""
        c = c or {}
        self.bg._blur_radius = c.get("blur", 12)
        self.bg._brightness = c.get("brightness", 0.25)
        self.bg._scale_factor = c.get("scale", 1.15)
        self.bg._vignette_h_alpha_edges = c.get("vignette_h_alpha_edges", 230)
        self.bg._vignette_h_alpha_center = c.get("vignette_h_alpha_center", 20)
        self.bg._vignette_v_alpha_edges = c.get("vignette_v_alpha_edges", 120)
        self.bg._vignette_v_alpha_center = c.get("vignette_v_alpha_center", 0)
        self.bg._rebuild_blurred()
        self.bg.update()

    # === Fondo por plataforma / snap como fondo ===

    def _bg_layout_override(self, sistema_id):
        """Seccion background del override de plataforma (layout_<id>.json)."""
        if not sistema_id:
            return {}
        over = self._read_json_safe(BASE_PATH / "layouts" / f"layout_{sistema_id}.json")
        return over.get("background") or {}

    def _resolve_image_path(self, path):
        """Ruta absoluta a un file_path existente, o '' si no existe."""
        if not path:
            return ""
        r = path if os.path.isabs(path) else str(BASE_PATH / path)
        return r if os.path.isfile(r) else ""

    def _active_global_background(self):
        """Entrada activa de la lista de fondos del config (dict or None).

        Migracion: configs viejos con fondo.imagen se tratan como lista
        de un elemento.
        """
        dialog = getattr(self, "_config_dialog", None)
        f = dialog.config().get("background", {}) if dialog else {}
        imgs = [e for e in (f.get("images") or [])
                if isinstance(e, dict) and e.get("path")]
        idx = f.get("active_image", -1)
        if not imgs and f.get("path"):
            imgs = [{"path": f.get("path", ""),
                     "stretch": bool(f.get("stretch", True)),
                     "brightness": 1.0}]
            idx = 0
        if isinstance(idx, int) and 0 <= idx < len(imgs):
            return imgs[idx]
        return None

    def _active_image_path_from(self, bg):
        """Extrae la ruta de la imagen activa de un dict de background."""
        if not isinstance(bg, dict):
            return ""
        imgs = bg.get("images") or []
        idx = bg.get("active_image", -1)
        if isinstance(idx, int) and 0 <= idx < len(imgs):
            e = imgs[idx]
            if isinstance(e, dict) and e.get("path"):
                return e["path"]
        # Fallback: campo legacy 'path'
        if bg.get("path"):
            return bg["path"]
        return ""

    def _global_background_path(self):
        """Imagen de fondo elegida desde el config (Shift); prioridad maxima."""
        e = self._active_global_background()
        return self._resolve_image_path(e.get("path", "")) if e else ""

    def _platform_background_path(self, cat):
        """Imagen de fondo configurada para una plataforma.

        En la seleccion de plataformas (mode categorias) se usa config.json
        (emuladores[].bg_image) y el fondo del config, dejando intacta la
        imagen de la tarjeta de plataforma.

        Una vez dentro de la plataforma (mode roms), la imagen del layout de
        esa plataforma (layout_<sistema>.json, campo 'image'/'path') tiene
        prioridad sobre el resto.

        Prioridad en mode roms:
        fondo del layout de la plataforma > bg_image de config.json >
        fondo per-plataforma del config (Shift) > imagen global del config.
        Retorna '' si no hay.
        """
        if not isinstance(cat, dict):
            return ""
        sys_id = cat.get("id", "")
        layout_img = ""
        if getattr(self, "_mode", "") == "roms":
            over = self._read_json_safe(BASE_PATH / "layouts" / f"layout_{sys_id}.json")
            bg = over.get("background") or {}
            layout_img = self._resolve_image_path(
                bg.get("path", "") or bg.get("image", "")
            )
            if not layout_img:
                apl = (getattr(self, "_layout_aplicado", {}) or {}).get("background") or {}
                layout_img = self._resolve_image_path(
                    apl.get("path", "") or apl.get("image", "")
                )
            if not layout_img:
                glob = self._read_json_safe(BASE_PATH / "layouts" / "layout.json").get("background") or {}
                layout_img = self._resolve_image_path(
                    glob.get("path", "") or glob.get("image", "")
                )
        path = layout_img
        if not path:
            path = self._resolve_image_path(cat.get("bg_image", ""))
        if not path:
            # Fondo per-plataforma del config (Shift)
            dialog = getattr(self, "_config_dialog", None)
            if dialog and sys_id:
                pb = dialog.config().get("platform_backgrounds", {}).get(sys_id, {})
                path = self._resolve_image_path(
                    self._active_image_path_from(pb) or ""
                )
        if not path:
            path = self._global_background_path()
        return path

    def _set_platform_background(self, cat, fallback_wheel=True):
        """Aplica el fondo configurado de la plataforma al BackgroundWidget.

        Si no hay imagen configurada y fallback_wheel, usa la imagen wheel
        (comportamiento original). Retorna True si se aplico alguna imagen.
        """
        path = self._platform_background_path(cat)
        if path:
            self.bg.set_image(path)
            return True
        if fallback_wheel and isinstance(cat, dict) and cat.get("wheel_img"):
            self.bg.set_image(cat["wheel_img"])
            return True
        return False

    def _use_snap_as_background(self):
        """Mostrar el snap del ROM como fondo.

        Prioridad: layout_<sistema>.json > layout.json (global) >
        config Shift (fondo.use_snap) > True.
        """
        dialog = getattr(self, "_config_dialog", None)
        glob = dialog.config().get("background", {}) if dialog else {}
        sid = getattr(self, "_current_system", "") or ""
        over = self._bg_layout_override(sid)
        if "use_snap" in over:
            return bool(over.get("use_snap"))
        aplicado = (getattr(self, "_layout_aplicado", {}) or {}).get("background") or {}
        if "use_snap" in aplicado:
            return bool(aplicado.get("use_snap"))
        return bool(glob.get("use_snap", True))

    def _background_rom_mode(self, rom):
        """Fondo en mode ROMs segun 'Fondo en juegos' del config (Shift):
        snap del juego (si tiene) o el fondo de la plataforma activa
        (propio > imagen global como fallback); sin nada configurado
        conserva el actual.

        Si la plataforma tiene bg_image configurado, siempre se usa
        como fondo y no se reemplaza por el snap."""
        if self._set_platform_background(self._current_category, fallback_wheel=False):
            return
        if self._use_snap_as_background():
            image_path = self._image_from_snap(rom.get("snap", ""))
            if image_path:
                self.bg.set_image(image_path)
                return
        self._set_platform_background(self._current_category, fallback_wheel=True)

    def _apply_background_config(self, f):
        """Aplica mode de ajuste/brillo de la imagen activa y refresca."""
        f = f or {}
        e = self._active_global_background()
        if e:
            self.bg.set_stretch(bool(e.get("stretch", True)))
            self.bg.set_brightness(float(e.get("brightness", 1.0)))
            path = self._resolve_image_path(e.get("path", ""))
            if path:
                self.bg.set_image(path)
        else:
            # Sin imagen activa: ajuste cover y el brillo global del config
            self.bg.set_stretch(False)
            self.bg.set_brightness(float(f.get("brightness", 0.25)))
        if hasattr(self, "wheel"):
            self._refresh_current_item_background()

    def _refresh_current_item_background(self):
        """Recalcula el fondo del item seleccionado sin tocar el video."""
        item = self.wheel.current_item()
        if not item:
            return
        if self._mode == "categorias":
            self._set_platform_background(item.meta)
        else:
            self._background_rom_mode(item.meta)

    def _apply_wheel(self, c):
        """Aplica la section wheel de layout.json al WheelWidget."""
        c = self._scaled_section("wheel", c)
        w = self.wheel
        w.visible_items = c.get("visible_items", 13)
        w.radius = c.get("radius", 320)
        w.angular_separation = c.get("angular_separation", 8.0)
        w.central_scale = c.get("central_scale", 1.4)
        w.min_scale = c.get("min_scale", 0.3)
        w.selection_scale = c.get("selection_scale", 1.35)
        w.image_height_percent = c.get("image_height_percent", 0.9)
        w.item_width = c.get("item_width", 300)
        w.item_height = c.get("item_height", 70)
        w.selected_color = QColor(c.get("selected_color", "#ff6600"))
        w.text_color = QColor(c.get("text_color", "#ffffff"))
        w.accent_color = QColor(c.get("accent_color", "#00ccff"))
        w.base_x_percent = c.get("base_x_percent", 0.15)
        w.pull_in_x = c.get("pull_in_x", 25)
        w.line_x_start_percent = c.get("line_x_start_percent", 0.08)
        w.line_x_end_percent = c.get("line_x_end_percent", 0.78)
        w.indicator_x_percent = c.get("indicator_x_percent", 0.03)
        w.indicator_y_percent = c.get("indicator_y_percent", 0.5)
        w.indicator_size = c.get("indicator_size", 12)
        w.font_size_selected = c.get("font_size_selected", 17)
        w.font_size_normal = c.get("font_size_normal", 15)
        w.font_min_size = c.get("font_min_size", 8)
        w.selected_opacity = c.get("selected_opacity", 1.0)
        w.normal_opacity = c.get("normal_opacity", 0.2)
        w._scroll_timer.setInterval(c.get("scroll_tick_ms", 16))
        w.scroll_max_steps = c.get("scroll_max_steps", 3)
        w.anim_duration = c.get("anim_duration", 240)
        w.anim_max_duration = c.get("anim_max_duration", 650)
        w.anim_easing = WheelWidget.parse_easing(c.get("anim_easing", "out_cubic"))
        w.update()

    # === Hot-reload del layout ===

    def _watch_layout(self):
        self._layout_watcher = QFileSystemWatcher(self)
        paths = [str(BASE_PATH / "layouts" / "layout.json")]
        # Overlays por plataforma: layout_mame.json, layout_nes.json, ...
        paths += [str(p) for p in sorted(BASE_PATH.glob("layouts/layout_*.json"))]
        existentes = [r for r in paths if os.path.isfile(r)]
        if existentes:
            self._layout_watcher.addPaths(existentes)
            self._layout_watcher.fileChanged.connect(self._on_layout_changed)

    def _on_layout_changed(self, path):
        # Algunos editores reemplazan el file_path al guardar: re-vigilarlo
        if os.path.isfile(path) and path not in self._layout_watcher.files():
            self._layout_watcher.addPath(path)
        QTimer.singleShot(250, self._reload_layout)

    def _read_json_safe(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _read_combined_layout(self):
        """layout.json + overrides de la plataforma activa (layout_<id>.json)."""
        base = self._read_json_safe(BASE_PATH / "layouts" / "layout.json")
        # El video global vive en ui_config.json: ignorar la section del base
        # para que solo un override de plataforma pueda pisarla.
        base.pop("video", None)
        system = getattr(self, "_current_system", None)
        if system:
            over = self._read_json_safe(BASE_PATH / "layouts" / f"layout_{system}.json")
            for section, values in over.items():
                if isinstance(values, dict) and isinstance(base.get(section), dict):
                    base[section] = {**base[section], **values}
                else:
                    base[section] = values
        return base

    # Campos de layout en pixeles que se escalan con el tamano de la ventana
    _SCALE_X = {"x", "w", "width", "item_width", "pull_in_x"}
    _SCALE_Y = {"y", "h", "height", "radius", "item_height", "logo_height",
                "logo_max_height", "snap_height", "indicator_size"}
    _SCALE_FONT = {"font_size_selected", "font_size_normal", "font_min_size",
                   "name_font_size", "stats_font_size", "emulator_font_size",
                   "info_font_size", "hint_font_size", "title_font_size",
                   "snap_radius"}

    # Valores por defecto (resolucion base) de cada seccion escalable, para que
    # aunque layout.json no defina la seccion se escale bien al resize.
    _LAYOUT_PRESETS = {
        "wheel": {
            "visible_items": 13, "radius": 320, "angular_separation": 8.0,
            "central_scale": 1.4, "min_scale": 0.3, "selection_scale": 1.35,
            "image_height_percent": 0.9, "item_width": 300, "item_height": 70,
            "base_x_percent": 0.15, "pull_in_x": 25,
            "line_x_start_percent": 0.08, "line_x_end_percent": 0.78,
            "indicator_x_percent": 0.03, "indicator_y_percent": 0.5,
            "indicator_size": 12, "font_size_selected": 17,
            "font_size_normal": 15, "font_min_size": 8,
            "selected_opacity": 1.0, "normal_opacity": 0.2,
            "scroll_tick_ms": 16, "scroll_max_steps": 3,
        },
        "top_bar": {
            "height": 55, "title_font_size": 18, "info_font_size": 12,
        },
        "bottom_bar": {
            "height": 40, "hint_font_size": 12,
        },
        "info_panel": {
            "width": 350, "logo_height": 80, "logo_max_height": 70,
            "name_font_size": 22, "stats_font_size": 14,
            "emulator_font_size": 12, "info_font_size": 12,
            "snap_height": 200, "snap_radius": 6,
        },
    }

    def _scaled_section(self, name, cfg):
        """Seccion de layout con sus por defecto mezclados y escalados al
        tamano actual de la ventana (valores=resolucion base)."""
        presets = self._LAYOUT_PRESETS.get(name, {})
        return self._scale_section({**presets, **(cfg or {})})

    def _scale_section(self, section):
        """Escala los campos en pixeles de una seccion de layout a la pantalla
        actual (los valores se interpretan en resolucion base)."""
        if not isinstance(section, dict):
            return section
        fx, fy = self._scale_factors()
        out = {}
        for k, v in section.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                out[k] = v
            elif k in self._SCALE_X:
                out[k] = v * fx
            elif k in self._SCALE_Y or k in self._SCALE_FONT:
                out[k] = v * fy
            else:
                out[k] = v
        return out

    def _scale_factors(self):
        """Factor de escala (x, y) entre la resolucion REAL del monitor y la base.

        Se calcula contra el tamano de la pantalla donde esta la ventana
        (no contra el tamano actual de la ventana), de modo que todo el
        frontend se ajuste automaticamente a la resolucion del monitor
        tanto en Windows como en Linux, sea cual sea el screen (fila de
        pantalla completa incluida), aunque la ventana aun no este mapeada.
        """
        base = getattr(self, "_resolucion_base", None)
        if not (isinstance(base, list) and len(base) == 2 and base[0] and base[1]):
            bw, bh = 1920, 1080
        else:
            bw, bh = base
        scr = self.screen()
        if scr is None:
            scr = QApplication.primaryScreen()
        if scr is None:
            cw, ch = 1920, 1080
        else:
            geom = scr.geometry()
            if geom.width() <= 0 or geom.height() <= 0:
                cw, ch = 1920, 1080
            else:
                cw, ch = geom.width(), geom.height()
        return max(cw / float(bw), 0.01), max(ch / float(bh), 0.01)

    def _rect_stored_to_real(self, d):
        """Coordenadas guardadas -> pixeles reales de esta pantalla."""
        if not isinstance(d, dict) or not d:
            return d
        fx, fy = self._scale_factors()
        r = dict(d)
        for k, f in (("x", fx), ("y", fy), ("w", fx), ("h", fy)):
            if k in r:
                r[k] = round(r[k] * f)
        return r

    def _rect_real_to_stored(self, d):
        """Pixeles reales -> coordenadas relativas a la resolucion base."""
        if not isinstance(d, dict) or not d:
            return d
        fx, fy = self._scale_factors()
        r = dict(d)
        for k, f in (("x", fx), ("y", fy), ("w", fx), ("h", fy)):
            if k in r and f > 0:
                r[k] = round(r[k] / f)
        return r

    def _effective_video(self):
        """Config de video (plataforma > global) en pixeles reales."""
        glob = self._config_dialog.config().get("video", {})
        lay_v = (getattr(self, "_layout_aplicado", {}) or {}).get("video")
        if isinstance(lay_v, dict) and lay_v:
            v = {**glob, **lay_v}
        else:
            v = dict(glob)
        return self._rect_stored_to_real(v)

    def _set_video_in_memory(self, v):
        """Mantiene la config global en memoria sincronizada con el admin."""
        try:
            self._config_dialog.set_video(v)
        except Exception as e:
            print(f"[Video] Error al sincronizar config: {e}")

    # === Snap configurable ===

    def _effective_snap(self):
        """Posicion del snap (plataforma > global) en pixeles reales."""
        dialog = getattr(self, "_config_dialog", None)
        glob = dialog.config().get("snap_pos", {}) if dialog else {}
        lay_s = (getattr(self, "_layout_aplicado", {}) or {}).get("snap_pos")
        if isinstance(lay_s, dict) and lay_s:
            s = {**glob, **lay_s}
        else:
            s = dict(glob)
        return self._rect_stored_to_real(s)

    def _set_snap_in_memory(self, v):
        try:
            self._config_dialog.set_section("snap_pos", v)
        except Exception as e:
            print(f"[Snap] Error al sincronizar config: {e}")

    def _apply_snap_config(self, s=None):
        """Coloca el snap en posicion libre (custom) o lo devuelve al panel."""
        if not hasattr(self, "info_panel") or not hasattr(self.info_panel, "lbl_snap"):
            return
        if self._mode == "categorias":
            self.info_panel.lbl_snap.hide()
            return
        if s is None:
            s = self._effective_snap()
        caja = self.info_panel.lbl_snap
        custom = bool(s.get("custom")) and all(
            k in s for k in ("x", "y", "w", "h")
        )
        if custom:
            if caja.parent() is not self._central:
                lay = self.info_panel.layout()
                for i in range(lay.count()):
                    it = lay.itemAt(i)
                    if it and it.widget() is caja:
                        self._snap_idx_original = i
                        break
                lay.removeWidget(caja)
                caja.setParent(self._central)
            caja.setMinimumSize(0, 0)
            caja.setMaximumSize(16777215, 16777215)
            caja.setGeometry(int(s["x"]), int(s["y"]), int(s["w"]), int(s["h"]))
            caja.show()
            caja.raise_()
        else:
            if caja.parent() is not self.info_panel:
                lay = self.info_panel.layout()
                idx = min(getattr(self, "_snap_idx_original", lay.count()), lay.count())
                lay.insertWidget(idx, caja)
                height = ((getattr(self, "_layout_aplicado", {}) or {})
                        .get("info_panel", {}).get("snap_height", 200))
                caja.setFixedHeight(int(height))
                caja.show()
        self._update_video_position()

    def _reload_layout(self):
        new_layout = self._read_combined_layout()
        print("[Layout] Cambios aplicados en vivo")
        self._apply_layout(new_layout)
        if getattr(self, "_layout_editor", None) and self._layout_editor.isVisible():
            self._layout_editor.sync_external()

    def _toggle_positions_admin(self):
        """Abre/cierra el administrador de posiciones (rueda, info, video)."""
        if self._pos_admin is None:
            self._pos_admin = PosicionesAdmin(
                self,
                load_ui_fn=lambda: json.loads(self.backend.get_ui_config()),
                save_ui_fn=lambda cfg: self.backend.save_ui_config(json.dumps(cfg)),
            )
            self._nav.register(self._pos_admin)
        if self._pos_admin.isVisible():
            self._pos_admin.hide()
        else:
            self._pos_admin.show_next_to(self)
            self.top_bar.lbl_info.setText(tr("Admin de posiciones activo"))

    def _toggle_layout_editor(self):
        """Abre/cierra el editor visual de layout con aplicacion en vivo."""
        if self._layout_editor is None:
            self._layout_editor = LayoutEditor(str(BASE_PATH / "layouts" / "layout.json"))
            self._nav.register(self._layout_editor)
        if self._layout_editor.isVisible():
            self._layout_editor.hide()
        else:
            self._layout_editor.show_next_to(self)
            self.top_bar.lbl_info.setText(tr("Editor de layout activo"))

    def _apply_layout(self, cfg):
        self._layout_aplicado = cfg
        self._apply_background(cfg.get("background", {}))
        self._apply_wheel(cfg.get("wheel", {}))
        self.top_bar.apply(self._scaled_section("top_bar", cfg.get("top_bar", {})))
        self.bottom_bar.apply(self._scaled_section("bottom_bar", cfg.get("bottom_bar", {})))
        self.info_panel.apply(self._scaled_section("info_panel", cfg.get("info_panel", {})))
        self._apply_images(cfg.get("images"))
        self._apply_snap_config()
        self.bg.setGeometry(self.rect())
        self._update_video_position()

    # === Imagenes personalizadas ===

    def _resolve_project_path(self, path):
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return str(BASE_PATH / path)

    def _apply_images(self, images):
        """Crea los overlays de imagen personalizados (posicion y escala).

        z >= 1: la imagen se coloca sobre el video (hija de la ventana).
        z <= 0: queda bajo la interfaz (hija del widget central).
        """
        for lbl in getattr(self, "_img_datos", []) or []:
            lbl[0].deleteLater()
        self._img_datos = []
        for cfg in (images or []):
            path = self._resolve_project_path(cfg.get("path", ""))
            if not path or not os.path.isfile(path):
                continue
            img = QImage(path)
            if img.isNull():
                continue
            pm = QPixmap.fromImage(img)
            z = int(cfg.get("z", 0))
            fx, fy = self._scale_factors()
            parent = self if z > 0 else self._central
            lbl = QLabel(parent)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lbl.setStyleSheet("background: transparent;")
            lbl.setProperty("z_alto", z > 0)
            lbl.setProperty("z_valor", z)
            # coordenadas guardadas -> pixeles reales de esta pantalla
            lbl.move(round(cfg.get("x", 0) * fx), round(cfg.get("y", 0) * fy))
            lbl.setPixmap(pm)
            self._scale_image(lbl, pm, float(cfg.get("scale", 1.0)) * fy)
            lbl.show()
            if z > 0:
                lbl.raise_()
            else:
                lbl.stackUnder(self.top_bar)
            self._img_datos.append([lbl, pm])
        self._reorder_layers()

    def _reorder_layers(self):
        """Apila video e imagenes flotantes por su Capa Z (empate: imagen encima)."""
        pares = []
        vw = getattr(self, "_video_widget", None)
        if vw is not None and not vw.isHidden():
            zv = max(int(getattr(self, "_video_z", 0) or 0), 1)
            pares.append((zv, 0, vw))
        for lbl, _pm in getattr(self, "_img_datos", []) or []:
            zi = int(lbl.property("z_valor") or 0)
            if zi > 0 and lbl.parent() is self:
                pares.append((zi, 1, lbl))
        for _z, _prio, wdgt in sorted(pares, key=lambda t: (t[0], t[1])):
            wdgt.raise_()

    def _scale_image(self, lbl, pm_orig, scale):
        if abs(scale - 1.0) > 0.001 and pm_orig.width() > 0:
            pm = pm_orig.scaled(
                max(1, int(pm_orig.width() * scale)),
                max(1, int(pm_orig.height() * scale)),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            lbl.setPixmap(pm)
        else:
            lbl.setPixmap(pm_orig)
        # QLabel no se redimensiona solo: ajustar al tamano del pixmap
        if lbl.pixmap() and not lbl.pixmap().isNull():
            lbl.resize(lbl.pixmap().size())

    def _update_image(self, idx, x=None, y=None, scale=None, z=None):
        """Actualiza en vivo una imagen sin esperar el hot-reload."""
        datos = getattr(self, "_img_datos", [])
        if not (0 <= idx < len(datos)):
            return
        lbl, pm = datos[idx]
        if x is not None:
            lbl.move(int(x), lbl.y())
        if y is not None:
            lbl.move(lbl.x(), int(y))
        if scale is not None:
            self._scale_image(lbl, pm, float(scale))
        if z is not None:
            height = int(z) > 0
            parent = self if height else self._central
            if lbl.parent() is not parent:
                # Ambos padres ocupan el rect completo: mismas coordenadas
                lbl.setParent(parent)
                lbl.show()
            lbl.setProperty("z_alto", height)
            lbl.setProperty("z_valor", int(z))
            if height:
                lbl.raise_()
                self._reorder_layers()
            else:
                lbl.stackUnder(self.top_bar)

    def eventFilter(self, obj, event):
        """Mantiene el video alineado al snap ante cambios de layout del panel."""
        if obj is self.info_panel and event.type() in (QEvent.Resize, QEvent.LayoutRequest):
            if (self._video_widget and not self._video_widget.isHidden()
                    and not self._effective_video().get("fixed", False)):
                self._align_video_to_snap()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposicionar background
        self.bg.setGeometry(self.rect())
        # Reescalar rueda, paneles, video, snap e imagenes al nuevo tamano
        if getattr(self, "_resolucion_base", None):
            lay = getattr(self, "_layout_aplicado", None)
            if isinstance(lay, dict):
                self._apply_wheel(lay.get("wheel", {}))
                if hasattr(self, "top_bar"):
                    self.top_bar.apply(self._scaled_section("top_bar", lay.get("top_bar", {})))
                    self.bottom_bar.apply(self._scaled_section("bottom_bar", lay.get("bottom_bar", {})))
                    self.info_panel.apply(self._scaled_section("info_panel", lay.get("info_panel", {})))
            v = self._effective_video()
            if isinstance(v, dict) and v:
                self._apply_video_config(v)
            if hasattr(self, "info_panel"):
                self._apply_snap_config()
            lay = getattr(self, "_layout_aplicado", None)
            if isinstance(lay, dict) and lay.get("images"):
                self._apply_images(lay["images"])
        # Reposicionar video widget
        self._update_video_position()

    def paintEvent(self, event):
        # El background se dibuja detras de todo
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        painter.end()
        super().paintEvent(event)

    def _update_video_position(self):
        vw = getattr(self, "_video_widget", None)
        if not vw or vw.isHidden():
            return
        v = self._effective_video()
        if v.get("fixed", False):
            vw.setGeometry(v["x"], v["y"], v["w"], v["h"])
        else:
            self._align_video_to_snap()

    def _align_video_to_snap(self):
        """Coloca el video exactamente sobre el area del snap (coords de ventana)."""
        caja = self.info_panel.lbl_snap
        esquina = caja.mapTo(self, QPoint(0, 0))
        self._video_widget.setGeometry(
            esquina.x(), esquina.y(), caja.width(), caja.height()
        )

    # === Datos ===

    def _init_data(self):
        """Carga datos iniciales desde el backend (con mensajes al splash)."""
        self._splash_msg("Verificando emulatores...", 68)
        try:
            self.backend.check_emulators()
        except Exception as e:
            print(f"[Error] check_emulators: {e}")

        self._load_categories()

    def _load_categories(self):
        """Escaneo en hilo aparte: cache rapida o generacion de file_paths base."""
        hay_cache = any((BASE_PATH / "romslist").glob("*.json"))
        if hay_cache:
            self._splash_msg("Cargando ROMs...", 80)
        else:
            self._splash_msg("Primer inicio: generando file_paths base...", 76)
        worker = ScanWorker(self.backend)
        worker.signals.done.connect(self._on_categories_ready)
        self._scan_pool.start(worker)

    def _on_categories_ready(self, raw):
        """Resultado del escaneo: poblar la rueda y retirar el splash."""
        try:
            data = json.loads(raw)
            self._categories = data.get("categories", [])
            self._populate_wheel_categorias()
            total = data.get("total_roms", 0)
            self.top_bar.lbl_info.setText(tr("{n} ROMs disponibles", n=total))
        except Exception as e:
            print(f"[Error] escanear: {e}")
            self.top_bar.lbl_info.setText(tr("Error al escanear ROMs"))
        self._close_splash()

    def _close_splash(self):
        """Retira el splash (overlay de la ventana principal).

        El splash ya vive dentro de la ventana; al terminar simplemente se
        cierra / se retira y se reafirma el fullscreen y el foco.
        """
        if not self._splash:
            return
        splash, self._splash = self._splash, None
        splash.closed.connect(self._show_after_splash)
        splash.close()
        # Red de seguridad por si la senal no llega (p.ej. splash eliminado)
        QTimer.singleShot(1200, self._show_after_splash)

    def attach_splash(self, splash):
        """Incrusta el splash como overlay que cubre esta ventana."""
        self._splash = splash or self._splash
        if self._splash:
            self._splash.attach_to(self)

    def _show_after_splash(self):
        # El splash ya termino: asegurar fullscreen y devolver el foco a la
        # rueda de la interfaz principal.
        if not getattr(self, "_fullscreen_disabled", False):
            self._ensure_fullscreen()
        self.raise_()
        self.activateWindow()
        if self.wheel is not None:
            self.wheel.setFocus()
        print("[OK] Ventana principal lista")

    def _splash_msg(self, text, progress=None):
        if not self._splash:
            return
        self._splash.set_message(text)
        if progress is not None:
            self._splash.set_progress(progress)

    def _populate_wheel_categorias(self):
        items = []
        sorted_cats = sorted(self._categories, key=lambda c: c.get("name", "").lower())
        for i, cat in enumerate(sorted_cats):
            img = cat.get("wheel_img", "")
            items.append(WheelItem(i, cat.get("name", ""), img, meta=cat))
        self.wheel.set_items(items)
        if items:
            # Restaurar la plataforma seleccionada antes de entrar a una
            # categoria (si sigue existiendo).
            idx = 0
            last_id = getattr(self, "_last_category_id", "") or ""
            if last_id:
                for i, item in enumerate(items):
                    if (item.meta or {}).get("id") == last_id:
                        idx = i
                        break
            self.wheel.select_index(idx)

    def _populate_wheel_roms(self, roms):
        items = []
        sorted_roms = sorted(roms, key=lambda r: r.get("name", "").lower())
        for i, rom in enumerate(sorted_roms):
            img = rom.get("image", "")
            items.append(WheelItem(i, rom.get("name", ""), img, meta=rom))
        self.wheel.set_items(items)
        if items:
            # Restaurar el ultimo juego seleccionado en esta plataforma
            # (si sigue existiendo).
            idx = 0
            last_key = self._last_rom_ids.get(self._current_system or "", "") or ""
            if last_key:
                for i, item in enumerate(items):
                    if (item.meta or {}).get("file_path") == last_key:
                        idx = i
                        break
            self.wheel.select_index(idx)
            self._on_selection_changed(items[idx])

    # === Navegacion ===

    def _on_selection_changed(self, item):
        if not item:
            return
        if self._mode == "categorias":
            cat = item.meta
            self._stop_video()
            self.info_panel.set_category(cat)
            self.top_bar.lbl_info.setText(tr("{n} ROMs", n=cat.get('total_roms', 0)))
            # Fondo de la plataforma (configurable; fallback: imagen wheel)
            self._set_platform_background(cat)
        else:
            rom = item.meta
            self.info_panel.set_rom(rom)
            self._show_snap(rom.get("snap", ""))
            # Fondo: snap del juego (si la opcion lo permite) o el de la plataforma
            self._background_rom_mode(rom)
            # Pedir info scrapeada (async, con cache)
            self._request_game_info(rom)

    def _image_from_snap(self, snap):
        """Ruta de imagen para el fondo: el propio snap si es imagen,
        o el file_path gemelo con el mismo name cuando el snap es video."""
        if not snap:
            return ""
        ext = os.path.splitext(snap)[1].lower()
        if ext not in (".mp4", ".avi", ".mkv", ".webm", ".mov"):
            return snap if os.path.isfile(snap) else ""
        base = os.path.splitext(snap)[0]
        for candidate in (
            base + ".png", base + ".jpg", base + ".jpeg",
            base + ".webp", base + ".bmp",
            base.lower() + ".png", base.lower() + ".jpg",
        ):
            if os.path.isfile(candidate):
                return candidate
        return ""

    def _request_game_info(self, rom):
        file_path = rom.get("file_path", "")
        if not file_path or rom.get("emulator", "") == "":
            return
        if rom.get("_info_scraped") or rom.get("_scrape_pendiente"):
            return
        rom["_scrape_pendiente"] = True
        if not rom.get("_info_scraped"):
            self.info_panel.lbl_info.setText(tr("Buscando info..."))
        worker = ScrapeWorker(file_path, rom.get("name", ""), rom.get("emulator", ""))
        worker.signals.info_ready.connect(self._on_scrape_ready)
        self._scrape_pool.start(worker)

    def _on_scrape_ready(self, file_path, data):
        rom = next((r for r in self._current_roms if r.get("file_path") == file_path), None)
        if rom is None:
            return
        rom["_scrape_pendiente"] = False
        if data:
            rom.update(data)
            rom["_info_scraped"] = True
        # Refrescar panel solo si esa ROM sigue seleccionada
        item = self.wheel.current_item()
        if item and item.meta.get("file_path") == file_path:
            self.info_panel.set_rom(item.meta)

    def _on_enter(self, item):
        if not item:
            return
        if self._mode == "categorias":
            self._enter_category(item.meta)
        else:
            self._launch_rom(item.meta)

    def _enter_category(self, cat):
        self._mode = "roms"
        self._current_category = cat
        self._current_system = cat.get("id", "")
        self._last_category_id = cat.get("id", "")
        roms = cat.get("roms", [])
        self._current_roms = roms
        self.bottom_bar.set_mode("roms", self._controls)
        self.info_panel.lbl_snap.hide()
        # Aplicar primero el layout propio de esta plataforma (si existe
        # override) para que fondo/usar_snap valgan desde el primer item
        self._apply_layout(self._read_combined_layout())
        self._apply_video_config(self._effective_video())
        # Fondo inicial: el configurado para esta plataforma
        self._set_platform_background(cat, fallback_wheel=False)
        self._populate_wheel_roms(roms)
        self.top_bar.lbl_info.setText(tr("Plataforma: {nombre}", nombre=cat.get('name', '')))
        if self._pos_admin and self._pos_admin.isVisible():
            self._pos_admin.refresh()

    def _back_to_categories(self):
        # Recordar el ultimo juego de esta plataforma antes de salir de ella
        if self._current_system and self._current_roms:
            item = self.wheel.current_item()
            if item and item.meta:
                self._last_rom_ids[self._current_system] = item.meta.get("file_path", "")
        self._mode = "categorias"
        self._current_category = None
        self._current_system = None
        self._current_roms = []
        self._stop_video()
        self.info_panel.lbl_snap.hide()
        self.info_panel.lbl_snap.clear()
        # Limpiar el fondo ANTES de poblar: al poblar, el primer item ya
        # fija su fondo (si se hace despues, queda la pantalla sin imagen)
        self.bg.clear()
        self._populate_wheel_categorias()
        self.bottom_bar.set_mode("categorias", self._controls)
        # Volver al layout global
        self._apply_layout(self._read_combined_layout())
        self._apply_video_config(self._effective_video())
        if self._pos_admin and self._pos_admin.isVisible():
            self._pos_admin.refresh()

    def _launch_rom(self, rom):
        file_path = rom.get("file_path", "")
        emulator = rom.get("emulator", "")
        if not file_path:
            return
        # Detener el snap de video antes de ejecutar el juego
        self._stop_video()
        self.info_panel.lbl_snap.hide()
        self.top_bar.lbl_info.setText(tr("Lanzando: {nombre}...", nombre=rom.get('name', '')))
        try:
            result = self.backend.launch_rom(file_path, emulator)
            r = json.loads(result)
            if r.get("success"):
                self._emulator_active = True
                self.wheel.setEnabled(False)
                self.top_bar.lbl_info.setText(tr("Emulador en ejecucion..."))
            else:
                self.top_bar.lbl_info.setText(tr("Error: {m}", m=r.get('error', tr("Desconocido"))))
        except Exception as e:
            self.top_bar.lbl_info.setText(tr("Error: {m}", m=e))

    # === Video ===

    def _show_snap(self, path):
        if not path:
            self._stop_video()
            self.info_panel.lbl_snap.show()
            self.info_panel.lbl_snap.setText(tr("SIN SNAP"))
            return

        ext = path.split(".")[-1].lower() if "." in path else ""
        video_exts = {"mp4", "avi", "mkv", "webm", "mov"}

        if ext in video_exts:
            if os.path.isfile(path):
                # Solo video: ocultar la caja del snap para que no se vea imagen
                self.info_panel.lbl_snap.hide()
                self.play_video(path)
            else:
                self.info_panel.lbl_snap.show()
                self.info_panel.lbl_snap.setText(tr("SIN SNAP"))
        else:
            self._stop_video()
            if os.path.isfile(path):
                img = QImage(path)
                if not img.isNull():
                    scaled = img.scaled(
                        self.info_panel.lbl_snap.size(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.info_panel.lbl_snap.setPixmap(QPixmap.fromImage(scaled))
                    self.info_panel.lbl_snap.show()
            else:
                self.info_panel.lbl_snap.show()
                self.info_panel.lbl_snap.setText(tr("SIN SNAP"))

    def _setup_audio_device(self):
        """Configura el dispositivo de audio del reproductor de previews.

        En Debian/Linux Qt a veces no detecta la salida de audio (faltan los
        plugins o no hay PulseAudio/PipeWire): se asigna la salida por defecto
        (o la primera disponible) y se loguea el estado para diagnosticar
        desde crashes.log sin tener la consola a la vista.
        """
        try:
            outs = QMediaDevices.audioOutputs()
            default = QMediaDevices.defaultAudioOutput()
            desc = default.description() if (default and not default.isNull()) else "NINGUNA"
            print(f"[Audio] Salidas detectadas: {len(outs)} - por defecto: {desc}")
            if default is not None and not default.isNull():
                self._audio_output.setDevice(default)
            elif outs:
                self._audio_output.setDevice(outs[0])
            self._audio_output.setVolume(1.0)
        except Exception as e:
            print(f"[Audio] No se pudo configurar el dispositivo: {e}")

    def play_video(self, path):
        if not self._media_player or not self._video_widget:
            return
        v = self._effective_video()
        if v.get("fixed", False):
            self._video_widget.setGeometry(v["x"], v["y"], v["w"], v["h"])
        else:
            # La caja del snap queda visible (estable) y el video la cubre
            self._align_video_to_snap()
        self._media_player.setSource(QUrl.fromLocalFile(path))
        self._media_player.play()
        self._video_widget.show()
        self._reorder_layers()

    def _stop_video(self):
        if self._media_player:
            self._media_player.stop()
        if self._video_widget:
            self._video_widget.hide()

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._media_player.setPosition(0)
            self._media_player.play()

    def _on_video_frame(self, frame):
        if not self._video_widget.isHidden():
            self._video_widget.setFrame(frame)

    # === Config ===

    def _toggle_config(self):
        if self._config_open:
            # close() dispara config_closed -> _on_config_closed
            self._config_dialog.close()
        else:
            # Cargar config actual
            try:
                raw = self.backend.get_ui_config()
                cfg = json.loads(raw)
                # Pass platform context for per-platform backgrounds
                self._config_dialog.set_platform(self._current_system)
                self._config_dialog.load_config(cfg)
            except Exception as e:
                print(f"[Config] Error al cargar: {e}")
            self._config_open = True
            self._config_dialog.show()
            self._config_dialog.raise_()

    def _on_config_closed(self):
        """El administrador de config se cerro (ESC, X o Guardar)."""
        self._config_open = False
        self._hide_video_preview()
        if not self._emulator_active:
            self.wheel.setFocus()

    def _hide_video_preview(self):
        """Oculta el rectangulo de previsualizacion si nada se esta reproduciendo."""
        if not self._video_widget or self._video_widget.isHidden():
            return
        reproduciendo = bool(
            self._media_player
            and self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )
        if not reproduciendo:
            self._video_widget.hide()

    def _on_config_live(self, config):
        """Aplicar config en vivo."""
        # Colores
        c = config.get("colors", {})
        palette = self.palette()
        if c.get("background"):
            palette.setColor(QPalette.Window, QColor(c["background"]))
        self.setPalette(palette)

        # Fondo: solo aplicar ajustes globales cuando NO estamos en modo plataforma
        dialog = getattr(self, "_config_dialog", None)
        en_plataforma = dialog is not None and dialog._platform_id is not None
        f = config.get("background", {})
        if not en_plataforma:
            if f.get("blur"):
                self.bg.set_blur(f["blur"])
            if f.get("brightness"):
                self.bg.set_brightness(f["brightness"])
            if f.get("scale"):
                self.bg.set_scale(f["scale"])
            # Imagen de fondo global + mode de ajuste a la ventana
            self._apply_background_config(f)

        # Rueda (values lineales se escalan al tamano de la ventana)
        r = config.get("wheel", {})
        if r:
            s = self._scale_section(r)
            self.wheel.visible_items = s.get("visible_items", 13)
            self.wheel.radius = s.get("radius", 320)
            self.wheel.angular_separation = s.get("angular_separation", 8)
            self.wheel.central_scale = s.get("central_scale", 1.4)
            self.wheel.min_scale = s.get("min_scale", 0.3)
            self.wheel.item_width = s.get("item_width", 300)
            self.wheel.item_height = s.get("item_height", 70)
            self.wheel.update()

        # Snap alto
        s = config.get("snap", {})
        if s.get("max_height"):
            self.info_panel.lbl_snap.setFixedHeight(s["max_height"])

        # Video: aplicar en vivo (con preview aunque no haya reproduccion)
        self._apply_video_config(self._rect_stored_to_real(config.get("video") or {}))

        # Fondo: recalcular por si cambio 'usar_snap' u otra opcion
        if hasattr(self, "wheel"):
            self._refresh_current_item_background()

    def _apply_video_config(self, v):
        """Aplica la section video del config en vivo."""
        if not v or not self._video_widget:
            return
        self._video_z = int(v.get("z", 0) or 0)
        reproduciendo = bool(
            self._media_player
            and self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )
        if v.get("fixed"):
            self._video_widget.setGeometry(
                v.get("x", 30), v.get("y", 90), v.get("w", 490), v.get("h", 368)
            )
            # Si nada se reproduce, mostrar el rectangulo como guia de posicion
            if not reproduciendo:
                self._video_widget.show()
            self._reorder_layers()
        else:
            if reproduciendo:
                self._align_video_to_snap()
                self._reorder_layers()
            elif not self._video_widget.isHidden():
                self._video_widget.hide()

    def _on_config_save(self, config):
        try:
            self.backend.save_ui_config(json.dumps(config))
        except Exception as e:
            print(f"[Config] Error al guardar: {e}")
        self._hide_video_preview()
        self._config_open = False
        # Reaplicar fondo de la plataforma si estamos en modo ROMs
        if self._mode == "roms" and self._current_category:
            self._set_platform_background(self._current_category, fallback_wheel=False)
        elif self._mode == "categorias":
            self._apply_background_config(config.get("background") or {})

    # === Emulador ===

    def _on_emulator_state(self, activo):
        self._emulator_active = activo
        if activo:
            self.wheel.setEnabled(False)
            self.top_bar.lbl_info.setText(tr("Emulador en ejecucion..."))
        else:
            self.wheel.setEnabled(True)
            self.wheel.setFocus()

    def _on_emulator_closed(self):
        self._emulator_active = False
        self.wheel.setEnabled(True)
        # Sin WM (startx) el foco X no vuelve solo al cerrar RetroArch:
        # reactivar la ventana explicitamente y devolverlo a la rueda.
        self._restore_window_focus()
        self.top_bar.lbl_info.setText(tr("Emulador cerrado"))
        self._restore_current_snap()

    def _restore_window_focus(self, attempts=10):
        """Devuelve el foco X a la ventana al volver de un emulador.

        En sesiones startx sin window manager (o WM minimo) el foco no se
        reasigna automaticamente cuando RetroArch se cierra: se activa la
        ventana explicitamente (XSetInputFocus) y se reitera hasta que el
        X server/driver de video libera el fullscreen del emulador.
        """
        if not self.isVisible():
            return
        self.raise_()
        self.activateWindow()
        self.wheel.setFocus()
        if attempts > 0 and not self.isActiveWindow():
            QTimer.singleShot(100, lambda: self._restore_window_focus(attempts - 1))

    def _restore_current_snap(self):
        """Al volver del emulador, re-muestra el snap (imagen o video) del
        item actual de la rueda. Al entrar al juego _launch_rom hizo stop_video
        y oculto la caja; aqui se reanuda la reproduccion."""
        if self._mode == "roms":
            item = self.wheel.current_item()
            if item:
                rom = item.meta
                if isinstance(rom, dict):
                    self._show_snap(rom.get("snap", ""))
                    self._background_rom_mode(rom)

    # === Busqueda ===

    def _clear_search(self):
        self._search_buffer = ""
        self.top_bar.lbl_info.setText(tr("{n} ROMs", n=len(self._current_roms)))

    # === Controles configurables ===

    def _build_key_map(self):
        """Construye un mapa invertido: name_tecla -> lista de actions."""
        key_map = {}
        keyboard = self._controls.get("keyboard", {})
        if not keyboard:
            keyboard = DEFAULT_CONTROLS.get("keyboard", {})
        for action, keys in keyboard.items():
            for k in keys:
                key_map.setdefault(k, []).append(action)
        return key_map

    def _reload_controls(self):
        """Recarga controls desde disco y reconstruye los mapas."""
        self._controls = load_controls()
        self._key_map = self._build_key_map()
        self._gamepad_deadzone = self._controls.get("gamepad_deadzone", 0.5)
        # Actualizar hints de la bottom bar
        self.bottom_bar.set_mode(self._mode, self._controls)

    def _is_gamepad_active(self):
        """Retorna True si el device activo es un gamepad."""
        dev = self._controls.get("device", "keyboard")
        return dev.startswith("gamepad:")

    def _on_gp_connected(self, device_id, name):
        print(f"[Gamepad] Conectado: {name} ({device_id})")
        dev = self._controls.get("device", "keyboard")
        if not dev.startswith("gamepad:"):
            self._controls["device"] = f"gamepad:{device_id}"
            save_controls(self._controls)
            self.bottom_bar.set_mode(self._mode, self._controls)

    def _on_gp_disconnected(self, device_id):
        print(f"[Gamepad] Desconectado: {device_id}")
        dev = self._controls.get("device", "keyboard")
        if dev == f"gamepad:{device_id}" or dev == device_id:
            self._controls["device"] = "keyboard"
            save_controls(self._controls)
            self.bottom_bar.set_mode(self._mode, self._controls)

    def _on_gp_button(self, device_id, button_name):
        """Handler para botones del gamepad."""
        if self._emulator_active:
            return
        if self._controls_open:
            return
        if not self._is_gamepad_active():
            print(f"[GP] NOT ACTIVE: device={self._controls.get('device')}")
            return
        gp = self._controls.get("gamepad", {})
        print(f"[GP] button={button_name} gp_keys={list(gp.keys())}")
        for action, mapping in gp.items():
            if button_name in mapping:
                print(f"[GP] -> {action}")
                self._execute_action(action)
                return
        print(f"[GP] -> sin match para {button_name}")

    def _on_gp_axis(self, device_id, axis_idx, value):
        """Handler para axis_names del gamepad."""
        if self._emulator_active or self._controls_open:
            return
        if not self._is_gamepad_active():
            return
        dz = self._gamepad_deadzone
        gp = self._controls.get("gamepad", {})
        if axis_idx == 0:
            if abs(value) < dz:
                self._gamepad_axes["x"] = 0.0
                return
            if self._gamepad_axes["x"] != 0.0:
                return
            self._gamepad_axes["x"] = value
            axis_name = "AxisLeftX-" if value < 0 else "AxisLeftX+"
        elif axis_idx == 1:
            if abs(value) < dz:
                self._gamepad_axes["y"] = 0.0
                return
            if self._gamepad_axes["y"] != 0.0:
                return
            self._gamepad_axes["y"] = value
            axis_name = "AxisLeftY-" if value < 0 else "AxisLeftY+"
        else:
            return
        print(f"[GP] axis={axis_idx} val={value:.2f} axis_name={axis_name}")
        for action, mapping in gp.items():
            if axis_name in mapping:
                print(f"[GP] -> {action}")
                self._execute_action(action)
                return

    def _on_gp_hat(self, device_id, hat_idx, hx, hy):
        """Handler para D-pad (hat) del gamepad."""
        if self._emulator_active or self._controls_open:
            return
        if not self._is_gamepad_active():
            return
        if hx == 0 and hy == 0:
            return
        gp = self._controls.get("gamepad", {})
        # Mapear hat a names de boton
        hat_map = []
        if hy > 0:
            hat_map.append("ButtonDPadUp")
        elif hy < 0:
            hat_map.append("ButtonDPadDown")
        if hx < 0:
            hat_map.append("ButtonDPadLeft")
        elif hx > 0:
            hat_map.append("ButtonDPadRight")
        for btn_name in hat_map:
            for action, mapping in gp.items():
                if btn_name in mapping:
                    self._execute_action(action)
                    return

    def _execute_action(self, action):
        """Ejecuta una action del frontend (comun para keyboard y gamepad)."""
        if self._emulator_active:
            return

        # Dialog abierto: las accionnes actuan sobre el dialog, no sobre la rueda
        nav = getattr(self, "_nav", None)
        if nav is not None and nav.active() is not None:
            if action in ("up", "down", "left", "right"):
                nav.move(action)
            elif action == "select":
                nav.activate()
            elif action in ("back", "close"):
                nav.close_active()
            elif action == "config" and nav.is_visible(self._config_dialog):
                self._toggle_config()
            return

        if action == "close":
            if self._config_open:
                self._toggle_config()
            elif self._controls_open:
                self._controls_dialog.close()
            return

        if action == "up":
            self._search_buffer = ""
            self.wheel.move(-1)
        elif action == "down":
            self._search_buffer = ""
            self.wheel.move(1)
        elif action == "left":
            self._search_buffer = ""
            self.wheel.move(-1)
        elif action == "right":
            self._search_buffer = ""
            self.wheel.move(1)
        elif action == "select":
            self._on_enter(self.wheel.current_item())
        elif action == "back":
            self._do_back()
        elif action == "fullscreen":
            fallback = getattr(self, "_fullscreen_fallback_active", False)
            if self.isFullScreen() or fallback:
                self._fullscreen_disabled = True
                self._fullscreen_fallback_active = False
                if fallback:
                    self.setWindowFlag(Qt.FramelessWindowHint, False)
                    saved = getattr(self, "_saved_released_geometry", None)
                    if saved is not None and not saved.isNull():
                        self.setGeometry(saved)
                self.showNormal()
            else:
                self._fullscreen_disabled = False
                self.showFullScreen()
                self._ensure_fullscreen()
        elif action == "config":
            self._toggle_config()
        elif action == "clear_search":
            if self._search_buffer:
                self._search_buffer = self._search_buffer[:-1]
                if self._search_buffer:
                    self._do_search()
                else:
                    self._clear_search()

    def _do_back(self):
        """Logica de volver/escape centralizada."""
        if self._search_buffer:
            self._clear_search()
            return
        if self._mode == "roms":
            self._back_to_categories()
            return
        if self.isFullScreen():
            self.showNormal()
            return
        self.quit()

    # === Controles dialog ===

    def _ensure_controls_dialog(self):
        if self._controls_dialog is None:
            self._controls_dialog = ControlsDialog(self, self._gamepad_manager)
            self._controls_dialog.controls_saved.connect(self._on_controls_save)
            self._controls_dialog.controls_closed.connect(self._on_controls_closed)
            self._nav.register(self._controls_dialog)
        return self._controls_dialog

    def _open_controls(self):
        dlg = self._ensure_controls_dialog()
        dlg.load_config(self._controls)
        self._controls_open = True
        dlg.show()
        dlg.raise_()

    def _open_controls_from_config(self):
        """Abre el mapeo de botones pidiendolo desde el config dialog."""
        self._open_controls()

    def _toggle_controls(self):
        if self._controls_open:
            self._controls_dialog.close()
        else:
            self._open_controls()

    def _on_controls_save(self, config):
        self._controls = config
        save_controls(config)
        self._key_map = self._build_key_map()
        self._gamepad_deadzone = config.get("gamepad_deadzone", 0.5)
        self.bottom_bar.set_mode(self._mode, self._controls)
        self._controls_open = False

    def _on_controls_closed(self):
        self._controls_open = False
        if not self._emulator_active:
            self.wheel.setFocus()

    # === Teclado ===

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        key_name = self._qt_key_name(key, event)

        # Config/Controls abierto: solo procesar la action "close"
        if self._config_open or self._controls_open:
            actions = self._key_map.get(key_name, [])
            if "close" in actions:
                self._execute_action("close")
            return

        # Emulador activo: ignorar todo
        if self._emulator_active:
            return

        # Buscar si la tecla pertenece a alguna action configurada
        actions = self._key_map.get(key_name, [])

        # Ctrl+L y Ctrl+P son atajos fijos (no configurables)
        if key == Qt.Key_L and (mods & Qt.ControlModifier):
            self._toggle_layout_editor()
            return
        if key == Qt.Key_P and (mods & Qt.ControlModifier):
            self._toggle_positions_admin()
            return
        if key == Qt.Key_Shift:
            self._toggle_controls()
            return

        for action in actions:
            if action == "fullscreen":
                self._execute_action("fullscreen")
                return
            elif action == "config":
                self._execute_action("config")
                return
            elif action == "back":
                self._execute_action("back")
                return
            elif action in ("up", "down", "left", "right"):
                self._execute_action(action)
                return
            elif action == "select":
                self._execute_action("select")
                return
            elif action == "clear_search":
                self._execute_action("clear_search")
                return

        # Busqueda por keyboard (solo en mode ROMs, sin modificadores)
        if self._mode == "roms" and not mods:
            text = event.text()
            if text and text.isalnum():
                self._search_buffer += text.upper()
                self._search_timer.start()
                self._do_search()
                return
            if key == Qt.Key_Backspace and self._search_buffer:
                self._search_buffer = self._search_buffer[:-1]
                if self._search_buffer:
                    self._do_search()
                else:
                    self._clear_search()
                return

    def _qt_key_name(self, key, event):
        """Convierte un Qt key code a name legible para el mapa de controls."""
        QT_KEY_NAMES = {
            Qt.Key_Up: "Up", Qt.Key_Down: "Down", Qt.Key_Left: "Left", Qt.Key_Right: "Right",
            Qt.Key_W: "W", Qt.Key_S: "S", Qt.Key_A: "A", Qt.Key_D: "D",
            Qt.Key_Return: "Return", Qt.Key_Enter: "Enter", Qt.Key_Space: "Space",
            Qt.Key_Escape: "Escape", Qt.Key_Backspace: "Backspace",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3", Qt.Key_F4: "F4",
            Qt.Key_F5: "F5", Qt.Key_F6: "F6", Qt.Key_F7: "F7", Qt.Key_F8: "F8",
            Qt.Key_F9: "F9", Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
            Qt.Key_Shift: "Shift", Qt.Key_Control: "Ctrl", Qt.Key_Alt: "Alt",
            Qt.Key_Tab: "Tab",
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3", Qt.Key_4: "4",
            Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7", Qt.Key_8: "8", Qt.Key_9: "9",
            Qt.Key_Minus: "-", Qt.Key_Equal: "=", Qt.Key_BracketLeft: "[",
            Qt.Key_BracketRight: "]", Qt.Key_Backslash: "\\", Qt.Key_Semicolon: ";",
            Qt.Key_Apostrophe: "'", Qt.Key_Comma: ",", Qt.Key_Period: ".",
            Qt.Key_Slash: "/",
        }
        name = QT_KEY_NAMES.get(key, "")
        if not name and event.text():
            name = event.text().upper()
        return name

    def _do_search(self):
        buf = self._search_buffer
        for i, rom in enumerate(self._current_roms):
            name = rom.get("name", "").upper()
            if name.startswith(buf):
                self.wheel.select_index(i)
                count = sum(1 for r in self._current_roms if r.get("name", "").upper().startswith(buf))
                self.top_bar.lbl_info.setText(tr("{n} encontrados", n=count))
                return
        self.top_bar.lbl_info.setText(tr("Sin resultados"))

    def close_slot(self):
        """Slot para cerrar desde backend."""
        self.quit()

    def quit(self):
        self._stop_video()
        if hasattr(self.backend, '_emulator_process') and self.backend._emulator_process:
            self.backend._emulator_process.terminate()
        self.close()


def main():
    # Consolas Windows (cp1252): evitar crashes al imprimir emojis/acentos
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 50)
    print("  LUNA - Arcade Frontend (Python nativo - PySide6)")
    print("  F11 = Pantalla completa")
    print("  Shift = Configuracion")
    print("  ESC = Volver / Salir")
    print("=" * 50)

    # Registro de errores: si algo truena al iniciar, se vuelca crashes.log
    # junto a la app para poder diagnosticar sin tener la consola a la vista.
    _crash_log = str(BASE_PATH / "crashes.log")

    def _excepthook(etype, value, tb):
        try:
            import traceback as _tb
            import time as _time
            with open(_crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n===== {_time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                f.write("".join(_tb.format_exception(etype, value, tb)))
        except Exception:
            pass
        traceback.print_exception(etype, value, tb)

    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("Luna")
    # Ocultar el cursor del mouse en toda la interfaz (estilo arcade)
    app.setOverrideCursor(Qt.CursorShape.BlankCursor)

    # Splash como overlay dentro de la ventana principal (misma pantalla):
    # se muestra la ventana ya y el splash se incrusta encima cubriendola
    # mientras se cargan la configuracion / se generan los file_paths base.
    splash = SplashScreen()
    window = VentanaArcade(splash=splash)
    window.show()
    app.processEvents()
    window.attach_splash(splash)

    # El fullscreen/raise/foco se reafirma al terminar (ver _show_after_splash).

    # En Linux (X11/Wayland) el fullscreen pedido antes del map puede perderse;
    # _ensure_fullscreen (disparado por showEvent) lo reafirma tras mapear.
    print("[OK] Frontend done")
    print("=" * 50)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
