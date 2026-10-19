"""Plain data types shared by the core and plugins."""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Req:
    """Hardware requirement. ``None``/0 means "don't care"."""
    archs: Optional[Tuple[str, ...]] = None   # arch families: x86_64, x86, arm64, arm32, riscv64
    isa: Tuple[str, ...] = ()                 # e.g. ("avx2",) or ("sse4_1",)
    cpu: float = 0.0                          # single-thread score (≈ GHz of a modern core)
    threads: int = 1
    gpu: int = 0                              # GPU class 0..5 (see hw.tiers)
    ram: float = 0.0                          # GB
    vulkan: Optional[str] = None              # minimum Vulkan API version, e.g. "1.3"


@dataclass
class System:
    id: str
    name: str
    short: str
    maker: str
    year: int
    exts: Tuple[str, ...]
    emulators: Tuple[str, ...] = ()          # first = default
    kind: str = "console"                     # console | handheld | arcade | computer | fantasy
    color: str = "#888888"
    bios: Tuple[str, ...] = ()                # file names expected in /userdata/bios
    demand: int = 0                           # rough difficulty rank for the "console ladder"
    ladder: bool = False                      # show on the hardware ladder (modern consoles)
    icon: str = ""                            # card icon (pad_nes, pad_snes, pad_n64, pad_modern, handheld …)
    note: str = ""
    order: int = 0


@dataclass
class Emulator:
    id: str
    name: str
    kind: str                                 # "libretro" | "standalone"
    min: Req = field(default_factory=Req)
    rec: Req = field(default_factory=Req)
    core: str = ""                            # libretro core name (without _libretro.so)
    binary: str = ""                          # standalone executable / AppImage name
    args: Tuple[str, ...] = ("{rom}",)        # standalone argument template
    features: Tuple[str, ...] = ()            # shaders, upscale, widescreen, rewind, runahead, achievements
    upscale: Optional[Callable] = None        # fn(scale:int) -> extra args or config patches
    source: Optional[dict] = None             # download spec for the emulator manager
    wrap: str = "gamescope"                   # standalone emulators run inside gamescope by default
    experimental: bool = False
    note: str = ""
    order: int = 0


@dataclass
class Shader:
    id: str
    name: str
    slang: Optional[str] = None               # RetroArch preset, relative to shaders_slang/
    reshade: Optional[str] = None             # gamescope ReShade effect (standalone emulators)
    gamescope_filter: Optional[str] = None    # fsr | nis | pixel | linear | nearest
    weight: int = 1                           # GPU cost 1..5 – heavy shaders are hidden on weak GPUs
    tags: Tuple[str, ...] = ()
    order: int = 0


@dataclass
class MenuEntry:
    id: str
    label: str
    action: Callable                          # action(app)
    icon: str = "*"
    section: str = "system"                   # system | power
    order: int = 0


@dataclass
class Collection:
    """Virtual game list shown on the home screen (favourites, recent, ...)."""
    id: str
    name: str
    query: Callable                           # query(core) -> List[Game]
    color: str = "#888888"
    short: str = ""
    order: int = 0
