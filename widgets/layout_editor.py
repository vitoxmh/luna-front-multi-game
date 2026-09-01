"""
layout_editor.py - Editor visual de layout.json con aplicacion en vivo.

Genera automaticamente controles (spinners, checkboxes, color pickers,
campos de texto) a partir de la estructura de layout.json. Cada cambio
se guarda en el archivo y el hot-reloader del frontend lo aplica al
instante. Se abre con Ctrl+L desde la window principal.
"""

import json
import os
import subprocess
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QPushButton,
    QScrollArea, QColorDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from i18n import tr, language_changed


STYLE = """
QWidget { background: #14141c; color: #ddd; font-size: 12px; }
QLabel[clase="titulo"] { color: #ff6600; font-size: 15px; font-weight: bold; }
QLabel[clase="hint"] { color: #777; font-size: 11px; }
QGroupBox {
    border: 1px solid #2a2a38; border-radius: 6px; margin-top: 10px;
    font-weight: bold; color: #00ccff;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #1e1e2a; border: 1px solid #33334a; border-radius: 4px;
    padding: 2px 4px; min-width: 70px;
}
QPushButton {
    background: #26263a; border: 1px solid #3a3a55; border-radius: 4px;
    padding: 5px 10px;
}
QPushButton:hover { background: #343452; }
QScrollArea { border: none; }
"""


