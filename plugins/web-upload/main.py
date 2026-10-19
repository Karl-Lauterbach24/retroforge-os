"""Example plugin: upload ROMs/BIOS from any browser in the local network.

Off by default; when enabled it is protected by a random PIN shown on the
import screen. Files are streamed to disk (no size limit, little RAM), ROMs
are auto-detected and sorted, unknown files land in /userdata/import.
"""
import html
import os
import random
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from retroforge import romdetect
from retroforge.settings import GLOBAL, SettingDef

PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RetroForge Upload</title>
<style>body{font-family:system-ui,sans-serif;background:#0d0221;color:#f6f1ff;max-width:640px;margin:0 auto;padding:16px}
h1{color:#ff2a6d;letter-spacing:2px}select,input,button{font-size:1rem;padding:10px;border-radius:10px;border:1px solid #5b1a6e;
background:#1a0b3a;color:#fff;width:100%;margin:6px 0}button{background:#ff2a6d;border:0;font-weight:700}
.f{margin:6px 0;padding:8px;background:#1a0b3a;border-radius:8px}progress{width:100%}</style></head><body>
<h1>RETROFORGE</h1><p>ROMs oder BIOS-Dateien hochladen – Zuordnung erfolgt automatisch.</p>
<input id="pin" placeholder="PIN (siehe Bildschirm)" inputmode="numeric">
<select id="sys"><option value="auto">Automatisch erkennen</option><option value="bios">BIOS</option>{options}</select>
<input id="files" type="file" multiple><button onclick="go()">Hochladen</button><div id="log"></div>
<script>
async function go(){const fs=[...document.getElementById('files').files];const log=document.getElementById('log');
for(const f of fs){const d=document.createElement('div');d.className='f';d.textContent=f.name;const p=document.createElement('progress');
d.appendChild(p);log.appendChild(d);
await new Promise(res=>{const x=new XMLHttpRequest();
x.open('PUT','/upload?'+new URLSearchParams({name:f.name,system:document.getElementById('sys').value,pin:document.getElementById('pin').value}));
x.upload.onprogress=e=>{p.max=e.total;p.value=e.loaded};x.onload=()=>{d.textContent=f.name+' – '+x.responseText;res()};
x.onerror=()=>{d.textContent=f.name+' – Fehler';res()};x.send(f)});}}
</script></body></html>"""


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent; picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def register(api):
    core = api.core
    state = {"server": None, "pin": f"{random.randint(0, 9999):04d}"}
    api.add_setting(SettingDef("webupload.enabled", "Web-Upload im Heimnetz", False, "System", "bool",
                               scopes=(GLOBAL,), order=60,
                               help="Startet einen kleinen Upload-Server (PIN-geschützt)."))
    api.add_setting(SettingDef("webupload.port", "Web-Upload Port", 8080, "System",
                               choices=[(8080, "8080"), (8000, "8000"), (8888, "8888")], scopes=(GLOBAL,), order=61))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _reply(self, code, body, ctype="text/plain; charset=utf-8"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            opts = "".join(f'<option value="{s.id}">{html.escape(s.name)}</option>'
                           for s in core.registry.all("system"))
            self._reply(200, PAGE.replace("{options}", opts), "text/html; charset=utf-8")

        def do_PUT(self):
            q = parse_qs(urlparse(self.path).query)
            arg = lambda k: (q.get(k) or [""])[0]
            if urlparse(self.path).path != "/upload":
                return self._reply(404, "nicht gefunden")
            if arg("pin") != state["pin"]:
                return self._reply(403, "falsche PIN")
            name = os.path.basename(arg("name").replace("\\", "/"))
            if not name or name.startswith("."):
                return self._reply(400, "ungültiger Dateiname")
            system = arg("system") or "auto"
            if system not in ("auto", "bios") and not core.registry.has("system", system):
                return self._reply(400, "unbekanntes System")
            length = int(self.headers.get("Content-Length") or 0)
            inbox = core.paths.import_inbox
            inbox.mkdir(parents=True, exist_ok=True)
            tmp = inbox / (name + ".part")
            with open(tmp, "wb") as f:
                left = length
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            staged = inbox / name
            os.replace(tmp, staged)
            tmp = staged
            if system == "auto":
                system = romdetect.detect(staged, core.registry) or ""
            if system == "bios":
                dest = core.paths.bios / name
            elif system:
                dest = core.paths.system_roms(system) / name
            else:
                dest = inbox / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dest)
            where = system or "Import-Ordner"
            api.notify(f"Upload: {name} → {where}", "good")
            if system and system != "bios":
                core.library.scan_async()
            self._reply(200, f"OK → {where}")

    def stop():
        srv = state["server"]
        if srv:
            srv.shutdown()
            srv.server_close()
            state["server"] = None

    def start():
        stop()
        if not api.setting("webupload.enabled", default=False):
            return
        port = int(api.setting("webupload.port", default=8080))
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        except OSError as e:
            api.notify(f"Web-Upload: Port {port} belegt ({e.strerror})", "bad")
            return
        state["server"] = srv
        threading.Thread(target=srv.serve_forever, daemon=True, name="web-upload").start()
        api.log.info("web upload on port %d", port)

    api.on("boot", lambda core, **_: start())
    api.on("settings.changed", lambda key, **_: start() if key.startswith("webupload.") else None)

    def hints(core, **_):
        if state["server"]:
            port = state["server"].server_address[1]
            return [f"Web-Upload aktiv:  http://{lan_ip()}:{port}   ·   PIN {state['pin']}"]
        return ["Tipp: 'Web-Upload im Heimnetz' unter Einstellungen › System aktivieren."]

    api.on("ui.import_hints", hints)
