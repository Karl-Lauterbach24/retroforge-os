"""Regenerates the README screenshots in docs/screenshots/.

    python tools/readme_screenshots.py

Runs headless with a temporary demo library and a fixed *example* hardware
profile (not the machine it runs on), so the images are reproducible and don't
publish anyone's hardware.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import logging  # noqa: E402

import pygame  # noqa: E402

import make_demo_library  # noqa: E402
from retroforge.core import Core  # noqa: E402
from retroforge.hw.probe import GpuInfo, HardwareInfo  # noqa: E402
from retroforge.settings import GAME  # noqa: E402
from retroforge.ui.app import App  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
EXAMPLE_HW = HardwareInfo(
    arch="x86_64", family="x86_64", cpu_model="AMD Ryzen 7 7800X3D 8-Core Processor", cores=8, threads=16,
    max_mhz=5050, isa=["sse4_1", "sse4_2", "avx", "avx2", "avx512f", "vaes", "f16c", "fma", "bmi1", "bmi2",
                       "abm", "movbe"],
    ram_mb=32 * 1024, board="Beispiel-PC", os="Debian GNU/Linux 13 (trixie)",
    gpus=[GpuInfo(name="NVIDIA GeForce RTX 4070", vendor="nvidia", vendor_id="0x10de", device_id="0x2786",
                  driver="nvidia", vram_mb=12282, integrated=False)],
    vulkan="1.3", vulkan_source="vulkaninfo")
THEMES = [("gameboy", "Game Boy DMG"), ("phosphor", "Phosphor-Terminal"), ("famicom", "Famicom (hell)"),
          ("midnight", "Midnight"), ("demoscene", "Demoscene-Plasma"), ("halloween", "Halloween (Plugin)")]


def main():
    logging.disable(logging.CRITICAL)
    home = Path(tempfile.mkdtemp(prefix="rf-shots-"))
    make_demo_library.main(home)
    core = Core(str(home))

    def fake_probe():
        core.hw = EXAMPLE_HW
        core.reassess()
        return core.hw
    core.probe = fake_probe

    app = App(core, windowed=True)
    app.setup()

    def run(seconds=0.6):
        for _ in range(int(seconds * 30)):
            app.step(1 / 30)

    def shot(name):
        run(0.6)
        pygame.image.save(app.screen, str(OUT / f"{name}.png"))
        print("  ", name)

    def home_screen():
        while len(app.stack) > 1:
            app.pop()
        return app.top

    t0 = time.time()
    while not app.booted and time.time() - t0 < 60:
        run(0.2)
    core.settings.set("ui.theme", "synthwave")
    app.apply_theme()
    # some history so collections and details look lived-in
    nes = core.library.games["nes"]
    for g, plays in ((nes[3], 4), (nes[1], 2)):
        for _ in range(plays):
            core.gamedata.record_play(g.key, 23 * 60)
    core.gamedata.toggle_favorite(nes[3].key)
    core.gamedata.toggle_favorite(core.library.games["snes"][0].key)
    core.settings.set("video.shader", "crt-lottes", GAME, nes[3].key)
    home_screen().rebuild()
    run(4.0)                                   # let the boot toast fade out
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    h = home_screen()
    h.idx = next(i for i, e in enumerate(h.entries) if e[0] == "sys" and e[1].id == "snes")
    shot("home")

    app.push("gamelist", system="nes")
    app.top.nav.set(next(i for i, g in enumerate(app.top.games) if g.key == nes[3].key))
    shot("gamelist")

    home_screen()
    app.push("settings", scope="game", target=nes[3].key, system="nes")
    app.top.focus = 1
    shot("settings-game")

    home_screen()
    app.push("hardware")
    app.top.nav.set(app.top.ladder.index("ps5"))
    shot("hardware")

    home_screen()
    disc = core.registry.service("disc")
    Info, Media = disc["drive"].DiscInfo, disc["drive"].Media
    disc["show"](app, Info(system="ps2", label="GRAN_TURISMO_4", serial="SCES-51719", device="/dev/sr0",
                           media=Media(True, "dvd")))
    shot("disc-detected")

    home_screen()
    disc["show"](app, Info(system="ps3", problem="ps3", label="BLES00932", device="/dev/sr0", media=Media(True, "bd")))
    shot("disc-ps3")

    home_screen()
    app.push("plugins")
    app.top.nav.set(next(i for i, p in enumerate(app.top.rows) if p.id == "ps3-disc"))
    shot("plugins")

    # theme gallery: 2 columns × 3 rows of home screens
    tiles = []
    for tid, label in THEMES:
        home_screen()
        core.settings.set("ui.theme", tid)
        app.apply_theme()
        run(1.5)
        tiles.append((pygame.transform.smoothscale(app.screen, (640, 360)), label))
    gallery = pygame.Surface((1280 + 8, 3 * 360 + 16))
    gallery.fill((12, 12, 18))
    font = pygame.font.SysFont("dejavusans,segoeui,arial", 20, bold=True)
    for k, (img, label) in enumerate(tiles):
        x, y = (k % 2) * 648, (k // 2) * 368
        gallery.blit(img, (x, y))
        txt = font.render(label, True, (255, 255, 255))
        box = pygame.Rect(x + 12, y + 360 - 44, txt.get_width() + 24, 32)
        pygame.draw.rect(gallery, (0, 0, 0), box, border_radius=16)
        gallery.blit(txt, txt.get_rect(center=box.center))
    pygame.image.save(gallery, str(OUT / "themes.png"))
    print("   themes")
    core.settings.set("ui.theme", "synthwave")


if __name__ == "__main__":
    main()
