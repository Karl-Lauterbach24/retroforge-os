"""AnyPS5 for RetroForge: experimental PS5 support without emulation.

AnyPS5 (https://github.com/boykopovar/AnyPS5, GPL-2.0) relinks decrypted PS5
executables into native Linux programs and reimplements the PS5 system
libraries; the PS5's Zen 2 code then runs directly on the host CPU and its
shaders are recompiled to SPIR-V for Vulkan. As of October 2026 only a few
titles are playable, so the emulator is flagged experimental and never moves
the "highest console" of the hardware ladder.
"""
import importlib.util
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

from retroforge.model import Emulator, Req
from retroforge.settings import GAME, SYSTEM, SettingDef

REPO = "boykopovar/AnyPS5"
# Zen 2 extensions that converted code uses without checking (AnyPS5 USAGE.md);
# names as in /proc/cpuinfo ("abm" is LZCNT).
PS5_ISA = ("avx2", "fma", "f16c", "bmi1", "bmi2", "abm", "movbe")


def register(api):
    core = api.core
    plugin_dir = Path(__file__).resolve().parent
    # plugin-local helper (also run as the game process), loaded under a unique module name
    spec = importlib.util.spec_from_file_location("retroforge_anyps5_port", plugin_dir / "port.py")
    port = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(port)

    def home():
        return core.paths.emulators / "anyps5"

    def can_install(core):
        return core.hw.family == "x86_64" and platform.system() == "Linux"

    def install(manager, emu, progress=None):
        target = home()
        target.mkdir(parents=True, exist_ok=True)
        relinker = manager.latest_asset(REPO, r"^relinker-v[\d.]+$")
        libs = manager.latest_asset(REPO, r"^prx-linux-v[\d.]+\.tar\.gz$")
        total = relinker["size"] + libs["size"]

        def part(offset):
            return (lambda done, _t: progress(offset + done, total)) if progress else None

        exe = target / "relinker"
        manager.download(relinker["browser_download_url"], exe, part(0))
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        with tempfile.TemporaryDirectory(dir=str(target)) as tmp:
            archive = Path(tmp) / "prx.tar.gz"
            manager.download(libs["browser_download_url"], archive, part(relinker["size"]))
            unpacked = Path(tmp) / "x"
            with tarfile.open(archive) as t:
                try:
                    t.extractall(unpacked, filter="data")
                except TypeError:   # Python < 3.11.4
                    t.extractall(unpacked, members=[m for m in t.getmembers()
                                                    if not (m.name.startswith("/") or ".." in Path(m.name).parts
                                                            or m.issym() or m.islnk())])
            # the archive's folder layout may change between releases: take the folder holding the .prx files
            dirs = {}
            for p in unpacked.rglob("*.prx"):
                dirs[p.parent] = dirs.get(p.parent, 0) + 1
            if not dirs:
                raise RuntimeError("prx-linux-Archiv enthält keine .prx-Bibliotheken")
            src = max(dirs, key=dirs.get)
            dest = target / "libs"
            shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(src), str(dest))
        (target / "VERSION").write_text(relinker.get("release_tag", ""), encoding="utf-8")
        return str(exe)

    api.add_emulator(Emulator(
        id="anyps5", name="AnyPS5 (Relinker)", kind="standalone", binary="relinker", args=("{rom}",),
        min=Req(archs=("x86_64",), isa=PS5_ISA, cpu=4.0, threads=8, gpu=4, ram=16, vulkan="1.3"),
        rec=Req(cpu=5.5, threads=12, gpu=5, ram=32),
        features=(), experimental=True,
        note="AnyPS5: keine Emulation, nur wenige Spiele laufen bisher (z. B. Animal Well, Hollow Knight: "
             "Silksong) – Stand Oktober 2026",
        source={"type": "custom", "install": install, "can_install": can_install,
                "hint": "AnyPS5 gibt es nur für x86-64-Linux (RetroForge OS). Die Spiele laufen nativ, "
                        "deshalb ist eine CPU mit AVX2/BMI2/MOVBE nötig."}))
    api.add_emulator_to_system("ps5", "anyps5")

    api.add_setting(SettingDef(
        "anyps5.intel", "AMD-Befehle für Intel umschreiben", "auto", "Emulator",
        choices=[("auto", "Automatisch (nach CPU)"), (True, "Immer"), (False, "Nie")],
        scopes=(SYSTEM, GAME), order=20, visible=lambda core, system, game: system == "ps5",
        help="PS5-Code enthält AMD-spezifische Befehle; auf Intel-CPUs schreibt der Relinker sie um. "
             "Zur Laufzeit erzeugter AMD-Code lässt sich nicht umschreiben."))

    def to_intel(game):
        mode = api.setting("anyps5.intel", game.system, game.key, default="auto")
        if mode == "auto":
            return "intel" in core.hw.cpu_model.lower()
        return bool(mode)

    def before_launch(plan, core, **_):
        if plan.emulator.id != "anyps5":
            return plan
        game = plan.game
        relinker = home() / "relinker"
        plan.cmd = [sys.executable, str(plugin_dir / "port.py"), "--relinker", str(relinker),
                    "--libs", str(home() / "libs"), "--game", game.path] + (["--to-intel"] if to_intel(game) else [])
        plan.cwd = game.path
        if not Path(game.path, "app0", "eboot.bin").is_file():
            plan.notes.append("Erwartet: <Spiel>.ps5/app0/eboot.bin (entschlüsselter Dump)")
        elif not port.is_converted(game.path):
            plan.notes.append("Erster Start: das Spiel wird jetzt für Linux konvertiert – das dauert etwas.")
        if not plan.gamescope:
            plan.notes.append("AnyPS5 braucht X11/Wayland – bitte 'Standalone in gamescope starten' anlassen.")
        return plan

    api.on("game.before_launch", before_launch)

    def details(game, core, **_):
        if game.system != "ps5":
            return None
        state = "konvertiert" if port.is_converted(game.path) else "wird beim ersten Start konvertiert"
        return [("PS5-Port", state)]

    api.on("ui.game_details", details)

    def game_menu(game, core, **_):
        if game.system != "ps5" or not Path(game.path, ".anyps5").exists():
            return None

        def rebuild(app):
            manifest = Path(game.path, ".anyps5", "manifest.json")
            if manifest.exists():
                manifest.unlink()
            app.toast("Wird beim nächsten Start neu konvertiert")

        def restore(app):
            app.confirm("Original wiederherstellen?",
                        "Entfernt den Linux-Port und legt die Original-Module zurück nach app0/.",
                        lambda: (port.restore(game.path), app.toast("Original wiederhergestellt", "good")))
        return [("AnyPS5: neu konvertieren", rebuild), ("AnyPS5: Original wiederherstellen", restore)]

    api.on("ui.game_menu", game_menu)
