"""
scraper.py - Scraping de información de games.

Fuentes (en orden de prioridad):
1. IGDB API (vía Twitch - mejor calidad)
2. RAWG.io API (gratuita, sin 2FA)
3. Wikipedia API (fallback gratuito)

Guarda cache en JSON para no repetir consultas.
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


from paths import BASE_PATH

CACHE_PATH = BASE_PATH / "game_cache.json"


@dataclass
class GameInfo:
    name: str = ""
    original_name: str = ""
    year: int = 0
    players: int = 1
    genre: str = ""
    manufacturer: str = ""
    description: str = ""
    source: str = ""


def clean_rom_name(name: str) -> str:
    """Normaliza el nombre de una ROM para la busqueda:
    - guiones bajos -> espacios
    - quita parentesis con tags de region/revision/numero: (USA), (Europe),
      (Rev 1), (1992), (En,Fr,De), (v1.0), (Arcade)...
    - quita sufijos numericos que no aportan y espacios duplicados.
    """
    clean = re.sub(r'[_]+', ' ', name or '')
    # Quitar extensiones: .zip .smc .nes etc.
    clean = re.sub(r'\.[a-z0-9]{1,4}\s*$', '', clean, flags=re.IGNORECASE)
    # Parentesis: v1.2, rev X, regiones, idiomas, año, etc.
    clean = re.sub(
        r'\s*\([^)]*(?:usa|eur|europe|jap|japan|world|wld|rev\s*\d+|v\d+(?:\.\d+)?|ver\s*\d+|proto|beta|demo|set\s*\d+|\d{4}[a-z]?|arcade|snes|nes|genesis|smc|gb[ca]?\s*,?[^)]*)\)\s*',
        ' ', clean, flags=re.IGNORECASE,
    )
    clean = re.sub(r'\s*\[[^\]]*\]\s*', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


class IGDBClient:
    """Cliente para IGDB API v4 (requiere Twitch credentials)."""

    BASE_URL = "https://api.igdb.com/v4"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = ""
        self.token_expires = 0

    def _get_token(self) -> bool:
        if self.access_token and time.time() < self.token_expires:
            return True

        params = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        })

        try:
            req = urllib.request.Request(f"{self.TOKEN_URL}?{params}", method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.access_token = data["access_token"]
                self.token_expires = time.time() + data.get("expires_in", 3600) - 300
                return True
        except Exception as e:
            print(f"[Scraper] Error token IGDB: {e}")
            return False

    def search_game(self, name: str) -> Optional[dict]:
        if not self._get_token():
            return None

        clean_name = re.sub(r'[_]+', ' ', name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()

        query = f'search "{clean_name}"; fields name,first_release_date,genres.name,multiplayer_modes,involved_companies.company.name; limit 1;'

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "text/plain"
        }

        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/games",
                data=query.encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data[0] if data else None
        except Exception as e:
            print(f"[Scraper] Error IGDB: {e}")
            return None


class RAWGClient:
    """Cliente para RAWG.io API."""

    BASE_URL = "https://api.rawg.io/api"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_game(self, name: str) -> Optional[dict]:
        clean_name = clean_rom_name(name)

        params = urllib.parse.urlencode({
            "key": self.api_key,
            "search": clean_name,
            "page_size": 1
        })

        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/games?{params}",
                headers={"User-Agent": "ArcadeFrontend/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                return results[0] if results else None
        except Exception as e:
            print(f"[Scraper] Error RAWG: {e}")
            return None

    def get_detail(self, game_id: int) -> Optional[dict]:
        params = urllib.parse.urlencode({"key": self.api_key})
        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/games/{game_id}?{params}",
                headers={"User-Agent": "ArcadeFrontend/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except:
            return None


class GameScraper:
    """Scraper principal con IGDB → RAWG → Wikipedia."""

    def __init__(self):
        self.cache = self._load_cache()
        self.igdb = None
        self.rawg = None
        self._configure()

    def _load_cache(self) -> dict:
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except:
            pass

    def _configure(self):
        try:
            config_path = BASE_PATH / "config.json"
            if not config_path.exists():
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            self._load_from(config)

        except Exception as e:
            print(f"[Scraper] Error config: {e}")

    def configure_with(self, client_id="", client_secret="", rawg_key=""):
        """Configura las APIs en caliente (sin reiniciar el programa)."""
        self.igdb = None
        self.rawg = None
        if client_id and client_secret:
            self.igdb = IGDBClient(client_id, client_secret)
            print("[Scraper] IGDB habilitado")
        if rawg_key:
            self.rawg = RAWGClient(rawg_key)
            print("[Scraper] RAWG habilitado")
        if not self.igdb and not self.rawg:
            print("[Scraper] Sin API - usando Wikipedia como fallback")

    def _load_from(self, config: dict):
        """Lee las APIs desde un dict de config (config.json)."""
        igdb_cfg = config.get("igdb", {})
        rawg_cfg = config.get("rawg", {})
        self.configure_with(
            igdb_cfg.get("client_id", "") if igdb_cfg.get("enabled") else "",
            igdb_cfg.get("client_secret", "") if igdb_cfg.get("enabled") else "",
            rawg_cfg.get("api_key", "") if rawg_cfg.get("enabled") else "",
        )

    def get_info(self, rom_name: str, emulator: str) -> GameInfo:
        cache_key = f"{emulator}:{rom_name}".lower()

        if cache_key in self.cache:
            data = self.cache[cache_key]
            return GameInfo(**data)

        info = GameInfo(name=rom_name, original_name=rom_name)

        # 1. Intentar IGDB
        if self.igdb:
            info = self._search_igdb(rom_name)
            if info.year > 0 or info.genre:
                self.cache[cache_key] = asdict(info)
                self._save_cache()
                return info

        # 2. Intentar RAWG
        if self.rawg:
            info = self._search_rawg(rom_name)
            if info.year > 0 or info.genre:
                self.cache[cache_key] = asdict(info)
                self._save_cache()
                return info

        # 3. Fallback Wikipedia
        info = self._search_wikipedia(rom_name)

        self.cache[cache_key] = asdict(info)
        self._save_cache()
        return info

    # === IGDB ===

    def _search_igdb(self, rom_name: str) -> GameInfo:
        info = GameInfo(name=rom_name, original_name=rom_name, source="igdb")
        game = self.igdb.search_game(rom_name)
        if not game:
            return info

        info.original_name = game.get("name", rom_name)

        release = game.get("first_release_date")
        if release:
            try:
                ts = int(release)
                info.year = int(time.strftime("%Y", time.gmtime(ts)))
            except:
                pass

        genres = game.get("genres", [])
        if genres:
            info.genre = ", ".join(g.get("name", "") for g in genres[:3])

        multiplayer = game.get("multiplayer_modes", [])
        if multiplayer:
            max_p = 1
            for mode in multiplayer:
                online = mode.get("online_max", 0) or 0
                offline = mode.get("offline_max", 0) or 0
                max_p = max(max_p, online, offline)
            info.players = max_p

        companies = game.get("involved_companies", [])
        if companies:
            company = companies[0].get("company", {})
            if isinstance(company, dict):
                info.manufacturer = company.get("name", "")

        return info

    # === RAWG ===

    def _search_rawg(self, rom_name: str) -> GameInfo:
        info = GameInfo(name=rom_name, original_name=rom_name, source="rawg")

        # Probar variantes del nombre hasta tener un resultado concreto
        variants = self._name_variants(rom_name)
        for variant in variants:
            game = self.rawg.search_game(variant)
            if game and self._rawg_matches(game, variant):
                game_id = game.get("id")
                if game_id:
                    detail = self.rawg.get_detail(game_id)
                    if detail:
                        return self._parse_rawg(rom_name, detail)
                return self._parse_rawg(rom_name, game)
        return info

    @staticmethod
    def _name_variants(name: str) -> list:
        """Variantes ordenadas por probabilidad de exito."""
        cleaned = clean_rom_name(name)
        variants = []
        if cleaned:
            variants.append(cleaned)
        # Quitar sub-titulos tras dos puntos / guion largo
        for sep in (":", " - ", " – "):
            if sep in cleaned:
                variants.append(cleaned.split(sep)[0].strip())
                break
        # Ultima palabra (probable sub-titulo)
        words = cleaned.split()
        if len(words) > 2 and words[-1].lower() in (
            "edition", "collection", "complete", "deluxe", "remastered",
            "remake", "ultimate", "gold", "platinum", "special",
        ):
            variants.append(" ".join(words[:-1]))
        return variants

    @staticmethod
    def _rawg_matches(game: dict, variant: str) -> bool:
        """Confirma que el resultado no sea un disparo en falso obvio."""
        title = (game.get("name") or "").lower()
        variant_l = variant.lower()
        return bool(variant_l and (variant_l in title or title in variant_l))

    def _parse_rawg(self, rom_name: str, game: dict) -> GameInfo:
        info = GameInfo(name=rom_name, source="rawg")

        info.original_name = game.get("name", rom_name)

        release = game.get("released")
        if release and len(str(release)) >= 4:
            try:
                info.year = int(str(release)[:4])
            except:
                pass

        genres = game.get("genres", [])
        if genres:
            info.genre = ", ".join(g.get("name", "") for g in genres[:3])

        developers = game.get("developers", [])
        if developers:
            info.manufacturer = ", ".join(d.get("name", "") for d in developers[:2])
        else:
            publishers = game.get("publishers", [])
            if publishers:
                info.manufacturer = publishers[0].get("name", "")

        info.players = 1
        platforms = game.get("platforms", [])
        for p in platforms:
            if p.get("requirements", {}).get("multiplayer"):
                info.players = 2
                break

        return info

    # === WIKIPEDIA FALLBACK ===

    def _search_wikipedia(self, rom_name: str) -> GameInfo:
        info = GameInfo(name=rom_name, original_name=rom_name)
        clean_name = clean_rom_name(rom_name)

        search_url = (
            "https://en.wikipedia.org/w/api.php?"
            "action=query&list=search&srsearch="
            + urllib.parse.quote(f'"{clean_name}" video game')
            + "&srnamespace=0&srlimit=5&format=json"
        )

        data_str = self._http_get(search_url)
        if not data_str:
            return info

        try:
            data = json.loads(data_str)
            results = data.get("query", {}).get("search", [])
            if not results:
                return info

            name_lower = rom_name.lower().replace("_", " ")
            best_title = results[0].get("title", "")

            for r in results:
                title = r.get("title", "").lower()
                if name_lower in title or title in name_lower:
                    best_title = r.get("title", "")
                    break

            page_url = (
                "https://en.wikipedia.org/w/api.php?"
                "action=query&titles=" + urllib.parse.quote(best_title)
                + "&prop=extracts&explaintext=1&exsectionformat=plain&format=json"
            )

            page_str = self._http_get(page_url)
            if not page_str:
                info.original_name = best_title
                info.source = "wikipedia"
                return info

            page_data = json.loads(page_str)
            pages = page_data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                if page_id == "-1":
                    continue
                info.original_name = page.get("title", best_title)
                extract = page.get("extract", "")
                info.year = self._extract_year(extract)
                info.genre = self._extract_genre(extract)
                info.manufacturer = self._extract_manufacturer(extract)
                info.players = self._extract_players(extract)
                info.source = "wikipedia"
                break
        except:
            pass

        return info

    def _http_get(self, url: str, timeout: int = 10) -> Optional[str]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except:
            return None

    def _extract_year(self, text: str) -> int:
        fragment = text[:800]
        match = re.search(r'\b(?:is|was)\s+a\s+(\d{4})\s+(?:video\s+)?game', fragment, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1970 <= year <= 2030:
                return year

        match = re.search(r'(?:released|published|developed|created|launched)\s+(?:in\s+)?(?:the\s+)?(\d{4})', fragment, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1970 <= year <= 2030:
                return year

        matches = re.findall(r'\b(19[7-9]\d|20[0-2]\d)\b', fragment[:300])
        return int(matches[0]) if matches else 0

    def _extract_genre(self, text: str) -> str:
        fragment = text[:500].lower()
        genres = [
            (r'fight(?:ing)?\s+game', 'Lucha'),
            (r'platform(?:er|ing)?\s+game', 'Plataformas'),
            (r'shooter', 'Disparos'),
            (r'puzzle\s+game', 'Puzzle'),
            (r'racing\s+game', 'Carreras'),
            (r'beat.?em.?up', 'Beat em up'),
            (r'action', 'Acción'),
            (r'adventure', 'Aventura'),
            (r'role.?playing', 'RPG'),
            (r'simulation', 'Simulación'),
            (r'sports?\s+game', 'Deportes'),
        ]
        for pattern, genre in genres:
            if re.search(pattern, fragment):
                return genre
        return ""

    def _extract_manufacturer(self, text: str) -> str:
        fragment = text[:500]
        match = re.search(r'(?:developed|published|created|made)\s+(?:and\s+(?:published|developed)\s+)?by\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s+for|\s+in|\s+on|\.|,)', fragment)
        if match:
            manufacturer = re.sub(r'\s+', ' ', match.group(1).strip())
            if 2 < len(manufacturer) < 60:
                return manufacturer
        return ""

    def _extract_players(self, text: str) -> int:
        text_lower = text.lower()[:500]
        match = re.search(r'(\d+)\s*[-–]?\s*(?:to\s*[-–]?\s*\d+\s*)?player', text_lower)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 8:
                return num
        if re.search(r'(?:two|2)\s*player', text_lower):
            return 2
        if re.search(r'(?:four|4)\s*player', text_lower):
            return 4
        return 1


scraper = GameScraper()
