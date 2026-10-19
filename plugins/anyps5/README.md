# AnyPS5-Plugin (PS5, experimentell)

[AnyPS5](https://github.com/boykopovar/AnyPS5) ist **kein Emulator**: Es linkt entschlüsselte PS5-Programme in native
Linux-Programme um und implementiert die PS5-Systembibliotheken nach. Der Zen-2-Code der PS5 läuft direkt auf der
CPU, die GPU-Shader werden nach SPIR-V/Vulkan übersetzt. Stand Oktober 2026 laufen nur wenige Spiele vollständig;
den aktuellen Stand zeigt die [Kompatibilitätsliste](https://alxcbtw.github.io/anyps5-roadmap/).

## Voraussetzungen

- x86-64-Prozessor mit AVX2, FMA, F16C, BMI1/2, LZCNT und MOVBE (Intel ab Haswell, AMD ab Zen). Auf Intel werden
  AMD-spezifische Befehle beim Konvertieren umgeschrieben; Code, den ein Spiel erst zur Laufzeit erzeugt, braucht
  eine AMD-CPU.
- Vulkan 1.3, mindestens GPU-Klasse 4, 16 GB RAM
- RetroForge OS (Linux); die Spiele laufen in gamescope

## Spiel ablegen

```
roms/ps5/<Spielname>.ps5/
    app0/              ← kompletter entschlüsselter Dump
        eboot.bin      ← entschlüsseltes ELF (kein SELF-Container)
        sce_module/
        sce_sys/param.json
        …
```

Beim **ersten Start** konvertiert das Plugin das Spiel (Protokoll: `<Spiel>.ps5/.anyps5/convert.log`) und startet
danach direkt die erzeugte `app.elf`. Die Original-Module werden dafür nur verschoben, nicht kopiert
(`.anyps5/input/`). Im Spiel-Menü (X) gibt es *neu konvertieren* und *Original wiederherstellen*. Ändern sich
Relinker oder Spiel, wird automatisch neu konvertiert.

## Rechtliches

RetroForge und AnyPS5 enthalten keine Spiele, Firmware oder Schlüssel. Ein entschlüsselter Dump stammt von einer
eigenen, gejailbreakten Konsole. Das Umgehen eines Kopierschutzes kann je nach Land verboten sein, in Deutschland
z. B. nach § 95a UrhG, auch für private Kopien. Prüfe die Rechtslage, bevor du Spiele dumpst.
