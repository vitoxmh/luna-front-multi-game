"""
posiciones_admin.py - Administrador de posiciones dentro del frontend.

Ajusta en vivo la posicion de la rueda (horizontal, ajuste fino, linea),
el ancho del panel de info, el video y las imagenes personalizadas.
Se abre con Ctrl+P desde la ventana principal.

Los cambios se escriben en layout_<sistema>.json cuando se esta dentro
de una plataforma (mame, nes, ...) y en layout.json / ui_config.json
cuando se esta en el menu global.
"""

import json
import os
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QPushButton, QCheckBox, QComboBox, QFileDialog,
    QTabWidget, QLineEdit
)
from PySide6.QtCore import Qt, QTimer

from i18n import tr, language_changed

import paths

_BASE_PATH = str(paths.base_path())
_LAYOUT_PATH = os.path.join(_BASE_PATH, "layouts", "layout.json")

STYLE = """
QWidget { background: #14141c; color: #ddd; font-size: 12px; }
QLabel[clase="titulo"] { color: #ff6600; font-size: 15px; font-weight: bold; }
QLabel[clase="hint"] { color: #777; font-size: 11px; }
QGroupBox {
    border: 1px solid #2a2a38; border-radius: 6px; margin-top: 10px;
    font-weight: bold; color: #00ccff;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QSpinBox, QDoubleSpinBox {
    background: #1e1e2a; border: 1px solid #33334a; border-radius: 4px;
    padding: 2px 4px; min-width: 80px;
}
QPushButton {
    background: #26263a; border: 1px solid #3a3a55; border-radius: 4px;
    padding: 5px 10px;
}
QPushButton:hover { background: #343452; }
QTabWidget::pane { border: 1px solid #2a2a38; border-radius: 4px; top: -1px; }
QTabBar::tab {
    background: #1a1a26; color: #8a8fa5;
    padding: 5px 12px; border: 1px solid #2a2a38; border-bottom: none;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}
QTabBar::tab:selected { background: #26263a; color: #ff8833; }
"""


