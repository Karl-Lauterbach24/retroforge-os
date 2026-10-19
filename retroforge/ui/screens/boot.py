"""Boot splash while the core probes hardware, loads plugins and scans ROMs."""
import math
import threading

import pygame

from .. import pixelfont
from .. import widgets as w
from ..theme import darken, lighten, mix
from .base import Screen


class BootScreen(Screen):
    animating = True

    def __init__(self, app):
        super().__init__(app)
        self.msg = "Starte …"
        self.done = False
        self.error = None
        threading.Thread(target=self._boot, daemon=True, name="boot").start()

    def _boot(self):
        core = self.core
        try:
            self.msg = "Themes & Plugins werden geladen …"
            core.boot(do_probe=False, scan=False)
            self.msg = "Hardware wird erkannt …"
            core.probe()
            self.msg = "Bibliothek wird gescannt …"
            core.library.scan()
            self.msg = "Bereit."
        except Exception as e:   # never get stuck on the splash
            import logging
            logging.getLogger("retroforge.ui").exception("boot failed")
            self.error = e
        self.done = True

    def update(self, dt):
        super().update(dt)
        if self.done and self.t > 1.6:
            app = self.app
            app.booted = True
            app.apply_theme()
            app.replace("home")
            if self.error:
                app.toast(f"Startfehler: {self.error}", "bad")
            elif app.core.assessment and app.core.assessment.max_console:
                s = app.core.registry.get("system", app.core.assessment.max_console)
                app.toast(f"Hardware erkannt – bis {s.name} spielbar", "good")

    def handle(self, action):
        return True

    def draw(self, surf):
        th = self.theme
        surf.fill(darken(th.c["bg"], 0.3))
        cx, cy = w.W // 2, w.H // 2 - 30
        # expanding rings
        for i in range(5):
            r = ((self.t * 120) + i * 70) % 360
            a = max(0, 1 - r / 360)
            pygame.draw.circle(surf, mix(th.c["bg"], th.c["accent2"], a * 0.6), (cx, cy), int(r), 2)
        reveal = min(1.0, self.t / 0.9)
        text = "RETROFORGE"
        n = int(len(text) * reveal + 0.999)
        logo = pixelfont.render(text[:n], 9, th.c["accent"], darken(th.c["accent"], 0.6))
        surf.blit(logo, logo.get_rect(center=(cx, cy)))
        sub = pixelfont.render("O S", 4, th.c["accent2"])
        if self.t > 0.9:
            surf.blit(sub, sub.get_rect(center=(cx, cy + 70)))
        # progress bar
        br = pygame.Rect(cx - 220, cy + 130, 440, 8)
        frac = 1.0 if self.done else min(0.92, self.t / 2.5)
        w.bar(surf, th, br, frac, th.c["accent2"])
        w.text(surf, th, self.msg, (cx, br.bottom + 24), 18, th.c["muted"], anchor="midtop")

    def hints(self):
        return []
