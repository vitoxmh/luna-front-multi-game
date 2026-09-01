"""
launcher.py - Lanzamiento de emulators.

Ejecuta el emulador correspondiente con la ROM seleccionada.
Compatible con Linux y Windows.
"""

import subprocess
import sys
import shutil
import shlex
import threading
import time
from pathlib import Path
from config import get_relative_path
from scanner import resolve_rom_path


def launch_rom(rom_info, config: dict, screen_rect=None) -> subprocess.Popen | None:
    """
    Lanza un emulador con la ROM especificada.

    RomInfo.file_path guarda solo el name del archivo: la path completa se
    reconstruye desde emulators[].rom_paths de config.json.

    Args:
        rom_info: Objeto RomInfo con los datos de la ROM
        config: Diccionario de configuración completo
        screen_rect: Tupla (x, y, w, h) del monitor donde corre el front.
            Si se pasa, tras lanzar se intenta llevar la ventana del emulador
            a ese mismo monitor (pantalla completa), para que emulador y
            frontend compartan pantalla.

    Returns:
        El objeto Popen del proceso si se lanzó correctamente, None si hubo error
    """
    emu_id = rom_info.emulator
    emulators = config.get("emulators", {})
    emu_config = emulators.get(emu_id, {})

    if not emu_config:
        print(f"[ERROR] Emulador '{emu_id}' no found en la configuración")
        return None

    executable = emu_config.get("executable", "")
    if not executable:
        print(f"[ERROR] No hay executable configurado para '{emu_id}'")
        return None

    rom_path = resolve_rom_path(rom_info, config)
    if not rom_path:
        print(f"[ERROR] No se encontró el archivo de la ROM: {rom_info.file_path}")
        print(f"        Verifica rom_paths de '{emu_id}' en config.json")
        return None

    executable_path = _find_executable(executable)
    if not executable_path:
        print(f"[ERROR] No se encontró el executable: {executable}")
        print(f"        Verifica la configuración en config.json")
        return None

    command = _build_command(executable_path, emu_config, rom_info, rom_path)

    print(f"[LANZANDO] {' '.join(command)}")

    try:
        if sys.platform == "linux":
            proc = subprocess.Popen(command, start_new_session=True)
        else:
            proc = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

        print(f"[OK] Emulador lanzado: {rom_info.name}")

        # Llevar la ventana del emulador al mismo monitor que el front
        # (misma pantalla), si conocemos su geometria.
        if screen_rect:
            threading.Thread(
                target=_move_window_to_screen,
                args=(proc, screen_rect),
                daemon=True,
            ).start()

        return proc

    except FileNotFoundError:
        print(f"[ERROR] No se pudo ejecutar: {executable_path}")
        return None
    except PermissionError:
        print(f"[ERROR] Sin permisos para ejecutar: {executable_path}")
        return None
    except Exception as e:
        print(f"[ERROR] Error al lanzar emulador: {e}")
        return None


def _move_window_to_screen(proc, screen_rect):
    """
    Recoloca la ventana principal del proceso emulador en el monitor dado.

    Espera un instante a que la ventana exista y luego, segun la plataforma:

      - Windows: mueve la ventana top-level del proceso (Win32 / SetWindowPos)
      - Linux (X11): usa xdotool search --pid para moverla

    Geo es (x, y, w, h) absoluto del monitor destino.
    """
    try:
        x, y, w, h = screen_rect
        time.sleep(0.8)
        if sys.platform == "win32":
            _win_move_to(proc, x, y, w, h)
        elif sys.platform == "linux":
            _x11_move_to(proc, x, y, w, h)
    except Exception as e:
        print(f"[WARN] No se pudo recolocar el emulador en pantalla: {e}")


