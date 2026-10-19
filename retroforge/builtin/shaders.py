"""Built-in video filters.

``slang`` paths are relative to the libretro slang-shaders tree
(/usr/share/libretro/shaders/shaders_slang on the image). ``reshade``
effects are applied by gamescope for standalone emulators. The launcher skips
(and logs) any file that is missing, so a broken path never blocks a game.
"""
from ..model import Shader

SHADERS = [
    Shader("none", "Aus (scharfe Pixel)", weight=0, order=0),
    Shader("crt-pi", "CRT Pi (leicht)", "crt/crt-pi.slangp", "crt-pi.fx", weight=1, tags=("crt",), order=10),
    Shader("crt-easymode", "CRT Easymode", "crt/crt-easymode.slangp", None, weight=2, tags=("crt",), order=11),
    Shader("crt-geom", "CRT Geom (gewölbt)", "crt/crt-geom.slangp", "CRT-Geom.fx", weight=2, tags=("crt",), order=12),
    Shader("crt-lottes", "CRT Lottes", "crt/crt-lottes.slangp", "crt-lottes.fx", weight=3, tags=("crt",), order=13),
    Shader("crt-guest", "CRT Guest Advanced", "crt/crt-guest-advanced.slangp", None, weight=4, tags=("crt",), order=14),
    Shader("crt-royale", "CRT Royale (aufwendig)", "crt/crt-royale.slangp", None, weight=5, tags=("crt",), order=15),
    Shader("scanlines", "Scanlines", "scanlines/scanline.slangp", "scanlines.fx", weight=1, tags=("crt",), order=20),
    Shader("ntsc", "NTSC Composite", "ntsc/ntsc-adaptive.slangp", None, weight=3, tags=("crt",), order=21),
    Shader("lcd-grid", "LCD-Raster (Handheld)", "handheld/lcd-grid-v2.slangp", None, weight=2,
           tags=("handheld",), order=30),
    Shader("dmg", "Game-Boy-Punktmatrix", "handheld/gameboy.slangp", None, weight=2, tags=("handheld",), order=31),
    Shader("sharp-bilinear", "Sharp Bilinear", "interpolation/sharp-bilinear-simple.slangp", None, weight=1,
           tags=("scale",), order=40),
    Shader("xbrz", "xBRZ Glättung", "xbrz/xbrz-freescale.slangp", None, weight=3, tags=("scale",), order=41),
    Shader("scalefx", "ScaleFX", "scalefx/scalefx.slangp", None, weight=3, tags=("scale",), order=42),
    Shader("hq4x", "HQ4x", "hqx/hq4x.slangp", None, weight=2, tags=("scale",), order=43),
    Shader("fsr", "AMD FSR (Upscaling)", "fsr/fsr.slangp", None, gamescope_filter="fsr", weight=2,
           tags=("upscale",), order=50),
    Shader("nis", "NVIDIA Image Scaling", None, None, gamescope_filter="nis", weight=2, tags=("upscale",), order=51),
]
