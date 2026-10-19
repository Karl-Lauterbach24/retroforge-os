"""Core tests (stdlib unittest, no pygame needed):  python -m unittest discover tests"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retroforge import romdetect  # noqa: E402
from retroforge.core import Core  # noqa: E402
from retroforge.hw import tiers  # noqa: E402
from retroforge.hw.probe import GpuInfo, HardwareInfo  # noqa: E402
from retroforge.launcher import ini_patch  # noqa: E402
from retroforge.library import clean_name  # noqa: E402
from retroforge.settings import GAME, SYSTEM  # noqa: E402

PROFILES = {
    "pi4": HardwareInfo(arch="aarch64", family="arm64", cpu_model="Cortex-A72", cores=4, threads=4, max_mhz=1800,
                        cpu_parts=["0x41:0xd08"], ram_mb=4096, board="Raspberry Pi 4 Model B",
                        gpus=[GpuInfo(name="VideoCore VI", vendor="broadcom", driver="v3d", integrated=True)],
                        vulkan="1.2"),
    "pi5": HardwareInfo(arch="aarch64", family="arm64", cpu_model="Cortex-A76", cores=4, threads=4, max_mhz=2400,
                        cpu_parts=["0x41:0xd0b"], ram_mb=8192, board="Raspberry Pi 5 Model B",
                        gpus=[GpuInfo(name="VideoCore VII", vendor="broadcom", driver="v3d", integrated=True)],
                        vulkan="1.3"),
    "core2": HardwareInfo(arch="x86_64", family="x86_64", cpu_model="Intel Core2 Duo E8400", cores=2, threads=2,
                          max_mhz=3000, isa=["sse3", "ssse3", "sse4_1"], ram_mb=4096,
                          gpus=[GpuInfo(name="Intel G45", vendor="intel", driver="i915", device_id="0x2e22",
                                        integrated=True)]),
    "deck": HardwareInfo(arch="x86_64", family="x86_64", cpu_model="AMD Custom APU 0405", cores=4, threads=8,
                         max_mhz=3500, isa=["sse4_1", "sse4_2", "avx", "avx2", "f16c", "bmi1", "bmi2", "fma", "abm",
                                                  "movbe"], ram_mb=16384,
                         gpus=[GpuInfo(name="AMD Radeon", vendor="amd", driver="amdgpu", device_id="0x163f",
                                       vram_mb=1024, integrated=True)], vulkan="1.3"),
    "gamingpc": HardwareInfo(arch="x86_64", family="x86_64", cpu_model="AMD Ryzen 7 7800X3D", cores=8, threads=16,
                             max_mhz=5000, isa=["sse4_1", "sse4_2", "avx", "avx2", "avx512f", "vaes", "f16c",
                                                "bmi1", "bmi2", "fma", "abm", "movbe"], ram_mb=32768,
                             gpus=[GpuInfo(name="NVIDIA GeForce RTX 4070", vendor="nvidia", driver="nvidia",
                                           vram_mb=12288, integrated=False)], vulkan="1.3"),
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rf-test-")
        self.core = Core(self.tmp)
        self.core.boot(do_probe=False, scan=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def use(self, profile):
        self.core.hw = PROFILES[profile]
        self.core.reassess()
        return self.core.assessment


class TestTiers(Base):
    def test_ladder_is_monotonic_with_hardware(self):
        order = self.core.assessment.ladder if self.core.assessment else None
        maxes = {}
        for p in PROFILES:
            a = self.use(p)
            order = a.ladder
            maxes[p] = order.index(a.max_console) if a.max_console else -1
        self.assertLess(maxes["core2"], maxes["pi5"])
        self.assertLessEqual(maxes["pi4"], maxes["pi5"])
        self.assertLess(maxes["pi5"], maxes["deck"])
        self.assertLessEqual(maxes["deck"], maxes["gamingpc"])

    def test_expected_rungs(self):
        a = self.use("pi4")
        self.assertGreaterEqual(a.status("psp"), tiers.EXPERIMENTAL)
        self.assertLess(a.status("ps2"), tiers.PLAYABLE)            # PCSX2 is x86-64 only
        a = self.use("pi5")
        self.assertGreaterEqual(a.status("dreamcast"), tiers.PLAYABLE)
        a = self.use("deck")
        self.assertGreaterEqual(a.status("ps2"), tiers.PLAYABLE)
        self.assertGreaterEqual(a.status("switch"), tiers.PLAYABLE)
        a = self.use("gamingpc")
        self.assertEqual(a.status("ps3"), tiers.FULL)
        self.assertEqual(a.max_console, "switch")                    # PS4/PS5 are experimental only
        self.assertEqual(a.status("ps5"), tiers.EXPERIMENTAL)        # AnyPS5 plugin
        self.assertEqual(a.status("xboxseries"), tiers.UNAVAILABLE)

    def test_arch_and_isa_blockers_are_reported(self):
        a = self.use("core2")
        v = a.verdicts["ps4"]
        self.assertEqual(v.status, tiers.IMPOSSIBLE)
        self.assertTrue(any("AVX" in r for r in v.reasons))
        a = self.use("pi5")
        self.assertTrue(any("Architektur" in r for r in a.verdicts["wiiu"].reasons))

    def test_gpu_override(self):
        self.use("pi4")
        self.core.settings.set("system.gpu_class", 5)
        self.assertEqual(self.core.assessment.cap.gpu, 5)

    def test_gpu_classes(self):
        self.assertEqual(tiers.gpu_class(PROFILES["pi4"]), 2)
        self.assertEqual(tiers.gpu_class(PROFILES["pi5"]), 3)
        self.assertEqual(tiers.gpu_class(PROFILES["deck"]), 4)
        self.assertEqual(tiers.gpu_class(PROFILES["gamingpc"]), 5)


class TestSettings(Base):
    def test_layering(self):
        s = self.core.settings
        self.assertEqual(s.resolve("video.shader", "snes", "snes/x.sfc").source, "default")
        s.set("video.shader", "crt-geom")
        s.set("video.shader", "crt-royale", SYSTEM, "snes")
        s.set("video.shader", "lcd-grid", GAME, "snes/x.sfc")
        self.assertEqual(s.get("video.shader", "snes", "snes/x.sfc"), "lcd-grid")
        self.assertEqual(s.get("video.shader", "snes", "snes/y.sfc"), "crt-royale")
        self.assertEqual(s.get("video.shader", "nes", "nes/z.nes"), "crt-geom")
        s.unset("video.shader", GAME, "snes/x.sfc")
        self.assertEqual(s.resolve("video.shader", "snes", "snes/x.sfc").source, "system")

    def test_persistence(self):
        self.core.settings.set("ui.theme", "gameboy")
        data = json.loads(Path(self.tmp, "system/retroforge/settings.json").read_text("utf-8"))
        self.assertEqual(data["global"]["ui.theme"], "gameboy")

    def test_recommended_filters(self):
        self.use("gamingpc")
        self.core.apply_recommended_filters()
        self.assertEqual(self.core.settings.get("video.shader", "snes"), "crt-royale")
        self.assertEqual(self.core.settings.get("video.shader", "gb"), "dmg")
        self.assertEqual(self.core.settings.get("video.internal_res", "gamecube"), 4)


class TestLibraryAndLauncher(Base):
    def add(self, system, name, data=b"\0" * 64):
        p = Path(self.tmp, "roms", system, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_scan_m3u_and_names(self):
        self.add("psx", "Game (Europe) (Disc 1).chd")
        self.add("psx", "Game (Europe) (Disc 2).chd")
        Path(self.tmp, "roms/psx/Game (Europe).m3u").write_text(
            "Game (Europe) (Disc 1).chd\nGame (Europe) (Disc 2).chd\n")
        self.add("snes", "Legend of Zelda, The - A Link to the Past (USA).sfc")
        self.core.library.scan()
        psx = self.core.library.games["psx"]
        self.assertEqual([g.name for g in psx], ["Game"])
        snes = self.core.library.games["snes"][0]
        self.assertEqual(snes.name, "The Legend of Zelda - A Link to the Past")
        self.assertEqual(snes.region, "US")

    def test_libretro_plan(self):
        self.use("deck")
        self.add("n64", "Test (USA).z64")
        self.core.library.scan()
        g = self.core.library.games["n64"][0]
        s = self.core.settings
        s.set("video.shader", "crt-lottes", SYSTEM, "n64")
        s.set("video.internal_res", 3, GAME, g.key)
        s.set("game.runahead", 2)
        plan = self.core.launcher.plan(g)
        self.assertEqual(plan.emulator.id, "mupen64plus_next")
        self.assertEqual(plan.core_options["mupen64plus-43screensize"], "960x720")
        self.assertTrue(plan.ra_config["run_ahead_enabled"])
        self.assertEqual(plan.ra_config["run_ahead_frames"], 2)
        self.assertEqual(plan.ra_config["video_driver"], "vulkan")
        argv = self.core.launcher.materialize(plan)
        self.assertIn("-L", argv)
        append = Path(argv[argv.index("--appendconfig") + 1]).read_text()
        self.assertIn('core_options_path = "', append)
        # shader file missing in the test env -> noted, not fatal
        self.assertTrue(any("crt-lottes" in n or "Shader" in n for n in plan.notes))

    def test_standalone_gamescope_plan(self):
        self.use("gamingpc")
        self.add("gamecube", "Test (USA).rvz")
        self.core.library.scan()
        g = self.core.library.games["gamecube"][0]
        s = self.core.settings
        s.set("video.internal_res", 4, SYSTEM, "gamecube")
        s.set("video.upscaler", "fsr", SYSTEM, "gamecube")
        with mock.patch("retroforge.launcher.platform.system", return_value="Linux"), \
                mock.patch("retroforge.launcher.shutil.which", return_value="/usr/bin/gamescope"):
            plan = self.core.launcher.plan(g)
        self.assertEqual(plan.emulator.id, "dolphin")
        full = plan.full_cmd()
        self.assertEqual(full[0], "gamescope")
        self.assertIn("fsr", full)
        self.assertIn("GFX.Settings.InternalResolution=4", full)
        self.assertEqual(full[-1], g.path)

    def test_standalone_falls_back_to_cage(self):
        """Debian 13 has no gamescope: standalone emulators still get a Wayland session via cage."""
        self.use("gamingpc")
        self.add("gamecube", "Test (USA).rvz")
        self.core.library.scan()
        g = self.core.library.games["gamecube"][0]
        which = lambda tool: "/usr/bin/cage" if tool == "cage" else None
        with mock.patch("retroforge.launcher.platform.system", return_value="Linux"), \
                mock.patch("retroforge.launcher.shutil.which", side_effect=which):
            plan = self.core.launcher.plan(g)
        self.assertEqual(plan.full_cmd()[:3], ["cage", "-s", "--"])
        self.assertTrue(plan.windowed)
        self.assertIn("wayland", plan.env["QT_QPA_PLATFORM"])

    def test_emulator_override_per_game(self):
        self.use("gamingpc")
        self.add("psx", "Test (USA).chd")
        self.core.library.scan()
        g = self.core.library.games["psx"][0]
        self.core.settings.set("emulator", "beetle_psx_hw", GAME, g.key)
        self.assertEqual(self.core.launcher.plan(g).emulator.id, "beetle_psx_hw")


class TestPlugins(unittest.TestCase):
    def test_user_plugin_can_add_system_and_filter_launch(self):
        tmp = tempfile.mkdtemp(prefix="rf-plug-")
        try:
            pdir = Path(tmp, "plugins", "ps5-test")
            pdir.mkdir(parents=True)
            (pdir / "plugin.json").write_text(json.dumps({"id": "ps5-test", "name": "T", "api": 1}))
            (pdir / "main.py").write_text(
                "from retroforge.model import Req\n"
                "def register(api):\n"
                "    api.add_emulator(id='fakeps5', name='FakePS5', kind='standalone', binary='fakeps5',\n"
                "                     min=Req(), rec=Req())\n"
                "    api.add_emulator_to_system('ps5', 'fakeps5')\n"
                "    api.on('game.before_launch', lambda plan, core: plan.env.update(X='1') or plan)\n")
            bad = Path(tmp, "plugins", "broken")
            bad.mkdir()
            (bad / "plugin.json").write_text(json.dumps({"id": "broken", "name": "B", "api": 1}))
            (bad / "main.py").write_text("def register(api):\n    raise ValueError('boom')\n")
            core = Core(tmp).boot(do_probe=False, scan=False)
            core.hw = PROFILES["gamingpc"]
            core.reassess()
            self.assertEqual(core.plugins.plugins["ps5-test"].status, "loaded")
            self.assertEqual(core.plugins.plugins["broken"].status, "error")
            self.assertGreaterEqual(core.assessment.status("ps5"), tiers.PLAYABLE)
            self.assertEqual(core.assessment.max_console, "ps5")
            Path(tmp, "roms", "ps5").mkdir(parents=True)
            Path(tmp, "roms", "ps5", "a.ps5").write_bytes(b"x")
            core.library.scan()
            plan = core.launcher.plan(core.library.games["ps5"][0])
            self.assertEqual(plan.env.get("X"), "1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_shipped_plugins_load(self):
        tmp = tempfile.mkdtemp(prefix="rf-plug-")
        try:
            core = Core(tmp).boot(do_probe=False, scan=False)
            for pid in ("stats", "save-backup", "web-upload", "screensaver", "retroachievements", "seasonal",
                        "anyps5"):
                self.assertEqual(core.plugins.plugins[pid].status, "loaded", core.plugins.plugins[pid].error)
            self.assertTrue(core.registry.has("theme", "halloween"))
            self.assertTrue(core.registry.has("setting", "backup.keep"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


FAKE_RELINKER = r"""
import sys, pathlib
args = sys.argv[1:]
smp = pathlib.Path(args[args.index("--sce-module-path") + 1])
inp, out = pathlib.Path(args[-2]), pathlib.Path(args[-1])
assert inp.name == "eboot.bin" and smp.name == "input", "modules must come from .anyps5/input, not app0/"
out.write_text("native " + ("intel" if "--to-intel" in args else "amd"))
for m in (smp / "sce_module").glob("*.prx"):
    dest = out.parent / "app0" / "sce_module" / m.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("converted")
