"""Built-in emulator definitions.

Requirements are deliberately conservative estimates; see ``hw/tiers.py`` for
the meaning of the cpu/gpu numbers. Download sources for standalone emulators
point at the upstream GitHub releases and are matched by regex, so they keep
working across versions. Emulators without a stable public release channel
use ``{"type": "manual"}`` and are installed by dropping the AppImage into
``/userdata/emulators``.
"""
from ..model import Emulator, Req

X64 = ("x86_64",)
X64_ARM = ("x86_64", "arm64")
LR_FEATURES = ("shaders", "rewind", "runahead", "achievements", "netplay")
LR3D_FEATURES = ("shaders", "upscale", "achievements", "netplay")
SA_FEATURES = ("upscale", "widescreen")


def lr(id, name, core, min=Req(), rec=Req(), features=LR_FEATURES, upscale=None, **kw):
    return Emulator(id=id, name=name, kind="libretro", core=core, min=min, rec=rec,
                    features=features, upscale=upscale, source={"type": "libretro"}, **kw)


def sa(id, name, binary, args, min, rec, source, features=SA_FEATURES, upscale=None, **kw):
    return Emulator(id=id, name=name, kind="standalone", binary=binary, args=tuple(args),
                    min=min, rec=rec, features=features, upscale=upscale, source=source, **kw)


def gh(repo, **assets):
    """GitHub release source; ``assets`` maps arch family → asset regex."""
    return {"type": "github", "repo": repo, "assets": assets}


# -- upscale helpers: return {"core_options": {...}} / {"args": [...]} / {"ini": [...]} ----
def _opt(key, fmt):
    return lambda s: {"core_options": {key: fmt(s)}}


def _ini(path, section, key, fmt=str):
    return lambda s: {"ini": [(path, section, key, fmt(s))]}


