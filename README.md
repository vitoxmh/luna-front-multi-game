# Luna Frontend - Arcade Wheel (Hyperspin Style)

[English](#english) | [Espanol](#espanol)

---

<a id="english"></a>

## English

Frontend for selecting and launching emulator ROMs with a 3D rotating wheel
in Hyperspin style. Written 100% in native Python with **PySide6** (no
HTML/CSS/JS). Runs on **Windows and Linux**.

### Features

- **3D rotating wheel** for platforms (MAME, NES, SNES, Neo Geo, Naomi...) and a second
  wheel for ROMs.
- Backgrounds with blur/brightness/vignette, animated snap (video or image) per
  game, and info panel.
- Automatic emulator launch configured per platform (RetroArch, MAME, etc.).
- ROM scanning with JSON cache (fast startup).
- Game metadata scraping: year, genre, players, manufacturer (IGDB / RAWG /
  Wikipedia).
- **Gamepad support** via `pygame-ce` (PS4/DualShock 4, Xbox-style controllers).
  Replaces PySide6's `QGamepad` for reliability.
- Configurable keyboard and gamepad mappings (`controls.json`).
- Live layout editor and position manager (Ctrl+L / Ctrl+P).
- ROM search by typing directly.
- Per-platform layout overrides (`layouts/layout_<system>.json`).
- Resolution auto-scaling: layout coordinates adapt to any screen size.
- Hot-reload layout system via `QFileSystemWatcher`.
- **Internationalization** (English/Spanish) with live language switching.
- **PyInstaller support**: packaged as a standalone binary with `paths.py`.
- Custom overlay images with configurable Z-order, position and scale.
- Multi-source background images with per-image brightness and stretch settings.

---

### Requirements

- Python 3.10+ (uses `X | None` syntax)
- PySide6 >= 6.5
- pygame-ce >= 2.5

---

### Installation on Windows

```bat
:: 1. Install Python from https://www.python.org/downloads/
::    IMPORTANT: check "Add Python to PATH"

cd frontend-arcade

:: 2. Virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

:: 3. Dependencies
pip install -r requirements.txt

:: 4. Run
python main.py
```

### Installation on Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv \
    libgl1-mesa-glx libegl1 libxkbcommon0 \
    libfontconfig1 libdbus-1-3

cd frontend-arcade
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Emulators (examples)
sudo apt install -y mame retroarch

python main.py
```

---

### Project Structure

```
frontend-arcade/
├── main.py                 # Entry point: window, wheel, backgrounds, hotkeys
├── backend.py              # Services: scan, launch, scrape, config (Qt signals)
├── launcher.py             # Emulator command builder + subprocess launch
├── scanner.py              # ROM folder scanner + JSON cache
├── scraper.py              # Game metadata (IGDB -> RAWG -> Wikipedia)
├── config.py               # Config load/save/validation + controls
├── gamepad_manager.py      # pygame-ce gamepad detection + polling (Qt signals)
├── i18n.py                 # Internationalization (English/Spanish)
├── paths.py                # Base paths for dev and PyInstaller packaging
│
├── config.json             # Main config: emulators, colors, API keys (gitignored)
├── config.json.example     # Example config to copy as config.json
├── ui_config.json          # Visual config: wheel, background, video, snap (gitignored)
├── controls.json           # Keyboard + gamepad button mappings (gitignored)
│
├── layouts/
│   ├── layout.json         # Global layout: bars, wheel, info, video, background
│   ├── layout_mame.json    # Per-platform override (MAME)
│   ├── layout_naomi.json   # Per-platform override (Naomi)
│   ├── layout_neogeo.json  # Per-platform override (Neo Geo)
│   ├── layout_nes.json     # Per-platform override (NES)
│   └── layout_snes.json    # Per-platform override (SNES)
│
├── widgets/                # Custom PySide6 widgets
│   ├── wheel_widget.py     # 3D carousel wheel (QPainter)
│   ├── bg_widget.py        # Background blur/brightness/vignette
│   ├── config_dialog.py    # Config panel (Shift key)
│   ├── controls_dialog.py  # Gamepad/keyboard mapping dialog
│   ├── focus_nav.py        # D-pad/keyboard navigation for dialogs
│   ├── layout_editor.py    # Live layout editor (Ctrl+L)
│   ├── posiciones_admin.py # Position admin (Ctrl+P)
│   └── splash.py           # Animated splash screen
│
├── roms/<emulator>/        # ROMs (folders created on first run)
├── images/
│   ├── <emulator>/wheel/   # Game logos (wheel)
│   ├── <emulator>/snap/    # Screenshots (.png/.jpg) and videos (.mp4)
│   ├── <emulator>/marquee/ # Arcade banners
│   ├── plataforma/         # Platform logos and backgrounds (versioned)
│   └── personalizadas/     # User custom images (versioned)
├── romslist/               # Scan cache: one JSON per emulator (gitignored)
├── game_cache.json         # Scraper metadata cache (gitignored)
├── assets/
│   ├── luna.jpg            # Splash screen image
│   └── styles/theme.qss    # Qt stylesheet
└── requirements.txt        # Python dependencies
```

> **Note**: `config.json`, `controls.json`, `ui_config.json`, `romslist/`,
> and `game_cache.json` are gitignored. On first run, defaults are generated
> automatically. Copy `config.json.example` to `config.json` to get started.

---

### How It Works

1. **Startup**: animated splash screen; reads `config.json`, verifies emulators,
   and loads scan data.
2. **Cache**: if `romslist/*.json` exists it loads from there (fast); if any
   emulator JSON is missing it rescans automatically. Delete files in `romslist/`
   to force a full rescan.
3. **Platform wheel**: shows available platforms with their logo/background.
4. **ENTER on a platform**: enters the ROM wheel for that system.
5. **ENTER on a ROM**: launches the assigned emulator. Search also filters by
   emulator, avoiding confusion when the same zip exists on two platforms.

---

### config.json - Full Reference

All configuration lives in `config.json`. Edit manually or from the config
panel (**Shift** key). A `config.json.example` is provided as a starting point.

#### General Keys

| Key | Description |
|---|---|
| `app_name` | Name shown in the title bar |
| `theme` | Color theme (`dark`) |
| `fullscreen` | Start in fullscreen (`true`/`false`) |
| `resolution` | Window resolution `[width, height]` |

#### `emulators` Section

Each entry is an emulator/platform. Example:

```json
"mame": {
    "name": "MAME (Arcade)",
    "executable": "retroarch",
    "launch_args": "-L mame2003_plus_libretro --fullscreen {rompath}",
    "extensions": [".zip"],
    "rom_paths": "roms/mame",
    "wheel_img": "images/plataforma/mame.png",
    "bg_image": "images/plataforma/bg-arcade.jpg",
    "images_path": "images/mame/wheel",
    "videos_path": "images/mame/snap",
    "marquees_path": "images/mame/marquee",
    "icon": "arcade"
}
```

| Key | Description |
|---|---|
| `name` | Display name in the platform wheel |
| `executable` | Absolute path or command for the emulator |
| `launch_args` | Launch arguments (see placeholders) |
| `extensions` | ROM extensions recognized by the scanner |
| `rom_paths` | ROM folder(s): string or dict (see below) |
| `wheel_img` | Platform logo in the wheel |
| `bg_image` | Default background for the platform |
| `images_path` / `videos_path` / `marquees_path` | Folders for game wheels/snaps/marquees |
| `icon` | Emoji icon for the category (`arcade`, `nes`, `snes`, `neogeo`...) |

#### `launch_args` Placeholders

| Placeholder | Value |
|---|---|
| `{rompath}` | Full ROM path, quoted |
| `{romdir}` | Directory containing the ROM, quoted |
| `{romname}` | Filename without extension or path |
| `{core}` | RetroArch core from the subcategory (if any) |

Examples:

```text
MAME:      -L mame2003_plus_libretro --fullscreen {rompath}
RetroArch: -L fbneo_libretro.dll --fullscreen {rompath}
```

If `launch_args` is not defined, `{rompath}` is used by default.

#### Executable Search Order

When `executable` is not an existing absolute path:

1. System `PATH` variable.
2. Linux: `/usr/bin`, `/usr/local/bin`, `/snap/bin`, `/opt/<name>/<name>`,
   `/usr/games`.
3. Windows: drives `C:\ D:\ E:\` inside `Emuladores\`, `Program Files\`,
   `Program Files (x86)\` with pattern `<folder>\<name>\<name>.exe`.

#### `rom_paths`: Simple vs Subcategories

**Simple** (one folder per emulator):

```json
"rom_paths": "roms/neogeo"
```

**Subcategories** (one emulator, multiple systems -- typical for RetroArch):

```json
"retroarch": {
    "extensions": [".zip", ".nes"],
    "rom_paths": {
        "nes":  { "name": "NES", "path": "roms/nes",  "core": "fceumm" },
        "snes": { "name": "SNES", "path": "roms/snes", "core": "snes9x" }
    }
}
```

Each subcategory accepts `bg_image`, `wheel_img`, `images_path`,
`marquees_path`, and `videos_path` (inherited from the emulator if missing).
The `core` is substituted in `{core}` within `launch_args`.

#### `colors` Section

Interface color palette:

```json
"colors": {
    "background": "#0a0a0f",
    "text": "#ffffff",
    "selected": "#ff6600",
    "accent": "#00ccff",
    "active_category": "#ffcc00",
    "borders": "#333333"
}
```

#### `igdb` and `rawg` Sections (Scraping)

Game metadata is fetched in this order: IGDB -> RAWG -> Wikipedia.
Results are cached in `game_cache.json`.

```json
"igdb": { "client_id": "", "client_secret": "", "enabled": false },
"rawg": { "api_key": "...", "enabled": true }
```

- **IGDB**: requires Twitch API credentials (`client_id` + `client_secret`).
- **RAWG**: a free API key from rawg.io is sufficient.

Without API keys configured, the Wikipedia fallback works without registration.

---

### Image Organization

For each ROM, the following resources are searched (in order):

**Wheel (logo in the wheel)**

1. `images_path` of the platform/subcategory in config.json
2. `images/<emulator>/<category>/wheel/<name>.<ext>`
3. `images/<category>/wheel/` -> `images/<emulator>/wheel/` -> `images/wheel/`

**Snap (screenshot/video)** -- video is prioritized over image

1. Configured `videos_path`
2. `images/<emulator>/<category>/snap/<name>.<ext>`
3. `images/<category>/snap/` -> `images/<emulator>/snap/` -> `images/snap/`

**Marquee (arcade banner)**

1. Configured `marquees_path`
2. `images/<emulator>/<category>/marquee/<name>.<ext>`
3. `images/<category>/marquee/` -> `images/<emulator>/marquee/` -> `images/marquee/`

Accepted extensions: `.png .jpg .jpeg .gif .bmp .webp .svg` (image) and
`.mp4 .avi .mkv .webm .mov` (video).

The `images/plataforma/` and `images/personalizadas/` folders are versioned in
git (`.gitignore` exceptions); the rest of `images/` is not uploaded.

---

### Backgrounds

Background priority for a platform:

1. Active global image from the Shift panel (`ui_config.json` -> `background.images`)
2. Platform override: `layout_<system>.json` -> `background.image`
3. `config.json` -> `emulators[].bg_image` (or the subcategory's)
4. Global layout: `layouts/layout.json` -> `background.image`
5. Automatic search in `images/<...>/fondo/`
6. Fallback: the platform's wheel image

In ROM mode, if "use snap as background" is enabled, the game's snap becomes
the background. Priority:
`layout_<system>.json` > `layout.json` > Shift config > enabled by default.

---

### Layout System

- `layouts/layout.json`: global layout with sections `window`, `top_bar`,
  `bottom_bar`, `info_panel`, `wheel`, `video`, `background`, `snap`.
- `layouts/layout_<system>.json` (e.g. `layout_mame.json`): per-platform
  override; any present section takes priority over the global one.

Edit from the built-in managers: **Ctrl+L** (live layout editor) and **Ctrl+P**
(wheel/info/video positions).

All layout coordinates are stored relative to a `base_resolution` and
dynamically rescaled to fit any screen size. Changes are hot-reloaded via
`QFileSystemWatcher` without restarting the app.

Per-platform layout files can also define:
- `images`: custom overlay images with `x`, `y`, `scale`, `z` (Z-order)
- `video`: video player position (`x`, `y`, `w`, `h`, `fixed`)
- `snap_pos`: snap position, supports `custom: true` for free placement
- `wheel`: wheel position overrides (`base_x_percent`, `indicator_x_percent`, etc.)

---

### Gamepad Support

The app uses `pygame-ce` (Community Edition) for gamepad input instead of
PySide6's `QGamepad`, which has reliability issues with PS4 controllers on
Windows.

- Automatic PS4/DualShock 4 detection by device name.
- Separate button maps for PS4 vs generic Xbox-style controllers.
- Hot-plug detection (polling for connect/disconnect).
- Configurable deadzone for analog sticks.
- All mappings customizable via the **Controls** tab in the Shift config panel
  or by editing `controls.json` directly.

---

### Internationalization

The app supports **English** and **Spanish** with live language switching.
- The active language is stored in `ui_config.json` (`"language": "es"|"en"`).
- Change it from the config panel (**Shift** -> LANGUAGE section).
- All UI strings are translated via `i18n.py` using a catalog system.
- Changing the language retraduces the interface instantly without restart.

---

### Keyboard Shortcuts

| Key | Action |
|---|---|
| Up/Down or W/S | Navigate the wheel |
| ENTER / SPACE | Enter category / Launch ROM |
| Left/Right | Page through long lists |
| ESC | Back / Exit fullscreen |
| F11 | Toggle fullscreen |
| Shift | Configuration panel |
| Ctrl+L | Live layout editor |
| Ctrl+P | Position manager |
| Type letters | Search ROM by name |
| Backspace | Clear search |
| Mouse wheel | Navigate the wheel |
| Click | Select item |

---

### Adding a New Emulator

1. Edit `config.json` and add an entry in `emulators`.
2. Define `executable`, `launch_args`, `extensions`, and `rom_paths`.
3. Create the ROM folder and copy your games there.
4. (Optional) Add wheels in `images/<emu>/wheel/` and snaps in
   `images/<emu>/snap/` with the same name as the zip.
5. Delete the corresponding JSON in `romslist/` (or all) and restart.

---

### Packaging with PyInstaller

The app supports PyInstaller packaging via `paths.py`:
- In development, `BASE_PATH` points to the project root.
- When frozen (`sys.frozen`), read-only bundle data comes from `sys._MEIPASS`
  while editable/config files live next to the executable.
- This allows `config.json`, `romslist/`, `images/`, etc. to persist across
  runs when packaged as a standalone `.exe`.

```bash
pyinstaller --onefile --add-data "assets;assets" --add-data "layouts;layouts" main.py
```

---

### Troubleshooting

**"Executable not found"**
Verify the path in `config.json`; if using only the name, it must be in PATH
or in the search folders described above.

**New ROMs not appearing**
Scanning uses cache: delete `romslist/<emulator>.json` and restart. If you
created a new emulator, rescanning is automatic.

**ROM launches with the wrong emulator**
Happens when the same file exists on two platforms. Launching filters by the
active platform's emulator; verify the zip is in the correct `rom_paths` folder.

**PySide6 won't install**
Linux: install `libgl1-mesa-glx libegl1` first. Windows: verify Python is in
PATH.

**No video/snaps**
Check that `images/<emu>/snap/<rom_name>.mp4|.png` exists using the same base
name as the ROM's ZIP file.

**Gamepad not detected**
Ensure `pygame-ce` is installed (`pip install pygame-ce`). On Linux, you may
need `sudo usermod -a -G input $USER` and a logout/login.

---

### License

Free project. Uses PySide6 (LGPL), pygame-ce (LGPL), and Python.

---

<a id="espanol"></a>

## Espanol

Frontend para seleccionar y lanzar ROMs de emuladores con rueda giratoria 3D
estilo Hyperspin. Escrito 100% en Python nativo con **PySide6** (sin
HTML/CSS/JS). Funciona en **Windows y Linux**.

### Caracteristicas

- **Rueda 3D giratoria** de plataformas (MAME, NES, SNES, Neo Geo, Naomi...) y segunda
  rueda con las ROMs.
- Fondos con blur/brillo/vignette, snap animado (video o imagen) por juego y
  panel de informacion.
- Lanzamiento automatico del emulador configurado por plataforma (RetroArch,
  MAME, etc.).
- Escaneo de ROMs con cache en JSON (arranque rapido).
- Scraping de info de juegos: anio, genero, jugadores, fabricante (IGDB / RAWG /
  Wikipedia).
- **Soporte de gamepad** via `pygame-ce` (PS4/DualShock 4, controles estilo
  Xbox). Reemplaza `QGamepad` de PySide6 por fiabilidad.
- Mapeos de teclado y gamepad configurables (`controls.json`).
- Editor de layout en vivo y administrador de posiciones (Ctrl+L / Ctrl+P).
- Busqueda de ROMs escribiendo directamente.
- Overrides de layout por plataforma (`layouts/layout_<sistema>.json`).
- Auto-escalamiento de resolucion: las coordenadas del layout se adaptan a
  cualquier tamano de pantalla.
- Sistema de layout con hot-reload via `QFileSystemWatcher`.
- **Internacionalizacion** (ingles/espanol) con cambio de idioma en vivo.
- **Soporte PyInstaller**: empaquetable como binario standalone con `paths.py`.
- Imagenes overlay personalizables con Z-order, posicion y escala configurables.
- Imagenes de fondo multi-fuente con brillo y ajuste por imagen.

---

### Requisitos

- Python 3.10+ (usa sintaxis `X | None`)
- PySide6 >= 6.5
- pygame-ce >= 2.5

---

### Instalacion en Windows

```bat
:: 1. Instalar Python desde https://www.python.org/downloads/
::    IMPORTANTE: marcar "Add Python to PATH"

cd frontend-arcade

:: 2. Entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate

:: 3. Dependencias
pip install -r requirements.txt

:: 4. Ejecutar
python main.py
```

### Instalacion en Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv \
    libgl1-mesa-glx libegl1 libxkbcommon0 \
    libfontconfig1 libdbus-1-3

cd frontend-arcade
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Emuladores (ejemplos)
sudo apt install -y mame retroarch

python main.py
```

---

### Estructura del proyecto

```
frontend-arcade/
├── main.py               # Punto de entrada: ventana, rueda, fondos, atajos
├── backend.py            # Servicios: escaneo, lanzamiento, scraping, config
├── launcher.py           # Construccion del comando y ejecucion del emulador
├── scanner.py            # Escaneo de carpetas de ROMs y cache JSON
├── scraper.py            # Info de juegos desde IGDB / RAWG / Wikipedia
├── config.py             # Carga/guardado/validacion de config.json + controles
├── gamepad_manager.py    # Deteccion y polling de gamepad via pygame-ce
├── i18n.py               # Internacionalizacion (ingles/espanol)
├── paths.py              # Rutas base para desarrollo y empaquetado PyInstaller
│
├── config.json           # Config principal (gitignored, se genera en el primer arranque)
├── config.json.example   # Ejemplo de config para copiar como config.json
├── ui_config.json        # Config visual (rueda, fondo, snap) (gitignored)
├── controls.json         # Mapeos de teclado y botones de gamepad (gitignored)
│
├── layouts/
│   ├── layout.json       # Layout global (barras, paneles, video)
│   ├── layout_mame.json  # Override de layout para MAME
│   ├── layout_naomi.json # Override de layout para Naomi
│   ├── layout_neogeo.json# Override de layout para Neo Geo
│   ├── layout_nes.json   # Override de layout para NES
│   └── layout_snes.json  # Override de layout para SNES
│
├── widgets/              # Widgets PySide6 propios
│   ├── wheel_widget.py       # Rueda 3D custom (QPainter)
│   ├── bg_widget.py          # Fondo con blur/brillo/vignette
│   ├── config_dialog.py      # Panel de configuracion (Shift)
│   ├── controls_dialog.py    # Dialogo de mapeo gamepad/teclado
│   ├── focus_nav.py          # Navegacion D-pad/teclado en dialogos
│   ├── layout_editor.py      # Editor de layout en vivo (Ctrl+L)
│   ├── posiciones_admin.py   # Posiciones rueda/info/video (Ctrl+P)
│   └── splash.py             # Splash screen animado
│
├── roms/<emulador>/      # ROMs (las carpetas se crean al primer arranque)
├── images/
│   ├── <emulador>/wheel/     # Logos de juegos (rueda)
│   ├── <emulador>/snap/      # Capturas (.png/.jpg) y videos (.mp4)
│   ├── <emulador>/marquee/   # Banners tipo arcade
│   ├── plataforma/           # Logos y fondos de cada plataforma (versionado)
│   └── personalizadas/       # Imagenes propias del usuario (versionado)
├── romslist/             # Cache del escaneo: un JSON por emulador (gitignored)
├── game_cache.json       # Cache del scraper (gitignored)
├── assets/
│   ├── luna.jpg          # Imagen del splash screen
│   └── styles/theme.qss  # Stylesheet Qt
└── requirements.txt      # Dependencias Python
```

> **Nota**: `config.json`, `controls.json`, `ui_config.json`, `romslist/` y
> `game_cache.json` estan en `.gitignore`. En el primer arranque se generan
> automaticamente con valores por defecto. Copia `config.json.example` a
> `config.json` para empezar.

---

### Flujo de funcionamiento

1. **Arranque**: splash animado; lee `config.json`, verifica emuladores y carga
   el escaneo.
2. **Cache**: si existe `romslist/*.json` se carga de ahi (rapido); si falta el
   JSON de algun emulador del config, re-escanea el disco automaticamente. Para
   forzar un re-escaneo completo borra los archivos de `romslist/`.
3. **Rueda de categorias**: muestra las plataformas disponibles con su
   logo/fondo.
4. **ENTER sobre una plataforma**: entra a la rueda de ROMs de ese sistema.
5. **ENTER sobre una ROM**: lanza el emulador asignado a esa ROM. La busqueda
   filtra tambien por emulador, evitando confusiones cuando el mismo zip existe
   en dos plataformas (ej. `kof94.zip` en mame y neogeo).

---

### config.json - Referencia completa

Toda la configuracion vive en `config.json`. Se puede editar a mano o desde el
panel de configuracion (tecla **Shift**). Se incluye `config.json.example` como
punto de partida.

#### Claves generales

| Clave | Descripcion |
|---|---|
| `app_name` | Nombre mostrado en la barra superior |
| `theme` | Tema de color (`dark`) |
| `fullscreen` | Arrancar en pantalla completa (`true`/`false`) |
| `resolution` | Resolucion de ventana `[ancho, alto]` |

#### Seccion `emulators`

Cada entrada es un emulador/plataforma. Ejemplo:

```json
"mame": {
    "name": "MAME (Arcade)",
    "executable": "retroarch",
    "launch_args": "-L mame2003_plus_libretro --fullscreen {rompath}",
    "extensions": [".zip"],
    "rom_paths": "roms/mame",
    "wheel_img": "images/plataforma/mame.png",
    "bg_image": "images/plataforma/bg-arcade.jpg",
    "images_path": "images/mame/wheel",
    "videos_path": "images/mame/snap",
    "marquees_path": "images/mame/marquee",
    "icon": "arcade"
}
```

| Clave | Descripcion |
|---|---|
| `name` | Nombre visible en la rueda de plataformas |
| `executable` | Ruta absoluta o comando del emulador |
| `launch_args` | Argumentos de lanzamiento (ver placeholders) |
| `extensions` | Extensiones de ROM que reconoce el escaneo |
| `rom_paths` | Carpeta(s) de ROMs: string o dict (ver abajo) |
| `wheel_img` | Logo de la plataforma en la rueda |
| `bg_image` | Fondo por defecto de la plataforma |
| `images_path` / `videos_path` / `marquees_path` | Carpetas de wheels/snaps/marquees |
| `icon` | Icono emoji de la categoria (`arcade`, `nes`, `snes`, `neogeo`...) |

#### Placeholders de `launch_args`

| Placeholder | Valor |
|---|---|
| `{rompath}` | Ruta completa de la ROM, entre comillas |
| `{romdir}` | Directorio que contiene la ROM, entre comillas |
| `{romname}` | Nombre del archivo sin extension ni ruta |
| `{core}` | Core RetroArch de la subcategoria (si existe) |

Ejemplos:

```text
MAME:      -L mame2003_plus_libretro --fullscreen {rompath}
RetroArch: -L fbneo_libretro.dll --fullscreen {rompath}
```

Si no se define `launch_args` se usa `{rompath}` por defecto.

#### Busqueda del ejecutable

Orden de busqueda cuando `executable` no es una ruta absoluta existente:

1. Variable `PATH` del sistema.
2. Linux: `/usr/bin`, `/usr/local/bin`, `/snap/bin`, `/opt/<nombre>/<nombre>`,
   `/usr/games`.
3. Windows: unidades `C:\ D:\ E:\` dentro de `Emuladores\`, `Program Files\`,
   `Program Files (x86)\` con el patron `<carpeta>\<nombre>\<nombre>.exe`.

#### `rom_paths` simple vs subcategorias

**Simple** (una carpeta por emulador):

```json
"rom_paths": "roms/neogeo"
```

**Subcategorias** (un emulador, varios sistemas; tipico de RetroArch):

```json
"retroarch": {
    "extensions": [".zip", ".nes"],
    "rom_paths": {
        "nes":  { "name": "NES", "path": "roms/nes",  "core": "fceumm" },
        "snes": { "name": "SNES", "path": "roms/snes", "core": "snes9x" }
    }
}
```

Cada subcategoria acepta ademas `bg_image`, `wheel_img`, `images_path`,
`marquees_path` y `videos_path` propios (si faltan, heredan los del emulador).
El `core` se sustituye en `{core}` dentro de `launch_args`.

#### Seccion `colors`

Paleta de la interfaz:

```json
"colors": {
    "background": "#0a0a0f",
    "text": "#ffffff",
    "selected": "#ff6600",
    "accent": "#00ccff",
    "active_category": "#ffcc00",
    "borders": "#333333"
}
```

#### Secciones `igdb` y `rawg` (scraping)

La info de los juegos se obtiene en este orden: IGDB -> RAWG -> Wikipedia.
El resultado queda cacheado en `game_cache.json`.

```json
"igdb": { "client_id": "", "client_secret": "", "enabled": false },
"rawg": { "api_key": "...", "enabled": true }
```

- **IGDB**: requiere credenciales de la API de Twitch (`client_id` +
  `client_secret`).
- **RAWG**: basta una API key gratuita de rawg.io.

Sin claves configuradas, el fallback a Wikipedia funciona sin registrarse.

---

### Organizacion de imagenes

Para cada ROM se buscan (en este orden) estos recursos:

**Wheel (logo en la rueda)**

1. `images_path` de la plataforma/subcategoria en config.json
2. `images/<emulador>/<categoria>/wheel/<nombre>.<ext>`
3. `images/<categoria>/wheel/` -> `images/<emulador>/wheel/` -> `images/wheel/`

**Snap (captura/video del juego)** - prioriza video sobre imagen

1. `videos_path` configurado
2. `images/<emulador>/<categoria>/snap/<nombre>.<ext>`
3. `images/<categoria>/snap/` -> `images/<emulador>/snap/` -> `images/snap/`

**Marquee (banner arcade)**

1. `marquees_path` configurado
2. `images/<emulador>/<categoria>/marquee/<nombre>.<ext>`
3. `images/<categoria>/marquee/` -> `images/<emulador>/marquee/` -> `images/marquee/`

Extensiones aceptadas: `.png .jpg .jpeg .gif .bmp .webp .svg` (imagen) y
`.mp4 .avi .mkv .webm .mov` (video).

Las carpetas `images/plataforma/` y `images/personalizadas/` estan versionadas
en git (excepciones del `.gitignore`); el resto de `images/` no se sube al repo.

---

### Fondos de pantalla

Prioridad para el fondo de una plataforma:

1. Imagen global activa del panel Shift (`ui_config.json` -> `background.images`)
2. Override de la plataforma: `layout_<sistema>.json` -> `background.image`
3. `config.json` -> `emulators[].bg_image` (o el de la subcategoria)
4. Layout global: `layouts/layout.json` -> `background.image`
5. Busqueda automatica en `images/<...>/fondo/`
6. Fallback: la imagen wheel de la plataforma

En modo ROMs, si "usar snap como fondo" esta activo, el snap del juego pasa a
ser el fondo. Orden de esa opcion:
`layout_<sistema>.json` > `layout.json` > config Shift > activado por defecto.

---

### Sistema de layout

- `layouts/layout.json`: layout global con secciones `window`, `top_bar`,
  `bottom_bar`, `info_panel`, `wheel`, `video`, `background`, `snap`.
- `layouts/layout_<sistema>.json` (ej. `layout_mame.json`): override por
  plataforma; cualquier seccion presente tiene prioridad sobre la global.

Se editan desde los administradores integrados: **Ctrl+L** (editor de layout en
vivo) y **Ctrl+P** (posiciones de rueda/info/video).

Todas las coordenadas del layout se almacenan relativamente a una
`base_resolution` y se reescalan dinamicamente para cualquier tamano de
pantalla. Los cambios se recargan automaticamente via `QFileSystemWatcher`
sin reiniciar la aplicacion.

Archivos de layout por plataforma tambien pueden definir:
- `images`: imagenes overlay personalizadas con `x`, `y`, `scale`, `z` (Z-order)
- `video`: posicion del reproductor de video (`x`, `y`, `w`, `h`, `fixed`)
- `snap_pos`: posicion del snap, soporta `custom: true` para colocacion libre
- `wheel`: overrides de posicion de la rueda (`base_x_percent`, `indicator_x_percent`, etc.)

---

### Soporte de gamepad

La app usa `pygame-ce` (Community Edition) para entrada de gamepad en vez del
`QGamepad` de PySide6, que tiene problemas de fiabilidad con controles PS4 en
Windows.

- Deteccion automatica de PS4/DualShock 4 por nombre del dispositivo.
- Mapas de botones separados para PS4 vs controles genericos estilo Xbox.
- Deteccion de hot-plug (polling de conexion/desconexion).
- Deadzone configurable para sticks analogicos.
- Todos los mapeos personalizables desde la pestana **Controles** en el panel
  Shift o editando `controls.json` directamente.

---

### Internacionalizacion

La app soporta **ingles** y **espanol** con cambio de idioma en vivo.
- El idioma activo se guarda en `ui_config.json` (`"language": "es"|"en"`).
- Cambialo desde el panel de configuracion (pestana **Shift** -> seccion IDIOMA).
- Todas las cadenas de la UI se traducen via `i18n.py` usando un sistema de catalogo.
- Cambiar el idioma retraduce la interfaz al instante sin reiniciar.

---

### Atajos de teclado

| Tecla | Accion |
|---|---|
| Arriba/Abajo o W/S | Navegar la rueda |
| ENTER / SPACE | Entrar a categoria / Lanzar ROM |
| Izquierda/Derecha | Cambiar pagina en listas largas |
| ESC | Volver / Salir de pantalla completa |
| F11 | Alternar pantalla completa |
| Shift | Panel de configuracion |
| Ctrl+L | Editor de layout en vivo |
| Ctrl+P | Administrador de posiciones |
| Letras | Buscar ROM por nombre |
| Backspace | Borrar busqueda |
| Rueda del mouse | Navegar la rueda |
| Click | Seleccionar item |

---

### Agregar un nuevo emulador

1. Edita `config.json` y anade una entrada en `emulators`.
2. Define `executable`, `launch_args`, `extensions` y `rom_paths`.
3. Crea la carpeta de ROMs y copia ahi tus juegos.
4. (Opcional) Anade wheels en `images/<emu>/wheel/` y snaps en
   `images/<emu>/snap/` con el mismo nombre del zip.
5. Borra el JSON correspondiente de `romslist/` (o todos) y reinicia.

---

### Empaquetado con PyInstaller

La app soporta empaquetado con PyInstaller via `paths.py`:
- En desarrollo, `BASE_PATH` apunta a la raiz del proyecto.
- Cuando esta empaquetado (`sys.frozen`), los datos de solo lectura vienen de
  `sys._MEIPASS` mientras que los archivos editables/config viven junto al ejecutable.
- Esto permite que `config.json`, `romslist/`, `images/`, etc. persistan entre
  ejecuciones cuando se empaquetan como un `.exe` standalone.

```bash
pyinstaller --onefile --add-data "assets;assets" --add-data "layouts;layouts" main.py
```

---

### Solucion de problemas

**"No se encontro el ejecutable"**
Verifica la ruta en `config.json`; si usas solo el nombre, debe estar en PATH
o en las carpetas de busqueda descritas arriba.

**No aparecen ROMs nuevas**
El escaneo usa cache: borra `romslist/<emulador>.json` y reinicia. Si creaste
un emulador nuevo, el re-escaneo es automatico.

**Una ROM se lanza con el emulador equivocado**
Ocurre cuando el mismo archivo existe en dos plataformas. El lanzamiento
filtra por emulador de la plataforma activa; verifica que el zip este en la
carpeta `rom_paths` correcta.

**PySide6 no instala**
Linux: instala antes `libgl1-mesa-glx libegl1`. Windows: verifica que Python
este en PATH.

**No hay video/snaps**
Comprueba que exista `images/<emu>/snap/<nombre_rom>.mp4|.png` usando el
mismo nombre base que el archivo ZIP de la ROM.

**El gamepad no se detecta**
Asegurate de tener `pygame-ce` instalado (`pip install pygame-ce`). En Linux
puede ser necesario `sudo usermod -a -G input $USER` y cerrar/abrir sesion.

---

### Licencia

Proyecto libre. Usa PySide6 (LGPL), pygame-ce (LGPL) y Python.
