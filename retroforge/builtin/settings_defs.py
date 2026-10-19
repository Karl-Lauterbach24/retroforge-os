"""Core setting definitions (everything the settings screen shows)."""
from ..settings import GAME, GLOBAL, SYSTEM, SettingDef

G = (GLOBAL,)
GS = (GLOBAL, SYSTEM)
GSG = (GLOBAL, SYSTEM, GAME)
SG = (SYSTEM, GAME)


def _themes(core, system, game):
    return [(t["id"], t.get("name", t["id"])) for t in core.registry.all("theme")]


def _soundpacks(core, system, game):
    return [(p["id"], p["name"]) for p in core.registry.all("soundpack")] + [("off", "Aus")]


def _shaders(core, system, game):
    gpu = core.assessment.cap.gpu if core and core.assessment else 5
    out = []
    for sh in core.registry.all("shader"):
        label = sh.name
        if sh.weight >= 4 and gpu < 4:
            label += "  (zu schwer?)"
        out.append((sh.id, label))
    return out


def _emulators(core, system, game):
    if system is None:
        return [("auto", "Automatisch")]
    sysdef = core.registry.get("system", system)
    out = [("auto", "Automatisch (beste Wahl)")]
    for eid in sysdef.emulators if sysdef else ():
        emu = core.registry.get("emulator", eid)
        if emu:
            out.append((eid, emu.name + (" – Standalone" if emu.kind == "standalone" else "")))
    return out


def _has_system(core, system, game):
    return system is not None