EMULATORS = [
    # ---- 8/16-bit & handhelds ------------------------------------------------
    lr("fceumm", "FCEUmm", "fceumm", Req(cpu=0.3)),
    lr("nestopia", "Nestopia UE", "nestopia", Req(cpu=0.4)),
    lr("mesen", "Mesen", "mesen", Req(cpu=1.0), Req(cpu=1.4)),
    lr("snes9x", "Snes9x", "snes9x", Req(cpu=0.4)),
    lr("bsnes", "bsnes (genau)", "bsnes", Req(cpu=1.4), Req(cpu=2.2)),
    lr("gambatte", "Gambatte", "gambatte", Req(cpu=0.3)),
    lr("sameboy", "SameBoy", "sameboy", Req(cpu=0.6)),
    lr("mgba", "mGBA", "mgba", Req(cpu=0.5), Req(cpu=0.8)),
    lr("pokemini", "PokeMini", "pokemini", Req(cpu=0.2)),
    lr("beetle_vb", "Beetle VB", "mednafen_vb", Req(cpu=0.6)),
    lr("genesis_plus_gx", "Genesis Plus GX", "genesis_plus_gx", Req(cpu=0.4)),
    lr("picodrive", "PicoDrive", "picodrive", Req(cpu=0.3)),
    lr("beetle_pce", "Beetle PCE Fast", "mednafen_pce_fast", Req(cpu=0.4)),
    lr("beetle_pcfx", "Beetle PC-FX", "mednafen_pcfx", Req(cpu=1.0)),
    lr("beetle_wswan", "Beetle WonderSwan", "mednafen_wswan", Req(cpu=0.4)),
    lr("race", "RACE", "race", Req(cpu=0.3)),
    lr("beetle_ngp", "Beetle NeoPop", "mednafen_ngp", Req(cpu=0.4)),
    lr("stella", "Stella", "stella", Req(cpu=0.3)),
    lr("a5200", "a5200", "a5200", Req(cpu=0.4)),
    lr("prosystem", "ProSystem", "prosystem", Req(cpu=0.3)),
    lr("handy", "Handy", "handy", Req(cpu=0.3)),
    lr("virtualjaguar", "Virtual Jaguar", "virtualjaguar", Req(cpu=1.8), Req(cpu=2.5)),
    lr("bluemsx", "blueMSX", "bluemsx", Req(cpu=0.5)),
    lr("freeintv", "FreeIntv", "freeintv", Req(cpu=0.3)),
    lr("vecx", "vecx", "vecx", Req(cpu=0.3)),
    lr("gearcoleco", "Gearcoleco", "gearcoleco", Req(cpu=0.3)),
    lr("fake08", "FAKE-08", "fake08", Req(cpu=0.4)),
    # ---- computers ---------------------------------------------------------
    lr("dosbox_pure", "DOSBox Pure", "dosbox_pure", Req(cpu=0.8), Req(cpu=1.5)),
    lr("vice", "VICE x64sc", "vice_x64sc", Req(cpu=0.8)),
    lr("puae", "PUAE (Amiga)", "puae", Req(cpu=1.0), Req(cpu=1.6)),
    lr("cap32", "Caprice32", "cap32", Req(cpu=0.4)),
    lr("fuse", "Fuse", "fuse", Req(cpu=0.3)),
    lr("hatari", "Hatari", "hatari", Req(cpu=0.8)),
    lr("scummvm", "ScummVM", "scummvm", Req(cpu=0.5), features=("shaders",)),
    # ---- arcade ------------------------------------------------------------
    lr("fbneo", "FinalBurn Neo", "fbneo", Req(cpu=0.6), Req(cpu=1.2)),
    lr("mame2003_plus", "MAME 2003-Plus", "mame2003_plus", Req(cpu=0.5), Req(cpu=1.0)),
    lr("mame", "MAME (aktuell)", "mame", Req(cpu=1.5, ram=2), Req(cpu=3.0, threads=4, ram=4)),
    # ---- 32/64-bit & 3D ----------------------------------------------------
    lr("pcsx_rearmed", "PCSX ReARMed", "pcsx_rearmed", Req(cpu=0.3), Req(cpu=0.7)),
    lr("swanstation", "SwanStation", "swanstation", Req(cpu=0.8, gpu=1), Req(cpu=1.4, gpu=2),
       features=LR3D_FEATURES + ("rewind", "runahead"),
       upscale=_opt("swanstation_GPU_ResolutionScale", str)),
    lr("beetle_psx_hw", "Beetle PSX HW", "mednafen_psx_hw", Req(cpu=1.6, gpu=2), Req(cpu=2.4, gpu=3),
       features=LR3D_FEATURES + ("rewind",),
       upscale=_opt("beetle_psx_hw_internal_resolution", lambda s: "1x(native)" if s == 1 else f"{s}x")),
    lr("mupen64plus_next", "Mupen64Plus-Next", "mupen64plus_next", Req(cpu=1.0, gpu=2), Req(cpu=1.6, gpu=3),
       features=LR3D_FEATURES,
       upscale=_opt("mupen64plus-43screensize", lambda s: f"{320 * s}x{240 * s}")),
    lr("parallel_n64", "ParaLLEl N64", "parallel_n64", Req(cpu=1.4, gpu=3, vulkan="1.1"), Req(cpu=2.0, gpu=4),
       features=LR3D_FEATURES),
    lr("melonds", "melonDS DS", "melondsds", Req(cpu=1.3), Req(cpu=2.0), features=LR3D_FEATURES),
    lr("desmume", "DeSmuME", "desmume", Req(cpu=1.6), Req(cpu=2.4)),
    lr("yabasanshiro", "YabaSanshiro", "yabasanshiro", Req(cpu=1.4, gpu=2), Req(cpu=2.2, gpu=3)),
    lr("beetle_saturn", "Beetle Saturn", "mednafen_saturn", Req(cpu=3.0, threads=2, archs=X64_ARM),
       Req(cpu=3.6, threads=4)),
    lr("flycast", "Flycast", "flycast", Req(cpu=1.4, gpu=2), Req(cpu=2.4, gpu=3),
       features=LR3D_FEATURES + ("widescreen",),
       upscale=_opt("reicast_internal_resolution", lambda s: f"{640 * s}x{480 * s}")),
    lr("ppsspp_lr", "PPSSPP (libretro)", "ppsspp", Req(cpu=1.4, gpu=2), Req(cpu=2.4, gpu=3),
       features=LR3D_FEATURES,
       upscale=_opt("ppsspp_internal_resolution", lambda s: f"{480 * s}x{272 * s}")),
    lr("opera", "Opera (3DO)", "opera", Req(cpu=1.4), Req(cpu=2.0)),
    lr("dolphin_lr", "Dolphin (libretro)", "dolphin", Req(cpu=2.8, threads=2, gpu=3, archs=X64_ARM),
       Req(cpu=4.0, threads=4, gpu=4), features=LR3D_FEATURES),
    lr("lrps2", "LRPS2 (libretro)", "pcsx2", Req(cpu=3.4, threads=4, gpu=3, ram=4, archs=X64, isa=("sse4_1",)),
       Req(cpu=4.5, threads=6, gpu=4), features=LR3D_FEATURES),

    # ---- standalone (run inside gamescope for FSR/NIS/ReShade) --------------
    sa("dolphin", "Dolphin", "dolphin-emu", ["-b", "-e", "{rom}"],
       Req(cpu=2.6, threads=2, gpu=3, ram=2, archs=X64_ARM), Req(cpu=3.8, threads=4, gpu=3, ram=4),
       {"type": "apt", "package": "dolphin-emu"},
       upscale=lambda s: {"args": ["-C", f"GFX.Settings.InternalResolution={s}"]},
       features=SA_FEATURES + ("achievements",)),
    sa("pcsx2", "PCSX2", "pcsx2-qt", ["-batch", "-fullscreen", "-nogui", "--", "{rom}"],
       Req(cpu=3.2, threads=4, gpu=3, ram=4, archs=X64, isa=("sse4_1",)),
       Req(cpu=4.5, threads=6, gpu=4, ram=8, vulkan="1.1", isa=("avx2",)),
       gh("PCSX2/pcsx2", x86_64=r"linux-appimage-x64-Qt\.AppImage$"),
       upscale=_ini("~/.config/PCSX2/inis/PCSX2.ini", "EmuCore/GS", "upscale_multiplier"),
       features=SA_FEATURES + ("achievements",)),
    sa("duckstation", "DuckStation", "duckstation-qt", ["-batch", "-fullscreen", "--", "{rom}"],
       Req(cpu=1.2, gpu=2, archs=X64_ARM), Req(cpu=2.0, gpu=3),
       gh("stenzek/duckstation", x86_64=r"x64\.AppImage$", arm64=r"arm64\.AppImage$"),
       upscale=_ini("~/.local/share/duckstation/settings.ini", "GPU", "ResolutionScale")),
    sa("ppsspp", "PPSSPP", "PPSSPPSDL", ["--fullscreen", "{rom}"],
       Req(cpu=1.4, gpu=2), Req(cpu=2.4, gpu=3), {"type": "apt", "package": "ppsspp"},
       upscale=_ini("~/.config/ppsspp/PSP/SYSTEM/ppsspp.ini", "Graphics", "InternalResolution")),
    sa("flycast_sa", "Flycast", "flycast", ["{rom}"],
       Req(cpu=1.4, gpu=2, archs=X64_ARM), Req(cpu=2.4, gpu=3),
       gh("flyinghead/flycast", x86_64=r"x86_64\.AppImage$")),
    sa("azahar", "Azahar", "azahar", ["-f", "{rom}"],
       Req(cpu=2.6, threads=2, gpu=3, ram=4, archs=X64_ARM), Req(cpu=3.8, threads=4, gpu=3, ram=8),
       gh("azahar-emu/azahar", x86_64=r"\.AppImage$")),
    sa("xemu", "xemu", "xemu", ["-full-screen", "-dvd_path", "{rom}"],
       Req(cpu=3.5, threads=4, gpu=3, ram=4, archs=X64_ARM), Req(cpu=4.5, threads=4, gpu=4, ram=8),
       gh("xemu-project/xemu", x86_64=r"x86_64\.AppImage$", arm64=r"aarch64\.AppImage$")),
    sa("vita3k", "Vita3K", "Vita3K", ["-F", "-r", "{content}"],
       Req(cpu=3.0, threads=4, gpu=3, ram=4, vulkan="1.1", archs=X64_ARM),
       Req(cpu=4.0, threads=6, gpu=4, ram=8),
       gh("Vita3K/Vita3K", x86_64=r"x86_64\.AppImage$")),
    sa("cemu", "Cemu", "Cemu", ["-f", "-g", "{rom}"],
       Req(cpu=3.8, threads=4, gpu=4, ram=6, vulkan="1.1", archs=X64),
       Req(cpu=5.0, threads=6, gpu=4, ram=8),
       gh("cemu-project/Cemu", x86_64=r"x86_64\.AppImage$")),
    sa("rpcs3", "RPCS3", "rpcs3", ["--no-gui", "{rom}"],
       Req(cpu=4.2, threads=6, gpu=4, ram=8, vulkan="1.1", archs=X64_ARM, isa=("sse4_1",)),
       Req(cpu=5.5, threads=12, gpu=5, ram=16, isa=("avx2",)),
       gh("RPCS3/rpcs3-binaries-linux", x86_64=r"linux64\.AppImage$")),
    sa("xenia", "Xenia Canary", "xenia_canary", ["--fullscreen", "{rom}"],
       Req(cpu=4.5, threads=4, gpu=4, ram=8, vulkan="1.1", archs=X64, isa=("avx",)),
       Req(cpu=5.5, threads=8, gpu=5, ram=16, isa=("avx2",)),
       {"type": "manual", "hint": "xenia_canary (Linux-Build) nach /userdata/emulators kopieren"},
       experimental=True, note="Xenia unter Linux ist noch experimentell"),
    sa("eden", "Eden", "eden", ["-f", "-g", "{rom}"],
       Req(cpu=3.6, threads=4, gpu=4, ram=8, vulkan="1.1", archs=X64_ARM),
       Req(cpu=4.8, threads=6, gpu=5, ram=16, vulkan="1.3"),
       {"type": "manual", "hint": "Eden-AppImage nach /userdata/emulators kopieren (Keys in bios/switch)"}),
    sa("ryujinx", "Ryujinx (Ryubing)", "Ryujinx", ["--fullscreen", "{rom}"],
       Req(cpu=4.0, threads=4, gpu=4, ram=8, vulkan="1.1", archs=X64_ARM),
       Req(cpu=5.0, threads=6, gpu=5, ram=16, vulkan="1.3"),
       {"type": "manual", "hint": "Ryujinx-AppImage nach /userdata/emulators kopieren (Keys in bios/switch)"}),
    sa("shadps4", "shadPS4", "shadps4", ["{rom}"],
       Req(cpu=5.0, threads=6, gpu=4, ram=8, vulkan="1.3", archs=X64, isa=("avx", "f16c", "bmi1")),
       Req(cpu=6.0, threads=8, gpu=5, ram=16, isa=("avx2",)),
       gh("shadps4-emu/shadPS4", x86_64=r"linux.*\.(zip|AppImage)$"),
       experimental=True, note="shadPS4: Kompatibilität wächst, viele Titel laufen noch nicht"),
]