class PosicionesAdmin(QWidget):
    """Panel flotante para posicionar rueda, video e info en vivo."""

    def __init__(self, window, load_ui_fn, save_ui_fn):
        super().__init__(None)
        self._window = window
        self._load_ui_fn = load_ui_fn      # () -> dict ui_config
        self._save_ui_fn = save_ui_fn      # (dict) -> None
        self._loading = False
        self._images = []                  # lista del layout.json
        self._selected_image = -1
        self._form_fields = []             # (form, spin, key) para retraducir etiquetas
        self._box_titles = []              # (box, key)
        self._tab_titles = []              # keys de las pestanas
        self._texts = []                   # (widget, key) texto fijo
        self._cs = []                      # (checkbox, key)
        self._tooltips = []                # (widget, key)
        self._placeholders = []            # (widget, key)

        self._timer_layout = QTimer(self)
        self._timer_layout.setSingleShot(True)
        self._timer_layout.setInterval(250)
        self._timer_layout.timeout.connect(self._save_layout)

        self._timer_video = QTimer(self)
        self._timer_video.setSingleShot(True)
        self._timer_video.setInterval(300)
        self._timer_video.timeout.connect(self._save_video)

        self._timer_imgs = QTimer(self)
        self._timer_imgs.setSingleShot(True)
        self._timer_imgs.setInterval(250)
        self._timer_imgs.timeout.connect(self._save_images)

        self._timer_snap = QTimer(self)
        self._timer_snap.setSingleShot(True)
        self._timer_snap.setInterval(250)
        self._timer_snap.timeout.connect(self._save_snap)

        self.setWindowTitle("Posiciones")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.resize(360, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QLabel("Administrador de Posiciones")
        title.setProperty("clase", "titulo")
        self._title_lbl = title
        root.addWidget(title)

        hint = QLabel("Los cambios se aplican en vivo sobre el frontend")
        hint.setProperty("clase", "hint")
        self._hint_lbl = hint
        root.addWidget(hint)

        self.lbl_target = QLabel("")
        self.lbl_target.setProperty("clase", "titulo")
        root.addWidget(self.lbl_target)

        # === Rueda ===
        box_wheel = QGroupBox("Rueda")
        self._box_titles.append((box_wheel, "Rueda"))
        form_r = QFormLayout(box_wheel)
        form_r.setVerticalSpacing(4)
        self.sp_base_x = self._dspin(form_r, box_wheel, "Posicion horizontal (%)", 0.0, 100.0, 1.0)
        self.sp_pull_x = self._ispin(form_r, box_wheel, "Ajuste fino X", -200, 200, 1)
        self.sp_line_ini = self._dspin(form_r, box_wheel, "Linea inicio (%)", 0.0, 100.0, 1.0)
        self.sp_line_fin = self._dspin(form_r, box_wheel, "Linea fin (%)", 0.0, 100.0, 1.0)

        sep = QLabel("Flecha (indicador)")
        sep.setProperty("clase", "hint")
        self._texts.append((sep, "Flecha (indicador)"))
        form_r.addRow(sep)
        self.sp_flecha_x = self._dspin(form_r, box_wheel, "Flecha X (%)", 0.0, 100.0, 0.5)
        self.sp_flecha_x.setToolTip("Posicion horizontal de la flecha")
        self._tooltips.append((self.sp_flecha_x, "Posicion horizontal de la flecha"))
        self.sp_flecha_y = self._dspin(form_r, box_wheel, "Flecha Y (%)", 0.0, 100.0, 0.5)
        self.sp_flecha_y.setToolTip("Posicion vertical de la flecha (50% = centro)")
        self._tooltips.append((self.sp_flecha_y, "Posicion vertical de la flecha (50% = centro)"))
        self.sp_flecha_size = self._ispin(form_r, box_wheel, "Tamano flecha", 4, 80, 1)

        # === Fondo ===
        box_background = QGroupBox("Fondo")
        self._box_titles.append((box_background, "Fondo"))
        form_f = QFormLayout(box_background)
        form_f.setVerticalSpacing(4)

        self.chk_usar_snap = QCheckBox("Usar snap como fondo")
        self.chk_usar_snap.setToolTip(
            "El snap del juego se muestra como fondo.\n"
            "En GLOBAL define el valor por defecto (layout.json);\n"
            "dentro de una plataforma solo la afecta (layout_<sistema>.json)."
        )
        self._cs.append((self.chk_usar_snap, "Usar snap como fondo"))
        self._tooltips.append((self.chk_usar_snap, "El snap del juego se muestra como fondo.\nEn GLOBAL define el valor por defecto (layout.json);\ndentro de una plataforma solo la afecta (layout_<sistema>.json)."))
        self.chk_usar_snap.toggled.connect(self._snap_background_changed)
        form_f.addRow(self.chk_usar_snap)

        self.txt_bg_path = QLineEdit()
        self.txt_bg_path.setReadOnly(True)
        self.txt_bg_path.setPlaceholderText("(sin imagen de fondo)")
        self.txt_bg_path.setToolTip("Ruta de la imagen de fondo actual")
        self._placeholders.append((self.txt_bg_path, "(sin imagen de fondo)"))
        self._tooltips.append((self.txt_bg_path, "Ruta de la imagen de fondo actual"))
        form_f.addRow("Imagen:", self.txt_bg_path)
        self._form_fields.append((form_f, self.txt_bg_path, "Imagen:"))

        bg_btns = QHBoxLayout()
        bg_btns.setSpacing(4)
        btn_bg_upload = QPushButton("Subir imagen...")
        btn_bg_upload.setToolTip(
            "Selecciona una imagen y la copia a images/personalizadas/.\n"
            "Guarda la ruta relativa en el layout."
        )
        self._texts.append((btn_bg_upload, "Subir imagen..."))
        self._tooltips.append((btn_bg_upload, "Selecciona una imagen y la copia a images/personalizadas/.\nGuarda la ruta relativa en el layout."))
        btn_bg_upload.clicked.connect(self._upload_platform_background)
        bg_btns.addWidget(btn_bg_upload)
        btn_bg_browse = QPushButton("Examinar...")
        btn_bg_browse.setToolTip(
            "Busca una imagen existente en tu disco.\n"
            "Usa la ruta absoluta seleccionada."
        )
        self._texts.append((btn_bg_browse, "Examinar..."))
        self._tooltips.append((btn_bg_browse, "Busca una imagen existente en tu disco.\nUsa la ruta absoluta seleccionada."))
        btn_bg_browse.clicked.connect(self._choose_platform_background)
        bg_btns.addWidget(btn_bg_browse)
        btn_bg_del = QPushButton("Quitar")
        btn_bg_del.setToolTip("Quita el fondo fijo configurado")
        self._texts.append((btn_bg_del, "Quitar"))
        self._tooltips.append((btn_bg_del, "Quita el fondo fijo configurado"))
        btn_bg_del.clicked.connect(self._remove_platform_background)
        bg_btns.addWidget(btn_bg_del)
        form_f.addRow(bg_btns)

        # === Panel info ===
        box_info = QGroupBox("Panel Info")
        self._box_titles.append((box_info, "Panel Info"))
        form_i = QFormLayout(box_info)
        form_i.setVerticalSpacing(4)
        self.sp_info_ancho = self._ispin(form_i, box_info, "Ancho", 150, 800, 10)

        # === Snap ===
        box_snap = QGroupBox("Snap")
        self._box_titles.append((box_snap, "Snap"))
        form_s = QFormLayout(box_snap)
        form_s.setVerticalSpacing(4)
        self.chk_snap = QCheckBox("Posicion personalizada")
        self.chk_snap.setToolTip("Saca el snap del panel y lo coloca libre")
        self._cs.append((self.chk_snap, "Posicion personalizada"))
        self._tooltips.append((self.chk_snap, "Saca el snap del panel y lo coloca libre"))
        self.chk_snap.toggled.connect(self._snap_changed)
        form_s.addRow(self.chk_snap)
        self.sp_sx = self._ispin(form_s, box_snap, "X", 0, 4000, 5)
        self.sp_sy = self._ispin(form_s, box_snap, "Y", 0, 4000, 5)
        self.sp_sw = self._ispin(form_s, box_snap, "Ancho", 50, 4000, 10)
        self.sp_sh = self._ispin(form_s, box_snap, "Alto", 40, 4000, 10)

        # === Video ===
        box_video = QGroupBox("Video")
        self._box_titles.append((box_video, "Video"))
        form_v = QFormLayout(box_video)
        form_v.setVerticalSpacing(4)
        self.chk_fijo = QCheckBox("Posicion fija")
        self.chk_fijo.toggled.connect(self._video_changed)
        self._cs.append((self.chk_fijo, "Posicion fija"))
        form_v.addRow(self.chk_fijo)
        self.sp_vx = self._ispin(form_v, box_video, "X", 0, 4000, 5)
        self.sp_vy = self._ispin(form_v, box_video, "Y", 0, 4000, 5)
        self.sp_vw = self._ispin(form_v, box_video, "Ancho", 50, 4000, 10)
        self.sp_vh = self._ispin(form_v, box_video, "Alto", 40, 4000, 10)
        self.sp_vz = self._ispin(form_v, box_video, "Capa Z", 0, 99, 1)
        self.sp_vz.setToolTip("Con Z>=1 compite con las imagenes; empate gana la imagen")
        self._tooltips.append((self.sp_vz, "Con Z>=1 compite con las imagenes; empate gana la imagen"))

        # === Imagenes personalizadas ===
        box_img = QGroupBox("Imagenes")
        self._box_titles.append((box_img, "Imagenes"))
        vi = QVBoxLayout(box_img)
        vi.setSpacing(4)

        fila_sel = QHBoxLayout()
        self.cmb_img = QComboBox()
        self.cmb_img.setToolTip("Imagen superpuesta seleccionada")
        self._tooltips.append((self.cmb_img, "Imagen superpuesta seleccionada"))
        fila_sel.addWidget(self.cmb_img, 1)
        btn_add = QPushButton("+")
        btn_add.setFixedWidth(28)
        btn_add.setToolTip("Agregar imagen...")
        self._tooltips.append((btn_add, "Agregar imagen..."))
        btn_add.clicked.connect(self._add_image_dialog)
        fila_sel.addWidget(btn_add)
        btn_del = QPushButton("-")
        btn_del.setFixedWidth(28)
        btn_del.setToolTip("Quitar imagen")
        self._tooltips.append((btn_del, "Quitar imagen"))
        btn_del.clicked.connect(self._remove_image)
        fila_sel.addWidget(btn_del)
        vi.addLayout(fila_sel)

        form_img = QFormLayout()
        form_img.setVerticalSpacing(4)
        self.sp_ix = self._ispin(form_img, box_img, "X", -5000, 5000, 5)
        self.sp_iy = self._ispin(form_img, box_img, "Y", -5000, 5000, 5)
        sp_esc = QDoubleSpinBox()
        sp_esc.setRange(5.0, 500.0)
        sp_esc.setDecimals(0)
        sp_esc.setSingleStep(10.0)
        sp_esc.setKeyboardTracking(False)
        sp_esc.setSuffix(" %")
        form_img.addRow("Escala", sp_esc)
        self._form_fields.append((form_img, sp_esc, "Escala"))
        self.sp_iesc = sp_esc
        sp_z = QSpinBox()
        sp_z.setRange(0, 9)
        sp_z.setKeyboardTracking(False)
        sp_z.setToolTip("0: bajo la interfaz. 1 o mas: sobre el video")
        self._tooltips.append((sp_z, "0: bajo la interfaz. 1 o mas: sobre el video"))
        form_img.addRow("Capa Z", sp_z)
        self._form_fields.append((form_img, sp_z, "Capa Z"))
        self.sp_iz = sp_z
        vi.addLayout(form_img)

        # === Pestañas: grupos apilados por funcion ===
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._tab_page(box_wheel), "Rueda")
        tabs.addTab(self._tab_page(box_background), "Fondo")
        tabs.addTab(self._tab_page(box_info, box_snap, box_video), "Paneles")
        tabs.addTab(self._tab_page(box_img), "Imagenes")
        self._tabs = tabs
        self._tab_titles = ["Rueda", "Fondo", "Paneles", "Imagenes"]
        root.addWidget(tabs, 1)

        btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setToolTip("Hace permanentes los cambios para este sistema")
        self._texts.append((btn_guardar, "Guardar"))
        self._tooltips.append((btn_guardar, "Hace permanentes los cambios para este sistema"))
        btn_guardar.clicked.connect(self.save_all)
        btns.addWidget(btn_guardar)
        btns.addStretch()
        btn_restaurar = QPushButton("Restaurar")
        btn_restaurar.setToolTip("Vuelve a los valores guardados")
        self._texts.append((btn_restaurar, "Restaurar"))
        self._tooltips.append((btn_restaurar, "Vuelve a los valores guardados"))
        btn_restaurar.clicked.connect(self.restore)
        btns.addWidget(btn_restaurar)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setToolTip("Cierra el administrador (aplica los cambios pendientes)")
        self._texts.append((btn_cerrar, "Cerrar"))
        self._tooltips.append((btn_cerrar, "Cierra el administrador (aplica los cambios pendientes)"))
        btn_cerrar.clicked.connect(self.close)
        btns.addWidget(btn_cerrar)

        root.addLayout(btns)

        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("clase", "hint")
        root.addWidget(self.lbl_status)

        self._timer_status = QTimer(self)
        self._timer_status.setSingleShot(True)
        self._timer_status.setInterval(4000)
        self._timer_status.timeout.connect(lambda: self.lbl_status.setText(""))

        language_changed().connect(self.retranslate)
        self.load_values()

    # === Helpers de creacion ===

    def _ispin(self, form, box, label, mn, mx, step):
        sp = QSpinBox()
        sp.setRange(mn, mx)
        sp.setSingleStep(step)
        sp.setKeyboardTracking(False)
        form.addRow(label, sp)
        self._form_fields.append((form, sp, label))
        return sp

    def _dspin(self, form, box, label, mn, mx, step):
        sp = QDoubleSpinBox()
        sp.setRange(mn, mx)
        sp.setDecimals(1)
        sp.setSingleStep(step)
        sp.setKeyboardTracking(False)
        form.addRow(label, sp)
        self._form_fields.append((form, sp, label))
        return sp

    def retranslate(self):
        try:
            self.setWindowTitle(tr("Posiciones"))
            self._title_lbl.setText(tr("Administrador de Posiciones"))
            self._hint_lbl.setText(tr("Los cambios se aplican en vivo sobre el frontend"))
            self._refresh_target_text()
            for box, key in self._box_titles:
                box.setTitle(tr(key))
            for i, key in enumerate(self._tab_titles):
                if i < self._tabs.count():
                    self._tabs.setTabText(i, tr(key))
            for form, spin, key in self._form_fields:
                lbl = form.labelForField(spin)
                if lbl is not None:
                    lbl.setText(tr(key))
            for w, key in self._placeholders:
                try:
                    w.setPlaceholderText(tr(key))
                except Exception:
                    pass
            # Etiquetas de formularios creados a mano
            for w, key in self._texts:
                try:
                    w.setText(tr(key))
                except Exception:
                    pass
            for w, key in self._cs:
                try:
                    w.setText(tr(key))
                except Exception:
                    pass
            for w, key in self._tooltips:
                try:
                    w.setToolTip(tr(key))
                except Exception:
                    pass
        except Exception:
            pass

    def _tab_page(self, *boxes):
        """Contenedor de pestana: grupos apilados con estiro al final."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(8)
        for c in boxes:
            v.addWidget(c)
        v.addStretch()
        return w

    # === Carga / guardado layout.json ===

    def _system_id(self):
        """Id de la plataforma activa del frontend (None = menu global)."""
        return getattr(self._window, "_current_system", None) or None

    def _layout_target_path(self):
        """Archivo al que se escriben los cambios segun la plataforma activa."""
        sis = self._system_id()
        if sis:
            return os.path.join(_BASE_PATH, "layouts", f"layout_{sis}.json")
        return _LAYOUT_PATH

    def _read_target(self):
        """Contenido del archivo destino ({} si no existe)."""
        try:
            with open(self._layout_target_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _refresh_target_text(self):
        sis = self._system_id()
        if sis:
            self.lbl_target.setText(tr("Ajustando: {sis}", sis=sis.upper()))
        else:
            self.lbl_target.setText(tr("Ajustando: GLOBAL"))

    def load_values(self):
        self._refresh_target_text()
        try:
            lay = self._window._read_combined_layout()
        except Exception as e:
            print(f"[Posiciones] Error al leer layout: {e}")
            return

        w = lay.get("wheel", {})
        self._loading = True
        self.sp_base_x.setValue(float(w.get("base_x_percent", 0.15)) * 100.0)
        self.sp_pull_x.setValue(int(w.get("pull_in_x", 25)))
        self.sp_line_ini.setValue(float(w.get("line_x_start_percent", 0.08)) * 100.0)
        self.sp_line_fin.setValue(float(w.get("line_x_end_percent", 0.78)) * 100.0)
        self.sp_flecha_x.setValue(float(w.get("indicator_x_percent", 0.03)) * 100.0)
        self.sp_flecha_y.setValue(float(w.get("indicator_y_percent", 0.5)) * 100.0)
        self.sp_flecha_size.setValue(int(w.get("indicator_size", 12)))
        self.chk_usar_snap.setChecked(self._window._use_snap_as_background())
        self._current_bg_path = (lay.get("background") or {}).get("image", "")
        self.txt_bg_path.setText(self._current_bg_path)
        self.sp_info_ancho.setValue(int(lay.get("info_panel", {}).get("width", 350)))

        v = {}
        try:
            v = self._window._effective_video() or {}
        except Exception as e:
            print(f"[Posiciones] Error al leer video: {e}")
        self.chk_fijo.setChecked(bool(v.get("fixed", False)))
        self.sp_vx.setValue(int(v.get("x", 30)))
        self.sp_vy.setValue(int(v.get("y", 90)))
        self.sp_vw.setValue(int(v.get("w", 490)))
        self.sp_vh.setValue(int(v.get("h", 368)))
        self.sp_vz.setValue(int(v.get("z", 0)))

        sn = {}
        try:
            sn = self._window._effective_snap() or {}
        except Exception as e:
            print(f"[Posiciones] Error al leer snap: {e}")
        self.chk_snap.setChecked(bool(sn.get("custom", False)))
        self.sp_sx.setValue(int(sn.get("x", 60)))
        self.sp_sy.setValue(int(sn.get("y", 120)))
        self.sp_sw.setValue(int(sn.get("w", 320)))
        self.sp_sh.setValue(int(sn.get("h", 240)))
        self._connect()
        self._loading = False
        self._reload_images()

    def _connect(self):
        for sp, field, conv in (
            (self.sp_base_x, "base_x_percent", lambda x: x / 100.0),
            (self.sp_pull_x, "pull_in_x", int),
            (self.sp_line_ini, "line_x_start_percent", lambda x: x / 100.0),
            (self.sp_line_fin, "line_x_end_percent", lambda x: x / 100.0),
            (self.sp_flecha_x, "indicator_x_percent", lambda x: x / 100.0),
            (self.sp_flecha_y, "indicator_y_percent", lambda x: x / 100.0),
            (self.sp_flecha_size, "indicator_size", int),
        ):
            sp.valueChanged.connect(lambda val, c=field, f=conv: self._layout_changed(c, f(val)))
        self.sp_info_ancho.valueChanged.connect(
            lambda val: self._layout_changed_info(val)
        )
        for sp in (self.sp_vx, self.sp_vy, self.sp_vw, self.sp_vh):
            sp.valueChanged.connect(lambda _: self._video_changed())
        self.cmb_img.currentIndexChanged.connect(self._image_selected)
        self.sp_ix.valueChanged.connect(lambda v: self._image_field_changed("x", v))
        self.sp_iy.valueChanged.connect(lambda v: self._image_field_changed("y", v))
        self.sp_iesc.valueChanged.connect(
            lambda v: self._image_field_changed("scale", v / 100.0)
        )
        self.sp_iz.valueChanged.connect(lambda v: self._image_field_changed("z", int(v)))
        self.chk_snap.toggled.connect(lambda _: self._snap_changed())
        for sp in (self.sp_sx, self.sp_sy, self.sp_sw, self.sp_sh):
            sp.valueChanged.connect(lambda _: self._snap_changed())

    def _read_layout(self):
        return self._read_target()

    def _layout_changed(self, field, value):
        if self._loading:
            return
        pend = getattr(self, "_pending_layout", None)
        if not isinstance(pend, dict):
            pend = {}
        pend[field] = value
        self._pending_layout = pend
        self._timer_layout.start()

    def _layout_changed_info(self, value):
        if self._loading:
            return
        self._pending_info = value
        self._timer_layout.start()

    def _save_layout(self):
        try:
            lay = self._read_layout()
            changes = getattr(self, "_pending_layout", None)
            if isinstance(changes, dict) and changes:
                lay.setdefault("wheel", {}).update(changes)
                self._pending_layout = {}
            info_val = getattr(self, "_pending_info", None)
            if info_val is not None:
                lay.setdefault("info_panel", {})["width"] = int(info_val)
                self._window.info_panel.setFixedWidth(int(info_val))
            with open(self._layout_target_path(), "w", encoding="utf-8") as f:
                json.dump(lay, f, indent=4, ensure_ascii=False)
            self._window._apply_layout(self._window._read_combined_layout())
        except Exception as e:
            print(f"[Posiciones] Error al guardar layout: {e}")

    # === Video ===

    def _video_changed(self):
        if self._loading:
            return
        v = {
            "fixed": self.chk_fijo.isChecked(),
            "x": self.sp_vx.value(),
            "y": self.sp_vy.value(),
            "w": self.sp_vw.value(),
            "h": self.sp_vh.value(),
            "z": self.sp_vz.value(),
        }
        self._window._apply_video_config(v)
        self._timer_video.start()

    def _save_video(self):
        try:
            v_real = {
                "fixed": self.chk_fijo.isChecked(),
                "x": self.sp_vx.value(),
                "y": self.sp_vy.value(),
                "w": self.sp_vw.value(),
                "h": self.sp_vh.value(),
                "z": self.sp_vz.value(),
            }
            v = self._window._rect_real_to_stored(v_real)
            if self._system_id():
                lay = self._read_target()
                lay["video"] = v
                with open(self._layout_target_path(), "w", encoding="utf-8") as f:
                    json.dump(lay, f, indent=4, ensure_ascii=False)
                aplicado = getattr(self._window, "_layout_aplicado", None)
                if isinstance(aplicado, dict):
                    aplicado["video"] = dict(v)
            else:
                cfg = self._load_ui_fn() or {}
                cfg["video"] = v
                self._save_ui_fn(cfg)
                self._window._set_video_in_memory(v)
        except Exception as e:
            print(f"[Posiciones] Error al guardar video: {e}")

    # === Fondo (snap como fondo / imagen por plataforma) ===

    def _write_background(self, partial):
        """Fusiona claves en la seccion background del archivo destino,
        reaplica el layout y refresca el fondo en vivo."""
        lay = self._read_layout()
        bg = lay.setdefault("background", {})
        for k, v in partial.items():
            if v in ("", None):
                bg.pop(k, None)
            else:
                bg[k] = v
        with open(self._layout_target_path(), "w", encoding="utf-8") as f:
            json.dump(lay, f, indent=4, ensure_ascii=False)
        self._window._apply_layout(self._window._read_combined_layout())
        self._window._refresh_current_item_background()

    def _snap_background_changed(self):
        """Guarda usar_snap en el archivo destino y aplica en vivo."""
        if self._loading:
            return
        try:
            self._write_background({"use_snap": bool(self.chk_usar_snap.isChecked())})
            estado = tr("activado") if self.chk_usar_snap.isChecked() else tr("desactivado")
            self.lbl_status.setText(tr("Snap como fondo: {estado}", estado=estado))
            self._timer_status.start()
        except Exception as e:
            print(f"[Posiciones] Error al guardar fondo: {e}")

    def _choose_platform_background(self):
        if self._loading:
            return
        start_dir = getattr(self, "_current_bg_path", "") or _BASE_PATH
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Imagen de fondo"), start_dir,
            tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        )
        if not path:
            return
        self._current_bg_path = path
        self.txt_bg_path.setText(path)
        try:
            self._write_background({"image": path})
            self.lbl_status.setText(tr("Fondo fijado"))
            self._timer_status.start()
        except Exception as e:
            print(f"[Posiciones] Error al guardar fondo: {e}")

    def _upload_platform_background(self):
        if self._loading:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Subir imagen de fondo"), _BASE_PATH,
            tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        )
        if not path:
            return
        copied = self._copy_to_custom(path)
        self._current_bg_path = copied
        self.txt_bg_path.setText(copied)
        try:
            self._write_background({"image": copied})
            self.lbl_status.setText(tr("Imagen subida y fondo actualizado"))
            self._timer_status.start()
        except Exception as e:
            print(f"[Posiciones] Error al guardar fondo: {e}")

    def _remove_platform_background(self):
        if self._loading:
            return
        self._current_bg_path = ""
        self.txt_bg_path.setText("")
        try:
            self._write_background({"image": ""})
            self.lbl_status.setText(tr("Fondo quitado"))
            self._timer_status.start()
        except Exception as e:
            print(f"[Posiciones] Error al quitar fondo: {e}")

    # === Snap ===

    def _snap_changed(self):
        """Aplica la posicion del snap en vivo y agenda guardado."""
        if self._loading:
            return
        v = {
            "custom": self.chk_snap.isChecked(),
            "x": self.sp_sx.value(),
            "y": self.sp_sy.value(),
            "w": self.sp_sw.value(),
            "h": self.sp_sh.value(),
        }
        self._window._apply_snap_config(v)
        self._timer_snap.start()

    def _save_snap(self):
        try:
            v_real = {
                "custom": self.chk_snap.isChecked(),
                "x": self.sp_sx.value(),
                "y": self.sp_sy.value(),
                "w": self.sp_sw.value(),
                "h": self.sp_sh.value(),
            }
            v = self._window._rect_real_to_stored(v_real)
            if self._system_id():
                lay = self._read_target()
                lay["snap_pos"] = v
                with open(self._layout_target_path(), "w", encoding="utf-8") as f:
                    json.dump(lay, f, indent=4, ensure_ascii=False)
                aplicado = getattr(self._window, "_layout_aplicado", None)
                if isinstance(aplicado, dict):
                    aplicado["snap_pos"] = dict(v)
            else:
                cfg = self._load_ui_fn() or {}
                cfg["snap_pos"] = v
                self._save_ui_fn(cfg)
                self._window._set_snap_in_memory(v)
        except Exception as e:
            print(f"[Posiciones] Error al guardar snap: {e}")

    # === Imagenes personalizadas ===

    def _reload_images(self):
        """Carga la lista de imagenes del layout.json y llena el combo."""
        try:
            lay = self._read_layout()
            self._images = list(lay.get("images", []))
        except Exception as e:
            print(f"[Posiciones] Error al leer imagenes: {e}")
            self._images = []
        has_items = bool(self._images)
        for sp in (self.sp_ix, self.sp_iy, self.sp_iesc, self.sp_iz):
            sp.setEnabled(has_items)
        self.cmb_img.blockSignals(True)
        self.cmb_img.clear()
        for cfg in self._images:
            name = os.path.basename(cfg.get("path", "")) or "(sin ruta)"
            self.cmb_img.addItem(name)
        self.cmb_img.blockSignals(False)
        if has_items:
            self.cmb_img.setCurrentIndex(0)
            self._image_selected(self.cmb_img.currentIndex())
        else:
            self._selected_image = -1

    def _image_selected(self, idx):
        """Muestra los campos de la imagen seleccionada."""
        self._selected_image = idx if 0 <= idx < len(self._images) else -1
        ok = self._selected_image >= 0
        for sp in (self.sp_ix, self.sp_iy, self.sp_iesc, self.sp_iz):
            sp.setEnabled(ok)
        if not ok:
            return
        c = self._images[self._selected_image]
        try:
            fx, fy = self._window._scale_factors()
        except Exception:
            fx = fy = 1.0
        self._loading = True
        self.sp_ix.setValue(round(int(c.get("x", 0)) * fx))
        self.sp_iy.setValue(round(int(c.get("y", 0)) * fy))
        self.sp_iesc.setValue(float(c.get("scale", 1.0)) * fy * 100.0)
        self.sp_iz.setValue(int(c.get("z", 0)))
        self._loading = False

    def _image_field_changed(self, field, value):
        """Aplica un cambio de posicion/escala en vivo y agenda guardado."""
        if self._loading or not (0 <= self._selected_image < len(self._images)):
            return
        try:
            fx, fy = self._window._scale_factors()
        except Exception:
            fx = fy = 1.0
        if field == "x":
            stored = round(value / fx)
        elif field == "y":
            stored = round(value / fy)
        elif field == "scale":
            stored = round(value / fy, 4)
        else:
            stored = value
        self._images[self._selected_image][field] = stored
        idx = self._selected_image
        self._window._update_image(
            idx,
            x=value if field == "x" else None,
            y=value if field == "y" else None,
            scale=value if field == "scale" else None,
            z=value if field == "z" else None,
        )
        self._timer_imgs.start()

    def _add_image_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Seleccionar imagen"), _BASE_PATH,
            tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        )
        if path:
            self._add_image_path(path)

    def _copy_to_custom(self, path):
        """Copia la imagen a images/personalizadas/ y devuelve la ruta
        relativa de la copia. Si falla, devuelve la ruta original."""
        dest_dir = os.path.join(_BASE_PATH, "images", "personalizadas")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            name = os.path.basename(path)
            base, ext = os.path.splitext(name)
            dest_file = os.path.join(dest_dir, name)
            n = 1
            while os.path.exists(dest_file):
                dest_file = os.path.join(dest_dir, f"{base}_{n}{ext}")
                n += 1
            shutil.copy2(path, dest_file)
            rel = os.path.relpath(dest_file, _BASE_PATH).replace("\\", "/")
            print(f"[Imagen] Copiada a {rel}")
            return rel
        except Exception as e:
            print(f"[Imagen] No se pudo copiar ({e}); se referencia la original")
            return path

    def _add_image_path(self, path):
        """Agrega una imagen: se copia al proyecto y se guarda la copia."""
        path = self._copy_to_custom(path)
        try:
            fx, fy = self._window._scale_factors()
        except Exception:
            fx = fy = 1.0
        self._images.append({
            "path": path,
            "x": round(50 / fx),
            "y": round(50 / fy),
            "scale": round(1.0 / fy, 4),
        })
        self._save_images()
        self._reload_from_disk()
        self._reload_images()
        self.cmb_img.setCurrentIndex(len(self._images) - 1)

    def _remove_image(self):
        if not (0 <= self._selected_image < len(self._images)):
            return
        self._images.pop(self._selected_image)
        self._selected_image = -1
        self._save_images()
        self._reload_from_disk()
        self._reload_images()

    def _save_images(self):
        try:
            lay = self._read_layout()
            lay["images"] = [c for c in self._images if c.get("path")]
            with open(self._layout_target_path(), "w", encoding="utf-8") as f:
                json.dump(lay, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Posiciones] Error al guardar imagenes: {e}")

    def _reload_from_disk(self):
        """Reaplica las imagenes en el frontend sin esperar el hot-reload."""
        try:
            lay = self._read_layout()
            self._window._apply_images(lay.get("images"))
        except Exception as e:
            print(f"[Posiciones] Error al recargar imagenes: {e}")

    # === Restaurar ===

    def restore(self):
        """Vuelve a los valores por defecto de posicion."""
        self._loading = True
        self.sp_base_x.setValue(15.0)
        self.sp_pull_x.setValue(25)
        self.sp_line_ini.setValue(8.0)
        self.sp_line_fin.setValue(78.0)
        self.sp_info_ancho.setValue(350)
        self.chk_fijo.setChecked(False)
        self.sp_vx.setValue(30)
        self.sp_vy.setValue(90)
        self.sp_vw.setValue(490)
        self.sp_vh.setValue(368)
        self.sp_vz.setValue(0)
        self._loading = False
        self._save_layout()
        self._save_video()

    def refresh(self):
        """Recarga los valores al cambiar de plataforma con el panel abierto."""
        self.load_values()

    def save_all(self):
        """Guarda todo de inmediato en el archivo del sistema activo."""
        self._timer_layout.stop()
        self._timer_video.stop()
        self._timer_imgs.stop()
        self._timer_snap.stop()
        self._save_layout()
        self._save_video()
        self._save_snap()
        self._save_images()
        dest_file = os.path.basename(self._layout_target_path())
        self.lbl_status.setText(tr("Guardado en {dest_file}", dest_file=dest_file))
        self._timer_status.start()

    def closeEvent(self, e):
        if (self._timer_layout.isActive() or self._timer_video.isActive()
                or self._timer_imgs.isActive() or self._timer_snap.isActive()):
            self.save_all()
        super().closeEvent(e)

    def show_next_to(self, window):
        geo = window.geometry()
        self.adjustSize()
        self.move(max(0, geo.x() + 40), geo.y() + 80)
        self.show()
        self.raise_()
        self.activateWindow()
