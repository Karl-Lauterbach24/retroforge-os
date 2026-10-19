# PS3-Disc-Sicherung (optional, auf eigene Gefahr)

> ⚠️ **Dieses Plugin umgeht einen wirksamen Kopierschutz.** PS3-Discs sind verschlüsselt; das Sichern ist nur
> mit den Disc-Schlüsseln möglich. Das Umgehen eines wirksamen Kopierschutzes ist in vielen Ländern verboten,
> in Deutschland nach **§ 95a UrhG** auch für Privatkopien eigener Discs. Die Nutzung erfolgt **ausschließlich
> auf eigene Gefahr**; RetroForge übernimmt keine Haftung.

## Was das Plugin tut – und was nicht

- Es ist **standardmäßig deaktiviert**. Beim Aktivieren (Startbildschirm › Plugins) und vor **jeder** Nutzung
  muss die Warnung oben bestätigt werden.
- Es enthält **keinen Entschlüsselungscode** und lädt **nichts automatisch herunter**. Es startet das externe,
  von dir selbst installierte [ps3-disc-dumper](https://github.com/13xforever/ps3-disc-dumper) (MIT), hängt die
  Disc vorher ein und verschiebt das fertige Spiel danach nach `roms/ps3/<Name>.ps3/`, wo RPCS3 es startet.
- Ohne das Plugin meldet RetroForge eine eingelegte PS3-Disc als **nicht unterstützt** und verweist hierher.

## Einrichten

1. Plugin aktivieren und die Warnung bestätigen, dann RetroForge neu starten.
2. `ps3-disc-dumper` (Linux-Build) selbst herunterladen und nach `/userdata/emulators/ps3-disc-dumper/` entpacken.
3. PS3-Disc einlegen › *Mit ps3-disc-dumper sichern (auf eigene Gefahr)*.

Voraussetzungen von ps3-disc-dumper: ein [kompatibles Blu-ray-Laufwerk](https://rpcs3.net/quickstart#dumping_drives)
und ein bekannter Disc-Schlüssel (Redump-Datenbank oder IRD-Bibliothek). Die Bedienung des Dumpers erfolgt per
Maus und Tastatur.
