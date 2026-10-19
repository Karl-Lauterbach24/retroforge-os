"""Builds and runs launch plans.

A :class:`LaunchPlan` is assembled from the layered settings, then passed
through the ``game.before_launch`` filter so plugins can change anything
(command, environment, RetroArch config lines, gamescope flags) before the
files are written and the process starts.
"""
import logging
import os
import platform
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .hw import tiers

log = logging.getLogger("retroforge.launcher")

SHADER_ROOTS = ["/usr/share/libretro/shaders/shaders_slang", "/usr/share/libretro/shaders/slang",
                "~/.config/retroarch/shaders/shaders_slang"]
# RetroArch aspect_ratio_index enum (1.15+)
RA_ASPECT = {"4:3": 0, "16:9": 1, "8:7": 15, "1:1": 21, "auto": 22, "full": 24}
RA_MENU_COMBO = {"select": 4, "l3r3": 2, "guide": 0}
GAMESCOPE_SCALER = {"integer": "integer", "integer_over": "integer", "fit": "fit",
                    "stretch": "stretch", "fill": "fill"}
GOVERNOR = {"powersave": "powersave", "balanced": "schedutil", "performance": "performance"}


@dataclass
class LaunchPlan:
    game: object
    emulator: object
    cmd: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    ra_config: Dict[str, object] = field(default_factory=dict)     # RetroArch append-config
    core_options: Dict[str, str] = field(default_factory=dict)
    ini_patches: list = field(default_factory=list)                 # (file, section, key, value)
    gamescope: List[str] = field(default_factory=list)              # gamescope args (empty = no wrap)
    governor: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    settings: Dict[str, object] = field(default_factory=dict)

    def full_cmd(self):
        if self.gamescope:
            return ["gamescope"] + self.gamescope + ["--"] + self.cmd
        return list(self.cmd)

    def describe(self):
        return " ".join(shlex.quote(c) for c in self.full_cmd()).replace("{appendconfig}", "<retroarch-append.cfg>")


