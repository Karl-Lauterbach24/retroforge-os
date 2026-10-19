"""Procedural icons (no image assets).

Icons are drawn as solid silhouettes with transparent cut-outs (d-pad,
buttons, screens), like glyphs of an icon font. They are rendered at 4×
size and smooth-scaled down, which gives anti-aliased edges with the plain
pygame drawing primitives. Results are cached per (kind, colour, scale).
"""
import math

import pygame

SS = 4               # supersampling factor


class Pen:
    """Draws in icon units (≈ 120 × 90 box around the centre) scaled by k."""

    def __init__(self, s, col, cx, cy, k):
        self.s, self.col, self.cx, self.cy, self.k = s, col, cx, cy, k
        # drawing with alpha 0 punches a hole; keeping the ink's RGB avoids dark
        # fringes when the supersampled surface is smooth-scaled down
        self.cut = tuple(col[:3]) + (0,)

    def p(self, x, y):
        return (self.cx + x * self.k, self.cy + y * self.k)

    def rect(self, x, y, w, h, r=0, cut=False, **corners):
        rr = {k: int(v * self.k) for k, v in corners.items()}
        pygame.draw.rect(self.s, self.cut if cut else self.col,
                         pygame.Rect(round(self.cx + x * self.k), round(self.cy + y * self.k),
                                     round(w * self.k), round(h * self.k)),
                         border_radius=int(r * self.k), **rr)

    def circle(self, x, y, r, cut=False, width=0):
        pygame.draw.circle(self.s, self.cut if cut else self.col, self.p(x, y), r * self.k,
                           int(width * self.k) if width else 0)

    def poly(self, pts, cut=False):
        pygame.draw.polygon(self.s, self.cut if cut else self.col, [self.p(x, y) for x, y in pts])

    def ellipse(self, x, y, rx, ry, angle=0, cut=False):
        t = math.radians(angle)
        pts = [(x + rx * math.cos(u) * math.cos(t) - ry * math.sin(u) * math.sin(t),
                y + rx * math.cos(u) * math.sin(t) + ry * math.sin(u) * math.cos(t))
               for u in (i * math.tau / 48 for i in range(48))]
        self.poly(pts, cut)

    def line(self, a, b, w, cut=False):
        pygame.draw.line(self.s, self.cut if cut else self.col, self.p(*a), self.p(*b), max(1, int(w * self.k)))

    def dpad(self, x, y, size, arm, cut=True):
        h = size / 2
        self.rect(x - h, y - arm / 2, size, arm, arm * 0.25, cut)
        self.rect(x - arm / 2, y - h, arm, size, arm * 0.25, cut)

    def diamond(self, x, y, off, r, cut=True):
        for dx, dy in ((0, -off), (off, 0), (0, off), (-off, 0)):
            self.circle(x + dx, y + dy, r, cut)

    def stick(self, x, y, r):
        self.circle(x, y, r, True)
        self.circle(x, y, r * 0.62)


# --- controllers ----------------------------------------------------------------
def pad_nes(P):
    """Rectangular 8-bit pad (NES, Master System, Atari 7800 …)."""
    P.rect(-58, -26, 116, 52, 7)
    P.rect(-52, -20, 104, 40, 4, cut=True)          # inset face plate
    P.rect(-49, -17, 98, 34, 3)
    P.dpad(-32, 0, 26, 8)
    P.rect(-12, 3, 9, 4, 2, cut=True)               # select
    P.rect(3, 3, 9, 4, 2, cut=True)                 # start
    P.circle(24, 3, 7, cut=True)                    # B
    P.circle(40, 3, 7, cut=True)                    # A


def pad_snes(P):
    """'Dog bone' 16-bit pad (SNES, PC Engine, Mega Drive era)."""
    P.rect(-44, -36, 30, 14, 6)                     # L shoulder
    P.rect(14, -36, 30, 14, 6)                      # R shoulder
    P.rect(-48, -27, 96, 6, cut=True)               # gap between shoulders and body
    P.circle(-34, 0, 29)
    P.circle(34, 0, 29)
    P.rect(-34, -24, 68, 46)
    P.dpad(-34, 0, 26, 9)
    P.diamond(34, 0, 11, 6)
    P.rect(-11, 1, 9, 4, 2, cut=True)
    P.rect(3, 1, 9, 4, 2, cut=True)


def pad_n64(P):
    """Three-pronged 64-bit pad."""
    P.rect(-58, -30, 116, 30, 15)
    P.rect(-58, -24, 26, 52, 13)                    # left prong
    P.rect(32, -24, 26, 52, 13)                     # right prong
    P.rect(-12, -14, 24, 50, 12)                    # centre prong
    P.dpad(-42, -13, 18, 6)
    P.circle(0, -18, 3.5, cut=True)                 # start
    P.diamond(44, -16, 6, 3)                        # C buttons
    P.circle(24, -10, 5, cut=True)                  # B
    P.circle(32, -2, 5, cut=True)                   # A
    P.stick(0, 8, 7)


