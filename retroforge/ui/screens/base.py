"""Screen base class and the generic dialogs (menu, confirm, info, progress)."""
import threading

import pygame

from .. import widgets as w
from ..theme import darken, lighten


class Screen:
    transparent = False        # draw the screen below (dialogs/overlays)
    animating = False          # forces redraw in power-saving mode

    def __init__(self, app):
        self.app = app
        self.core = app.core
        self.t = 0.0

    @property
    def theme(self):
        return self.app.theme

    def on_enter(self):
        pass

    def on_resume(self):
        pass

    def handle(self, action):
        return False

    def text_input(self, s):
        pass

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        pass

    def hints(self):
        return [("back", "Zurück")]


class ListNav:
    """Index + smooth scroll helper for vertical lists."""

    def __init__(self, n=0, visible=10):
        self.n, self.visible = n, visible
        self.i = 0
        self.top = 0.0
        self.top_target = 0

    def move(self, d, wrap=True):
        if not self.n:
            return False
        old = self.i
        if wrap and abs(d) == 1:
            self.i = (self.i + d) % self.n
        else:
            self.i = max(0, min(self.n - 1, self.i + d))
        self._fix()
        return self.i != old

    def set(self, i):
        self.i = max(0, min(max(0, self.n - 1), i))
        self._fix()

    def _fix(self):
        if self.i < self.top_target:
            self.top_target = self.i
        elif self.i >= self.top_target + self.visible:
            self.top_target = self.i - self.visible + 1
        self.top_target = max(0, min(self.top_target, max(0, self.n - self.visible)))

    def update(self, dt):
        self.top = w.ease(self.top, self.top_target, dt, 16)


# ---------------------------------------------------------------------------
class Dialog(Screen):
    transparent = True
    width = 620

    def __init__(self, app, title):
        super().__init__(app)
        self.title = title
        self.appear = 0.0

    def update(self, dt):
        super().update(dt)
        self.appear = min(1.0, self.appear + dt * 7)

    def frame(self, surf, height):
        dim = pygame.Surface((w.W, w.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(150 * self.appear)))
        surf.blit(dim, (0, 0))
        k = 0.92 + 0.08 * self.appear
        rw, rh = int(self.width * k), int(height * k)
        rect = pygame.Rect((w.W - rw) // 2, (w.H - rh) // 2, rw, rh)
        w.panel(surf, rect, self.theme, self.theme.c["panel2"], border=self.theme.c["accent"])
        w.text(surf, self.theme, self.title, (rect.x + 28, rect.y + 20), 24, bold=True, max_w=rw - 56)
        return rect


class MenuDialog(Dialog):
    """items: [(label, callback)] or [(label, callback, enabled)]; callback(app) or None."""

    def __init__(self, app, title, items, subtitle=None, warn=False):
        super().__init__(app, title)
        self.items = [(it[0], it[1], it[2] if len(it) > 2 else True) for it in items]
        self.subtitle = subtitle
        self.warn = warn                       # subtitle is a warning (legal notice, data loss …)
        if subtitle and len(str(subtitle)) > 70:
            self.width = 820
        self.nav = ListNav(len(self.items), 9)
        while self.items and not self.items[self.nav.i][2] and self.nav.i < len(self.items) - 1:
            self.nav.i += 1

    def handle(self, a):
        if a in ("up", "down"):
            for _ in range(len(self.items)):
                self.nav.move(-1 if a == "up" else 1)
                if self.items[self.nav.i][2]:
                    break
            self.app.sfx("move")
            return True
        if a == "ok" and self.items:
            label, cb, enabled = self.items[self.nav.i]
            if not enabled:
                self.app.sfx("error")
                return True
            self.app.sfx("select")
            self.app.pop(self)
            if cb:
                cb(self.app)
            return True
        return False

    def update(self, dt):
        super().update(dt)
        self.nav.update(dt)

    def sub_lines(self):
        """Subtitle wrapped to the dialog width; paragraphs separated by newlines."""
        if not self.subtitle:
            return []
        out = []
        for para in str(self.subtitle).split("\n"):
            out += w.wrap(self.theme, para, 16, self.width - 56) or [""]
        return out[:10]

    def draw(self, surf):
        rows = min(len(self.items), 9)
        lines = self.sub_lines()
        sub_h = len(lines) * 22 + 10 if lines else 0
        rect = self.frame(surf, 90 + sub_h + rows * 46)
        th = self.theme
        y0 = rect.y + 64
        if lines:
            col = th.c["warn"] if self.warn else th.c["muted"]
            for k, line in enumerate(lines):
                w.text(surf, th, line, (rect.x + 28, y0 - 4 + k * 22), 16, col)
            y0 += sub_h
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(rect.x, y0, rect.w, rows * 46))
        for i, (label, cb, enabled) in enumerate(self.items):
            y = y0 + (i - self.nav.top) * 46
            r = pygame.Rect(rect.x + 16, int(y), rect.w - 32, 40)
            if i == self.nav.i:
                pygame.draw.rect(surf, darken(th.c["accent"], 0.35), r, border_radius=10)
                pygame.draw.rect(surf, th.c["accent"], (r.x, r.y + 8, 4, r.h - 16), border_radius=2)
            col = th.c["text"] if enabled else th.c["off"]
            w.text(surf, th, label, (r.x + 18, r.centery), 20, col, anchor="midleft", max_w=r.w - 36)
        surf.set_clip(clip)

    def hints(self):
        return [("ok", "Auswählen"), ("back", "Abbrechen")]


