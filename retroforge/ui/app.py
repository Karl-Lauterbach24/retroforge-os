"""Main loop: display, input, screen stack, toasts, game handover."""
import logging
import os
import platform
import subprocess
import threading
import time

import pygame

from . import backgrounds
from . import widgets as w
from .audio import AudioManager
from .input import Input
from .theme import Theme

log = logging.getLogger("retroforge.ui")
LOGICAL = (w.W, w.H)
IS_OS = os.path.exists("/etc/retroforge-release")


class Toast:
    def __init__(self, text, kind):
        self.text, self.kind, self.age = text, kind, 0.0


class App:
    def __init__(self, core, windowed=False, size=LOGICAL):
        self.core = core
        self.windowed = windowed
        self.win_size = size
        self.stack = []
        self.toasts = []
        self.theme = Theme({})
        self.bg = None
        self.audio = AudioManager(core)
        self.running = True
        self.idle = 0.0
        self.redraw_until = 0.0
        self.booted = False
        self.release_display = (not windowed) and platform.system() == "Linux"
        self._idle_emit = 0.0
        self.overlay_crt = None
        core.registry.on("ui.notify", lambda text, kind="info", **_: self.toast(text, kind), origin="ui")

    # -- display ---------------------------------------------------------------
    def open_display(self):
        info = pygame.display.Info()
        if info.current_w > 0:
            self.core.display_size = (info.current_w, info.current_h)
        flags = pygame.SCALED
        if not self.windowed:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode(LOGICAL, flags, vsync=1)
        except (pygame.error, TypeError):
            try:
                self.screen = pygame.display.set_mode(LOGICAL, flags)
            except pygame.error:
                self.screen = pygame.display.set_mode(LOGICAL)
        pygame.display.set_caption("RetroForge OS")
        pygame.mouse.set_visible(self.windowed)

    def apply_theme(self, theme_id=None):
        tid = theme_id or self.core.settings.get("ui.theme", default="synthwave")
        data = self.core.registry.get("theme", tid) or self.core.registry.get("theme", "synthwave") or {}
        self.theme = Theme(data, self.core.registry)
        self.bg = self.theme.background(self.core.registry, LOGICAL)
        crt = self.core.settings.get("ui.crt_overlay", default=False) or self.theme.ui_crt
        self.overlay_crt = w.scanlines(LOGICAL, 45) if crt else None
        w._panel_cache.clear()
        if self.booted:
            self.audio.load_pack(self.theme)
            self.audio.start_music(self.theme)
        self.redraw()

    # -- stack -------------------------------------------------------------------
    def make(self, screen, **kw):
        if isinstance(screen, str):
            factory = self.core.registry.get("screen", screen)
            if not factory:
                self.toast(f"Unbekannter Bildschirm: {screen}", "bad")
                return None
            return factory(self, **kw)
        return screen

    def push(self, screen, **kw):
        s = self.make(screen, **kw)
        if s:
            self.stack.append(s)
            s.on_enter()
            self.redraw()
        return s

    def pop(self, screen=None):
        if not self.stack:
            return
        if screen is None or self.stack[-1] is screen:
            self.stack.pop()
        elif screen in self.stack:
            self.stack.remove(screen)
        if self.stack:
            self.stack[-1].on_resume()
        self.redraw()

    def replace(self, screen, **kw):
        if self.stack:
            self.stack.pop()
        return self.push(screen, **kw)

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    # -- helpers for screens ------------------------------------------------------
    def sfx(self, name):
        self.audio.play(name)

    def toast(self, text, kind="info"):
        self.toasts.append(Toast(text, kind))
        self.toasts = self.toasts[-4:]
        self.redraw()

    def redraw(self, seconds=0.6):
        self.redraw_until = max(self.redraw_until, time.time() + seconds)

    def menu(self, title, items, subtitle=None, warn=False):
        from .screens.base import MenuDialog
        return self.push(MenuDialog(self, title, items, subtitle, warn))

    def confirm(self, title, text, on_yes, yes="Ja", warn=False):
        from .screens.base import ConfirmDialog
        return self.push(ConfirmDialog(self, title, text, on_yes, yes, warn=warn))

    def info(self, title, lines):
        from .screens.base import InfoDialog
        return self.push(InfoDialog(self, title, lines))

    def progress(self, title, work, done=None):
        from .screens.base import ProgressDialog
        return self.push(ProgressDialog(self, title, work, done))

    # -- games ----------------------------------------------------------------------
    def launch(self, game, emulator_id=None):
        try:
            plan = self.core.launcher.plan(game, emulator_id)
        except RuntimeError as e:
            self.sfx("error")
            self.info("Start nicht möglich", [str(e)])
            return
        emu = plan.emulator
        if not self.core.emus.installed(emu):
            items = []
            if self.core.emus.can_install(emu):
                items.append((f"{emu.name} jetzt installieren", lambda a: self.install_emulator(
                    emu, after=lambda: self.launch(game, emulator_id))))
            items += [("Startbefehl anzeigen", lambda a: self.info("Startbefehl", [plan.describe()] + plan.notes)),
                      ("Trotzdem starten", lambda a: self._start(plan)), ("Abbrechen", None)]
            hint = self.core.emus.install_hint(emu)
            self.sfx("error")
            self.menu(f"{emu.name} ist nicht installiert", items, subtitle=hint or None)
            return
        self._start(plan)

    def install_emulator(self, emu, after=None):
        def work(progress):
            return self.core.emus.install(emu, lambda d, t: progress(d / t if t else 0, f"{d // 1048576} MB geladen"))

        def done(result, error):
            if error:
                self.sfx("error")
                self.info("Installation fehlgeschlagen", [str(error)])
            else:
                self.toast(f"{emu.name} installiert", "good")
                if after:
                    after()
        self.progress(f"{emu.name} wird installiert …", work, done)

    def _start(self, plan):
        from .screens.launch import LaunchScreen
        self.push(LaunchScreen(self, plan))

    def run_game(self, plan):
        """Blocking hand-over of the display to the emulator."""
        self.audio.duck()
        released = False
        if self.release_display:
            pygame.display.quit()   # frees the DRM master for RetroArch / gamescope
            released = True
        result = {}
        th = threading.Thread(target=lambda: result.update(r=self.core.launcher.run(plan)), daemon=True)
        th.start()
        if released:
            th.join()
            pygame.display.init()
            self.open_display()
            self.apply_theme()
        else:
            from .screens.launch import RunningScreen
            self.push(RunningScreen(self, plan, th, result))
            return None
        self.after_game(plan, result.get("r"))
        return result.get("r")

    def after_game(self, plan, r):
        self.audio.unduck(self.theme)
        if not r:
            return
        rc, secs, tail = r
        if rc != 0 and secs < 10:
            self.sfx("error")
            self.info(f"{plan.emulator.name} wurde mit Fehler {rc} beendet",
                      ["Befehl:", plan.describe(), "", "Ausgabe:"] + (tail or "–").splitlines()[-12:])
        else:
            mins = int(secs // 60)
            self.toast(f"{plan.game.name}: {mins} min gespielt" if mins else f"{plan.game.name} beendet", "good")

    def power(self, what):
        if what == "quit":
            self.running = False
            return
        if IS_OS:
            subprocess.Popen(["systemctl", what])
        self.running = False

    # -- main loop ----------------------------------------------------------------
    def dispatch(self, action):
        self.idle = 0.0
        self.redraw()
        top = self.top
        if top is None:
            return
        if top.handle(action):
            return
        if action == "back" and len(self.stack) > 1:
            self.sfx("back")
            self.pop()

    def setup(self):
        os.environ.setdefault("SDL_VIDEO_KMSDRM_MANAGER", "1")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        pygame.init()
        self.open_display()
        self.audio.init()
        backgrounds.register_builtin(self.core.registry)
        self.input = Input()
        if hasattr(pygame.key, "start_text_input"):
            pygame.key.start_text_input()
        from .screens import register_screens
        register_screens(self.core.registry)
        from .screens.boot import BootScreen
        self.bg = self.theme.background(self.core.registry, LOGICAL)
        self.push(BootScreen(self))

    def run(self):
        self.setup()
        clock = pygame.time.Clock()
        while self.running:
            fps = self.target_fps()
            if self.core.settings.get("ui.animations", default="full") == "off" and not self.busy():
                fps = 10   # nothing moves: wake up rarely, don't redraw
            self.step(min(0.1, clock.tick(fps) / 1000.0))
        pygame.quit()
        return 0

    def target_fps(self):
        r = self.core.settings.resolve("ui.fps")
        a = self.core.assessment
        if r.source == "default" and a and a.cap.gpu <= 2:
            return 30   # Pi Zero–Pi 4, old iGPUs: halve the UI frame rate unless the user chose otherwise
        return int(r.value or 60)

    def busy(self):
        return time.time() < self.redraw_until or any(getattr(s, "animating", False) for s in self.stack)             or bool(self.toasts)

    def step(self, dt, draw=True):
        anim = self.core.settings.get("ui.animations", default="full")
        busy = self.busy()
        for ev in pygame.event.get():
            self.handle_event(ev)
        for a in self.input.update(dt):
            self.dispatch(a)
        self.idle += dt
        self._idle_emit += dt
        if self._idle_emit >= 1.0:
            self._idle_emit = 0.0
            self.core.registry.emit("ui.idle", app=self, seconds=self.idle)
        for t in self.toasts:
            t.age += dt
        self.toasts = [t for t in self.toasts if t.age < 3.2]
        if anim != "off" or busy:
            if self.bg and getattr(self.bg, "animated", False) and anim != "off":
                self.bg.update(dt * (0.35 if anim == "reduced" else 1.0))
            for s in self.stack[-2:]:
                s.update(dt)
            if draw:
                self.draw()

    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == getattr(pygame, "JOYDEVICEADDED", -1):
            try:
                name = self.input.device_added(ev.device_index)
                self.toast(f"Controller verbunden: {name}", "good")
            except pygame.error:
                pass
        elif ev.type == getattr(pygame, "JOYDEVICEREMOVED", -1):
            self.input.device_removed(ev.instance_id)
            self.toast("Controller getrennt", "warn")
        elif ev.type == pygame.TEXTINPUT:
            if self.top:
                self.top.text_input(ev.text)
                self.redraw()
        elif ev.type in (pygame.USEREVENT + 7, pygame.USEREVENT + 8):
            self.audio.on_event(ev)
        elif ev.type == pygame.VIDEOEXPOSE or ev.type == getattr(pygame, "WINDOWEXPOSED", -1):
            self.redraw()
        else:
            for a in self.input.translate(ev):
                self.dispatch(a)

    def draw(self):
        surf = self.screen
        if self.bg:
            self.bg.draw(surf)
        else:
            surf.fill(self.theme.c["bg"])
        start = 0
        for i in range(len(self.stack) - 1, -1, -1):
            if not self.stack[i].transparent:
                start = i
                break
        for s in self.stack[start:]:
            s.draw(surf)
        if self.top:
            w.hints(surf, self.theme, self.top.hints())
        self.draw_toasts(surf)
        if self.overlay_crt:
            surf.blit(self.overlay_crt, (0, 0))
        pygame.display.flip()

    def draw_toasts(self, surf):
        th = self.theme
        y = 92
        for t in self.toasts:
            slide = min(1.0, t.age * 6) * (1.0 if t.age < 2.8 else max(0.0, (3.2 - t.age) / 0.4))
            col = th.c.get({"good": "good", "bad": "bad", "warn": "warn"}.get(t.kind, "accent2"))
            f = th.font(17, True)
            img = f.render(t.text, True, th.c["text"])
            box = pygame.Rect(0, y, img.get_width() + 40, 42)
            box.right = w.W - 24 + int((1 - slide) * (box.w + 30))
            w.panel(surf, box, th, th.c["panel2"], radius=12)
            pygame.draw.rect(surf, col, (box.x, box.y + 8, 5, box.h - 16), border_radius=2)
            surf.blit(img, (box.x + 22, box.centery - img.get_height() // 2))
            y += 50
