"""Layered settings: global  <  system  <  game.

Every value a user can change is described by a :class:`SettingDef` in the
registry, so plugins can add settings that automatically show up in the UI
with the same per-system / per-game override mechanics.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence, Union

log = logging.getLogger("retroforge.settings")

GLOBAL, SYSTEM, GAME = "global", "system", "game"
ALL_SCOPES = (GLOBAL, SYSTEM, GAME)

Choices = Union[Sequence, Callable[..., Sequence]]


@dataclass
class SettingDef:
    key: str
    label: str
    default: Any
    category: str = "Allgemein"
    type: str = "choice"          # choice | bool | range | text
    choices: Optional[Choices] = None   # [(value, label)] or callable(core, system, game)
    scopes: tuple = ALL_SCOPES
    help: str = ""
    min: int = 0
    max: int = 100
    step: int = 10
    order: int = 0
    origin: str = "core"
    visible: Optional[Callable[..., bool]] = None   # visible(core, system, game)

    def choice_list(self, core=None, system=None, game=None):
        if self.type == "bool":
            return [(True, "An"), (False, "Aus")]
        if self.type == "range":
            return [(v, str(v)) for v in range(self.min, self.max + 1, self.step)]
        c = self.choices
        if callable(c):
            c = c(core, system, game)
        return [x if isinstance(x, tuple) else (x, str(x)) for x in (c or ())]

    def label_for(self, value, core=None, system=None, game=None):
        for v, label in self.choice_list(core, system, game):
            if v == value:
                return label
        return str(value)


@dataclass
class Resolved:
    value: Any
    source: str    # "game" | "system" | "global" | "default"


class Settings:
    def __init__(self, registry, path):
        self.registry = registry
        self.path = path
        self.data = {"global": {}, "systems": {}, "games": {}}

    # -- persistence ---------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k in self.data:
                self.data[k] = raw.get(k, {})
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("settings file broken, keeping defaults (backup written)")
            try:
                os.replace(self.path, str(self.path) + ".broken")
            except OSError:
                pass

    def save(self):
        tmp = str(self.path) + ".tmp"
        os.makedirs(os.path.dirname(str(self.path)), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, self.path)   # atomic, survives power loss mid-write

    # -- access --------------------------------------------------------------
    def definition(self, key) -> Optional[SettingDef]:
        return self.registry.get("setting", key)

    def _layer(self, scope, target=None, create=False):
        if scope == GLOBAL:
            return self.data["global"]
        bucket = self.data["systems" if scope == SYSTEM else "games"]
        if create:
            return bucket.setdefault(target, {})
        return bucket.get(target, {})

    def resolve(self, key, system=None, game=None) -> Resolved:
        if game is not None:
            layer = self._layer(GAME, game)
            if key in layer:
                return Resolved(layer[key], GAME)
        if system is not None:
            layer = self._layer(SYSTEM, system)
            if key in layer:
                return Resolved(layer[key], SYSTEM)
        if key in self.data["global"]:
            return Resolved(self.data["global"][key], GLOBAL)
        d = self.definition(key)
        return Resolved(d.default if d else None, "default")

    def get(self, key, system=None, game=None, default=None):
        r = self.resolve(key, system, game)
        return default if r.value is None else r.value

    def set(self, key, value, scope=GLOBAL, target=None, save=True):
        self._layer(scope, target, create=True)[key] = value
        if save:
            self.save()
        self.registry.emit("settings.changed", key=key, value=value, scope=scope, target=target)

    def unset(self, key, scope=GLOBAL, target=None, save=True):
        layer = self._layer(scope, target)
        if key in layer:
            del layer[key]
            if scope != GLOBAL and not layer:
                self.data["systems" if scope == SYSTEM else "games"].pop(target, None)
            if save:
                self.save()
            self.registry.emit("settings.changed", key=key, value=None, scope=scope, target=target)

    def overrides(self, scope, target):
        """Keys explicitly set on a system or game (for the UI badge)."""
        return dict(self._layer(scope, target))

    def definitions(self, scope=GLOBAL):
        return [d for d in self.registry.all("setting") if scope in d.scopes]
