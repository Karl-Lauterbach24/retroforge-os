"""Example plugin: collection + screen + menu entry + detail hook."""


def register(api):
    core = api.core

    def most_played(core):
        gd = core.gamedata
        games = [g for g in core.library.by_key.values() if gd.get(g.key, "time", 0) > 0]
        return sorted(games, key=lambda g: -gd.get(g.key, "time", 0))[:25]

    api.add_collection("most-played", "Meistgespielt", most_played, color="#f72585", short="TOP", order=2)

    def details(game, core, **_):
        gd = core.gamedata
        plays, secs = gd.get(game.key, "plays", 0), gd.get(game.key, "time", 0)
        if plays:
            return [("Ø Sitzung", f"{int(secs / plays // 60)} min")]
        return None

    api.on("ui.game_details", details)

    def make_screen(app, **kw):
        # imported lazily: the core itself must stay UI-free
        from retroforge.ui import widgets as w
        from retroforge.ui.screens.base import Screen
        from retroforge.ui.theme import color

        class StatsScreen(Screen):
            def draw(self, surf):
                th = self.theme
                gd = self.core.gamedata
                per_sys = {}
                total = 0
                for g in self.core.library.by_key.values():
                    t = gd.get(g.key, "time", 0)
                    per_sys[g.system] = per_sys.get(g.system, 0) + t
                    total += t
                w.header(surf, th, "Statistik", f"Gesamt: {total // 3600} h {total % 3600 // 60} min gespielt")
                w.panel(surf, (40, 132, 1200, 528), th)
                top = sorted(per_sys.items(), key=lambda kv: -kv[1])[:9]
                mx = max([v for _, v in top] + [1])
                for i, (sid, secs) in enumerate(top):
                    s = self.core.registry.get("system", sid)
                    y = 160 + i * 54
                    w.text(surf, th, s.name if s else sid, (70, y + 6), 19, bold=True, max_w=300)
                    w.bar(surf, th, (380, y + 10, 700, 16), secs / mx, color(s.color) if s else None)
                    w.text(surf, th, f"{secs // 60} min", (1210, y + 6), 17, th.c["muted"], anchor="topright")
                if not top or mx <= 1:
                    w.text(surf, th, "Noch keine Spielzeit erfasst – leg los!", (640, 400), 22, th.c["muted"],
                           anchor="center")

        return StatsScreen(app)

    api.add_screen("stats", make_screen)
    api.add_menu_entry("stats", "Statistik", lambda app: app.push("stats"), section="home", order=10)
