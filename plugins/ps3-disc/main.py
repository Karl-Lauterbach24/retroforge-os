"""PS3-Disc-Sicherung (opt-in, auf eigene Gefahr).

PS3 discs are protected by an effective copy protection. This plugin does not
contain any decryption code and does not download anything: it starts the
external, user-installed ps3-disc-dumper (https://github.com/13xforever/ps3-disc-dumper)
with the disc mounted, and afterwards moves the finished game folder to
roms/ps3/<Name>.ps3/. It is disabled by default; enabling it and every use
require confirming the warning below.
"""
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

from retroforge.library import Game
from retroforge.model import Emulator, Req

EMU_ID = "ps3-disc-dumper"
WARNING = ("Dieses Plugin umgeht den wirksamen Kopierschutz von PS3-Discs über das externe Programm "
           "ps3-disc-dumper und öffentliche Disc-Schlüssel. Das ist in vielen Ländern verboten, in Deutschland "
           "nach § 95a UrhG auch für Privatkopien eigener Discs. Die Nutzung erfolgt ausschließlich auf eigene "
           "Gefahr; RetroForge übernimmt keine Haftung.")
BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def register(api):
    core = api.core
    home = core.paths.emulators / EMU_ID
    state = {"before": set(), "mounted": None}
    hint = (f"ps3-disc-dumper selbst von github.com/13xforever/ps3-disc-dumper herunterladen und nach {home} "
            "entpacken. RetroForge lädt Werkzeuge zur Kopierschutzumgehung bewusst nicht automatisch herunter.")

    def exe():
        for name in ("ps3-disc-dumper", "ps3-disc-dumper.exe"):
            if (home / name).is_file():
                return home / name
        found = shutil.which("ps3-disc-dumper")
        return Path(found) if found else None

    api.add_emulator(Emulator(
        id=EMU_ID, name="ps3-disc-dumper (extern)", kind="standalone", binary="ps3-disc-dumper", args=(),
        min=Req(archs=("x86_64", "arm64")), rec=Req(), features=(),
        source={"type": "manual", "hint": hint},
        note="Externes Werkzeug, umgeht den PS3-Kopierschutz – Nutzung auf eigene Gefahr"))

    # -- disc dialog: offered by the disc plugin for problem "ps3" ---------------
    def start(app, info):
        if exe() is None:
            app.info("ps3-disc-dumper fehlt", [hint])
            return
        game = Game(key=f"tool/{EMU_ID}", system="ps3", path=info.device, name=f"PS3-Disc sichern: {info.title}")
        app.launch(game, EMU_ID)

    api.registry.add("disc_handler", "ps3", {
        "title": "PS3-Disc – Sicherung auf eigene Gefahr",
        "label": "Mit ps3-disc-dumper sichern (auf eigene Gefahr)",
        "warning": WARNING + " Nur fortfahren, wenn du das Risiko selbst trägst.",
        "action": start,
    }, origin=api.id)

    # -- launch / exit ------------------------------------------------------------
    def mount(dev):
        if platform.system() != "Linux" or not shutil.which("udisksctl"):
            return None
        r = subprocess.run(["udisksctl", "mount", "-b", dev, "--no-user-interaction"],
                           capture_output=True, text=True, errors="replace", timeout=60)
        return dev if r.returncode == 0 or "AlreadyMounted" in r.stderr else None

    def unmount(dev):
        if dev and shutil.which("udisksctl"):
            subprocess.run(["udisksctl", "unmount", "-b", dev, "--no-user-interaction"],
                           capture_output=True, timeout=60)

    def output_dirs():
        """Where the dumper writes: its own folder by default, or the folder set in its settings."""
        dirs = [home]
        for cfg in (Path.home() / ".config" / "ps3-disc-dumper").glob("*.json"):
            try:
                out = json.loads(cfg.read_text(encoding="utf-8")).get("OutputDir")
                if out:
                    dirs.append(Path(out))
            except (OSError, ValueError, AttributeError):
                pass
        return [d for d in dirs if d.is_dir()]

    def games_in(dirs):
        return {p for d in dirs for p in d.iterdir() if p.is_dir() and (p / "PS3_GAME").is_dir()}

    def before_launch(plan, core, **_):
        if plan.emulator.id != EMU_ID:
            return plan
        path = exe()
        plan.cmd = [str(path or "ps3-disc-dumper")]
        plan.cwd = str(path.parent) if path else None
        state["before"] = games_in(output_dirs())
        state["mounted"] = mount(plan.game.path)
        if state["mounted"] is None and platform.system() == "Linux":
            plan.notes.append("Disc konnte nicht automatisch eingehängt werden – im Dumper ggf. manuell wählen.")
        plan.notes.append("Bedienung per Maus/Tastatur. Das fertige Spiel wird danach nach roms/ps3 verschoben.")
        return plan

    def after_exit(plan, core, **_):
        if plan.emulator.id != EMU_ID:
            return
        unmount(state.pop("mounted", None))
        moved = []
        for folder in sorted(games_in(output_dirs()) - state.get("before", set())):
            name = BAD_CHARS.sub("", folder.name).strip(" .") or "PS3-Spiel"
            target = core.paths.system_roms("ps3") / f"{name}.ps3"
            n = 2
            while target.exists():
                target = core.paths.system_roms("ps3") / f"{name} ({n}).ps3"
                n += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(target))
            moved.append(name)
        if moved:
            core.library.scan_async()
            api.notify("PS3-Spiel gesichert: " + ", ".join(moved), "good")
        else:
            api.notify("ps3-disc-dumper beendet – kein neues Spiel gefunden", "warn")

    api.on("game.before_launch", before_launch)
    api.on("game.after_exit", after_exit)
