"""Screens are registered by id so plugins can open, wrap or replace them."""


def register_screens(registry):
    from .gamelist import GameListScreen
    from .hardware import HardwareScreen
    from .home import HomeScreen
    from .settings_screen import SettingsScreen
    from .tools import BiosScreen, EmulatorsScreen, ImportScreen, PluginsScreen

    for sid, factory in (("home", HomeScreen), ("gamelist", GameListScreen), ("settings", SettingsScreen),
                         ("hardware", HardwareScreen), ("importer", ImportScreen), ("plugins", PluginsScreen),
                         ("emulators", EmulatorsScreen), ("bios", BiosScreen)):
        if not registry.has("screen", sid):   # a plugin may already have replaced it
            registry.add("screen", sid, factory, origin="core")
