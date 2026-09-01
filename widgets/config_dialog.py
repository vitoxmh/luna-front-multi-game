"""
config_dialog.py - Administrador de configuracion nativo PySide6.

Se abre con Shift. Todos los campos numericos son editables directamente
(spinboxes con texto libre + flechas), los colores con selector nativo y
todo se aplica en vivo. Guardar persiste en ui_config.json via backend.
"""

import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QCheckBox, QComboBox, QWidget, QScrollArea, QFrame,
    QGridLayout, QSpinBox, QDoubleSpinBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent

from i18n import tr, language_changed, set_language


DEFAULT_CONFIG = {
    "colors": {"background": "#000000", "text": "#ffffff", "selected": "#ff6600",
                "accent": "#00ccff", "text_dim": "#888888", "border": "#222222"},
    "wheel": {"visible_items": 13, "radio": 320, "angular_separation": 8,
              "central_scale": 1.4, "min_scale": 0.3, "item_width": 300, "item_height": 70},
    "background": {"blur": 12, "brightness": 0.25, "scale": 1.15, "use_snap": True,
              "images": [], "active_image": -1},
    "snap": {"max_height": 180},
    "info_panel": {"width": 320},
    "video": {"x": 30, "y": 90, "w": 490, "h": 368, "fixed": False},
    "platform_backgrounds": {}
}


class ColorButton(QPushButton):
    """Boton que abre un selector de color."""

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(50, 28)
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid #555; border-radius: 4px;"
        )

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


