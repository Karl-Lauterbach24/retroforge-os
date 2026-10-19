"""Settings for any scope (global / system / game), generated from the
registry's SettingDefs – plugin settings appear here automatically."""
import pygame

from ...settings import GAME, GLOBAL, SYSTEM
from .. import widgets as w
from ..theme import darken, lighten, mix
from .base import ListNav, Screen

CAT = pygame.Rect(40, 132, 300, 528)
OPT = pygame.Rect(360, 132, 880, 528)
ROW_H = 50
SOURCE_LABEL = {"game": "Spiel", "system": "System", "global": "Global", "default": "Standard"}
LIVE_KEYS = {"ui.theme", "ui.crt_overlay"}
AUDIO_KEYS = {"audio.music_mode", "audio.music_volume", "audio.sound_pack", "audio.sfx_volume"}


class SettingsScreen(Screen):
    def __init__(self, app, scope=GLOBAL, target=None, system=None):
        super().__init__(app)
        self.scope = scope
        self.target = target
        self.system = target if scope == SYSTEM else system
        self.game = target if scope == GAME else None
        self.focus = 0     # 0 categories, 1 options
        self.build()
        self.cnav = ListNav(len(self.cats), CAT.h // 48)
        self.onav = ListNav(0, OPT.h // ROW_H - 1)
        self.sync_options()

    def build(self):
        defs = [d for d in self.core.settings.definitions(self.scope)
                if d.visible is None or d.visible(self.core, self.system, self.game)]
        cats = []
        for d in sorted(defs, key=lambda d: d.order):
            if d.category not in cats:
                cats.append(d.category)
        self.defs = defs
        self.cats = cats + ["Aktionen"]

    def actions(self):
        core, app = self.core, self.app
        if self.scope == GLOBAL:
            return [("Empfohlene Filter für alle Systeme setzen", lambda: app.confirm(
                        "Empfohlene Filter?",
                        "Setzt pro System passende Filter und Upscaling für deine GPU-Klasse.",
                        lambda: (core.apply_recommended_filters(), app.toast("Filter-Profile gesetzt", "good")))),
                    ("Musik-Cache leeren (Theme-Musik neu erzeugen)", self.clear_music),
                    ("Hardware neu erkennen", lambda: app.progress("Hardware wird erkannt",
                                                                    lambda p: core.probe(),
                                                                    lambda r, e: app.toast("Hardware aktualisiert")))]
        label = "System" if self.scope == SYSTEM else "Spiel"
        return [(f"Alle {label}-Einstellungen zurücksetzen", self.reset_all)]

    def clear_music(self):
        for p in self.core.paths.cache.glob("music-*.wav"):
            try:
                p.unlink()
            except OSError:
                pass
        self.app.audio.start_music(self.app.theme)
        self.app.toast("Musik wird neu erzeugt …")

    def reset_all(self):
        for k in list(self.core.settings.overrides(self.scope, self.target)):
            self.core.settings.unset(k, self.scope, self.target, save=False)
        self.core.settings.save()
        self.app.toast("Zurückgesetzt", "good")

    @property
    def cat(self):
        return self.cats[self.cnav.i]

    def items(self):
        if self.cat == "Aktionen":
            return [("action", a) for a in self.actions()]
        return [("def", d) for d in self.defs if d.category == self.cat]

    def sync_options(self):
        self.onav.n = len(self.items())
        self.onav.set(0)

    # -- values -----------------------------------------------------------------
    def resolve(self, d):
        return self.core.settings.resolve(d.key, self.system, self.game)

    def change(self, d, step):
        core = self.core
        choices = d.choice_list(core, self.system, self.game)
        if not choices:
            return
        cur = self.resolve(d).value
        values = [c[0] for c in choices]
        i = values.index(cur) if cur in values else 0
        i = (i + step) % len(values) if d.type != "range" else max(0, min(len(values) - 1, i + step))
        core.settings.set(d.key, values[i], self.scope, self.target)
        self.after_change(d.key)
        self.app.sfx("toggle")

    def after_change(self, key):
        app = self.app
        if key in LIVE_KEYS:
            app.apply_theme()
        elif key in AUDIO_KEYS:
            if key in ("audio.music_mode",):
                app.audio.start_music(app.theme)
            elif key == "audio.sound_pack":
                app.audio.load_pack(app.theme)
            else:
                app.audio.apply_volume()

    # -- input -----------------------------------------------------------------
    def handle(self, a):
        if self.focus == 0:
            if a in ("up", "down"):
                if self.cnav.move(-1 if a == "up" else 1):
                    self.sync_options()
                    self.app.sfx("move")
                return True
            if a in ("ok", "right"):
                self.focus = 1
                self.app.sfx("select")
                return True
            return False
        kind, item = self.items()[self.onav.i] if self.items() else (None, None)
        if a in ("up", "down"):
            if self.onav.move(-1 if a == "up" else 1):
                self.app.sfx("move")
            return True
        if a == "back":
            self.focus = 0
            self.app.sfx("back")
            return True
        if kind == "action":
            if a == "ok":
                self.app.sfx("select")
                item[1]()
            return True
        if kind == "def":
            if a in ("left", "right"):
                self.change(item, -1 if a == "left" else 1)
                return True
            if a == "ok":
                self.change(item, 1)
                return True
            if a == "x" and self.scope != GLOBAL:
                self.core.settings.unset(item.key, self.scope, self.target)
                self.after_change(item.key)
                self.app.sfx("back")
                return True
        return True

    # -- drawing ----------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        self.cnav.update(dt)
        self.onav.update(dt)

    def title(self):
        if self.scope == SYSTEM:
            s = self.core.registry.get("system", self.target)
            return "Einstellungen", f"System: {s.name if s else self.target} – überschreibt die globalen Werte"
        if self.scope == GAME:
            g = self.core.library.get(self.target)
            return "Einstellungen", f"Spiel: {g.name if g else self.target} – überschreibt System und Global"
        return "Einstellungen", "Global – gilt für alle Systeme, sofern nicht überschrieben"

    def draw(self, surf):
        th = self.theme
        t, sub = self.title()
        w.header(surf, th, t, sub)
        # categories
        w.panel(surf, CAT, th)
        for i, c in enumerate(self.cats):
            r = pygame.Rect(CAT.x + 10, CAT.y + 10 + i * 48, CAT.w - 20, 42)
            sel = i == self.cnav.i
            if sel:
                col = th.c["accent"] if self.focus == 0 else darken(th.c["accent"], 0.45)
                pygame.draw.rect(surf, col, r, border_radius=10)
            w.text(surf, th, c, (r.x + 16, r.centery), 19,
                   darken(th.c["accent"], 0.8) if sel and self.focus == 0 else th.c["text"],
                   bold=sel, anchor="midleft")
        # options
        w.panel(surf, OPT, th)
        items = self.items()
        clip = surf.get_clip()
        list_area = pygame.Rect(OPT.x, OPT.y + 8, OPT.w, OPT.h - 90)
        surf.set_clip(list_area)
        for i, (kind, item) in enumerate(items):
            y = OPT.y + 12 + (i - self.onav.top) * ROW_H
            r = pygame.Rect(OPT.x + 12, int(y), OPT.w - 24, ROW_H - 6)
            sel = self.focus == 1 and i == self.onav.i
            if sel:
                pygame.draw.rect(surf, darken(th.c["accent"], 0.3), r, border_radius=10)
                pygame.draw.rect(surf, th.c["accent"], (r.x, r.y + 8, 4, r.h - 16), border_radius=2)
            if kind == "action":
                w.text(surf, th, item[0], (r.x + 20, r.centery), 19, th.c["accent2"], anchor="midleft")
                continue
            d = item
            res = self.resolve(d)
            own = res.source == self.scope
            label_col = th.c["text"] if own or self.scope == GLOBAL else th.c["muted"]
            w.text(surf, th, d.label, (r.x + 20, r.centery), 19, label_col, anchor="midleft", max_w=430)
            val = d.label_for(res.value, self.core, self.system, self.game)
            vx = r.right - 20
            if sel:
                w.text(surf, th, "›", (vx, r.centery - 2), 26, th.c["accent"], anchor="midright")
                vx -= 22
            if d.type == "range":
                br = pygame.Rect(vx - 160, r.centery - 5, 160, 10)
                w.bar(surf, th, br, (res.value or 0) / max(1, d.max), th.c["accent2"] if own else th.c["muted"])
                vx = br.x - 14
            vimg = w.text(surf, th, val, (vx, r.centery), 19, th.c["text"] if own or self.scope == GLOBAL
                          else th.c["muted"], bold=own, anchor="midright", max_w=320)
            if sel:
                w.text(surf, th, "‹", (vimg.x - 10, r.centery - 2), 26, th.c["accent"], anchor="midright")
            if self.scope != GLOBAL:
                tag = "eigener Wert" if own else f"erbt von {SOURCE_LABEL[res.source]}"
                w.pill(surf, th, tag, (r.x + 460, r.centery), th.c["accent2"] if own else th.c["off"], 12,
                       anchor="midleft")
        surf.set_clip(clip)
        # help
        if self.focus == 1 and items:
            kind, item = items[self.onav.i]
            text = getattr(item, "help", "") if kind == "def" else ""
            if kind == "def" and item.origin not in ("core", ""):
                text = (text + "  " if text else "") + f"(Plugin: {item.origin})"
            if text:
                y = OPT.bottom - 70
                pygame.draw.line(surf, mix(th.c["muted"], th.c["bg"], 0.5), (OPT.x + 20, y - 8), (OPT.right - 20, y - 8))
                for i, line in enumerate(w.wrap(th, text, 16, OPT.w - 40)[:2]):
                    w.text(surf, th, line, (OPT.x + 20, y + i * 24), 16, th.c["muted"])

    def hints(self):
        if self.focus == 0:
            return [("updown", "Kategorie"), ("ok", "Öffnen"), ("back", "Zurück")]
        h = [("leftright", "Ändern")]
        if self.scope != GLOBAL:
            h.append(("x", "Erben"))
        return h + [("back", "Kategorien")]
