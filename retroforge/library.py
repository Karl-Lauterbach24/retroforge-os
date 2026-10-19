"""ROM library: scanning, name cleanup, favourites and play statistics."""
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("retroforge.library")

REGION_TAGS = {
    "usa": "US", "us": "US", "u": "US", "europe": "EU", "eur": "EU", "e": "EU", "japan": "JP",
    "jpn": "JP", "j": "JP", "world": "WORLD", "w": "WORLD", "germany": "DE", "de": "DE",
    "france": "FR", "fr": "FR", "spain": "ES", "italy": "IT", "korea": "KR", "brazil": "BR",
    "australia": "AU", "asia": "ASIA", "china": "CN",
}
DISC_RE = re.compile(r"\((?:disc|disk|cd)\s*(\d+)(?:\s*of\s*\d+)?\)", re.I)
IGNORE_DIRS = {"images", "media", "videos", "manuals", "downloaded_images", "bios", ".git"}


def clean_name(filename):
    """'Chrono Trigger (USA) [!].sfc' -> ('Chrono Trigger', 'US')"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    region = ""
    for tag in re.findall(r"\(([^)]*)\)", stem):
        for part in re.split(r"[,\s]+", tag.lower()):
            if part in REGION_TAGS and not region:
                region = REGION_TAGS[part]
    name = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", stem).strip()
    name = re.sub(r"\s{2,}", " ", name.replace("_", " "))
    # "Legend of Zelda, The" -> "The Legend of Zelda"
    m = re.match(r"^(.*), (The|A|An|Der|Die|Das)(\s*-.*)?$", name)
    if m:
        name = f"{m.group(2)} {m.group(1)}{m.group(3) or ''}"
    return name or stem, region


@dataclass
class Game:
    key: str                  # "<system>/<relative path>"
    system: str
    path: str
    name: str
    region: str = ""
    size: int = 0
    is_dir: bool = False

    @property
    def stem(self):
        return os.path.splitext(os.path.basename(self.path))[0]


class GameData:
    """Per-game user data: favourite flag, play count, last played, plugin fields."""

    def __init__(self, path):
        self.path = path
        self.data: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def save(self):
        with self._lock:
            tmp = str(self.path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)

    def get(self, key, field_name, default=None):
        return self.data.get(key, {}).get(field_name, default)

    def set(self, key, field_name, value, save=True):
        self.data.setdefault(key, {})[field_name] = value
        if save:
            self.save()

    def is_favorite(self, key):
        return bool(self.get(key, "fav"))

    def toggle_favorite(self, key):
        self.set(key, "fav", not self.is_favorite(key))
        return self.is_favorite(key)

    def record_play(self, key, seconds):
        d = self.data.setdefault(key, {})
        d["plays"] = d.get("plays", 0) + 1
        d["last"] = int(time.time())
        d["time"] = d.get("time", 0) + int(seconds)
        self.save()


class Library:
    def __init__(self, core):
        self.core = core
        self.games: Dict[str, List[Game]] = {}
        self.by_key: Dict[str, Game] = {}
        self.scanning = False
        self.last_scan = 0.0

    def _scan_system(self, sysdef) -> List[Game]:
        root = self.core.paths.system_roms(sysdef.id)
        if not root.is_dir():
            return []
        exts = set(e.lower() for e in sysdef.exts)
        found, referenced = [], set()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in IGNORE_DIRS and not d.startswith(".")]
            # directory-style games (e.g. "Game.ps3/", "Game.wua/")
            for d in list(dirnames):
                if os.path.splitext(d)[1].lower() in exts:
                    full = os.path.join(dirpath, d)
                    found.append((full, True))
                    dirnames.remove(d)
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in exts:
                    continue
                full = os.path.join(dirpath, fn)
                if ext == ".m3u":
                    referenced |= _m3u_entries(full)
                if ext == ".cue":
                    referenced |= _cue_entries(full)
                found.append((full, False))
        games = []
        for full, is_dir in found:
            if os.path.normcase(os.path.abspath(full)) in referenced:
                continue   # hide discs/tracks that an .m3u/.cue already covers
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            name, region = clean_name(full)
            try:
                size = os.path.getsize(full) if not is_dir else 0
            except OSError:
                size = 0
            games.append(Game(f"{sysdef.id}/{rel}", sysdef.id, full, name, region, size, is_dir))
        games.sort(key=lambda g: g.name.lower())
        return games

    def scan(self):
        self.scanning = True
        t0 = time.time()
        games, by_key = {}, {}
        for sysdef in self.core.registry.all("system"):
            lst = self._scan_system(sysdef)
            if lst:
                games[sysdef.id] = lst
                for g in lst:
                    by_key[g.key] = g
        self.games, self.by_key = games, by_key
        self.scanning = False
        self.last_scan = time.time()
        log.info("library: %d games in %d systems (%.0f ms)", len(by_key), len(games), (time.time() - t0) * 1000)
        self.core.registry.emit("library.scanned", library=self)

    def scan_async(self, done=None):
        def run():
            self.scan()
            if done:
                done()
        threading.Thread(target=run, daemon=True, name="library-scan").start()

    def count(self, system_id):
        return len(self.games.get(system_id, ()))

    def total(self):
        return len(self.by_key)

    def get(self, key) -> Optional[Game]:
        return self.by_key.get(key)

    def sorted_games(self, system_id, mode="name"):
        lst = list(self.games.get(system_id, ()))
        gd = self.core.gamedata
        if mode == "recent":
            lst.sort(key=lambda g: -(gd.get(g.key, "last") or 0))
        elif mode == "plays":
            lst.sort(key=lambda g: -(gd.get(g.key, "plays") or 0))
        return lst

    def favorites(self):
        return sorted((g for g in self.by_key.values() if self.core.gamedata.is_favorite(g.key)),
                      key=lambda g: g.name.lower())

    def recent(self, limit=30):
        gd = self.core.gamedata
        played = [g for g in self.by_key.values() if gd.get(g.key, "last")]
        return sorted(played, key=lambda g: -gd.get(g.key, "last"))[:limit]


def _m3u_entries(path):
    out = set()
    base = os.path.dirname(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    out.add(os.path.normcase(os.path.abspath(os.path.join(base, line))))
    except OSError:
        pass
    return out


def _cue_entries(path):
    out = set()
    base = os.path.dirname(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r'FILE\s+"([^"]+)"', f.read()):
                out.add(os.path.normcase(os.path.abspath(os.path.join(base, m.group(1)))))
    except OSError:
        pass
    return out
