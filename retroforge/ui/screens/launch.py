"""Launch animation and the 'game running' screen (windowed/dev mode)."""
import time

import pygame

from .. import pixelfont
from .. import widgets as w
from ..theme import darken, mix
from .base import Screen


class LaunchScreen(Screen):
    animating = True

    def __init__(self, app, plan):
        super().__init__(app)
        self.plan = plan
        self.started = False
        app.sfx("launch")

    def handle(self, a):
        return True

    def update(self, dt):
        super().update(dt)
        if self.t > 0.9 and not self.started:
            self.started = True
            self.app.pop(self)
            self.app.run_game(self.plan)

    def draw(self, surf):
        th = self.theme
        sysdef = self.core.registry.get("system", self.plan.game.system)
        col = th.c["accent"]
        if sysdef:
            from ..theme import color
            col = color(sysdef.color)
        k = min(1.0, self.t / 0.5)
        surf.fill(darken(th.c["bg"], 0.5))
        # wipe bars
        for i in range(12):
            h = w.H / 12
            x = int(-w.W + (w.W * 2) * min(1, max(0, k * 1.6 - i * 0.05)))
            pygame.draw.rect(surf, mix(col, th.c["bg"], 0.55 + 0.03 * i), (x, int(i * h), w.W, int(h) + 1))
        title = th.title(self.plan.game.name[:28], 4)
        surf.blit(title, title.get_rect(center=(w.W // 2, w.H // 2 - 20)))
        dots = "." * (int(self.t * 6) % 4)
        w.text(surf, th, f"{self.plan.emulator.name} startet{dots}", (w.W // 2, w.H // 2 + 40), 22,
               th.c["text"], anchor="midtop")
        for i, n in enumerate(self.plan.notes[:3]):
            w.text(surf, th, n, (w.W // 2, w.H // 2 + 90 + i * 26), 16, th.c["warn"], anchor="midtop")

    def hints(self):
        return []


class RunningScreen(Screen):
    """Shown while a game runs in its own window (development / desktop)."""
    animating = True

    def __init__(self, app, plan, thread, result):
        super().__init__(app)
        self.plan, self.thread, self.result = plan, thread, result
        self.t0 = time.time()

    def update(self, dt):
        super().update(dt)
        if not self.thread.is_alive():
            self.app.pop(self)
            self.app.after_game(self.plan, self.result.get("r"))

    def handle(self, a):
        if a == "back":
            self.app.core.launcher.stop()
        return True

    def draw(self, surf):
        th = self.theme
        w.panel(surf, (240, 200, 800, 300), th, th.c["panel2"], border=th.c["accent"])
        img = pixelfont.render("SPIEL LÄUFT", 5, th.c["accent"])
        surf.blit(img, img.get_rect(center=(w.W // 2, 260)))
        w.text(surf, th, self.plan.game.name, (w.W // 2, 310), 26, bold=True, anchor="midtop", max_w=740)
        secs = int(time.time() - self.t0)
        w.text(surf, th, f"{self.plan.emulator.name} · {secs // 60:02d}:{secs % 60:02d}", (w.W // 2, 356), 18,
               th.c["muted"], anchor="midtop")
        w.text(surf, th, self.plan.describe(), (w.W // 2, 410), 13, th.c["muted"], anchor="midtop", max_w=740)

    def hints(self):
        return [("back", "Spiel beenden")]
