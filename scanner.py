"""
scanner.py - Escaneo automático de ROMs.

Recorre las folders configuradas en emulators[].rom_paths
y genera una lista de ROMs disponibles agrupadas por emulator/categoría.
Guarda y carga desde JSON en romslist/ para escaneos rápidos.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from config import get_relative_path


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.webm', '.mov'}
SNAP_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

from paths import BASE_PATH
from paths import base_path


def path_for_cache(path: str) -> str:
    """Convierte una path absoluta bajo la folder del proyecto a relativa.

    El cache (romslist/) guarda paths relativas porque la ubicacion base
    ya esta en config.json; si la path apunta fuera del proyecto se
    conserva tal cual.
    """
    if not path:
        return ""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(BASE_PATH))
    except ValueError:
        return str(p)


def absolute_path(path: str) -> str:
    """Inverso de path_for_cache: resuelve una path relativa al proyecto."""
    if not path:
        return ""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(BASE_PATH / p)


def find_category_wheel(emu_id: str, cat_id: str = "") -> str:
    """Busca la image wheel de una categoría/emulator.
    Busca en: images/<emu>/wheel/, images/plataforma/, images/
    """
    base_path = BASE_PATH
    name = cat_id if cat_id else emu_id

    search_folders = []
    if cat_id:
        search_folders.append(base_path / "images" / emu_id / cat_id / "wheel")
    search_folders.append(base_path / "images" / emu_id / "wheel")
    search_folders.append(base_path / "images" / "plataforma")
    search_folders.append(base_path / "images")

    for folder in search_folders:
        if not folder.exists():
            continue
        for ext in IMAGE_EXTENSIONS:
            for n in (name, name.lower(), name.upper(), emu_id, emu_id.lower()):
                img = folder / f"{n}{ext}"
                if img.exists():
                    return str(img)
            # Buscar también con guiones bajos: NES_logo.svg
            for file_path in folder.iterdir():
                if file_path.suffix.lower() == ext and name.lower() in file_path.stem.lower():
                    return str(file_path)
    return ""


def find_category_background(emu_id: str, cat_id: str = "") -> str:
    """Busca image de fondo de una plataforma.
    Busca en: images/<emu>/<cat>/fondo/, images/<cat>/fondo/,
    images/<emu>/fondo/, images/plataforma/fondo/, images/fondo/
    """
    base_path = BASE_PATH
    name = cat_id if cat_id else emu_id

    search_folders = []
    if cat_id:
        search_folders.append(base_path / "images" / emu_id / cat_id / "fondo")
        search_folders.append(base_path / "images" / cat_id / "fondo")
    search_folders.append(base_path / "images" / emu_id / "fondo")
    search_folders.append(base_path / "images" / "plataforma" / "fondo")
    search_folders.append(base_path / "images" / "fondo")

    for folder in search_folders:
        if not folder.exists():
            continue
        for ext in IMAGE_EXTENSIONS:
            for n in (name, name.lower(), name.upper(), emu_id, emu_id.lower()):
                img = folder / f"{n}{ext}"
                if img.exists():
                    return str(img)
            # Buscar tambien por coincidencia parcial en el name
            for file_path in folder.iterdir():
                if file_path.suffix.lower() == ext and name.lower() in file_path.stem.lower():
                    return str(file_path)
    return ""


def find_rom_image(
    rom_name: str, rom_path: Path, emulator: str, cat_id: str = "",
    images_path: str = "",
) -> str:
    """Busca wheel image: images/<emulator>/<category>/wheel/<name>.ext

    Si images_path está configurado (config.json), se busca primero ahí.
    """
    name_lower = rom_name.lower()
    base_path = BASE_PATH

    folders = []
    if images_path:
        folders.append(get_relative_path(images_path))
    if cat_id:
        folders.append(base_path / "images" / emulator / cat_id / "wheel")
        folders.append(base_path / "images" / cat_id / "wheel")
    folders.append(base_path / "images" / emulator / "wheel")
    folders.append(base_path / "images" / "wheel")

    for folder in folders:
        if not folder.exists():
            continue
        for ext in IMAGE_EXTENSIONS:
            for name in (rom_name, name_lower):
                image = folder / f"{name}{ext}"
                if image.exists():
                    return path_for_cache(str(image))
    return ""


def find_rom_snap(
    rom_name: str, rom_path: Path, emulator: str, cat_id: str = "",
    videos_path: str = "",
) -> str:
    """Busca snap/screenshot: images/<emulator>/<category>/snap/<name>.ext
    Prioriza video sobre image.

    Si videos_path está configurado (config.json), se busca primero ahí.
    """
    name_lower = rom_name.lower()
    base_path = BASE_PATH

    folders = []
    if videos_path:
        folders.append(get_relative_path(videos_path))
    if cat_id:
        folders.append(base_path / "images" / emulator / cat_id / "snap")
        folders.append(base_path / "images" / cat_id / "snap")
    folders.append(base_path / "images" / emulator / "snap")
    folders.append(base_path / "images" / "snap")

    for folder in folders:
        if not folder.exists():
            continue
        # Buscar video primero
        for ext in VIDEO_EXTENSIONS:
            for name in (rom_name, name_lower):
                snap = folder / f"{name}{ext}"
                if snap.exists():
                    return path_for_cache(str(snap))
        # Si no hay video, buscar image
        for ext in IMAGE_EXTENSIONS:
            for name in (rom_name, name_lower):
                snap = folder / f"{name}{ext}"
                if snap.exists():
                    return path_for_cache(str(snap))
    return ""


def find_rom_marquee(
    rom_name: str, rom_path: Path, emulator: str, cat_id: str = "",
    marquees_path: str = "",
) -> str:
    """Busca marquee (banner arcade): images/<emulator>/marquee/<name>.ext

    Si marquees_path está configurado (config.json), se busca primero ahí.
    """
    name_lower = rom_name.lower()
    base_path = BASE_PATH

    folders = []
    if marquees_path:
        folders.append(get_relative_path(marquees_path))
    if cat_id:
        folders.append(base_path / "images" / emulator / cat_id / "marquee")
        folders.append(base_path / "images" / cat_id / "marquee")
    folders.append(base_path / "images" / emulator / "marquee")
    folders.append(base_path / "images" / "marquee")

    for folder in folders:
        if not folder.exists():
            continue
        for ext in IMAGE_EXTENSIONS:
            for name in (rom_name, name_lower):
                marquee = folder / f"{name}{ext}"
                if marquee.exists():
                    return path_for_cache(str(marquee))
    return ""


@dataclass
class RomInfo:
    """Información básica de una ROM encontrada.

    file_path guarda SOLO el name del file_path (sin path); la path completa
    se reconstruye con resolve_rom_path() usando rom_paths de config.json.
    """
    name: str
    file_path: str
    emulator: str
    category: str
    extension: str
    size_kb: int = 0
    image: str = ""
    marquee: str = ""
    snap: str = ""
    core: str = ""


@dataclass
class SystemInfo:
    """Información de un system/categoría para la rueda."""
    id: str
    name: str
    emulator: str
    roms: list = field(default_factory=list)
    core: str = ""
    wheel_img: str = ""


def scan_roms(config: dict) -> dict:
    """
    Escanea todas las paths de ROMs configuradas.

    Cada emulator puede tener:
      - rom_paths como string  -> una sola folder
      - rom_paths como dict    -> subcategorías (cada una con name, path, core opcional)
    """
    emulators = config.get("emulators", {})
    results = {}

    for emu_id, emu_config in emulators.items():
        rom_paths = emu_config.get("rom_paths", "")
        extensions = set(emu_config.get("extensions", []))

        if isinstance(rom_paths, dict):
            systems = _scan_subcategories(emu_id, emu_config, rom_paths, extensions)
        elif isinstance(rom_paths, str) and rom_paths:
            systems = [_scan_simple_folder(emu_id, emu_config, rom_paths, extensions)]
        else:
            systems = []

        results[emu_id] = systems

    total = sum(
        len(system.roms)
        for systems in results.values()
        for system in systems
    )
    print(f"[OK] Escaneo completado: {total} ROMs encontradas")

    return results


def _scan_simple_folder(
    emu_id: str, emu_config: dict, path: str, extensions: set
) -> SystemInfo:
    """Escanea una folder simple (un emulator, una folder)."""
    full_path = get_relative_path(path)
    system_name = emu_config.get("name", emu_id)

    wheel_img = emu_config.get("wheel_img", "") or find_category_wheel(emu_id)

    system = SystemInfo(
        id=emu_id,
        name=system_name,
        emulator=emu_id,
        wheel_img=wheel_img,
    )

    if not full_path.exists():
        print(f"[AVISO] Carpeta no encontrada: {full_path}")
        print(f"        Creando folder para {system_name}...")
        full_path.mkdir(parents=True, exist_ok=True)
        return system

    for file_path in sorted(full_path.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            image = find_rom_image(
                file_path.stem, file_path, emu_id,
                images_path=emu_config.get("images_path", ""),
            )
            marquee = find_rom_marquee(
                file_path.stem, file_path, emu_id,
                marquees_path=emu_config.get("marquees_path", ""),
            )
            snap = find_rom_snap(
                file_path.stem, file_path, emu_id,
                videos_path=emu_config.get("videos_path", ""),
            )

            rom = RomInfo(
                name=file_path.stem,
                file_path=file_path.name,
                emulator=emu_id,
                category=emu_id,
                extension=file_path.suffix.lower(),
                size_kb=file_path.stat().st_size // 1024,
                image=image,
                marquee=marquee,
                snap=snap,
            )
            system.roms.append(rom)

    print(f"  [{system_name}] {len(system.roms)} ROMs")
    return system


def _scan_subcategories(
    emu_id: str, emu_config: dict, rom_paths: dict, global_extensions: set
) -> list:
    """
    Escanea subcategorías de un emulator.

    Cada subcategoría puede tener:
      - name: display name
      - path: folder de ROMs
      - core: (opcional) core para emulators como RetroArch
    """
    systems = []

    for cat_id, cat_config in rom_paths.items():
        if isinstance(cat_config, str):
            cat_config = {"path": cat_config, "name": cat_id.upper()}

        name = cat_config.get("name", cat_id.upper())
        path = cat_config.get("path", "")
        core = cat_config.get("core", "")
        wheel_img = cat_config.get("wheel_img", "") or find_category_wheel(emu_id, cat_id)
        full_path = get_relative_path(path)

        system = SystemInfo(
            id=f"{emu_id}_{cat_id}",
            name=name,
            emulator=emu_id,
            core=core,
            wheel_img=wheel_img,
        )

        if not full_path.exists():
            print(f"[AVISO] Carpeta no encontrada: {full_path}")
            print(f"        Creando folder para {name}...")
            full_path.mkdir(parents=True, exist_ok=True)
            systems.append(system)
            continue

        for file_path in sorted(full_path.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in global_extensions:
                # images_path/marquees_path/videos_path: primero en la
                # subcategoría, si no, los del emulator.
                images_path = cat_config.get(
                    "images_path", ""
                ) or emu_config.get("images_path", "")
                marquees_path = cat_config.get(
                    "marquees_path", ""
                ) or emu_config.get("marquees_path", "")
                videos_path = cat_config.get(
                    "videos_path", ""
                ) or emu_config.get("videos_path", "")

                image = find_rom_image(
                    file_path.stem, file_path, emu_id, cat_id,
                    images_path=images_path,
                )
                marquee = find_rom_marquee(
                    file_path.stem, file_path, emu_id, cat_id,
                    marquees_path=marquees_path,
                )
                snap = find_rom_snap(
                    file_path.stem, file_path, emu_id, cat_id,
                    videos_path=videos_path,
                )

                rom = RomInfo(
                    name=file_path.stem,
                    file_path=file_path.name,
                    emulator=emu_id,
                    category=cat_id,
                    extension=file_path.suffix.lower(),
                    size_kb=file_path.stat().st_size // 1024,
                    image=image,
                    marquee=marquee,
                    snap=snap,
                    core=core,
                )
                system.roms.append(rom)

        print(f"  [{name}] {len(system.roms)} ROMs")
        systems.append(system)

    return systems


def get_statistics(results: dict) -> dict:
    """Retorna estadísticas del escaneo para mostrar en la UI."""
    stats = {}
    for emu_id, systems in results.items():
        total_roms = sum(len(s.roms) for s in systems)
        stats[emu_id] = {
            "systems": len(systems),
            "total_roms": total_roms,
        }
    return stats


def rom_folder_path(emu_id: str, category: str, config: dict) -> str:
    """Carpeta de ROMs de un emulator/categoría según config.json.

    rom_paths puede ser string (una folder) o dict de subcategorías
    (cada una con 'path', o directamente el valor como string).
    Retorna '' si no está configurado.
    """
    emu_config = config.get("emulators", {}).get(emu_id, {})
    rom_paths = emu_config.get("rom_paths", "")
    if isinstance(rom_paths, dict):
        cat_config = rom_paths.get(category, "")
        if isinstance(cat_config, str):
            return cat_config
        return cat_config.get("path", "")
    if isinstance(rom_paths, str):
        return rom_paths
    return ""


def resolve_rom_path(rom_info, config: dict) -> str:
    """Ruta completa y existente de una ROM.

    RomInfo.file_path guarda solo el name; la folder sale de
    emulators[emulator].rom_paths (config.json) usando la categoría.
    Compatibilidad: si file_path ya trae una path absoluta existente
    (caches viejos), se devuelve tal cual. Retorna '' si no existe.
    """
    if not rom_info or not rom_info.file_path:
        return ""

    direct_path = Path(rom_info.file_path)
    if direct_path.is_absolute():
        return str(direct_path) if direct_path.exists() else ""

    folder = rom_folder_path(rom_info.emulator, rom_info.category, config)
    if not folder:
        print(f"[ERROR] Sin rom_paths para '{rom_info.emulator}/{rom_info.category}'")
        return ""
    candidate = get_relative_path(folder) / rom_info.file_path
    if candidate.exists():
        return str(candidate)
    return ""


ROMSLIST_PATH = BASE_PATH / "romslist"


def _system_to_dict(system: SystemInfo) -> dict:
    """Serializa un SystemInfo a dict para JSON."""
    return {
        "id": system.id,
        "name": system.name,
        "emulator": system.emulator,
        "core": system.core,
        "wheel_img": system.wheel_img,
        "roms": [asdict(rom) for rom in system.roms],
    }


def _dict_to_system(data: dict) -> SystemInfo:
    """Deserializa un dict a SystemInfo."""
    system = SystemInfo(
        id=data["id"],
        name=data["name"],
        emulator=data["emulator"],
        core=data.get("core", ""),
        wheel_img=data.get("wheel_img", ""),
    )
    for rom_data in data.get("roms", []):
        rom = RomInfo(
            name=rom_data["name"],
            file_path=rom_data["file_path"],
            emulator=rom_data["emulator"],
            category=rom_data["category"],
            extension=rom_data["extension"],
            size_kb=rom_data.get("size_kb", 0),
            image=rom_data.get("image", ""),
            marquee=rom_data.get("marquee", ""),
            snap=rom_data.get("snap", ""),
            core=rom_data.get("core", ""),
        )
        system.roms.append(rom)
    return system


def save_scan(results: dict) -> None:
    """
    Guarda el resultado del escaneo como JSONs individuales por emulator.
    Crea: romslist/{emu_id}.json
    """
    ROMSLIST_PATH.mkdir(parents=True, exist_ok=True)

    for emu_id, systems in results.items():
        data = {
            "emulator": emu_id,
            "systems": [_system_to_dict(s) for s in systems],
        }
        file_path = ROMSLIST_PATH / f"{emu_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    total = sum(
        len(s.roms)
        for systems in results.values()
        for s in systems
    )
    print(f"[OK] Escaneo guardado en {ROMSLIST_PATH} ({total} ROMs)")


def load_scan() -> dict | None:
    """
    Carga el escaneo desde los JSONs en romslist/.
    Retorna el mismo formato que scan_roms() o None si no existe.
    """
    if not ROMSLIST_PATH.exists():
        return None

    json_files = list(ROMSLIST_PATH.glob("*.json"))
    if not json_files:
        return None

    results = {}
    for file_path in sorted(json_files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[AVISO] Error leyendo {file_path.name}: {e}")
            continue

        emu_id = data.get("emulator", file_path.stem)
        systems = [_dict_to_system(s) for s in data.get("systems", [])]
        results[emu_id] = systems

    total = sum(
        len(s.roms)
        for systems in results.values()
        for s in systems
    )
    print(f"[OK] Escaneo cargado desde {ROMSLIST_PATH} ({total} ROMs)")
    return results
