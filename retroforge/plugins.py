"""Plugin discovery, loading and the public plugin API.

A plugin is a folder containing ``plugin.json`` and a Python entry module with
``register(api)``. Plugins are searched in the shipped ``plugins/`` folder and
in ``/userdata/plugins`` (user plugins override shipped ones with the same id).
"""
import importlib.util
import json
import logging
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import API_VERSION
from .model import Collection, Emulator, MenuEntry, Shader, System
from .settings import SettingDef

log = logging.getLogger("retroforge.plugins")


class PluginAPI:
    """Everything a plugin is allowed to touch. Kept small and stable."""

    version = API_VERSION

    def __init__(self, core, plugin_id, plugin_dir=None):
        self.core = core
        self.id = plugin_id
        self.dir = Path(plugin_dir) if plugin_dir else None
        self.registry = core.registry
        self.settings = core.settings
        self.paths = core.paths
        self.log = logging.getLogger(f"retroforge.plugin.{plugin_id}")

    # -- registration ----------------------------------------------------------
    def _add(self, kind, item_id, obj):
        if hasattr(obj, "origin"):
            try:
                obj.origin = self.id
            except AttributeError:
                pass
        return self.registry.add(kind, item_id, obj, origin=self.id)

    def add_system(self, system=None, **kw):
        system = system or System(**kw)
        return self._add("system", system.id, system)

    def add_emulator(self, emulator=None, **kw):
        emulator = emulator or Emulator(**kw)
        return self._add("emulator", emulator.id, emulator)

    def add_emulator_to_system(self, system_id, emulator_id, first=False):
        s = self.registry.get("system", system_id)
        if s and emulator_id not in s.emulators:
            s.emulators = ((emulator_id,) + s.emulators) if first else (s.emulators + (emulator_id,))

    def add_shader(self, shader=None, **kw):
        shader = shader or Shader(**kw)
        return self._add("shader", shader.id, shader)

    def add_setting(self, setting=None, **kw):
        setting = setting or SettingDef(**kw)
        setting.origin = self.id
        return self._add("setting", setting.key, setting)

    def add_theme(self, theme: dict):
        theme.setdefault("origin", self.id)
        if self.dir and "dir" not in theme:
            theme["dir"] = str(self.dir)
        return self._add("theme", theme["id"], theme)

    def add_soundpack(self, pack_id, name, style=None, **params):
        return self._add("soundpack", pack_id, {"id": pack_id, "name": name, "style": style or pack_id, **params})

    def add_background(self, bg_id, factory):
        """factory(theme: dict, params: dict) -> object with update(dt) and draw(surface)."""
        return self._add("background", bg_id, factory)

    def add_screen(self, screen_id, factory):
        """factory(app, **kwargs) -> Screen. Open it with app.push(screen_id, ...)."""
        return self._add("screen", screen_id, factory)

    def add_menu_entry(self, entry_id, label, action, icon="*", section="system", order=50):
        return self._add("menu_entry", entry_id, MenuEntry(entry_id, label, action, icon, section, order))

    def add_collection(self, coll_id, name, query, color="#888888", short="", order=50):
        return self._add("collection", coll_id, Collection(coll_id, name, query, color, short or name, order))

    def add_rom_detector(self, fn, detector_id=None):
        return self._add("rom_detector", detector_id or f"{self.id}.{fn.__name__}", fn)

    # -- events ----------------------------------------------------------------
    def on(self, event, fn, priority=0):
        self.registry.on(event, fn, priority, origin=self.id)

    # -- helpers ---------------------------------------------------------------
    def setting(self, key, system=None, game=None, default=None):
        return self.settings.get(key, system, game, default)

    def data_dir(self):
        d = self.paths.config / "plugins" / self.id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def notify(self, text, kind="info"):
        self.registry.emit("ui.notify", text=text, kind=kind)


@dataclass
class PluginInfo:
    id: str
    name: str
    version: str = "0"
    description: str = ""
    author: str = ""
    api: int = API_VERSION
    entry: str = "main.py"
    default_enabled: bool = True
    path: Optional[Path] = None
    builtin: bool = True
    status: str = "unloaded"       # loaded | disabled | error | incompatible
    error: str = ""
    module: object = field(default=None, repr=False)


class PluginManager:
    def __init__(self, core):
        self.core = core
        self.plugins = {}

    def discover(self):
        found = {}
        for root, builtin in ((self.core.paths.builtin_plugins, True), (self.core.paths.plugins, False)):
            if not root.is_dir():
                continue
            for d in sorted(root.iterdir()):
                manifest = d / "plugin.json"
                if not manifest.is_file():
                    continue
                try:
                    meta = json.loads(manifest.read_text(encoding="utf-8"))
                    known = PluginInfo.__dataclass_fields__
                    info = PluginInfo(**{k: v for k, v in meta.items() if k in known})
                    info.path, info.builtin = d, builtin
                    found[info.id] = info
                except Exception as e:
                    log.error("bad plugin manifest %s: %s", manifest, e)
        self.plugins = found
        return found

    def enabled(self, info):
        disabled = self.core.settings.get("plugins.disabled", default=[]) or []
        enabled = self.core.settings.get("plugins.enabled", default=[]) or []
        if info.id in disabled:
            return False
        return info.default_enabled or info.id in enabled

    def set_enabled(self, plugin_id, on):
        dis = set(self.core.settings.get("plugins.disabled", default=[]) or [])
        en = set(self.core.settings.get("plugins.enabled", default=[]) or [])
        (dis.discard if on else dis.add)(plugin_id)
        (en.add if on else en.discard)(plugin_id)
        self.core.settings.data["global"]["plugins.disabled"] = sorted(dis)
        self.core.settings.data["global"]["plugins.enabled"] = sorted(en)
        self.core.settings.save()

    def load_all(self):
        self.discover()
        for info in self.plugins.values():
            if not self.enabled(info):
                info.status = "disabled"
                continue
            self.load(info)

    def load(self, info):
        if int(info.api) > API_VERSION:
            info.status, info.error = "incompatible", f"benötigt API {info.api} (OS hat {API_VERSION})"
            return
        entry = info.path / info.entry
        try:
            modname = f"retroforge_plugin_{info.id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(modname, entry,
                                                          submodule_search_locations=[str(info.path)])
            mod = importlib.util.module_from_spec(spec)
            sys.modules[modname] = mod
            spec.loader.exec_module(mod)
            mod.register(PluginAPI(self.core, info.id, info.path))
            info.module, info.status = mod, "loaded"
            log.info("plugin %s %s loaded", info.id, info.version)
        except Exception as e:
            info.status = "error"
            info.error = f"{type(e).__name__}: {e}"
            log.error("plugin %s failed:\n%s", info.id, traceback.format_exc())
            self.core.registry.off_origin(info.id)