DEFS = [
    # ---- Oberfläche ----------------------------------------------------------
    SettingDef("ui.theme", "Theme", "synthwave", "Oberfläche", choices=_themes, scopes=G, order=1),
    SettingDef("ui.animations", "Animationen", "full", "Oberfläche",
               choices=[("full", "Voll"), ("reduced", "Reduziert"), ("off", "Aus (Energiesparen)")],
               scopes=G, order=2, help="'Aus' zeichnet den Hintergrund nur einmal – ideal für Pi Zero & Co."),
    SettingDef("ui.fps", "Bildrate der Oberfläche", 60, "Oberfläche",
               choices=[(30, "30 fps"), (60, "60 fps"), (120, "120 fps")], scopes=G, order=3),
    SettingDef("ui.crt_overlay", "CRT-Scanlines auf der Oberfläche", False, "Oberfläche", "bool", scopes=G, order=4),
    SettingDef("ui.show_empty", "Systeme ohne Spiele anzeigen", True, "Oberfläche", "bool", scopes=G, order=5),
    SettingDef("ui.show_unsupported", "Nicht lauffähige Systeme anzeigen", False, "Oberfläche", "bool",
               scopes=G, order=6),
    SettingDef("ui.clock24", "24-Stunden-Uhr", True, "Oberfläche", "bool", scopes=G, order=7),
    SettingDef("ui.sort", "Spiele sortieren nach", "name", "Oberfläche",
               choices=[("name", "Name"), ("recent", "Zuletzt gespielt"), ("plays", "Am meisten gespielt")],
               scopes=GS, order=8),
    # ---- Audio ----------------------------------------------------------------
    SettingDef("audio.music_mode", "Hintergrundmusik", "theme", "Audio",
               choices=[("theme", "Theme-Musik (Chiptune)"), ("playlist", "Eigene Musik (/userdata/music)"),
                        ("shuffle", "Eigene Musik – Zufall"), ("off", "Aus")], scopes=G, order=1),
    SettingDef("audio.music_volume", "Musik-Lautstärke", 50, "Audio", "range", scopes=G, order=2),
    SettingDef("audio.sound_pack", "Menü-Sounds", "theme", "Audio",
               choices=lambda c, s, g: [("theme", "Wie Theme")] + _soundpacks(c, s, g), scopes=G, order=3),
    SettingDef("audio.sfx_volume", "Sound-Lautstärke", 70, "Audio", "range", scopes=G, order=4),
    SettingDef("audio.duck_in_game", "Musik im Spiel ausblenden", True, "Audio", "bool", scopes=G, order=5),
    # ---- Video (pro System / pro Spiel überschreibbar) ------------------------
    SettingDef("video.shader", "Filter / Shader", "none", "Video", choices=_shaders, scopes=GSG, order=1,
               help="RetroArch-Kerne nutzen Slang-Shader, Standalone-Emulatoren ReShade über gamescope."),
    SettingDef("video.scaling", "Skalierung", "integer", "Video",
               choices=[("integer", "Ganzzahlig (pixelgenau)"), ("integer_over", "Ganzzahlig + Überscan"),
                        ("fit", "Einpassen"), ("stretch", "Strecken"), ("fill", "Füllen (Zoom)")],
               scopes=GSG, order=2),
    SettingDef("video.aspect", "Seitenverhältnis", "auto", "Video",
               choices=[("auto", "Automatisch"), ("4:3", "4:3"), ("16:9", "16:9"), ("8:7", "8:7 (SNES-PAR)"),
                        ("1:1", "1:1 Pixel"), ("full", "Vollbild")], scopes=GSG, order=3),
    SettingDef("video.internal_res", "Interne Auflösung (3D)", 1, "Video",
               choices=[(1, "Nativ"), (2, "2×"), (3, "3× (≈1080p)"), (4, "4×"), (6, "6× (≈4K)"), (8, "8×")],
               scopes=GSG, order=4, help="Upscaling direkt im Emulator – kostet GPU-Leistung."),
    SettingDef("video.upscaler", "Ausgabe-Upscaler", "none", "Video",
               choices=[("none", "Aus"), ("fsr", "AMD FSR 1"), ("nis", "NVIDIA NIS"), ("pixel", "Pixel-Art"),
                        ("linear", "Weich (bilinear)")], scopes=GSG, order=5,
               help="Über gamescope; skaliert das fertige Bild auf die Bildschirmauflösung."),
    SettingDef("video.smooth", "Bildglättung (bilinear)", False, "Video", "bool", scopes=GSG, order=6),
    SettingDef("video.bezel", "Bezel / Rahmen-Artwork", "off", "Video",
               choices=[("off", "Aus"), ("auto", "Automatisch (falls vorhanden)")], scopes=GSG, order=7),
    SettingDef("video.widescreen", "Widescreen-Hack (3D)", False, "Video", "bool", scopes=GSG, order=8),
    SettingDef("video.rotation", "Bildschirmdrehung", "auto", "Video",
               choices=[("auto", "Automatisch"), (0, "0°"), (90, "90° (TATE)"), (180, "180°"), (270, "270°")],
               scopes=GSG, order=9),
    SettingDef("video.renderer", "Grafik-API", "auto", "Video",
               choices=[("auto", "Automatisch"), ("vulkan", "Vulkan"), ("glcore", "OpenGL Core"),
                        ("gl", "OpenGL / GLES")], scopes=GSG, order=10),
    SettingDef("video.vsync", "VSync", True, "Video", "bool", scopes=GSG, order=11),
    SettingDef("video.vrr", "Variable Refresh Rate", False, "Video", "bool", scopes=GSG, order=12),
    # ---- Latenz & Komfort -----------------------------------------------------
    SettingDef("game.runahead", "Run-Ahead (Latenz senken)", 0, "Latenz & Komfort",
               choices=[(0, "Aus"), (1, "1 Frame"), (2, "2 Frames"), (3, "3 Frames")], scopes=GSG, order=1),
    SettingDef("game.rewind", "Zurückspulen", False, "Latenz & Komfort", "bool", scopes=GSG, order=2),
    SettingDef("game.autosave", "Auto-Speichern & Fortsetzen", True, "Latenz & Komfort", "bool", scopes=GSG, order=3),
    SettingDef("game.ff_speed", "Vorspulen-Tempo", 0, "Latenz & Komfort",
               choices=[(0, "Max"), (2, "2×"), (3, "3×"), (4, "4×"), (8, "8×")], scopes=GSG, order=4),
    SettingDef("game.achievements", "RetroAchievements", False, "Latenz & Komfort", "bool", scopes=GSG, order=5),
    # ---- Emulator --------------------------------------------------------------
    SettingDef("emulator", "Emulator", "auto", "Emulator", choices=_emulators, scopes=SG, order=1,
               visible=_has_system),
    SettingDef("emu.gamescope", "Standalone in gamescope starten", True, "Emulator", "bool", scopes=GSG, order=2,
               help="Ermöglicht FSR/NIS/ReShade-Filter und sauberes Vollbild ohne Desktop."),
    # ---- System ------------------------------------------------------------------
    SettingDef("system.gpu_class", "Leistungsklasse GPU", "auto", "System",
               choices=[("auto", "Automatisch erkennen")] + [(i, f"Klasse {i} erzwingen") for i in range(6)],
               scopes=G, order=1, help="Falls die Erkennung danebenliegt (z. B. unbekannte GPU)."),
    SettingDef("system.hotkey", "Hotkey fürs In-Game-Menü", "select", "System",
               choices=[("select", "Select + Start"), ("guide", "Home/Guide-Taste"), ("l3r3", "L3 + R3")],
               scopes=G, order=2),
    SettingDef("system.cpu_governor", "CPU-Profil", "balanced", "System",
               choices=[("powersave", "Akku sparen"), ("balanced", "Ausgewogen"), ("performance", "Maximale Leistung")],
               scopes=GSG, order=3, help="Auf dem OS über cpufreq gesetzt, auch pro Spiel."),
]
