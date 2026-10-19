"""ROM import, plugin manager, emulator manager, BIOS check."""
import glob
import os
import platform
import shutil
from pathlib import Path

import pygame

from ... import romdetect
from ...hw import tiers
from .. import widgets as w
from ..theme import color, darken, mix
from .base import ListNav, Screen

BOX = pygame.Rect(40, 132, 1200, 528)
ROW = 46


class ListScreen(Screen):
    """Shared layout: one big panel with selectable rows."""
    title, subtitle = "", ""

    def __init__(self, app):
        super().__init__(app)
        self.rows = []
        self.nav = ListNav(0, (BOX.h - 20) // ROW)

    def set_rows(self, rows):
        self.rows = rows
        self.nav.n = len(rows)
        self.nav.set(self.nav.i)

    def handle(self, a):
        if a in ("up", "down"):
            if self.nav.move(-1 if a == "up" else 1):
                self.app.sfx("move")
            return True
        if a in ("l1", "r1"):
            self.nav.move(self.nav.visible if a == "r1" else -self.nav.visible, wrap=False)
            return True
        return False

    def update(self, dt):
        super().update(dt)
        self.nav.update(dt)

    def draw_row(self, surf, r, row, sel):
        pass

    def draw(self, surf):
        th = self.theme
        w.header(surf, th, self.title, self.subtitle)
        w.panel(surf, BOX, th)
        if not self.rows:
            w.text(surf, th, self.empty_text(), BOX.center, 19, th.c["muted"], anchor="center")
            return
        clip = surf.get_clip()
        surf.set_clip(BOX.inflate(-8, -8))
        for i, row in enumerate(self.rows):
            y = BOX.y + 10 + (i - self.nav.top) * ROW
            if y < BOX.y - ROW or y > BOX.bottom:
                continue
            r = pygame.Rect(BOX.x + 10, int(y), BOX.w - 20, ROW - 6)
            sel = i == self.nav.i
            if sel:
                pygame.draw.rect(surf, darken(th.c["accent"], 0.3), r, border_radius=10)
                pygame.draw.rect(surf, th.c["accent"], (r.x, r.y + 8, 4, r.h - 16), border_radius=2)
            self.draw_row(surf, r, row, sel)
        surf.set_clip(clip)

    def empty_text(self):
        return "Nichts gefunden."


# ---------------------------------------------------------------------------
class ImportScreen(ListScreen):
    title = "Spiele importieren"

    def __init__(self, app):
        super().__init__(app)
        self.mode = "sources"
        self.source = None
        self.found = []
        self.subtitle = "Quelle wählen – ROMs & BIOS werden automatisch erkannt und einsortiert"
        self.bios_names = {}
        for s in self.core.registry.all("system"):
            for entry in s.bios:
                for alt in entry.split("|"):
                    if "*" not in alt:
                        self.bios_names[os.path.basename(alt).lower()] = alt
        self.show_sources()

    def sources(self):
        inbox = self.core.paths.import_inbox
        out = [("Import-Ordner (userdata/import)", inbox)]
        if platform.system() == "Linux":
            for pattern in ("/media/*/*", "/media/*", "/run/media/*/*", "/mnt/*"):
                for p in sorted(glob.glob(pattern)):
                    if os.path.ismount(p):
                        out.append((f"Laufwerk {os.path.basename(p)}", Path(p)))
        else:
            dl = Path.home() / "Downloads"
            if dl.is_dir():
                out.append(("Downloads (Entwicklungsmodus)", dl))
        return out

    def show_sources(self):
        self.mode = "sources"
        hints = []
        for lines in self.core.registry.emit("ui.import_hints", core=self.core):
            hints += lines
        self.extra_hints = hints
        self.set_rows([("src", lbl, p) for lbl, p in self.sources()])

    def scan(self, root):
        exts = {}
        for s in self.core.registry.all("system"):
            for e in s.exts:
                exts.setdefault(e, []).append(s.id)

        def work(progress):
            found, n = [], 0
            for dirpath, dirnames, files in os.walk(root):
                depth = Path(dirpath).relative_to(root).parts
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and len(depth) < 5]
                for fn in files:
                    n += 1
                    if n > 20000:
                        return found
                    p = Path(dirpath) / fn
                    low = fn.lower()
                    if low in self.bios_names:
                        found.append([p, "bios", [self.bios_names[low]]])
                        continue
                    ext = p.suffix.lower()
                    if ext not in exts:
                        continue
                    progress(0, fn)
                    guess = romdetect.detect(p, self.core.registry)
                    cands = exts[ext]
                    if guess and guess not in cands:
                        cands = [guess] + cands
                    found.append([p, guess or (cands[0] if len(cands) == 1 else None), cands])
            return found

        def done(result, error):
            if error:
                self.app.info("Fehler beim Durchsuchen", [str(error)])
                return
            self.found = result or []
            self.mode = "files"
            self.source = root
            ok = sum(1 for f in self.found if f[1])
            self.subtitle = f"{len(self.found)} Dateien gefunden, {ok} zugeordnet – ←→ ändert die Zuordnung"
            self.set_rows([("all",)] + [("file", f) for f in self.found])
            self.nav.set(0)
        self.app.progress("Durchsuche Quelle …", work, done)

    def do_import(self):
        items = [f for f in self.found if f[1]]
        move = self.source == self.core.paths.import_inbox
        paths = self.core.paths

        def work(progress):
            for i, (src, target, cands) in enumerate(items):
                progress(i / max(1, len(items)), src.name)
                if target == "bios":
                    dest = paths.bios / cands[0]
                else:
                    dest = paths.system_roms(target) / src.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    continue
                if move:
                    shutil.move(str(src), str(dest))
                else:
                    shutil.copy2(str(src), str(dest))
            progress(1, "Bibliothek wird aktualisiert …")
            self.core.library.scan()
            return len(items)

        def done(result, error):
            if error:
                self.app.info("Import fehlgeschlagen", [str(error)])
                return
            self.app.toast(f"{result} Dateien importiert", "good")
            self.show_sources()
            self.subtitle = "Fertig – weitere Quelle wählen"
        self.app.progress("Importiere …", work, done)

    def handle(self, a):
        if super().handle(a):
            return True
        row = self.rows[self.nav.i] if self.rows else None
        if a == "back" and self.mode == "files":
            self.show_sources()
            return True
        if not row:
            return False
        if a == "ok":
            self.app.sfx("select")
            if row[0] == "src":
                row[2].mkdir(parents=True, exist_ok=True) if row[2] == self.core.paths.import_inbox else None
                self.scan(row[2])
            elif row[0] == "all":
                self.do_import()
            return True
        if a in ("left", "right") and row[0] == "file":
            f = row[1]
            opts = [c for c in f[2]] + [None]
            i = opts.index(f[1]) if f[1] in opts else len(opts) - 1
            f[1] = opts[(i + (1 if a == "right" else -1)) % len(opts)]
            self.app.sfx("toggle")
            return True
        return False

    def draw(self, surf):
        super().draw(surf)
        if self.mode == "sources" and self.extra_hints:
            th = self.theme
            y = BOX.bottom - 30 * len(self.extra_hints) - 10
            for line in self.extra_hints:
                w.text(surf, th, line, (BOX.x + 30, y), 17, th.c["accent2"])
                y += 30

    def draw_row(self, surf, r, row, sel):
        th = self.theme
        if row[0] == "src":
            w.text(surf, th, row[1], (r.x + 20, r.centery), 19, anchor="midleft")
            w.text(surf, th, str(row[2]), (r.right - 20, r.centery), 14, th.c["muted"], anchor="midright", max_w=600)
        elif row[0] == "all":
            n = sum(1 for f in self.found if f[1])
            w.text(surf, th, f"▶  {n} Dateien importieren", (r.x + 20, r.centery), 20, th.c["good"], bold=True,
                   anchor="midleft")
        else:
            path, target, cands = row[1]
            w.text(surf, th, path.name, (r.x + 20, r.centery), 17, anchor="midleft", max_w=760)
            if target == "bios":
                lbl, col = "BIOS", th.c["warn"]
            elif target:
                s = self.core.registry.get("system", target)
                lbl, col = (s.short if s else target), color(s.color) if s else th.c["muted"]
                col = mix(col, (255, 255, 255), 0.35)
            else:
                lbl, col = "überspringen", th.c["off"]
            w.pill(surf, th, ("‹ " + lbl + " ›") if sel else lbl, (r.right - 16, r.centery), col, 14, anchor="midright")

    def hints(self):
        if self.mode == "files":
            return [("leftright", "System"), ("ok", "Importieren"), ("back", "Quellen")]
        return [("ok", "Durchsuchen"), ("back", "Zurück")]

    def empty_text(self):
        return "Keine Quelle gefunden – USB-Stick einstecken oder Dateien nach userdata/import kopieren."


