"""Small drawing helpers shared by all screens."""
import pygame

from . import pixelfont
from .theme import darken, lighten, mix

W, H = 1280, 720
STATUS_COLOR_KEYS = {0: "off", 1: "bad", 2: "warn", 3: "ok", 4: "good"}

_panel_cache = {}


def panel(surf, rect, theme, col=None, radius=None, border=None, alpha=None):
    """Rounded translucent panel (cached per size/colour)."""
    rect = pygame.Rect(rect)
    col = col or theme.c["panel"]
    if alpha is not None:
        col = col[:3] + (alpha,)
    r = theme.radius if radius is None else radius
    key = (rect.size, tuple(col), r, tuple(border) if border else None)
    s = _panel_cache.get(key)
    if s is None:
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, col, s.get_rect(), border_radius=r)
        if border:
            pygame.draw.rect(s, border, s.get_rect(), 2, border_radius=r)
        if len(_panel_cache) > 300:
            _panel_cache.clear()
        _panel_cache[key] = s
    surf.blit(s, rect.topleft)


def text(surf, theme, s, pos, size=20, col=None, bold=False, anchor="topleft", max_w=None):
    f = theme.font(size, bold)
    s = str(s)
    if max_w and f.size(s)[0] > max_w:
        while s and f.size(s + "…")[0] > max_w:
            s = s[:-1]
        s += "…"
    img = f.render(s, True, col or theme.c["text"])
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def wrap(theme, s, size, max_w, bold=False):
    f = theme.font(size, bold)
    lines, cur = [], ""
    for word in str(s).split():
        t = (cur + " " + word).strip()
        if f.size(t)[0] <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def pill(surf, theme, label, pos, col, size=15, anchor="topleft", filled=False):
    f = theme.font(size, True)
    img = f.render(label, True, darken(col, 0.75) if filled else col)
    r = img.get_rect()
    box = pygame.Rect(0, 0, r.w + 18, r.h + 6)
    setattr(box, anchor, pos)
    s = pygame.Surface(box.size, pygame.SRCALPHA)
    if filled:
        pygame.draw.rect(s, col, s.get_rect(), border_radius=box.h // 2)
    else:
        pygame.draw.rect(s, col + (40,), s.get_rect(), border_radius=box.h // 2)
        pygame.draw.rect(s, col, s.get_rect(), 1, border_radius=box.h // 2)
    surf.blit(s, box)
    surf.blit(img, img.get_rect(center=box.center))
    return box


def status_color(theme, status):
    return theme.c[STATUS_COLOR_KEYS.get(status, "off")]


def bar(surf, theme, rect, frac, col=None, bg=None):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, bg or darken(theme.c["panel2"][:3], 0.2), rect, border_radius=rect.h // 2)
    if frac > 0:
        f = rect.copy()
        f.w = max(rect.h, int(rect.w * min(1, frac)))
        pygame.draw.rect(surf, col or theme.c["accent"], f, border_radius=rect.h // 2)


def segments(surf, rect, n, filled, col, off):
    rect = pygame.Rect(rect)
    gap = 4
    w = (rect.w - gap * (n - 1)) / n
    for i in range(n):
        r = pygame.Rect(int(rect.x + i * (w + gap)), rect.y, int(w), rect.h)
        pygame.draw.rect(surf, col if i < filled else off, r, border_radius=3)


def header(surf, theme, title, subtitle=None, right=None):
    img = theme.title(title, 4, theme.c["text"])
    surf.blit(img, (48, 34))
    if subtitle:
        text(surf, theme, subtitle, (50, 34 + img.get_height() + 10), 18, theme.c["muted"])
    if right:
        text(surf, theme, right, (W - 48, 40), 18, theme.c["muted"], anchor="topright")
    pygame.draw.line(surf, mix(theme.c["accent"], theme.c["bg"], 0.4), (48, 112), (W - 48, 112), 2)


BUTTON_GLYPH = {"ok": "A", "back": "B", "x": "X", "y": "Y", "menu": "START", "select": "SELECT",
                "lr": "L/R", "dpad": "+", "updown": "↑↓", "leftright": "←→"}
BUTTON_COLOR = {"ok": (60, 200, 120), "back": (230, 70, 90), "x": (70, 140, 240), "y": (240, 190, 60)}


def hints(surf, theme, items, y=H - 38):
    """Bottom button-hint bar: [(button, label), ...]"""
    x = W - 40
    f = theme.font(17)
    for btn, label in reversed(items):
        lab = f.render(label, True, theme.c["muted"])
        x -= lab.get_width()
        surf.blit(lab, (x, y))
        glyph = BUTTON_GLYPH.get(btn, btn)
        gcol = BUTTON_COLOR.get(btn, theme.c["muted"])
        gi = theme.font(14, True).render(glyph, True, (20, 20, 28))
        gw = max(24, gi.get_width() + 12)
        x -= gw + 8
        r = pygame.Rect(x, y - 1, gw, 24)
        pygame.draw.rect(surf, gcol, r, border_radius=12)
        surf.blit(gi, gi.get_rect(center=r.center))
        x -= 26


def glow_rect(surf, rect, col, t, radius=16, width=3):
    """Pulsing selection outline."""
    import math
    a = 0.55 + 0.45 * math.sin(t * 4)
    rect = pygame.Rect(rect)
    for i, alpha in ((6, 40), (3, 90)):
        s = pygame.Surface((rect.w + i * 2, rect.h + i * 2), pygame.SRCALPHA)
        pygame.draw.rect(s, col + (int(alpha * a),), s.get_rect(), width + i, border_radius=radius + i)
        surf.blit(s, (rect.x - i, rect.y - i))
    pygame.draw.rect(surf, lighten(col, 0.25 * a), rect, width, border_radius=radius)


def scanlines(size, strength=60):
    s = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(0, size[1], 3):
        s.fill((0, 0, 0, strength), (0, y, size[0], 1))
    return s


def star(surf, col, center, r):
    """Filled five-pointed star (font-independent)."""
    import math
    cx, cy = center
    pts = [(cx + (r if i % 2 == 0 else r * 0.45) * math.cos(-math.pi / 2 + i * math.pi / 5),
            cy + (r if i % 2 == 0 else r * 0.45) * math.sin(-math.pi / 2 + i * math.pi / 5)) for i in range(10)]
    pygame.draw.polygon(surf, col, pts)


def ease(cur, target, dt, speed=14.0):
    d = target - cur
    if abs(d) < 0.001:
        return target
    return cur + d * min(1.0, dt * speed)
