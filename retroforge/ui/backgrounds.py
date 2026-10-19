"""Animated backgrounds, all procedural and cheap.

Expensive parts are pre-rendered once; per frame only a few lines/blits are
drawn (the plasma uses 8-bit palette cycling, the classic demoscene trick, so
animating it costs one palette swap and one scale). Plugins register more
via ``api.add_background(id, factory)``.
"""
import math
import os
import random

import pygame

from .theme import color, darken, lighten, mix


def vertical_gradient(size, top, bottom):
    w, h = size
    surf = pygame.Surface((1, h))
    for y in range(h):
        surf.set_at((0, y), mix(top, bottom, y / max(1, h - 1)))
    return pygame.transform.scale(surf, (w, h))


class Background:
    animated = True

    def __init__(self, theme, params, size):
        self.theme, self.p, self.size = theme, params, size
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        pass


class GradientBG(Background):
    animated = False

    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        self.surf = vertical_gradient(size, color(params.get("top"), theme.c["bg2"]),
                                      color(params.get("bottom"), theme.c["bg"]))

    def draw(self, surf):
        surf.blit(self.surf, (0, 0))


class SynthwaveBG(Background):
    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        w, h = size
        self.horizon = int(h * 0.56)
        sky_top = color(params.get("sky_top"), theme.c["bg"])
        sky_bottom = color(params.get("sky_bottom"), theme.c["bg2"])
        self.grid_col = color(params.get("grid"), theme.c["accent"])
        self.floor_col = color(params.get("floor"), darken(theme.c["bg"], 0.3))
        base = pygame.Surface(size)
        base.blit(vertical_gradient((w, self.horizon), sky_top, sky_bottom), (0, 0))
        base.fill(self.floor_col, (0, self.horizon, w, h - self.horizon))
        # stars
        rnd = random.Random(7)
        for _ in range(90):
            x, y = rnd.randrange(w), rnd.randrange(int(self.horizon * 0.8))
            b = rnd.randint(90, 230)
            base.set_at((x, y), (b, b, b))
        # sun with stripes
        r = int(h * 0.22)
        cx, cy = w // 2, self.horizon - int(r * 0.35)
        sun = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        top, bot = color(params.get("sun_top"), (255, 230, 109)), color(params.get("sun_bottom"), theme.c["accent"])
        for y in range(r * 2):
            dy = y - r
            half = int(math.sqrt(max(0, r * r - dy * dy)))
            col = mix(top, bot, y / (2 * r))
            gap = y > r * 0.9 and (y // 6) % 3 == 0
            if not gap:
                pygame.draw.line(sun, col, (r - half, y), (r + half, y))
        glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        for i in range(12, 0, -1):
            pygame.draw.circle(glow, bot + (6,), (r * 2, r * 2), int(r * (1 + i * 0.07)))
        base.blit(glow, (cx - 2 * r, cy - 2 * r))
        base.blit(sun, (cx - r, cy - r), area=pygame.Rect(0, 0, 2 * r, r + int(r * 0.35)))
        # mountains silhouette
        pts = [(0, self.horizon)]
        rnd = random.Random(3)
        x = 0
        while x < w:
            x += rnd.randint(40, 110)
            pts.append((x, self.horizon - rnd.randint(10, int(h * 0.09))))
        pts.append((w, self.horizon))
        pygame.draw.polygon(base, darken(sky_bottom, 0.55), pts)
        pygame.draw.lines(base, self.grid_col, False, pts[1:-1], 1)
        self.base = base

    def draw(self, surf):
        surf.blit(self.base, (0, 0))
        w, h = self.size
        hz = self.horizon
        col = self.grid_col
        dim = mix(col, self.floor_col, 0.55)
        cx = w // 2
        for i in range(-14, 15):
            x_bottom = cx + i * w * 0.11
            pygame.draw.line(surf, dim, (cx + i * 18, hz), (int(x_bottom), h), 1)
        speed = float(self.p.get("speed", 0.35))
        phase = (self.t * speed) % 1.0
        for i in range(14):
            z = i + 1 - phase                      # depth; decreasing → lines move towards us
            y = hz + int((h - hz) * 0.6 / z)
            if hz < y < h:
                pygame.draw.line(surf, mix(dim, col, (y - hz) / (h - hz)), (0, y), (w, y), 1)
        pygame.draw.line(surf, lighten(col, 0.3), (0, hz), (w, hz), 2)


class StarfieldBG(Background):
    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        self.base = vertical_gradient(size, theme.c["bg"], darken(theme.c["bg2"], 0.2))
        rnd = random.Random(11)
        self.stars = [[rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.05, 1)] for _ in range(int(params.get("count", 180)))]
        self.tint = color(params.get("tint"), theme.c["accent2"])

    def update(self, dt):
        super().update(dt)
        sp = float(self.p.get("speed", 0.12)) * dt
        for s in self.stars:
            s[2] -= sp
            if s[2] <= 0.02:
                s[0], s[1], s[2] = random.uniform(-1, 1), random.uniform(-1, 1), 1.0

    def draw(self, surf):
        surf.blit(self.base, (0, 0))
        w, h = self.size
        for x, y, z in self.stars:
            sx, sy = int(w / 2 + x / z * w * 0.5), int(h / 2 + y / z * h * 0.5)
            if 0 <= sx < w and 0 <= sy < h:
                b = 1 - z
                c = mix((40, 40, 60), lighten(self.tint, 0.5), b)
                r = 2 if z < 0.3 else 1
                surf.fill(c, (sx, sy, r, r))