def pad_modern(P):
    """Twin-stick pad (PlayStation / Xbox / Switch Pro era)."""
    P.rect(-48, -40, 30, 10, 5)                     # bumpers
    P.rect(18, -40, 30, 10, 5)
    P.rect(-52, -33, 104, 5, cut=True)
    P.rect(-54, -30, 108, 40, 16)                   # body
    P.ellipse(-37, 12, 17, 26, -28)                 # grips, tilted outwards
    P.ellipse(37, 12, 17, 26, 28)
    P.dpad(-34, -12, 20, 7)
    P.diamond(34, -12, 8.5, 4.2)
    P.rect(-11, -20, 8, 4, 2, cut=True)             # select / view
    P.rect(3, -20, 8, 4, 2, cut=True)               # start / menu
    P.stick(-16, 10, 9)
    P.stick(16, 10, 9)


# --- other device kinds ---------------------------------------------------------
def handheld(P):
    P.rect(-36, -56, 72, 112, 8, border_bottom_right_radius=26)
    P.rect(-28, -48, 56, 44, 4, cut=True)           # screen bezel
    P.rect(-22, -43, 44, 34, 2)                     # screen
    P.circle(-22, -36, 2.4, cut=True)               # power LED
    P.dpad(-16, 18, 20, 7)
    P.circle(24, 12, 6, cut=True)
    P.circle(12, 20, 6, cut=True)
    for i in range(4):                              # speaker grille
        P.line((14 + i * 6, 46), (22 + i * 6, 38), 2.4, cut=True)
    P.rect(-12, 36, 8, 3.5, 2, cut=True)
    P.rect(0, 36, 8, 3.5, 2, cut=True)


def arcade(P):
    P.poly([(-62, 6), (62, 6), (54, 40), (-54, 40)])  # control panel
    P.rect(-30, -44, 7, 46, 3)                      # stick shaft
    P.circle(-27, -44, 13)                          # ball top
    P.circle(-31, -48, 4, cut=True)                 # highlight
    P.circle(-27, 6, 9)                             # dust washer
    for i in range(3):
        for j in range(2):
            P.circle(6 + i * 18, 17 + j * 13 - i * 2, 6, cut=True)


def computer(P):
    P.rect(-48, -46, 96, 64, 7)
    P.rect(-40, -38, 80, 48, 3, cut=True)
    for i in range(4):                              # text lines on screen
        P.rect(-34, -32 + i * 10, 22 + (i * 23) % 40, 5, 2)
    P.rect(-10, 18, 20, 8)
    P.rect(-58, 30, 116, 18, 5)
    for row in range(2):
        for col in range(9):
            P.rect(-53 + col * 12, 33 + row * 7, 9, 4.5, 1.5, cut=True)


def heart(P):
    rows = ["01100110", "11111111", "11111111", "11111111", "01111110", "00111100", "00011000"]
    px = 12
    for y, row in enumerate(rows):
        for x, b in enumerate(row):
            if b == "1":
                P.rect(-48 + x * px, -42 + y * px, px - 1, px - 1)


def star(P):
    pts = []
    for i in range(10):
        r = 54 if i % 2 == 0 else 22
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((r * math.cos(a), 4 + r * math.sin(a)))
    P.poly(pts)


def clock(P):
    P.circle(0, 0, 48)
    P.circle(0, 0, 40, cut=True)
    P.line((0, 0), (0, -28), 6)
    P.line((0, 0), (20, 8), 6)
    P.circle(0, 0, 5)
    for i in range(12):
        a = i * math.pi / 6
        P.circle(34 * math.cos(a), 34 * math.sin(a), 2)


def chart(P):
    for i, h in enumerate((30, 55, 42, 80)):
        P.rect(-54 + i * 30, 40 - h, 20, h, 3)


ICONS = {"pad_nes": pad_nes, "pad_snes": pad_snes, "pad_n64": pad_n64, "pad_modern": pad_modern,
         "console": pad_modern, "handheld": handheld, "arcade": arcade, "computer": computer,
         "fantasy": heart, "favorites": star, "recent": clock, "chart": chart}


def for_system(system):
    """Icon kind for a system: explicit ``icon`` field, else by kind and era."""
    if getattr(system, "icon", ""):
        return system.icon
    if system.kind != "console":
        return system.kind
    if system.year < 1988:
        return "pad_nes"
    if system.year < 1996:
        return "pad_snes"
    return "pad_modern"


_cache = {}
BOX = (180, 130)


def render(kind, col, k=1.0):
    """Anti-aliased icon surface (BOX × k), centred on its box."""
    key = (kind, tuple(col), k)
    surf = _cache.get(key)
    if surf is not None:
        return surf
    w, h = int(BOX[0] * k), int(BOX[1] * k)
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    big.fill(tuple(col[:3]) + (0,))
    ICONS.get(kind, pad_modern)(Pen(big, col, w * SS / 2, h * SS / 2, k * SS))
    surf = pygame.transform.smoothscale(big, (w, h))
    if len(_cache) > 200:
        _cache.clear()
    _cache[key] = surf
    return surf


def draw(kind, s, col, cx, cy, k=1.0):
    img = render(kind, col, k)
    s.blit(img, img.get_rect(center=(int(cx), int(cy))))
