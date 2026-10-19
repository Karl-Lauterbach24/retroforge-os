# Changelog

## Unveröffentlicht

### Neu
- **Klare Meldungen für nicht unterstützte Discs:** Jede Art (PS3, verschlüsselte Blu-ray, unlesbare Disc,
  Audio-CD, unbekannt) bekommt den Titel „Nicht unterstützt: …“, eine Begründung und einen Hinweis, was stattdessen geht.
- **Plugin `ps3-disc` (optional, standardmäßig aus):** sichert PS3-Discs über das extern installierte
  ps3-disc-dumper und legt das Ergebnis nach `roms/ps3/`. Es umgeht einen wirksamen Kopierschutz; die Nutzung erfolgt
  auf eigene Gefahr. Die Warnung muss beim Aktivieren und vor jeder Nutzung bestätigt werden. Das Plugin enthält keinen
  Entschlüsselungscode und lädt nichts automatisch herunter.
- Plugins können eine Warnung in `plugin.json` (`"warning"`) angeben; der Plugin-Bildschirm verlangt dann eine
  Bestätigung und markiert sie mit „eigene Gefahr“.
- Disc-Plugin: andere Plugins können über `disc_handler` Aktionen für nicht unterstützte Discs anbieten.
- Dialoge brechen lange Hinweistexte um und heben Warnungen farblich hervor.
- OS-Image: `udisks2` und Polkit-Regel zum Einhängen von Discs.

## 0.1.1 – 2026-10-19 · Vorschau

### Neu
- **Plugin `disc`:** CDs und DVDs beim Einlegen erkennen (PS1, PS2, Saturn, Mega-CD, PC Engine CD, PC-FX, 3DO, PC-CD-ROMs) und entweder **direkt vom Laufwerk spielen** (DuckStation, PCSX2, RetroArch-Kerne über `cdrom://`) oder **als CHD sichern** (cdrdao mit Audiospuren bzw. Sektorkopie, `chdman`). Optionaler Abgleich mit Redump-/No-Intro-DATs in `/userdata/system/dats`, der auch den richtigen Spielnamen liefert. Verschlüsselte oder für PC-Laufwerke unlesbare Discs (PS3/PS4/PS5, Xbox, GameCube/Wii, Dreamcast) werden erkannt und erklärt.
- ISO-9660-Leser im Kern: Der ROM-Import unterscheidet PS1 und PS2 jetzt zuverlässig über `SYSTEM.CNF`.
- **Plugin `anyps5`:** experimentelle PS5-Unterstützung über [AnyPS5](https://github.com/boykopovar/AnyPS5) (Relinker statt Emulation). Das Spiel wird beim ersten Start für Linux konvertiert und danach direkt gestartet; die Original-Module bleiben erhalten und lassen sich wiederherstellen. Installation von Relinker und Systembibliotheken aus den offiziellen Releases, AMD→Intel-Umschreibung automatisch nach CPU.
- Hardware-Leiter prüft jetzt auch BMI2, FMA, LZCNT und MOVBE (Zen-2-Befehlssatz der PS5).
- Emulator-Manager: Plugins können eigene Installer mitbringen (`source = {"type": "custom", ...}`).
- OS-Image: Zugriff auf `/dev/udmabuf` für die Frontend-Sitzung; `cdrdao`, `mame-tools` (chdman) und die Gruppe `cdrom`.

### Korrigiert
- Hinweis zur PS5: Es gibt zwar keinen Emulator, einzelne Spiele laufen aber experimentell über AnyPS5.
- Hardware-Bericht (`--probe`) bricht in Windows-Konsolen (cp1252) nicht mehr ab.

## 0.1.0 – 2026-10-19 · erstes Release (Vorschau)

### Frontend
- Konsolen-Karussell mit prozeduralen, kantengeglätteten Icons je Ära (8-Bit, 16-Bit, N64, modern, Handheld, Arcade, Computer)
- Spielelisten mit Detailpanel, Tippen-zum-Suchen, Buchstabensprung, Favoriten, Region-Badges, Cover-Unterstützung
- Sammlungen „Zuletzt gespielt“, „Favoriten“ (Plugins können weitere hinzufügen)
- Einstellungen in drei Ebenen (global → System → Spiel) mit Vererbungsanzeige; 25 Optionen inkl. 17 Filter/Shader, interne Auflösung, FSR/NIS, Run-Ahead, Rewind, Emulatorwahl
- 6 Themes mit animierten, prozeduralen Hintergründen; synthetisierte Chiptune-Musik pro Theme, 3 Menü-Soundpacks, eigene Musik-Playlist
- Import von USB/Import-Ordner mit Header-Erkennung für ROMs und BIOS; BIOS-Check; Emulator-Manager mit Installation bei Bedarf
- Tastatur und Gamepads (SDL GameController, Hotplug, Nintendo-Layout), Energiesparmodus, 30 fps auf schwacher Hardware

### Kern
- Hardware-Erkennung (CPU/IPC, Befehlssätze, GPU-Klasse 0–5, Vulkan, RAM) und Konsolen-Leiter mit Begründungen
- 63 Systeme, 65 Emulatoren (libretro + Standalone) mit Mindest-/Empfehlungsanforderungen
- Launcher: RetroArch-Append-Config, Core-Optionen, INI-Patches, gamescope-Wrapper (FSR/NIS/ReShade), CPU-Governor pro Spiel
- Plugin-API v1 (Systeme, Emulatoren, Shader, Settings, Themes, Hintergründe, Screens, Menüs, Sammlungen, ROM-Detektoren, Hooks)
- 6 mitgelieferte Plugins: Statistik, Spielstand-Backup, Web-Upload (PIN), Bildschirmschoner, RetroAchievements, Saison-Themes

### OS-Image
- Image-Build auf Debian-Basis für 6 Profile (pc-x86_64, pc-i686, arm64-uefi, rpi-arm64, rpi-armhf, riscv64)
- Breite Treiberbasis (Mesa, non-free-Firmware), NVIDIA-Treiberwahl beim Boot, exFAT-Datenpartition

### Bekannte Einschränkungen
- Der Image-Build ist in diesem Release **noch nicht auf echter Hardware verifiziert**; Paketnamen, Shader-Pfade und Release-Asset-Muster können Anpassungen brauchen.
- Xbox Series und Switch 2 haben keinen Emulator (Stand 2026); PS4 und Xbox 360 gelten als experimentell. Für die PS5 siehe 0.1.1 (AnyPS5).
