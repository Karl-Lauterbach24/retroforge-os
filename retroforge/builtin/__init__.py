"""The core registers its own content through the plugin API ("dogfooding"),
so every built-in system, emulator, shader or setting can be replaced by a
plugin that registers the same id."""
from .emulators import EMULATORS
from .settings_defs import DEFS
from .shaders import SHADERS
from .systems import SYSTEMS


def register(api):
    for i, s in enumerate(SYSTEMS):
        s.order = i
        api.add_system(s)
    for i, e in enumerate(EMULATORS):
        e.order = i
        api.add_emulator(e)
    for sh in SHADERS:
        api.add_shader(sh)
    for d in DEFS:
        api.add_setting(d)
    api.add_soundpack("chiptune", "Chiptune (Rechteck-Blips)")
    api.add_soundpack("soft", "Soft (Glocken)")
    api.add_soundpack("arcade", "Arcade (Laser & Münzen)")
    api.add_collection("recent", "Zuletzt gespielt", lambda core: core.library.recent(),
                       color="#4cc9f0", short="ZULETZT", order=0)
    api.add_collection("favorites", "Favoriten", lambda core: core.library.favorites(),
                       color="#ffd166", short="FAVORITEN", order=1)


def recommended_filters(core):
    """System-level filter presets that match the detected GPU class."""
    gpu = core.assessment.cap.gpu if core.assessment else 2
    crt = "crt-royale" if gpu >= 5 else "crt-lottes" if gpu >= 4 else "crt-geom" if gpu >= 3 else \
        "crt-pi" if gpu >= 1 else "none"
    out = {}
    for s in core.registry.all("system"):
        if s.kind == "handheld":
            out[s.id] = {"video.shader": "dmg" if s.id == "gb" else "lcd-grid" if gpu >= 2 else "none",
                         "video.scaling": "integer"}
        elif s.kind in ("console", "arcade") and s.year < 2000:
            out[s.id] = {"video.shader": crt, "video.scaling": "integer"}
        elif s.year >= 2000 and s.kind != "computer":
            scale = 4 if gpu >= 5 else 3 if gpu >= 4 else 2 if gpu >= 3 else 1
            out[s.id] = {"video.internal_res": scale, "video.shader": "none", "video.scaling": "fit"}
    return out
