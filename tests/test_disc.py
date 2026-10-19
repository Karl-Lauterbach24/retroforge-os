"""Disc plugin tests with tiny fake disc images (no drive needed)."""
import hashlib
import importlib.util
import io
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retroforge import romdetect  # noqa: E402
from retroforge.core import Core  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "disc"
S = 2048


def load(name):
    spec = importlib.util.spec_from_file_location(f"test_disc_{name}", PLUGIN / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


drive, rip = load("drive"), load("rip")


def both32(v):
    return struct.pack("<I", v) + struct.pack(">I", v)


def dir_record(name, lba, size, is_dir=False):
    rec = bytes([0, 0]) + both32(lba) + both32(size) + bytes(7) + bytes([2 if is_dir else 0, 0, 0]) \
        + struct.pack("<H", 1) + struct.pack(">H", 1) + bytes([len(name)]) + name
    if len(rec) % 2:
        rec += b"\0"
    return bytes([len(rec)]) + rec[1:]


def make_iso(files, system_id="", volume_id="TESTDISC", head=b""):
    """Minimal ISO 9660 image: PVD at sector 16, root dir at 18, files from 19 on."""
    sectors = {}
    lba, records = 19, [dir_record(b"\0", 18, S, True), dir_record(b"\1", 18, S, True)]
    for name, data in files.items():
        records.append(dir_record(name.encode() + b";1", lba, len(data)))
        sectors[lba] = data
        lba += max(1, -(-len(data) // S))
    pvd = bytearray(S)
    pvd[0:6] = b"\x01CD001"
    pvd[8:40] = system_id.ljust(32).encode()
    pvd[40:72] = volume_id.ljust(32).encode()
    pvd[156:190] = dir_record(b"\0", 18, S, True)
    img = bytearray(S * lba)
    img[0:len(head)] = head
    img[16 * S:17 * S] = pvd
    root = b"".join(records)
    img[18 * S:18 * S + len(root)] = root
    for at, data in sectors.items():
        img[at * S:at * S + len(data)] = data
    return bytes(img)


class Unreadable(io.BytesIO):
    def read(self, *a):
        raise OSError(5, "I/O error")


def ident(data, **media):
    return drive.identify_stream(io.BytesIO(data), drive.Media(present=True, **media))


class TestIdentify(unittest.TestCase):
    def test_playstation(self):
        ps1 = make_iso({"SYSTEM.CNF": b"BOOT = cdrom:\\SLUS_012.34;1\r\nTCB = 4\r\n"}, "PLAYSTATION")
        info = ident(ps1, kind="cd", data_tracks=1)
        self.assertEqual((info.system, info.serial), ("psx", "SLUS-01234"))
        self.assertEqual(info.actions(), {"play": True, "rip": True})
        ps2 = make_iso({"SYSTEM.CNF": b"BOOT2 = cdrom0:\\SLES_123.45;1\r\nVER = 1.00\r\n"}, "PLAYSTATION")
        info = ident(ps2, kind="dvd", data_tracks=1)
        self.assertEqual((info.system, info.serial), ("ps2", "SLES-12345"))

    def test_sega_and_3do_headers(self):
        sat = bytearray(make_iso({}, head=b"SEGA SEGASATURN SEGA TP T-999   V1.000"))
        self.assertEqual(ident(bytes(sat), kind="cd", data_tracks=1).system, "saturn")
        self.assertEqual(ident(b"SEGADISCSYSTEM  " + bytes(S * 4), kind="cd", data_tracks=1).system, "segacd")
        self.assertEqual(ident(b"\x01" + b"\x5a" * 5 + bytes(S * 4), kind="cd", data_tracks=1).system, "3do")

    def test_pc_engine_data_track_after_audio(self):
        img = bytearray(S * 20)
        img[11 * S + 32:11 * S + 55] = b"PC Engine CD-ROM SYSTEM"
        info = ident(bytes(img), kind="cd", audio_tracks=20, data_tracks=1, first_data_lba=10)
        self.assertEqual(info.system, "pcenginecd")

    def test_mixed_mode_unreadable_asks_for_system(self):
        info = drive.identify_stream(Unreadable(b""), drive.Media(present=True, kind="cd",
                                                                   audio_tracks=12, data_tracks=1))
        self.assertIn("pcenginecd", info.candidates)
        self.assertIsNone(info.system)

    def test_unsupported_formats_are_explained(self):
        ps3 = make_iso({"PS3_DISC.SFB": b".SFB"}, volume_id="PS3VOLUME")
        self.assertEqual(ident(ps3, kind="bd", data_tracks=1).problem, "ps3")
        self.assertEqual(ident(bytes(S * 40), kind="bd", data_tracks=1).problem, "bd")       # PS4/PS5 UDF
        self.assertEqual(drive.identify_stream(Unreadable(b""), drive.Media(present=True, kind="dvd",
                                                                            data_tracks=1)).problem, "unreadable")
        self.assertEqual(ident(b"", kind="cd", audio_tracks=14).problem, "audio")
        for key in ("ps3", "bd", "unreadable", "audio", "unknown"):
            self.assertTrue(drive.UNSUPPORTED[key])

    def test_pc_cdrom_is_saved_for_dosbox(self):
        info = ident(make_iso({"SETUP.EXE": b"MZ"}, volume_id="DOOM2"), kind="cd", data_tracks=1)
        self.assertEqual(info.system, "dos")
        self.assertEqual(info.actions(), {"play": False, "rip": True})
        self.assertEqual(info.title, "Doom2")

    def test_retroarch_path(self):
        self.assertEqual(drive.retroarch_path("/dev/sr0"), "cdrom://drive1.cue")
        self.assertEqual(drive.retroarch_path("/dev/sr1"), "cdrom://drive2.cue")


class TestRomImportUsesSystemCnf(unittest.TestCase):
    def test_ps2_iso_import(self):
        tmp = tempfile.mkdtemp()
        try:
            core = Core(tmp).boot(do_probe=False, scan=False)
            p = Path(tmp, "game.iso")
            p.write_bytes(make_iso({"SYSTEM.CNF": b"BOOT2 = cdrom0:\\SLUS_200.01;1\n"}, "PLAYSTATION"))
            self.assertEqual(romdetect.detect(p, core.registry), "ps2")
            p.write_bytes(make_iso({"SYSTEM.CNF": b"BOOT = cdrom:\\SCES_000.01;1\n"}, "PLAYSTATION"))
            self.assertEqual(romdetect.detect(p, core.registry), "psx")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class FakeTools:
    """Pretends to be cdrdao / toc2cue / chdman by creating their output files."""

    def __init__(self):
        self.calls = []

    def which(self, tool):
        return f"/usr/bin/{tool}"

    def run(self, cmd, on_line):
        self.calls.append(cmd[0])
        if cmd[0] == "cdrdao":
            Path(cmd[cmd.index("--datafile") + 1]).write_bytes(b"\0" * 2352 * 10)
            Path(cmd[-1]).write_text("CD_ROM\n")
            for line in ("Copying data track 1 (MODE2_RAW): start 00:00:00, length 40:00:00",
                         "20:00:00", "40:00:00"):
                on_line(line)
        elif cmd[0] == "toc2cue":
            Path(cmd[2]).write_text('FILE "disc.bin" BINARY\n')
        elif cmd[0] == "chdman":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"MComprHD")
        return 0


class TestRip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dvd_to_chd_with_dat_name(self):
        image = make_iso({"SYSTEM.CNF": b"BOOT2 = cdrom0:\\SLUS_200.01;1\n"}, "PLAYSTATION", "SLUS_20001")
        dev = self.tmp / "sr0"
        dev.write_bytes(image)
        dats = self.tmp / "dats"
        dats.mkdir()
        sha1 = hashlib.sha1(image).hexdigest()
        (dats / "ps2.dat").write_text(
            f'<?xml version="1.0"?><datafile><game name="Testspiel (USA)"><rom name="Testspiel (USA).iso" '
            f'size="{len(image)}" sha1="{sha1}"/></game></datafile>', encoding="utf-8")
        info = drive.DiscInfo(system="ps2", label="SLUS_20001", device=str(dev),
                              media=drive.Media(present=True, kind="dvd", size=len(image)))
        tools, seen = FakeTools(), []
        res = rip.Ripper(tools.run, tools.which).rip(info, "dvd", self.tmp / "roms", lambda f, m="": seen.append(f),
                                                     dats)
        self.assertEqual(res["path"].name, "Testspiel (USA).chd")
        self.assertTrue(res["verified"])
        self.assertTrue(res["path"].exists())
        self.assertEqual(list((self.tmp / "roms").glob(".rip-*")), [])          # temp files removed
        self.assertTrue(any(f > 0.5 for f in seen))

    def test_cd_pipeline(self):
        info = drive.DiscInfo(system="psx", label="FINAL_FANTASY_VII", serial="SCES-00867", device="/dev/sr0",
                              media=drive.Media(present=True, kind="cd"))
        tools = FakeTools()
        res = rip.Ripper(tools.run, tools.which).rip(info, "cd", self.tmp / "psx")
        self.assertEqual(tools.calls, ["cdrdao", "toc2cue", "chdman"])
        self.assertEqual(res["path"].name, "Final Fantasy Vii [SCES-00867].chd")
        self.assertIsNone(res["verified"])

    def test_missing_tools(self):
        info = drive.DiscInfo(system="psx", device="/dev/sr0", media=drive.Media(present=True, kind="cd"))
        with self.assertRaises(rip.RipError):
            rip.Ripper(lambda c, l: 0, lambda t: None).rip(info, "cd", self.tmp)


class TestPluginPlay(unittest.TestCase):
    def test_play_builds_launch_from_drive(self):
        tmp = tempfile.mkdtemp()
        try:
            core = Core(tmp).boot(do_probe=False, scan=False)
            self.assertEqual(core.plugins.plugins["disc"].status, "loaded")
            disc = core.registry.service("disc")
            launched = []

            class App:
                def launch(self, game, emulator_id=None):
                    launched.append((game, emulator_id))

            Info = disc["drive"].DiscInfo
            Media = disc["drive"].Media
            disc["play"](App(), Info(system="psx", label="TEST", device="/dev/sr0", media=Media(True, "cd")))
            disc["play"](App(), Info(system="segacd", label="SONIC CD", device="/dev/sr0", media=Media(True, "cd")))
            (g1, e1), (g2, e2) = launched
            self.assertEqual((e1, g1.path), ("duckstation", "/dev/sr0"))
            self.assertEqual((e2, g2.path), ("genesis_plus_gx", "cdrom://drive1.cue"))
            plan = core.launcher.plan(g2, e2)
            self.assertEqual(plan.cmd[-1], "cdrom://drive1.cue")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
