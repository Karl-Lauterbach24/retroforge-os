"""Home: system carousel + quick-access bar."""
import time

import pygame

from ...hw import tiers
from .. import icons, pixelfont
from .. import widgets as w
from ..theme import color, darken, lighten, mix
from .base import Screen

CARD_W, CARD_H = 290, 330
SPACING = 318
CAROUSEL_Y = 300


class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.row = 0
        self.idx = 0
        self.pos = 0.0
        self.qi = 0
        self.cards = {}
        self.entries = []
        self.quick = []
        self.last_scan = None
        self.rebuild()

    @property
    def animating(self):
        return abs(self.pos - self.idx) > 0.001 or self.core.settings.get("ui.animations") == "full"

    # -- data ------------------------------------------------------------------
    def rebuild(self):
        core = self.core
        cur = self.entries[self.idx][1] if self.entries and self.idx < len(self.entries) else None
        entries = []
        for coll in core.registry.all("collection"):
            try:
                if coll.query(core):
                    entries.append(("coll", coll))
            except Exception:
                pass
        entries += [("sys", s) for s in core.visible_systems()]
        self.entries = entries
        self.idx = next((i for i, e in enumerate(entries) if e[1] is cur), min(self.idx, max(0, len(entries) - 1)))
        self.pos = float(self.idx)
        if core.library.last_scan != self.last_scan or self.app.theme is not getattr(self, "_theme", None):
            self.cards.clear()
        self._theme = self.app.theme
        self.last_scan = core.library.last_scan
        self.quick = [
            ("Spiele importieren", lambda: self.app.push("importer")),
            ("Einstellungen", lambda: self.app.push("settings")),
            ("Hardware & Konsolen", lambda: self.app.push("hardware")),
            ("Emulatoren", lambda: self.app.push("emulators")),
            ("BIOS-Check", lambda: self.app.push("bios")),
            ("Plugins", lambda: self.app.push("plugins")),
        ] + [(m.label, (lambda m=m: m.action(self.app))) for m in core.registry.all("menu_entry")
             if m.section == "home"]
        self.qi = min(self.qi, len(self.quick) - 1)

    def on_resume(self):
        self.rebuild()

    def current(self):
        return self.entries[self.idx] if self.entries else None

    # -- input -----------------------------------------------------------------
    def handle(self, a):
        if a == "menu":
            self.main_menu()
            return True
        if self.row == 0:
            if a in ("left", "right") and self.entries:
                self.idx = (self.idx + (1 if a == "right" else -1)) % len(self.entries)
                if abs(self.idx - self.pos) > 3:
                    self.pos = self.idx - (1 if a == "right" else -1)
                self.app.sfx("move")
                return True
            if a in ("l1", "r1") and self.entries:
                self.idx = max(0, min(len(self.entries) - 1, self.idx + (5 if a == "r1" else -5)))
                self.app.sfx("move")
                return True
            if a == "down":
                self.row = 1
                self.app.sfx("move")
                return True
            if a == "ok":
                self.open_current()
                return True
            if a == "x":
                self.system_menu()
                return True
        else:
            if a in ("left", "right"):
                self.qi = (self.qi + (1 if a == "right" else -1)) % len(self.quick)
                self.app.sfx("move")
                return True
            if a in ("up", "back"):
                self.row = 0
                self.app.sfx("move")
                return True
            if a == "ok":
                self.app.sfx("select")
                self.quick[self.qi][1]()
                return True
        return a == "back"   # don't pop the home screen

    def text_input(self, s):
        s = s.lower().strip()
        if not s or not self.entries:
            return
        n = len(self.entries)
        for k in range(1, n + 1):
            kind, obj = self.entries[(self.idx + k) % n]
            if obj.name.lower().startswith(s) or getattr(obj, "short", "").lower().startswith(s):
                self.idx = (self.idx + k) % n
                self.app.sfx("move")
                return

    def open_current(self):
        e = self.current()
        if not e:
            return
        kind, obj = e
        self.app.sfx("select")
        if kind == "coll":
            self.app.push("gamelist", collection=obj)
            return
        if self.core.library.count(obj.id):
            self.app.push("gamelist", system=obj.id)
            return
        v = self.core.assessment.verdicts.get(obj.id) if self.core.assessment else None
        lines = [f"Noch keine Spiele für {obj.name}.", "",
                 f"• ROMs nach  roms/{obj.id}/  kopieren (USB, Netzwerkfreigabe oder Web-Upload)",
                 "• oder 'Spiele importieren' im Startbildschirm nutzen.",
                 f"• Unterstützte Dateitypen: {' '.join(obj.exts)}"]
        if obj.bios:
            lines.append(f"• BIOS benötigt: {', '.join(obj.bios)}")
        if v and v.reasons:
            lines += ["", f"Hardware: {v.label}"] + [f"  – {r}" for r in v.reasons]
        self.app.info(obj.name, lines)

    def system_menu(self):
        e = self.current()
        if not e or e[0] != "sys":
            return
        s = e[1]
        v = self.core.assessment.verdicts.get(s.id)
        self.app.sfx("select")
        self.app.menu(s.name, [
            ("Einstellungen für dieses System", lambda a: a.push("settings", scope="system", target=s.id)),
            ("Kompatibilität & Anforderungen", lambda a: self.compat_info(s)),
            ("BIOS-Status", lambda a: a.push("bios", only=s.id)),
            ("Bibliothek neu scannen", lambda a: self.rescan()),
        ], subtitle=f"{s.maker} · {s.year} · {v.label if v else ''}")

    def compat_info(self, s):
        core = self.core
        lines = []
        for eid in s.emulators:
            emu = core.registry.get("emulator", eid)
            if not emu:
                continue
            v = tiers.evaluate_emulator(emu, core.assessment.cap)
            inst = "installiert" if core.emus.installed(emu) else "nicht installiert"
            lines.append(f"{emu.name}  [{v.label}, {inst}]")
            lines += [f"   – {r}" for r in v.reasons]
        self.app.info(f"{s.name} – Emulatoren", lines or [s.note or "Kein Emulator verfügbar."])

    def rescan(self):
        def work(progress):
            progress(0, "Durchsuche roms/ …")
            self.core.library.scan()
            return self.core.library.total()
        self.app.progress("Bibliothek wird gescannt", work,
                          lambda r, e: (self.rebuild(), self.app.toast(f"{r} Spiele gefunden", "good")))

    def main_menu(self):
        app = self.app
        items = [("Bibliothek neu scannen", lambda a: self.rescan()),
                 ("Hardware neu erkennen", lambda a: a.progress(
                     "Hardware wird erkannt", lambda p: self.core.probe(),
                     lambda r, e: (self.rebuild(), a.push("hardware"))))]
        items += [(m.label, (lambda a, m=m: m.action(a))) for m in self.core.registry.all("menu_entry")
                  if m.section == "system"]
        from ..app import IS_OS
        if IS_OS:
            items += [("Neu starten", lambda a: a.confirm("Neu starten?", "Das System wird neu gestartet.",
                                                          lambda: a.power("reboot"))),
                      ("Herunterfahren", lambda a: a.confirm("Herunterfahren?", "Das System wird ausgeschaltet.",
                                                             lambda: a.power("poweroff")))]
        items.append(("Frontend beenden", lambda a: a.confirm("Beenden?", "RetroForge wird geschlossen.",
                                                               lambda: a.power("quit"))))
        app.sfx("select")
        app.menu("Menü", items)

    # -- drawing ----------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        self.pos = w.ease(self.pos, float(self.idx), dt, 11)

    def card(self, entry, small):
        key = (id(entry[1]), small)
        surf = self.cards.get(key)
        if surf is not None:
            return surf
        kind, obj = entry
        th = self.theme
        base = color(obj.color)
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        # body gradient
        grad = pygame.Surface((1, CARD_H))
        for y in range(CARD_H):
            grad.set_at((0, y), mix(lighten(base, 0.18), darken(base, 0.55), y / CARD_H))
        grad = pygame.transform.scale(grad, (CARD_W, CARD_H))
        mask = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=22)
        grad = grad.convert_alpha()
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(grad, (0, 0))
        # diagonal stripes
        stripes = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        for x in range(-CARD_H, CARD_W, 22):
            pygame.draw.line(stripes, (255, 255, 255, 14), (x, CARD_H), (x + CARD_H, 0), 8)
        stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(stripes, (0, 0))
        pygame.draw.rect(surf, lighten(base, 0.35) + (160,), surf.get_rect(), 2, border_radius=22)
        ink = (255, 255, 255, 230) if sum(base) < 600 else (30, 30, 40, 230)
        if kind == "coll":
            icon_kind = obj.id if obj.id in icons.ICONS else "chart"
        else:
            icon_kind = icons.for_system(obj)
        icons.draw(icon_kind, surf, ink, CARD_W // 2, 108, 1.0)
        label = obj.short if kind == "sys" else (obj.short or obj.name)
        sc = max(2, min(6, (CARD_W - 40) // max(1, len(label) * 6)))
        img = pixelfont.render(label, sc, ink[:3], darken(base, 0.7) + (180,))
        surf.blit(img, img.get_rect(center=(CARD_W // 2, 222)))
        if kind == "sys":
            n = self.core.library.count(obj.id)
            sub = (f"{n} SPIELE" if n != 1 else "1 SPIEL") if n else "LEER"
            st = self.core.assessment.status(obj.id) if self.core.assessment else 3
            pygame.draw.circle(surf, w.status_color(th, st), (CARD_W - 26, 26), 9)
            pygame.draw.circle(surf, (255, 255, 255), (CARD_W - 26, 26), 9, 2)
        else:
            n = len(obj.query(self.core))
            sub = f"{n} SPIELE" if n != 1 else "1 SPIEL"
        img = pixelfont.render(sub, 2, ink[:3])
        surf.blit(img, img.get_rect(center=(CARD_W // 2, CARD_H - 34)))
        if small:
            surf = pygame.transform.smoothscale(surf, (int(CARD_W * 0.78), int(CARD_H * 0.78)))
            surf.fill((165, 165, 175, 255), special_flags=pygame.BLEND_RGBA_MULT)   # dim, keep alpha
        if len(self.cards) > 40:
            self.cards.clear()
        self.cards[key] = surf
        return surf

    def draw_header(self, surf):
        th = self.theme
        logo = pixelfont.render("RETROFORGE", 3, th.c["accent"], darken(th.c["accent"], 0.65))
        surf.blit(logo, (44, 30))
        tag = pixelfont.render("OS", 2, th.c["accent2"])
        surf.blit(tag, (44 + logo.get_width() + 10, 36))
        a = self.core.assessment
        if a and a.max_console:
            s = self.core.registry.get("system", a.max_console)
            w.pill(surf, th, f"▲ Max: {s.name}", (w.W // 2, 28), th.c["good"], 16, anchor="midtop")
        fmt = "%H:%M" if self.core.settings.get("ui.clock24", default=True) else "%I:%M %p"
        w.text(surf, th, time.strftime(fmt), (w.W - 44, 24), 28, bold=True, anchor="topright")
        info = f"{self.core.library.total()} Spiele"
        pads = self.app.input.names() if hasattr(self.app, "input") else []
        if pads:
            info += f" · {len(pads)} Controller"
        np = self.app.audio.now_playing()
        if np:
            info = f"♪ {np[:28]}   " + info
        w.text(surf, th, info, (w.W - 44, 60), 15, th.c["muted"], anchor="topright")

    def draw(self, surf):
        th = self.theme
        self.draw_header(surf)
        if not self.entries:
            w.text(surf, th, "Keine Systeme sichtbar – Einstellungen prüfen.", (w.W // 2, CAROUSEL_Y), 22,
                   anchor="center")
            return
        cx = w.W // 2
        order = sorted(range(len(self.entries)), key=lambda i: -abs(i - self.pos))
        for i in order:
            d = i - self.pos
            if abs(d) > 2.6:
                continue
            small = abs(d) > 0.5
            img = self.card(self.entries[i], small)
            x = cx + d * SPACING
            r = img.get_rect(center=(int(x), CAROUSEL_Y + (0 if not small else 6)))
            surf.blit(img, r)
            if i == self.idx and not small and self.row == 0:
                w.glow_rect(surf, r.inflate(10, 10), th.c["accent"], self.t, 26)
        self.draw_info(surf)
        self.draw_quick(surf)

    def draw_info(self, surf):
        th = self.theme
        kind, obj = self.current()
        y = CAROUSEL_Y + CARD_H // 2 + 22
        w.text(surf, th, obj.name, (w.W // 2, y), 28, bold=True, anchor="midtop")
        if kind == "coll":
            w.text(surf, th, "Sammlung", (w.W // 2, y + 40), 17, th.c["muted"], anchor="midtop")
            return
        a = self.core.assessment
        v = a.verdicts.get(obj.id) if a else None
        parts = [obj.maker, str(obj.year), f"{self.core.library.count(obj.id)} Spiele"]
        w.text(surf, th, "  ·  ".join(parts), (w.W // 2, y + 40), 17, th.c["muted"], anchor="midtop")
        if v:
            emu = self.core.registry.get("emulator", v.emulator) if v.emulator else None
            label = v.label.upper() + (f"  ·  {emu.name}" if emu else "")
            w.pill(surf, th, label, (w.W // 2, y + 70), w.status_color(th, v.status), 14, anchor="midtop")
        ov = self.core.settings.overrides("system", obj.id)
        if ov:
            names = []
            for k, val in ov.items():
                d = self.core.settings.definition(k)
                if d:
                    names.append(f"{d.label}: {d.label_for(val, self.core, obj.id)}")
            w.text(surf, th, "  ·  ".join(names[:3]), (w.W // 2, y + 104), 14, th.c["accent2"], anchor="midtop",
                   max_w=1000)

    def draw_quick(self, surf):
        th = self.theme
        f = th.font(17, True)
        widths = [f.size(lbl)[0] + 36 for lbl, _ in self.quick]
        total = sum(widths) + 12 * (len(widths) - 1)
        x = (w.W - total) // 2
        y = w.H - 98
        for i, (lbl, _) in enumerate(self.quick):
            r = pygame.Rect(x, y, widths[i], 40)
            sel = self.row == 1 and i == self.qi
            if sel:
                pygame.draw.rect(surf, th.c["accent"], r, border_radius=20)
                img = f.render(lbl, True, darken(th.c["accent"], 0.8))
            else:
                w.panel(surf, r, th, th.c["panel"], radius=20)
                img = f.render(lbl, True, th.c["text"])
            surf.blit(img, img.get_rect(center=r.center))
            x += widths[i] + 12

    def hints(self):
        if self.row == 1:
            return [("leftright", "Wählen"), ("ok", "Öffnen"), ("updown", "Konsolen"), ("menu", "Menü")]
        return [("leftright", "Wählen"), ("ok", "Öffnen"), ("x", "System-Optionen"), ("menu", "Menü")]
