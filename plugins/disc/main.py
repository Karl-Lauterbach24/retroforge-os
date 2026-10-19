"""Disc support: insert a CD/DVD → play it straight from the drive or save it as CHD.

A background thread polls the optical drives (cheap sysfs/udev reads); a
detected disc is handed to the UI thread through the ``ui.idle`` hook, which
then shows the dialog. Copy-protected formats (PS3/PS4/PS5, Xbox, GameCube …)
are explained, never worked around.
"""
import dataclasses
import importlib.util
import queue
import threading
import time
from pathlib import Path

from retroforge.library import Game
from retroforge.settings import GLOBAL, SettingDef

BUSY_SCREENS = ("BootScreen", "LaunchScreen", "RunningScreen", "ProgressDialog", "MenuDialog",
                "ConfirmDialog", "InfoDialog", "Saver")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def register(api):
    core = api.core
    here = Path(__file__).resolve().parent
    drive = _load("retroforge_disc_drive", here / "drive.py")
    rip = _load("retroforge_disc_rip", here / "rip.py")
    events = queue.Queue()
    sigs = {}

    api.add_setting(SettingDef("disc.autodetect", "Discs beim Einlegen erkennen", True, "System", "bool",
                               scopes=(GLOBAL,), order=70,
                               help="CD/DVD einlegen → direkt spielen oder als CHD sichern."))

    # -- background detection ---------------------------------------------------
    def poll():
        while True:
            if api.setting("disc.autodetect", default=True):
                for dev in drive.drives():
                    try:
                        sig = drive.signature(dev)
                    except Exception:
                        continue
                    if sig != sigs.get(dev):
                        sigs[dev] = sig
                        if sig[0]:                      # a disc is (now) in the drive
                            events.put(drive.identify(dev))
            time.sleep(2)

    def on_boot(core, **_):
        if drive.drives():
            threading.Thread(target=poll, daemon=True, name="disc-poll").start()

    api.on("boot", on_boot)

    def on_idle(app, **_):
        if events.empty() or type(app.top).__name__ in BUSY_SCREENS:
            return                                      # never interrupt a game, a dialog or the boot
        show(app, events.get_nowait())

    api.on("ui.idle", on_idle)

    # -- dialogs ----------------------------------------------------------------
    def show(app, info):
        reg = core.registry
        if info.problem:
            title, lines = drive.UNSUPPORTED[info.problem]
            handler = reg.get("disc_handler", info.problem)
            if handler:   # a plugin offers a way (e.g. PS3 discs) – always behind its own warning
                app.sfx("select")
                app.menu(handler["title"], [(handler["label"], lambda a: handler["action"](a, info)),
                                            ("Abbrechen", None)],
                         subtitle=(f"Disc: {info.title}\n" if info.label else "") + handler["warning"], warn=True)
                return
            app.sfx("error")
            app.info(title, ([f"Disc: {info.title}", ""] if info.label else []) + list(lines))
            return
        if info.candidates:
            app.menu("Welches System ist diese Disc?",
                     [(reg.get("system", s).name, lambda a, s=s: show(a, dataclasses.replace(info, system=s,
                                                                                            candidates=[])))
                      for s in info.candidates if reg.has("system", s)] + [("Abbrechen", None)],
                     subtitle="Gemischte CD (Audio + Daten) ohne eindeutige Kennung")
            return
        sysdef = reg.get("system", info.system)
        acts = info.actions()
        items = []
        if acts["play"]:
            items.append(("Direkt spielen", lambda a: play(a, info)))
        if acts["rip"]:
            items.append(("Auf Festplatte sichern (CHD)", lambda a: save(a, info)))
        items.append(("Abbrechen", None))
        kind = {"cd": "CD", "dvd": "DVD", "bd": "Blu-ray"}.get(info.media.kind, "Disc")
        sub = f"{info.title}  ·  {kind}"
        if info.system == "dos":
            sub += "  ·  wird für DOSBox Pure gesichert"
        app.sfx("select")
        app.menu(f"{sysdef.name if sysdef else info.system}-Disc erkannt", items, subtitle=sub)

    def play(app, info):
        options = drive.DISC_SYSTEMS[info.system]["play"]
        emus = [core.registry.get("emulator", e) for e in options if core.registry.has("emulator", e)]
        emu = next((e for e in emus if core.emus.installed(e)), emus[0] if emus else None)
        if emu is None:
            app.info("Kein Emulator", ["Für dieses System gibt es keinen Emulator mit Laufwerks-Unterstützung."])
            return
        path = drive.retroarch_path(info.device) if emu.kind == "libretro" else info.device
        game = Game(key=f"disc/{info.system}/{rip.safe_name(info.title)}", system=info.system, path=path,
                    name=info.title)
        app.launch(game, emu.id)

    def save(app, info):
        kind = drive.DISC_SYSTEMS[info.system]["rip"]
        ripper = rip.Ripper()
        missing = ripper.missing_tools(kind)
        if missing:
            app.info("Programme fehlen", [f"Zum Sichern werden benötigt: {', '.join(missing)}",
                                           "Auf RetroForge OS sind sie enthalten (Pakete cdrdao, mame-tools)."])
            return
        dest = core.paths.system_roms(info.system)
        dats = core.paths.home / "system" / "dats"

        def work(progress):
            return ripper.rip(info, kind, dest, progress, dats if dats.is_dir() else None)

        def done(result, error):
            if error:
                app.sfx("error")
                app.info("Sichern fehlgeschlagen", [str(error)])
                return
            core.library.scan()
            check = {True: "  ·  per DAT verifiziert", False: "  ·  nicht in der DAT gefunden", None: ""}
            app.toast(f"Gesichert: {result['name']}{check[result['verified']]}", "good")
        app.progress(f"{info.title} wird gesichert …", work, done)

    # -- entry points -------------------------------------------------------------
    def open_drive(app):
        devs = drive.drives()
        if not devs:
            app.info("Disc-Laufwerk", ["Kein optisches Laufwerk gefunden."])
            return

        def work(progress):
            progress(0, "Disc wird gelesen …")
            for dev in devs:
                m = drive.media(dev)
                if m.present:
                    return drive.identify(dev, m)
            return None

        def done(info, error):
            if error:
                app.info("Disc-Laufwerk", [str(error)])
            elif info is None:
                app.info("Disc-Laufwerk", ["Keine Disc eingelegt."])
            else:
                show(app, info)
        app.progress("Disc-Laufwerk", work, done)

    if drive.drives():
        api.add_menu_entry("disc", "Disc-Laufwerk", open_drive, section="home", order=5)
        api.on("ui.import_hints", lambda core, **_: ["Tipp: Spiele-CDs/-DVDs einfach einlegen – sie werden "
                                                     "automatisch erkannt."])

    # exposed for tests and other plugins
    api.registry.provide("disc", {"drive": drive, "rip": rip, "show": show, "play": play, "save": save})
