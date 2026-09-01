"""
gamepad_manager.py - Deteccion y entrada de gamepads via pygame.

Reemplaza QGamepad de PySide6 que no detecta bien algunos controles
(en particular PS4/DualShock 4) en Windows.
"""

import pygame
from PySide6.QtCore import QObject, QTimer, Signal


# Mapa de botones PS4/estandar a nombres genericos
_BUTTON_MAP_PS4 = {
    0: "ButtonCross",      # X / A
    1: "ButtonCircle",     # O / B
    2: "ButtonSquare",     # [] / X
    3: "ButtonTriangle",   # Triangle / Y
    4: "ButtonL1",
    5: "ButtonR1",
    6: "ButtonL2",
    7: "ButtonR2",
    8: "ButtonShare",      # Select
    9: "ButtonOptions",    # Start
    10: "ButtonL3",        # Click stick izq
    11: "ButtonR3",        # Click stick der
    12: "ButtonDPadUp",
    13: "ButtonDPadDown",
    14: "ButtonDPadLeft",
    15: "ButtonDPadRight",
    16: "ButtonPS",        # Boton PS central
    17: "ButtonTouchpad",  # Click touchpad
}

# Mapa generico (Xbox/Logitech/etc)
_BUTTON_MAP_GENERIC = {
    0: "ButtonA",
    1: "ButtonB",
    2: "ButtonX",
    3: "ButtonY",
    4: "ButtonLB",
    5: "ButtonRB",
    6: "ButtonBack",       # Select
    7: "ButtonStart",      # Start
    8: "ButtonL3",
    9: "ButtonR3",
    10: "ButtonDPadUp",
    11: "ButtonDPadDown",
    12: "ButtonDPadLeft",
    13: "ButtonDPadRight",
}

# Botones comunes para el dialogo de controles
GAMEPAD_BUTTON_NAMES = {
    "ButtonCross": "X / A",
    "ButtonCircle": "O / B",
    "ButtonSquare": "Square / X",
    "ButtonTriangle": "Triangle / Y",
    "ButtonA": "A",
    "ButtonB": "B",
    "ButtonX": "X",
    "ButtonY": "Y",
    "ButtonL1": "LB / L1",
    "ButtonR1": "RB / R1",
    "ButtonL2": "LT / L2",
    "ButtonR2": "RT / R2",
    "ButtonLB": "LB",
    "ButtonRB": "RB",
    "ButtonBack": "Select / Back",
    "ButtonShare": "Share",
    "ButtonStart": "Start / Options",
    "ButtonOptions": "Options",
    "ButtonL3": "L3 (Click)",
    "ButtonR3": "R3 (Click)",
    "ButtonDPadUp": "DPad Up",
    "ButtonDPadDown": "DPad Down",
    "ButtonDPadLeft": "DPad Left",
    "ButtonDPadRight": "DPad Right",
    "ButtonPS": "PS",
    "ButtonTouchpad": "Touchpad",
    "AxisLeftX-": "Left Stick Left",
    "AxisLeftX+": "Left Stick Right",
    "AxisLeftY-": "Left Stick Up",
    "AxisLeftY+": "Left Stick Down",
    "AxisRightX-": "Right Stick Left",
    "AxisRightX+": "Right Stick Right",
    "AxisRightY-": "Right Stick Up",
    "AxisRightY+": "Right Stick Down",
    "AxisL2": "Trigger L2",
    "AxisR2": "Trigger R2",
}


class GamepadDevice:
    """Wrapper de un joystick pygame con estado previo para detectar cambios."""

    def __init__(self, joystick):
        self.joystick = joystick
        self.device_id = joystick.get_id()
        self.name = joystick.get_name()
        self.num_axes = joystick.get_numaxes()
        self.num_buttons = joystick.get_numbuttons()
        self.num_hats = joystick.get_numhats()
        self._prev_buttons = [False] * self.num_buttons
        self._prev_axes = [0.0] * self.num_axes
        self._prev_hats = [(0, 0)] * self.num_hats
        # Detectar si es control PS4 por nombre
        name_lower = self.name.lower()
        self.is_ps4 = any(k in name_lower for k in
                         ("ps4", "dualshock", "dual sense", "sony", "wireless controller"))
        self._button_map = _BUTTON_MAP_PS4 if self.is_ps4 else _BUTTON_MAP_GENERIC

    def get_button_name(self, idx):
        return self._button_map.get(idx, f"Button{idx}")

    def poll(self):
        """Retorna listas de eventos: (buttons_pressed, buttons_released, axes_changed, hats_changed)."""
        buttons_pressed = []
        buttons_released = []
        axes_changed = []
        hats_changed = []

        for i in range(self.num_buttons):
            current = self.joystick.get_button(i)
            prev = self._prev_buttons[i]
            name = self.get_button_name(i)
            if current and not prev:
                buttons_pressed.append(name)
            elif not current and prev:
                buttons_released.append(name)
            self._prev_buttons[i] = bool(current)

        for i in range(self.num_axes):
            current = self.joystick.get_axis(i)
            prev = self._prev_axes[i]
            if abs(current - prev) > 0.1:
                axes_changed.append((i, current))
            self._prev_axes[i] = current

        for i in range(self.num_hats):
            current = self.joystick.get_hat(i)
            prev = self._prev_hats[i]
            if current != prev:
                hats_changed.append((i, current))
            self._prev_hats[i] = current

        return buttons_pressed, buttons_released, axes_changed, hats_changed


