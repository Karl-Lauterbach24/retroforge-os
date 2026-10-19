"""Hardware report + the console ladder ("how far does my machine go?")."""
import pygame

from ...hw import tiers
from .. import pixelfont
from .. import widgets as w
from ..theme import color, darken, lighten, mix
from .base import ListNav, Screen

LEFT = pygame.Rect(40, 132, 470, 528)
RIGHT = pygame.Rect(530, 132, 710, 528)
ROW = 34


class HardwareScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        a = self.core.assessment
        self.ladder = list(reversed(a.ladder)) if a else []
        start = self.ladder.index(a.max_console) if a and a.max_console in self.ladder else 0
        self.nav = ListNav(len(self.ladder), 12)
        self.nav.set(start)

    def handle(self, a):
        if a in ("up", "down"):
            if self.nav.move(-1 if a == "up" else 1):
                self.app.sfx("move")
            return True
        if a == "ok" and self.ladder:
            s = self.core.registry.get("system", self.ladder[self.nav.i])
            from .home import HomeScreen
            HomeScreen.compat_info(self, s)
            return True
        return False

    def update(self, dt):
        super().update(dt)
        self.nav.update(dt)

    def draw(self, surf):
        th, core = self.theme, self.core
        hw, a = core.hw, core.assessment
        w.header(surf, th, "Hardware", f"{hw.os or ''}  ·  {hw.board or hw.arch}")
        w.panel(surf, LEFT, th)
        x, y = LEFT.x + 24, LEFT.y + 20
        cap = a.cap

        def row(label, value, sub=None, frac=None, col=None):
            nonlocal y
            w.text(surf, th, label, (x, y), 14, th.c["muted"])
            w.text(surf, th, value, (x, y + 18), 19, bold=True, max_w=LEFT.w - 48)
            y += 44
            if sub:
                w.text(surf, th, sub, (x, y - 2), 14, th.c["muted"], max_w=LEFT.w - 48)
                y += 20
            if frac is not None:
                w.bar(surf, th, (x, y, LEFT.w - 48, 8), frac, col)
                y += 22

        row("Prozessor", hw.cpu_model, f"{hw.family} · {hw.cores} Kerne / {hw.threads} Threads · "
                                       f"{hw.max_mhz} MHz", min(1, cap.cpu / 7.0), th.c["accent2"])
        isa = [i.upper().replace("_", ".") for i in ("sse4_2", "avx", "avx2", "avx512f", "asimd") if i in hw.isa]
        if isa:
            xx = x
            for i in isa:
                b = w.pill(surf, th, i, (xx, y - 6), th.c["accent2"], 12)
                xx = b.right + 6
            y += 26
        row("Arbeitsspeicher", f"{cap.ram:.1f} GB", None, min(1, cap.ram / 32), th.c["accent2"])
        g = hw.gpu
        row("Grafik", g.name, f"Treiber: {g.driver or '–'}" + (f" · {g.vram_mb} MB VRAM" if g.vram_mb else ""))
        w.text(surf, th, "GPU-Klasse", (x, y), 14, th.c["muted"])
        w.segments(surf, (x, y + 20, LEFT.w - 48, 12), 5, cap.gpu, th.c["accent"], mix(th.c["muted"], th.c["bg"], 0.6))
        y += 44
        vk = f"Vulkan {hw.vulkan}" if hw.vulkan else "kein Vulkan"
        if hw.vulkan_source == "inferred":
            vk += " (geschätzt)"
        w.text(surf, th, vk + ("  ·  virtuelle Maschine" if hw.is_vm else ""), (x, y), 16, th.c["text"])
        y += 30
        playable = sum(1 for s in core.registry.all("system") if a.status(s.id) >= tiers.PLAYABLE)
        total = len(core.registry.all("system"))
        big = pixelfont.render(f"{playable}/{total}", 5, th.c["good"])
        surf.blit(big, (x, LEFT.bottom - 70))
        w.text(surf, th, "Systeme spielbar", (x + big.get_width() + 14, LEFT.bottom - 52), 17, th.c["muted"])

        # ladder
        w.panel(surf, RIGHT, th)
        w.text(surf, th, "KONSOLEN-LEITER", (RIGHT.x + 24, RIGHT.y + 16), 15, th.c["muted"], bold=True)
        top = RIGHT.y + 46
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(RIGHT.x, top, RIGHT.w, self.nav.visible * ROW))
        for i, sid in enumerate(self.ladder):
            s = core.registry.get("system", sid)
            v = a.verdicts[sid]
            yy = top + (i - self.nav.top) * ROW
            r = pygame.Rect(RIGHT.x + 12, int(yy), RIGHT.w - 24, ROW - 4)
            is_max = sid == a.max_console
            if i == self.nav.i:
                pygame.draw.rect(surf, darken(th.c["accent"], 0.35), r, border_radius=8)
            if is_max:
                pygame.draw.rect(surf, th.c["good"], r, 2, border_radius=8)
            sc = w.status_color(th, v.status)
            pygame.draw.circle(surf, color(s.color), (r.x + 16, r.centery), 6)
            w.text(surf, th, s.name, (r.x + 32, r.centery), 17, th.c["text"] if v.status >= 2 else th.c["muted"],
                   bold=is_max, anchor="midleft", max_w=250)
            w.text(surf, th, str(s.year), (r.x + 290, r.centery), 14, th.c["muted"], anchor="midleft")
            w.segments(surf, (r.x + 345, r.centery - 5, 150, 10), 4, v.status, sc, mix(th.c["muted"], th.c["bg"], 0.7))
            w.text(surf, th, ("» DEIN MAXIMUM" if is_max else v.label), (r.right - 12, r.centery), 14,
                   th.c["good"] if is_max else sc, bold=is_max, anchor="midright")
        surf.set_clip(clip)
        # reasons for the selected rung
        if self.ladder:
            sid = self.ladder[self.nav.i]
            v = a.verdicts[sid]
            y = RIGHT.bottom - 62
            pygame.draw.line(surf, mix(th.c["muted"], th.c["bg"], 0.5), (RIGHT.x + 20, y - 8), (RIGHT.right - 20, y - 8))
            text = "; ".join(v.reasons) if v.reasons else "Alle empfohlenen Anforderungen erfüllt."
            for k, line in enumerate(w.wrap(th, text, 15, RIGHT.w - 40)[:2]):
                w.text(surf, th, line, (RIGHT.x + 20, y + k * 22), 15, th.c["muted"])

    def hints(self):
        return [("updown", "Konsole"), ("ok", "Details"), ("back", "Zurück")]
