"""Hardware probing without external dependencies.

Linux (the OS target) is probed via /proc and /sys plus ``vulkaninfo`` when
available. Windows/macOS probing exists only so the frontend can be developed
on a desktop machine.
"""
import glob
import json
import logging
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import List, Optional

log = logging.getLogger("retroforge.hw")


@dataclass
class GpuInfo:
    name: str = "Unbekannt"
    vendor: str = ""          # amd | intel | nvidia | arm | broadcom | qualcomm | vivante | apple | virtual | ...
    vendor_id: str = ""
    device_id: str = ""
    driver: str = ""
    vram_mb: int = 0
    integrated: Optional[bool] = None
    compatible: str = ""      # device-tree compatible string (SoC GPUs)


@dataclass
class HardwareInfo:
    arch: str = ""            # raw machine string
    family: str = "other"     # x86_64 | x86 | arm64 | arm32 | riscv64 | ppc64 | other
    cpu_model: str = ""
    cores: int = 1
    threads: int = 1
    max_mhz: int = 0
    isa: List[str] = field(default_factory=list)
    cpu_parts: List[str] = field(default_factory=list)   # ARM "implementer:part"
    ram_mb: int = 0
    gpus: List[GpuInfo] = field(default_factory=list)
    vulkan: Optional[str] = None
    vulkan_source: str = ""   # vulkaninfo | inferred | ""
    board: str = ""
    os: str = ""
    is_vm: bool = False
    battery: bool = False

    @property
    def gpu(self) -> GpuInfo:
        """The GPU used for gaming: prefer discrete, then the one with most VRAM."""
        if not self.gpus:
            return GpuInfo()
        return sorted(self.gpus, key=lambda g: (g.integrated is False, g.vram_mb), reverse=True)[0]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d["gpus"] = [GpuInfo(**g) for g in d.get("gpus", [])]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


def arch_family(machine):
    m = (machine or "").lower()
    if m in ("x86_64", "amd64", "x64"):
        return "x86_64"
    if re.fullmatch(r"i[3-6]86|x86|ia32", m):
        return "x86"
    if m in ("aarch64", "arm64", "armv8b", "aarch64_be"):
        return "arm64"
    if m.startswith("arm"):
        return "arm32"
    if m.startswith("riscv64"):
        return "riscv64"
    if m.startswith("ppc64") or m.startswith("powerpc64"):
        return "ppc64"
    return "other"


PCI_VENDORS = {
    "0x1002": "amd", "0x1022": "amd", "0x8086": "intel", "0x10de": "nvidia",
    "0x1af4": "virtual", "0x15ad": "virtual", "0x80ee": "virtual", "0x1234": "virtual",
    "0x1414": "virtual", "0x5143": "qualcomm", "0x1ed5": "moore-threads",
}

DRIVER_VENDORS = {
    "vc4": "broadcom", "v3d": "broadcom", "lima": "arm", "panfrost": "arm", "panthor": "arm",
    "msm": "qualcomm", "etnaviv": "vivante", "rockchip": "arm", "sun4i-drm": "arm",
    "meson": "arm", "mali": "arm", "asahi": "apple", "virtio_gpu": "virtual",
    "vmwgfx": "virtual", "bochs-drm": "virtual", "qxl": "virtual", "simpledrm": "firmware",
    "efifb": "firmware", "imagination": "imagination", "powervr": "imagination",
}


def _read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip().strip("\x00")
    except OSError:
        return default


