"""Optical drives: enumeration, media state and disc identification.

Identification works on any file-like source, so it is tested with small fake
images; the Linux-specific parts (sysfs, udev properties, TOC ioctls) only
supply facts about the medium.
"""
import glob
import os
import platform
import struct
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from retroforge.iso9660 import ISO9660, playstation_info

# What can be done per system with a disc in a PC drive.
#   play: emulators that boot straight from the drive (in order of preference)
#   rip:  "cd" (cdrdao, keeps audio tracks) or "dvd" (sector copy)
DISC_SYSTEMS = {
    "psx": {"play": ["duckstation", "beetle_psx_hw"], "rip": "cd"},
    "ps2": {"play": ["pcsx2"], "rip": "dvd"},
    "saturn": {"play": ["beetle_saturn"], "rip": "cd"},
    "segacd": {"play": ["genesis_plus_gx"], "rip": "cd"},
    "pcenginecd": {"play": ["beetle_pce"], "rip": "cd"},
    "pcfx": {"play": ["beetle_pcfx"], "rip": "cd"},
    "3do": {"play": ["opera"], "rip": "cd"},
    "dos": {"play": [], "rip": "cd"},
}

UNSUPPORTED = {
    "ps3": ["PS3-Discs sind verschlüsselt und lassen sich hier weder starten noch sichern.",
            "Mit einem kompatiblen Blu-ray-Laufwerk geht es außerhalb von RetroForge über „ps3-disc-dumper“ "
            "und die öffentlichen Disc-Schlüssel (IRD). Das Ergebnis kommt dann nach roms/ps3/<Spiel>.ps3/."],
    "bd": ["Diese Blu-ray ist verschlüsselt (PS4, PS5 oder Xbox One/Series) oder ein Film.",
           "Das Laufwerk liest zwar die Rohdaten, die Schlüssel stecken aber nur in der Konsole selbst.",
           "PS5-Spiele laufen in RetroForge nur über einen entschlüsselten Dump einer eigenen, "
           "gejailbreakten Konsole (Plugin AnyPS5)."],
    "unreadable": ["Das Laufwerk kann diese Disc nicht lesen.",
                   "GameCube-, Wii-, Wii-U- und Xbox-Discs sowie die GD-ROM der Dreamcast nutzen Formate, "
                   "die normale PC-Laufwerke nicht lesen. Solche Spiele lassen sich nur auf der jeweiligen "
                   "Konsole (z. B. mit CleanRip) sichern."],
    "audio": ["Das ist eine Audio-CD – kein Spiel."],
    "unknown": ["Für diese Disc wurde kein unterstütztes System erkannt."],
}


@dataclass
class Media:
    present: bool = False
    kind: str = ""                 # cd | dvd | bd | ""
    audio_tracks: int = 0
    data_tracks: int = 0
    label: str = ""
    size: int = 0                  # bytes, 0 if unknown
    first_data_lba: int = 0        # sector of the first data track (PC Engine CDs start with audio)


@dataclass
class DiscInfo:
    system: Optional[str] = None
    candidates: List[str] = field(default_factory=list)   # when unsure: let the user pick
    label: str = ""
    serial: str = ""
    problem: str = ""              # key of UNSUPPORTED, or ""
    device: str = ""
    media: Media = field(default_factory=Media)

    @property
    def title(self):
        name = (self.label or "").replace("_", " ").strip().title()
        if self.serial and self.serial.replace("-", " ").lower() not in name.lower():
            return f"{name} [{self.serial}]" if name else self.serial
        return name or "Unbenannte Disc"

    def actions(self):
        caps = DISC_SYSTEMS.get(self.system or "", {})
        return {"play": bool(caps.get("play")), "rip": bool(caps.get("rip"))}


# ---------------------------------------------------------------------------
def drives():
    """Optical drives on this machine (Linux); empty elsewhere."""
    if platform.system() != "Linux":
        return []
    return sorted("/dev/" + os.path.basename(p) for p in glob.glob("/sys/block/sr*"))


