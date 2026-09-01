"""
wheel_widget.py - Rueda/carousel 3D estilo Hyperspin con QPainter.

Renderiza items con efecto 3D usando posicion sin/cos, scale por distancia,
opacity y blur simulado. Navegacion por teclado y raton con transiciones
animadas (QVariantAnimation + easing) y rotateY real via transform.
"""

import math
import os
import sys
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    Qt, Signal, QTimer, QRectF, QPointF,
    QVariantAnimation, QAbstractAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPen, QBrush,
    QLinearGradient, QPixmap, QImage, QTransform, QPainterPath
)

import paths

_BASE_PATH = str(paths.base_path())

# Fuente disponible en cada plataforma (Qt hara fallback si falta)
UI_FONT = "Segoe UI" if sys.platform == "win32" else "Noto Sans"


def _resolve_path(path):
    """Resuelve rutas relativas contra la raiz del proyecto."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(_BASE_PATH, path)


class WheelItem:
    """Un item en la rueda."""

    def __init__(self, index, name, image_path="", meta=None):
        self.index = index
        self.name = name
        self.image_path = image_path
        self.meta = meta or {}
        self._pixmap_cache = None
        self._pixmap_path = None

    def get_pixmap(self):
        """Pixmap a resolucion nativa (se scale al dibujar, sin perdida al ampliar)."""
        path = _resolve_path(self.image_path)
        if not path or not os.path.isfile(path):
            return None
        if self._pixmap_path == path and self._pixmap_cache:
            return self._pixmap_cache
        img = QImage(path)
        if img.isNull():
            return None
        self._pixmap_cache = QPixmap.fromImage(img)
        self._pixmap_path = path
        return self._pixmap_cache


class WheelWidget(QWidget):
    """Widget custom que dibuja una rueda/carousel 3D estilo Hyperspin."""

    selection_changed = Signal(object)  # Emite WheelItem seleccionado
    selection_enter = Signal(object)     # Emite WheelItem al presionar Enter

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.items = []
        self.current_index = 0
        self._float_center = 0.0
        self._scroll_accumulated = 0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(16)
        self._scroll_timer.timeout.connect(self._tick_scroll)

        # Animacion suave de la rueda (QVariantAnimation)
        self.anim_duration = 240
        self.anim_max_duration = 650
        self.anim_easing = QEasingCurve.Type.OutCubic
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_anim_value)

        # Parametros de la rueda (configurables desde layout.json)
        self.visible_items = 13
        self.radius = 320
        self.angular_separation = 8.0
        self.central_scale = 1.4
        self.min_scale = 0.3
        self.selection_scale = 1.35
        self.image_height_percent = 0.9
        self.item_width = 300
        self.item_height = 70
        self.base_x_percent = 0.15
        self.pull_in_x = 25
        self.line_x_start_percent = 0.08
        self.line_x_end_percent = 0.78
        self.indicator_x_percent = 0.03
        self.indicator_y_percent = 0.5
        self.indicator_size = 12
        self.font_size_selected = 17
        self.font_size_normal = 15
        self.font_min_size = 8
        self.selected_opacity = 1.0
        self.normal_opacity = 0.2
        self.scroll_max_steps = 3

        # Colores
        self.selected_color = QColor("#ff6600")
        self.text_color = QColor("#ffffff")
        self.dim_text_color = QColor("#888888")
        self.accent_color = QColor("#00ccff")

        self._items_cache = []

    def _on_anim_value(self, value):
        """Actualiza el centro flotante mientras se anima."""
        self._float_center = float(value)
        self.update()

    @staticmethod
    def parse_easing(name):
        """Traduce un string ('out_cubic') a QEasingCurve.Type."""
        table = {
            "linear": QEasingCurve.Type.Linear,
            "in_quad": QEasingCurve.Type.InQuad,
            "out_quad": QEasingCurve.Type.OutQuad,
            "in_out_quad": QEasingCurve.Type.InOutQuad,
            "in_cubic": QEasingCurve.Type.InCubic,
            "out_cubic": QEasingCurve.Type.OutCubic,
            "in_out_cubic": QEasingCurve.Type.InOutCubic,
            "in_back": QEasingCurve.Type.InBack,
            "out_back": QEasingCurve.Type.OutBack,
            "in_out_back": QEasingCurve.Type.InOutBack,
            "out_elastic": QEasingCurve.Type.OutElastic,
            "out_bounce": QEasingCurve.Type.OutBounce,
        }
        if isinstance(name, QEasingCurve.Type):
            return name
        return table.get(name, QEasingCurve.Type.OutCubic)

    def _animate_to(self, index, instant=False):
        """Anima el centro flotante hasta 'index' (re-apuntable mid-flight)."""
        if instant or self.anim_duration <= 1 or not self.isEnabled():
            self._anim.stop()
            self._float_center = float(index)
            self.update()
            return
        if self._anim.state() == QAbstractAnimation.State.Running:
            start = self._anim.currentValue()
        else:
            start = self._float_center
        dist = abs(float(index) - start)
        if dist < 0.001:
            return
        duration = int(min(self.anim_max_duration, self.anim_duration * (1.0 + 0.35 * dist)))
        self._anim.stop()
        self._anim.setDuration(max(60, duration))
        self._anim.setEasingCurve(self.anim_easing)
        self._anim.setStartValue(float(start))
        self._anim.setEndValue(float(index))
        self._anim.start()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        if not enabled and self._anim.state() == QAbstractAnimation.State.Running:
            self._anim.stop()
            self._float_center = float(self.current_index)

    def set_items(self, items_list):
        """Establece la lista de WheelItems."""
        self.items = items_list
        self.current_index = 0
        self._float_center = 0.0
        self._anim.stop()
        self._items_cache = []
        self.update()

    def set_index(self, idx):
        if not self.items:
            return
        idx = max(0, min(len(self.items) - 1, idx))
        if idx != self.current_index:
            self.current_index = idx
            self._items_cache = []
            self.selection_changed.emit(self.items[idx])
            self._animate_to(idx)

    def select_index(self, idx, instant=True):
        """Selecciona un indice sin emitir senal (para busqueda)."""
        if not self.items:
            return
        idx = max(0, min(len(self.items) - 1, idx))
        self.current_index = idx
        self._items_cache = []
        self.selection_changed.emit(self.items[idx])
        self._animate_to(idx, instant=instant)

    def current_item(self):
        if self.items and 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def move(self, delta):
        """Mueve la seleccion por delta posiciones."""
        if not self.items:
            return
        new_index = self.current_index + delta
        new_index = max(0, min(len(self.items) - 1, new_index))
        if new_index != self.current_index:
            self.current_index = new_index
            self._items_cache = []
            self.selection_changed.emit(self.items[new_index])
            self._animate_to(new_index)

    def paintEvent(self, event):
        if not self.items:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w = self.width()
        h = self.height()
        center_y = h / 2
        base_x = w * self.base_x_percent
        half = self.visible_items // 2

        # Centro flotante de la rueda (integer en reposo, fraccional al animar)
        center_idx = float(self._float_center)
        base = int(center_idx)

        # Calcular posiciones de todos los items visibles
        draw_list = []

        for i in range(-half, half + 1):
            idx = base + i
            if idx < 0 or idx >= len(self.items):
                continue

            rel = idx - center_idx
            angle = rel * self.angular_separation
            angle_rad = math.radians(angle)

            # Posicion Y vertical (arco sinusoidal)
            y = center_y + math.sin(angle_rad) * self.radius

            # Posicion X ligeramente curvada
            x = base_x - math.cos(angle_rad) * self.pull_in_x

            # Factor de distancia 0..1
            distance_factor = abs(rel) / half if half > 0 else 0
            distance_factor = min(1.0, distance_factor)

            # Escala lineal del centro al borde
            scale = self.central_scale - distance_factor * (self.central_scale - self.min_scale)

            # Rotacion Y simulada (compresion horizontal)
            rotation = angle * 0.5

            # Opacidad: seleccion = 1.0, demas = 0.2
            is_selected = (idx == self.current_index)
            opacity = 1.0 if is_selected else max(0.08, 0.2 - distance_factor * 0.12)

            # Z-index para orden de pintado
            z = 100 - abs(i)

            draw_list.append((z, idx, x, y, scale, rotation, opacity, is_selected))

        # Ordenar por z (menor z se pinta primero, queda detras)
        draw_list.sort(key=lambda d: d[0])

        for z, idx, x, y, scale, rotation, opacity, is_selected in draw_list:
            item = self.items[idx]
            self._draw_item(painter, item, x, y, scale, rotation, opacity, is_selected, w, h)

        # Linea decorativa central
        self._draw_central_line(painter, w, h)

        # Indicador triangular
        self._draw_indicator(painter, h)

        painter.end()

    def _draw_item(self, painter, item, x, y, scale, rotation, opacity, is_selected, w, h):
        """Dibuja un item individual de la rueda."""
        painter.save()

        # Tamanio del item
        iw = self.item_width * scale
        ih = self.item_height * scale

        # Centrar verticalmente en y
        draw_y = y - ih / 2
        draw_x = x

        # Rotacion Y real: compresion horizontal alrededor del eje central
        cos_factor = math.cos(math.radians(rotation))
        if cos_factor < 0.999:
            pivot_x = draw_x + iw / 2.0
            transform = QTransform()
            transform.translate(pivot_x, 0.0)
            transform.scale(max(0.05, cos_factor), 1.0)
            transform.translate(-pivot_x, 0.0)
            painter.setTransform(transform, True)

        # Aplicar opacity
        painter.setOpacity(opacity)

        # Imagen del item (si existe): se muestra sola, sin texto
        pix = None
        if item.image_path:
            pix = item.get_pixmap()

        content_bottom = draw_y + ih
        content_left, content_right = draw_x, draw_x + iw

        if pix:
            boost = self.selection_scale if is_selected else 1.0
            target_h = ih * self.image_height_percent * boost
            target_w = pix.width() * target_h / max(1, pix.height())
            max_w = iw * 1.25
            if target_w > max_w:
                target_w = max_w
                target_h = pix.height() * target_w / max(1, pix.width())
            ix = draw_x + (iw - target_w) / 2
            iy = draw_y + (ih - target_h) / 2
            painter.drawPixmap(QRectF(ix, iy, target_w, target_h), pix,
                               QRectF(pix.rect()))
            content_bottom = iy + target_h + 4 * scale
            content_left, content_right = ix, ix + target_w

        # Linea inferior de acento en el item seleccionado
        if is_selected:
            pen = QPen(self.selected_color, 2)
            pen.setColor(QColor(self.selected_color.red(), self.selected_color.green(),
                              self.selected_color.blue(), int(100 * opacity)))
            painter.setPen(pen)
            painter.drawLine(QPointF(content_left, content_bottom),
                            QPointF(content_right, content_bottom))

        if pix:
            painter.restore()
            return

        # Texto del nombre (fallback sin imagen)
        font_size = int(self.font_size_selected * scale) if is_selected else int(self.font_size_normal * scale)
        font = QFont(UI_FONT, max(self.font_min_size, font_size))
        font.setWeight(QFont.ExtraBold if is_selected else QFont.DemiBold)
        painter.setFont(font)

        if is_selected:
            painter.setPen(self.selected_color)
        else:
            c = QColor(self.text_color)
            c.setAlpha(int(opacity * 255))
            painter.setPen(c)

        text_rect = QRectF(draw_x + 10 * scale, draw_y, iw - 20 * scale, ih)
        text_flags = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        fm = QFontMetrics(font)
        elided = fm.elidedText(item.name, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, text_flags, elided)

        painter.restore()

    def _draw_central_line(self, painter, w, h):
        """Linea decorativa naranja en el centro vertical."""
        painter.save()
        line_y = h / 2
        line_x1 = w * self.line_x_start_percent
        line_x2 = w * self.line_x_end_percent

        gradient = QLinearGradient(QPointF(line_x1, 0), QPointF(line_x2, 0))
        gradient.setColorAt(0, QColor(255, 140, 0, 0))
        gradient.setColorAt(0.5, QColor(255, 140, 0, 90))
        gradient.setColorAt(1, QColor(255, 140, 0, 0))

        painter.setPen(QPen(QBrush(gradient), 2))
        painter.drawLine(QPointF(line_x1, line_y), QPointF(line_x2, line_y))

        painter.restore()

    def _draw_indicator(self, painter, h):
        """Triangle indicador naranja (flecha) posicion configurable."""
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.selected_color)

        cx = self.width() * self.indicator_x_percent
        cy = h * getattr(self, "indicator_y_percent", 0.5)
        size = self.indicator_size

        path = QPainterPath()
        path.moveTo(cx, cy - size)
        path.lineTo(cx + size * 1.5, cy)
        path.lineTo(cx, cy + size)
        path.closeSubpath()
        painter.drawPath(path)

        painter.restore()

    # --- Navegacion por teclado ---

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_W):
            self.move(-1)
        elif key in (Qt.Key_Down, Qt.Key_S):
            self.move(1)
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.selection_enter.emit(self.current_item())
        else:
            super().keyPressEvent(event)

    # --- Navegacion por raton ---

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if abs(delta) > 10:
            self._scroll_accumulated += 1 if delta > 0 else -1
            if not self._scroll_timer.isActive():
                self._scroll_timer.start()

    def _tick_scroll(self):
        if self._scroll_accumulated == 0:
            self._scroll_timer.stop()
            return
        step = min(self.scroll_max_steps, abs(self._scroll_accumulated))
        if self._scroll_accumulated > 0:
            self.move(-step)
            self._scroll_accumulated -= step
        else:
            self.move(step)
            self._scroll_accumulated += step

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Detectar si clickeo un item
            hit = self._hit_test(event.position().toPoint())
            if hit is not None:
                if hit == self.current_index:
                    self.selection_enter.emit(self.items[hit])
                else:
                    self.set_index(hit)

    def _hit_test(self, pos):
        """Devuelve el indice del item clickeado o None."""
        if not self.items:
            return None

        w = self.width()
        h = self.height()
        center_y = h / 2
        base_x = w * self.base_x_percent
        half = self.visible_items // 2

        for i in range(-half, half + 1):
            idx = self.current_index + i
            if idx < 0 or idx >= len(self.items):
                continue

            angle = i * self.angular_separation
            angle_rad = math.radians(angle)
            y = center_y + math.sin(angle_rad) * self.radius
            x = base_x - math.cos(angle_rad) * self.pull_in_x
            distance_factor = abs(i) / half if half > 0 else 0
            scale = self.central_scale - distance_factor * (self.central_scale - self.min_scale)
            iw = self.item_width * scale
            ih = self.item_height * scale
            draw_y = y - ih / 2

            item_rect = QRectF(x, draw_y, iw, ih)
            if item_rect.contains(QPointF(pos.x(), pos.y())):
                return idx
        return None
