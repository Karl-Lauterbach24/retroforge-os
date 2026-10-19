"""Menu sounds and background music – synthesised, no audio assets needed.

* Sound packs are tiny parameter sets rendered to PCM at startup (~50 ms).
* Theme music is a deterministic chiptune loop generated from the theme's
  ``music`` block (tempo, key, scale, chord progression), rendered once in a
  background thread and cached as WAV.
* "Eigene Musik" plays ogg/mp3/flac/wav files from /userdata/music.
"""
import array
import hashlib
import json
import logging
import math
import os
import random
import threading
import wave

import pygame

log = logging.getLogger("retroforge.audio")
RATE = 22050
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
          "dorian": [0, 2, 3, 5, 7, 9, 10], "penta": [0, 3, 5, 7, 10], "lydian": [0, 2, 4, 6, 7, 9, 11]}
MUSIC_EXTS = (".ogg", ".mp3", ".flac", ".wav", ".opus", ".mod", ".xm", ".it", ".s3m")


def midi_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def osc(wave_type, phase, duty=0.5):
    p = phase % 1.0
    if wave_type == "square":
        return 1.0 if p < duty else -1.0
    if wave_type == "tri":
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if wave_type == "saw":
        return 2 * p - 1
    if wave_type == "noise":
        return random.uniform(-1, 1)
    return math.sin(p * math.tau)


def tone(f0, dur, wave_type="square", vol=0.5, f1=None, attack=0.004, decay=None, duty=0.5, bell=False):
    n = int(RATE * dur)
    f1 = f0 if f1 is None else f1
    out = [0.0] * n
    ph = 0.0
    decay = dur if decay is None else decay
    for i in range(n):
        t = i / RATE
        f = f0 + (f1 - f0) * (i / n)
        ph += f / RATE
        env = min(1.0, t / attack) if attack else 1.0
        env *= math.exp(-3.0 * t / decay)
        s = osc(wave_type, ph, duty)
        if bell:
            s = 0.6 * s + 0.3 * math.sin(ph * 2.01 * math.tau) + 0.1 * math.sin(ph * 3.98 * math.tau)
        out[i] = s * env * vol
    return out


def seq(*parts):
    out = []
    for p in parts:
        out += p
    return out


def _pack_sounds(style):
    if style == "soft":
        b = lambda f, d=0.18: tone(f, d, "sine", 0.45, bell=True, decay=d * 0.6)
        return {"move": b(1046, 0.08), "select": seq(b(784, 0.07), b(1175, 0.16)),
                "back": seq(b(880, 0.07), b(587, 0.14)), "error": b(220, 0.3),
                "launch": seq(*[b(f, 0.09) for f in (523, 659, 784, 1046)]), "toggle": b(1319, 0.06)}
    if style == "arcade":
        return {"move": tone(1800, 0.03, "square", 0.25, 1400, duty=0.25),
                "select": seq(tone(988, 0.06, "square", 0.3), tone(1319, 0.22, "square", 0.3, decay=0.12)),
                "back": tone(900, 0.12, "saw", 0.25, 300),
                "error": seq(tone(160, 0.08, "noise", 0.3), tone(110, 0.2, "square", 0.3)),
                "launch": seq(tone(300, 0.25, "square", 0.3, 1600, duty=0.25), tone(1600, 0.2, "noise", 0.15)),
                "toggle": tone(1200, 0.04, "tri", 0.4)}
    # chiptune (default)
    sq = lambda f, d, **k: tone(f, d, "square", 0.22, duty=0.25, **k)
    return {"move": sq(880, 0.035), "select": seq(sq(660, 0.05), sq(990, 0.09)),
            "back": seq(sq(660, 0.05), sq(440, 0.08)), "error": tone(110, 0.18, "square", 0.25, 90),
            "launch": seq(*[sq(f, 0.06) for f in (523, 659, 784, 1046, 1319)]), "toggle": sq(1320, 0.025)}


