# -*- coding: utf-8 -*-
"""Hungry Hedgie: a gentle berry adventure for GameHub (quality pass 2.0).

Drop-in entry point: ``await main(screen, clock)``. Run this file directly
for desktop play. Existing assets/hungryHedgie sprites are used when present;
the game also includes drawn artwork so missing assets never prevent play.

Design: three short stages, two basket trips each, no countdown or lost food.
Settings and progress use browser localStorage in Pygbag or a small adjacent
JSON file on desktop. A blocked or unavailable save store is harmless.
"""

import asyncio
import json
import math
import os
import random
import sys
from array import array
from pathlib import Path

import pygame


VERSION = "2.0"
WIDTH, HEIGHT = 800, 600
FPS = 60
CREAM = (255, 247, 224)
INK = (52, 67, 53)
GREEN = (65, 119, 75)
GOLD = (245, 192, 72)
BERRY = (177, 61, 88)
STAGES = (
    {"name": "A cosy bed", "goal": 6, "capacity": 3,
     "reward": "A cosy bed is ready!", "next": "Let's grow a berry garden."},
    {"name": "A little garden", "goal": 8, "capacity": 4,
     "reward": "Your garden is growing!", "next": "Let's make a picnic for friends."},
    {"name": "A picnic for friends", "goal": 10, "capacity": 5,
     "reward": "A picnic for everyone!", "next": "You made a lovely home."},
)


def clamp(value, low, high):
    return max(low, min(high, value))