def _udev_props(dev):
    try:
        out = subprocess.run(["udevadm", "info", "--query=property", dev], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


CDROMREADTOCHDR, CDROMREADTOCENTRY, CDROM_LBA = 0x5305, 0x5306, 0x01


def _first_data_lba(dev):
    """LBA of the first data track via the CD-ROM TOC ioctls (0 when unknown)."""
    try:
        import fcntl
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    except (ImportError, OSError):
        return 0
    try:
        first, last = struct.unpack("BB", fcntl.ioctl(fd, CDROMREADTOCHDR, b"\0\0"))
        for track in range(first, last + 1):
            # struct cdrom_tocentry: track, adr:4|ctrl:4, format, (pad), int lba, datamode (+pad)
            buf = fcntl.ioctl(fd, CDROMREADTOCENTRY, struct.pack("BBBxiB3x", track, 0, CDROM_LBA, 0, 0))
            _, adr_ctrl, _, lba, _ = struct.unpack("BBBxiB3x", buf)
            if (adr_ctrl >> 4) & 0x04:                        # cdte_ctrl (high nibble): data track
                return lba
    except OSError:
        pass
    finally:
        os.close(fd)
    return 0


def media(dev):
    """Facts about the medium in ``dev`` (Linux, via sysfs/udev)."""
    name = os.path.basename(dev)
    m = Media()
    try:
        m.size = int(open(f"/sys/block/{name}/size").read().strip()) * 512
    except (OSError, ValueError):
        pass
    p = _udev_props(dev)
    m.present = p.get("ID_CDROM_MEDIA") == "1" or m.size > 0
    m.kind = "bd" if p.get("ID_CDROM_MEDIA_BD") == "1" else "dvd" if p.get("ID_CDROM_MEDIA_DVD") == "1" else \
        "cd" if p.get("ID_CDROM_MEDIA_CD") == "1" else ""
    m.audio_tracks = int(p.get("ID_CDROM_MEDIA_TRACK_COUNT_AUDIO", 0) or 0)
    m.data_tracks = int(p.get("ID_CDROM_MEDIA_TRACK_COUNT_DATA", 0) or 0)
    m.label = p.get("ID_FS_LABEL", "")
    if m.present and m.audio_tracks and m.data_tracks:
        m.first_data_lba = _first_data_lba(dev)
    return m


def signature(dev):
    """Changes when a disc is inserted, swapped or removed (cheap, for polling)."""
    m = media(dev)
    return (m.present, m.kind, m.size, m.label, m.audio_tracks, m.data_tracks)


# ---------------------------------------------------------------------------
def _read(f, offset, size):
    try:
        f.seek(offset)
        return f.read(size)
    except OSError:
        return b""


def identify_stream(f, m: Media) -> DiscInfo:
    info = DiscInfo(media=m, label=m.label)
    if m.data_tracks == 0 and m.audio_tracks > 0:
        info.problem = "audio"
        return info
    base = m.first_data_lba * 2048
    head = _read(f, base, 0x10000)
    if len(head) < 2048:
        if m.audio_tracks and m.data_tracks:
            info.candidates = ["pcenginecd", "pcfx", "segacd", "saturn"]   # data track not reachable: ask
        else:
            info.problem = "bd" if m.kind == "bd" else "unreadable"
        return info
    text = head[:0x1000].decode("latin-1", "replace")
    if head.startswith(b"SEGA SEGASATURN"):
        info.system = "saturn"
        info.serial = head[0x20:0x2A].decode("ascii", "replace").strip()
        info.label = info.label or head[0x60:0xD0].decode("ascii", "replace").strip()
        return info
    if head.startswith(b"SEGADISCSYSTEM") or head.startswith(b"SEGA SEGACD"):
        info.system = "segacd"
        info.label = info.label or head[0x150:0x180].decode("ascii", "replace").strip()
        return info
    if head[0:1] == b"\x01" and head[1:6] == b"\x5a" * 5:
        info.system = "3do"
        return info
    if "PC Engine CD-ROM SYSTEM" in head[:0x2000].decode("latin-1", "replace"):
        info.system = "pcenginecd"
        return info
    if "PC-FX:Hu_CD-ROM" in text:
        info.system = "pcfx"
        return info
    try:
        iso = ISO9660(f, base)
    except ValueError:
        iso = None
    if iso:
        info.label = info.label or iso.volume_id
        root = iso.root()
        system, serial = playstation_info(iso)
        if system:
            info.system, info.serial = system, serial
            return info
        if "PS3_DISC.SFB" in root or "PS3_GAME" in root:
            info.system, info.problem = "ps3", "ps3"
            return info
        if "PLAYSTATION" in iso.system_id:
            info.system = "psx"
            return info
        if "SEGAKATANA" in iso.system_id:
            info.system, info.problem = "dreamcast", "unreadable"
            return info
        if m.kind == "bd":
            info.problem = "bd"
            return info
        info.system = "dos"          # an ordinary PC CD-ROM: can be saved for DOSBox
        return info
    if m.kind == "bd":
        info.problem = "bd"
    elif m.audio_tracks and m.data_tracks:
        info.candidates = ["pcenginecd", "segacd", "saturn", "pcfx"]   # mixed mode, no known header
    else:
        info.problem = "unknown"
    return info


def identify(dev, m: Optional[Media] = None) -> DiscInfo:
    m = m or media(dev)
    try:
        with open(dev, "rb", buffering=0) as f:
            info = identify_stream(f, m)
    except OSError:
        info = DiscInfo(media=m, label=m.label, problem="unreadable")
    info.device = dev
    return info


def retroarch_path(dev):
    """RetroArch's VFS path for a physical disc (cdrom://driveN.cue, N = sr index + 1)."""
    if platform.system() == "Windows" and len(dev) <= 3:
        return f"cdrom://{dev[0].lower()}:/drive.cue"
    idx = int("".join(c for c in os.path.basename(dev) if c.isdigit()) or 0)
    return f"cdrom://drive{idx + 1}.cue"
