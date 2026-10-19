"""Example plugin: idle hook + custom screen."""
import random

from retroforge.settings import GLOBAL, SettingDef


def register(api):
    api.add_setting(SettingDef("screensaver.minutes", "Bildschirmschoner nach", 5, "Oberfläche",
                               choices=[(0, "Nie"), (2, "2 min"), (5, "5 min"), (10, "10 min"), (30, "30 min")],
                               scopes=(GLOBAL,), order=20))

    def make(app, **kw):
        import pygame
        from retroforge.ui import pixelfont
        from retroforge.ui import widgets as w
        from retroforge.ui.screens.base import Screen
        from retroforge.ui.theme import color

        class Saver(Screen):
            animating = True

            def __init__(self, app):
                super().__init__(app)
                self.x, self.y, self.vx, self.vy = 200.0, 150.0, 140.0, 95.0
                self.col = app.theme.c["accent"]
                games = list(self.core.library.by_key.values())
                self.tips = random.sample(games, min(12, len(games)))
                self.tip_t = 0.0

            def handle(self, a):
                self.app.pop(self)
                return True

            def text_input(self, s):
                self.app.pop(self)

            def update(self, dt):
                super().update(dt)
                self.tip_t += dt
                logo = pixelfont.size("RETROFORGE", 6)
                self.x += self.vx * dt
                self.y += self.vy * dt
                for axis, lim in (("x", w.W - logo[0]), ("y", w.H - logo[1])):
                    v = getattr(self, axis)
                    if v < 0 or v > lim:
                        setattr(self, "v" + axis, -getattr(self, "v" + axis))
                        setattr(self, axis, max(0, min(lim, v)))
                        self.col = random.choice([self.theme.c["accent"], self.theme.c["accent2"],
                                                  self.theme.c["good"], self.theme.c["warn"]])

            def draw(self, surf):
                surf.fill((0, 0, 0))
                surf.blit(pixelfont.render("RETROFORGE", 6, self.col), (int(self.x), int(self.y)))
                if self.tips:
                    g = self.tips[int(self.tip_t / 6) % len(self.tips)]
                    s = self.core.registry.get("system", g.system)
                    w.text(surf, self.theme, f"Lust auf  {g.name}  ({s.short if s else g.system})?",
                           (w.W // 2, w.H - 70), 20, color("#888888"), anchor="center")

            def hints(self):
                return []

        return Saver(app)

    api.add_screen("screensaver", make)

    def on_idle(app, seconds, **_):
        minutes = int(api.setting("screensaver.minutes", default=5) or 0)
        top = app.top
        if not minutes or seconds < minutes * 60 or top is None:
            return
        if type(top).__name__ in ("Saver", "BootScreen", "LaunchScreen", "RunningScreen", "ProgressDialog"):
            return
        app.push("screensaver")

    api.on("ui.idle", on_idle)
