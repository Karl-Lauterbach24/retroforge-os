"""Example plugin: zips a game's saves/states before every launch."""
import time
import zipfile

from retroforge.settings import GLOBAL, SettingDef


def register(api):
    api.add_setting(SettingDef("backup.keep", "Spielstand-Backups behalten", 5, "System",
                               choices=[(0, "Aus"), (3, "3"), (5, "5"), (10, "10"), (25, "25")],
                               scopes=(GLOBAL,), order=50,
                               help="Vor jedem Spielstart werden Saves & Savestates gesichert."))

    def on_launch(plan, core, **_):
        keep = int(api.setting("backup.keep", default=5) or 0)
        if not keep:
            return
        g = plan.game
        files = []
        for root in (core.paths.saves / g.system, core.paths.states / g.system):
            if root.is_dir():
                files += [p for p in root.glob(g.stem + ".*") if p.is_file()]
        if not files:
            return
        dest = api.data_dir() / g.system
        dest.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        with zipfile.ZipFile(dest / f"{g.stem}__{stamp}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, f"{p.parent.parent.name}/{p.name}")
        backups = sorted(dest.glob(f"{g.stem}__*.zip"))
        for old in backups[:-keep]:
            old.unlink()
        api.log.info("backup of %d files for %s", len(files), g.key)

    api.on("game.launch", on_launch)

    def menu(game, core, **_):
        dest = api.data_dir() / game.system
        n = len(list(dest.glob(f"{game.stem}__*.zip"))) if dest.is_dir() else 0
        if not n:
            return None
        return [(f"Spielstand-Backups ({n})", lambda app: app.info(
            "Spielstand-Backups", [p.name for p in sorted(dest.glob(f"{game.stem}__*.zip"), reverse=True)]
            + ["", f"Ordner: {dest}"]))]

    api.on("ui.game_menu", menu)
