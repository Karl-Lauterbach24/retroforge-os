"""Filesystem layout.

On the OS everything user-facing lives on the exFAT ``/userdata`` partition so
ROMs, BIOS files and music can be copied from any PC. During development the
layout is created under ``./userdata`` (or ``$RETROFORGE_HOME``).
"""
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PKG_DIR.parent


def default_home():
    env = os.environ.get("RETROFORGE_HOME")
    if env:
        return Path(env)
    if Path("/userdata").is_dir():
        return Path("/userdata")
    return PROJECT_DIR / "userdata"


class Paths:
    def __init__(self, home=None):
        self.home = Path(home) if home else default_home()
        self.roms = self.home / "roms"
        self.bios = self.home / "bios"
        self.saves = self.home / "saves"
        self.states = self.home / "states"
        self.screenshots = self.home / "screenshots"
        self.music = self.home / "music"
        self.themes = self.home / "themes"
        self.plugins = self.home / "plugins"
        self.emulators = self.home / "emulators"
        self.import_inbox = self.home / "import"
        self.config = self.home / "system" / "retroforge"
        self.cache = self.config / "cache"
        self.logs = self.config / "logs"
        # Shipped with the OS (read-only rootfs on the image).
        self.builtin_themes = PROJECT_DIR / "themes"
        self.builtin_plugins = PROJECT_DIR / "plugins"

    def ensure(self):
        for p in (self.roms, self.bios, self.saves, self.states, self.screenshots,
                  self.music, self.themes, self.plugins, self.emulators,
                  self.import_inbox, self.config, self.cache, self.logs):
            p.mkdir(parents=True, exist_ok=True)

    def system_roms(self, system_id):
        return self.roms / system_id

    def file(self, name):
        return self.config / name
