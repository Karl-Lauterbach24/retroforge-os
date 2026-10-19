"""The Core ties registry, settings, plugins, hardware, library and launcher
together. It has no UI dependency, so it can be used headless (CLI, tests,
a future web remote, ...)."""
import json
import logging
import threading

from . import builtin
from .emumanager import EmulatorManager
from .hw.probe import HardwareInfo, probe
from .hw.tiers import assess
from .launcher import Launcher
from .library import GameData, Library
from .paths import Paths
from .plugins import PluginAPI, PluginManager
from .registry import Registry
from .settings import Settings, SYSTEM

log = logging.getLogger("retroforge.core")


class Core:
    def __init__(self, home=None):
        self.paths = Paths(home)
        self.paths.ensure()
        self.registry = Registry()
        self.settings = Settings(self.registry, self.paths.file("settings.json"))
        self.plugins = PluginManager(self)
        self.gamedata = GameData(self.paths.file("gamedata.json"))
        self.library = Library(self)
        self.launcher = Launcher(self)
        self.emus = EmulatorManager(self)
        self.hw: HardwareInfo = HardwareInfo()
        self.assessment = None
        self.display_size = (1920, 1080)
        self.registry.on("settings.changed", self._on_setting)

    # -- boot ------------------------------------------------------------------
    def boot(self, do_probe=True, scan=True):
        builtin.register(PluginAPI(self, "core"))
        self.load_themes()
        self.settings.load()
        self.gamedata.load()
        self.plugins.load_all()
        if do_probe:
            self.probe()
        else:
            self.load_cached_probe()
        if scan:
            self.library.scan()
        self.registry.emit("boot", core=self)
        return self

    def load_themes(self):
        for root in (self.paths.builtin_themes, self.paths.themes):
            if not root.is_dir():
                continue
            for f in sorted(root.glob("*/theme.json")):
                try:
                    t = json.loads(f.read_text(encoding="utf-8"))
                    t.setdefault("id", f.parent.name)
                    t["dir"] = str(f.parent)
                    t.setdefault("origin", "core" if root == self.paths.builtin_themes else "user")
                    self.registry.add("theme", t["id"], t, origin=t["origin"])
                except Exception as e:
                    log.error("theme %s broken: %s", f, e)

    # -- hardware ----------------------------------------------------------------
    def probe(self):
        hw = probe()
        hw = self.registry.filter("hw.probed", hw, core=self)
        self.hw = hw
        try:
            self.paths.file("hardware.json").write_text(json.dumps(hw.to_dict(), indent=1), encoding="utf-8")
        except OSError:
            pass
        self.reassess()
        return hw

    def load_cached_probe(self):
        try:
            self.hw = HardwareInfo.from_dict(json.loads(self.paths.file("hardware.json").read_text("utf-8")))
            self.reassess()
            return True
        except (OSError, ValueError, TypeError):
            return False

    def probe_async(self, done=None):
        def run():
            self.probe()
            if done:
                done()
        threading.Thread(target=run, daemon=True, name="hw-probe").start()

    def reassess(self):
        override = self.settings.get("system.gpu_class")
        self.assessment = assess(self.hw, self.registry, None if override in (None, "auto") else int(override))
        self.registry.emit("hw.assessed", assessment=self.assessment, core=self)

    def _on_setting(self, key, **_):
        if key == "system.gpu_class" and self.hw.arch:
            self.reassess()

    # -- convenience ---------------------------------------------------------------
    def visible_systems(self):
        show_empty = self.settings.get("ui.show_empty", default=True)
        show_unsup = self.settings.get("ui.show_unsupported", default=False)
        out = []
        for s in self.registry.all("system"):
            has_games = self.library.count(s.id) > 0
            status = self.assessment.status(s.id) if self.assessment else 3
            if has_games:
                out.append(s)
            elif show_empty and (show_unsup or status >= 2):
                out.append(s)
        return out

    def apply_recommended_filters(self):
        for sys_id, values in builtin.recommended_filters(self).items():
            for k, v in values.items():
                self.settings.set(k, v, SYSTEM, sys_id, save=False)
        self.settings.save()

    def bios_status(self, system):
        """[(entry, found_name_or_None)] for each required BIOS entry."""
        out = []
        for entry in system.bios:
            found = None
            for alt in entry.split("|"):
                hits = list(self.paths.bios.glob(alt)) if "*" in alt else \
                    ([self.paths.bios / alt] if (self.paths.bios / alt).exists() else [])
                if hits:
                    found = hits[0].name
                    break
            out.append((entry, found))
        return out
