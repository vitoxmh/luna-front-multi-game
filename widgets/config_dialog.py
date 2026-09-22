"""
config_dialog.py - Administrador de configuracion nativo PySide6.

Se abre con Shift. Todos los campos numericos son editables directamente
(spinboxes con texto libre + flechas), los colores con selector nativo y
todo se aplica en vivo. Guardar persiste en ui_config.json via backend.
"""

import json
import os
import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QCheckBox, QComboBox, QWidget, QScrollArea, QFrame,
    QGridLayout, QSpinBox, QDoubleSpinBox, QFileDialog, QAbstractSpinBox,
    QProgressBar, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QColor, QKeyEvent

from i18n import tr, language_changed, set_language
from widgets.platform_editor import PlatformEditor
from scraper import scraper
from scanner import load_scan, scan_roms


DEFAULT_CONFIG = {
    "colors": {"background": "#000000", "text": "#ffffff", "selected": "#ff6600",
                "accent": "#00ccff", "text_dim": "#888888", "border": "#222222"},
    "wheel": {"visible_items": 13, "radio": 320, "angular_separation": 8,
              "central_scale": 1.4, "min_scale": 0.3, "item_width": 300, "item_height": 70},
    "background": {"blur": 12, "brightness": 0.25, "scale": 1.15, "use_snap": True,
              "images": [], "active_image": -1},
    "snap": {"max_height": 180, "scale": 100,
             "skew_x": 0, "skew_y": 0, "pinch_x": 0, "pinch_y": 0, "rotation": 0},
    "info_panel": {"width": 320},
    "video": {"x": 30, "y": 90, "w": 490, "h": 368, "fixed": False, "scale": 100},
    "platform_backgrounds": {}
}


# ======================================================================
# Paleta y estilos reutilizables del panel (evita estilos inline repetidos)
# ======================================================================

_BTN_PRIMARY = (
    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
    "stop:0 #ff8a3d, stop:1 #d94f00); color: #ffffff; font-weight: 700; "
    "border: none; border-radius: 8px; padding: 10px 26px; font-size: 13px; }"
    "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
    "stop:0 #ffa156, stop:1 #e85a00); }"
    "QPushButton:pressed { background: #b34700; }"
)
_BTN_DANGER = (
    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
    "stop:0 #ff5c5c, stop:1 #c22e2e); color: #ffffff; font-weight: 700; "
    "border: none; border-radius: 8px; padding: 10px 22px; font-size: 13px; }"
    "QPushButton:hover { background: #ff6f6f; }"
    "QPushButton:pressed { background: #992323; }"
)
_BTN_GHOST = (
    "QPushButton { background: #1c1c38; color: #c6cbe8; border: 1px solid #34345c; "
    "border-radius: 8px; padding: 9px 20px; font-size: 12px; font-weight: 600; }"
    "QPushButton:hover { background: #26264a; border-color: #ff6600; color: #ffffff; }"
    "QPushButton:pressed { background: #15152c; }"
)
_BTN_ACCENT = (
    "QPushButton { background: rgba(255, 102, 0, 0.08); color: #ff8a3d; "
    "border: 1px solid #ff6600; border-radius: 8px; padding: 9px 18px; "
    "font-size: 12px; font-weight: 700; }"
    "QPushButton:hover { background: rgba(255, 102, 0, 0.16); color: #ffb37a; }"
    "QPushButton:pressed { background: rgba(255, 102, 0, 0.28); }"
)
_BTN_ROUND = (
    "QPushButton { background: #26264a; color: #c6cbe8; border: 1px solid #34345c; "
    "border-radius: 14px; font-size: 15px; font-weight: 700; }"
    "QPushButton:hover { background: #34345c; color: #ffffff; border-color: #ff6600; }"
    "QPushButton:pressed { background: #1c1c38; }"
)
_COMBO_STYLE = (
    "QComboBox { background: #1b1b38; color: #e8eaf4; border: 1px solid #34345c; "
    "border-radius: 7px; padding: 6px 10px; font-size: 12px; }"
    "QComboBox:hover { border-color: #ff6600; }"
    "QComboBox::drop-down { border: none; width: 24px; }"
    "QComboBox::down-arrow { image: none; border-left: 4px solid transparent; "
    "border-right: 4px solid transparent; border-top: 5px solid #9aa3c2; }"
    "QComboBox QAbstractItemView { background: #1b1b38; color: #e8eaf4; "
    "selection-background-color: #ff6600; selection-color: #ffffff; "
    "border: 1px solid #34345c; outline: none; }"
)
_CHECK_STYLE = (
    "QCheckBox { color: #c6cbe8; font-size: 12px; spacing: 8px; background: transparent; }"
    "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #34345c; "
    "border-radius: 4px; background: #1b1b38; }"
    "QCheckBox::indicator:hover { border-color: #ff6600; }"
    "QCheckBox::indicator:checked { background: #ff6600; border-color: #ff6600; }"
)
_SPIN_STYLE = (
    "QSpinBox, QDoubleSpinBox { background: #1b1b38; color: #e8eaf4; "
    "border: 1px solid #34345c; border-radius: 7px; padding: 4px 8px; font-size: 12px; }"
    "QSpinBox:focus, QDoubleSpinBox:focus { border-color: #00ccff; }"
    "QSpinBox::up-button, QDoubleSpinBox::up-button, "
    "QSpinBox::down-button, QDoubleSpinBox::down-button { width: 16px; "
    "background: transparent; border: none; }"
    "QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: none; "
    "border-left: 4px solid transparent; border-right: 4px solid transparent; "
    "border-bottom: 5px solid #9aa3c2; }"
    "QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: none; "
    "border-left: 4px solid transparent; border-right: 4px solid transparent; "
    "border-top: 5px solid #9aa3c2; }"
)


class ColorButton(QPushButton):
    """Boton swatch que abre un selector de color y muestra el hex."""

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(100, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Seleccionar color"))
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self):
        c = self._color.name()
        self.setText(c.upper())
        self.setStyleSheet(
            f"QPushButton {{ background-color: {c}; color: {self._text_color()}; "
            f"border: 2px solid rgba(255,255,255,0.12); border-radius: 7px; "
            f"font-size: 10px; font-weight: 700; padding: 0; letter-spacing: 1px; }}"
            f"QPushButton:hover {{ border-color: #ff6600; }}"
        )

    def _text_color(self):
        c = self._color
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
        return "#0d0d1a" if lum > 0.6 else "#ffffff"

    def _pick(self):
        c = QColorDialog.getColor(self._color, self, tr("Seleccionar color"))
        if c.isValid():
            self._color = c
            self._update_style()

    def color(self):
        return self._color.name()

    def set_color(self, c):
        self._color = QColor(c)
        self._update_style()


