"""Guess the system of a loose ROM file (used by the importer).

1. Header magic (reliable, works for ambiguous extensions like .bin/.iso).
2. Unique file extension.
3. Plugins can add detectors via ``api.add_rom_detector(fn)``;
   ``fn(path, head: bytes) -> system_id | None``.
"""
import os
import zipfile

HEAD_SIZE = 0x10000


def _at(head, off, magic):
    return head[off:off + len(magic)] == magic


NINTENDO_LOGO_START = bytes.fromhex("CEED6666CC0D000B")


def header_detect(path, head):
    if _at(head, 0, b"NES\x1a"):
        return "nes"
    if _at(head, 0, b"FDS\x1a") or _at(head, 1, b"*NINTENDO-HVC*"):
        return "fds"
    if _at(head, 0x104, NINTENDO_LOGO_START):
        return "gbc" if len(head) > 0x143 and head[0x143] in (0x80, 0xC0) else "gb"
    if _at(head, 0x04, bytes.fromhex("24FFAE51699AA221")):
        return "gba"
    if _at(head, 0xC0, bytes.fromhex("24FFAE51699AA221")):
        return "nds"
    if head[:4] in (b"\x80\x37\x12\x40", b"\x37\x80\x40\x12", b"\x40\x12\x37\x80"):
        return "n64"
    if _at(head, 0x100, b"SEGA 32X"):
        return "sega32x"
    if _at(head, 0x100, b"SEGA"):
        return "megadrive"
    if _at(head, 0x7FF0, b"TMR SEGA"):
        return "mastersystem"
    if _at(head, 0x1C, bytes.fromhex("C2339F3D")):
        return "gamecube"
    if _at(head, 0x18, bytes.fromhex("5D1C9EA3")) or _at(head, 0, b"WBFS"):
        return "wii"
    if _at(head, 0, b"RVZ\x01"):
        # RVZ stores the disc header after a 0x48 byte file header (+0x58 = disc magic area)
        return "wii" if _at(head, 0x58 + 0x18, bytes.fromhex("5D1C9EA3")) else "gamecube"
    if _at(head, 0, b"PFS0"):
        return "switch"
    if _at(head, 0x100, b"HEAD"):
        return "switch"
    if _at(head, 0, b"NCSD") or _at(head, 0x100, b"NCSD"):
        return "3ds"
    if _at(head, 0, b"ATARI7800", ) or _at(head, 1, b"ATARI7800"):
        return "atari7800"
    if _at(head, 0, b"LYNX"):
        return "lynx"
    if _at(head, 0, b"MComprHD"):
        return None   # CHD: system can't be derived from the container header
    if _at(head, 0x8001, b"CD001"):
        return iso_detect(head)
    if _at(head, 0x9319, b"CD001"):   # raw 2352-byte sectors (BIN of a CUE)
        return iso_detect(head, raw=True)
    if _at(head, 0, b"MICROSOFT*XBOX*MEDIA"):
        return "xbox"
    return None


def iso_detect(head, raw=False):
    text = head.decode("latin-1", "replace")
    if "PLAYSTATION" in text:
        return "ps2" if "BOOT2" in text else "psx"
    if "PSP GAME" in text or "UMD_DATA" in text:
        return "psp"
    if "SEGA SEGASATURN" in text:
        return "saturn"
    if "SEGADISCSYSTEM" in text or "SEGA SEGACD" in text:
        return "segacd"
    if "SEGA SEGAKATANA" in text:
        return "dreamcast"
    return None


def _unique_ext_map(registry):
    seen = {}
    for sysdef in registry.all("system"):
        for ext in sysdef.exts:
            seen.setdefault(ext, set()).add(sysdef.id)
    return {ext: next(iter(ids)) for ext, ids in seen.items() if len(ids) == 1}


def detect(path, registry):
    path = str(path)
    ext = os.path.splitext(path)[1].lower()
    head = b""
    try:
        if ext == ".zip" and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                if len(names) == 1:
                    inner_ext = os.path.splitext(names[0])[1].lower()
                    with z.open(names[0]) as f:
                        head = f.read(HEAD_SIZE)
                    res = header_detect(path, head) or _unique_ext_map(registry).get(inner_ext)
                    if res:
                        return res
            return None   # multi-file zips are arcade sets → needs folder choice
        with open(path, "rb") as f:
            head = f.read(HEAD_SIZE)
    except OSError:
        return None
    for fn in registry.all("rom_detector"):
        try:
            r = fn(path, head)
            if r:
                return r
        except Exception:
            pass
    if _at(head, 0x8001, b"CD001"):
        # cooked ISO: SYSTEM.CNF tells PS1 (BOOT) and PS2 (BOOT2) apart reliably
        from .iso9660 import ISO9660, playstation_info
        try:
            with open(path, "rb") as f:
                system, _ = playstation_info(ISO9660(f))
            if system:
                return system
        except (OSError, ValueError, KeyError):
            pass
    return header_detect(path, head) or _unique_ext_map(registry).get(ext)
