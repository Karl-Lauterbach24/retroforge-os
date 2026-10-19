# Disc-Plugin: direkt spielen oder als CHD sichern

Disc einlegen, RetroForge erkennt das System und fragt: **Direkt spielen**, **Auf Festplatte sichern (CHD)** oder
**Abbrechen**. Über *Disc-Laufwerk* in der Schnellleiste lässt sich eine eingelegte Disc auch manuell öffnen.

| System | Erkennung | Direkt spielen | Sichern |
|---|---|---|---|
| PlayStation | `SYSTEM.CNF` (BOOT) inkl. Seriennummer | DuckStation (`/dev/srN`), sonst Beetle PSX HW | CD (cdrdao) → CHD |
| PlayStation 2 | `SYSTEM.CNF` (BOOT2) | PCSX2 (`/dev/srN`) | DVD (Sektorkopie) → CHD |
| Saturn | Header `SEGA SEGASATURN` | Beetle Saturn (`cdrom://`) | CD → CHD |
| Mega-CD | Header `SEGADISCSYSTEM` | Genesis Plus GX (`cdrom://`) | CD → CHD |
| PC Engine CD | Datenspur hinter der Audiospur (TOC) | Beetle PCE Fast (`cdrom://`) | CD → CHD |
| PC-FX | Kennung `PC-FX:Hu_CD-ROM` | Beetle PC-FX (`cdrom://`) | CD → CHD |
| 3DO | Opera-Dateisystem | Opera (`cdrom://`) | CD → CHD |
| PC-CD-ROM | ISO 9660 ohne Konsolenkennung | – | CD → CHD (für DOSBox Pure) |
| PS3 | `PS3_DISC.SFB` | ❌ | ❌ verschlüsselt, Hinweis auf ps3-disc-dumper + IRD |
| PS4 / PS5 / Xbox One/Series | Blu-ray ohne lesbares Dateisystem | ❌ | ❌ verschlüsselt, Schlüssel nur in der Konsole |
| GameCube / Wii / Wii U / Xbox / Dreamcast | nicht lesbar | ❌ | ❌ Format für PC-Laufwerke unlesbar |

Gemischte CDs (Audio + Daten), deren Datenspur sich nicht eindeutig zuordnen lässt, fragen nach dem System.

## Sichern

- **CD:** `cdrdao read-cd --read-raw` (inkl. Audiospuren) → `toc2cue` → `chdman createcd`
- **DVD:** Sektorkopie mit Wiederholungen bei Lesefehlern → `chdman createdvd` (ohne passendes chdman bleibt die `.iso`)
- Ziel: `roms/<system>/<Name>.chd`; die Bibliothek wird danach neu gescannt.
- **Verifizieren:** Liegen Redump- oder No-Intro-DATs (logiqx-XML) in `/userdata/system/dats/`, wird die Kopie
  per SHA-1 geprüft und nach dem DAT-Eintrag benannt. Bei CDs mit mehreren Spuren passt der Hash der
  zusammengefassten `.bin` nicht zu den einzelnen Spuren in der DAT, dort bleibt die Prüfung leer.

Benötigt `cdrdao` und `mame-tools` (im OS-Image enthalten). Unter Windows (Entwicklungsmodus) gibt es keine
Laufwerkserkennung.

## Rechtliches

RetroForge umgeht keinen Kopierschutz. Sichere nur Discs, die dir gehören. Ob eine Privatkopie erlaubt ist,
hängt vom Land ab.
