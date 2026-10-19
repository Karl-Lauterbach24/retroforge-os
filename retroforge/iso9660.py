"""Minimal read-only ISO 9660 reader (root directory only).

Enough to tell console discs apart by their files (SYSTEM.CNF, PS3_DISC.SFB …)
and to read a game's serial. Works on image files and on optical drives
(/dev/srN delivers 2048-byte "cooked" sectors).
"""
import struct

SECTOR = 2048


class ISO9660:
    def __init__(self, f, base=0):
        """``f``: binary file object; ``base``: byte offset of the session's sector 0."""
        self.f, self.base = f, base
        pvd = self.sector(16)
        if pvd[0:1] != b"\x01" or pvd[1:6] != b"CD001":
            raise ValueError("kein ISO-9660-Dateisystem")
        self.system_id = pvd[8:40].decode("ascii", "replace").strip()
        self.volume_id = pvd[40:72].decode("ascii", "replace").strip()
        root = pvd[156:190]
        self.root_lba, self.root_size = struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0]
        self._root = None

    def sector(self, lba, count=1):
        self.f.seek(self.base + lba * SECTOR)
        data = self.f.read(SECTOR * count)
        if len(data) < SECTOR * count:
            raise ValueError("Sektor nicht lesbar")
        return data

    def root(self):
        """{NAME: (lba, size, is_dir)} of the root directory (names upper-case, without ';1')."""
        if self._root is not None:
            return self._root
        data = self.sector(self.root_lba, max(1, -(-self.root_size // SECTOR)))[:self.root_size]
        out, pos = {}, 0
        while pos < len(data):
            n = data[pos]
            if n == 0:                       # records never span sectors: skip to the next one
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + n]
            name_len = rec[32]
            name = rec[33:33 + name_len]
            if name not in (b"\x00", b"\x01"):
                clean = name.decode("ascii", "replace").split(";")[0].rstrip(".").upper()
                out[clean] = (struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0],
                              bool(rec[25] & 2))
            pos += n
        self._root = out
        return out

    def read(self, name, limit=65536):
        lba, size, _ = self.root()[name.upper()]
        size = min(size, limit)
        return self.sector(lba, max(1, -(-size // SECTOR)))[:size]


def playstation_info(iso):
    """('psx'|'ps2', serial) from SYSTEM.CNF, or (None, '')."""
    if "SYSTEM.CNF" not in iso.root():
        return None, ""
    text = iso.read("SYSTEM.CNF", 4096).decode("ascii", "replace")
    system = "ps2" if "BOOT2" in text.upper() else "psx" if "BOOT" in text.upper() else None
    serial = ""
    for line in text.splitlines():
        if line.strip().upper().startswith(("BOOT2", "BOOT")):
            exe = line.split("\\")[-1].split(":")[-1].split(";")[0].strip()
            serial = exe.replace("_", "-").replace(".", "")    # SLUS_012.34 -> SLUS-01234
            break
    return system, serial
