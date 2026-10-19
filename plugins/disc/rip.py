"""Saves a disc as CHD.

CD:  cdrdao (raw, keeps audio tracks) -> toc2cue -> chdman createcd
DVD: sector copy in Python (with retries)  -> chdman createdvd (falls back to .iso)
Optionally verified against Redump/No-Intro DAT files in /userdata/system/dats,
which also gives the game its proper name.
"""
import hashlib
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = {"cd": ("cdrdao", "toc2cue", "chdman"), "dvd": ()}
BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
MSF = re.compile(r"(\d{1,2}):(\d\d):(\d\d)")


class RipError(RuntimeError):
    pass


def safe_name(name):
    return BAD_CHARS.sub("", name).strip(" .") or "Disc"


def _frames(m):
    return (int(m.group(1)) * 60 + int(m.group(2))) * 75 + int(m.group(3))


def run_streaming(cmd, on_line):
    """Runs ``cmd``, feeding each output line (cdrdao uses \\r) to on_line. Returns the exit code."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                            bufsize=1)
    buf = ""
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            break
        if ch in "\r\n":
            if buf.strip():
                on_line(buf.strip())
            buf = ""
        else:
            buf += ch
    return proc.wait()


def lookup_dat(dats_dir, sha1, size):
    """Game name for a file hash in any DAT (logiqx XML) of ``dats_dir``, or None."""
    if not dats_dir or not Path(dats_dir).is_dir():
        return None
    for dat in sorted(Path(dats_dir).glob("*.dat")):
        try:
            for _, el in ET.iterparse(str(dat), events=("end",)):
                if el.tag == "game" or el.tag == "machine":
                    for rom in el.findall("rom"):
                        if rom.get("sha1", "").lower() == sha1 and int(rom.get("size", -1)) == size:
                            return el.get("name")
                    el.clear()
        except (ET.ParseError, OSError, ValueError):
            continue
    return None


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Ripper:
    def __init__(self, run=run_streaming, which=shutil.which):
        self.run, self.which = run, which

    def missing_tools(self, kind):
        return [t for t in TOOLS.get(kind, ()) if not self.which(t)]

    def rip(self, info, kind, dest_dir, progress=lambda f, m="": None, dats_dir=None):
        """Returns {"path", "name", "verified"}; raises RipError."""
        missing = self.missing_tools(kind)
        if missing:
            raise RipError(f"Fehlende Programme: {', '.join(missing)} (Pakete cdrdao und mame-tools)")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = safe_name(info.title)
        work = dest_dir / f".rip-{name}"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        try:
            image = self._rip_cd(info, work, progress) if kind == "cd" else self._rip_dvd(info, work, progress)
            progress(0.9, "Prüfe gegen DAT-Datenbank …")
            verified_name = lookup_dat(dats_dir, _sha1(image), image.stat().st_size) if dats_dir else None
            if verified_name:
                name = safe_name(verified_name)
            progress(0.92, "Komprimiere zu CHD …")
            out = self._to_chd(image, work, dest_dir, name, kind)
            return {"path": out, "name": name, "verified": bool(verified_name) if dats_dir else None}
        finally:
            shutil.rmtree(work, ignore_errors=True)

    # -- CD ----------------------------------------------------------------------
    def _rip_cd(self, info, work, progress):
        total = [0]
        last = [""]

        def on_line(line):
            last[0] = line
            for m in re.finditer(r"length (\d{1,2}:\d\d:\d\d)", line):
                total[0] += _frames(MSF.search(m.group(1)))
            pos = MSF.findall(line)
            if total[0] and pos and "length" not in line:
                mm, ss, ff = (int(x) for x in pos[-1])
                progress(min(0.85, ((mm * 60 + ss) * 75 + ff) / total[0] * 0.85), f"Lese Disc … {line}")
            else:
                progress(0, line[:80])
        rc = self.run(["cdrdao", "read-cd", "--read-raw", "--datafile", str(work / "disc.bin"),
                       "--device", info.device, "--driver", "generic-mmc-raw", str(work / "disc.toc")], on_line)
        if rc != 0 or not (work / "disc.bin").exists():
            raise RipError(f"cdrdao ist fehlgeschlagen (Code {rc}): {last[0]}")
        rc = self.run(["toc2cue", str(work / "disc.toc"), str(work / "disc.cue")], lambda l: None)
        if rc != 0:
            raise RipError("toc2cue ist fehlgeschlagen")
        return work / "disc.bin"

    # -- DVD ---------------------------------------------------------------------
    def _rip_dvd(self, info, work, progress, chunk=4 << 20):
        size = info.media.size
        out = work / "disc.iso"
        done = 0
        with open(info.device, "rb", buffering=0) as src, open(out, "wb") as dst:
            while True:
                data = None
                for attempt in range(3):
                    try:
                        src.seek(done)
                        data = src.read(chunk)
                        break
                    except OSError as e:
                        if attempt == 2:
                            raise RipError(f"Lesefehler bei {done // 1048576} MB ({e.strerror}). "
                                           "Disc reinigen oder mit ddrescue sichern.")
                if not data:
                    break
                dst.write(data)
                done += len(data)
                if size:
                    progress(min(0.85, done / size * 0.85), f"Lese Disc … {done // 1048576} / {size // 1048576} MB")
                else:
                    progress(0, f"Lese Disc … {done // 1048576} MB")
        if done == 0:
            raise RipError("Die Disc lieferte keine Daten.")
        return out

    # -- CHD ---------------------------------------------------------------------
    def _to_chd(self, image, work, dest_dir, name, kind):
        target = dest_dir / f"{name}.chd"
        n = 2
        while target.exists():
            target = dest_dir / f"{name} ({n}).chd"
            n += 1
        if self.which("chdman"):
            src = work / "disc.cue" if kind == "cd" else image
            cmd = ["chdman", "createcd" if kind == "cd" else "createdvd", "-i", str(src), "-o", str(target)]
            if self.run(cmd, lambda l: None) == 0 and target.exists():
                return target
            if kind == "cd":
                raise RipError("chdman konnte keine CHD erzeugen")
        # DVD without (a new enough) chdman: keep the plain ISO, PCSX2 reads it directly
        iso = target.with_suffix(".iso")
        shutil.move(str(image), str(iso))
        return iso
