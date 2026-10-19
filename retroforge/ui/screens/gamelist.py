"""Game list with details panel, type-to-search and per-game options."""
import os
import time

import pygame

from ...hw import tiers
from .. import pixelfont
from .. import widgets as w
from ..theme import color, darken, lighten, mix
from .base import ListNav, Screen

ROW_H = 44
LIST = pygame.Rect(40, 132, 600, 528)
DETAIL = pygame.Rect(664, 132, 576, 528)
ART_DIRS = ("images", "media/images", "media/covers", "boxart", "covers")


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def ago(ts):
    if not ts:
        return "nie"
    d = time.time() - ts
    if d < 3600:
        return "gerade eben" if d < 120 else f"vor {int(d // 60)} min"
    if d < 86400:
        return f"vor {int(d // 3600)} h"
    if d < 86400 * 30:
        return f"vor {int(d // 86400)} Tagen"
    return time.strftime("%d.%m.%Y", time.localtime(ts))


def fmt_time(secs):
    secs = int(secs or 0)
    return f"{secs // 3600} h {secs % 3600 // 60:02d} min" if secs >= 3600 else f"{secs // 60} min"


class GameListScreen(Screen):
    def __init__(self, app, system=None, collection=None):
        super().__init__(app)
        self.system = system
        self.coll = collection
        self.query = ""
        self.games = []
        self.nav = ListNav(0, LIST.h // ROW_H)
        self.art_cache = {}
        self.reload()

    @property
    def title(self):
        if self.coll:
            return self.coll.name
        s = self.core.registry.get("system", self.system)
        return s.name if s else self.system

    def reload(self, keep=None):
        core = self.core
        if self.coll:
            games = list(self.coll.query(core))
        else:
            games = core.library.sorted_games(self.system, core.settings.get("ui.sort", self.system, default="name"))
        if self.query:
            q = self.query.lower()
            games = [g for g in games if q in g.name.lower()]
        self.games = games
        self.nav.n = len(games)
        if keep:
            idx = next((i for i, g in enumerate(games) if g.key == keep), 0)
            self.nav.set(idx)
        else:
            self.nav.set(min(self.nav.i, max(0, len(games) - 1)))

    def current(self):
        return self.games[self.nav.i] if self.games else None

    def on_resume(self):
        g = self.current()
        self.reload(keep=g.key if g else None)

    # -- input -----------------------------------------------------------------
    def handle(self, a):
        g = self.current()
        if a in ("up", "down"):
            if self.nav.move(-1 if a == "up" else 1):
                self.app.sfx("move")
            return True
        if a in ("l1", "r1", "left", "right"):
            step = self.nav.visible if a in ("l1", "r1") else 1
            if a in ("left", "right") and g:   # jump to next/previous letter
                self.jump_letter(1 if a == "right" else -1)
            else:
                self.nav.move(step if a == "r1" else -step, wrap=False)
            self.app.sfx("move")
            return True
        if a == "back" and self.query:
            self.query = ""
            self.reload()
            return True
        if not g:
            return False
        if a == "ok":
            self.app.launch(g)
            return True
        if a == "y":
            fav = self.core.gamedata.toggle_favorite(g.key)
            self.app.sfx("toggle")
            self.app.toast(("Favorit: " if fav else "Entfernt: ") + g.name, "good" if fav else "info")
            return True
        if a == "x":
            self.game_menu(g)
            return True
        return False

    def jump_letter(self, d):
        if not self.games:
            return
        cur = self.games[self.nav.i].name[:1].upper()
        n = len(self.games)
        i = self.nav.i
        for _ in range(n):
            i = (i + d) % n
            if self.games[i].name[:1].upper() != cur:
                if d < 0:   # go to the first game of that letter
                    letter = self.games[i].name[:1].upper()
                    while i > 0 and self.games[i - 1].name[:1].upper() == letter:
                        i -= 1
                self.nav.set(i)
                return

    def text_input(self, s):
        if s.isprintable():
            self.query += s
            self.reload()

    def game_menu(self, g):
        core, app = self.core, self.app
        sysdef = core.registry.get("system", g.system)
        emus = [core.registry.get("emulator", e) for e in (sysdef.emulators if sysdef else ())]
        fav = core.gamedata.is_favorite(g.key)

        def start_with(a):
            items = []
            for e in emus:
                if not e:
                    continue
                v = tiers.evaluate_emulator(e, core.assessment.cap)
                inst = "" if core.emus.installed(e) else " · nicht installiert"
                items.append((f"{e.name}  ({v.label}{inst})", lambda a, e=e: a.launch(g, e.id)))
            a.menu("Starten mit …", items)

        def show_cmd(a):
            plan = core.launcher.plan(g)
            a.info("Startbefehl", [plan.describe(), ""] + [f"Hinweis: {n}" for n in plan.notes])

        items = [("Starten", lambda a: a.launch(g)),
                 ("Starten mit …", start_with),
                 ("Aus Favoriten entfernen" if fav else "Zu Favoriten hinzufügen",
                  lambda a: (core.gamedata.toggle_favorite(g.key), a.sfx("toggle"))),
                 ("Einstellungen für dieses Spiel", lambda a: a.push("settings", scope="game", target=g.key,
                                                                     system=g.system)),
                 ("Einstellungen für das System", lambda a: a.push("settings", scope="system", target=g.system)),
                 ("Startbefehl anzeigen", show_cmd)]
        for extra in core.registry.emit("ui.game_menu", game=g, core=core):
            items += extra
        app.sfx("select")
        app.menu(g.name, items)

    # -- drawing ----------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        self.nav.update(dt)

    def art(self, g):
        if g.key in self.art_cache:
            return self.art_cache[g.key]
        img = None
        root = self.core.paths.system_roms(g.system)
        for d in ART_DIRS:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = root / d / (g.stem + ext)
                if p.is_file():
                    try:
                        img = pygame.image.load(str(p)).convert_alpha()
                        k = min(250 / img.get_height(), (DETAIL.w - 60) / img.get_width())
                        img = pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))
                    except pygame.error:
                        img = None
                    break
            if img:
                break
        if len(self.art_cache) > 60:
            self.art_cache.clear()
        self.art_cache[g.key] = img
        return img

    def draw(self, surf):
        th = self.theme
        count = f"{len(self.games)} Spiele"
        if self.query:
            count = f"Suche „{self.query}“ · {count}"
        w.header(surf, th, self.title, count, right=None)
        self.draw_list(surf)
        self.draw_details(surf)

    def draw_list(self, surf):
        th, core = self.theme, self.core
        w.panel(surf, LIST, th)
        if not self.games:
            w.text(surf, th, "Keine Treffer" if self.query else "Keine Spiele", LIST.center, 20, th.c["muted"],
                   anchor="center")
            return
        clip = surf.get_clip()
        surf.set_clip(LIST.inflate(-8, -8))
        first = int(self.nav.top)
        for i in range(first, min(len(self.games), first + self.nav.visible + 2)):
            g = self.games[i]
            y = LIST.y + 4 + (i - self.nav.top) * ROW_H
            r = pygame.Rect(LIST.x + 8, int(y), LIST.w - 16, ROW_H - 4)
            sel = i == self.nav.i
            if sel:
                pygame.draw.rect(surf, darken(th.c["accent"], 0.3), r, border_radius=10)
                pygame.draw.rect(surf, th.c["accent"], (r.x, r.y + 8, 4, r.h - 16), border_radius=2)
            x = r.x + 16
            if core.gamedata.is_favorite(g.key):
                w.star(surf, th.c["warn"], (x + 7, r.centery), 9)
            x += 22
            right = r.right - 12
            if g.region:
                b = w.pill(surf, th, g.region, (right, r.centery), th.c["muted"], 12, anchor="midright")
                right = b.x - 6
            if core.settings.overrides("game", g.key):
                b = w.pill(surf, th, "EIGEN", (right, r.centery), th.c["accent2"], 12, anchor="midright")
                right = b.x - 6
            if self.coll:
                s = core.registry.get("system", g.system)
                b = w.pill(surf, th, s.short if s else g.system, (right, r.centery),
                           mix(color(s.color), (255, 255, 255), 0.45) if s else th.c["muted"], 12, anchor="midright")
                right = b.x - 6
            w.text(surf, th, g.name, (x, r.centery), 19, th.c["text"] if sel else lighten(th.c["muted"], 0.3),
                   bold=sel, anchor="midleft", max_w=right - x - 8)
        surf.set_clip(clip)
        # scrollbar
        if len(self.games) > self.nav.visible:
            frac = self.nav.visible / len(self.games)
            h = max(30, int((LIST.h - 20) * frac))
            y = LIST.y + 10 + int((LIST.h - 20 - h) * (self.nav.top / max(1, len(self.games) - self.nav.visible)))
            pygame.draw.rect(surf, mix(th.c["muted"], th.c["bg"], 0.4), (LIST.right - 6, y, 3, h), border_radius=2)

    def draw_details(self, surf):
        th, core = self.theme, self.core
        w.panel(surf, DETAIL, th)
        g = self.current()
        if not g:
            return
        sysdef = core.registry.get("system", g.system)
        base = color(sysdef.color) if sysdef else th.c["accent"]
        art_rect = pygame.Rect(DETAIL.x + 24, DETAIL.y + 22, DETAIL.w - 48, 200)
        img = self.art(g)
        if img:
            surf.blit(img, img.get_rect(center=art_rect.center))
        else:
            pygame.draw.rect(surf, darken(base, 0.35), art_rect, border_radius=14)
            clip = surf.get_clip()
            surf.set_clip(art_rect.inflate(-8, -8))
            for k in range(-60, art_rect.w, 18):
                pygame.draw.line(surf, darken(base, 0.25), (art_rect.x + k, art_rect.bottom - 1),
                                 (art_rect.x + k + 60, art_rect.y), 6)
            surf.set_clip(clip)
            initials = "".join(p[0] for p in g.name.split()[:3] if p[:1].isalnum()) or "?"
            pi = pixelfont.render(initials, 9, lighten(base, 0.5), darken(base, 0.7))
            surf.blit(pi, pi.get_rect(center=art_rect.center))
            if sysdef:
                ps = pixelfont.render(sysdef.short, 2, lighten(base, 0.6))
                surf.blit(ps, (art_rect.x + 14, art_rect.y + 12))
        y = art_rect.bottom + 18
        for line in w.wrap(th, g.name, 26, DETAIL.w - 48, True)[:2]:
            w.text(surf, th, line, (DETAIL.x + 24, y), 26, bold=True)
            y += 34
        gd = core.gamedata
        rows = [("System", sysdef.name if sysdef else g.system)]
        if g.region:
            rows.append(("Region", g.region))
        if g.size:
            rows.append(("Größe", human_size(g.size)))
        rows.append(("Zuletzt", ago(gd.get(g.key, "last"))))
        plays = gd.get(g.key, "plays", 0)
        if plays:
            rows.append(("Gespielt", f"{plays}× · {fmt_time(gd.get(g.key, 'time', 0))}"))
        emu = core.launcher.choose_emulator(g)
        if emu:
            v = tiers.evaluate_emulator(emu, core.assessment.cap) if core.assessment else None
            inst = "" if core.emus.installed(emu) else "  (nicht installiert)"
            rows.append(("Emulator", f"{emu.name} – {v.label if v else ''}{inst}"))
        sh = core.settings.resolve("video.shader", g.system, g.key)
        shdef = core.registry.get("shader", sh.value)
        src = {"game": "Spiel", "system": "System", "global": "global", "default": "Standard"}[sh.source]
        rows.append(("Filter", f"{shdef.name if shdef else sh.value}  ·  {src}"))
        res = core.settings.get("video.internal_res", g.system, g.key)
        if res and int(res) > 1:
            rows.append(("Auflösung", f"{res}× intern"))
        for extra in core.registry.emit("ui.game_details", game=g, core=core):
            rows += extra
        y += 6
        for label, value in rows:
            if y > DETAIL.bottom - 30:
                break
            w.text(surf, th, label, (DETAIL.x + 24, y), 16, th.c["muted"])
            w.text(surf, th, value, (DETAIL.x + 130, y), 16, th.c["text"], max_w=DETAIL.w - 160)
            y += 26

    def hints(self):
        return [("ok", "Starten"), ("y", "Favorit"), ("x", "Optionen"), ("leftright", "Buchstabe"),
                ("back", "Zurück")]
