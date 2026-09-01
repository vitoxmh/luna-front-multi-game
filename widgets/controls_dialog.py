"""
controls_dialog.py - Dialogo de mapeo de controles.

6 acciones: arriba, abajo, izquierda, derecha, aceptar, volver.
Clic en la accion -> presiona boton/tecla del gamepad o teclado -> asignado.
"""

import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QFrame, QGridLayout, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal

from gamepad_manager import GAMEPAD_BUTTON_NAMES
from config import DEFAULT_CONTROLS
from i18n import tr, language_changed


ACTIONS = {
    "up": "Arriba",
    "down": "Abajo",
    "left": "Izquierda",
    "right": "Derecha",
    "select": "Aceptar",
    "back": "Volver",
    "close": "Cerrar",
}

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

BTN_STYLE = (
    "QPushButton { background: #1a1a2e; color: #fff; border: 1px solid #444; "
    "border-radius: 4px; padding: 8px 14px; font-size: 13px; }"
    "QPushButton:hover { border-color: #ff6600; }"
)
BTN_CAPTURING_STYLE = (
    "QPushButton { background: #2a1a0e; color: #ff6600; border: 2px solid #ff6600; "
    "border-radius: 4px; padding: 8px 14px; font-size: 13px; }"
)
CLEAR_STYLE = (
    "QPushButton { background: #333; color: #aaa; border-radius: 4px; font-size: 10px; }"
    "QPushButton:hover { background: #cc0000; color: #fff; }"
)


