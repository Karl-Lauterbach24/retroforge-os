"""Built-in system database.

``bios`` entries are file names relative to /userdata/bios; ``a|b`` means
"one of", a ``*`` makes it a glob. ``ladder``/``demand`` drive the hardware
ladder ("bis zu welcher Konsole reicht meine Hardware?").
"""
from ..model import System

ICONS = {"n64": "pad_n64", "mastersystem": "pad_nes", "sg1000": "pad_nes"}
DISC = (".chd", ".cue", ".iso", ".m3u", ".pbp")


def s(id, name, short, maker, year, exts, emus, kind="console", color="#888888",
      bios=(), demand=0, ladder=False, note=""):
    return System(id=id, name=name, short=short, maker=maker, year=year, exts=tuple(exts),
                  emulators=tuple(emus), kind=kind, color=color, bios=tuple(bios),
                  demand=demand, ladder=ladder, note=note, icon=ICONS.get(id, ""))


NINTENDO, SEGA, SONY, MS, NEC, SNK, ATARI = "#e4000f", "#1a5fd6", "#3a3a8c", "#107c10", "#f39800", "#c8a000", "#c0392b"

SYSTEMS = [
    # Nintendo
    s("nes", "Nintendo Entertainment System", "NES", "Nintendo", 1983, [".nes", ".unf", ".unif"],
      ["fceumm", "nestopia", "mesen"], color=NINTENDO),
    s("fds", "Famicom Disk System", "FDS", "Nintendo", 1986, [".fds"], ["fceumm", "mesen"],
      color=NINTENDO, bios=["disksys.rom"]),
    s("snes", "Super Nintendo", "SNES", "Nintendo", 1990, [".sfc", ".smc", ".bs", ".st"],
      ["snes9x", "bsnes"], color="#7b5aa6"),
    s("n64", "Nintendo 64", "N64", "Nintendo", 1996, [".z64", ".n64", ".v64"],
      ["mupen64plus_next", "parallel_n64"], color="#2a8c3a", demand=12, ladder=True),
    s("gamecube", "GameCube", "GC", "Nintendo", 2001, [".rvz", ".iso", ".gcz", ".ciso", ".gcm"],
      ["dolphin", "dolphin_lr"], color="#6a4fb3", demand=30, ladder=True),
    s("wii", "Wii", "WII", "Nintendo", 2006, [".rvz", ".wbfs", ".iso", ".wad"],
      ["dolphin", "dolphin_lr"], color="#29a8e0", demand=32, ladder=True),
    s("wiiu", "Wii U", "WIIU", "Nintendo", 2012, [".wua", ".wud", ".wux", ".rpx"],
      ["cemu"], color="#009ac7", demand=50, ladder=True),
    s("switch", "Nintendo Switch", "SWITCH", "Nintendo", 2017, [".nsp", ".xci", ".nca"],
      ["eden", "ryujinx"], color="#e60012", bios=["switch/prod.keys"], demand=65, ladder=True),
    s("switch2", "Nintendo Switch 2", "SWITCH 2", "Nintendo", 2025, [".xci"], [],
      color="#e60012", demand=85, ladder=True,
      note="Stand 2026 existiert kein nutzbarer Switch-2-Emulator – ein Plugin kann ihn nachrüsten."),
    s("gb", "Game Boy", "GB", "Nintendo", 1989, [".gb"], ["gambatte", "sameboy", "mgba"],
      kind="handheld", color="#8b956d"),
    s("gbc", "Game Boy Color", "GBC", "Nintendo", 1998, [".gbc"], ["gambatte", "sameboy", "mgba"],
      kind="handheld", color="#6c3fa8"),
    s("gba", "Game Boy Advance", "GBA", "Nintendo", 2001, [".gba"], ["mgba"],
      kind="handheld", color="#4b3fa8"),
    s("nds", "Nintendo DS", "NDS", "Nintendo", 2004, [".nds", ".dsi"], ["melonds", "desmume"],
      kind="handheld", color="#9a9a9a", demand=14, ladder=True),
    s("3ds", "Nintendo 3DS", "3DS", "Nintendo", 2011, [".3ds", ".cci", ".cxi", ".3dsx", ".app"],
      ["azahar"], kind="handheld", color="#ce1126", demand=42, ladder=True),
    s("virtualboy", "Virtual Boy", "VB", "Nintendo", 1995, [".vb", ".vboy"], ["beetle_vb"],
      kind="handheld", color="#b30000"),
    s("pokemini", "Pokémon Mini", "PMINI", "Nintendo", 2001, [".min"], ["pokemini"],
      kind="handheld", color="#ffcb05"),
    # Sega
    s("sg1000", "SG-1000", "SG1000", "Sega", 1983, [".sg"], ["genesis_plus_gx"], color=SEGA),
    s("mastersystem", "Master System", "SMS", "Sega", 1985, [".sms"], ["genesis_plus_gx", "picodrive"], color=SEGA),
    s("megadrive", "Mega Drive / Genesis", "MD", "Sega", 1988, [".md", ".gen", ".smd", ".bin"],
      ["genesis_plus_gx", "picodrive"], color="#111111"),
    s("segacd", "Mega-CD", "MCD", "Sega", 1991, [".chd", ".cue", ".iso", ".m3u"],
      ["genesis_plus_gx", "picodrive"], color=SEGA,
      bios=["bios_CD_E.bin|bios_CD_U.bin|bios_CD_J.bin"]),
    s("sega32x", "32X", "32X", "Sega", 1994, [".32x"], ["picodrive"], color=SEGA),
    s("saturn", "Saturn", "SATURN", "Sega", 1994, [".chd", ".cue", ".iso", ".m3u", ".ccd"],
      ["yabasanshiro", "beetle_saturn"], color="#3f3f3f", bios=["sega_101.bin|mpr-17933.bin"]),
    s("dreamcast", "Dreamcast", "DC", "Sega", 1998, [".chd", ".gdi", ".cdi", ".cue", ".m3u"],
      ["flycast", "flycast_sa"], color="#f26522", bios=["dc/dc_boot.bin"], demand=20, ladder=True),
    s("naomi", "NAOMI", "NAOMI", "Sega", 1998, [".zip", ".7z", ".lst", ".dat"], ["flycast"],
      kind="arcade", color="#f26522", bios=["naomi.zip"]),
    s("gamegear", "Game Gear", "GG", "Sega", 1990, [".gg"], ["genesis_plus_gx"], kind="handheld", color="#222222"),
    # Sony
    s("psx", "PlayStation", "PS1", "Sony", 1994, DISC + (".exe",),
      ["swanstation", "pcsx_rearmed", "beetle_psx_hw", "duckstation"], color="#9a9a9a",
      bios=["scph5501.bin|scph1001.bin|scph7001.bin|scph5500.bin|scph5502.bin"]),
    s("ps2", "PlayStation 2", "PS2", "Sony", 2000, [".chd", ".iso", ".cso", ".gz", ".m3u"],
      ["pcsx2", "lrps2"], color=SONY, bios=["ps2/*.bin"], demand=35, ladder=True),
    s("ps3", "PlayStation 3", "PS3", "Sony", 2006, [".ps3", ".psn", ".iso"],
      ["rpcs3"], color="#222222", bios=["ps3/PS3UPDAT.PUP"], demand=60, ladder=True),
    s("ps4", "PlayStation 4", "PS4", "Sony", 2013, [".ps4"], ["shadps4"],
      color="#003791", demand=70, ladder=True),
    s("ps5", "PlayStation 5", "PS5", "Sony", 2020, [".ps5"], [], color="#ffffff", demand=92, ladder=True,
      note="Stand 2026 gibt es keinen lauffähigen PS5-Emulator – das System ist vorbereitet."),
    s("psp", "PlayStation Portable", "PSP", "Sony", 2004, [".iso", ".cso", ".pbp", ".chd"],
      ["ppsspp_lr", "ppsspp"], kind="handheld", color="#1f1f1f", demand=18, ladder=True),
    s("psvita", "PlayStation Vita", "VITA", "Sony", 2011, [".psvita"], ["vita3k"],
      kind="handheld", color="#0b3d91", demand=45, ladder=True),
    # Microsoft
    s("xbox", "Xbox", "XBOX", "Microsoft", 2001, [".iso", ".xiso"], ["xemu"], color=MS,
      bios=["mcpx_1.0.bin", "Complex_4627.bin"], demand=40, ladder=True),
    s("xbox360", "Xbox 360", "X360", "Microsoft", 2005, [".iso", ".xex", ".zar"], ["xenia"],
      color="#5dc21e", demand=62, ladder=True),
    s("xboxseries", "Xbox Series X|S", "SERIES", "Microsoft", 2020, [".xvc"], [],
      color="#107c10", demand=90, ladder=True,
      note="Für Xbox One/Series existiert Stand 2026 kein Emulator."),
    # NEC / SNK / Bandai / others
    s("pcengine", "PC Engine / TurboGrafx-16", "PCE", "NEC", 1987, [".pce", ".sgx"], ["beetle_pce"], color=NEC),
    s("pcenginecd", "PC Engine CD", "PCECD", "NEC", 1988, [".chd", ".cue", ".ccd", ".m3u"], ["beetle_pce"],
      color=NEC, bios=["syscard3.pce"]),
    s("pcfx", "PC-FX", "PCFX", "NEC", 1994, [".chd", ".cue", ".ccd"], ["beetle_pcfx"], color=NEC, bios=["pcfx.rom"]),
    s("neogeo", "Neo Geo", "NEOGEO", "SNK", 1990, [".zip", ".7z"], ["fbneo"], kind="arcade", color=SNK,
      bios=["neogeo.zip"]),
    s("ngp", "Neo Geo Pocket", "NGP", "SNK", 1998, [".ngp"], ["race", "beetle_ngp"], kind="handheld", color=SNK),
    s("ngpc", "Neo Geo Pocket Color", "NGPC", "SNK", 1999, [".ngc"], ["race", "beetle_ngp"], kind="handheld", color=SNK),
    s("wonderswan", "WonderSwan", "WS", "Bandai", 1999, [".ws"], ["beetle_wswan"], kind="handheld", color="#5a6e8c"),
    s("wonderswancolor", "WonderSwan Color", "WSC", "Bandai", 2000, [".wsc"], ["beetle_wswan"],
      kind="handheld", color="#5a6e8c"),
    s("3do", "3DO", "3DO", "Panasonic", 1993, [".chd", ".iso", ".cue"], ["opera"], color="#444444",
      bios=["panafz10.bin|panafz1.bin|goldstar.bin"]),
    # Atari
    s("atari2600", "Atari 2600", "2600", "Atari", 1977, [".a26", ".bin"], ["stella"], color=ATARI),
    s("atari5200", "Atari 5200", "5200", "Atari", 1982, [".a52"], ["a5200"], color=ATARI, bios=["5200.rom"]),
    s("atari7800", "Atari 7800", "7800", "Atari", 1986, [".a78"], ["prosystem"], color=ATARI),
    s("lynx", "Atari Lynx", "LYNX", "Atari", 1989, [".lnx", ".o"], ["handy"], kind="handheld", color=ATARI,
      bios=["lynxboot.img"]),
    s("jaguar", "Atari Jaguar", "JAGUAR", "Atari", 1993, [".j64", ".jag"], ["virtualjaguar"], color=ATARI),
    s("atarist", "Atari ST", "ST", "Atari", 1985, [".st", ".msa", ".stx"], ["hatari"], kind="computer",
      color=ATARI, bios=["tos.img"]),
    # Classic
    s("colecovision", "ColecoVision", "COLECO", "Coleco", 1982, [".col"], ["gearcoleco", "bluemsx"],
      color="#333333", bios=["colecovision.rom"]),
    s("intellivision", "Intellivision", "INTV", "Mattel", 1979, [".int"], ["freeintv"], color="#8a6d3b",
      bios=["exec.bin", "grom.bin"]),
    s("vectrex", "Vectrex", "VECTREX", "GCE", 1982, [".vec"], ["vecx"], color="#222222"),
    # Arcade
    s("arcade", "Arcade (FBNeo)", "ARCADE", "Diverse", 1978, [".zip", ".7z"], ["fbneo", "mame2003_plus", "mame"],
      kind="arcade", color="#d4145a"),
    s("mame", "MAME", "MAME", "Diverse", 1978, [".zip", ".7z", ".chd"], ["mame", "mame2003_plus"],
      kind="arcade", color="#3a7bd5"),
    # Computers
    s("dos", "MS-DOS", "DOS", "PC", 1981, [".zip", ".dosz", ".exe", ".com", ".bat", ".conf"], ["dosbox_pure"],
      kind="computer", color="#2c3e50"),
    s("c64", "Commodore 64", "C64", "Commodore", 1982, [".d64", ".t64", ".prg", ".crt", ".tap"], ["vice"],
      kind="computer", color="#7a6a53"),
    s("amiga", "Amiga", "AMIGA", "Commodore", 1985, [".adf", ".hdf", ".lha", ".ipf", ".m3u"], ["puae"],
      kind="computer", color="#c0392b", bios=["kick34005.A500|kick40068.A1200"]),
    s("amstradcpc", "Amstrad CPC", "CPC", "Amstrad", 1984, [".dsk", ".sna", ".cdt"], ["cap32"],
      kind="computer", color="#16a085"),
    s("zxspectrum", "ZX Spectrum", "ZX", "Sinclair", 1982, [".tzx", ".tap", ".z80", ".sna"], ["fuse"],
      kind="computer", color="#1a1a1a"),
    s("msx", "MSX", "MSX", "ASCII", 1983, [".rom", ".mx1", ".mx2", ".dsk"], ["bluemsx"], kind="computer",
      color="#2e86c1"),
    s("scummvm", "ScummVM", "SCUMM", "Diverse", 1987, [".scummvm"], ["scummvm"], kind="computer", color="#4caf50"),
    # Fantasy consoles
    s("pico8", "PICO-8", "PICO-8", "Lexaloffle", 2015, [".p8", ".png"], ["fake08"], kind="fantasy",
      color="#ff004d"),
]
