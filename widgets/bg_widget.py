"""
bg_widget.py - Widget de fondo fanart con efecto blur/brightness nativo Qt.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QLinearGradient

import os

import paths

_BASE_PATH = str(paths.base_path())


def _resolve_path(path):
    """Resuelve rutas relativas contra la raiz del proyecto."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(_BASE_PATH, path)


def _blur_image(img, radius):
    """Difuminado tipo gaussiano mediante una cadena progresiva de
    escalados con filtrado suave (baja en pasos de ~1/2 y sube en pasos
    de ~2x). Sin FastTransformation: no genera bloques ni dientes."""
    if radius <= 0:
        return img
    w0, h0 = img.width(), img.height()
    if w0 < 2 or h0 < 2:
        return img

    # Fuerza del difuminado: factor de reduccion final proporcional al radio
    factor = max(2.0, min(32.0, radius / 4.0))
    tw = max(1, round(w0 / factor))
    th = max(1, round(h0 / factor))

    # Bajada progresiva (mipmap descendente)
    cur = img
    while cur.width() > tw * 2 and cur.height() > th * 2:
        cur = cur.scaled(
            max(1, cur.width() // 2), max(1, cur.height() // 2),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    cur = cur.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # Subida progresiva (mipmap ascendente): difusion uniforme
    while cur.width() * 2 <= w0 and cur.height() * 2 <= h0:
        cur = cur.scaled(
            cur.width() * 2, cur.height() * 2,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    return cur.scaled(w0, h0, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class BackgroundWidget(QWidget):
    """Widget que muestra una imagen de fondo con blur y brightness."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._pixmap = None
        self._blurred_pixmap = None
        # Cache del ultimo escalado dibujado (evita re-escalar en cada paint)
        self._cache_key = None
        self._cache_pix = None
        self._current_path = ""
        self._blur_radius = 12
        self._brightness = 0.25
        self._scale_factor = 1.15
        # Ajuste de la imagen al tamano exacto de la ventana (ancho x alto)
        self._stretch = False
        # Viñeta configurable
        self._vignette_h_alpha_edges = 230
        self._vignette_h_alpha_center = 20
        self._vignette_v_alpha_edges = 120
        self._vignette_v_alpha_center = 0

    def set_image(self, path):
        resolved_path = _resolve_path(path)
        if not resolved_path:
            return
        try:
            mtime = os.path.getmtime(resolved_path)
        except OSError:
            return
        if resolved_path == self._current_path and mtime == getattr(self, "_current_mtime", 0):
            return
        img = QImage(resolved_path)
        if img.isNull():
            return
        self._current_path = resolved_path
        self._current_mtime = mtime
        self._pixmap = QPixmap.fromImage(img)
        self._rebuild_blurred()
        self.update()

    def clear(self):
        self._pixmap = None
        self._blurred_pixmap = None
        self._cache_key = None
        self._cache_pix = None
        self._current_path = ""
        self.update()

    def set_blur(self, radius):
        if radius != self._blur_radius:
            self._blur_radius = radius
            self._rebuild_blurred()
            self.update()

    def set_brightness(self, b):
        self._brightness = b
        self.update()

    def set_scale(self, s):
        self._scale_factor = s
        self.update()

    def set_stretch(self, enabled):
        """Si esta activo, la imagen se escala exactamente al ancho y alto
        de la ventana (sin respetar proporcion)."""
        if enabled != self._stretch:
            self._stretch = bool(enabled)
            self.update()

    def _rebuild_blurred(self):
        self._cache_key = None
        self._cache_pix = None
        if not self._pixmap:
            self._blurred_pixmap = None
            return
        img = self._pixmap.toImage()
        blurred = _blur_image(img, self._blur_radius)
        self._blurred_pixmap = QPixmap.fromImage(blurred)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()

        if not self._blurred_pixmap:
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(5, 5, 8))
            grad.setColorAt(1, QColor(10, 10, 18))
            painter.fillRect(0, 0, w, h, grad)
            painter.end()
            return

        # Dibujar con brightness (escalado cacheado por tamano/modo)
        painter.setOpacity(self._brightness)
        key = (w, h, self._stretch, self._scale_factor)
        if key != self._cache_key:
            if self._stretch:
                # Ajuste exacto al ancho y alto de la ventana
                self._cache_pix = self._blurred_pixmap.scaled(
                    w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                )
            else:
                # Escalar para cubrir toda la ventana con margen extra
                s = self._scale_factor
                sw, sh = int(w * s), int(h * s)
                sx, sy = (w - sw) / 2, (h - sh) / 2
                self._cache_pix = (
                    self._blurred_pixmap.scaled(
                        sw, sh, Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    ),
                    int(sx), int(sy),
                )
            self._cache_key = key
        if self._stretch:
            painter.drawPixmap(0, 0, self._cache_pix)
        else:
            pix, sx, sy = self._cache_pix
            painter.drawPixmap(sx, sy, pix)
        painter.setOpacity(1.0)

        # Viñeta sobre todo
        grad_h = QLinearGradient(0, 0, w, 0)
        grad_h.setColorAt(0, QColor(0, 0, 0, self._vignette_h_alpha_edges))
        grad_h.setColorAt(0.15, QColor(0, 0, 0, 100))
        grad_h.setColorAt(0.5, QColor(0, 0, 0, self._vignette_h_alpha_center))
        grad_h.setColorAt(0.85, QColor(0, 0, 0, 100))
        grad_h.setColorAt(1, QColor(0, 0, 0, self._vignette_h_alpha_edges))
        painter.fillRect(0, 0, w, h, grad_h)

        grad_v = QLinearGradient(0, 0, 0, h)
        grad_v.setColorAt(0, QColor(0, 0, 0, self._vignette_v_alpha_edges))
        grad_v.setColorAt(0.3, QColor(0, 0, 0, self._vignette_v_alpha_center))
        grad_v.setColorAt(0.7, QColor(0, 0, 0, self._vignette_v_alpha_center))
        grad_v.setColorAt(1, QColor(0, 0, 0, self._vignette_v_alpha_edges))
        painter.fillRect(0, 0, w, h, grad_v)

        painter.end()
