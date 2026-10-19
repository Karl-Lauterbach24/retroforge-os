"""Theme: colours, fonts, background, sounds. Themes are plain JSON
(``themes/<id>/theme.json``) or dicts registered by plugins."""
import os

import pygame

from . import pixelfont

DEFAULT_COLORS = {
    "bg": "#0d0221", "bg2": "#241147", "panel": "#160a33d8", "panel2": "#2a1758e6",
    "accent": "#ff2a6d", "accent2": "#05d9e8", "text": "#f6f1ff", "muted": "#a89cc8",
    "good": "#3df5a7", "ok": "#4cc9f0", "warn": "#ffd166", "bad": "#ff4d6d", "off": "#6c6c80",
    "shadow": "#00000090",
}
SANS_CANDIDATES = "notosans,dejavusans,segoeui,ubuntu,cantarell,arial,helvetica"


def color(value, default=(255, 0, 255)):
    if isinstance(value, (tuple, list)):
        return tuple(value)
    if not isinstance(value, str) or not value.startswith("#"):
        return default
    h = value[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in range(0, len(h), 2))
    except ValueError:
        return default


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(c, t):
    return mix(c, (255, 255, 255), t)


def darken(c, t):
    return mix(c, (0, 0, 0), t)


class Theme:
    def __init__(self, data, registry=None):
        self.data = data
        self.id = data.get("id", "theme")
        self.name = data.get("name", self.id)
        self.dir = data.get("dir")
        self.c = {k: color(v) for k, v in DEFAULT_COLORS.items()}
        self.c.update({k: color(v) for k, v in data.get("colors", {}).items()})
        self.radius = int(data.get("radius", 14))
        self.title_style = data.get("title_font", "pixel")
        self.font_spec = data.get("font", "sans")
        self.soundpack = data.get("soundpack", "chiptune")
        self.music = data.get("music", {})
        self.ui_crt = bool(data.get("crt", False))
        self.bg_spec = data.get("background", {"type": "gradient"})
        self._fonts = {}

    def font(self, size, bold=False):
        key = (size, bold)
        f = self._fonts.get(key)
        if f:
            return f
        spec = self.font_spec
        if spec not in ("sans", "pixel") and self.dir and os.path.isfile(os.path.join(self.dir, spec)):
            f = pygame.font.Font(os.path.join(self.dir, spec), size)
            f.set_bold(bold)
        else:
            try:
                f = pygame.font.SysFont(SANS_CANDIDATES, size, bold=bold)
            except Exception:
                f = pygame.font.Font(None, int(size * 1.35))
        self._fonts[key] = f
        return f

    def title(self, text, scale, col=None, shadow=True):
        """Heading in the theme's title style (pixel font or bold sans)."""
        col = col or self.c["text"]
        if self.title_style == "pixel":
            return pixelfont.render(text, scale, col, darken(self.c["bg"], 0.4) + (200,) if shadow else None)
        return self.font(int(scale * 9), bold=True).render(text, True, col)

    def background(self, registry, size):
        from .backgrounds import make_background
        return make_background(self, registry, size)
