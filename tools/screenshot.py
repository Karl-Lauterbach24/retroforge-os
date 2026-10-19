"""Headless UI walkthrough that saves screenshots (used for visual checks/CI).

    python tools/screenshot.py OUTDIR [--home DIR] [--theme ID]
"""
import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from retroforge.core import Core  # noqa: E402
from retroforge.ui.app import App  # noqa: E402

def home(app):
    while len(app.stack) > 1:
        app.pop()


# (name, setup(app) or None, actions)
SCRIPT = [
    ("home", None, ["right", "left"]),
    ("home-quickbar", None, ["down", "right", "right"]),
    ("gamelist", lambda a: (home(a), a.push("gamelist", system="nes")), ["down", "down"]),
    ("game-menu", None, ["x"]),
    ("settings-game", None, ["down", "down", "down", "ok", "ok", "right", "right"]),
    ("settings-global", lambda a: (home(a), a.push("settings")), ["down", "ok"]),
    ("hardware", lambda a: (home(a), a.push("hardware")), []),
    ("emulators", lambda a: (home(a), a.push("emulators")), ["down"]),
    ("bios", lambda a: (home(a), a.push("bios")), []),
    ("plugins", lambda a: (home(a), a.push("plugins")), []),
    ("importer", lambda a: (home(a), a.push("importer")), []),
    ("main-menu", lambda a: home(a), ["menu"]),
    ("collection", lambda a: (home(a), a.core.gamedata.toggle_favorite(a.core.library.games["nes"][0].key),
                              a.push("gamelist", collection=a.core.registry.get("collection", "favorites"))), []),
]


def frames(app, seconds, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        app.step(dt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--home")
    ap.add_argument("--theme")
    ap.add_argument("--only", help="comma separated shot names")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    core = Core(args.home)
    app = App(core, windowed=True)
    app.setup()
    frames(app, 0.5)
    pygame.image.save(app.screen, str(out / "00-boot.png"))
    t0 = time.time()
    while not app.booted and time.time() - t0 < 30:
        frames(app, 0.2)
    if args.theme:
        core.settings.set("ui.theme", args.theme)
        app.apply_theme()
    frames(app, 1.0)
    only = set(args.only.split(",")) if args.only else None
    for i, (name, setup, actions) in enumerate(SCRIPT, 1):
        if setup:
            setup(app)
            frames(app, 0.3)
        for a in actions:
            app.dispatch(a)
            frames(app, 0.12)
        frames(app, 0.8)
        while app.top and type(app.top).__name__ == "ProgressDialog":
            frames(app, 0.2)
        frames(app, 0.4)
        if not only or name in only:
            pygame.image.save(app.screen, str(out / f"{i:02d}-{name}.png"))
    print("ok", out)


if __name__ == "__main__":
    main()