class GamepadManager(QObject):
    """Detecta gamepads via pygame y emite senales Qt ante cambios."""

    gamepad_connected = Signal(str, str)     # device_id, name
    gamepad_disconnected = Signal(str)       # device_id
    button_pressed = Signal(str, str)        # device_id, button_name
    button_released = Signal(str, str)       # device_id, button_name
    axis_changed = Signal(str, int, float)   # device_id, axis_index, value
    hat_changed = Signal(str, int, int, int) # device_id, hat_index, x, y

    def __init__(self, parent=None, poll_ms=16):
        super().__init__(parent)
        self._devices = {}  # device_id -> GamepadDevice
        self._initialized = False
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.setInterval(poll_ms)
        self._init_pygame()

    def _init_pygame(self):
        try:
            pygame.display.init()
            pygame.joystick.init()
            self._initialized = True
            print(f"[Gamepad] pygame joystick init OK")
            self._detect_devices()
        except Exception as e:
            print(f"[Gamepad] Error al inicializar pygame joystick: {e}")

    def _detect_devices(self):
        """Detecta todos los joysticks conectados."""
        pygame.joystick.quit()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        print(f"[Gamepad] Joysticks detectados: {count}")

        # Dispositivos nuevos
        found_ids = set()
        for i in range(count):
            try:
                js = pygame.joystick.Joystick(i)
                js.init()
                dev_id = f"pygame:{js.get_id()}"
                found_ids.add(dev_id)
                if dev_id not in self._devices:
                    device = GamepadDevice(js)
                    self._devices[dev_id] = device
                    print(f"[Gamepad] Conectado: {device.name} (id={dev_id})")
                    self.gamepad_connected.emit(dev_id, device.name)
            except Exception as e:
                print(f"[Gamepad] Error al init joystick {i}: {e}")

        # Dispositivos desconectados
        for dev_id in list(self._devices.keys()):
            if dev_id not in found_ids:
                del self._devices[dev_id]
                print(f"[Gamepad] Desconectado: {dev_id}")
                self.gamepad_disconnected.emit(dev_id)

    def start(self):
        """Inicia el polling de gamepads."""
        if self._initialized:
            self._poll_timer.start()
            print("[Gamepad] Polling iniciado")

    def stop(self):
        """Detiene el polling."""
        self._poll_timer.stop()

    def _poll(self):
        """Polling periodico: detecta cambios y emite senales."""
        if not self._initialized:
            return

        pygame.event.pump()

        # Verificar si cambio el numero de joysticks
        current_count = pygame.joystick.get_count()
        if current_count != len(self._devices):
            self._detect_devices()

        # Poll cada dispositivo
        for dev_id, device in list(self._devices.items()):
            try:
                pressed, released, axes, hats = device.poll()
                for btn in pressed:
                    self.button_pressed.emit(dev_id, btn)
                for btn in released:
                    self.button_released.emit(dev_id, btn)
                for axis_idx, value in axes:
                    self.axis_changed.emit(dev_id, axis_idx, value)
                for hat_idx, (hx, hy) in hats:
                    self.hat_changed.emit(dev_id, hat_idx, hx, hy)
            except pygame.error:
                # Joystick desconectado
                del self._devices[dev_id]
                self.gamepad_disconnected.emit(dev_id)

    def get_devices(self):
        """Retorna dict de device_id -> GamepadDevice."""
        return dict(self._devices)

    def get_device_names(self):
        """Retorna lista de (device_id, name) para todos los dispositivos."""
        return [(dev_id, dev.name) for dev_id, dev in self._devices.items()]