# ---------------------------------------------------------------------------
class PluginsScreen(ListScreen):
    title = "Plugins"
    subtitle = "Erweiterungen aus /userdata/plugins und dem System – Änderungen wirken nach Neustart"

    def __init__(self, app):
        super().__init__(app)
        self.set_rows(sorted(self.core.plugins.plugins.values(), key=lambda p: p.name.lower()))

    def handle(self, a):
        if super().handle(a):
            return True
        if a == "ok" and self.rows:
            p = self.rows[self.nav.i]
            on = not self.core.plugins.enabled(p)

            def apply():
                self.core.plugins.set_enabled(p.id, on)
                self.app.sfx("toggle")
                self.app.toast(f"{p.name} {'aktiviert' if on else 'deaktiviert'} – wirkt nach Neustart")
            if on and p.warning:
                self.app.confirm(f"{p.name} aktivieren?", p.warning, apply,
                                 yes="Verstanden – auf eigene Gefahr aktivieren", warn=True)
            else:
                apply()
            return True
        return False

    def draw_row(self, surf, r, p, sel):
        th = self.theme
        enabled = self.core.plugins.enabled(p)
        w.text(surf, th, p.name, (r.x + 20, r.y + 4), 18, bold=True, max_w=360)
        desc = p.error if p.status == "error" else p.description
        w.text(surf, th, desc, (r.x + 20, r.y + 24), 13, th.c["bad"] if p.status == "error" else th.c["muted"],
               max_w=720)
        w.text(surf, th, f"v{p.version}" + ("" if p.builtin else " · Benutzer"), (r.x + 760, r.centery), 14,
               th.c["muted"], anchor="midleft")
        state = {"loaded": ("aktiv", th.c["good"]), "disabled": ("aus", th.c["off"]),
                 "error": ("Fehler", th.c["bad"]), "incompatible": ("inkompatibel", th.c["warn"])}
        lbl, col = state.get(p.status, (p.status, th.c["muted"]))
        if enabled and p.status == "disabled":
            lbl, col = "nach Neustart an", th.c["accent2"]
        if not enabled and p.status == "loaded":
            lbl, col = "nach Neustart aus", th.c["warn"]
        box = w.pill(surf, th, lbl, (r.right - 16, r.centery), col, 13, anchor="midright")
        if p.warning:
            w.pill(surf, th, "eigene Gefahr", (box.x - 8, r.centery), th.c["warn"], 13, anchor="midright")

    def hints(self):
        return [("ok", "An/Aus"), ("back", "Zurück")]

    def empty_text(self):
        return "Keine Plugins installiert."


