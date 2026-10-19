"""Central registry + event bus.

Everything in RetroForge – systems, emulators, shaders, themes, settings,
screens, background renderers, sound packs, ROM detectors – is registered
here. The core itself registers its built-ins through exactly the same calls a
plugin uses, so a plugin can add to or replace any part of the system.
"""
import logging
from collections import defaultdict

log = logging.getLogger("retroforge.registry")

# Known registry kinds (plugins may introduce new ones freely).
KINDS = ("system", "emulator", "shader", "theme", "setting", "screen",
         "menu_entry", "background", "soundpack", "rom_detector", "collection")


class Registry:
    def __init__(self):
        self._items = defaultdict(dict)
        self._origin = {}
        self._hooks = defaultdict(list)
        self._services = {}

    # -- items ---------------------------------------------------------------
    def add(self, kind, item_id, obj, origin="core", override=True):
        if item_id in self._items[kind]:
            if not override:
                raise KeyError(f"{kind} '{item_id}' already registered")
            log.info("%s '%s' overridden by %s", kind, item_id, origin)
        self._items[kind][item_id] = obj
        self._origin[(kind, item_id)] = origin
        return obj

    def remove(self, kind, item_id):
        self._items[kind].pop(item_id, None)
        self._origin.pop((kind, item_id), None)

    def get(self, kind, item_id, default=None):
        return self._items[kind].get(item_id, default)

    def has(self, kind, item_id):
        return item_id in self._items[kind]

    def all(self, kind):
        """All items of a kind, ordered by their ``order`` attribute (if any)."""
        items = list(self._items[kind].values())
        return sorted(items, key=lambda o: getattr(o, "order", 0))

    def ids(self, kind):
        return list(self._items[kind].keys())

    def origin(self, kind, item_id):
        return self._origin.get((kind, item_id))

    # -- events / hooks ------------------------------------------------------
    def on(self, event, fn, priority=0, origin="core"):
        self._hooks[event].append((priority, origin, fn))
        self._hooks[event].sort(key=lambda h: -h[0])

    def off_origin(self, origin):
        for event in self._hooks:
            self._hooks[event] = [h for h in self._hooks[event] if h[1] != origin]

    def emit(self, event, **kwargs):
        """Call every handler; returns the list of non-None results."""
        results = []
        for _, origin, fn in list(self._hooks.get(event, ())):
            try:
                r = fn(**kwargs)
                if r is not None:
                    results.append(r)
            except Exception:
                log.exception("hook %s from %s failed", event, origin)
        return results

    def filter(self, event, value, **kwargs):
        """Pipe ``value`` through every handler; a handler returning None keeps it."""
        for _, origin, fn in list(self._hooks.get(event, ())):
            try:
                r = fn(value, **kwargs)
                if r is not None:
                    value = r
            except Exception:
                log.exception("filter %s from %s failed", event, origin)
        return value

    # -- services (replaceable singletons, e.g. "scraper", "audio") ----------
    def provide(self, name, obj):
        self._services[name] = obj

    def service(self, name, default=None):
        return self._services.get(name, default)