class ConfigDialog(QDialog):
    """Administrador de configuracion: campos editables + aplicacion en vivo."""

    config_changed = Signal(dict)  # Emite la config completa al cambiar en vivo
    config_saved = Signal(dict)
    config_closed = Signal()       # El dialogo se cerro (ESC o X)
    quit_signal = Signal()
    controls_requested = Signal()  # El usuario pidio configurar los botones

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Administrador de Configuracion")
        self.setMinimumSize(520, 560)
        self.setModal(False)
        # Nunca quedar detras de la ventana principal en pantalla completa
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._config = json.loads(json.dumps(DEFAULT_CONFIG))
        self._spins = {}
        self._color_buttons = {}
        self._building = False
        self._platform_id = None  # plataforma activa (None = global)
        self._original_global_bg = None  # backup del fondo global al editar plataforma
        self._ui_texts = []      # (widget, key) para retraduccion en vivo
        self._ui_combos = []     # (combo, [keys...]) items traducibles
        self._ui_tooltips = []   # (widget, key)

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0a0a12; }")

        container = QWidget()
        container.setStyleSheet("background: #0a0a12;")
        grid = QVBoxLayout(container)
        grid.setSpacing(12)
        grid.setContentsMargins(20, 16, 20, 10)

        hint = QLabel("Edita cualquier valor: se aplica en vivo. 'Guardar' lo persiste.")
        hint.setStyleSheet("color: #777; font-size: 11px;")
        self._register_text(hint, "Edita cualquier valor: se aplica en vivo. 'Guardar' lo persiste.")
        grid.addWidget(hint)

        # === Colores ===
        grid.addWidget(self._section_label("COLORES"))
        colors_frame = self._make_frame()
        colors_layout = QGridLayout(colors_frame)
        color_names = [
            ("background", "Fondo"), ("text", "Texto"), ("selected", "Seleccionado"),
            ("accent", "Acento"), ("text_dim", "Texto Dim"), ("border", "Borde")
        ]
        for i, (key, label) in enumerate(color_names):
            row, col = divmod(i, 3)
            w = QWidget()
            wl = QVBoxLayout(w)
            wl.setSpacing(4)
            l = QLabel(label)
            l.setStyleSheet("color: #aaa; font-size: 11px;")
            self._register_text(l, label)
            btn = ColorButton(self._config["colors"][key])
            btn.setFixedWidth(100)
            self._color_buttons[key] = btn
            wl.addWidget(l)
            wl.addWidget(btn)
            colors_layout.addWidget(w, row, col)
        grid.addWidget(colors_frame)

        # === Rueda ===
        grid.addWidget(self._section_label("RUEDA"))
        wheel_frame = self._make_frame()
        wheel_layout = QGridLayout(wheel_frame)
        wheel_layout.setSpacing(8)

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
        grid.addWidget(self._section_label("FONDO FANART"))
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
        lbl_mode.setStyleSheet("color: #ccc; font-size: 12px;")
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
        self._cmb_bg_mode.setStyleSheet(
            "QComboBox { color: #fff; background: #1a1a2e; padding: 4px; "
            "border-radius: 4px; font-size: 11px; }"
        )
        modo_row.addWidget(lbl_mode)
        modo_row.addWidget(self._cmb_bg_mode, 1)
        bg_layout.addLayout(modo_row, 1, 0, 1, 3)

        # Lista de imagenes de fondo (cada una con su propia configuracion)
        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        self._cmb_background = QComboBox()
        self._cmb_background.setToolTip("Imagen de fondo activa")
        self._register_tooltip(self._cmb_background, "Imagen de fondo activa")
        self._cmb_background.setStyleSheet(
            "QComboBox { color: #fff; background: #1a1a2e; padding: 4px; "
            "border-radius: 4px; font-size: 11px; }"
        )
        img_row.addWidget(self._cmb_background, 1)
        btn_add = QPushButton("+")
        btn_add.setFixedWidth(32)
        btn_add.setToolTip("Agregar imagen(es)...")
        self._register_tooltip(btn_add, "Agregar imagen(es)...")
        btn_add.setStyleSheet(
            "QPushButton { background: #26263a; color: #ddd; padding: 4px 10px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #343452; }"
        )
        btn_add.clicked.connect(self._add_background_images)
        img_row.addWidget(btn_add)
        btn_del = QPushButton("-")
        btn_del.setFixedWidth(32)
        btn_del.setToolTip("Quitar la imagen seleccionada")
        self._register_tooltip(btn_del, "Quitar la imagen seleccionada")
        btn_del.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; padding: 4px 10px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #444; color: #fff; }"
        )
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
        self._chk_stretch.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(self._chk_stretch, "Imagen ajustada al ancho y alto de la ventana")
        bg_layout.addWidget(self._chk_stretch, 4, 0, 1, 3)
        grid.addWidget(bg_frame)

        # === Snap ===
        grid.addWidget(self._section_label("SNAP"))
        snap_frame = self._make_frame()
        snap_layout = QVBoxLayout(snap_frame)
        w, spin = self._make_spin("Alto max", 80, 600, self._config["snap"]["max_height"], 10, 0)
        self._spins["snap.max_height"] = spin
        snap_layout.addWidget(w)
        grid.addWidget(snap_frame)

        # === Video ===
        grid.addWidget(self._section_label("VIDEO (posicion fija)"))
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

        self._chk_fixed = QCheckBox("Usar posicion fija (si no, se alinea al snap)")
        self._chk_fixed.setStyleSheet("color: #ccc; font-size: 12px;")
        self._chk_fixed.setChecked(self._config["video"]["fixed"])
        self._register_text(self._chk_fixed, "Usar posicion fija (si no, se alinea al snap)")
        video_layout.addWidget(self._chk_fixed, 2, 0, 1, 2)
        grid.addWidget(video_frame)

        # === Resolucion ===
        grid.addWidget(self._section_label("RESOLUCION"))
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
        self._cmb_resolution.setStyleSheet(
            "color: #fff; background: #1a1a2e; padding: 6px; border-radius: 4px;"
        )
        res_layout.addWidget(self._cmb_resolution)

        self._chk_fullscreen = QCheckBox("Pantalla completa")
        self._chk_fullscreen.setChecked(True)
        self._chk_fullscreen.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(self._chk_fullscreen, "Pantalla completa")
        res_layout.addWidget(self._chk_fullscreen)

        # === Idioma ===
        grid.addWidget(self._section_label("IDIOMA"))
        lang_frame = self._make_frame()
        lang_layout = QHBoxLayout(lang_frame)
        lbl_lang = QLabel("Idioma")
        lbl_lang.setFixedWidth(105)
        lbl_lang.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(lbl_lang, "Idioma")
        self._cmb_language = QComboBox()
        self._cmb_language.addItems(["Espanol", "English"])
        self._cmb_language.setStyleSheet(
            "QComboBox { color: #fff; background: #1a1a2e; padding: 4px; "
            "border-radius: 4px; font-size: 12px; }"
        )
        self._cmb_language.currentIndexChanged.connect(self._language_changed)
        lang_layout.addWidget(lbl_lang)
        lang_layout.addWidget(self._cmb_language, 1)
        grid.addWidget(lang_frame)

        # === Botones (configuracion) ===
        grid.addWidget(self._section_label("BOTONES"))
        controls_frame = self._make_frame()
        ctrl_layout = QVBoxLayout(controls_frame)

        ctrl_hint = QLabel("Configura que botones/teclas navegan por los juegos, seleccionan y vuelven.")
        ctrl_hint.setStyleSheet("color: #777; font-size: 11px;")
        ctrl_hint.setWordWrap(True)
        self._register_text(ctrl_hint, "Configura que botones/teclas navegan por los juegos, seleccionan y vuelven.")
        ctrl_layout.addWidget(ctrl_hint)

        btn_row_ctrl = QHBoxLayout()
        btn_ctrl = QPushButton("Configurar botones...")
        btn_ctrl.setStyleSheet(
            "QPushButton { background: #1a1a2e; color: #fff; padding: 10px 24px; "
            "border: 1px solid #ff6600; border-radius: 6px; font-size: 13px; "
            "font-weight: bold; }"
            "QPushButton:hover { background: #2a1a0e; }"
        )
        btn_ctrl.setToolTip("Abre el mapeo de botones del teclado y del gamepad")
        self._register_text(btn_ctrl, "Configurar botones...")
        self._register_tooltip(btn_ctrl, "Abre el mapeo de botones del teclado y del gamepad")
        btn_ctrl.clicked.connect(self.controls_requested.emit)
        btn_row_ctrl.addWidget(btn_ctrl)
        btn_row_ctrl.addStretch()
        ctrl_layout.addLayout(btn_row_ctrl)
        grid.addWidget(controls_frame)

        # === Botones (acciones) ===
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; padding: 8px 24px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background: #444; color: #fff; }"
        )
        btn_close.clicked.connect(self.close)
        self._register_text(btn_close, "Cerrar")
        btn_row.addWidget(btn_close)

        btn_quit = QPushButton("Salir")
        btn_quit.setStyleSheet(
            "QPushButton { background: #cc0000; color: white; padding: 8px 24px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #ff0000; }"
        )
        btn_quit.clicked.connect(self.quit_signal.emit)
        self._register_text(btn_quit, "Salir")
        btn_row.addWidget(btn_quit)

        btn_restore = QPushButton("Restablecer")
        btn_restore.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background: #444; color: #fff; }"
        )
        btn_restore.clicked.connect(self._restore)
        self._register_text(btn_restore, "Restablecer")
        btn_row.addWidget(btn_restore)

        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background: #ff6600; color: white; padding: 8px 24px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #ff8833; }"
        )
        btn_save.clicked.connect(self._save)
        self._register_text(btn_save, "Guardar")
        btn_row.addWidget(btn_save)

        grid.addLayout(btn_row)
        grid.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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
        lbl.setStyleSheet("color: #ccc; font-size: 12px;")
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
        spin.setMinimumWidth(90)
        spin.setStyleSheet(
            "QSpinBox, QDoubleSpinBox { background: #1a1a2e; color: #fff; "
            "border: 1px solid #333; border-radius: 4px; padding: 3px 6px; "
            "font-size: 12px; }"
            "QSpinBox::up-button, QDoubleSpinBox::up-button,"
            "QSpinBox::down-button, QDoubleSpinBox::down-button { width: 16px; }"
        )
        spin.setKeyboardTracking(False)
        h.addWidget(spin)
        h.addStretch()
        return w, spin

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ff6600; font-size: 13px; font-weight: bold; "
            "padding: 4px 0; border-bottom: 1px solid #333;"
        )
        self._register_text(lbl, text)
        return lbl

    def _make_frame(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(15, 15, 25, 0.85); border: 1px solid #222; "
            "border-radius: 6px; padding: 8px; }"
        )
        return frame

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
