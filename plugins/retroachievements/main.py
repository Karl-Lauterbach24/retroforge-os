"""Example plugin: modifies every RetroArch launch via the before_launch filter.

Credentials are read from /userdata/system/retroachievements.cfg:
    username = myname
    token = <API token from RetroArch login or retroachievements.org>
(no password is ever stored).
"""
from retroforge.settings import GLOBAL, SettingDef


def _read_creds(path):
    creds = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip().lower()] = v.strip().strip('"')
    except OSError:
        pass
    return creds


def register(api):
    api.add_setting(SettingDef("cheevos.hardcore", "RetroAchievements Hardcore", False, "Latenz & Komfort", "bool",
                               scopes=(GLOBAL,), order=6,
                               help="Hardcore deaktiviert Savestates, Rewind & Cheats – für die Bestenlisten."))
    cfg = api.paths.home / "system" / "retroachievements.cfg"

    def before_launch(plan, core, **_):
        if plan.emulator.kind != "libretro" or not plan.settings.get("game.achievements"):
            return plan
        creds = _read_creds(cfg)
        if not creds.get("username") or not creds.get("token"):
            plan.notes.append("RetroAchievements: Zugangsdaten fehlen (system/retroachievements.cfg)")
            return plan
        plan.ra_config.update({
            "cheevos_enable": True,
            "cheevos_username": creds["username"],
            "cheevos_token": creds["token"],
            "cheevos_hardcore_mode_enable": bool(api.setting("cheevos.hardcore", default=False)),
        })
        if api.setting("cheevos.hardcore", default=False):
            plan.ra_config["rewind_enable"] = False
            plan.ra_config["run_ahead_enabled"] = False
        return plan

    api.on("game.before_launch", before_launch)