def _cfgval(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


class Launcher:
    def __init__(self, core):
        self.core = core
        self.running = None
        self.proc = None

    def stop(self):
        """Terminate the running game (e.g. from the frontend in windowed mode)."""
        p = self.proc
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()

    # -- emulator choice -------------------------------------------------------
    def choose_emulator(self, game, emulator_id=None):
        reg = self.core.registry
        sysdef = reg.get("system", game.system)
        wanted = emulator_id or self.core.settings.get("emulator", game.system, game.key)
        if wanted and wanted != "auto" and reg.get("emulator", wanted):
            return reg.get("emulator", wanted)
        cap = self.core.assessment.cap if self.core.assessment else None
        best, best_key = None, None
        for idx, eid in enumerate(sysdef.emulators if sysdef else ()):
            emu = reg.get("emulator", eid)
            if not emu:
                continue
            status = tiers.evaluate_emulator(emu, cap).status if cap else tiers.PLAYABLE
            key = (status >= tiers.PLAYABLE, self.core.emus.installed(emu), status, -idx)
            if best_key is None or key > best_key:
                best, best_key = emu, key
        return best

    # -- plan ------------------------------------------------------------------
    def plan(self, game, emulator_id=None) -> LaunchPlan:
        core = self.core
        emu = self.choose_emulator(game, emulator_id)
        if emu is None:
            raise RuntimeError("Für dieses System ist kein Emulator verfügbar.")
        S = {d.key: core.settings.get(d.key, game.system, game.key) for d in core.registry.all("setting")}
        plan = LaunchPlan(game=game, emulator=emu, settings=S)
        plan.governor = GOVERNOR.get(S.get("system.cpu_governor"))
        rom = self._rom_arg(game)
        if emu.kind == "libretro":
            self._plan_libretro(plan, emu, rom, S)
        else:
            self._plan_standalone(plan, emu, rom, S)
        return core.registry.filter("game.before_launch", plan, core=core)

    def _rom_arg(self, game):
        p = game.path
        if game.is_dir and game.system == "ps4":
            eboot = Path(p) / "eboot.bin"
            return str(eboot) if eboot.exists() else p
        return p

    def _shader(self, S):
        return self.core.registry.get("shader", S.get("video.shader") or "none")

    def _plan_libretro(self, plan, emu, rom, S):
        core, paths = self.core, self.core.paths
        ra = core.emus.retroarch() or "retroarch"
        core_path = core.emus.core_path(emu.core) or f"{emu.core}_libretro.so"
        if not core.emus.core_path(emu.core):
            plan.notes.append(f"Core '{emu.core}' ist nicht installiert.")
        cap = core.assessment.cap if core.assessment else None
        renderer = S.get("video.renderer", "auto")
        if renderer == "auto":
            renderer = "vulkan" if cap and cap.vulkan and cap.gpu >= 3 else "glcore" if cap and cap.gpu >= 2 else "gl"
        c = plan.ra_config
        c.update({
            "video_fullscreen": True,
            "video_driver": renderer,
            "video_scale_integer": S["video.scaling"] in ("integer", "integer_over"),
            "video_scale_integer_overscale": S["video.scaling"] == "integer_over",
            "aspect_ratio_index": RA_ASPECT.get(S["video.aspect"], 22),
            "video_smooth": bool(S["video.smooth"]),
            "video_vsync": bool(S["video.vsync"]),
            "vrr_runloop_enable": bool(S["video.vrr"]),
            "run_ahead_enabled": int(S["game.runahead"]) > 0,
            "run_ahead_frames": max(1, int(S["game.runahead"])),
            "rewind_enable": bool(S["game.rewind"]),
            "savestate_auto_save": bool(S["game.autosave"]),
            "savestate_auto_load": bool(S["game.autosave"]),
            "fastforward_ratio": f"{float(S['game.ff_speed']):.1f}",
            "cheevos_enable": bool(S["game.achievements"]),
            "input_menu_toggle_gamepad_combo": RA_MENU_COMBO.get(S["system.hotkey"], 4),
            "system_directory": str(paths.bios),
            "savefile_directory": str(paths.saves / plan.game.system),
            "savestate_directory": str(paths.states / plan.game.system),
            "screenshot_directory": str(paths.screenshots),
            "config_save_on_exit": False,
        })
        if S["video.rotation"] not in ("auto", None):
            c["video_rotation"] = int(S["video.rotation"]) // 90
        if S["video.bezel"] == "auto":
            overlay = paths.home / "bezels" / f"{plan.game.system}.cfg"
            if overlay.exists():
                c["input_overlay"] = str(overlay)
                c["input_overlay_enable"] = True
                c["video_scale_integer"] = False
        scale = int(S.get("video.internal_res") or 1)
        if scale > 1:
            if emu.upscale:
                patch = emu.upscale(scale)
                plan.core_options.update(patch.get("core_options", {}))
            else:
                plan.notes.append(f"{emu.name} unterstützt keine interne Auflösung – nutze Shader/Upscaler.")
        shader = self._shader(S)
        upscaler = S.get("video.upscaler")
        if (not shader or shader.id == "none") and upscaler == "fsr":
            shader = core.registry.get("shader", "fsr")
        plan.cmd = [ra, "-L", core_path, "--appendconfig", "{appendconfig}"]
        if shader and shader.slang:
            preset = self._find_shader(shader.slang)
            if preset:
                plan.cmd += ["--set-shader", preset]
                c["video_shader_enable"] = True
                if cap and shader.weight >= 4 and cap.gpu < 4:
                    plan.notes.append(f"'{shader.name}' ist für GPU-Klasse {cap.gpu} sehr anspruchsvoll.")
            else:
                plan.notes.append(f"Shader-Datei {shader.slang} nicht gefunden – ohne Filter gestartet.")
        plan.cmd.append(rom)

    def _find_shader(self, rel):
        roots = [self.core.paths.home / "shaders"] + [Path(os.path.expanduser(r)) for r in SHADER_ROOTS]
        for r in roots:
            p = Path(r) / rel
            if p.exists():
                return str(p)
        return None

    def _plan_standalone(self, plan, emu, rom, S):
        core = self.core
        exe = core.emus.standalone_path(emu)
        if not exe:
            plan.notes.append(f"{emu.name} ist nicht installiert. {core.emus.install_hint(emu)}".strip())
            exe = emu.binary
        content = ""
        if "{content}" in " ".join(emu.args):
            try:
                with open(rom, "r", encoding="utf-8", errors="replace") as f:
                    content = f.readline().strip()
            except OSError:
                content = plan.game.stem
        fmt = {"rom": rom, "content": content or plan.game.stem, "stem": plan.game.stem,
               "dir": os.path.dirname(rom), "bios": str(core.paths.bios)}
        args = [a.format(**fmt) for a in emu.args]
        extra = []
        scale = int(S.get("video.internal_res") or 1)
        if scale > 1 and emu.upscale:
            patch = emu.upscale(scale)
            extra += patch.get("args", [])
            plan.ini_patches += patch.get("ini", [])
        if S.get("video.widescreen") and emu.id == "dolphin":
            extra += ["-C", "GFX.Settings.wideScreenHack=True"]
        plan.cmd = [exe] + extra + args
        # gamescope: upscaling filters + ReShade shaders for standalone emulators
        if S.get("emu.gamescope", True) and emu.wrap == "gamescope":
            if platform.system() == "Linux" and shutil.which("gamescope"):
                plan.gamescope = self._gamescope_args(S)
            else:
                shader = self._shader(S)
                if S.get("video.upscaler") != "none" or (shader and shader.id != "none"):
                    plan.notes.append("gamescope fehlt – Upscaler/Filter für Standalone-Emulatoren inaktiv.")

    def _gamescope_args(self, S):
        W, H = self.core.display_size
        g = ["-f", "-W", str(W), "-H", str(H)]
        up = S.get("video.upscaler", "none")
        if up in ("fsr", "nis"):
            g += ["-w", str(int(W * 0.67)), "-h", str(int(H * 0.67)), "-F", up]
        elif up in ("pixel", "linear"):
            g += ["-F", up]
        g += ["-S", GAMESCOPE_SCALER.get(S.get("video.scaling"), "fit")]
        if S.get("video.vrr"):
            g.append("--adaptive-sync")
        shader = self._shader(S)
        if shader and shader.reshade:
            g += ["--reshade-effect", shader.reshade]
        elif shader and shader.gamescope_filter and up == "none":
            g += ["-F", shader.gamescope_filter]
        return g

    # -- execution ---------------------------------------------------------------
    def materialize(self, plan):
        """Writes generated config files; returns the final argv."""
        run_dir = self.core.paths.cache / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        if plan.core_options:
            base = self.core.paths.file("core-options.cfg")
            lines = base.read_text(encoding="utf-8").splitlines() if base.exists() else []
            keys = set(plan.core_options)
            lines = [l for l in lines if l.split("=", 1)[0].strip() not in keys]
            lines += [f'{k} = "{v}"' for k, v in plan.core_options.items()]
            opt = run_dir / "core-options.cfg"
            opt.write_text("\n".join(lines) + "\n", encoding="utf-8")
            plan.ra_config["core_options_path"] = str(opt)
            plan.ra_config["global_core_options"] = True
        append = run_dir / "retroarch-append.cfg"
        append.write_text("".join(f'{k} = "{_cfgval(v)}"\n' for k, v in plan.ra_config.items()),
                          encoding="utf-8")
        for path, section, key, value in plan.ini_patches:
            ini_patch(os.path.expanduser(path), section, key, value)
        for sub in ("saves", "states"):
            (getattr(self.core.paths, sub) / plan.game.system).mkdir(parents=True, exist_ok=True)
        return [str(append) if a == "{appendconfig}" else a for a in plan.full_cmd()]

    def _set_governor(self, gov):
        if not gov or platform.system() != "Linux":
            return
        for p in Path("/sys/devices/system/cpu/cpufreq").glob("policy*/scaling_governor"):
            try:
                p.write_text(gov)
            except OSError:
                return   # needs the retroforge-governor udev rule on the OS image

    def run(self, plan):
        """Blocking. Returns (returncode, seconds, error_tail)."""
        argv = self.materialize(plan)
        env = dict(os.environ, **plan.env)
        log.info("launch: %s", " ".join(shlex.quote(a) for a in argv))
        self.core.registry.emit("game.launch", plan=plan, core=self.core)
        self._set_governor(plan.governor)
        t0 = time.time()
        self.running = plan
        logfile = self.core.paths.logs / "last-game.log"
        try:
            with open(logfile, "w", encoding="utf-8", errors="replace") as lf:
                self.proc = subprocess.Popen(argv, env=env, cwd=plan.cwd, stdout=lf, stderr=subprocess.STDOUT)
                rc = self.proc.wait()
        except (FileNotFoundError, PermissionError, OSError) as e:
            rc = 127
            logfile.write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
        finally:
            self.running = None
            self.proc = None
            self._set_governor(GOVERNOR["balanced"])
        secs = time.time() - t0
        tail = ""
        if rc != 0:
            try:
                tail = logfile.read_text(encoding="utf-8", errors="replace")[-600:]
            except OSError:
                pass
        if rc == 0 or secs > 20:
            self.core.gamedata.record_play(plan.game.key, secs)
        self.core.registry.emit("game.after_exit", plan=plan, returncode=rc, seconds=secs, core=self.core)
        return rc, secs, tail


def ini_patch(path, section, key, value):
    """Set ``key = value`` in ``[section]`` keeping comments and unknown keys intact."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    out, in_sec, done, seen_sec = [], False, False, False
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_sec and not done:
                out.append(f"{key} = {value}")
                done = True
            in_sec = s[1:-1] == section
            seen_sec = seen_sec or in_sec
        elif in_sec and not done and s.split("=", 1)[0].strip() == key:
            out.append(f"{key} = {value}")
            done = True
            continue
        out.append(line)
    if not done:
        if not seen_sec:
            out.append(f"[{section}]")
        out.append(f"{key} = {value}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
