"""Creates a demo userdata folder with dummy ROM files (homebrew titles, no
real game data) so the frontend can be tried without any ROMs.

    python tools/make_demo_library.py [userdata-dir]
"""
import sys
from pathlib import Path

DEMO = {
    "nes": [("Micro Mages (World).nes", b"NES\x1a"), ("Battle Kid - Fortress of Peril (USA).nes", b"NES\x1a"),
            ("Lizard (World).nes", b"NES\x1a"), ("Nova the Squirrel (World).nes", b"NES\x1a"),
            ("Twin Dragons (World).nes", b"NES\x1a"), ("Alter Ego (Europe).nes", b"NES\x1a")],
    "snes": [("Super Boss Gaiden (World).sfc", b""), ("Dottie Flowers (World).sfc", b""),
             ("Unholy Night (Japan).sfc", b"")],
    "gb": [("Tobu Tobu Girl (World).gb", b""), ("Deadeus (World).gb", b""), ("Dangan GB (World).gb", b"")],
    "gba": [("Goodboy Galaxy (World).gba", b""), ("Anguna - Warriors of Virtue (World).gba", b"")],
    "megadrive": [("Xeno Crisis (World).md", b""), ("Tanglewood (Europe).md", b""),
                  ("Demons of Asteborg (World).md", b"")],
    "n64": [("Portal 64 - First Slice (World).z64", b"\x80\x37\x12\x40"), ("Flappy Bird 64 (World).z64", b"\x80\x37\x12\x40")],
    "psx": [("Homebrew Collection (Europe) (Disc 1).chd", b""), ("Homebrew Collection (Europe) (Disc 2).chd", b""),
            ("Homebrew Collection (Europe).m3u", None)],
    "dreamcast": [("Xeno Crisis (World).cdi", b""), ("Ghost Blade HD (World).cdi", b"")],
    "pico8": [("Celeste Classic.p8", b"pico-8 cartridge"), ("Just One Boss.p8", b"pico-8 cartridge")],
    "arcade": [("homebrew-shmup.zip", b"PK\x05\x06" + b"\0" * 18)],
}


def main(root):
    root = Path(root)
    for system, files in DEMO.items():
        d = root / "roms" / system
        d.mkdir(parents=True, exist_ok=True)
        for name, head in files:
            p = d / name
            if head is None:   # m3u playlist referencing the discs
                discs = [f for f, _ in files if f.endswith(".chd")]
                p.write_text("\n".join(discs) + "\n", encoding="utf-8")
            else:
                p.write_bytes(head + b"\0" * (4096 - len(head)))
    (root / "bios").mkdir(parents=True, exist_ok=True)
    (root / "bios" / "scph5501.bin").write_bytes(b"\0" * 16)
    print(f"Demo-Bibliothek angelegt in {root}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "userdata")
