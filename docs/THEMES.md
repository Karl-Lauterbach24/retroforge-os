# Themes erstellen

Ein Theme ist ein Ordner `/userdata/themes/<id>/` mit einer `theme.json`. Bilder, Schriften oder Musik dürfen daneben liegen.

```json
{
  "id": "mein-theme",
  "name": "Mein Theme",
  "colors": {
    "bg": "#0d0221", "bg2": "#2b1055",
    "panel": "#12062ccc", "panel2": "#24104ef0",
    "accent": "#ff2a6d", "accent2": "#05d9e8",
    "text": "#f6f1ff", "muted": "#a89cc8",
    "good": "#3df5a7", "ok": "#4cc9f0", "warn": "#ffd166", "bad": "#ff4d6d", "off": "#6c6c80"
  },
  "background": {"type": "synthwave", "speed": 0.35},
  "title_font": "pixel",
  "font": "sans",
  "radius": 16,
  "crt": false,
  "soundpack": "chiptune",
  "music": {"tempo": 108, "root": 57, "scale": "minor", "progression": [0, 5, 3, 4], "style": "arp"}
}
```

Farben mit 8 Stellen (`#rrggbbaa`) sind halbtransparent. Bei `panel` lässt das den animierten Hintergrund durchscheinen.

## Hintergründe (`background.type`)

| Typ | Parameter | Beschreibung |
|---|---|---|
| `gradient` | `top`, `bottom` | statischer Verlauf (am sparsamsten) |
| `synthwave` | `speed`, `sky_top`, `sky_bottom`, `sun_top`, `sun_bottom`, `grid`, `floor` | Retro-Sonne, Berge, bewegtes Perspektivgitter |
| `starfield` | `speed`, `count`, `tint` | Flug durch Sterne |
| `phosphor` | – | grünes Terminal mit wanderndem Scan-Balken |
| `dmg` | `palette` (4 Farben) | Game-Boy-Kacheln, diagonal scrollend |
| `plasma` | `darkness` | Demoscene-Plasma per Palette-Cycling |
| `image` | `image` (Pfad relativ zum Theme), `dim` (0–255) | eigenes Hintergrundbild |
| `falling` | `particles` (`leaves`/`snow`), `colors`, `moon` | aus dem Plugin `seasonal` |

Plugins können weitere Typen registrieren (`api.add_background`).

## Schrift

- `title_font`: `"pixel"` nutzt die eingebaute 5×7-Bitmapschrift für Überschriften, `"sans"` eine fette Systemschrift.
- `font`: `"sans"` (DejaVu/Noto/Segoe) oder ein Dateiname einer `.ttf`/`.otf` im Theme-Ordner.

## Musik

`music` beschreibt einen Chiptune-Loop, der beim ersten Verwenden erzeugt und als WAV gecacht wird:

| Feld | Werte |
|---|---|
| `tempo` | BPM, z. B. 84–150 |
| `root` | Grundton als MIDI-Nummer (57 = A3, 60 = C4) |
| `scale` | `major`, `minor`, `dorian`, `lydian`, `penta` |
| `progression` | Stufen der Akkordfolge, z. B. `[0, 5, 3, 4]` (i–VI–iv–v in Moll) |
| `style` | `arp` (Arpeggio + Drums), `drive` (schneller), `calm` (Flächen, ohne Drums) |
| `seed` | optional: anderer Wert ergibt eine andere Melodie |
| `file` | optional: eigene Musikdatei im Theme-Ordner statt Synthese |

`soundpack`: `chiptune`, `soft`, `arcade` oder ein von Plugins registriertes Pack.