class _PlatformScrapeSignals(QObject):
    """Señales del worker de scraping por plataforma."""
    started = Signal(int)            # total de ROMs
    progress = Signal(int, int, str)   # (actual, total, nombre_rom)
    finished = Signal(int, int)        # (obtenidos, total)


class PlatformScrapeWorker(QRunnable):
    """Scrapea la info de todos los juegos de una plataforma fuera del hilo
    GUI y reporta progreso por ROM procesada. La lista de ROMs se resuelve
    en el propio worker para no bloquear la interfaz."""

    # Pausa entre peticiones para respetar el rate-limit de RAWG/IGDB
    # (evita HTTP 502 / timeouts por lanzar todas las peticiones en rafaga)
    REQUEST_DELAY = 0.35

    def __init__(self, emulator_id, emulator_config):
        super().__init__()
        self.emulator_id = emulator_id
        self.emulator_config = emulator_config
        self._cancel = False
        self.signals = _PlatformScrapeSignals()

    def cancel(self):
        self._cancel = True

    def _rom_names(self):
        """Nombres de ROM de la plataforma: cache romslist o escaneo directo."""
        try:
            data = load_scan()
            if data and self.emulator_id in data:
                names = []
                for system in data[self.emulator_id]:
                    names.extend(rom.name for rom in getattr(system, "roms", []))
                if names:
                    return names
        except Exception as e:
            print(f"[Scrape] load_scan fallo: {e}")
        if not self.emulator_config:
            return []
        try:
            results = scan_roms({"emulators": {self.emulator_id: self.emulator_config}})
            names = []
            for system in results.get(self.emulator_id, []):
                names.extend(rom.name for rom in getattr(system, "roms", []))
            return names
        except Exception as e:
            print(f"[Scrape] scan_roms fallo: {e}")
            return []

    def run(self):
        names = self._rom_names()
        total = len(names)
        if total == 0:
            self.signals.finished.emit(0, 0)
            return
        self.signals.started.emit(total)
        obtenidos = 0
        for i, name in enumerate(names, start=1):
            if self._cancel:
                break
            try:
                info = scraper.get_info(name, self.emulator_id)
                if info and (info.genre or info.year or info.manufacturer):
                    obtenidos += 1
            except Exception as e:
                print(f"[Scrape {self.emulator_id}] Error con '{name}': {e}")
            self.signals.progress.emit(i, total, name)
            time.sleep(self.REQUEST_DELAY)
        self.signals.finished.emit(obtenidos, total)


