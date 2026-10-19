"""Locates and installs emulators on demand.

The base image only ships RetroArch plus a handful of cores; everything else
is fetched when the user installs it from the UI (or bundled at image build
time with ``os/build.sh --bundle``). That keeps the image small and every
emulator up to date.
"""
import json
import logging
import os
import platform
import re
import shutil
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("retroforge.emus")

BUILDBOT_ARCH = {"x86_64": "x86_64", "x86": "x86", "arm64": "aarch64", "arm32": "armhf"}
SYSTEM_CORE_DIRS = ["/usr/lib/libretro", "/usr/lib/x86_64-linux-gnu/libretro",
                    "/usr/lib/aarch64-linux-gnu/libretro", "/usr/lib/arm-linux-gnueabihf/libretro",
                    "/usr/lib/i386-linux-gnu/libretro", "/usr/local/lib/libretro",
                    "~/.config/retroarch/cores"]
USER_AGENT = "RetroForge-OS/0.1"


def _core_suffix():
    return {"Windows": ".dll", "Darwin": ".dylib"}.get(platform.system(), ".so")


class EmulatorManager:
    def __init__(self, core):
        self.core = core

    @property
    def cores_dir(self):
        return self.core.paths.emulators / "cores"

    def retroarch(self):
        local = sorted(self.core.paths.emulators.glob("RetroArch*.AppImage"))
        return str(local[-1]) if local else shutil.which("retroarch")

    def core_path(self, core_name):
        fn = f"{core_name}_libretro{_core_suffix()}"
        for d in [self.cores_dir] + [Path(os.path.expanduser(p)) for p in SYSTEM_CORE_DIRS]:
            p = Path(d) / fn
            if p.is_file():
                return str(p)
        return None

    def standalone_path(self, emu):
        root = self.core.paths.emulators
        names = {emu.binary.lower(), emu.id.lower()}
        if root.is_dir():
            for p in sorted(root.iterdir()):
                low = p.name.lower()
                if p.is_file() and any(low == n or (low.startswith(n) and low.endswith(".appimage"))
                                       for n in names):
                    return str(p)
            sub = root / emu.id / emu.binary
            if sub.is_file():
                return str(sub)
        return shutil.which(emu.binary)

    def locate(self, emu):
        if emu.kind == "libretro":
            return self.core_path(emu.core) if self.retroarch() else None
        return self.standalone_path(emu)

    def installed(self, emu):
        return self.locate(emu) is not None

    # -- installation ---------------------------------------------------------
    def can_install(self, emu):
        src = emu.source or {}
        if src.get("type") == "libretro":
            return self.core.hw.family in BUILDBOT_ARCH
        if src.get("type") == "github":
            return self.core.hw.family in src.get("assets", {})
        if src.get("type") == "custom":   # plugin-provided installer
            check = src.get("can_install")
            return bool(check(self.core)) if callable(check) else True
        return False

    def install_hint(self, emu):
        src = emu.source or {}
        t = src.get("type")
        if t == "apt":
            return f"Im OS-Image über das Paket '{src['package']}' enthalten (Build-Profil)."
        if t == "custom":
            return src.get("hint", "")
        if t == "manual":
            return src.get("hint", "Manuell nach /userdata/emulators kopieren.")
        if t == "github" and self.core.hw.family not in src.get("assets", {}):
            return f"Kein offizieller Build für {self.core.hw.family}."
        return ""

    def install(self, emu, progress=None):
        """Blocking download+install. Raises on failure. Returns installed path."""
        src = emu.source or {}
        fam = self.core.hw.family
        if src.get("type") == "custom":
            return src["install"](self, emu, progress)
        if src.get("type") == "libretro":
            url = (f"https://buildbot.libretro.com/nightly/linux/{BUILDBOT_ARCH[fam]}/latest/"
                   f"{emu.core}_libretro.so.zip")
            self.cores_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.cores_dir / f".{emu.core}.zip"
            self._download(url, tmp, progress)
            with zipfile.ZipFile(tmp) as z:
                z.extractall(self.cores_dir)
            tmp.unlink()
            return self.core_path(emu.core)
        if src.get("type") == "github":
            asset = self.latest_asset(src["repo"], src["assets"][fam])
            dest = self.core.paths.emulators / asset["name"]
            self._download(asset["browser_download_url"], dest, progress)
            if dest.suffix.lower() == ".appimage":
                dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                return str(dest)
            target = self.core.paths.emulators / emu.id
            target.mkdir(exist_ok=True)
            if zipfile.is_zipfile(dest):
                with zipfile.ZipFile(dest) as z:
                    z.extractall(target)
            elif tarfile.is_tarfile(dest):
                with tarfile.open(dest) as t:
                    try:
                        t.extractall(target, filter="data")
                    except TypeError:   # Python < 3.11.4 has no extraction filters
                        safe = [m for m in t.getmembers()
                                if not (m.name.startswith("/") or ".." in Path(m.name).parts
                                        or m.issym() or m.islnk())]
                        t.extractall(target, members=safe)
            dest.unlink()
            for p in target.rglob("*"):
                if p.is_file() and (p.name == emu.binary or p.suffix.lower() == ".appimage"):
                    p.chmod(p.stat().st_mode | stat.S_IXUSR)
            return self.standalone_path(emu)
        raise RuntimeError(self.install_hint(emu) or "Keine Installationsquelle bekannt")

    def latest_asset(self, repo, pattern):
        """The newest release asset of a GitHub repo whose name matches ``pattern``."""
        api = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            rel = json.load(r)
        rx = re.compile(pattern)
        asset = next((a for a in rel.get("assets", []) if rx.search(a["name"])), None)
        if not asset:
            raise RuntimeError(f"Kein passendes Release-Asset ({pattern}) in {repo} gefunden")
        asset["release_tag"] = rel.get("tag_name", "")
        return asset

    def download(self, url, dest, progress=None):
        self._download(url, dest, progress)

    def _download(self, url, dest, progress=None):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        tmp = Path(str(dest) + ".part")
        with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        os.replace(tmp, dest)