def _win_move_to(proc, x, y, w, h):
    """Windows: mueve/recoloca la ventana top-level del pid a (x,y)+(w,h)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    pid = proc.pid

    GW_OWNER = 4
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    hwnds = []

    def _enum(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid:
            hwnds.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(_enum), 0)

    for hwnd in hwnds:
        # Mantener maximizado a pantalla completa del monitor destino:
        # mover la esquina y fijar tamano al del monitor.
        user32.SetWindowPos(
            hwnd, 0, x, y, w, h,
            SWP_NOZORDER | SWP_NOACTIVATE,
        )
        print(f"[OK] Emulador movido al monitor del front (hwnd={hwnd})")


def _x11_move_to(proc, x, y, w, h):
    """Linux/X11: mueve la ventana del pid al monitor destino via xdotool."""
    # Permitir que el emulador abra en la pantalla correcta desde el arranque
    # usando variables SDL (muchos emuladores las respetan a pantalla completa).
    import os
    os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = ""
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

    which = shutil.which("xdotool")
    if not which:
        return
    try:
        found = subprocess.run(
            [which, "search", "--pid", str(proc.pid)],
            capture_output=True, text=True, timeout=5,
        ).stdout.split()
        if found:
            wid = found[-1].strip()
            subprocess.run([which, "windowmove", wid, str(x), str(y)], timeout=5)
            subprocess.run([which, "windowsize", wid, str(w), str(h)], timeout=5)
            print(f"[OK] Emulador movido al monitor del front (wid={wid})")
    except Exception as e:
        print(f"[WARN] xdotool: {e}")


def _find_executable(name: str) -> str:
    """
    Busca el executable del emulador.
    Primero busca en PATH del sistema, luego en paths absolutas.
    """
    path = Path(name)
    if path.is_absolute() and path.exists():
        return str(path)

    found = shutil.which(name)
    if found:
        return found

    if sys.platform == "linux":
        for folder in ["/usr/bin", "/usr/local/bin", "/snap/bin", "/opt", "/usr/games"]:
            variant = f"{folder}/{name}/{name}" if "/opt" in folder else f"{folder}/{name}"
            if Path(variant).exists():
                return variant

    elif sys.platform == "win32":
        for drive in ["C", "D", "E"]:
            for folder in ["Emuladores", "Program Files", "Program Files (x86)"]:
                variant = f"{drive}:\\{folder}\\{name}\\{name}.exe"
                if Path(variant).exists():
                    return variant
                variant = f"{drive}:\\{folder}\\{name}.exe"
                if Path(variant).exists():
                    return variant

    return name


def _build_command(executable: str, emu_config: dict, rom_info, rom_path: str) -> list:
    """
    Construye el command usando launch_args del config.

    Placeholders availables:
      {rompath}  -> path completa de la ROM (resuelta desde config.json)
      {romdir}   -> directorio que contiene la ROM
      {romname}  -> name del archivo ROM sin extensión
      {core}     -> core del emulador (si existe)
    """
    launch_args = emu_config.get("launch_args", "{rompath}")
    rom_dir = str(Path(rom_path).parent)
    rom_name = Path(rom_path).stem
    core = getattr(rom_info, 'core', '') or ''

    quoted_path = f'"{rom_path}"'
    quoted_dir = f'"{rom_dir}"'
    quoted_name = f'"{rom_name}"'

    args = launch_args.format(
        rompath=quoted_path,
        romdir=quoted_dir,
        romname=quoted_name,
        core=core,
    )

    if sys.platform == "win32":
        tokens = shlex.split(args, posix=False)
        return [executable] + [t.strip('"') for t in tokens]
    return [executable] + shlex.split(args)


def check_emulators(config: dict) -> dict:
    """
    Verifica qué emulators están availables en el sistema.
    """
    emulators = config.get("emulators", {})
    status = {}

    for emu_id, emu_config in emulators.items():
        executable = emu_config.get("executable", "")
        path = _find_executable(executable)
        available = Path(path).exists() if path else False

        if not available:
            available = shutil.which(executable) is not None
            if available:
                path = shutil.which(executable)

        status[emu_id] = {
            "name": emu_config.get("name", emu_id),
            "available": available,
            "path": path,
        }

        status_str = "✅" if available else "❌"
        print(f"  {status_str} {emu_config.get('name', emu_id)}: {path}")

    return status