class PhosphorBG(Background):
    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        w, h = size
        self.base = vertical_gradient(size, darken(theme.c["bg2"], 0.1), theme.c["bg"])
        # faint grid of "characters"
        rnd = random.Random(5)
        glyph = theme.font(14)
        col = mix(theme.c["bg"], theme.c["accent"], 0.13)
        for y in range(10, h, 22):
            line = "".join(rnd.choice("01  ░▒  RETROFORGE  <>/#") for _ in range(w // 9))
            self.base.blit(glyph.render(line, False, col), (6, y))
        self.bar = pygame.Surface((w, 90), pygame.SRCALPHA)
        for y in range(90):
            a = int(18 * math.sin(math.pi * y / 90))
            self.bar.fill(theme.c["accent"] + (a,), (0, y, w, 1))

    def draw(self, surf):
        surf.blit(self.base, (0, 0))
        y = int((self.t * 60) % (self.size[1] + 90)) - 90
        surf.blit(self.bar, (0, y))


class DmgBG(Background):
    """Game Boy style: four-tone dithered tiles scrolling diagonally."""

    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        pal = [color(c) for c in params.get("palette", ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"])]
        tile = 48
        w, h = size
        self.tile = tile
        big = pygame.Surface((w + tile * 2, h + tile * 2))
        big.fill(pal[0])
        for ty in range(0, h + tile * 2, tile):
            for tx in range(0, w + tile * 2, tile):
                if ((tx // tile) + (ty // tile)) % 2 == 0:
                    pygame.draw.rect(big, pal[1], (tx + 6, ty + 6, tile - 12, tile - 12), 2)
                else:
                    for py in range(ty + 8, ty + tile - 8, 4):
                        for px in range(tx + 8 + (py // 4) % 2 * 2, tx + tile - 8, 4):
                            big.set_at((px, py), pal[1])
        self.big = big

    def draw(self, surf):
        o = int(self.t * 14) % self.tile
        surf.blit(self.big, (-o, -o))


class PlasmaBG(Background):
    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        lw, lh = 160, 90
        self.low = pygame.Surface((lw, lh), 0, 8)
        arr = pygame.PixelArray(self.low)
        for y in range(lh):
            for x in range(lw):
                v = (math.sin(x / 16.0) + math.sin(y / 8.0) + math.sin((x + y) / 16.0)
                     + math.sin(math.sqrt(x * x + y * y) / 8.0))
                arr[x, y] = int((v + 4) * 31.875) & 255
        del arr
        a, b, c = theme.c["bg"], theme.c["accent"], theme.c["accent2"]
        dark = float(params.get("darkness", 0.62))
        self.pal = []
        for i in range(256):
            t = (math.sin(i / 256 * math.tau) + 1) / 2
            u = (math.sin(i / 256 * math.tau * 2 + 1) + 1) / 2
            self.pal.append(darken(mix(mix(a, b, t), c, u * 0.6), dark))
        # scale once; animating is then just a palette rotation of the 8-bit surface
        self.out = pygame.transform.scale(self.low, size)

    def draw(self, surf):
        shift = int(self.t * 40) % 256
        self.out.set_palette(self.pal[shift:] + self.pal[:shift])
        surf.blit(self.out, (0, 0))


class ImageBG(Background):
    animated = False

    def __init__(self, theme, params, size):
        super().__init__(theme, params, size)
        path = params.get("image", "")
        if theme.dir and not os.path.isabs(path):
            path = os.path.join(theme.dir, path)
        try:
            img = pygame.image.load(path).convert()
            iw, ih = img.get_size()
            k = max(size[0] / iw, size[1] / ih)
            img = pygame.transform.smoothscale(img, (int(iw * k), int(ih * k)))
            self.surf = img.subsurface(((img.get_width() - size[0]) // 2, (img.get_height() - size[1]) // 2,
                                        size[0], size[1])).copy()
        except (pygame.error, FileNotFoundError, ValueError):
            self.surf = vertical_gradient(size, theme.c["bg2"], theme.c["bg"])
        dim = pygame.Surface(size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(params.get("dim", 110))))
        self.surf.blit(dim, (0, 0))

    def draw(self, surf):
        surf.blit(self.surf, (0, 0))


BUILTIN = {"gradient": GradientBG, "synthwave": SynthwaveBG, "starfield": StarfieldBG,
           "phosphor": PhosphorBG, "dmg": DmgBG, "plasma": PlasmaBG, "image": ImageBG}


def register_builtin(registry):
    for k, cls in BUILTIN.items():
        if not registry.has("background", k):
            registry.add("background", k, cls, origin="core")


def make_background(theme, registry, size):
    spec = dict(theme.bg_spec)
    factory = registry.get("background", spec.get("type", "gradient")) or GradientBG
    try:
        return factory(theme, spec, size)
    except Exception:
        import logging
        logging.getLogger("retroforge.ui").exception("background %s failed", spec.get("type"))
        return GradientBG(theme, {}, size)
