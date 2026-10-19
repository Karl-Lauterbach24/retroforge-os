"""Unified input: keyboard, SDL GameControllers and raw joysticks → actions.

Actions: up down left right ok back x y menu select l1 r1
"""
import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except Exception:   # very old pygame
    sdl_controller = None

KEYMAP = {
    pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
    pygame.K_RETURN: "ok", pygame.K_KP_ENTER: "ok", pygame.K_ESCAPE: "back", pygame.K_BACKSPACE: "back",
    pygame.K_TAB: "x", pygame.K_F2: "y", pygame.K_INSERT: "y", pygame.K_F1: "menu", pygame.K_F3: "select",
    pygame.K_PAGEUP: "l1", pygame.K_PAGEDOWN: "r1",
}
# SDL GameController button indices (standardised across pads)
CTRL_BUTTONS = {0: "ok", 1: "back", 2: "x", 3: "y", 4: "select", 5: "menu", 6: "menu",
                9: "l1", 10: "r1", 11: "up", 12: "down", 13: "left", 14: "right"}
JOY_BUTTONS = {0: "ok", 1: "back", 2: "x", 3: "y", 4: "l1", 5: "r1", 6: "select", 7: "menu"}
DIRS = ("up", "down", "left", "right")
DEADZONE = 0.55
REPEAT_DELAY, REPEAT_RATE = 0.35, 0.065


class Input:
    def __init__(self, nintendo_layout=False):
        self.controllers = {}
        self.joysticks = {}
        self.held = {}          # action -> time held (for pad auto-repeat)
        self.axis_state = {}
        self.nintendo = nintendo_layout
        pygame.key.set_repeat(int(REPEAT_DELAY * 1000), int(REPEAT_RATE * 1000))

    def _swap(self, action):
        if self.nintendo:
            return {"ok": "back", "back": "ok", "x": "y", "y": "x"}.get(action, action)
        return action

    def device_added(self, index):
        if sdl_controller is not None and sdl_controller.is_controller(index):
            c = sdl_controller.Controller(index)
            self.controllers[c.as_joystick().get_instance_id()] = c
            return c.name
        j = pygame.joystick.Joystick(index)
        j.init()
        self.joysticks[j.get_instance_id()] = j
        return j.get_name()

    def device_removed(self, instance_id):
        self.controllers.pop(instance_id, None)
        self.joysticks.pop(instance_id, None)

    def names(self):
        return [c.name for c in self.controllers.values()] + [j.get_name() for j in self.joysticks.values()]

    def translate(self, ev):
        """Returns a list of actions for this event."""
        t = ev.type
        if t == pygame.KEYDOWN:
            a = KEYMAP.get(ev.key)
            return [a] if a else []
        if t == getattr(pygame, "CONTROLLERBUTTONDOWN", -1):
            a = CTRL_BUTTONS.get(ev.button)
            if a in DIRS:
                self.held[a] = 0.0
            return [self._swap(a)] if a else []
        if t == getattr(pygame, "CONTROLLERBUTTONUP", -1):
            self.held.pop(CTRL_BUTTONS.get(ev.button), None)
            return []
        if t == getattr(pygame, "CONTROLLERAXISMOTION", -1):
            if ev.axis in (0, 1):
                v = ev.value / 32767.0
                return self._axis(("ctrl", ev.instance_id, ev.axis), v, ev.axis)
            return []
        # raw joysticks (ignored when the device is handled as GameController)
        iid = getattr(ev, "instance_id", None)
        if iid in self.controllers:
            return []
        if t == pygame.JOYBUTTONDOWN:
            a = JOY_BUTTONS.get(ev.button)
            return [self._swap(a)] if a else []
        if t == pygame.JOYHATMOTION:
            x, y = ev.value
            for d in DIRS:
                self.held.pop(d, None)
            out = []
            if x:
                out.append("left" if x < 0 else "right")
            if y:
                out.append("up" if y > 0 else "down")
            for a in out:
                self.held[a] = 0.0
            return out
        if t == pygame.JOYAXISMOTION and ev.axis in (0, 1):
            return self._axis(("joy", iid, ev.axis), ev.value, ev.axis)
        return []

    def _axis(self, key, v, axis):
        neg, pos = ("left", "right") if axis == 0 else ("up", "down")
        prev = self.axis_state.get(key, 0)
        cur = -1 if v < -DEADZONE else 1 if v > DEADZONE else 0
        if cur == prev:
            return []
        self.axis_state[key] = cur
        self.held.pop(neg, None)
        self.held.pop(pos, None)
        if cur:
            a = neg if cur < 0 else pos
            self.held[a] = 0.0
            return [a]
        return []

    def update(self, dt):
        """Auto-repeat for held pad directions."""
        out = []
        for a, t in list(self.held.items()):
            nt = t + dt
            if t < REPEAT_DELAY <= nt or (nt > REPEAT_DELAY and int((nt - REPEAT_DELAY) / REPEAT_RATE)
                                          > int((t - REPEAT_DELAY) / REPEAT_RATE)):
                out.append(a)
            self.held[a] = nt
        return out
