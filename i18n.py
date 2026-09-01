"""
i18n.py - Internacionalizacion (Ingles/Espanol) del Frontend Arcade.

Centraliza las cadenas visibles de la interfaz. El texto fuente esta en
espanol; tr() devuelve la traduccion al ingles cuando el idioma activo es 'en'.

El idioma se guarda en ui_config.json ("language": "es"|"en"). Al cambiar,
se emite una senal para que la ventana principal y los dialogos persistentes
se retraduzcan en vivo (retranslate()).
"""

from PySide6.QtCore import QObject, Signal

# Catalogo: clave (cadena en espanol) -> traduccion al ingles.
# Solo las cadenas UI van aqui. Si no hay clave, tr() devuelve el original
# (funciona como fallback y para el idioma espanol).
_CATALOG = {
    # --- General / botones ---
    "Cerrar": "Close",
    "Salir": "Quit",
    "Restablecer": "Reset",
    "Restaurar": "Restore",
    "Guardar": "Save",
    "Recargar": "Reload",
    "Abrir folder": "Open folder",
    "Examinar...": "Browse...",
    "Subir imagen...": "Upload image...",
    "Quitar": "Remove",
    "Resetear a defaults": "Reset to defaults",
    "Desconocido": "Unknown",
    "Buscar": "Search",

    # --- Ventana principal ---
    "ARCADE": "ARCADE",
    "Luna": "Luna",
    "Shift Config": "Shift Config",
    "Navegar": "Navigate",
    "Seleccionar": "Select",
    "Jugar": "Play",
    "Volver": "Back",
    "Salir": "Quit",
    "Controles": "Controls",
    "Config": "Config",
    "Escribir para buscar": "Type to search",
    "SIN SNAP": "NO SNAP",
    "Emulador: {nombre}": "Emulator: {nombre}",
    "Shift Config": "Shift Config",
    "{nav} Navegar | {sel} Seleccionar | {esc} Salir | Shift Controles | {cfg} Config":
        "{nav} Navigate | {sel} Select | {esc} Quit | Shift Controls | {cfg} Config",
    "{nav} Navegar | {sel} Jugar | {esc} Volver | Shift Controles | Escribir para buscar":
        "{nav} Navigate | {sel} Play | {esc} Back | Shift Controls | Type to search",
    "Tamanio: {s} | Formato: .{e}": "Size: {s} | Format: .{e}",
    "Jugadores: {n}": "Players: {n}",
    "{n} ROMs": "{n} ROMs",
    "{n} ROMs disponibles": "{n} ROMs available",
    "{n} encontrados": "{n} found",
    "Plataforma: {nombre}": "Platform: {nombre}",
    "Lanzando: {nombre}...": "Launching: {nombre}...",
    "Error: {m}": "Error: {m}",
    "Buscando info...": "Searching info...",

    # --- Estado / mensajes principales ---
    "Admin de posiciones activo": "Positions admin active",
    "Editor de layout activo": "Layout editor active",
    "Error al escanear ROMs": "Error scanning ROMs",
    "Emulador en ejecucion...": "Emulator running...",
    "Emulador cerrado": "Emulator closed",
    "Sin resultados": "No results",

    # --- Splash ---
    "ARCADE FRONTEND": "ARCADE FRONTEND",
    "Iniciando...": "Starting...",
    "Cargando configuracion...": "Loading config...",
    "Preparando interfaz...": "Preparing interface...",
    "Aplicando configuracion...": "Applying config...",
    "Verificando emulatores...": "Checking emulators...",
    "Cargando ROMs...": "Loading ROMs...",
    "Primer inicio: generando file_paths base...": "First run: generating base file paths...",

    # --- ConfigDialog ---
    "Administrador de Configuracion": "Configuration Manager",
    "Edita cualquier valor: se aplica en vivo. 'Guardar' lo persiste.":
        "Edit any value: applied live. 'Save' persists it.",
    "COLORES": "COLORS",
    "RUEDA": "WHEEL",
    "FONDO FANART": "FANART BACKGROUND",
    "SNAP": "SNAP",
    "VIDEO (posicion fija)": "VIDEO (fixed position)",
    "RESOLUCION": "RESOLUTION",
    "IDIOMA": "LANGUAGE",
    "Fondo": "Background",
    "Texto": "Text",
    "Seleccionado": "Selected",
    "Acento": "Accent",
    "Texto Dim": "Dim Text",
    "Borde": "Border",
    "Items visibles": "Visible items",
    "Radio": "Radius",
    "Sep. angular": "Angular sep.",
    "Escala central": "Central scale",
    "Escala min": "Min scale",
    "Ancho item": "Item width",
    "Alto item": "Item height",
    "Blur": "Blur",
    "Brillo": "Brightness",
    "Escala": "Scale",
    "Fondo en juegos": "Background in games",
    "Snap del juego": "Game snap",
    "Imagen de fondo": "Background image",
    "Lo que se ve de fondo al navegar los juegos de una plataforma:\n- Snap del juego (si no tiene, el fondo de la plataforma)\n- Fondo de la plataforma (si no tiene, la imagen activa de esta lista)":
        "What is shown as background when browsing the games of a platform:\n- Game snap (if none, the platform background)\n- Platform background (if none, the active image of this list)",
    "Imagen de fondo activa": "Active background image",
    "Agregar imagen(es)...": "Add image(s)...",
    "Quitar la imagen seleccionada": "Remove selected image",
    "Brillo imagen": "Image brightness",
    "Brillo propio de la imagen activa": "Brightness of the active image",
    "Imagen ajustada al ancho y alto de la ventana": "Image stretched to window width and height",
    "Alto max": "Max height",
    "X posicion": "X position",
    "Y posicion": "Y position",
    "Ancho": "Width",
    "Alto": "Height",
    "Usar posicion fija (si no, se alinea al snap)": "Use fixed position (if not, it aligns to the snap)",
    "Automatica (pantalla completa)": "Automatic (fullscreen)",
    "Pantalla completa": "Fullscreen",
    "Seleccionar imagenes de fondo": "Select background images",
    "Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)": "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
    "Seleccionar color": "Select color",
    "Idioma": "Language",
    "BOTONES": "BUTTONS",
    "Configurar botones...": "Configure buttons...",
    "Configura que botones/teclas navegan por los juegos, seleccionan y vuelven.":
        "Configure which buttons/keys browse the games, select and go back.",
    "Abre el mapeo de botones del teclado y del gamepad": "Opens the keyboard and gamepad button mapping",

    # --- ControlsDialog ---
    "Mapeo de Controles": "Controls Mapping",
    "Arriba": "Up",
    "Abajo": "Down",
    "Izquierda": "Left",
    "Derecha": "Right",
    "Aceptar": "Accept",
    "Volver": "Back",
    "Haz clic en una accion, luego presiona el boton/tecla que quieres asignar.":
        "Click an action, then press the button/key you want to assign.",
    "ACTIONS": "ACTIONS",
    "Deadzone del stick:": "Stick deadzone:",
    "Presiona un boton / tecla ...": "Press a button / key ...",
    "(sin asignar)": "(unassigned)",
    "Control detectado: {n}": "Controller detected: {n}",
    "Sin control detectado (solo teclado)": "No controller detected (keyboard only)",

    # --- LayoutEditor ---
    "Editor de Layout (en vivo)": "Layout Editor (live)",
    "Editor de Layout": "Layout Editor",
    "Los cambios se guardan y se aplican al instante": "Changes are saved and applied instantly",

    # --- PosicionesAdmin ---
    "Posiciones": "Positions",
    "Administrador de Posiciones": "Positions Manager",
    "Los cambios se aplican en vivo sobre el frontend": "Changes are applied live on the frontend",
    "Rueda": "Wheel",
    "Fondo": "Background",
    "Panel Info": "Info Panel",
    "Snap": "Snap",
    "Video": "Video",
    "Imagenes": "Images",
    "Posicion horizontal (%)": "Horizontal position (%)",
    "Ajuste fino X": "Fine tune X",
    "Linea inicio (%)": "Start line (%)",
    "Linea fin (%)": "End line (%)",
    "Flecha (indicador)": "Arrow (indicator)",
    "Flecha X (%)": "Arrow X (%)",
    "Flecha Y (%)": "Arrow Y (%)",
    "Tamano flecha": "Arrow size",
    "Posicion horizontal de la flecha": "Horizontal position of the arrow",
    "Posicion vertical de la flecha (50% = centro)": "Vertical position of the arrow (50% = center)",
    "X": "X",
    "Y": "Y",
    "Capa Z": "Z layer",
    "Escala": "Scale",
    "Imagen:": "Image:",
    "Usar snap como fondo": "Use snap as background",
    "El snap del juego se muestra como fondo.\nEn GLOBAL define el valor por defecto (layout.json);\ndentro de una plataforma solo la afecta (layout_<sistema>.json).":
        "The game snap is shown as background.\nIn GLOBAL it defines the default (layout.json);\ninside a platform it only affects it (layout_<system>.json).",
    "Ruta de la imagen de fondo actual": "Path of the current background image",
    "Selecciona una imagen y la copia a images/personalizadas/.\nGuarda la ruta relativa en el layout.":
        "Selects an image and copies it to images/personalizadas/.\nSaves the relative path in the layout.",
    "Busca una imagen existente en tu disco.\nUsa la ruta absoluta seleccionada.":
        "Looks for an existing image on your disk.\nUses the selected absolute path.",
    "Quita el fondo fijo configurado": "Removes the configured fixed background",
    "Posicion personalizada": "Custom position",
    "Saca el snap del panel y lo coloca libre": "Takes the snap out of the panel and places it freely",
    "Posicion fija": "Fixed position",
    "Con Z>=1 compite con las imagenes; empate gana la imagen":
        "With Z>=1 it competes with the images; tie goes to the image",
    "Imagen superpuesta seleccionada": "Selected overlay image",
    "Agregar imagen...": "Add image...",
    "Quitar imagen": "Remove image",
    "0: bajo la interfaz. 1 o mas: sobre el video": "0: below the interface. 1 or more: over the video",
    "Hace permanentes los cambios para este sistema": "Makes the changes permanent for this system",
    "Cierra el administrador (aplica los cambios pendientes)": "Closes the manager (applies pending changes)",
    "Imagen de fondo": "Background image",
    "Seleccionar imagen": "Select image",
    "(sin imagen de fondo)": "(no background image)",
    "(sin ruta)": "(no path)",
    "Ajustando: {sis}": "Adjusting: {sis}",
    "Ajustando: GLOBAL": "Adjusting: GLOBAL",
    "Snap como fondo: {estado}": "Snap as background: {estado}",
    "activado": "enabled",
    "desactivado": "disabled",
    "Fondo fijado": "Background set",
    "Imagen subida y fondo actualizado": "Image uploaded and background updated",
    "Fondo quitado": "Background removed",
    "Guardado en {dest_file}": "Saved to {dest_file}",
    "Subir imagen de fondo": "Upload background image",
    "Vuelve a los valores guardados": "Reverts to the saved values",
    "Paneles": "Panels",
}


class _LanguageSignals(QObject):
    """Senal global para notificar el cambio de idioma en vivo."""
    changed = Signal(str)


_language = "es"
_signals = _LanguageSignals()


def current_language() -> str:
    return _language


def set_language(lang: str):
    """Cambia el idioma activo y notifica a la UI (retranslate)."""
    global _language
    lang = lang if lang in ("es", "en") else "es"
    if lang != _language:
        _language = lang
        try:
            _signals.changed.emit(lang)
        except Exception:
            pass


def language_changed():
    """Devuelve la senal global de cambio de idioma."""
    return _signals.changed


def tr(msg, **kwargs):
    """
    Traduce una cadena UI. Si el idioma es 'en' y existe clave, devuelve la
    traduccion; si se pasan kwargs se hace .format() sobre el resultado.
    """
    out = _CATALOG.get(msg, msg) if _language == "en" else msg
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return out
    return out


# Alias corto para los modulos de interfaz
_ = tr
