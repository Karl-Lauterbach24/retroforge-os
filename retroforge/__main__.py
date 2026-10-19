"""Entry point.

    retroforge                 # start the frontend (fullscreen on the OS)
    retroforge --windowed      # development window
    retroforge --probe         # hardware report + console ladder in the terminal
    retroforge --plan KEY      # show the command a game would be launched with
"""
import argparse
import logging
import sys

from . import __version__


def _report(core):
    from .hw import tiers
    hw, a = core.hw, core.assessment
    c = a.cap
    print(f"RetroForge OS {__version__} – Hardware-Bericht\n")
    print(f"  CPU     {hw.cpu_model}  [{hw.family}]")
    print(f"          {hw.cores} Kerne / {hw.threads} Threads, {hw.max_mhz} MHz, Score {c.cpu:.2f}")
    isa = [i for i in ("sse4_1", "sse4_2", "avx", "avx2", "avx512f", "asimd", "neon") if i in hw.isa]
    print(f"          Befehlssätze: {', '.join(isa) or '–'}")
    print(f"  RAM     {c.ram:.1f} GB")
    for g in hw.gpus:
        print(f"  GPU     {g.name}  (Treiber {g.driver or '?'}, {g.vram_mb} MB)")
    print(f"          GPU-Klasse {c.gpu}/5, Vulkan {hw.vulkan or '–'} ({hw.vulkan_source or 'nicht erkannt'})")
    print("\n  Konsolen-Leiter")
    for sid in a.ladder:
        s = core.registry.get("system", sid)
        v = a.verdicts[sid]
        mark = "»" if sid == a.max_console else " "
        bar = "█" * v.status + "░" * (4 - v.status)
        print(f"  {mark} {s.name:<24} {bar} {v.label:<14} {('– ' + v.reasons[0]) if v.reasons else ''}")
    if a.max_console:
        print(f"\n  Höchste lauffähige Konsole: {core.registry.get('system', a.max_console).name}")
    if a.next_goal:
        v = a.verdicts[a.next_goal]
        print(f"  Nächstes Ziel: {core.registry.get('system', a.next_goal).name} – {'; '.join(v.reasons)}")
    total = sum(1 for s in core.registry.all('system') if a.status(s.id) >= tiers.PLAYABLE)
    print(f"\n  {total} von {len(core.registry.all('system'))} Systemen spielbar.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="retroforge", description="RetroForge OS Frontend")
    p.add_argument("--home", help="userdata-Verzeichnis (Standard: /userdata bzw. ./userdata)")
    p.add_argument("--windowed", action="store_true", help="im Fenster starten")
    p.add_argument("--size", default="1280x720", help="Fenstergröße im Fenstermodus")
    p.add_argument("--probe", action="store_true", help="Hardware-Bericht ausgeben und beenden")
    p.add_argument("--plan", metavar="GAME_KEY", help="Startbefehl für ein Spiel anzeigen")
    p.add_argument("--scan", action="store_true", help="Bibliothek scannen und Statistik ausgeben")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    from .core import Core
    if args.probe or args.plan or args.scan:
        core = Core(args.home).boot(do_probe=True, scan=bool(args.plan or args.scan))
        if args.probe:
            _report(core)
        if args.scan:
            for sid, games in core.library.games.items():
                print(f"{sid:<14} {len(games)} Spiele")
        if args.plan:
            game = core.library.get(args.plan)
            if not game:
                print("Unbekanntes Spiel:", args.plan)
                return 1
            plan = core.launcher.plan(game)
            print(plan.describe())
            for n in plan.notes:
                print("  Hinweis:", n)
        return 0

    from .ui.app import App
    w, h = (int(x) for x in args.size.lower().split("x"))
    return App(Core(args.home), windowed=args.windowed, size=(w, h)).run()


if __name__ == "__main__":
    sys.exit(main())