with open(pathlib.Path(__file__).with_suffix(".count"), "a") as f:
    f.write("x")
"""


class TestAnyPS5(Base):
    def port(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "anyps5_port_test", Path(__file__).resolve().parent.parent / "plugins" / "anyps5" / "port.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def make_game(self):
        game = Path(self.tmp, "roms", "ps5", "Animal Well.ps5")
        (game / "app0" / "sce_module").mkdir(parents=True)
        (game / "app0" / "sce_sys").mkdir()
        (game / "app0" / "eboot.bin").write_bytes(b"\x7fELF" + b"\0" * 60)
        (game / "app0" / "sce_module" / "libgame.prx").write_text("original")
        return game

    def test_ladder(self):
        a = self.use("gamingpc")
        v = a.verdicts["ps5"]
        self.assertEqual((v.status, v.emulator), (tiers.EXPERIMENTAL, "anyps5"))
        self.assertTrue(any("AnyPS5" in r for r in v.reasons))
        self.assertTrue(any("Architektur" in r for r in self.use("pi5").verdicts["ps5"].reasons))
        reasons = " ".join(self.use("core2").verdicts["ps5"].reasons)
        self.assertIn("AVX2", reasons)
        self.assertIn("MOVBE", reasons)

    def test_launch_plan(self):
        self.use("gamingpc")
        game = self.make_game()
        self.core.library.scan()
        g = self.core.library.games["ps5"][0]
        self.assertTrue(g.is_dir)
        plan = self.core.launcher.plan(g)
        self.assertEqual(plan.emulator.id, "anyps5")
        self.assertTrue(plan.cmd[1].endswith("port.py"))
        self.assertEqual(plan.cmd[plan.cmd.index("--game") + 1], str(game))
        self.assertNotIn("--to-intel", plan.cmd)                 # Ryzen: no rewrite
        self.assertTrue(any("Erster Start" in n for n in plan.notes))
        self.core.hw = HardwareInfo(**{**PROFILES["gamingpc"].__dict__, "cpu_model": "Intel Core i7-14700K"})
        self.assertIn("--to-intel", self.core.launcher.plan(g).cmd)

    def test_convert_once_and_restore(self):
        port = self.port()
        game = self.make_game()
        libs = Path(self.tmp, "libs")
        libs.mkdir()
        fake = Path(self.tmp, "fake_relinker.py")
        fake.write_text(FAKE_RELINKER)
        cmd = [sys.executable, str(fake)]
        exe = port.prepare(cmd, libs, game, to_intel=True, log=lambda *a: None)
        self.assertEqual(exe.read_text(), "native intel")
        self.assertEqual((game / "app0/sce_module/libgame.prx").read_text(), "converted")
        self.assertEqual((game / ".anyps5/input/sce_module/libgame.prx").read_text(), "original")
        port.prepare(cmd, libs, game, to_intel=True, log=lambda *a: None)
        self.assertEqual(fake.with_suffix(".count").read_text(), "x")   # cached, not converted again
        port.prepare(cmd, libs, game, to_intel=False, log=lambda *a: None)
        self.assertEqual(fake.with_suffix(".count").read_text(), "xx")  # flag changed -> reconverted
        port.restore(game, log=lambda *a: None)
        self.assertEqual((game / "app0/sce_module/libgame.prx").read_text(), "original")
        self.assertFalse((game / "app.elf").exists() or (game / ".anyps5").exists())

    def test_rejects_encrypted_dump(self):
        port = self.port()
        game = self.make_game()
        (game / "app0" / "eboot.bin").write_bytes(b"\x54\x14\xf5\xee" + b"\0" * 60)
        with self.assertRaises(port.PortError):
            port.prepare([sys.executable, "x"], self.tmp, game, log=lambda *a: None)


class TestRomDetect(Base):
    def detect(self, name, data):
        p = Path(self.tmp, name)
        p.write_bytes(data)
        return romdetect.detect(p, self.core.registry)

    def test_headers(self):
        self.assertEqual(self.detect("a.bin", b"NES\x1a" + b"\0" * 100), "nes")
        self.assertEqual(self.detect("b.bin", b"\x80\x37\x12\x40" + b"\0" * 100), "n64")
        gb = bytearray(0x200)
        gb[0x104:0x10C] = bytes.fromhex("CEED6666CC0D000B")
        self.assertEqual(self.detect("c.bin", bytes(gb)), "gb")
        gb[0x143] = 0x80
        self.assertEqual(self.detect("d.bin", bytes(gb)), "gbc")
        md = bytearray(0x200)
        md[0x100:0x104] = b"SEGA"
        self.assertEqual(self.detect("e.bin", bytes(md)), "megadrive")
        iso = bytearray(0x9000)
        iso[0x8001:0x8006] = b"CD001"
        iso[0x8008:0x8013] = b"PLAYSTATION"
        self.assertEqual(self.detect("f.iso", bytes(iso)), "psx")
        self.assertEqual(self.detect("g.gba", b"\0" * 10), "gba")   # extension fallback

    def test_ini_patch(self):
        p = Path(self.tmp, "x.ini")
        p.write_text("; comment\n[EmuCore/GS]\nfoo = 1\nupscale_multiplier = 1\n[Other]\na = b\n")
        ini_patch(str(p), "EmuCore/GS", "upscale_multiplier", 3)
        ini_patch(str(p), "New", "k", "v")
        text = p.read_text()
        self.assertIn("upscale_multiplier = 3", text)
        self.assertIn("; comment", text)
        self.assertIn("[New]\nk = v", text)
        self.assertEqual(text.count("upscale_multiplier"), 1)


if __name__ == "__main__":
    unittest.main()