class LayoutEditor(QWidget):
    """Panel flotante que edita layout.json y aplica los cambios en vivo."""

    def __init__(self, json_path, parent=None):
        super().__init__(parent)
        self._path = json_path
        self._data = {}
        self._controls = {}   # (section, key) -> lst de widgets
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(200)
        self._save_timer.timeout.connect(self._save)

        self.setWindowTitle("Editor de Layout (en vivo)")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.resize(340, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QLabel("Editor de Layout")
        title.setProperty("clase", "titulo")
        self._title_lbl = title
        root.addWidget(title)

        hint = QLabel("Los cambios se guardan y se aplican al instante")
        hint.setProperty("clase", "hint")
        self._hint_lbl = hint
        root.addWidget(hint)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._sections_layout = QVBoxLayout(self._container)
        self._sections_layout.setContentsMargins(0, 0, 4, 0)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        btn_row = QHBoxLayout()
        btn_reload = QPushButton("Recargar")
        btn_reload.clicked.connect(self.load_from_disk)
        btn_folder = QPushButton("Abrir folder")
        btn_folder.clicked.connect(self._open_folder)
        self._btn_reload = btn_reload
        self._btn_folder = btn_folder
        btn_row.addWidget(btn_reload)
        btn_row.addWidget(btn_folder)
        btn_row.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.close)
        self._btn_cerrar = btn_cerrar
        btn_row.addWidget(btn_cerrar)

        root.addLayout(btn_row)

        language_changed().connect(self.retranslate)
        self.retranslate()

        self.load_from_disk()

    def retranslate(self):
        try:
            self.setWindowTitle(tr("Editor de Layout (en vivo)"))
            self._title_lbl.setText(tr("Editor de Layout"))
            self._hint_lbl.setText(tr("Los cambios se guardan y se aplican al instante"))
            self._btn_reload.setText(tr("Recargar"))
            self._btn_folder.setText(tr("Abrir folder"))
            self._btn_cerrar.setText(tr("Cerrar"))
        except Exception:
            pass

    # === Carga ===

    def load_from_disk(self):
        """Fuerza la recarga desde el archivo y reconstruye los controles."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception as e:
            print(f"[LayoutEditor] Error al leer: {e}")
            return
        self._rebuild()

    def sync_external(self):
        """Recarga solo si el archivo cambio por fuera del editor."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
        except Exception:
            return
        if json.dumps(disk_data, sort_keys=True) == json.dumps(self._data, sort_keys=True):
            return
        self._data = disk_data
        self._rebuild()

    def _rebuild(self):
        self._clear_controls()

        for section, values in self._data.items():
            if not isinstance(values, dict):
                continue
            box = QGroupBox(section)
            form = QFormLayout(box)
            form.setContentsMargins(8, 14, 8, 8)
            form.setVerticalSpacing(4)
            for key, value in values.items():
                control = self._create_control(section, key, value)
                label = QLabel(key)
                label.setToolTip(f"{section}.{key}")
                form.addRow(label, control)
            self._sections_layout.addWidget(box)

        self._sections_layout.addStretch()

    def _clear_controls(self):
        self._controls.clear()
        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # === Creacion de controles segun tipo ===

    def _create_control(self, section, key, value):
        if isinstance(value, bool):
            return self._ctrl_bool(section, key, value)
        if isinstance(value, int):
            return self._ctrl_int(section, key, value)
        if isinstance(value, float):
            return self._ctrl_float(section, key, value)
        if isinstance(value, str) and value.startswith("#") and len(value) in (7, 9):
            return self._ctrl_color(section, key, value)
        if isinstance(value, list):
            return self._ctrl_list(section, key, value)
        return self._ctrl_text(section, key, str(value))

    def _ctrl_bool(self, section, key, value):
        cb = QCheckBox()
        cb.setChecked(value)
        cb.toggled.connect(lambda v: self._set_value(section, key, v))
        return cb

    def _ctrl_int(self, section, key, value):
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(value)
        sp.valueChanged.connect(lambda v: self._set_value(section, key, int(v)))
        return sp

    def _ctrl_float(self, section, key, value):
        sp = QDoubleSpinBox()
        sp.setRange(-9999.0, 9999.0)
        sp.setDecimals(2)
        sp.setSingleStep(0.05)
        sp.setValue(value)
        sp.valueChanged.connect(lambda v: self._set_value(section, key, float(v)))
        return sp

    def _ctrl_color(self, section, key, value):
        btn = QPushButton(value)
        btn.setMinimumHeight(22)
        color = QColor(value)
        btn.setStyleSheet(
            f"background: {value}; color: {'#000' if color.lightness() > 128 else '#fff'};"
            "border-radius: 4px; font-weight: bold;"
        )
        def choose():
            initial = QColor(btn.text())
            chosen = QColorDialog.getColor(initial, self, f"{section}.{key}")
            if chosen.isValid():
                new_color = chosen.name() if len(btn.text()) == 7 else chosen.name(QColor.HexArgb)
                btn.setText(new_color)
                btn.setStyleSheet(
                    f"background: {new_color}; "
                    f"color: {'#000' if chosen.lightness() > 128 else '#fff'};"
                    "border-radius: 4px; font-weight: bold;"
                )
                self._set_value(section, key, new_color)
        btn.clicked.connect(choose)
        return btn

    def _ctrl_text(self, section, key, value):
        edit = QLineEdit(value)
        edit.editingFinished.connect(
            lambda: self._set_value(section, key, edit.text())
        )
        return edit

    def _ctrl_list(self, section, key, values):
        cont = QWidget()
        h = QHBoxLayout(cont)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        edits = []
        for i, v in enumerate(values):
            if isinstance(v, float):
                sp = QDoubleSpinBox()
                sp.setRange(-9999.0, 9999.0)
                sp.setDecimals(2)
                sp.setValue(v)
                sp.valueChanged.connect(
                    lambda _, idx=i: self._set_list(section, key, idx, sp.value())
                )
            else:
                sp = QSpinBox()
                sp.setRange(-99999, 99999)
                sp.setValue(int(v))
                sp.valueChanged.connect(
                    lambda _, idx=i: self._set_list(section, key, idx, sp.value())
                )
            h.addWidget(sp)
            edits.append(sp)
        cont.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return cont

    # === Actualizacion de datos + guardado ===

    def _set_value(self, section, key, value):
        if section not in self._data or not isinstance(self._data[section], dict):
            return
        self._data[section][key] = value
        self._schedule_save()

    def _set_list(self, section, key, index, value):
        lst = self._data.get(section, {}).get(key)
        if isinstance(lst, list) and 0 <= index < len(lst):
            original = lst[index]
            lst[index] = float(value) if isinstance(original, float) else int(value)
            self._schedule_save()

    def _schedule_save(self):
        self._save_timer.start()

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[LayoutEditor] Error al guardar: {e}")

    def _open_folder(self):
        folder = os.path.dirname(self._path)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "linux":
            subprocess.Popen(["xdg-open", folder])
        else:
            subprocess.Popen(["open", folder])

    # === Posicion por defecto junto a la rueda ===

    def show_next_to(self, window):
        geo = window.geometry()
        self.adjustSize()
        x = geo.x() + geo.width() - self.width() - 40
        y = geo.y() + 80
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