class CaptureButton(QPushButton):
    """Boton que captura input de gamepad o teclado."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capturing = False
        self._values = []
        self._update_display()
        self.clicked.connect(self._start_capture)
        self.setMinimumWidth(240)
        self.setFixedHeight(38)
        self.setStyleSheet(BTN_STYLE)
        self.setFocusPolicy(Qt.StrongFocus)

    def _start_capture(self):
        if self._capturing:
            self._capturing = False
            self._update_display()
            self.setStyleSheet(BTN_STYLE)
            return
        self._capturing = True
        self.setText(tr("Presiona un boton / tecla ..."))
        self.setStyleSheet(BTN_CAPTURING_STYLE)

    def receive_input(self, name):
        if not self._capturing:
            return
        self._values = [name]
        self._capturing = False
        self._update_display()
        self.setStyleSheet(BTN_STYLE)

    def _update_display(self):
        if not self._values:
            self.setText(tr("(sin asignar)"))
            return
        labels = [GAMEPAD_BUTTON_NAMES.get(v, v) for v in self._values]
        self.setText(" / ".join(labels))

    def refresh_text(self):
        if not self._capturing:
            self._update_display()

    def set_values(self, values):
        self._values = list(values) if values else []
        self._capturing = False
        self._update_display()
        self.setStyleSheet(BTN_STYLE)

    def get_values(self):
        return list(self._values)


class ControlsDialog(QDialog):
    """Dialogo de mapeo de controles."""

    controls_saved = Signal(dict)
    controls_closed = Signal()

    def __init__(self, parent=None, gamepad_mgr=None):
        super().__init__(parent)
        self.setWindowTitle("Mapeo de Controles")
        self.setMinimumSize(500, 460)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._config = {}
        self._buttons = {}
        self._action_labels = {}

        self._gamepad_mgr = gamepad_mgr
        if self._gamepad_mgr:
            self._gamepad_mgr.button_pressed.connect(self._on_gp_button)
            self._gamepad_mgr.axis_changed.connect(self._on_gp_axis)
            self._gamepad_mgr.hat_changed.connect(self._on_gp_hat)

        self._build_ui()
        language_changed().connect(self.retranslate)
        self.retranslate()

    def retranslate(self):
        try:
            self.setWindowTitle(tr("Mapeo de Controles"))
            for a, lbl in self._action_labels.items():
                lbl.setText(tr(ACTIONS[a]))
            self._lbl_hint.setText(tr("Haz clic en una accion, luego presiona el boton/tecla que quieres asignar."))
            self._lbl_sep.setText(tr("ACTIONS"))
            self._lbl_dz.setText(tr("Deadzone del stick:"))
            self._btn_reset.setText(tr("Resetear a defaults"))
            self._btn_save.setText(tr("Guardar"))
            self._btn_close.setText(tr("Cerrar"))
            for btn in self._buttons.values():
                btn.refresh_text()
            self._update_status()
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
        vbox = QVBoxLayout(container)
        vbox.setSpacing(12)
        vbox.setContentsMargins(24, 20, 24, 16)

        hint = QLabel("Haz clic en una accion, luego presiona el boton/tecla que quieres asignar.")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setWordWrap(True)
        self._lbl_hint = hint
        vbox.addWidget(hint)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #00ccff; font-size: 12px; padding: 2px 0;")
        vbox.addWidget(self._lbl_status)
        self._update_status()

        self._lbl_sep = self._make_separator("ACTIONS")
        vbox.addWidget(self._lbl_sep)

        grid = QGridLayout()
        grid.setSpacing(10)

        for i, (action, label) in enumerate(ACTIONS.items()):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #ccc; font-size: 14px; font-weight: bold;")
            lbl.setFixedWidth(100)
            self._action_labels[action] = lbl
            grid.addWidget(lbl, i, 0)

            btn = CaptureButton()
            self._buttons[action] = btn
            grid.addWidget(btn, i, 1)

            btn_x = QPushButton("X")
            btn_x.setFixedSize(28, 28)
            btn_x.setStyleSheet(CLEAR_STYLE)
            btn_x.clicked.connect(lambda checked=False, a=action: self._buttons[a].set_values([]))
            grid.addWidget(btn_x, i, 2)

        vbox.addLayout(grid)

        self._dz_frame = QFrame()
        self._dz_frame.setStyleSheet(
            "QFrame { background: rgba(15, 15, 25, 0.85); border: 1px solid #222; "
            "border-radius: 6px; padding: 10px; }"
        )
        dz_layout = QHBoxLayout(self._dz_frame)
        lbl_dz = QLabel("Deadzone del stick:")
        lbl_dz.setStyleSheet("color: #ccc; font-size: 12px;")
        self._lbl_dz = lbl_dz
        dz_layout.addWidget(lbl_dz)
        self._spin_deadzone = QDoubleSpinBox()
        self._spin_deadzone.setRange(0.1, 0.9)
        self._spin_deadzone.setSingleStep(0.05)
        self._spin_deadzone.setDecimals(2)
        self._spin_deadzone.setValue(0.5)
        self._spin_deadzone.setFixedWidth(100)
        self._spin_deadzone.setStyleSheet(
            "QDoubleSpinBox { background: #1a1a2e; color: #fff; border: 1px solid #333; "
            "border-radius: 4px; padding: 4px 8px; font-size: 12px; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; }"
        )
        dz_layout.addWidget(self._spin_deadzone)
        dz_layout.addStretch()
        vbox.addWidget(self._dz_frame)

        vbox.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Resetear a defaults")
        btn_reset.setFixedHeight(38)
        btn_reset.setStyleSheet(
            "QPushButton { background: #444; color: #ccc; padding: 8px 20px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #666; color: #fff; }"
        )
        btn_reset.clicked.connect(self._reset)
        self._btn_reset = btn_reset
        btn_row.addWidget(btn_reset)

        btn_row.addStretch()

        btn_save = QPushButton("Guardar")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet(
            "QPushButton { background: #ff6600; color: white; padding: 8px 32px; "
            "border-radius: 4px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #ff8833; }"
        )
        btn_save.clicked.connect(self._save)
        self._btn_save = btn_save
        btn_row.addWidget(btn_save)

        btn_close = QPushButton("Cerrar")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            "QPushButton { background: #333; color: #ccc; padding: 8px 20px; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #444; color: #fff; }"
        )
        btn_close.clicked.connect(self.close)
        self._btn_close = btn_close
        btn_row.addWidget(btn_close)

        vbox.addLayout(btn_row)
        vbox.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _update_status(self):
        if self._gamepad_mgr:
            devices = self._gamepad_mgr.get_device_names()
            if devices:
                names = ", ".join(n for _, n in devices)
                self._lbl_status.setText(tr("Control detectado: {n}", n=names))
                self._lbl_status.setStyleSheet("color: #00ccff; font-size: 12px; padding: 2px 0;")
                return
        self._lbl_status.setText(tr("Sin control detectado (solo teclado)"))
        self._lbl_status.setStyleSheet("color: #888; font-size: 12px; padding: 2px 0;")

    def _make_separator(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ff6600; font-size: 14px; font-weight: bold; "
            "padding: 4px 0; border-bottom: 1px solid #333;"
        )
        return lbl

    def _get_capturing(self):
        for action, btn in self._buttons.items():
            if btn._capturing:
                return action, btn
        return None, None

    @property
    def dpad_nav_skip(self):
        """Mientras hay captura, las teclas las consume el propio dialog."""
        return self._get_capturing()[1] is not None

    def _on_gp_button(self, device_id, button_name):
        print(f"[Dialog] GP button: {device_id} -> {button_name}")
        action, btn = self._get_capturing()
        if btn:
            print(f"[Dialog]   -> asignando a {action}")
            btn.receive_input(button_name)

    def _on_gp_axis(self, device_id, axis_idx, value):
        deadzone = self._spin_deadzone.value()
        if abs(value) < deadzone:
            return
        axis_names = {
            0: ("AxisLeftX-", "AxisLeftX+"),
            1: ("AxisLeftY-", "AxisLeftY+"),
            2: ("AxisRightX-", "AxisRightX+"),
            3: ("AxisRightY-", "AxisRightY+"),
        }
        names = axis_names.get(axis_idx, ())
        if not names:
            return
        name = names[0] if value < 0 else names[1]
        print(f"[Dialog] GP axis: {device_id} -> {name}")
        action, btn = self._get_capturing()
        if btn:
            btn.receive_input(name)

    def _on_gp_hat(self, device_id, hat_idx, hx, hy):
        print(f"[Dialog] GP hat: {device_id} -> ({hx}, {hy})")
        hat_map = []
        if hy > 0:
            hat_map.append("ButtonDPadUp")
        elif hy < 0:
            hat_map.append("ButtonDPadDown")
        if hx < 0:
            hat_map.append("ButtonDPadLeft")
        elif hx > 0:
            hat_map.append("ButtonDPadRight")
        if hat_map:
            action, btn = self._get_capturing()
            if btn:
                print(f"[Dialog]   -> asignando {hat_map[0]} a {action}")
                btn.receive_input(hat_map[0])

    def _reset(self):
        gp_defaults = DEFAULT_CONTROLS.get("gamepad", {})
        kb_defaults = DEFAULT_CONTROLS.get("keyboard", {})
        dz = DEFAULT_CONTROLS.get("gamepad_deadzone", 0.5)
        for action, btn in self._buttons.items():
            btn.set_values(gp_defaults.get(action, []) or kb_defaults.get(action, []))
        self._spin_deadzone.setValue(dz)

    def load_config(self, config):
        self._config = json.loads(json.dumps(config))
        gamepad = self._config.get("gamepad", {})
        keyboard = self._config.get("keyboard", {})
        for action, btn in self._buttons.items():
            gp_vals = gamepad.get(action, [])
            kb_vals = keyboard.get(action, [])
            btn.set_values(gp_vals or kb_vals)
        dz = self._config.get("gamepad_deadzone", 0.5)
        self._spin_deadzone.blockSignals(True)
        self._spin_deadzone.setValue(dz)
        self._spin_deadzone.blockSignals(False)
        self._update_status()

    def _save(self):
        self._config["gamepad"] = {}
        self._config["keyboard"] = {}
        for action, btn in self._buttons.items():
            vals = btn.get_values()
            if not vals:
                continue
            gp = [v for v in vals if v.startswith("Button") or v.startswith("Axis")]
            kb = [v for v in vals if not v.startswith("Button") and not v.startswith("Axis")]
            if gp:
                self._config["gamepad"][action] = gp
            if kb:
                self._config["keyboard"][action] = kb
        self._config["gamepad_deadzone"] = self._spin_deadzone.value()
        self._config["device"] = "gamepad:pygame:0" if self._config.get("gamepad") else "teclado"
        self.controls_saved.emit(self._config)
        self.close()

    def event(self, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            action, btn = self._get_capturing()
            if btn:
                name = QT_KEY_NAMES.get(key, event.text().upper() if event.text() else "")
                if name:
                    print(f"[Dialog] Key: {name} -> {action}")
                    btn.receive_input(name)
                    return True
            elif key == Qt.Key_Escape:
                self.close()
                return True
        return super().event(event)

    def closeEvent(self, event):
        self.controls_closed.emit()
        super().closeEvent(event)
