# Plugins schreiben

Ein Plugin ist ein Ordner in `/userdata/plugins/<id>/` (oder im mitgelieferten `plugins/`) mit zwei Dateien:

```
plugins/mein-plugin/
  plugin.json
  main.py
```

```json
{ "id": "mein-plugin", "name": "Mein Plugin", "version": "1.0", "api": 1,
  "description": "Was es tut", "author": "du", "default_enabled": true }
```

```python
def register(api):
    ...   # wird beim Booten einmal aufgerufen
```

Ein Plugin, das beim Laden abstürzt, wird mit seiner Fehlermeldung im Plugin-Bildschirm angezeigt. Seine Hooks werden wieder entfernt, das System läuft weiter.

## Was die API kann

| Aufruf | Wirkung |
|---|---|
| `api.add_system(id=…, name=…, short=…, maker=…, year=…, exts=(…), emulators=(…), ladder=True, demand=…)` | neues System (oder ein bestehendes mit gleicher `id` ersetzen) |
| `api.add_emulator(id=…, name=…, kind="libretro"/"standalone", core=…/binary=…, args=(…), min=Req(…), rec=Req(…), source={…})` | neuer Emulator inkl. Hardware-Anforderungen → erscheint sofort in der Leiter |
| `api.add_emulator_to_system("ps5", "mein-emu", first=True)` | Emulator einem System zuordnen |
| `api.add_shader(id=…, name=…, slang="crt/xyz.slangp", reshade="xyz.fx", weight=1..5)` | neuer Filter |
| `api.add_setting(SettingDef(...))` | Einstellung mit Ebenen-Logik (`scopes=(GLOBAL, SYSTEM, GAME)`), taucht automatisch im UI auf |
| `api.add_theme({...})` | Theme als Dict (gleiches Format wie `theme.json`) |
| `api.add_background("id", factory)` | neuer Hintergrundtyp; `factory(theme, params, size)` liefert ein Objekt mit `update(dt)` und `draw(surface)` |
| `api.add_soundpack("id", "Name", render=lambda: {"move": [floats], ...})` | eigenes Menü-Soundpack |
| `api.add_screen("id", factory)` | eigener Bildschirm; öffnen mit `app.push("id")` |
| `api.add_menu_entry("id", "Label", action, section="home"/"system")` | Eintrag in der Schnellleiste (`home`) oder im Hauptmenü (`system`) |
| `api.add_collection("id", "Name", query)` | virtuelle Spieleliste als Karussell-Karte; `query(core) -> [Game]` |
| `api.add_rom_detector(fn)` | `fn(path, head_bytes) -> system_id or None` für den Import |
| `api.on(event, fn, priority=0)` | Hook (siehe unten) |
| `api.setting(key, system, game)` · `api.data_dir()` · `api.notify(text, kind)` · `api.log` | Hilfsfunktionen |

## Events

| Event | Argumente | Typ |
|---|---|---|
| `boot` | `core` | Benachrichtigung |
| `hw.probed` | `hw, core` → **gibt `hw` zurück** | Filter: z. B. eigene GPU-Datenbank |
| `hw.assessed` | `assessment, core` | Benachrichtigung |
| `library.scanned` | `library` | Benachrichtigung (z. B. Scraper anstoßen) |
| `game.before_launch` | `plan, core` → **gibt `plan` zurück** | Filter: `plan.cmd`, `plan.env`, `plan.ra_config`, `plan.core_options`, `plan.gamescope`, `plan.notes` |
| `game.launch` | `plan, core` | direkt vor dem Prozessstart |
| `game.after_exit` | `plan, returncode, seconds, core` | nach Spielende |
| `settings.changed` | `key, value, scope, target` | Benachrichtigung |
| `ui.game_details` | `game, core` → `[(label, wert), …]` | Zeilen im Detailpanel |
| `ui.game_menu` | `game, core` → `[(label, callback(app)), …]` | Einträge im Spiel-Optionsmenü |
| `ui.import_hints` | `core` → `[str, …]` | Hinweise im Import-Bildschirm |
| `ui.idle` | `app, seconds` | einmal pro Sekunde |
| `ui.notify` | `text, kind` | Toast anzeigen (lieber `api.notify`) |

## Beispiel: Emulator für ein neues System nachrüsten

```python
from retroforge.model import Req

def register(api):
    api.add_emulator(id="neo-ps5", name="NeoPS5", kind="standalone", binary="neops5",
                     args=("--fullscreen", "{rom}"),
                     min=Req(archs=("x86_64",), isa=("avx2",), cpu=6.0, threads=8, gpu=5, ram=16, vulkan="1.3"),
                     rec=Req(cpu=7.0, threads=16, gpu=5, ram=32),
                     source={"type": "github", "repo": "someone/neops5", "assets": {"x86_64": r"x86_64\.AppImage$"}})
    api.add_emulator_to_system("ps5", "neo-ps5")
```

Ein echtes Beispiel dafür ist [`plugins/anyps5`](../plugins/anyps5/main.py): Es hängt AnyPS5 an die PS5, bringt einen eigenen Installer mit (`source={"type": "custom", ...}`) und ersetzt per `game.before_launch` den Startbefehl durch einen Wrapper, der beim ersten Start konvertiert.

Ab dann zeigt die Hardware-Leiter, ob die Maschine PS5 schafft. Der Emulator lässt sich aus dem Emulatoren-Bildschirm installieren, und die Shader- und Upscaling-Einstellungen greifen automatisch über gamescope.

## Beispiel: jeden Start verändern

```python
def register(api):
    def boost(plan, core):
        if plan.game.system == "n64":
            plan.core_options["mupen64plus-cpucore"] = "dynamic_recompiler"
            plan.env["MESA_GLTHREAD"] = "true"
        return plan
    api.on("game.before_launch", boost)
```

Die mitgelieferten Plugins in `plugins/` sind kurz und zeigen jeweils eine Technik: Collection + Screen (`stats`), Launch-Hook (`save-backup`), Hintergrund-Thread mit Netzwerkserver (`web-upload`), Idle-Hook + Screen (`screensaver`), Launch-Filter (`retroachievements`) und Theme + Hintergrundtyp (`seasonal`).
