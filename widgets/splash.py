"""
splash.py - Splash de arranque de LUNA (Frontend Arcade).

Overlay que se incrusta DENTRO de la ventana principal (misma pantalla,
no una ventana separada) mientras se carga la configuracion y se escanean /
generan los archivos base. Se pinta encima de la interfaz y se retira al
terminar la carga.

Dibujo 100% nativo con QPainter:
  - images/splash_fondo.(png|jpg|webp): imagen de fondo (se escala para
    cubrir la pantalla, con veil oscuro para que el texto se lea bien)
  - images/splash.(png|jpg|webp): logo encima del titulo (opcional)
Si no hay fondo, se usa el degradado oscuro con resplandor de siempre.
"""

from pathlib import Path

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QEvent
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter,
    QRadialGradient, QPixmap
)

import paths
from i18n import tr

BASE_PATH = paths.base_path()

_TITLE = ""
_SUBTITLE = "ARCADE FRONTEND"

_LOGO_NAMES = ("splash.png", "splash.jpg", "splash.jpeg", "splash.webp")
_BACKGROUND_NAMES = (
    "splash_fondo.png", "splash_fondo.jpg", "splash_fondo.jpeg",
    "splash_fondo.webp",
)


class SplashScreen(QWidget):
    """Overlay de carga incrustado en la ventana principal (misma pantalla)."""

    # Emitida cuando el splash termino de mostrarse (tras el fade del 100%).
    # Quien lo crea puede esperar esta senal para reafirmar fullscreen/foco.
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # El splash es un overlay que se incrusta dentro de la ventana
        # principal (no una ventana separada a pantalla completa). Se
        # reescala con attach_to() para cubrir la ventana que lo aloja.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._message = "Iniciando..."
        # Barra con interpolacion: _mostrado persigue a _objetivo (0..100)
        self._target = 8.0
        self._displayed = 0.0

        self._logo = self._find_logo()
        self._background = self._find_background()
        # Cache del fondo ya escalado al tamano de la pantalla
        self._background_cache = None
        self._background_cache_key = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # === API ===

    def set_message(self, texto):
        self._message = str(texto)
        self.update()

    def set_progress(self, value):
        """Fija el objetivo de la barra (0..100); se alcanza suavemente."""
        self._target = max(0.0, min(100.0, float(value)))
        self.update()

    def attach_to(self, parent):
        """Incrusta el splash como overlay que cubre a `parent`.

        Hace que el splash se pinte encima de la interfaz de la ventana
        principal (una sola pantalla/ventana) y que la siga en redimensiones.
        """
        parent = parent or QApplication.activeWindow()
        if not parent:
            return
        self.setParent(parent)
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        parent.installEventFilter(self)

    def eventFilter(self, obj, ev):
        # Mantener el overlay acompasado al tamano de la ventana padre.
        if obj is self.parent() and ev.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
            self.raise_()
        return super().eventFilter(obj, ev)

    def close(self):
        """Deja ver el 100% un instante y cierra el splash."""
        self.set_progress(100)
        self._displayed = max(self._displayed, 60.0)
        QTimer.singleShot(400, self._close_now)

    def _close_now(self):
        self._timer.stop()
        self.hide()
        if self.parent() is not None:
            self.parent().removeEventFilter(self)
        self.closed.emit()
        self.deleteLater()

    # === Interno ===

    def _find_logo(self):
        for name in _LOGO_NAMES:
            path = BASE_PATH / "images" / name
            if path.is_file():
                pm = QPixmap(str(path))
                if not pm.isNull():
                    return pm
        return None

    def _find_background(self):
        for name in _BACKGROUND_NAMES:
            path = BASE_PATH / "images" / name
            if path.is_file():
                pm = QPixmap(str(path))
                if not pm.isNull():
                    return pm
        # Fallback: fondo del frontend (assets/luna.jpg)
        fallback = BASE_PATH / "assets" / "luna.jpg"
        if fallback.is_file():
            pm = QPixmap(str(fallback))
            if not pm.isNull():
                return pm
        return None

    def _scaled_background(self, w, h):
        """Fondo escalado para cubrir la pantalla (cacheado por tamano)."""
        key = (w, h)
        if key != self._background_cache_key:
            self._background_cache = self._background.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._background_cache_key = key
        return self._background_cache

    def _tick(self):
        diff = self._target - self._displayed
        if abs(diff) < 0.05:
            if diff != 0:
                self._displayed = self._target
                self.update()
            return
        self._displayed += diff * 0.07
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        if self._background is not None and not self._background.isNull():
            # Imagen de fondo cubriendo la pantalla + veil para legibilidad
            x0 = (w - self._scaled_background(w, h).width()) // 2
            y0 = (h - self._background_cache.height()) // 2
            p.drawPixmap(x0, y0, self._background_cache)
            veil = QLinearGradient(0, 0, 0, h)
            veil.setColorAt(0.0, QColor(0, 0, 0, 185))
            veil.setColorAt(0.5, QColor(0, 0, 0, 105))
            veil.setColorAt(1.0, QColor(0, 0, 0, 200))
            p.fillRect(self.rect(), veil)
        else:
            # Fondo oscuro con resplandor central tenue naranja
            p.fillRect(self.rect(), QColor("#050508"))
            glow = QRadialGradient(w / 2.0, h * 0.45, h * 0.65)
            glow.setColorAt(0.0, QColor(255, 102, 0, 26))
            glow.setColorAt(1.0, QColor(255, 102, 0, 0))
            p.fillRect(self.rect(), glow)

        title_height = int(max(34, min(h * 0.085, 110)))

        y_cursor = h * 0.36

        # Logo opcional encima del titulo
        if self._logo is not None and not self._logo.isNull():
            logo_h = int(h * 0.16)
            logo = self._logo.scaledToHeight(
                logo_h, Qt.TransformationMode.SmoothTransformation
            )
            p.drawPixmap(
                int((w - logo.width()) / 2),
                int(y_cursor - logo_h * 0.9),
                logo,
            )
            y_cursor += logo_h * 0.55

        # Titulo
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPixelSize(title_height)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, title_height * 0.12)
        p.setFont(title_font)
        p.setPen(QColor("#ff6600"))
        p.drawText(QRectF(0, y_cursor - title_height, w, title_height * 1.15),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   tr(_TITLE))
        y_cursor += title_height * 0.95

        # Subtitulo espaciado
        subtitle_font = QFont()
        subtitle_font.setPixelSize(int(max(12, title_height * 0.30)))
        subtitle_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, title_height * 0.42)
        p.setFont(subtitle_font)
        p.setPen(QColor("#8a93a6"))
        p.drawText(QRectF(0, y_cursor - subtitle_font.pixelSize(), w, subtitle_font.pixelSize() * 2.2),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   tr(_SUBTITLE))
        y_cursor += subtitle_font.pixelSize() * 1.9

        # Barra de progreso
        track_w = min(w * 0.42, 720.0)
        x0 = (w - track_w) / 2.0
        bar_y = max(y_cursor + h * 0.02, h * 0.66)
        bar_height = 6.0
        radius = bar_height / 2.0

        track = QRectF(x0, bar_y, track_w, bar_height)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 28))
        p.drawRoundedRect(track, radius, radius)

        frac = max(0.0, min(1.0, self._displayed / 100.0))
        width = max(radius * 2.0 if frac > 0.005 else 0.0, track_w * frac)
        if width > 0:
            grad = QLinearGradient(x0, 0, x0 + track_w, 0)
            grad.setColorAt(0.0, QColor("#ff6600"))
            grad.setColorAt(1.0, QColor("#ffb347"))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x0, bar_y, width, bar_height), radius, radius)

            # Punto luminoso al frente del avance
            cx = x0 + width
            halo = QRadialGradient(cx, bar_y + radius, 14.0)
            halo.setColorAt(0.0, QColor(255, 200, 120, 160))
            halo.setColorAt(1.0, QColor(255, 200, 120, 0))
            p.setBrush(halo)
            p.drawEllipse(QRectF(cx - 14, bar_y + radius - 14, 28, 28))
            p.setBrush(QColor("#ffc46b"))
            p.drawEllipse(QRectF(cx - 3.5, bar_y + radius - 3.5, 7, 7))

        # Porcentaje sobre el extremo derecho de la barra
        f_pct = QFont()
        f_pct.setPixelSize(int(max(11, h * 0.016)))
        p.setFont(f_pct)
        p.setPen(QColor("#5d6673"))
        p.drawText(
            QRectF(x0, bar_y - f_pct.pixelSize() * 1.7, track_w, f_pct.pixelSize() * 1.5),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{int(round(self._displayed))}%",
        )

        # Mensaje de estado bajo la barra
        f_msg = QFont()
        f_msg.setPixelSize(int(max(13, h * 0.022)))
        p.setFont(f_msg)
        p.setPen(QColor("#9aa0ab"))
        p.drawText(
            QRectF(0, bar_y + bar_height + h * 0.018, w, f_msg.pixelSize() * 1.8),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            tr(self._message),
        )