class ConfigDialog(QDialog):
    """Administrador de configuracion: campos editables + aplicacion en vivo."""

    config_changed = Signal(dict)  # Emite la config completa al cambiar en vivo
    config_saved = Signal(dict)
    config_closed = Signal()       # El dialogo se cerro (ESC o X)
    quit_signal = Signal()
    controls_requested = Signal()  # El usuario pidio configurar los botones
    platforms_requested = Signal()  # El usuario pidio gestionar plataformas
    rawg_key_saved = Signal(str)   # El usuario guardo la API key de RAWG
    cache_cleared = Signal(str, int)  # (emulador_id, juegos_borrados)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Administrador de Configuracion")
        self.setMinimumSize(620, 640)
        self.setModal(False)
        # Nunca quedar detras de la ventana principal en pantalla completa
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("QDialog { background: #0d0d1a; }")

        self._config = json.loads(json.dumps(DEFAULT_CONFIG))
        self._spins = {}
        self._color_buttons = {}
        self._building = False
        self._platform_id = None  # plataforma activa (None = global)
        self._original_global_bg = None  # backup del fondo global al editar plataforma
        self._ui_texts = []      # (widget, key) para retraduccion en vivo
        self._ui_combos = []     # (combo, [keys...]) items traducibles
        self._ui_tooltips = []   # (widget, key)

        # Scraping por plataforma
        self._scrape_pool = QThreadPool(self)
        self._scrape_pool.setMaxThreadCount(1)
        self._scrape_worker = None
        self._scrape_emulators = {}  # id -> config del emulador (config.json)

        self._build_ui()
        language_changed().connect(self.retranslate)
        self.retranslate()

    def _register_text(self, widget, key):
        """Guarda (widget, clave de traduccion) para re-aplicarla en vivo."""
        self._ui_texts.append((widget, key))

    def _register_tooltip(self, widget, key):
        self._ui_tooltips.append((widget, key))

    def retranslate(self):
        """Re-aplica los textos estaticos segun el idioma actual."""
        try:
            self.setWindowTitle(tr("Administrador de Configuracion"))
            for widget, key in self._ui_texts:
                try:
                    widget.setText(tr(key))
                except Exception:
                    pass
            for combo, keys in self._ui_combos:
                try:
                    for i, k in enumerate(keys):
                        if i < combo.count():
                            combo.setItemText(i, tr(k))
                except Exception:
                    pass
            for widget, key in self._ui_tooltips:
                try:
                    widget.setToolTip(tr(key))
                except Exception:
                    pass
        except Exception:
            pass

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Encabezado "hero" con la wordmark LUNA
        main_layout.addWidget(self._hero_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
            "stop:0 #12122a, stop:1 #0a0a16);"
        )
        grid = QVBoxLayout(container)
        grid.setSpacing(16)
        grid.setContentsMargins(20, 18, 20, 16)

        # === Idioma ===
        grid.addWidget(self._section_label("IDIOMA", "▲"))
        lang_frame = self._make_frame()
        lang_layout = QHBoxLayout(lang_frame)
        lbl_lang = QLabel("Idioma")
        lbl_lang.setFixedWidth(105)
        lbl_lang.setStyleSheet("color: #b8c0d8; font-size: 12px;")
        self._register_text(lbl_lang, "Idioma")
        self._cmb_language = QComboBox()
        self._cmb_language.addItems(["Espanol", "English"])
        self._cmb_language.setStyleSheet(_COMBO_STYLE)
        self._cmb_language.currentIndexChanged.connect(self._language_changed)
        lang_layout.addWidget(lbl_lang)
        lang_layout.addWidget(self._cmb_language, 1)
        grid.addWidget(lang_frame)

        # === Colores ===
        grid.addWidget(self._section_label("COLORES", "●"))
        colors_frame = self._make_frame()
        colors_layout = QGridLayout(colors_frame)
        colors_layout.setHorizontalSpacing(14)
        colors_layout.setVerticalSpacing(10)
        color_names = [
            ("background", "Fondo"), ("text", "Texto"), ("selected", "Seleccionado"),
            ("accent", "Acento"), ("text_dim", "Texto Dim"), ("border", "Borde")
        ]
        for i, (key, label) in enumerate(color_names):
            row, col = divmod(i, 3)
            w = QWidget()
            wl = QVBoxLayout(w)
            wl.setSpacing(4)
            wl.setContentsMargins(0, 0, 0, 0)
            l = QLabel(label)
            l.setStyleSheet("color: #9aa3c2; font-size: 11px;")
            self._register_text(l, label)
            btn = ColorButton(self._config["colors"][key])
            btn.setFixedWidth(100)
            self._color_buttons[key] = btn
            wl.addWidget(l)
            wl.addWidget(btn)
            colors_layout.addWidget(w, row, col)
        grid.addWidget(colors_frame)

        # === Rueda ===
        grid.addWidget(self._section_label("RUEDA", "◭"))
        wheel_frame = self._make_frame()
        wheel_layout = QGridLayout(wheel_frame)
        wheel_layout.setSpacing(10)

        wheel_params = [
            ("visible_items", "Items visibles", 5, 25, 1, 0),
            ("radio", "Radio", 100, 800, 5, 0),
            ("angular_separation", "Sep. angular", 2, 20, 0.5, 1),
            ("central_scale", "Escala central", 0.5, 3.0, 0.1, 1),
            ("min_scale", "Escala min", 0.1, 1.0, 0.05, 2),
            ("item_width", "Ancho item", 100, 600, 10, 0),
            ("item_height", "Alto item", 30, 120, 5, 0),
        ]
        for i, (key, label, mn, mx, step, dec) in enumerate(wheel_params):
            w, spin = self._make_spin(
                label, mn, mx, self._config["wheel"][key], step, dec
            )
            self._spins[f"wheel.{key}"] = spin
            row, col = divmod(i, 2)
            wheel_layout.addWidget(w, row, col)
        grid.addWidget(wheel_frame)

        # === Fondo ===
        grid.addWidget(self._section_label("FONDO FANART", "◉"))
        bg_frame = self._make_frame()
        bg_layout = QGridLayout(bg_frame)

        bg_params = [
            ("blur", "Blur", 0, 30, 1, 0),
            ("brightness", "Brillo", 0, 1, 0.05, 2),
            ("scale", "Escala", 1, 2, 0.05, 2),
        ]
        for col, (key, label, mn, mx, step, dec) in enumerate(bg_params):
            w, spin = self._make_spin(
                label, mn, mx, self._config["background"][key], step, dec
            )
            self._spins[f"background.{key}"] = spin
            bg_layout.addWidget(w, 0, col)

        modo_row = QHBoxLayout()
        lbl_mode = QLabel("Fondo en juegos")
        lbl_mode.setFixedWidth(105)
        lbl_mode.setStyleSheet("color: #b8c0d8; font-size: 12px;")
        self._register_text(lbl_mode, "Fondo en juegos")
        self._cmb_bg_mode = QComboBox()
        self._cmb_bg_mode.setToolTip(
            "Lo que se ve de fondo al navegar los juegos de una plataforma:\n"
            "- Snap del juego (si no tiene, el fondo de la plataforma)\n"
            "- Fondo de la plataforma (si no tiene, la imagen activa de esta lista)"
        )
        self._register_tooltip(self._cmb_bg_mode, "Lo que se ve de fondo al navegar los juegos de una plataforma:\n- Snap del juego (si no tiene, el fondo de la plataforma)\n- Fondo de la plataforma (si no tiene, la imagen activa de esta lista)")
        self._cmb_bg_mode.addItems(["Snap del juego", "Imagen de fondo"])
        self._ui_combos.append((self._cmb_bg_mode, ["Snap del juego", "Imagen de fondo"]))
        self._cmb_bg_mode.setStyleSheet(_COMBO_STYLE)
        modo_row.addWidget(lbl_mode)
        modo_row.addWidget(self._cmb_bg_mode, 1)
        bg_layout.addLayout(modo_row, 1, 0, 1, 3)

        # Lista de imagenes de fondo (cada una con su propia configuracion)
        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        self._cmb_background = QComboBox()
        self._cmb_background.setToolTip("Imagen de fondo activa")
        self._register_tooltip(self._cmb_background, "Imagen de fondo activa")
        self._cmb_background.setStyleSheet(_COMBO_STYLE)
        img_row.addWidget(self._cmb_background, 1)
        btn_add = QPushButton("+")
        btn_add.setFixedSize(28, 26)
        btn_add.setToolTip("Agregar imagen(es)...")
        self._register_tooltip(btn_add, "Agregar imagen(es)...")
        btn_add.setStyleSheet(_BTN_ROUND)
        btn_add.clicked.connect(self._add_background_images)
        img_row.addWidget(btn_add)
        btn_del = QPushButton("-")
        btn_del.setFixedSize(28, 26)
        btn_del.setToolTip("Quitar la imagen seleccionada")
        self._register_tooltip(btn_del, "Quitar la imagen seleccionada")
        btn_del.setStyleSheet(_BTN_ROUND)
        btn_del.clicked.connect(self._remove_background_image)
        img_row.addWidget(btn_del)
        bg_layout.addLayout(img_row, 2, 0, 1, 3)

        w_brillo, self._spin_image_brightness = self._make_spin(
            "Brillo imagen", 0, 1, 1.0, 0.05, 2
        )
        self._spin_image_brightness.setToolTip("Brillo propio de la imagen activa")
        self._register_tooltip(self._spin_image_brightness, "Brillo propio de la imagen activa")
        bg_layout.addWidget(w_brillo, 3, 0, 1, 3)

        self._chk_stretch = QCheckBox("Imagen ajustada al ancho y alto de la ventana")
        self._chk_stretch.setStyleSheet(_CHECK_STYLE)
        self._register_text(self._chk_stretch, "Imagen ajustada al ancho y alto de la ventana")
        bg_layout.addWidget(self._chk_stretch, 4, 0, 1, 3)
        grid.addWidget(bg_frame)

        # === Snap ===
        grid.addWidget(self._section_label("SNAP", "▣"))
        snap_frame = self._make_frame()
        snap_layout = QGridLayout(snap_frame)
        w, spin = self._make_spin("Alto max", 80, 600, self._config["snap"]["max_height"], 10, 0)
        self._spins["snap.max_height"] = spin
        snap_layout.addWidget(w, 0, 0)
        w, spin = self._make_spin("Escala", 25, 300, self._config["snap"]["scale"], 5, 0)
        self._spins["snap.scale"] = spin
        snap_layout.addWidget(w, 0, 1)

        snap_tf_params = [
            ("skew_x", "Skew X", -90, 90, 1),
            ("skew_y", "Skew Y", -90, 90, 1),
            ("pinch_x", "Pinch X", -100, 100, 1),
            ("pinch_y", "Pinch Y", -100, 100, 1),
            ("rotation", "Rotacion", -180, 180, 1),
        ]
        for i, (key, label, mn, mx, step) in enumerate(snap_tf_params):
            w, spin = self._make_spin(label, mn, mx, self._config["snap"][key], step, 0)
            self._spins[f"snap.{key}"] = spin
            snap_layout.addWidget(w, 1 + i // 2, i % 2)
        grid.addWidget(snap_frame)

        # === Video ===
        grid.addWidget(self._section_label("VIDEO (posicion fija)", "▶"))
        video_frame = self._make_frame()
        video_layout = QGridLayout(video_frame)

        video_params = [
            ("x", "X posicion", 0, 3000, 5, 0),
            ("y", "Y posicion", 0, 3000, 5, 0),
            ("w", "Ancho", 100, 3000, 10, 0),
            ("h", "Alto", 80, 2000, 10, 0),
        ]
        for i, (key, label, mn, mx, step, dec) in enumerate(video_params):
            w, spin = self._make_spin(
                label, mn, mx, self._config["video"][key], step, dec
            )
            self._spins[f"video.{key}"] = spin
            video_layout.addWidget(w, i // 2, i % 2)

        w, spin = self._make_spin("Escala", 25, 300, self._config["video"]["scale"], 5, 0)
        self._spins["video.scale"] = spin
        video_layout.addWidget(w, 2, 0, 1, 2)

        self._chk_fixed = QCheckBox("Usar posicion fija (si no, se alinea al snap)")
        self._chk_fixed.setStyleSheet(_CHECK_STYLE)
        self._chk_fixed.setChecked(self._config["video"]["fixed"])
        self._register_text(self._chk_fixed, "Usar posicion fija (si no, se alinea al snap)")
        video_layout.addWidget(self._chk_fixed, 3, 0, 1, 2)
        grid.addWidget(video_frame)

        # === Resolucion ===
        grid.addWidget(self._section_label("RESOLUCION", "☐"))
        res_frame = self._make_frame()
        res_layout = QVBoxLayout(res_frame)

        self._cmb_resolution = QComboBox()
        self._cmb_resolution.addItems([
            "Automatica (pantalla completa)", "1920 x 1080", "1366 x 768",
            "1280 x 720", "2560 x 1440", "3840 x 2160 (4K)"
        ])
        self._ui_combos.append((self._cmb_resolution, [
            "Automatica (pantalla completa)", "1920 x 1080", "1366 x 768",
            "1280 x 720", "2560 x 1440", "3840 x 2160 (4K)"
        ]))
        self._cmb_resolution.setStyleSheet(_COMBO_STYLE)
        res_layout.addWidget(self._cmb_resolution)

        self._chk_fullscreen = QCheckBox("Pantalla completa")
        self._chk_fullscreen.setChecked(True)
        self._chk_fullscreen.setStyleSheet(_CHECK_STYLE)
        self._register_text(self._chk_fullscreen, "Pantalla completa")
        res_layout.addWidget(self._chk_fullscreen)

        # === Botones (configuracion) ===
        grid.addWidget(self._section_label("BOTONES", "⌨"))
        controls_frame = self._make_frame()
        ctrl_layout = QVBoxLayout(controls_frame)

        ctrl_hint = QLabel("Configura que botones/teclas navegan por los juegos, seleccionan y vuelven.")
        ctrl_hint.setStyleSheet("color: #9aa3c2; font-size: 11px;")
        ctrl_hint.setWordWrap(True)
        self._register_text(ctrl_hint, "Configura que botones/teclas navegan por los juegos, seleccionan y vuelven.")
        ctrl_layout.addWidget(ctrl_hint)

        btn_row_ctrl = QHBoxLayout()
        btn_ctrl = QPushButton("Configurar botones...")
        btn_ctrl.setStyleSheet(_BTN_ACCENT)
        btn_ctrl.setToolTip("Abre el mapeo de botones del teclado y del gamepad")
        self._register_text(btn_ctrl, "Configurar botones...")
        self._register_tooltip(btn_ctrl, "Abre el mapeo de botones del teclado y del gamepad")
        btn_ctrl.clicked.connect(self.controls_requested.emit)
        btn_row_ctrl.addWidget(btn_ctrl)
        btn_row_ctrl.addStretch()
        ctrl_layout.addLayout(btn_row_ctrl)
        grid.addWidget(controls_frame)

        # === Plataformas ===
        grid.addWidget(self._section_label("PLATAFORMAS", "▦"))
        platforms_frame = self._make_frame()
        plat_layout = QVBoxLayout(platforms_frame)

        plat_hint = QLabel("Agrega, edita o elimina plataformas/emuladores desde la interfaz.")
        plat_hint.setStyleSheet("color: #9aa3c2; font-size: 11px;")
        plat_hint.setWordWrap(True)
        self._register_text(plat_hint, "Agrega, edita o elimina plataformas/emuladores desde la interfaz.")
        plat_layout.addWidget(plat_hint)

        btn_row_plat = QHBoxLayout()
        btn_platforms = QPushButton("Gestionar plataformas...")
        btn_platforms.setStyleSheet(_BTN_ACCENT)
        btn_platforms.setToolTip("Abre el editor de plataformas para agregar, editar o eliminar emuladores")
        self._register_text(btn_platforms, "Gestionar plataformas...")
        self._register_tooltip(btn_platforms, "Abre el editor de plataformas para agregar, editar o eliminar emuladores")
        btn_platforms.clicked.connect(self.platforms_requested.emit)
        btn_row_plat.addWidget(btn_platforms)
        btn_row_plat.addStretch()
        plat_layout.addLayout(btn_row_plat)
        grid.addWidget(platforms_frame)

        # === Scraper ===
        grid.addWidget(self._section_label("SCRAPER", "⛏"))
        scraper_frame = self._make_frame()
        scraper_layout = QVBoxLayout(scraper_frame)

        scraper_hint = QLabel("Obtiene la informacion de los juegos de una plataforma (anio, genero, fabricante). Los resultados se guardan en el cache.")
        scraper_hint.setStyleSheet("color: #9aa3c2; font-size: 11px;")
        scraper_hint.setWordWrap(True)
        self._register_text(scraper_hint, "Obtiene la informacion de los juegos de una plataforma (anio, genero, fabricante). Los resultados se guardan en el cache.")
        scraper_layout.addWidget(scraper_hint)

        self._cmb_scrape_platform = QComboBox()
        self._cmb_scrape_platform.setStyleSheet(_COMBO_STYLE)
        self._cmb_scrape_platform.setToolTip("Selecciona la plataforma a scrapear")
        self._register_tooltip(self._cmb_scrape_platform, "Selecciona la plataforma a scrapear")
        self._cmb_scrape_platform.currentIndexChanged.connect(self._refresh_scrape_cache_count)
        scraper_layout.addWidget(self._cmb_scrape_platform)

        cache_row = QHBoxLayout()
        self._lbl_scrape_cached = QLabel("")
        self._lbl_scrape_cached.setStyleSheet("color: #9aa3c2; font-size: 11px;")
        self._lbl_scrape_cached.setWordWrap(True)
        cache_row.addWidget(self._lbl_scrape_cached, 1)
        self._btn_scrape_clear = QPushButton("Borrar cache")
        self._btn_scrape_clear.setStyleSheet(_BTN_GHOST)
        self._btn_scrape_clear.setToolTip("Borra la cache de la plataforma seleccionada")
        self._register_text(self._btn_scrape_clear, "Borrar cache")
        self._register_tooltip(self._btn_scrape_clear, "Borra la cache de la plataforma seleccionada")
        self._btn_scrape_clear.clicked.connect(self._clear_scrape_cache)
        cache_row.addWidget(self._btn_scrape_clear)
        scraper_layout.addLayout(cache_row)

        # API key RAWG (gratuita en rawg.io/apidocs) para mejor calidad de info
        rawg_row = QHBoxLayout()
        rawg_lbl = QLabel("API key RAWG")
        rawg_lbl.setFixedWidth(105)
        rawg_lbl.setStyleSheet("color: #b8c0d8; font-size: 12px;")
        self._register_text(rawg_lbl, "API key RAWG")
        rawg_row.addWidget(rawg_lbl)
        self._txt_rawg_key = QLineEdit()
        self._txt_rawg_key.setPlaceholderText("Pega tu api_key gratuita...")
        self._txt_rawg_key.setEchoMode(QLineEdit.Password)
        self._txt_rawg_key.setStyleSheet(
            "QLineEdit { background: #1b1b38; color: #e8eaf4; border: 1px solid #34345c; "
            "border-radius: 7px; padding: 6px 10px; font-size: 12px; }"
            "QLineEdit:focus { border-color: #00ccff; }"
        )
        self._txt_rawg_key.setToolTip("Obtener gratis en https://rawg.io/apidocs")
        self._register_tooltip(self._txt_rawg_key, "Obtener gratis en https://rawg.io/apidocs")
        rawg_row.addWidget(self._txt_rawg_key, 1)
        btn_rawg = QPushButton("Guardar key")
        btn_rawg.setStyleSheet(_BTN_ACCENT)
        btn_rawg.setCursor(Qt.PointingHandCursor)
        btn_rawg.clicked.connect(self._save_rawg_key)
        self._register_text(btn_rawg, "Guardar key")
        rawg_row.addWidget(btn_rawg)
        scraper_layout.addLayout(rawg_row)

        scrape_btn_row = QHBoxLayout()
        self._btn_scrape_start = QPushButton("Scrapear juegos")
        self._btn_scrape_start.setStyleSheet(_BTN_ACCENT)
        self._register_text(self._btn_scrape_start, "Scrapear juegos")
        self._btn_scrape_start.setToolTip("Lanza el scraping de todos los juegos de la plataforma seleccionada")
        self._register_tooltip(self._btn_scrape_start, "Lanza el scraping de todos los juegos de la plataforma seleccionada")
        self._btn_scrape_start.clicked.connect(self._start_scrape_platform)
        scrape_btn_row.addWidget(self._btn_scrape_start)

        self._btn_scrape_stop = QPushButton("Detener")
        self._btn_scrape_stop.setStyleSheet(_BTN_GHOST)
        self._btn_scrape_stop.setEnabled(False)
        self._register_text(self._btn_scrape_stop, "Detener")
        self._btn_scrape_stop.clicked.connect(self._stop_scrape_platform)
        scrape_btn_row.addWidget(self._btn_scrape_stop)
        scrape_btn_row.addStretch()
        scraper_layout.addLayout(scrape_btn_row)

        self._scrape_progress = QProgressBar()
        self._scrape_progress.setRange(0, 100)
        self._scrape_progress.setValue(0)
        self._scrape_progress.setTextVisible(True)
        self._scrape_progress.setStyleSheet(
            "QProgressBar { background: #1b1b38; border: 1px solid #34345c; "
            "border-radius: 7px; height: 18px; text-align: center; color: #e8eaf4; "
            "font-size: 11px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 #ff8a3d, stop:1 #d94f00); border-radius: 6px; }"
        )
        scraper_layout.addWidget(self._scrape_progress)

        self._lbl_scrape_status = QLabel("Listo")
        self._lbl_scrape_status.setStyleSheet("color: #b8c0d8; font-size: 11px;")
        self._lbl_scrape_status.setWordWrap(True)
        self._register_text(self._lbl_scrape_status, "Listo")
        scraper_layout.addWidget(self._lbl_scrape_status)

        grid.addWidget(scraper_frame)

        # === Botones (acciones) ===
        grid.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        main_layout.addWidget(self._footer_bar())

        # Conectar controles para live update
        for key, spin in self._spins.items():
            spin.valueChanged.connect(lambda v, k=key: self._on_live_change(k, v))
        for key, btn in self._color_buttons.items():
            btn.clicked.connect(lambda checked=False, k=key: self._on_color_change(k))
        self._chk_fixed.stateChanged.connect(lambda s: self._on_live_change("video.fixed", s))
        self._cmb_bg_mode.currentIndexChanged.connect(self._bg_mode_changed)
        self._cmb_background.currentIndexChanged.connect(self._combo_bg_changed)
        self._spin_image_brightness.valueChanged.connect(
            lambda v: self._set_active_image_field("brightness", float(v))
        )
        self._chk_stretch.stateChanged.connect(
            lambda s: self._set_active_image_field("stretch", bool(s))
        )
        self._refresh_background_combo()

    # === Constructores de controles ===

    def _make_spin(self, label_text, mn, mx, value, step, decimals):
        """Campo etiqueta + spinner editable (texto libre o flechas)."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(8)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(105)
        lbl.setStyleSheet("color: #b8c0d8; font-size: 12px;")
        self._register_text(lbl, label_text)
        h.addWidget(lbl)

        if decimals:
            spin = QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setSingleStep(step)
            spin.setValue(float(value))
        else:
            spin = QSpinBox()
            spin.setSingleStep(int(step))
            spin.setValue(int(value))
        spin.setRange(mn, mx)
        spin.setMinimumWidth(100)
        spin.setStyleSheet(_SPIN_STYLE)
        spin.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        spin.setKeyboardTracking(False)
        h.addWidget(spin)
        h.addStretch()
        return w, spin

    def _section_label(self, text, glyph=None):
        """Encabezado de seccion: barra acento + icono + titulo en mayusculas."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row.setFixedHeight(24)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        bar = QLabel()
        bar.setFixedSize(4, 16)
        bar.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
            "stop:0 #ff8a3d, stop:1 #d94f00); border-radius: 2px;"
        )
        h.addWidget(bar)

        if glyph:
            gl = QLabel(glyph)
            gl.setStyleSheet("color: #ff6600; font-size: 13px;")
            gl.setFixedWidth(16)
            h.addWidget(gl)

        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ff8a3d; font-size: 12px; font-weight: 800; "
            "letter-spacing: 2px; padding: 0; border: none;"
        )
        self._register_text(lbl, text)
        h.addWidget(lbl)
        h.addStretch()
        return row

    def _make_frame(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(23, 23, 47, 0.75); border: 1px solid #2c2c4e; "
            "border-radius: 10px; padding: 10px; }"
        )
        return frame

    def _hero_header(self):
        """Wordmark LUNA + subtitulo persistente, fijo arriba del panel."""
        hero = QWidget()
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hero.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 #12122a, stop:1 #0d0d1c);"
        )
        hero.setFixedHeight(78)
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(24, 12, 24, 12)
        hl.setSpacing(14)

        badge = QLabel("L")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, "
            "stop:0 #ff8a3d, stop:1 #d94f00); color: #ffffff; "
            "font-size: 24px; font-weight: 900; border-radius: 10px;"
        )
        hl.addWidget(badge)

        title_box = QWidget()
        title_box.setStyleSheet("background: transparent;")
        tl = QVBoxLayout(title_box)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(2)
        title = QLabel("LUNA")
        title.setStyleSheet(
            "color: #ff8a3d; font-size: 19px; font-weight: 900; "
            "letter-spacing: 4px; background: transparent;"
        )
        self._register_text(title, "LUNA")
        tl.addWidget(title)
        sub = QLabel("Edita cualquier valor: se aplica en vivo. 'Guardar' lo persiste.")
        sub.setStyleSheet("color: #9aa3c2; font-size: 11px; background: transparent;")
        self._register_text(sub, "Edita cualquier valor: se aplica en vivo. 'Guardar' lo persiste.")
        tl.addWidget(sub)
        hl.addWidget(title_box)
        hl.addStretch()

        tag = QLabel("CONFIGURACION")
        tag.setStyleSheet(
            "color: #b8c0d8; font-size: 10px; font-weight: 700; "
            "letter-spacing: 3px; background: rgba(255,255,255,0.04); "
            "border: 1px solid #2c2c4e; border-radius: 6px; padding: 5px 10px;"
        )
        hl.addWidget(tag)
        return hero

    def _footer_bar(self):
        """Acciones persistentes: Restablecer / Cerrar / Guardar / Salir."""
        bar = QWidget()
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setStyleSheet(
            "background: #0d0d1c; border-top: 1px solid #2c2c4e;"
        )
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 10, 20, 10)
        bl.setSpacing(10)

        btn_restore = QPushButton("Restablecer")
        btn_restore.setStyleSheet(_BTN_GHOST)
        btn_restore.clicked.connect(self._restore)
        self._register_text(btn_restore, "Restablecer")
        bl.addWidget(btn_restore)
        bl.addStretch()

        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet(_BTN_GHOST)
        btn_close.clicked.connect(self.close)
        self._register_text(btn_close, "Cerrar")
        bl.addWidget(btn_close)

        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(_BTN_PRIMARY)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save)
        self._register_text(btn_save, "Guardar")
        bl.addWidget(btn_save)

        btn_quit = QPushButton("Salir")
        btn_quit.setStyleSheet(_BTN_DANGER)
        btn_quit.setCursor(Qt.PointingHandCursor)
        btn_quit.clicked.connect(self.quit_signal.emit)
        self._register_text(btn_quit, "Salir")
        bl.addWidget(btn_quit)
        return bar

    # === Logica ===

    def _on_live_change(self, key, value):
        if self._building:
            return
        section, field = key.split(".")
        if key == "video.fixed":
            self._config["video"]["fixed"] = bool(value)
        elif key == "background.use_snap":
            self._config["background"]["use_snap"] = bool(value)
        else:
            # QSpinBox emite int, QDoubleSpinBox emite float
            self._config[section][field] = float(value) if isinstance(value, float) else int(value)
        self.config_changed.emit(self._config)

    def _on_color_change(self, key):
        if self._building:
            return
        self._config["colors"][key] = self._color_buttons[key].color()
        self.config_changed.emit(self._config)

    def _bg_mode_changed(self, idx):
        """Fondo al navegar juegos: 0 = snap del juego, 1 = imagen de fondo."""
        if self._building:
            return
        self._config.setdefault("background", {})["use_snap"] = (int(idx) == 0)
        self.config_changed.emit(self._config)

    # === Imagenes de fondo (lista con config individual) ===

    def _normalize_background(self):
        """Normaliza la seccion fondo: migracion + validaciones."""
        bg = self._config.setdefault("background", {})
        # Migrar configs previas con una sola imagen (fondo.imagen)
        if not bg.get("images") and bg.get("image"):
            bg["images"] = [{
                "path": bg.get("image", ""),
                "stretch": bool(bg.get("stretch", True)),
                "brightness": 1.0,
            }]
            bg["image"] = ""
            bg.pop("stretch", None)
        imgs = bg.get("images")
        bg["images"] = [e for e in imgs if isinstance(e, dict) and e.get("path")] \
            if isinstance(imgs, list) else []
        idx = bg.get("active_image", -1)
        if not isinstance(idx, int) or not (0 <= idx < len(bg["images"])):
            idx = 0 if bg["images"] else -1
            bg["active_image"] = idx
        return bg

    def _active_image(self):
        bg = self._config.get("background", {})
        i = bg.get("active_image", -1)
        imgs = bg.get("images") or []
        if 0 <= i < len(imgs):
            return imgs[i]
        return None

    def _refresh_background_combo(self):
        """Reconstruye el combo desde la lista y refresca los controles."""
        self._cmb_background.blockSignals(True)
        self._cmb_background.clear()
        for e in self._config.get("background", {}).get("images", []):
            self._cmb_background.addItem(os.path.basename(e.get("path", "")))
            self._cmb_background.setItemData(self._cmb_background.count() - 1,
                                        e.get("path", ""), Qt.ToolTipRole)
        idx = self._config.get("background", {}).get("active_image", -1)
        if 0 <= idx < self._cmb_background.count():
            self._cmb_background.setCurrentIndex(idx)
        self._cmb_background.blockSignals(False)
        self._refresh_image_controls()

    def _refresh_image_controls(self):
        """Sincroniza brillo/estirar con la entrada activa del combo."""
        entry = self._active_image()
        hay = entry is not None
        self._spin_image_brightness.blockSignals(True)
        self._chk_stretch.blockSignals(True)
        self._spin_image_brightness.setValue(float(entry.get("brightness", 1.0)) if hay else 1.0)
        self._chk_stretch.setChecked(bool(entry.get("stretch", True)) if hay else False)
        self._spin_image_brightness.setEnabled(hay)
        self._chk_stretch.setEnabled(hay)
        self._spin_image_brightness.blockSignals(False)
        self._chk_stretch.blockSignals(False)

    def _combo_bg_changed(self, idx):
        if self._building:
            return
        self._config.setdefault("background", {})["active_image"] = int(idx)
        self._refresh_image_controls()
        self.config_changed.emit(self._config)

    def _set_active_image_field(self, field, value):
        """Cambia un campo de la imagen activa y aplica en vivo."""
        if self._building:
            return
        entry = self._active_image()
        if entry is None:
            return
        entry[field] = value
        self.config_changed.emit(self._config)

    def _add_background_images(self):
        """Agrega una o varias imagenes a la lista (seleccion multiple)."""
        if self._building:
            return
        bg = self._normalize_background()
        rutas, _ = QFileDialog.getOpenFileNames(
            self, tr("Seleccionar imagenes de fondo"),
            "", tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        )
        nuevas = [r for r in rutas if r]
        if not nuevas:
            return
        primera = len(bg["images"])
        for r in nuevas:
            bg["images"].append({"path": r, "stretch": True, "brightness": 1.0})
        bg["active_image"] = primera
        self._refresh_background_combo()
        self.config_changed.emit(self._config)

    def _remove_background_image(self):
        if self._building:
            return
        bg = self._normalize_background()
        i = bg.get("active_image", -1)
        if not (0 <= i < len(bg["images"])):
            return
        del bg["images"][i]
        bg["active_image"] = min(i, len(bg["images"]) - 1) if bg["images"] else -1
        self._refresh_background_combo()
        self.config_changed.emit(self._config)

    def _language_changed(self, idx):
        if self._building:
            return
        set_language("en" if idx == 1 else "es")

    def set_emulators(self, config):
        """Carga los emuladores de config.json en el combo del scraper."""
        self._scrape_emulators = config.get("emulators", {}) if config else {}
        prev = self._cmb_scrape_platform.currentData()
        self._cmb_scrape_platform.blockSignals(True)
        self._cmb_scrape_platform.clear()
        for emu_id, emu_config in self._scrape_emulators.items():
            name = emu_config.get("name", emu_id)
            self._cmb_scrape_platform.addItem(name, emu_id)
        if prev is not None:
            idx = self._cmb_scrape_platform.findData(prev)
            if idx >= 0:
                self._cmb_scrape_platform.setCurrentIndex(idx)
        self._cmb_scrape_platform.blockSignals(False)
        self._refresh_scrape_cache_count()

    def _refresh_scrape_cache_count(self):
        """Muestra cuantos juegos tiene cacheados la plataforma seleccionada."""
        emu_id = self._cmb_scrape_platform.currentData()
        has_platform = bool(emu_id)
        self._btn_scrape_clear.setEnabled(has_platform)
        if not emu_id:
            self._lbl_scrape_cached.setText(tr("Sin plataforma seleccionada"))
            return
        count = 0
        try:
            count = scraper.platform_cache_count(emu_id)
        except Exception:
            pass
        self._btn_scrape_clear.setEnabled(count > 0)
        if count > 0:
            self._lbl_scrape_cached.setText(
                tr("{n} juego(s) en cache", n=count)
            )
        else:
            self._lbl_scrape_cached.setText(tr("Cache vacia para esta plataforma"))

    def _clear_scrape_cache(self):
        """Borra la cache de la plataforma seleccionada."""
        emu_id = self._cmb_scrape_platform.currentData()
        if not emu_id:
            return
        emu_config = self._scrape_emulators.get(emu_id, {})
        name = emu_config.get("name", emu_id)
        ask = QMessageBox.question(
            self,
            tr("Borrar cache"),
            tr("Borra la cache de '{name}'?", name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ask != QMessageBox.Yes:
            return
        try:
            removed = scraper.clear_platform(emu_id)
        except Exception as e:
            removed = 0
            print(f"[Config] Error al borrar cache: {e}")
        self._refresh_scrape_cache_count()
        self.cache_cleared.emit(emu_id, removed)

    def set_rawg_key(self, key):
        """Precarga la API key de RAWG en el campo."""
        self._rawg_key = key or ""
        self._txt_rawg_key.setText(self._rawg_key)

    def _save_rawg_key(self):
        """Guarda la API key de RAWG en config.json y recarga el scraper."""
        key = self._txt_rawg_key.text().strip()
        self.rawg_key_saved.emit(key)

    def _start_scrape_platform(self):
        emu_id = self._cmb_scrape_platform.currentData()
        if not emu_id:
            return
        emu_config = self._scrape_emulators.get(emu_id, {})
        self._btn_scrape_start.setEnabled(False)
        self._btn_scrape_stop.setEnabled(True)
        self._btn_scrape_clear.setEnabled(False)
        self._scrape_progress.setRange(0, 100)
        self._scrape_progress.setValue(0)
        self._lbl_scrape_status.setText(tr("Scrapeando: {rom}...", rom=emu_config.get("name", emu_id)))
        self._scrape_worker = PlatformScrapeWorker(emu_id, emu_config)
        self._scrape_worker.signals.started.connect(self._on_scrape_started)
        self._scrape_worker.signals.progress.connect(self._on_scrape_progress)
        self._scrape_worker.signals.finished.connect(self._on_scrape_finished)
        self._scrape_pool.start(self._scrape_worker)

    def _stop_scrape_platform(self):
        if self._scrape_worker is not None:
            self._scrape_worker.cancel()
            self._btn_scrape_stop.setEnabled(False)
            self._lbl_scrape_status.setText(tr("Deteniendo..."))
            self._refresh_scrape_cache_count()

    def _on_scrape_started(self, total):
        self._scrape_progress.setRange(0, total)
        self._scrape_progress.setValue(0)
        self._lbl_scrape_status.setText(tr("Scrapeando {n} juegos...", n=total))

    def _on_scrape_progress(self, actual, total, name):
        self._scrape_progress.setValue(actual)
        self._lbl_scrape_status.setText(tr("Scrapeando: {rom} ({a}/{t})", rom=name, a=actual, t=total))

    def _on_scrape_finished(self, obtenidos, total):
        self._btn_scrape_start.setEnabled(True)
        self._btn_scrape_stop.setEnabled(False)
        if total:
            self._scrape_progress.setValue(total)
        self._lbl_scrape_status.setText(
            tr("{o} de {t} juegos con info", o=obtenidos, t=total)
        )
        self._refresh_scrape_cache_count()

    def set_language_combo(self, lang):
        """Sincroniza el combo de idioma con 'es'|'en' sin disparar live."""
        self._building = True
        self._cmb_language.blockSignals(True)
        self._cmb_language.setCurrentIndex(1 if lang == "en" else 0)
        self._cmb_language.blockSignals(False)
        self._building = False

    def selected_language(self):
        return "en" if self._cmb_language.currentIndex() == 1 else "es"

    def load_config(self, config):
        """Carga una config y actualiza todos los controles."""
        self._building = True
        self._config = json.loads(json.dumps(config))
        # Compatibilidad con ui_config.json previos a la opcion snap-fondo
        self._config.setdefault("background", {}).setdefault("use_snap", True)
        self._config.setdefault("snap", {}).setdefault("scale", 100)
        self._config.setdefault("video", {}).setdefault("scale", 100)
        self._config.setdefault("platform_backgrounds", {})
        # Si hay plataforma activa y tiene fondo propio, usarlo
        self._original_global_bg = None
        if self._platform_id and self._platform_id in self._config.get("platform_backgrounds", {}):
            self._original_global_bg = json.loads(json.dumps(self._config.get("background", {})))
            self._config["background"] = json.loads(
                json.dumps(self._config["platform_backgrounds"][self._platform_id])
            )
        self._normalize_background()
        self._refresh_background_combo()
        for key, btn in self._color_buttons.items():
            if key in self._config.get("colors", {}):
                btn.set_color(self._config["colors"][key])
        for key, spin in self._spins.items():
            section, field = key.split(".")
            val = self._config.get(section, {}).get(field, 0)
            spin.blockSignals(True)
            spin.setValue(float(val))
            spin.blockSignals(False)
        self._chk_fixed.setChecked(self._config.get("video", {}).get("fixed", False))
        usar_snap = bool(self._config.get("background", {}).get("use_snap", True))
        self._cmb_bg_mode.blockSignals(True)
        self._cmb_bg_mode.setCurrentIndex(0 if usar_snap else 1)
        self._cmb_bg_mode.blockSignals(False)
        self._building = False

    def _restore(self):
        self.load_config(DEFAULT_CONFIG)
        self.config_changed.emit(self._config)

    def _save(self):
        # Si hay plataforma activa, guardar su fondo en platform_backgrounds
        # y restaurar el fondo global original
        if self._platform_id:
            self._config.setdefault("platform_backgrounds", {})
            self._config["platform_backgrounds"][self._platform_id] = json.loads(
                json.dumps(self._config.get("background", {}))
            )
            if self._original_global_bg is not None:
                self._config["background"] = self._original_global_bg
        self.config_saved.emit(self._config)
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # Si hay un scraping en curso, pedir cancelacion al cerrar
        if self._scrape_worker is not None:
            self._scrape_worker.cancel()
        self._scrape_pool.clear()
        self.config_closed.emit()
        super().closeEvent(event)

    def set_section(self, section, values):
        """Actualiza una seccion de la config en memoria."""
        self._config.setdefault(section, {}).update(values or {})
        self.load_config(self._config)

    def set_video(self, v):
        """Actualiza solo la seccion video de la config en memoria."""
        self.set_section("video", v)

    def config(self):
        return self._config

    def set_platform(self, platform_id):
        """Establece el contexto de plataforma para fondos per-plataforma."""
        self._platform_id = platform_id
