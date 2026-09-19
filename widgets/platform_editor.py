"""
platform_editor.py - Editor de plataformas/emuladores nativo PySide6.

Permite agregar, editar y eliminar emuladores desde la interfaz.
Se accede desde el ConfigDialog (Shift) en la seccion PLATAFORMAS.
"""

import json
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QMessageBox, QWidget, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

from i18n import tr, language_changed

from config import get_relative_path as _resolve_path


class PlatformEditor(QDialog):
    """Editor de plataformas/emuladores."""

    platforms_changed = Signal()

    ICONS = {
        "arcade": "Arcade",
        "nes": "NES",
        "snes": "SNES",
        "genesis": "Genesis",
        "playstation": "PlayStation",
        "nintendo": "Nintendo",
        "multi": "Multi",
        "naomi": "Naomi",
        "neogeo": "NeoGeo",
        "default": "Otro",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Editor de Plataformas"))
        self.setMinimumSize(680, 520)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._config = {}
        self._editing_id = None
        self._building = False
        self._ui_texts = []
        self._ui_combos = []

        self._build_ui()
        language_changed().connect(self.retranslate)
        self.retranslate()

    def _register_text(self, widget, key):
        self._ui_texts.append((widget, key))

    def retranslate(self):
        try:
            self.setWindowTitle(tr("Editor de Plataformas"))
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
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 10)

        hint = QLabel("Agrega, edita o elimina plataformas. Los cambios se aplican al guardar.")
        hint.setStyleSheet("color: #777; font-size: 11px;")
        hint.setWordWrap(True)
        self._register_text(hint, "Agrega, edita o elimina plataformas. Los cambios se aplican al guardar.")
        layout.addWidget(hint)

        layout.addWidget(self._section_label("PLATAFORMAS EXISTENTES"))

        list_frame = self._make_frame()
        list_layout = QVBoxLayout(list_frame)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: #12121e; color: #fff; border: 1px solid #222; "
            "border-radius: 4px; font-size: 12px; padding: 4px; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #1a1a2e; }"
            "QListWidget::item:selected { background: #1a1a3e; }"
            "QListWidget::item:hover { background: #15152a; }"
        )
        self._list.setMinimumHeight(120)
        list_layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Agregar")
        btn_add.setStyleSheet(
            "QPushButton { background: #1a6b1a; color: #fff; padding: 6px 16px; "
            "border-radius: 4px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #228b22; }"
        )
        btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(btn_add)

        btn_edit = QPushButton("Editar")
        btn_edit.setStyleSheet(
            "QPushButton { background: #1a1a3e; color: #fff; padding: 6px 16px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #2a2a4e; }"
        )
        btn_edit.clicked.connect(self._on_edit)
        btn_row.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setStyleSheet(
            "QPushButton { background: #5a1a1a; color: #fff; padding: 6px 16px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #8b2222; }"
        )
        btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(btn_delete)

        btn_row.addStretch()
        list_layout.addLayout(btn_row)
        layout.addWidget(list_frame)

        layout.addWidget(self._section_label("FORMULARIO"))

        form_frame = self._make_frame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(8)

        self._txt_name = self._make_field("Nombre", form_layout)
        self._txt_executable = self._make_file_field(
            "Ejecutable", form_layout, is_file=True,
            file_filter=tr("Ejecutables (*.exe);;Archivos (*.*)")
        )
        self._txt_launch_args = self._make_field("Args de lanzamiento", form_layout)
        self._txt_launch_args.setPlaceholderText(
            "Placeholders: {rompath} ruta completa | {romdir} carpeta | "
            "{romname} nombre sin ext | {core} core\n"
            "Ej: {romname} -rompath {romdir}"
        )
        self._txt_extensions = self._make_field("Extensiones", form_layout)
        self._txt_extensions.setPlaceholderText(".nes,.zip")
        self._txt_rom_paths = self._make_folder_field("Carpeta ROMs", form_layout)
        self._txt_images_path = self._make_folder_field("Carpeta wheels", form_layout)
        self._txt_videos_path = self._make_folder_field("Carpeta snaps / videos", form_layout)
        self._txt_marquees_path = self._make_folder_field("Carpeta marquee", form_layout)
        self._txt_wheel_img = self._make_file_field(
            "Imagen wheel", form_layout,
            file_filter=tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.svg)")
        )
        self._txt_bg_image = self._make_file_field(
            "Imagen de fondo", form_layout,
            file_filter=tr("Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.svg)")
        )

        icon_row = QHBoxLayout()
        lbl_icon = QLabel("Icono")
        lbl_icon.setFixedWidth(105)
        lbl_icon.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(lbl_icon, "Icono")
        self._cmb_icon = QComboBox()
        self._cmb_icon.addItems(list(self.ICONS.values()))
        self._cmb_icon.setStyleSheet(
            "QComboBox { color: #fff; background: #1a1a2e; padding: 4px; "
            "border-radius: 4px; font-size: 12px; }"
        )
        self._ui_combos.append((self._cmb_icon, list(self.ICONS.values())))
        icon_row.addWidget(lbl_icon)
        icon_row.addWidget(self._cmb_icon, 1)
        form_layout.addLayout(icon_row)

        form_frame.hide()
        self._form_frame = form_frame
        layout.addWidget(form_frame)

        btn_row_bottom = QHBoxLayout()
        btn_row_bottom.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; padding: 8px 24px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background: #444; color: #fff; }"
        )
        btn_cancel.clicked.connect(self._on_cancel)
        self._register_text(btn_cancel, "Cancelar")
        btn_row_bottom.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background: #ff6600; color: white; padding: 8px 24px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #ff8833; }"
        )
        btn_save.clicked.connect(self._on_save)
        self._register_text(btn_save, "Guardar")
        btn_row_bottom.addWidget(btn_save)

        layout.addLayout(btn_row_bottom)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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

    def _make_field(self, label_text, parent_layout):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(105)
        lbl.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(lbl, label_text)
        txt = QLineEdit()
        txt.setStyleSheet(
            "QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; "
            "border-radius: 4px; padding: 4px 8px; font-size: 12px; }"
        )
        row.addWidget(lbl)
        row.addWidget(txt, 1)
        parent_layout.addLayout(row)
        return txt

    def _make_file_field(self, label_text, parent_layout, is_file=True, file_filter=None):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(105)
        lbl.setStyleSheet("color: #ccc; font-size: 12px;")
        self._register_text(lbl, label_text)
        txt = QLineEdit()
        txt.setStyleSheet(
            "QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; "
            "border-radius: 4px; padding: 4px 8px; font-size: 12px; }"
        )
        btn = QPushButton("Examinar...")
        btn.setStyleSheet(
            "QPushButton { background: #26263a; color: #ddd; padding: 4px 10px; "
            "border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background: #343452; }"
        )
        self._register_text(btn, "Examinar...")
        if is_file and file_filter is None:
            file_filter = tr("Ejecutables (*.exe);;Archivos (*.*)")
        if is_file:
            btn.clicked.connect(
                lambda checked=False, t=txt, flt=file_filter: self._browse_file(t, flt)
            )
        else:
            btn.clicked.connect(lambda checked=False: self._browse_folder(txt))
        row.addWidget(lbl)
        row.addWidget(txt, 1)
        row.addWidget(btn)
        parent_layout.addLayout(row)
        return txt

    def _make_folder_field(self, label_text, parent_layout):
        return self._make_file_field(label_text, parent_layout, is_file=False)

    def _browse_file(self, txt_widget, file_filter=None):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Seleccionar archivo"), "",
            file_filter or tr("Ejecutables (*.exe);;Archivos (*.*)")
        )
        if path:
            txt_widget.setText(path)

    def _browse_folder(self, txt_widget):
        path = QFileDialog.getExistingDirectory(
            self, tr("Seleccionar carpeta"), ""
        )
        if path:
            txt_widget.setText(path)

    def load_config(self, config):
        self._config = json.loads(json.dumps(config))
        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        emulators = self._config.get("emulators", {})
        for emu_id, emu_config in emulators.items():
            name = emu_config.get("name", emu_id)
            exe = emu_config.get("executable", "")
            rom_count = self._count_roms(
                emu_config.get("rom_paths", ""),
                emu_config.get("extensions", [])
            )

            display = f"{name}  [{emu_id}]"
            if exe:
                exe_name = Path(exe).stem
                display += f"  - {exe_name}"
            if rom_count:
                display += f"  ({rom_count} ROMs)"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, emu_id)
            self._list.addItem(item)

    def _count_roms(self, rom_paths, extensions):
        """Cuenta solo archivos con las extensiones configuradas."""
        exts = set(e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions)

        def _count_dir(full):
            if not full.exists():
                return 0
            return sum(1 for f in full.iterdir() if f.is_file() and f.suffix.lower() in exts)

        if isinstance(rom_paths, str) and rom_paths:
            return _count_dir(_resolve_path(rom_paths))
        if isinstance(rom_paths, dict):
            total = 0
            for cat_config in rom_paths.values():
                p = cat_config.get("path", "") if isinstance(cat_config, dict) else cat_config
                if p:
                    total += _count_dir(_resolve_path(p))
            return total
        return 0

    def _get_selected_id(self):
        item = self._list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _on_add(self):
        self._editing_id = None
        self._clear_form()
        self._form_frame.show()
        self._txt_name.setFocus()

    def _on_edit(self):
        emu_id = self._get_selected_id()
        if not emu_id:
            return
        self._editing_id = emu_id
        emu_config = self._config.get("emulators", {}).get(emu_id, {})
        self._load_form(emu_config)
        self._form_frame.show()

    def _on_delete(self):
        emu_id = self._get_selected_id()
        if not emu_id:
            return
        emu_config = self._config.get("emulators", {}).get(emu_id, {})
        name = emu_config.get("name", emu_id)

        reply = QMessageBox.question(
            self,
            tr("Eliminar plataforma"),
            tr("Estas seguro de que quieres eliminar '{name}'?", name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self._config["emulators"][emu_id]
            self._refresh_list()
            self.platforms_changed.emit()

    def _on_cancel(self):
        self._form_frame.hide()
        self._editing_id = None
        self._clear_form()

    def _on_save(self):
        name = self._txt_name.text().strip()
        if not name:
            return

        executable = self._txt_executable.text().strip()
        launch_args = self._txt_launch_args.text().strip()
        extensions_str = self._txt_extensions.text().strip()
        rom_paths = self._txt_rom_paths.text().strip()
        images_path = self._txt_images_path.text().strip()
        videos_path = self._txt_videos_path.text().strip()
        marquees_path = self._txt_marquees_path.text().strip()
        wheel_img = self._txt_wheel_img.text().strip()
        bg_image = self._txt_bg_image.text().strip()
        icon_text = self._cmb_icon.currentText()
        icon_key = "default"
        for k, v in self.ICONS.items():
            if v == icon_text:
                icon_key = k
                break

        extensions = [e.strip() for e in extensions_str.split(",") if e.strip()]

        emu_id = self._editing_id
        if not emu_id:
            emu_id = name.lower().replace(" ", "_").replace("-", "_")
            emu_id = ''.join(c for c in emu_id if c.isalnum() or c == '_')
            if emu_id in self._config.get("emulators", {}):
                QMessageBox.warning(
                    self,
                    tr("Plataforma duplicada"),
                    tr("Ya existe una plataforma con el id '{id}'. Cambia el nombre para generar otro id.", id=emu_id)
                )
                return

        emu_config = {
            "name": name,
            "executable": executable,
            "launch_args": launch_args,
            "extensions": extensions,
            "icon": icon_key,
        }
        if rom_paths:
            emu_config["rom_paths"] = rom_paths
        if images_path:
            emu_config["images_path"] = images_path
        if videos_path:
            emu_config["videos_path"] = videos_path
        if marquees_path:
            emu_config["marquees_path"] = marquees_path
        if wheel_img:
            emu_config["wheel_img"] = wheel_img
        if bg_image:
            emu_config["bg_image"] = bg_image

        if "emulators" not in self._config:
            self._config["emulators"] = {}
        self._config["emulators"][emu_id] = emu_config

        if rom_paths:
            rom_full = _resolve_path(rom_paths)
            os.makedirs(rom_full, exist_ok=True)

        self._refresh_list()
        self._form_frame.hide()
        self._editing_id = None
        self._clear_form()
        self.platforms_changed.emit()

    def _clear_form(self):
        self._building = True
        self._txt_name.clear()
        self._txt_executable.clear()
        self._txt_launch_args.clear()
        self._txt_extensions.clear()
        self._txt_rom_paths.clear()
        self._txt_images_path.clear()
        self._txt_videos_path.clear()
        self._txt_marquees_path.clear()
        self._txt_wheel_img.clear()
        self._txt_bg_image.clear()
        idx = self._cmb_icon.findText(self.ICONS.get("default", "Otro"))
        self._cmb_icon.setCurrentIndex(idx if idx >= 0 else 0)
        self._building = False

    def _load_form(self, emu_config):
        self._building = True
        self._txt_name.setText(emu_config.get("name", ""))
        self._txt_executable.setText(emu_config.get("executable", ""))
        self._txt_launch_args.setText(emu_config.get("launch_args", ""))
        extensions = emu_config.get("extensions", [])
        self._txt_extensions.setText(",".join(extensions))
        rom_paths = emu_config.get("rom_paths", "")
        if isinstance(rom_paths, str):
            self._txt_rom_paths.setText(rom_paths)
        else:
            self._txt_rom_paths.setText("")
        self._txt_images_path.setText(emu_config.get("images_path", ""))
        self._txt_videos_path.setText(emu_config.get("videos_path", ""))
        self._txt_marquees_path.setText(emu_config.get("marquees_path", ""))
        self._txt_wheel_img.setText(emu_config.get("wheel_img", ""))
        self._txt_bg_image.setText(emu_config.get("bg_image", ""))
        icon = emu_config.get("icon", "default")
        icon_text = self.ICONS.get(icon, "Otro")
        idx = self._cmb_icon.findText(icon_text)
        if idx >= 0:
            self._cmb_icon.setCurrentIndex(idx)
        self._building = False

    def config(self):
        return self._config

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)