class ConfirmDialog(MenuDialog):
    def __init__(self, app, title, text, on_yes, yes="Ja", no="Abbrechen", warn=False):
        super().__init__(app, title, [(yes, lambda a: on_yes()), (no, None)], subtitle=text, warn=warn)


class InfoDialog(Dialog):
    width = 900

    def __init__(self, app, title, lines, mono=False):
        super().__init__(app, title)
        self.raw = lines if isinstance(lines, list) else str(lines).splitlines()
        self.lines = []
        for ln in self.raw:
            self.lines += w.wrap(app.theme, ln, 17, self.width - 70) or [""]
        self.nav = ListNav(max(1, len(self.lines)), 14)

    def handle(self, a):
        if a in ("up", "down"):
            self.nav.top_target = max(0, min(max(0, len(self.lines) - 14),
                                             self.nav.top_target + (-1 if a == "up" else 1)))
            return True
        if a in ("ok",):
            self.app.pop(self)
            return True
        return False

    def update(self, dt):
        super().update(dt)
        self.nav.update(dt)

    def draw(self, surf):
        rows = min(14, len(self.lines))
        rect = self.frame(surf, 100 + rows * 26)
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(rect.x, rect.y + 60, rect.w, rows * 26 + 4))
        for i, ln in enumerate(self.lines):
            y = rect.y + 64 + (i - self.nav.top) * 26
            w.text(surf, self.theme, ln, (rect.x + 30, int(y)), 17, self.theme.c["text"])
        surf.set_clip(clip)

    def hints(self):
        return [("updown", "Blättern"), ("ok", "OK")]


class ProgressDialog(Dialog):
    """Runs ``work(progress)`` in a thread; progress(fraction, text)."""

    animating = True

    def __init__(self, app, title, work, done=None):
        super().__init__(app, title)
        self.frac, self.msg, self.result, self.error = 0.0, "", None, None
        self.done_cb = done
        self.finished = False

        def run():
            try:
                self.result = work(self._progress)
            except Exception as e:
                self.error = e
            self.finished = True
        threading.Thread(target=run, daemon=True, name="progress").start()

    def _progress(self, frac, msg=""):
        self.frac, self.msg = frac, msg or self.msg

    def update(self, dt):
        super().update(dt)
        if self.finished:
            self.app.pop(self)
            if self.done_cb:
                self.done_cb(self.result, self.error)

    def handle(self, a):
        return True   # modal

    def draw(self, surf):
        rect = self.frame(surf, 170)
        w.text(surf, self.theme, self.msg, (rect.x + 28, rect.y + 66), 17, self.theme.c["muted"], max_w=rect.w - 56)
        br = pygame.Rect(rect.x + 28, rect.y + 104, rect.w - 56, 18)
        if self.frac > 0:
            w.bar(surf, self.theme, br, self.frac)
        else:   # indeterminate: moving block
            w.bar(surf, self.theme, br, 0)
            x = br.x + int((self.t * 0.6 % 1) * (br.w - 120))
            pygame.draw.rect(surf, self.theme.c["accent"], (x, br.y, 120, br.h), border_radius=9)

    def hints(self):
        return []