def point(value):
    return round(value[0]), round(value[1])


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def berry_icon(surface, center, size=12, filled=True):
    """A readable single berry, also used for counting in the basket and goal."""
    x, y = point(center)
    radius = max(3, round(size / 2))
    color = BERRY if filled else (211, 211, 181)
    pygame.draw.circle(surface, color, (x, y + 2), radius)
    if filled:
        pygame.draw.circle(surface, (236, 137, 145),
                           (x - radius // 3, y - radius // 3 + 2), max(1, radius // 4))
    pygame.draw.ellipse(surface, (76, 132, 75) if filled else (172, 185, 152),
                        (x, y - radius - 2, radius + 3, max(3, radius // 2)))


def heart(surface, center, size=8, color=(221, 116, 113)):
    x, y = point(center)
    pygame.draw.circle(surface, color, (x - size // 3, y), size // 2)
    pygame.draw.circle(surface, color, (x + size // 3, y), size // 2)
    pygame.draw.polygon(surface, color,
                        [(x - size + 1, y + 1), (x + size - 1, y + 1), (x, y + size)])


def hedgehog_art(size=(62, 47), friend=False):
    """Code-drawn fallback, with a face that stays readable at game size."""
    image = pygame.Surface((80, 64), pygame.SRCALPHA)
    spikes = (116, 107, 125) if friend else (116, 77, 56)
    for i in range(10):
        angle = math.pi + i * math.pi / 9
        x, y = 34 + math.cos(angle) * 29, 39 + math.sin(angle) * 27
        pygame.draw.polygon(image, spikes,
                            [(35, 39), point((x - 6, y + 7)), point((x, y - 6)),
                             point((x + 7, y + 7))])
    pygame.draw.ellipse(image, spikes, (7, 15, 58, 39))
    pygame.draw.ellipse(image, (230, 188, 139), (34, 28, 38, 27))
    pygame.draw.ellipse(image, (238, 203, 160), (46, 23, 12, 15))
    pygame.draw.circle(image, (239, 153, 139), (55, 44), 4)
    pygame.draw.circle(image, (43, 43, 41), (59, 36), 3)
    pygame.draw.circle(image, (255, 255, 241), (60, 35), 1)
    pygame.draw.circle(image, (55, 49, 43), (72, 43), 4)
    pygame.draw.ellipse(image, (110, 75, 54), (19, 51, 13, 7))
    pygame.draw.ellipse(image, (110, 75, 54), (47, 51, 13, 7))
    for x, y in ((20, 22), (33, 18), (18, 35), (35, 30), (29, 42)):
        pygame.draw.line(image, (174, 128, 86), (x, y), (x + 4, y + 7), 2)
    return pygame.transform.smoothscale(image, size)


class Art:
    """Load only after setup; importing this module needs neither assets nor GUI."""

    def __init__(self):
        self.loaded = set()
        self.hedgie = self.sprite("hedgie.png", (62, 49), hedgehog_art())
        self.friend = self.sprite("enemy.png", (55, 47), hedgehog_art((55, 47), True))
        self.hedgie_left = pygame.transform.flip(self.hedgie, True, False)
        self.friend_left = pygame.transform.flip(self.friend, True, False)
        self.tree = self.sprite("tree.png", (85, 113))
        self.burrow = self.sprite("burrow.png", (202, 159))
        self.berry = self.sprite("berry.png", (27, 27))
        self.torch = self.sprite("torch.png", (14, 33))
        self.grass = self.sprite("grass.png", (WIDTH, HEIGHT))

    def sprite(self, name, size, fallback=None):
        candidates = (Path("assets") / "hungryHedgie" / name,
                      Path(__file__).resolve().parent / "assets" / "hungryHedgie" / name)
        for path in candidates:
            try:
                image = pygame.image.load(str(path)).convert_alpha()
                self.loaded.add(name)
                return pygame.transform.smoothscale(image, size)
            except (OSError, pygame.error):
                pass
        return fallback


class ProgressStore:
    KEY = "GameHub.hungryHedgie.v2"

    def __init__(self):
        self.path = Path(__file__).resolve().with_name("hungryHedgie.save.json")

    def load(self):
        try:
            if sys.platform == "emscripten":
                import platform
                raw = platform.window.localStorage.getItem(self.KEY)
                return json.loads(str(raw)) if raw else {}
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            # A browser's SecurityError / quota exception need not be an
            # OSError. Storage is optional; it must never stop the game.
            return {}

    def save(self, data):
        try:
            raw = json.dumps(data, separators=(",", ":"))
            if sys.platform == "emscripten":
                import platform
                platform.window.localStorage.setItem(self.KEY, raw)
            else:
                temp = self.path.with_suffix(".tmp")
                temp.write_text(raw, encoding="utf-8")
                os.replace(str(temp), str(self.path))
            return True
        except Exception:
            return False


class Sounds:
    """Small optional chimes; no sound files, numpy, or mixer reconfiguration."""

    def __init__(self):
        self.cache = {}

    def play(self, name, muted):
        config = pygame.mixer.get_init()
        if muted or not config or config[1] != -16:
            return
        key = name, config
        try:
            if key not in self.cache:
                rate, _, channels = config
                notes = {"pick": (659, 880), "home": (523, 659, 784),
                         "win": (523, 659, 784, 1047), "lantern": (784, 988)}[name]
                samples = array("h")
                length = max(1, int(rate * 0.085))
                for freq in notes:
                    for i in range(length):
                        envelope = min(1, i / max(1, rate * 0.009)) * (1 - i / length) ** 2
                        sample = round(3500 * envelope * math.sin(2 * math.pi * freq * i / rate))
                        samples.extend([sample] * channels)
                if sys.byteorder == "big":
                    samples.byteswap()
                self.cache[key] = pygame.mixer.Sound(buffer=samples.tobytes())
            self.cache[key].play()
        except (pygame.error, OverflowError):
            pass


class HedgieGame:
    HOME = pygame.Rect(566, 117, 210, 165)
    DOOR = pygame.Rect(572, 232, 204, 91)
    EXIT = pygame.Rect(17, 17, 46, 46)
    SOUND = pygame.Rect(681, 18, 44, 44)
    PAUSE = pygame.Rect(736, 18, 44, 44)
    ACTION = pygame.Rect(250, 421, 300, 61)

    def __init__(self, screen, clock=None, storage=None):
        if not pygame.font.get_init():
            pygame.font.init()
        self.screen, self.clock = screen, clock
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.storage = storage if storage is not None else ProgressStore()
        self.art, self.sounds = Art(), Sounds()
        self.fonts = {size: pygame.font.Font(None, size) for size in (18, 20, 22, 24, 28, 30, 34, 40, 46)}
        self.running = True
        self.muted = False
        self.time = 0.0
        self.last_ticks = pygame.time.get_ticks()
        self.save_elapsed = 0.0
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.pointer = None
        self.pointer_down = False
        self.held = set()
        self.flows = []
        self.particles = []
        self.notice, self.notice_time = "", 0.0
        self.lantern_time = 0.0
        self.bump_time = self.invulnerable = 0.0
        self.has_played = False
        self._make_background()
        self.reset()
        self._load()
        # A deliberate large start/continue button prevents accidental movement
        # from the GameHub menu's opening click.
        self.welcome = self.state == "play"
        self._layout_viewport()

    @property
    def stage(self):
        return STAGES[self.stage_index]

    @property
    def capacity(self):
        return self.stage["capacity"]

    @property
    def total_delivered(self):
        return sum(stage["goal"] for stage in STAGES[:self.stage_index]) + self.delivered

    @property
    def in_home(self):
        return self.DOOR.collidepoint(self.pos)

    def reset(self):
        self.stage_index = 0
        self.delivered = self.carrying = 0
        self.pos = pygame.Vector2(636, 302)
        self.target = self.pos.copy()
        self.facing_left = True
        self.state = "play"
        self.has_played = False
        self.flows.clear()
        self.particles.clear()
        self.lantern_time = self.bump_time = self.invulnerable = 0.0
        self.notice_time = 0.0
        self.delivery_time = 0.0
        self._build_stage()

    def _build_stage(self):
        # Fixed seed gives a well-spaced, recoverable map without moving targets.
        rng = random.Random(7703 + self.stage_index)
        fixed = [(521, 328), (458, 298), (447, 402), (343, 372),
                 (315, 249), (214, 318), (149, 425), (202, 193),
                 (390, 175), (103, 278)]
        self.berries = []
        for i, (x, y) in enumerate(fixed[:self.stage["goal"]]):
            if i > 1:
                x += rng.randint(-13, 13)
                y += rng.randint(-10, 10)
            self.berries.append({"id": i, "pos": pygame.Vector2(x, y), "active": True})
        self.neighbour = pygame.Vector2(285, 442)
        self.neighbour_target = pygame.Vector2(205, 370)
        self.neighbour_wait = 0.0
        self.neighbour_left = True
        self.lantern = pygame.Vector2(376, 296)
        self.lantern_collected = False
        self.lantern_time = 0.0

    def _load(self):
        try:
            data = self.storage.load()
            if not isinstance(data, dict) or data.get("schema") != 2:
                return
            self.muted = bool(data.get("muted", False))
            self.stage_index = int(clamp(int(data.get("stage", 0)), 0, len(STAGES) - 1))
            self._build_stage()
            self.delivered = int(clamp(int(data.get("delivered", 0)), 0, self.stage["goal"]))
            self.carrying = int(clamp(int(data.get("carrying", 0)), 0,
                                      min(self.capacity, self.stage["goal"] - self.delivered)))
            remaining = self.stage["goal"] - self.delivered - self.carrying
            ids = data.get("remaining", [])
            if (not isinstance(ids, list) or len(ids) != remaining
                    or any(type(i) is not int or not 0 <= i < len(self.berries) for i in ids)
                    or len(set(ids)) != len(ids)):
                ids = list(range(remaining))
            for berry in self.berries:
                berry["active"] = berry["id"] in ids
            position = data.get("pos", [636, 302])
            if (isinstance(position, list) and len(position) == 2
                    and all(isinstance(v, (int, float)) and math.isfinite(v) for v in position)):
                self.pos.update(clamp(position[0], 49, 751), clamp(position[1], 145, 478))
            self.target = self.pos.copy()
            self.has_played = bool(data.get("started", False))
            self.state = "play"
            if self.delivered == self.stage["goal"]:
                self.state = "win" if self.stage_index == 2 else "reward"
        except (OSError, ValueError, TypeError, OverflowError, AttributeError):
            self.reset()

    def persist(self):
        """Transfers count at dispatch; animations can never count food twice."""
        data = {"schema": 2, "stage": self.stage_index, "delivered": self.delivered,
                "carrying": self.carrying, "remaining": [b["id"] for b in self.berries if b["active"]],
                "pos": list(self.pos), "started": self.has_played,
                "muted": self.muted}
        try:
            return self.storage.save(data)
        except Exception:
            return False

    def _make_background(self):
        rng = random.Random(43)
        self.background = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.background.fill((153, 184, 119))
        if self.art.grass:
            # Keep the supplied texture as a subtle layer so food remains clear.
            grass = self.art.grass.copy()
            grass.set_alpha(48)
            self.background.blit(grass, (0, 0))
        pygame.draw.ellipse(self.background, (172, 198, 133), (35, 87, 724, 471))
        pygame.draw.ellipse(self.background, (183, 205, 143), (94, 125, 585, 374))
        path = [(645, 296), (554, 355), (450, 408), (332, 429), (216, 434)]
        for a, b in zip(path, path[1:]):
            pygame.draw.line(self.background, (199, 204, 151), a, b, 43)
            pygame.draw.circle(self.background, (199, 204, 151), a, 21)
            pygame.draw.circle(self.background, (199, 204, 151), b, 21)
        for _ in range(190):
            x, y = rng.randint(25, 775), rng.randint(99, 502)
            color = rng.choice([(136, 170, 103), (168, 191, 126), (192, 205, 145)])
            pygame.draw.line(self.background, color, (x - 2, y + 2), (x, y - 3), 1)
            pygame.draw.line(self.background, color, (x, y + 2), (x + 3, y - 2), 1)
        for x, y in ((53, 193), (282, 164), (533, 448), (109, 357), (707, 415), (468, 212)):
            self.flower(self.background, (x, y), (255, 238, 185))
        # Trees frame the clearing; they never hide food or block movement.
        for x, y in ((28, 109), (115, 107), (480, 104), (782, 354), (25, 473), (772, 486)):
            self.tree(self.background, (x, y))
        self.veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.veil.fill((30, 53, 43, 145))

    def tree(self, surface, position):
        x, y = position
        if self.art.tree:
            surface.blit(self.art.tree, self.art.tree.get_rect(midbottom=(x, y + 33)))
        else:
            pygame.draw.ellipse(surface, (121, 157, 102), (x - 40, y + 17, 83, 22))
            pygame.draw.rect(surface, (136, 105, 69), (x - 8, y - 19, 16, 52), border_radius=5)
            for dx, dy, radius in ((-23, -27, 28), (19, -34, 31), (0, -55, 33), (0, -22, 32)):
                pygame.draw.circle(surface, (77, 130, 85), (x + dx, y + dy), radius)
            pygame.draw.circle(surface, (99, 151, 96), (x - 10, y - 56), 22)

    @staticmethod
    def flower(surface, position, color, scale=1):
        x, y = point(position)
        r = max(2, round(3 * scale))
        for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r)):
            pygame.draw.circle(surface, color, (x + dx, y + dy), r)
        pygame.draw.circle(surface, GOLD, (x, y), max(1, r - 1))

    def text(self, words, center, size=24, color=INK, surface=None, max_width=None):
        surface = surface if surface is not None else self.canvas
        font = self.fonts[size]
        rendered = font.render(words, True, color)
        if max_width and rendered.get_width() > max_width:
            scale = max_width / rendered.get_width()
            rendered = pygame.transform.smoothscale(rendered,
                        (max_width, max(1, round(rendered.get_height() * scale))))
        surface.blit(rendered, rendered.get_rect(center=point(center)))

    def card(self, rect, color=CREAM, radius=18, surface=None):
        surface = surface if surface is not None else self.canvas
        pygame.draw.rect(surface, (115, 144, 96), rect.move(0, 4), border_radius=radius)
        pygame.draw.rect(surface, color, rect, border_radius=radius)

    def _layout_viewport(self):
        w, h = self.screen.get_size()
        scale = max(0.001, min(w / WIDTH, h / HEIGHT))
        size = max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale))
        self.viewport = pygame.Rect(0, 0, *size)
        self.viewport.center = (w // 2, h // 2)

    def logical_position(self, pos):
        self._layout_viewport()
        if not self.viewport.collidepoint(pos):
            return None
        return pygame.Vector2((pos[0] - self.viewport.x) * WIDTH / self.viewport.w,
                              (pos[1] - self.viewport.y) * HEIGHT / self.viewport.h)

    def _stop_input(self):
        self.pointer = None
        self.pointer_down = False
        self.held.clear()
        self.target = self.pos.copy()

    def close(self):
        self.persist()
        self.running = False
        self._stop_input()

    def toast(self, words, duration=2.4):
        self.notice, self.notice_time = words, duration

    def sparkle(self, pos, color=GOLD, count=12):
        for i in range(count):
            angle = i * math.tau / count + self.time
            speed = 32 + (i % 4) * 14
            self.particles.append({"pos": pygame.Vector2(pos),
                                   "vel": pygame.Vector2(math.cos(angle), math.sin(angle)) * speed,
                                   "life": 0.65 + (i % 3) * 0.13, "color": color})
        self.particles = self.particles[-100:]

    def _ui_click(self, pos):
        if self.EXIT.collidepoint(pos):
            self.close()
            return True
        if self.SOUND.collidepoint(pos):
            self.muted = not self.muted
            self.persist()
            return True
        if self.welcome:
            if self.ACTION.collidepoint(pos):
                self.welcome = False
                self.has_played = True
                self.sounds.play("home", self.muted)
                self._stop_input()
                self.persist()
            return True
        if self.state in ("reward", "win", "pause"):
            if self.ACTION.collidepoint(pos):
                if self.state == "reward":
                    self.stage_index += 1
                    self.delivered = self.carrying = 0
                    self.state = "play"
                    self.pos.update(636, 302)
                    self._build_stage()
                    self.toast("A bigger basket!", 3)
                elif self.state == "win":
                    self.reset()
                    self.has_played = True
                else:
                    self.state = "play"
                self._stop_input()
                self.persist()
            return True
        if self.PAUSE.collidepoint(pos):
            self.pause()
            return True
        # Both the HUD and blank margins consume input instead of steering.
        return pos.y < 113 or pos.y > 501

    def pause(self):
        if not self.welcome and self.state == "play":
            self.state = "pause"
            self._stop_input()
            self.persist()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.close()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
            elif event.key in (pygame.K_p, pygame.K_SPACE):
                if self.state == "pause":
                    self.state = "play"
                    self._stop_input()
                else:
                    self.pause()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and (
                    self.welcome or self.state in ("reward", "win", "pause")):
                self._ui_click(self.ACTION.center)
            elif event.key == pygame.K_m:
                self.muted = not self.muted
                self.persist()
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                               pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d):
                # A key pressed behind a panel must not move Hedgie after it closes.
                if not self.welcome and self.state == "play":
                    self.held.add(event.key)
        elif event.type == pygame.KEYUP:
            self.held.discard(event.key)
        elif event.type in tuple(t for t in (
                getattr(pygame, "WINDOWFOCUSLOST", None),
                getattr(pygame, "WINDOWMINIMIZED", None)) if t is not None):
            self._stop_input()
            self.pause()
        elif event.type == getattr(pygame, "ACTIVEEVENT", -1):
            if not getattr(event, "gain", 1) and getattr(event, "state", 0) & 6:
                self._stop_input()
                self.pause()
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            if getattr(event, "touch", False):
                return  # SDL generates mouse events too; handle each touch once.
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._pointer_start("mouse", event.pos)
            elif event.type == pygame.MOUSEMOTION and self.pointer == "mouse" and self.pointer_down:
                self._pointer_move(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.pointer == "mouse":
                self.pointer_down, self.pointer = False, None
        elif event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            size = self.screen.get_size()
            pos = (event.x * size[0], event.y * size[1])
            if event.type == pygame.FINGERDOWN and self.pointer is None:
                self._pointer_start(event.finger_id, pos)
            elif event.finger_id == self.pointer:
                if event.type == pygame.FINGERMOTION:
                    self._pointer_move(pos)
                else:
                    self.pointer_down, self.pointer = False, None

    def _pointer_start(self, identity, raw_pos):
        if self.pointer is not None:
            return
        pos = self.logical_position(raw_pos)
        if pos is None or self._ui_click(pos):
            return
        if self.state == "play" and not self.welcome:
            self.pointer, self.pointer_down = identity, True
            self._set_target(pos)

    def _pointer_move(self, raw_pos):
        pos = self.logical_position(raw_pos)
        if pos is not None and 113 <= pos.y <= 501 and self.state == "play" and not self.welcome:
            self._set_target(pos)

    def _set_target(self, pos):
        self.target.update(clamp(pos.x, 49, 751), clamp(pos.y, 145, 478))

    def deliver(self):
        if self.carrying <= 0 or self.delivery_time > 0:
            return
        count = self.carrying
        self.carrying = 0
        self.delivered += count
        self.delivery_time = 0.62 + count * 0.12
        self.target = self.pos.copy()
        self.pointer, self.pointer_down = None, False
        for i in range(count):
            self.flows.append({"start": self.pos.copy() + pygame.Vector2(0, -22),
                               "end": pygame.Vector2(679 - i * 13, 260),
                               "time": -i * 0.12})
        self.toast("Thank you, Hedgie!", 2)
        self.sparkle((674, 256), GOLD, 18)
        self.sounds.play("home", self.muted)
        self.persist()

    def _finish_stage(self):
        self.state = "win" if self.stage_index == len(STAGES) - 1 else "reward"
        self._stop_input()
        self.sparkle((400, 239), GOLD, 36)
        self.sounds.play("win", self.muted)
        self.persist()

    def tick(self, dt):
        # Substeps keep pickup and arrival reliable even on slow mobile frames.
        dt = clamp(float(dt), 0.0, 0.1)
        steps = max(1, math.ceil(dt / (1 / 60)))
        for _ in range(steps):
            self._step(dt / steps)

    def _step(self, dt):
        if not self.running:
            return
        self.time += dt
        if self.welcome or self.state == "pause":
            return
        self.notice_time = max(0, self.notice_time - dt)
        for p in self.particles:
            p["pos"] += p["vel"] * dt
            p["vel"].y += 55 * dt
            p["life"] -= dt
        self.particles[:] = [p for p in self.particles if p["life"] > 0]
        for flow in self.flows:
            flow["time"] += dt
        self.flows[:] = [f for f in self.flows if f["time"] < 0.6]
        if self.state != "play":
            return
        self.lantern_time = max(0, self.lantern_time - dt)
        self.invulnerable = max(0, self.invulnerable - dt)
        self.bump_time = max(0, self.bump_time - dt)
        self.save_elapsed += dt
        if self.save_elapsed >= 2:
            self.save_elapsed = 0
            self.persist()
        if self.delivery_time > 0:
            self.delivery_time = max(0, self.delivery_time - dt)
            if self.delivery_time == 0 and self.delivered >= self.stage["goal"]:
                self._finish_stage()
            return
        direction = pygame.Vector2(
            int(bool(self.held & {pygame.K_RIGHT, pygame.K_d})) - int(bool(self.held & {pygame.K_LEFT, pygame.K_a})),
            int(bool(self.held & {pygame.K_DOWN, pygame.K_s})) - int(bool(self.held & {pygame.K_UP, pygame.K_w})))
        if direction.length_squared():
            direction.normalize_ip()
            movement = direction * (188 * dt)
        else:
            delta = self.target - self.pos
            distance = delta.length()
            movement = delta * min(1, 188 * dt / distance) if distance > 0.5 else pygame.Vector2()
        if self.bump_time <= 0:
            self.pos += movement
            if abs(movement.x) > 0.05:
                self.facing_left = movement.x < 0
        self.pos.update(clamp(self.pos.x, 49, 751), clamp(self.pos.y, 145, 478))
        if direction.length_squared():
            # Releasing a key should stop here, without walking back toward
            # the position from the preceding frame.
            self.target = self.pos.copy()
        if self.in_home and self.carrying:
            self.deliver()
            return
        reach = 47 if self.lantern_time else 33
        for berry in self.berries:
            if berry["active"] and self.pos.distance_squared_to(berry["pos"]) <= reach * reach:
                if self.carrying < self.capacity:
                    berry["active"] = False
                    self.carrying += 1
                    self.sparkle(berry["pos"], (255, 231, 137), 9)
                    self.sounds.play("pick", self.muted)
                    if self.carrying == self.capacity:
                        self.toast("Basket full. Let's go home!", 3)
                    elif self.carrying == 1 and self.delivered == 0 and self.stage_index == 0:
                        self.toast("You found a berry!", 2)
                    self.persist()
        if self.stage_index >= 1:
            if not self.lantern_collected and self.pos.distance_squared_to(self.lantern) < 42 ** 2:
                self.lantern_collected = True
                self.lantern_time = 14
                self.toast("A lantern! Reach a little farther.", 3)
                self.sparkle(self.lantern, GOLD, 20)
                self.sounds.play("lantern", self.muted)
            self._move_neighbour(dt)

    def _move_neighbour(self, dt):
        # A slow, predictable neighbour never chases Hedgie or enters home.
        if self.neighbour_wait > 0:
            self.neighbour_wait = max(0, self.neighbour_wait - dt)
        else:
            delta = self.neighbour_target - self.neighbour
            if delta.length() < 4:
                if self.neighbour_target.x < 280:
                    self.neighbour_target.update(425, 446)
                else:
                    self.neighbour_target.update(205, 370)
                self.neighbour_wait = 1.4
            else:
                step = delta.normalize() * min(delta.length(), 29 * dt)
                self.neighbour += step
                self.neighbour_left = step.x < 0
        if not self.in_home and self.invulnerable <= 0 and self.pos.distance_squared_to(self.neighbour) < 37 ** 2:
            self.bump_time = 0.25
            self.invulnerable = 3
            self.neighbour_wait = 2
            self.toast("Oops! Your berries are safe.", 2)
            self.sparkle(self.pos, (245, 210, 143), 7)

    def _draw_home(self):
        s = self.canvas
        pygame.draw.ellipse(s, (151, 169, 110), (548, 220, 237, 91))
        if self.carrying:
            pulse = 4 * math.sin(self.time * 3)
            pygame.draw.ellipse(s, (255, 223, 126), (560 - pulse, 229 - pulse, 222 + 2 * pulse, 79 + 2 * pulse), 3)
        if self.art.burrow:
            s.blit(self.art.burrow, self.HOME)
        else:
            pygame.draw.ellipse(s, (123, 151, 93), (563, 126, 214, 148))
            pygame.draw.ellipse(s, (146, 169, 101), (573, 126, 181, 108))
            pygame.draw.ellipse(s, (119, 85, 60), (613, 168, 103, 100))
            pygame.draw.ellipse(s, (78, 65, 48), (628, 183, 73, 85))
            pygame.draw.ellipse(s, (207, 171, 116), (630, 246, 71, 22))
            for x, y in ((587, 186), (742, 202), (598, 227), (725, 151)):
                self.flower(s, (x, y), (254, 233, 180))
        self.card(pygame.Rect(620, 119, 96, 28), CREAM, 10)
        self.text("HOME", (668, 133), 20, GREEN)
        # An open food tray keeps deliveries visible instead of hiding them.
        pygame.draw.rect(s, (147, 100, 61), (615, 263, 113, 32), border_radius=10)
        pygame.draw.rect(s, (207, 159, 94), (618, 259, 107, 27), border_radius=9)
        for i in range(self.stage["goal"]):
            bx, by = 629 + (i % 5) * 20, 265 + (i // 5) * 12
            berry_icon(s, (bx, by), 11, i < self.delivered)
        # Permanent rewards remain in the world during later stages.
        completed = self.stage_index + int(self.delivered >= self.stage["goal"])
        if completed >= 1:
            self._draw_bed((738, 315), 0.72)
            baby = pygame.transform.smoothscale(self.art.hedgie_left, (34, 27))
            s.blit(baby, baby.get_rect(center=(739, 312)))
        if completed >= 2:
            for i in range(4):
                x, y = 601 + i * 30, 347 + (i % 2) * 12
                pygame.draw.ellipse(s, (109, 149, 88), (x - 11, y - 5, 22, 12))
                self.flower(s, (x, y - 9), (243, 171, 148), 1.5)
                berry_icon(s, (x + 6, y), 9)
        if completed >= 3:
            self._draw_picnic((654, 432), 0.7)

    def _draw_bed(self, center, scale=1, surface=None):
        s = surface if surface is not None else self.canvas
        x, y = point(center)
        w, h = round(90 * scale), round(32 * scale)
        pygame.draw.ellipse(s, (143, 109, 66), (x - w // 2, y - h // 2, w, h))
        for i in range(5):
            rect = pygame.Rect(x - w // 2 + i * w // 5, y - h // 2 - 4, max(8, w // 3), h)
            pygame.draw.ellipse(s, (177 + i * 7, 178 + i * 5, 90), rect)
        pygame.draw.ellipse(s, CREAM, (x + w // 7, y - h // 2 - 4, max(8, w // 3), h - 4))

    def _draw_picnic(self, center, scale=1):
        x, y = center
        w, h = round(145 * scale), round(66 * scale)
        rect = pygame.Rect(round(x - w / 2), round(y - h / 2), w, h)
        pygame.draw.rect(self.canvas, (246, 224, 191), rect, border_radius=7)
        tile = max(6, round(15 * scale))
        for row in range(0, h // tile):
            for col in range(0, w // tile):
                if (row + col) % 2 == 0:
                    pygame.draw.rect(self.canvas, (223, 143, 120),
                                     (rect.x + col * tile, rect.y + row * tile, tile, tile))
        pygame.draw.ellipse(self.canvas, CREAM, (x - 22, y - 16, 45, 26))
        for dx, dy in ((-10, -4), (0, -8), (10, -3), (2, 2)):
            berry_icon(self.canvas, (x + dx, y + dy), max(7, round(12 * scale)))

    def _draw_trail(self):
        if not self.carrying or self.delivery_time > 0:
            return
        end = pygame.Vector2(650, 295)
        delta = end - self.pos
        if delta.length() < 55:
            return
        count = max(2, int(delta.length() / 27))
        for i in range(1, count):
            t = i / count
            pos = self.pos.lerp(end, t)
            radius = 3 + int((i + int(self.time * 3)) % 4 == 0)
            pygame.draw.circle(self.canvas, (255, 237, 154), point(pos), radius)
        # A large arrow is useful even before the child can read.
        unit = delta.normalize()
        normal = pygame.Vector2(-unit.y, unit.x)
        middle = self.pos + unit * 57
        pygame.draw.polygon(self.canvas, (255, 242, 177),
                            [point(middle + unit * 12), point(middle - unit * 8 + normal * 10),
                             point(middle - unit * 8 - normal * 10)])

    def _draw_berry(self, berry):
        s = self.canvas
        pos = berry["pos"]
        bob = math.sin(self.time * 2.5 + berry["id"]) * 2.5
        pygame.draw.ellipse(s, (132, 168, 103), (pos.x - 18, pos.y + 4, 36, 13))
        pygame.draw.ellipse(s, (105, 151, 90), (pos.x - 16, pos.y - 2, 23, 15))
        pygame.draw.ellipse(s, (120, 162, 94), (pos.x - 1, pos.y - 2, 20, 16))
        if self.lantern_time:
            pygame.draw.circle(s, (243, 222, 133), point(pos + pygame.Vector2(0, -6)), 21, 2)
        if self.art.berry:
            s.blit(self.art.berry, self.art.berry.get_rect(center=point(pos + pygame.Vector2(0, -7 + bob))))
        else:
            berry_icon(s, pos + pygame.Vector2(0, -9 + bob), 23)

    def _draw_lantern(self, pos, active=False, scale=1):
        x, y = point(pos)
        glow = pygame.Surface((82, 82), pygame.SRCALPHA)
        for radius, alpha in ((38, 18), (28, 28), (18, 35)):
            pygame.draw.circle(glow, (255, 217, 95, alpha), (41, 41), radius)
        self.canvas.blit(glow, (x - 41, y - 41))
        if self.art.torch:
            self.canvas.blit(self.art.torch, self.art.torch.get_rect(center=(x, y)))
        else:
            pygame.draw.circle(self.canvas, (147, 109, 62), (x, y - 13), 8, 3)
            pygame.draw.rect(self.canvas, (134, 104, 62), (x - 10, y - 10, 20, 25), border_radius=5)
            pygame.draw.rect(self.canvas, (255, 223, 117), (x - 6, y - 6, 12, 15), border_radius=3)
        if active:
            width = round(38 * self.lantern_time / 14)
            pygame.draw.rect(self.canvas, (110, 125, 81), (x - 20, y + 23, 40, 5), border_radius=2)
            pygame.draw.rect(self.canvas, GOLD, (x - 19, y + 24, width, 3), border_radius=1)

    def _draw_player(self):
        s = self.canvas
        x, y = self.pos
        walking = self.state == "play" and self.pos.distance_squared_to(self.target) > 4
        bob = math.sin(self.time * 17) * 1.5 if walking else math.sin(self.time * 3) * 0.6
        pygame.draw.ellipse(s, (128, 154, 98), (x - 29, y + 13, 58, 16))
        if self.invulnerable > 0:
            pygame.draw.ellipse(s, CREAM, (x - 37, y - 29, 74, 58), 2)
        image = self.art.hedgie_left if self.facing_left else self.art.hedgie
        s.blit(image, image.get_rect(center=point((x, y + bob))))
        if self.carrying:
            # A little basket stays on Hedgie's back, with one visible berry each.
            pygame.draw.rect(s, (152, 107, 65), (x - 19, y - 33 + bob, 38, 20), border_radius=5)
            pygame.draw.line(s, (226, 189, 118), (x - 18, y - 25 + bob), (x + 18, y - 25 + bob), 3)
            for i in range(self.carrying):
                berry_icon(s, (x - (self.carrying - 1) * 3.5 + i * 7, y - 34 + bob), 8)
        if self.lantern_time:
            self._draw_lantern((x + (-33 if self.facing_left else 33), y - 5), True)

    def _draw_hud(self):
        s = self.canvas
        pygame.draw.rect(s, CREAM, (0, 0, WIDTH, 103))
        pygame.draw.line(s, (211, 220, 175), (0, 101), (800, 101), 3)
        self._icon_button(self.EXIT, "exit")
        self._icon_button(self.SOUND, "mute" if self.muted else "sound")
        self._icon_button(self.PAUSE, "pause")
        self.text("Hungry Hedgie", (191, 31), 30, GREEN)
        self.text("A little help makes a lovely home", (202, 59), 18)
        self.text(self.stage["name"], (493, 28), 24, GREEN)
        goal = self.stage["goal"]
        for i in range(goal):
            berry_icon(s, (493 - (goal - 1) * 10 + i * 20, 57), 13, i < self.delivered)
        # Three simple milestones supplement the text.
        for i in range(3):
            pygame.draw.circle(s, GREEN if i <= self.stage_index else (207, 213, 179), (376 + i * 25, 86), 7)
        self.text("%s / %s" % (self.delivered, goal), (589, 85), 18)
        self.card(pygame.Rect(17, 516, 218, 67), CREAM, 16)
        self.text("MY BASKET", (126, 532), 18, GREEN)
        for i in range(self.capacity):
            bx = 126 - (self.capacity - 1) * 17 + i * 34
            pygame.draw.circle(s, (236, 226, 198), (bx, 560), 13)
            berry_icon(s, (bx, 558), 15, i < self.carrying)
        self.card(pygame.Rect(250, 524, 533, 59), CREAM, 16)
        if self.delivery_time > 0:
            prompt = "Berries for our home!"
        elif self.carrying == self.capacity:
            prompt = "Basket full! Follow the dots home."
        elif self.notice_time > 0:
            prompt = self.notice
        elif self.carrying:
            prompt = "Find more berries, or take them home."
        else:
            prompt = "Tap a berry. Hedgie will walk to it."
        self.text(prompt, (517, 545), 24, max_width=498)
        self.text("Tap to walk  /  drag to guide  /  arrow keys", (517, 568), 18, (111, 126, 96))

    def _icon_button(self, rect, kind):
        s = self.canvas
        pygame.draw.rect(s, (229, 232, 201), rect, border_radius=13)
        x, y = rect.center
        if kind == "exit":
            pygame.draw.lines(s, GREEN, False, [(x + 8, y - 12), (x - 9, y - 12), (x - 9, y + 12), (x + 8, y + 12)], 3)
            pygame.draw.line(s, GREEN, (x - 2, y), (x + 13, y), 3)
            pygame.draw.lines(s, GREEN, False, [(x + 7, y - 6), (x + 13, y), (x + 7, y + 6)], 3)
        elif kind == "pause":
            pygame.draw.rect(s, GREEN, (x - 9, y - 10, 6, 20), border_radius=2)
            pygame.draw.rect(s, GREEN, (x + 3, y - 10, 6, 20), border_radius=2)
        else:
            pygame.draw.polygon(s, GREEN, [(x - 11, y - 5), (x - 5, y - 5), (x + 1, y - 11), (x + 1, y + 11), (x - 5, y + 5), (x - 11, y + 5)])
            if kind == "mute":
                pygame.draw.line(s, BERRY, (x + 6, y - 7), (x + 15, y + 7), 3)
                pygame.draw.line(s, BERRY, (x + 15, y - 7), (x + 6, y + 7), 3)
            else:
                pygame.draw.arc(s, GREEN, (x - 1, y - 10, 18, 20), -0.9, 0.9, 3)

    def _draw_reward_art(self, stage, center=(400, 273)):
        x, y = center
        pygame.draw.ellipse(self.canvas, (229, 230, 189), (x - 139, y - 52, 278, 105))
        if stage == 0:
            self._draw_bed((x + 10, y + 12), 1.55)
            image = pygame.transform.smoothscale(self.art.hedgie_left, (69, 55))
            self.canvas.blit(image, image.get_rect(center=(x - 11, y - 2)))
            heart(self.canvas, (x + 45, y - 37), 12)
        elif stage == 1:
            for i in range(5):
                bx, by = x - 88 + i * 44, y + 14 - (i % 2) * 18
                pygame.draw.ellipse(self.canvas, (142, 167, 103), (bx - 24, by - 3, 48, 23))
                pygame.draw.line(self.canvas, GREEN, (bx, by), (bx, by - 32), 4)
                self.flower(self.canvas, (bx, by - 34), (239, 159, 136), 2)
                berry_icon(self.canvas, (bx + 8, by - 9), 17)
        else:
            self._draw_picnic((x, y + 15), 1.2)
            for i, (dx, dy) in enumerate(((-110, 0), (106, 0), (0, -45))):
                image = self.art.hedgie_left if i == 1 else self.art.hedgie
                image = pygame.transform.smoothscale(image, (55, 43))
                self.canvas.blit(image, image.get_rect(center=(x + dx, y + dy)))
                heart(self.canvas, (x + dx, y + dy - 34), 8)

    def _draw_panel(self):
        s = self.canvas
        s.blit(self.veil, (0, 0))
        # Exit and sound remain reachable; all other background input is blocked.
        self.card(pygame.Rect(151, 119, 498, 393), CREAM, 27)
        if self.welcome:
            self.text("Hello, little Hedgie!", (400, 158), 40, GREEN)
            self.text("Let's make a cosy home.", (400, 194), 24)
            if self.has_played:
                self._draw_reward_art(self.stage_index)
                self.text("Your berries are safe. Ready to carry on?", (400, 365), 24, max_width=440)
                label = "Continue"
            else:
                # A visual collect -> carry -> home tutorial needs no reading.
                berry_icon(s, (264, 274), 44)
                s.blit(self.art.hedgie, self.art.hedgie.get_rect(center=(400, 274)))
                pygame.draw.polygon(s, GREEN, [(493, 270), (530, 241), (567, 270)])
                pygame.draw.rect(s, (186, 145, 91), (503, 268, 54, 43), border_radius=8)
                pygame.draw.rect(s, (90, 82, 55), (523, 285, 16, 26), border_radius=6)
                for x in (323, 455):
                    pygame.draw.line(s, (163, 174, 124), (x - 14, 275), (x + 10, 275), 4)
                    pygame.draw.polygon(s, (163, 174, 124), [(x + 17, 275), (x + 5, 267), (x + 5, 283)])
                self.text("Find", (264, 332), 24)
                self.text("Carry", (400, 332), 24)
                self.text("Bring home", (530, 332), 24)
                self.text("Tap where you want to go.", (400, 375), 24)
                label = "Let's play!"
        elif self.state == "pause":
            self.text("A little rest", (400, 170), 40, GREEN)
            self._draw_reward_art(0)
            self.text("Hedgie and the berries can wait.", (400, 367), 24)
            label = "Keep playing"
        else:
            self.text(self.stage["reward"], (400, 161), 34, GREEN, max_width=442)
            self._draw_reward_art(self.stage_index)
            self.text(self.stage["next"], (400, 349), 24)
            if self.state == "win":
                self.text("24 berries shared. Three lovely things made.", (400, 384), 22, max_width=440)
                label = "Play again"
            else:
                next_capacity = STAGES[self.stage_index + 1]["capacity"]
                self.text("Your basket grows!", (400, 380), 22)
                for i in range(next_capacity):
                    berry_icon(s, (400 - (next_capacity - 1) * 10 + i * 20, 403), 12)
                label = "Let's go!"
        self.card(self.ACTION, GREEN, 20)
        self.text(label, self.ACTION.center, 30, CREAM)
        self._icon_button(self.EXIT, "exit")
        self._icon_button(self.SOUND, "mute" if self.muted else "sound")

    def draw(self):
        s = self.canvas
        s.blit(self.background, (0, 0))
        self._draw_home()
        self._draw_trail()
        if self.state == "play" and not self.welcome and self.delivery_time <= 0 and self.pos.distance_squared_to(self.target) > 20 ** 2:
            pygame.draw.circle(s, (242, 234, 179), point(self.target), 11, 2)
            pygame.draw.circle(s, (242, 234, 179), point(self.target), 3)
        for berry in self.berries:
            if berry["active"]:
                self._draw_berry(berry)
        if self.stage_index >= 1 and not self.lantern_collected:
            self._draw_lantern(self.lantern)
        # Draw the two moving characters by their feet, for consistent depth.
        neighbour_first = self.neighbour.y < self.pos.y
        if self.stage_index >= 1 and neighbour_first:
            self._draw_neighbour()
        self._draw_player()
        if self.stage_index >= 1 and not neighbour_first:
            self._draw_neighbour()
        for flow in self.flows:
            if flow["time"] >= 0:
                t = min(1, flow["time"] / 0.6)
                pos = flow["start"].lerp(flow["end"], t)
                pos.y -= math.sin(t * math.pi) * 48
                berry_icon(s, pos, 17)
        for p in self.particles:
            r = max(1, round(min(1, p["life"] * 2) * 3))
            pygame.draw.circle(s, p["color"], point(p["pos"]), r)
        self._draw_hud()
        if self.welcome or self.state in ("pause", "reward", "win"):
            self._draw_panel()
        self._layout_viewport()
        self.screen.fill((43, 66, 51))
        if self.viewport.size == (WIDTH, HEIGHT):
            self.screen.blit(s, self.viewport)
        else:
            self.screen.blit(pygame.transform.smoothscale(s, self.viewport.size), self.viewport)

    def _draw_neighbour(self):
        image = self.art.friend_left if self.neighbour_left else self.art.friend
        x, y = self.neighbour
        pygame.draw.ellipse(self.canvas, (132, 159, 103), (x - 25, y + 13, 50, 12))
        self.canvas.blit(image, image.get_rect(center=point(self.neighbour)))
        heart(self.canvas, (x, y - 34 + math.sin(self.time * 2) * 2), 6, (251, 229, 175))


GAME = None
RUNNING = False


def ret():
    """Return to GameHub without quitting its shared display or mixer."""
    global RUNNING
    RUNNING = False
    if GAME is not None:
        GAME.close()


def setup(screen, clock):
    global GAME, SCREEN, CLOCK, RUNNING
    SCREEN, CLOCK = screen, clock
    GAME = HedgieGame(screen, clock)
    RUNNING = True


def update(dt=None):
    global RUNNING
    if GAME is None:
        return
    now = pygame.time.get_ticks()
    if dt is None:
        dt = (now - GAME.last_ticks) / 1000
    GAME.last_ticks = now
    for event in pygame.event.get():
        GAME.handle_event(event)
        if not GAME.running:
            break
    if GAME.running:
        GAME.tick(dt)
    RUNNING = GAME.running


def draw():
    if GAME is not None:
        GAME.draw()
        pygame.display.flip()


async def main(screen, clock):
    setup(screen, clock)
    try:
        while RUNNING:
            update(clock.tick(FPS) / 1000)
            draw()
            await asyncio.sleep(0)
    finally:
        GAME.persist()


def debug_main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Hungry Hedgie")
    asyncio.run(main(screen, pygame.time.Clock()))
    pygame.quit()


if __name__ == "__main__":
    debug_main()
