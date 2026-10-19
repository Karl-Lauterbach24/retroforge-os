"""Example plugin: adds themes *and* a new animated background type."""
import math
import random


def register(api):
    def make_falling(theme, params, size):
        import pygame
        from retroforge.ui.backgrounds import Background, vertical_gradient
        from retroforge.ui.theme import color

        class Falling(Background):
            """Falling leaves (Halloween) or snow (winter) over a moonlit gradient."""

            def __init__(self, theme, params, size):
                super().__init__(theme, params, size)
                w, h = size
                self.base = vertical_gradient(size, color(params.get("top"), theme.c["bg2"]), theme.c["bg"])
                moon = color(params.get("moon", "#fff4d6"))
                pygame.draw.circle(self.base, moon, (int(w * 0.82), int(h * 0.18)), 54)
                pygame.draw.circle(self.base, theme.c["bg2"], (int(w * 0.82) + 22, int(h * 0.18) - 10), 48)
                self.kind = params.get("particles", "leaves")
                self.cols = [color(c) for c in params.get("colors", ["#ff7b00", "#ffb703", "#9d0208"])]
                rnd = random.Random(1)
                self.parts = [[rnd.uniform(0, w), rnd.uniform(-h, h), rnd.uniform(18, 60), rnd.uniform(0, 6.28),
                               rnd.choice(self.cols), rnd.uniform(3, 7)] for _ in range(70)]

            def update(self, dt):
                super().update(dt)
                w, h = self.size
                for p in self.parts:
                    p[1] += p[2] * dt
                    p[3] += dt * 1.7
                    if p[1] > h + 10:
                        p[1], p[0] = -10, random.uniform(0, w)

            def draw(self, surf):
                surf.blit(self.base, (0, 0))
                for x, y, sp, ph, col, r in self.parts:
                    xx = int(x + math.sin(ph) * 22)
                    if self.kind == "snow":
                        pygame.draw.circle(surf, col, (xx, int(y)), int(r * 0.5))
                    else:
                        pygame.draw.ellipse(surf, col, (xx, int(y), int(r * 2), int(r * (1 + math.sin(ph)))+1))

        return Falling(theme, params, size)

    api.add_background("falling", make_falling)
    api.add_theme({
        "id": "halloween", "name": "Halloween (Saison)",
        "colors": {"bg": "#0b0710", "bg2": "#2b1236", "panel": "#140b1cd8", "panel2": "#24122ef2",
                   "accent": "#ff7b00", "accent2": "#b5e48c", "text": "#fff4e6", "muted": "#b39ab8"},
        "background": {"type": "falling", "particles": "leaves", "top": "#2b1236"},
        "title_font": "pixel", "radius": 12, "soundpack": "arcade",
        "music": {"tempo": 100, "root": 50, "scale": "minor", "progression": [0, 1, 0, 5], "style": "arp"},
    })
    api.add_theme({
        "id": "winter", "name": "Winterabend (Saison)",
        "colors": {"bg": "#0a1426", "bg2": "#1d3557", "panel": "#0d1b30d8", "panel2": "#16294af2",
                   "accent": "#a8dadc", "accent2": "#f1faee", "text": "#f1faee", "muted": "#8fa9c4"},
        "background": {"type": "falling", "particles": "snow", "colors": ["#ffffff", "#dbe9ff"], "top": "#1d3557"},
        "title_font": "pixel", "radius": 16, "soundpack": "soft",
        "music": {"tempo": 92, "root": 64, "scale": "major", "progression": [0, 5, 3, 4], "style": "calm"},
    })