def to_sound(samples, channels):
    a = array.array("h", (max(-32767, min(32767, int(s * 32767))) for s in samples))
    if channels == 2:
        st = array.array("h", [0]) * (len(a) * 2)
        st[0::2] = a
        st[1::2] = a
        a = st
    return pygame.mixer.Sound(buffer=a.tobytes())


# ---------------------------------------------------------------------------
def compose(spec, seconds=32):
    """Deterministic chiptune loop: bass, arpeggio, lead and noise drums."""
    tempo = float(spec.get("tempo", 112))
    root = int(spec.get("root", 57))
    scale = SCALES.get(spec.get("scale", "minor"), SCALES["minor"])
    prog = spec.get("progression", [0, 5, 3, 4])
    style = spec.get("style", "arp")
    rnd = random.Random(spec.get("seed", json.dumps(spec, sort_keys=True)))
    step = 60.0 / tempo / 4                         # 16th notes
    steps_per_bar = 16
    bars = max(len(prog), int(seconds / (step * steps_per_bar)) // len(prog) * len(prog))
    n = int(bars * steps_per_bar * step * RATE)
    buf = [0.0] * n

    def deg(d, octave=0):
        return root + scale[d % len(scale)] + 12 * (d // len(scale) + octave)

    def add(start, note_samples):
        s = int(start * RATE)
        for i, v in enumerate(note_samples):
            j = s + i
            if j >= n:
                break
            buf[j] += v

    melody_deg = 7
    for bar in range(bars):
        chord = prog[bar % len(prog)]
        t0 = bar * steps_per_bar * step
        triad = [deg(chord), deg(chord + 2), deg(chord + 4)]
        # bass: root on 1 and 3, fifth on the off-beats
        for k in range(0, 16, 4):
            note = triad[0] - 24 if k % 8 == 0 else triad[2] - 24
            add(t0 + k * step, tone(midi_hz(note), step * 3.2, "tri", 0.32, decay=step * 6))
        # arpeggio
        if style in ("arp", "drive"):
            for k in range(16):
                note = triad[k % 3] + (12 if (k // 3) % 2 else 0)
                add(t0 + k * step, tone(midi_hz(note), step * 0.9, "square", 0.07, duty=0.125, decay=step * 2))
        else:   # pads for calm themes
            for nn in triad:
                add(t0, tone(midi_hz(nn), step * 15, "sine", 0.06, attack=0.3, decay=step * 30))
        # lead: seeded random walk on chord tones, phrase repeats every 4 bars
        if bar % 4 == 0:
            phrase = []
            for k in range(0, 64, 2):
                melody_deg = max(2, min(12, melody_deg + rnd.choice((-2, -1, 0, 1, 1, 2))))
                phrase.append(melody_deg if rnd.random() > 0.3 else None)
        for k in range(8):
            d = phrase[(bar % 4) * 8 + k]
            if d is not None:
                add(t0 + k * 2 * step, tone(midi_hz(deg(d, 1) - 12 + 12 * (chord % 2 == 0)), step * 1.8,
                                            "square", 0.09, duty=0.5, decay=step * 3))
        # drums
        if style != "calm":
            for k in range(16):
                if k % 8 == 0:
                    add(t0 + k * step, tone(150, 0.12, "sine", 0.45, 45, decay=0.06))      # kick
                elif k % 8 == 4:
                    add(t0 + k * step, tone(0, 0.09, "noise", 0.18, decay=0.04))          # snare
                elif k % 2 == 0:
                    add(t0 + k * step, tone(0, 0.025, "noise", 0.06, decay=0.01))         # hat
    peak = max(1e-6, max(abs(v) for v in buf))
    g = 0.85 / peak if peak > 0.85 else 1.0
    return [v * g for v in buf]


def write_wav(path, samples):
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(array.array("h", (int(max(-1, min(1, s)) * 32767) for s in samples)).tobytes())
    os.replace(tmp, path)


class AudioManager:
    def __init__(self, core):
        self.core = core
        self.ok = False
        self.sounds = {}
        self.music_path = None
        self.playlist, self.pl_index = [], 0
        self.paused = False
        self._gen_thread = None

    def init(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(RATE, -16, 2, 512)
                pygame.mixer.init()
            self.ok = True
            pygame.mixer.music.set_endevent(pygame.USEREVENT + 7)
        except pygame.error as e:
            log.warning("no audio device: %s", e)
            self.ok = False

    # -- sound effects ---------------------------------------------------------
    def load_pack(self, theme):
        if not self.ok:
            return
        sel = self.core.settings.get("audio.sound_pack", default="theme")
        if sel == "off":
            self.sounds = {}
            return
        pack_id = theme.soundpack if sel == "theme" else sel
        pack = self.core.registry.get("soundpack", pack_id) or {"style": "chiptune"}
        ch = pygame.mixer.get_init()[2]
        if callable(pack.get("render")):
            raw = pack["render"]()        # plugin-provided generator -> {name: [floats]}
        else:
            raw = _pack_sounds(pack.get("style", "chiptune"))
        self.sounds = {k: to_sound(v, ch) for k, v in raw.items()}
        self.apply_volume()

    def apply_volume(self):
        vol = (self.core.settings.get("audio.sfx_volume", default=70) or 0) / 100
        for s in self.sounds.values():
            s.set_volume(vol)
        if self.ok:
            pygame.mixer.music.set_volume((self.core.settings.get("audio.music_volume", default=50) or 0) / 100)

    def play(self, name):
        s = self.sounds.get(name)
        if s:
            s.play()

    # -- music -------------------------------------------------------------------
    def start_music(self, theme):
        if not self.ok:
            return
        mode = self.core.settings.get("audio.music_mode", default="theme")
        pygame.mixer.music.stop()
        self.playlist = []
        if mode == "off":
            return
        if mode in ("playlist", "shuffle"):
            root = self.core.paths.music
            files = sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in MUSIC_EXTS) if root.is_dir() else []
            if mode == "shuffle":
                random.shuffle(files)
            if files:
                self.playlist, self.pl_index = files, 0
                self._play_file(files[0], loops=0)
                return
            mode = "theme"   # empty folder → fall back to theme music
        # a theme may ship its own track
        if theme.dir and theme.music.get("file"):
            p = os.path.join(theme.dir, theme.music["file"])
            if os.path.isfile(p):
                self._play_file(p, loops=-1)
                return
        spec = dict(theme.music or {})
        key = hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]
        path = str(self.core.paths.cache / f"music-{theme.id}-{key}.wav")
        if os.path.isfile(path):
            self._play_file(path, loops=-1)
            return

        def gen():
            try:
                write_wav(path, compose(spec))
                if self.music_path is None or self.music_path.endswith(".wav"):
                    pygame.event.post(pygame.event.Event(pygame.USEREVENT + 8, path=path))
            except Exception:
                log.exception("music generation failed")
        self._gen_thread = threading.Thread(target=gen, daemon=True, name="music-gen")
        self._gen_thread.start()

    def _play_file(self, path, loops=-1):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(loops, fade_ms=1200)
            self.music_path = path
            self.apply_volume()
        except pygame.error as e:
            log.warning("cannot play %s: %s", path, e)

    def on_event(self, ev):
        if ev.type == pygame.USEREVENT + 8 and self.core.settings.get("audio.music_mode", default="theme") != "off":
            self._play_file(ev.path, loops=-1)
        elif ev.type == pygame.USEREVENT + 7 and self.playlist and not self.paused:
            self.pl_index = (self.pl_index + 1) % len(self.playlist)
            self._play_file(self.playlist[self.pl_index], loops=0)

    def now_playing(self):
        if self.playlist:
            return os.path.splitext(os.path.basename(self.playlist[self.pl_index]))[0]
        return None

    def duck(self):
        if self.ok:
            self.paused = True
            pygame.mixer.music.fadeout(400)

    def unduck(self, theme):
        if self.ok:
            self.paused = False
            self.start_music(theme)
