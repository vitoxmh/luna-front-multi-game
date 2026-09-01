"""
focus_nav.py - Navegacion por teclado/gamepad para dialogs.

Filtro global instalado en QApplication. Cuando un dialog registrado esta
visible, las flechas mueven el foco entre controles (navegacion tipo grilla),
Enter/Return activa el control enfocado (boton/combo), Izquierda/Derecha
ajustan el valor de spinboxes/combos y ESC cierra el dialog.

Para permitir que un dialog capture teclas por si mismo (p. ej. el mapeo de
controles), se puede definir el atributo o propiedad ``dpad_nav_skip`` (bool
o callable) sobre el dialog.
"""

from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QAbstractButton, QAbstractSpinBox, QComboBox, QTabBar, QTabWidget
)

_QT_KEY_TO_ACTION = {
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
}


class DpadNav(QObject):
    """Navega con flechas y activa con Enter sobre los dialogs registrados."""

    def __init__(self, app):
        super().__init__(app)
        self._windows = set()
        app.installEventFilter(self)

    # === Registro ===

    def register(self, widget):
        if widget is not None:
            self._windows.add(widget)

    def _skip(self, win):
        if win is None or not win.isVisible():
            return True
        attr = getattr(win, "dpad_nav_skip", None)
        if callable(attr):
            return bool(attr())
        return bool(attr)

    def active(self):
        """Devuelve el dialog registrado visible (y no en modo captura)."""
        for w in list(self._windows):
            if w is not None and not self._skip(w):
                return w
        return None

    def is_visible(self, widget):
        return widget is not None and widget.isVisible()

    def close_active(self):
        win = self.active()
        if win is not None:
            win.close()

    # === Controles candidatos ===

    def _focusables(self, win):
        out = []
        for w in win.findChildren(QWidget):
            if w is win or w.isWindow() or w.isHidden():
                continue
            if not w.isEnabled() or not w.isVisible():
                continue
            if not (w.focusPolicy() & Qt.FocusPolicy.TabFocus):
                continue
            if isinstance(w, QTabWidget):
                continue
            parent = w.parentWidget()
            if isinstance(parent, (QAbstractSpinBox, QComboBox)):
                continue
            out.append(w)
        return out

    def _center(self, win, w):
        return w.mapTo(win, w.rect().center())

    def _first(self, win):
        fs = self._focusables(win)
        if not fs:
            return None
        fs.sort(key=lambda w: (self._center(win, w).y(), self._center(win, w).x()))
        return fs[0]

    def _steer(self, win, cur, dx, dy):
        """Elige el widget mas cercano y alineado en la direccion (dx, dy).

        Se prueba primero un cono estrecho alrededor del eje de movimiento
        (misma fila); si no hay candidato se va relajando el cono, y si ningun
        candidato esta en la direccion se envuelve al extremo opuesto.
        """
        c0 = self._center(win, cur)
        cx0, cy0 = c0.x(), c0.y()
        in_dir = []
        for w in self._focusables(win):
            if w is cur:
                continue
            c = self._center(win, w)
            cx, cy = c.x(), c.y()
            if dx:
                fwd = (cx - cx0) * dx
                perp = abs(cy - cy0)
            else:
                fwd = (cy - cy0) * dy
                perp = abs(cx - cx0)
            if fwd > 0:
                in_dir.append((w, fwd, perp))
        if in_dir:
            rows = [t for t in in_dir if t[2] <= 14]
            if rows:
                rows.sort(key=lambda t: (t[1], t[2]))
                return rows[0][0]
            for tol in (1.0, 2.5, 100.0):
                cone = [t for t in in_dir if t[2] <= t[1] * tol]
                if cone:
                    cone.sort(key=lambda t: (t[1], t[2]))
                    return cone[0][0]
        # No hay candidato: envuelve al extremo opuesto
        best = None
        best_fwd = None
        for w in self._focusables(win):
            if w is cur:
                continue
            c = self._center(win, w)
            cx, cy = c.x(), c.y()
            fwd = (cx - cx0) * dx if dx else (cy - cy0) * dy
            if best_fwd is None or fwd < best_fwd:
                best_fwd = fwd
                best = w
        return best

    # === Acciones ===

    def move(self, action, win=None):
        if win is None:
            win = self.active()
        if win is None:
            return
        fw = QApplication.focusWidget()
        if fw is None or fw.window() is not win:
            first = self._first(win)
            if first is not None:
                first.setFocus()
            return
        if isinstance(fw, QTabBar):
            if action in ("left", "right"):
                return
        if isinstance(fw, QAbstractSpinBox) and action in ("left", "right"):
            if action == "left":
                fw.stepDown()
            else:
                fw.stepUp()
            return
        if isinstance(fw, QComboBox) and action in ("left", "right"):
            idx = fw.currentIndex()
            nxt = idx - 1 if action == "left" else idx + 1
            if 0 <= nxt < fw.count():
                fw.setCurrentIndex(nxt)
            return
        dx = {"left": -1, "right": 1}.get(action, 0)
        dy = {"up": -1, "down": 1}.get(action, 0)
        if not dx and not dy:
            return
        target = self._steer(win, fw, dx, dy)
        if target is not None:
            target.setFocus()

    def activate(self, win=None):
        if win is None:
            win = self.active()
        if win is None:
            return
        fw = QApplication.focusWidget()
        if fw is None or fw.window() is not win:
            fw = self._first(win)
            if fw is None:
                return
            fw.setFocus()
        if isinstance(fw, QAbstractButton):
            fw.click()
        elif isinstance(fw, QComboBox):
            fw.showPopup()

    def _focus_first_in(self, win):
        if self._skip(win):
            return
        fw = win.focusWidget()
        if fw is not None and fw.window() is win:
            return
        first = self._first(win)
        if first is not None:
            first.setFocus()

    # === Filtro de eventos ===

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Show:
            if isinstance(obj, QWidget) and obj in self._windows:
                if obj.isVisible():
                    QTimer.singleShot(0, lambda o=obj: self._focus_first_in(o))
            return False
        if et == QEvent.KeyPress and isinstance(obj, QWidget):
            win = obj.window()
            if win not in self._windows or self._skip(win):
                return False
            key = event.key()
            if key == Qt.Key_Escape:
                win.close()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.activate(win)
                return True
            action = _QT_KEY_TO_ACTION.get(key)
            if action is not None:
                self.move(action, win)
                return True
        return False