def _run(cmd, timeout=6):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             errors="replace")
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------
def _probe_linux(hw: HardwareInfo):
    info = _read("/proc/cpuinfo")
    flags, parts, models = set(), set(), []
    physical = set()
    cur = {}
    for line in info.splitlines() + [""]:
        if not line.strip():
            if cur:
                physical.add((cur.get("physical id", "0"), cur.get("core id", cur.get("processor"))))
            cur = {}
            continue
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        cur[k] = v
        if k in ("flags", "Features", "isa"):
            flags.update(v.lower().split())
        elif k == "CPU part":
            parts.add(f"{cur.get('CPU implementer', '0x41')}:{v.lower()}")
        elif k in ("model name", "Model", "Hardware", "cpu model", "uarch") and v:
            models.append(v)
    hw.isa = sorted(flags)
    hw.cpu_parts = sorted(parts)
    hw.cpu_model = models[0] if models else platform.processor()
    hw.threads = os.cpu_count() or 1
    hw.cores = max(1, min(len(physical), hw.threads)) if physical else hw.threads

    mhz = 0
    for f in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq"):
        try:
            mhz = max(mhz, int(_read(f, "0")) // 1000)
        except ValueError:
            pass
    if not mhz:
        m = re.findall(r"cpu MHz\s*:\s*([\d.]+)", info)
        if m:
            mhz = int(max(float(x) for x in m))
    hw.max_mhz = mhz

    m = re.search(r"MemTotal:\s+(\d+)", _read("/proc/meminfo"))
    hw.ram_mb = int(m.group(1)) // 1024 if m else 0
    hw.board = _read("/proc/device-tree/model") or _read("/sys/class/dmi/id/product_name")
    sysvendor = _read("/sys/class/dmi/id/sys_vendor").lower()
    hw.is_vm = "hypervisor" in flags or any(
        v in sysvendor for v in ("qemu", "vmware", "innotek", "virtualbox", "microsoft corporation", "xen"))
    hw.battery = bool(glob.glob("/sys/class/power_supply/BAT*"))
    osr = _read("/etc/os-release")
    m = re.search(r'PRETTY_NAME="?([^"\n]+)', osr)
    hw.os = m.group(1) if m else "Linux"

    for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        if "-" in os.path.basename(card):
            continue   # connector entries like card0-HDMI-A-1
        dev = os.path.join(card, "device")
        g = GpuInfo()
        drv = os.path.realpath(os.path.join(dev, "driver"))
        g.driver = os.path.basename(drv) if os.path.exists(drv) else ""
        g.vendor_id = _read(os.path.join(dev, "vendor")).lower()
        g.device_id = _read(os.path.join(dev, "device")).lower()
        g.vendor = PCI_VENDORS.get(g.vendor_id) or DRIVER_VENDORS.get(g.driver, "")
        g.compatible = _read(os.path.join(dev, "of_node", "compatible")).replace("\x00", " ")
        vram = _read(os.path.join(dev, "mem_info_vram_total"))
        if vram.isdigit():
            g.vram_mb = int(vram) // (1024 * 1024)
        if g.vendor == "intel":
            g.integrated = not _intel_is_discrete(g.device_id)
        elif g.vendor == "amd" and g.vram_mb:
            g.integrated = g.vram_mb < 3000   # APUs only carve out 0.5–2 GB
        elif g.vendor == "nvidia":
            g.integrated = "tegra" in g.compatible
        elif g.vendor in ("arm", "broadcom", "qualcomm", "vivante", "apple", "imagination"):
            g.integrated = True
        g.name = _gpu_name_linux(g, hw.board)
        if g.vendor == "firmware" and hw.gpus:
            continue
        hw.gpus.append(g)

    if any(g.vendor == "nvidia" and g.driver == "nvidia" for g in hw.gpus) and shutil.which("nvidia-smi"):
        out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        for line, g in zip(out.splitlines(), [g for g in hw.gpus if g.vendor == "nvidia"]):
            name, _, mem = line.rpartition(",")
            g.name = name.strip() or g.name
            if mem.strip().isdigit():
                g.vram_mb = int(mem.strip())
    _probe_vulkan(hw)


def _intel_is_discrete(device_id):
    d = device_id.lower()
    return d.startswith("0x56") or d.startswith("0xe20") or d.startswith("0xe21")


def _gpu_name_linux(g, board):
    if g.vendor == "broadcom":
        return "VideoCore " + ("VII" if "bcm2712" in g.compatible or "Pi 5" in board else
                              "VI" if g.driver == "v3d" else "IV")
    if g.vendor == "arm":
        return {"lima": "ARM Mali Utgard", "panfrost": "ARM Mali (Panfrost)",
                "panthor": "ARM Mali Valhall (Panthor)"}.get(g.driver, "ARM Mali")
    if g.vendor == "qualcomm":
        return "Qualcomm Adreno"
    names = {"amd": "AMD Radeon", "intel": "Intel Graphics", "nvidia": "NVIDIA GeForce",
             "virtual": "Virtuelle GPU", "firmware": "Framebuffer (keine 3D-Beschleunigung)"}
    base = names.get(g.vendor, g.driver or "GPU")
    return f"{base} [{g.device_id}]" if g.device_id else base


def _probe_vulkan(hw):
    exe = shutil.which("vulkaninfo")
    if not exe:
        return
    out = _run([exe, "--summary"], timeout=8)
    best = None
    blocks = re.split(r"\nGPU\d+:", out)
    for b in blocks[1:]:
        if "PHYSICAL_DEVICE_TYPE_CPU" in b:
            continue   # llvmpipe / software – doesn't count
        m = re.search(r"apiVersion\s*=\s*(\d+)\.(\d+)", b)
        if m:
            v = (int(m.group(1)), int(m.group(2)))
            best = max(best, v) if best else v
    if best:
        hw.vulkan = f"{best[0]}.{best[1]}"
        hw.vulkan_source = "vulkaninfo"


# ---------------------------------------------------------------------------
# Windows / macOS (development hosts)
# ---------------------------------------------------------------------------
def _probe_windows(hw):
    import ctypes

    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = MEMSTAT()
    st.dwLength = ctypes.sizeof(MEMSTAT)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        hw.ram_mb = st.ullTotalPhys // (1024 * 1024)
    feat = ctypes.windll.kernel32.IsProcessorFeaturePresent
    for flag, pf in (("sse3", 13), ("ssse3", 36), ("sse4_1", 37), ("sse4_2", 38),
                     ("avx", 39), ("avx2", 40), ("avx512f", 41)):
        try:
            if feat(pf):
                hw.isa.append(flag)
        except OSError:
            pass
    ps = ("$c=Get-CimInstance Win32_Processor|Select-Object -First 1 Name,MaxClockSpeed,NumberOfCores;"
          "$g=@(Get-CimInstance Win32_VideoController|Select-Object Name,AdapterRAM,PNPDeviceID,DriverVersion);"
          "@{cpu=$c;gpu=$g}|ConvertTo-Json -Depth 3 -Compress")
    out = _run(["powershell", "-NoProfile", "-Command", ps], timeout=15)
    try:
        d = json.loads(out)
        c = d.get("cpu") or {}
        hw.cpu_model = (c.get("Name") or "").strip()
        hw.max_mhz = int(c.get("MaxClockSpeed") or 0)
        hw.cores = int(c.get("NumberOfCores") or hw.cores)
        gl = d.get("gpu") or []
        for g in gl if isinstance(gl, list) else [gl]:
            name = g.get("Name") or "GPU"
            m = re.search(r"VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})", g.get("PNPDeviceID") or "", re.I)
            gi = GpuInfo(name=name, driver="windows")
            if m:
                gi.vendor_id, gi.device_id = "0x" + m.group(1).lower(), "0x" + m.group(2).lower()
                gi.vendor = PCI_VENDORS.get(gi.vendor_id, "")
            ram = g.get("AdapterRAM") or 0
            gi.vram_mb = int(ram) // (1024 * 1024) if ram else 0
            gi.integrated = _win_is_integrated(gi)
            low = name.lower()
            if "basic display" in low or "remote" in low or "virtual" in low or "parsec" in low:
                gi.vendor = "virtual"
            hw.gpus.append(gi)
    except (ValueError, TypeError, AttributeError):
        pass
    # Win32_Processor reports the base clock; estimate the boost clock instead.
    hw.max_mhz = max(hw.max_mhz, bench_mhz())
    if "avx2" in hw.isa:   # every AVX2 CPU also has these (not exposed by IsProcessorFeaturePresent)
        hw.isa += [f for f in ("f16c", "bmi1", "fma") if f not in hw.isa]
    real = [g for g in hw.gpus if g.vendor not in ("virtual", "firmware", "")]
    if real:
        hw.gpus = real
    hw.os = f"Windows {platform.release()} (Entwicklungsmodus)"
    # Windows drivers for all three vendors ship Vulkan 1.3 on any GPU that can run modern emulators.
    if any(g.vendor in ("amd", "nvidia", "intel") for g in hw.gpus):
        hw.vulkan, hw.vulkan_source = "1.3", "inferred"


def bench_mhz():
    """Boost-clock estimate from a tiny single-thread loop (calibrated on a
    4.4 GHz Alder Lake P-core). Only used where the OS hides the boost clock."""
    import time
    best = 9.0
    for _ in range(5):
        t = time.perf_counter()
        x = 0
        for i in range(200000):
            x = (x * 31 + i) & 0xFFFFFFF
        best = min(best, time.perf_counter() - t)
    return int(50.0 / best) if best > 0 else 0


def _win_is_integrated(g):
    n = g.name.lower()
    if g.vendor == "intel":
        return not re.search(r"arc.*[ab]\d{3}", n)   # Arc A380/A770/B580 are discrete
    if g.vendor == "amd":
        return n.strip() in ("amd radeon(tm) graphics", "amd radeon graphics") or bool(re.search(r"\d{3}m\b", n))
    return False if g.vendor == "nvidia" else None


def _probe_macos(hw):
    hw.cpu_model = _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
    mem = _run(["sysctl", "-n", "hw.memsize"]).strip()
    hw.ram_mb = int(mem) // (1024 * 1024) if mem.isdigit() else 0
    hw.os = "macOS (Entwicklungsmodus)"
    if hw.family == "arm64":
        hw.cpu_parts = ["0x61:apple"]
        hw.max_mhz = 3200
        hw.gpus.append(GpuInfo(name="Apple GPU", vendor="apple", integrated=True))
        hw.vulkan, hw.vulkan_source = "1.2", "inferred"   # MoltenVK


# ---------------------------------------------------------------------------
def infer_vulkan(hw: HardwareInfo):
    """Best-effort Vulkan version when vulkaninfo is missing (Mesa defaults)."""
    if hw.vulkan:
        return
    g = hw.gpu
    v = None
    if g.driver in ("amdgpu",):
        v = "1.3"
    elif g.driver == "radeon":
        v = None
    elif g.driver in ("i915", "xe"):
        v = "1.3" if _intel_gen(g.device_id) >= 9 else ("1.2" if _intel_gen(g.device_id) >= 7 else None)
    elif g.driver == "nvidia":
        v = "1.3"
    elif g.driver == "nouveau":
        v = "1.3"   # NVK (Mesa 24.1+) for Turing and newer, otherwise none
    elif g.driver == "v3d":
        v = "1.3" if "Pi 5" in hw.board or "bcm2712" in g.compatible else "1.2"
    elif g.driver == "msm":
        v = "1.3"   # turnip
    elif g.driver == "panthor":
        v = "1.1"
    elif g.driver == "virtio_gpu":
        v = "1.2"   # venus, if the host exposes it
    if v:
        hw.vulkan, hw.vulkan_source = v, "inferred"


def _intel_gen(device_id):
    """Very coarse Intel iGPU generation from the PCI device id."""
    d = (device_id or "").lower().replace("0x", "")
    if len(d) < 2:
        return 0
    p2 = d[:2]
    if p2 in ("56", "e2", "64", "7d", "a7", "46", "9a", "4c", "4e", "8a"):
        return 12 if p2 != "8a" else 11
    if p2 in ("19", "59", "3e", "9b", "87", "31", "5a"):
        return 9
    if p2 in ("16", "22"):
        return 8
    if p2 in ("04", "0a", "0d", "0c", "0f", "01"):
        return 7
    return 0


def probe() -> HardwareInfo:
    hw = HardwareInfo()
    hw.arch = platform.machine()
    hw.family = arch_family(hw.arch)
    hw.threads = os.cpu_count() or 1
    hw.cores = hw.threads
    system = platform.system()
    try:
        if system == "Linux":
            _probe_linux(hw)
        elif system == "Windows":
            _probe_windows(hw)
        elif system == "Darwin":
            _probe_macos(hw)
    except Exception:
        log.exception("hardware probe failed partially")
    infer_vulkan(hw)
    if not hw.cpu_model:
        hw.cpu_model = platform.processor() or hw.arch
    return hw
