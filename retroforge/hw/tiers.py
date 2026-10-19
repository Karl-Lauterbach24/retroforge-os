"""Turns raw hardware info into capability scores and per-system verdicts.

* CPU score  ≈ single-thread performance expressed in "GHz of a modern core"
  (clock × estimated IPC of the micro-architecture).
* GPU class  0 … 5:
    0  no 3D acceleration (framebuffer / llvmpipe)
    1  GLES2-class   (VideoCore IV, Mali-400, VMs)
    2  GLES3/GL3.3   (Pi 4, Intel HD ≤ Gen8, Mali Midgard, old Radeon)
    3  entry Vulkan  (Pi 5, Intel UHD Gen9–11, Mali Valhall, Vega APUs)
    4  mid Vulkan    (Intel Xe/Arc iGPU, RDNA2/3 APUs, ≥4 GB dGPUs)
    5  high          (≥8 GB dGPUs)
* Every emulator has a min/rec :class:`~retroforge.model.Req`; a system's
  verdict is the best verdict over its emulators.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..model import Req
from .probe import HardwareInfo

# Status levels
UNAVAILABLE = 0    # no emulator exists (yet)
IMPOSSIBLE = 1     # hard blocker: architecture, ISA, Vulkan
EXPERIMENTAL = 2   # slightly below minimum or emulator flagged experimental
PLAYABLE = 3       # minimum met
FULL = 4           # recommended met

STATUS_LABEL = {
    UNAVAILABLE: "kein Emulator",
    IMPOSSIBLE: "nicht möglich",
    EXPERIMENTAL: "experimentell",
    PLAYABLE: "spielbar",
    FULL: "flüssig",
}

# IPC estimates for ARM cores, keyed by "implementer:part".
ARM_IPC = {
    "0x41:0xb76": 0.25, "0x41:0xc07": 0.30, "0x41:0xc09": 0.40, "0x41:0xc0f": 0.55,
    "0x41:0xc0d": 0.55, "0x41:0xc0e": 0.55, "0x41:0xd03": 0.45, "0x41:0xd04": 0.40,
    "0x41:0xd05": 0.50, "0x41:0xd07": 0.65, "0x41:0xd08": 0.80, "0x41:0xd09": 0.85,
    "0x41:0xd0a": 0.95, "0x41:0xd0b": 1.10, "0x41:0xd0c": 1.10, "0x41:0xd0d": 1.20,
    "0x41:0xd41": 1.30, "0x41:0xd44": 1.45, "0x41:0xd46": 0.55, "0x41:0xd47": 1.35,
    "0x41:0xd48": 1.55, "0x41:0xd4d": 1.40, "0x41:0xd4e": 1.65, "0x41:0xd80": 0.60,
    "0x41:0xd81": 1.45, "0x41:0xd82": 1.75, "0x51:0x001": 1.90, "0x61:apple": 2.00,
}

LOW_POWER_X86 = ("atom", "celeron n", "pentium n", "pentium silver", "intel(r) n",
                 "processor n", "athlon silver", "a4-", "a6-", "e-350", "e-450", "geode", "via ")


def cpu_score(hw: HardwareInfo) -> float:
    ghz = (hw.max_mhz or 1500) / 1000.0
    isa = set(hw.isa)
    if hw.family in ("x86_64", "x86"):
        if "avx512f" in isa or "vaes" in isa:
            ipc = 1.55
        elif "avx2" in isa:
            ipc = 1.30
        elif "avx" in isa:
            ipc = 1.05
        elif "sse4_2" in isa:
            ipc = 0.85
        elif "sse4_1" in isa or "ssse3" in isa:
            ipc = 0.70
        elif "sse3" in isa or "pni" in isa:
            ipc = 0.55
        else:
            ipc = 0.40
        if any(t in hw.cpu_model.lower() for t in LOW_POWER_X86):
            ipc *= 0.8
    elif hw.family in ("arm64", "arm32"):
        known = [ARM_IPC[p] for p in hw.cpu_parts if p in ARM_IPC]
        ipc = max(known) if known else (0.8 if hw.family == "arm64" else 0.4)
    elif hw.family == "riscv64":
        ipc = 0.6
    else:
        ipc = 0.6
    return round(ghz * ipc, 2)


def _intel_gpu_class(device_id):
    from .probe import _intel_gen, _intel_is_discrete
    if _intel_is_discrete(device_id):
        return 5
    gen = _intel_gen(device_id)
    return 4 if gen >= 12 else 3 if gen >= 9 else 2 if gen >= 7 else 1


RDNA_APU = ("0x1681", "0x15bf", "0x15c8", "0x1900", "0x1901", "0x150e", "0x163f", "0x1435")


def gpu_class(hw: HardwareInfo) -> int:
    g = hw.gpu
    name = g.name.lower()
    if not hw.gpus or g.vendor == "firmware" or "llvmpipe" in name:
        return 0
    if g.vendor == "virtual":
        return 1
    if g.vendor == "broadcom":
        if "VII" in g.name:
            return 3
        return 2 if g.driver == "v3d" or "VI" in g.name else 1
    if g.vendor == "arm":
        return {"lima": 1, "panfrost": 2, "panthor": 3}.get(g.driver, 2)
    if g.vendor == "qualcomm":
        return 4 if "x1" in hw.board.lower() or "snapdragon x" in hw.cpu_model.lower() else 3
    if g.vendor == "vivante":
        return 1
    if g.vendor == "apple":
        return 4
    if g.vendor == "intel":
        if g.driver == "windows" and not g.device_id:
            if "arc" in name and not g.integrated:
                return 5
            return 4 if ("iris xe" in name or "arc" in name) else 3 if "uhd" in name or "iris" in name else 2
        return _intel_gpu_class(g.device_id)
    if g.vendor == "amd":
        if g.driver == "radeon":
            return 2
        if g.integrated:
            return 4 if g.device_id in RDNA_APU or "780m" in name or "680m" in name or "890m" in name else 3
        return 5 if g.vram_mb >= 7500 else 4 if g.vram_mb >= 3500 else 3
    if g.vendor == "nvidia":
        if g.driver == "nouveau":
            return 3          # no reclocking on many cards → capped
        if g.vram_mb:
            return 5 if g.vram_mb >= 7500 else 4 if g.vram_mb >= 3500 else 3
        return 5 if "rtx" in name else 4 if "gtx" in name else 3
    return 2


def _ver(v):
    try:
        a, b = (v or "0.0").split(".")[:2]
        return int(a), int(b)
    except ValueError:
        return (0, 0)


@dataclass
class Capabilities:
    family: str
    isa: set
    cpu: float
    threads: int
    gpu: int
    ram: float
    vulkan: Optional[str]

    @classmethod
    def from_hw(cls, hw: HardwareInfo, gpu_override=None):
        return cls(family=hw.family, isa=set(hw.isa), cpu=cpu_score(hw), threads=hw.threads,
                   gpu=gpu_class(hw) if gpu_override is None else gpu_override,
                   ram=round(hw.ram_mb / 1024, 1), vulkan=hw.vulkan)


ISA_LABEL = {"avx2": "AVX2", "avx": "AVX", "sse4_1": "SSE4.1", "sse4_2": "SSE4.2", "f16c": "F16C",
             "bmi1": "BMI1", "bmi2": "BMI2", "fma": "FMA", "abm": "LZCNT", "movbe": "MOVBE",
             "avx512f": "AVX-512"}


def check(req: Req, cap: Capabilities):
    """Returns (hard_failures, soft_failures) as lists of German reason strings."""
    hard, soft = [], []
    if req.archs and cap.family not in req.archs:
        hard.append(f"Architektur {cap.family} nicht unterstützt (nur {', '.join(req.archs)})")
    if req.isa and cap.family in ("x86_64", "x86"):
        missing = [ISA_LABEL.get(i, i.upper()) for i in req.isa if i not in cap.isa]
        if missing:
            hard.append("CPU-Befehlssatz fehlt: " + ", ".join(missing))
    if req.vulkan and _ver(cap.vulkan) < _ver(req.vulkan):
        hard.append(f"Vulkan {req.vulkan} benötigt (vorhanden: {cap.vulkan or 'keins'})")
    if req.cpu and cap.cpu < req.cpu:
        soft.append(f"CPU zu schwach ({cap.cpu:.1f} von {req.cpu:.1f})")
    if req.threads > 1 and cap.threads < req.threads:
        soft.append(f"{req.threads} Threads empfohlen (vorhanden: {cap.threads})")
    if req.gpu and cap.gpu < req.gpu:
        soft.append(f"GPU-Klasse {cap.gpu} < {req.gpu}")
    if req.ram and cap.ram + 0.3 < req.ram:
        soft.append(f"RAM {cap.ram:.0f} GB < {req.ram:.0f} GB")
    return hard, soft


def _near_miss(req: Req, cap: Capabilities):
    """Within ~20 % of the minimum → still worth a try."""
    return ((not req.cpu or cap.cpu >= req.cpu * 0.8) and (cap.threads >= req.threads - 2)
            and (not req.gpu or cap.gpu >= req.gpu - 1) and (not req.ram or cap.ram >= req.ram * 0.7))


@dataclass
class Verdict:
    status: int
    emulator: Optional[str] = None
    reasons: List[str] = field(default_factory=list)

    @property
    def label(self):
        return STATUS_LABEL[self.status]


def evaluate_emulator(emu, cap: Capabilities) -> Verdict:
    hard, soft = check(emu.min, cap)
    if hard:
        return Verdict(IMPOSSIBLE, emu.id, hard + soft)
    if soft:
        return Verdict(EXPERIMENTAL if _near_miss(emu.min, cap) else IMPOSSIBLE, emu.id, soft)
    if emu.experimental:
        return Verdict(EXPERIMENTAL, emu.id, [emu.note or "Emulator noch experimentell"])
    hard_r, soft_r = check(emu.rec, cap)
    if hard_r or soft_r:
        return Verdict(PLAYABLE, emu.id, ["Für volle Geschwindigkeit: " + "; ".join(hard_r + soft_r)])
    return Verdict(FULL, emu.id, [])


def evaluate_system(system, registry, cap: Capabilities) -> Verdict:
    best = None
    for eid in system.emulators:
        emu = registry.get("emulator", eid)
        if emu is None:
            continue
        v = evaluate_emulator(emu, cap)
        if best is None or v.status > best.status:
            best = v
    if best is None:
        return Verdict(UNAVAILABLE, None, [system.note or "Für dieses System gibt es noch keinen nutzbaren Emulator."])
    return best


@dataclass
class Assessment:
    cap: Capabilities
    verdicts: Dict[str, Verdict]
    ladder: List[str]                 # ladder system ids, easiest → hardest
    max_console: Optional[str]        # hardest ladder system that is at least PLAYABLE
    next_goal: Optional[str]          # the next rung that isn't reachable

    def status(self, system_id):
        v = self.verdicts.get(system_id)
        return v.status if v else UNAVAILABLE


def assess(hw: HardwareInfo, registry, gpu_override=None) -> Assessment:
    cap = Capabilities.from_hw(hw, gpu_override)
    verdicts = {s.id: evaluate_system(s, registry, cap) for s in registry.all("system")}
    ladder = sorted((s for s in registry.all("system") if s.ladder), key=lambda s: s.demand)
    order = [s.id for s in ladder]
    reachable = [i for i, sid in enumerate(order) if verdicts[sid].status >= PLAYABLE]
    max_console = order[reachable[-1]] if reachable else None
    start = reachable[-1] + 1 if reachable else 0
    next_goal = next((sid for sid in order[start:] if verdicts[sid].status != UNAVAILABLE), None)
    return Assessment(cap, verdicts, order, max_console, next_goal)