# ---------------------------------------------------------------------------
class EmulatorsScreen(ListScreen):
    title = "Emulatoren"

    def __init__(self, app):
        super().__init__(app)
        self.users = {}
        for s in self.core.registry.all("system"):
            for e in s.emulators:
                self.users.setdefault(e, []).append(s.short)
        self.refresh()

    def refresh(self):
        emus = self.core.registry.all("emulator")
        inst = sum(1 for e in emus if self.core.emus.installed(e))
        ra = "RetroArch gefunden" if self.core.emus.retroarch() else "RetroArch fehlt"
        self.subtitle = f"{inst} von {len(emus)} installiert · {ra} · fehlende werden bei Bedarf geladen"
        self.set_rows(sorted(emus, key=lambda e: (e.kind != "standalone", e.order)))

    def handle(self, a):
        if super().handle(a):
            return True
        if a == "ok" and self.rows:
            e = self.rows[self.nav.i]
            path = self.core.emus.locate(e)
            if path:
                self.app.info(e.name, [f"Installiert: {path}", "", e.note or ""])
            elif self.core.emus.can_install(e):
                self.app.confirm(f"{e.name} installieren?",
                                 f"Wird aus der offiziellen Quelle geladen ({(e.source or {}).get('type')}).",
                                 lambda: self.app.install_emulator(e, after=self.refresh), yes="Installieren")
            else:
                self.app.info(e.name, [self.core.emus.install_hint(e) or "Keine automatische Installation möglich."])
            return True
        return False

    def draw_row(self, surf, r, e, sel):
        th = self.theme
        v = tiers.evaluate_emulator(e, self.core.assessment.cap)
        inst = self.core.emus.installed(e)
        w.text(surf, th, e.name, (r.x + 20, r.centery), 18, bold=True, anchor="midleft", max_w=300)
        kind = "libretro" if e.kind == "libretro" else "Standalone"
        w.text(surf, th, kind, (r.x + 330, r.centery), 14, th.c["muted"], anchor="midleft")
        w.text(surf, th, " ".join(self.users.get(e.id, [])), (r.x + 450, r.centery), 14, th.c["accent2"],
               anchor="midleft", max_w=330)
        w.pill(surf, th, v.label, (r.right - 160, r.centery), w.status_color(th, v.status), 13, anchor="midright")
        w.pill(surf, th, "installiert" if inst else "fehlt", (r.right - 16, r.centery),
               th.c["good"] if inst else th.c["off"], 13, anchor="midright")

    def hints(self):
        return [("ok", "Details / Installieren"), ("back", "Zurück")]


# ---------------------------------------------------------------------------
class BiosScreen(ListScreen):
    title = "BIOS-Check"

    def __init__(self, app, only=None):
        super().__init__(app)
        rows = []
        missing = 0
        for s in self.core.registry.all("system"):
            if not s.bios or (only and s.id != only):
                continue
            for entry, found in self.core.bios_status(s):
                rows.append((s, entry, found))
                missing += found is None
        self.subtitle = f"BIOS-Dateien gehören nach userdata/bios · {missing} fehlen"
        self.set_rows(rows)

    def draw_row(self, surf, r, row, sel):
        th = self.theme
        s, entry, found = row
        w.text(surf, th, s.name, (r.x + 20, r.centery), 17, bold=True, anchor="midleft", max_w=300)
        w.text(surf, th, entry.replace("|", "  oder  "), (r.x + 340, r.centery), 15, th.c["muted"],
               anchor="midleft", max_w=620)
        w.pill(surf, th, f"OK: {found}" if found else "fehlt", (r.right - 16, r.centery),
               th.c["good"] if found else th.c["bad"], 13, anchor="midright")

    def hints(self):
        return [("updown", "Blättern"), ("back", "Zurück")]

    def empty_text(self):
        return "Für dieses System wird kein BIOS benötigt."
