"""WastePilot – a Mode 7-style helicopter ring-and-coin course for GameHub.

Drop-in replacement for WasteGame/wastePilot.py. All art uses the existing
assets/wastePilot directory; no additional images or libraries are required.

Entry point: await main(screen, clock)
"""

import asyncio
import math
import random
from functools import lru_cache

import numpy as np
import pygame
import pygame.surfarray

from GUI import Button


# The old Mode 7 map uses hundreds of thousands of ground projection units.
# Converting the altitude display to this projection scale lets rings and
# coins genuinely sit above the terrain rather than on the horizon.
ALT_SCALE = 1000.0
MIN_ALT = 65.0
MAX_ALT = 360.0
START_ALT = 190.0
TARGET_FPS = 60
BASE_SPEED = 275.0
BOOST_SPEED = 390.0
TURN_SPEED = 79.0
CLIMB_SPEED = 57.0
COLLECT_RADIUS = 65.0
COIN_ALT_TOLERANCE = 20.0

HELICOPTERS = [
    {"name": "SKY SCOUT", "color": (253, 190, 63), "trim": (246, 106, 49),
     "detail": "Amber patrol livery"},
    {"name": "RESCUE ONE", "color": (242, 244, 236), "trim": (238, 82, 74),
     "detail": "White and red rescue livery"},
    {"name": "NIGHT HAWK", "color": (83, 199, 198), "trim": (45, 74, 110),
     "detail": "Teal and midnight livery"},
]

COURSES = [
    {"name": "COASTAL WARM-UP", "gates": 6, "time": 70.0,
     "side": [0, 110, -100, 155, -145, 40],
     "alt": [190, 204, 184, 217, 195, 210],
     "ring_radius": 94.0, "ring_alt": 30.0, "accent": (76, 237, 228)},
    {"name": "LOW & HIGH", "gates": 8, "time": 83.0,
     "side": [0, -150, 175, 35, -205, 160, -105, 60],
     "alt": [195, 232, 182, 255, 207, 164, 230, 192],
     "ring_radius": 82.0, "ring_alt": 25.0, "accent": (255, 200, 82)},
    {"name": "ACE PILOT", "gates": 10, "time": 101.0,
     "side": [0, 160, -205, 150, -95, 225, -195, 95, -145, 30],
     "alt": [190, 242, 190, 270, 205, 155, 241, 177, 265, 200],
     "ring_radius": 73.0, "ring_alt": 22.0, "accent": (244, 117, 198)},
]


def clamp(value, lo, hi):
    return max(lo, min(value, hi))


def mix(a, b, amount):
    return a + (b - a) * amount


def brighten(color, factor):
    return tuple(int(clamp(c * factor, 0, 255)) for c in color)


@lru_cache(maxsize=44)
def font(size, bold=False):
    # pygame's default font is available in both desktop builds and Pygbag.
    return pygame.font.Font(None, max(12, int(size)))


def text(surface, label, x, y, size=24, color=(255, 255, 255),
         center=False, bold=False, shadow=True):
    label = str(label)
    face = font(size, bold)
    image = face.render(label, True, color)
    rect = image.get_rect()
    if center:
        rect.center = (int(x), int(y))
    else:
        rect.topleft = (int(x), int(y))
    if shadow:
        dark = face.render(label, True, (14, 25, 37))
        surface.blit(dark, rect.move(1, 2))
    surface.blit(image, rect)
    return rect


def panel(surface, rect, color=(10, 28, 48), alpha=216, radius=13,
          outline=None):
    rect = pygame.Rect(rect)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, alpha), layer.get_rect(),
                     border_radius=radius)
    if outline is not None:
        pygame.draw.rect(layer, (*outline, 200), layer.get_rect(),
                         width=2, border_radius=radius)
    surface.blit(layer, rect.topleft)


def load_image(path, alpha=True):
    image = pygame.image.load(path)
    return image.convert_alpha() if alpha else image.convert()


class Coin:
    def __init__(self, x, y, z, valuable=False):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.valuable = valuable
        self.value = 30 if valuable else 10
        self.phase = random.random() * math.tau
        self.taken = False


class Ring:
    def __init__(self, x, y, z, radius, vertical):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.radius = float(radius)
        self.vertical = float(vertical)
        self.resolved = False
        self.passed = False


class Spark:
    """Lightweight feedback particle in screen space."""
    def __init__(self, x, y, color):
        angle = random.random() * math.tau
        speed = random.uniform(35, 130)
        self.x = float(x)
        self.y = float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.uniform(.27, .58)
        self.total = self.life
        self.color = color

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 65 * dt
        self.life -= dt

    def draw(self, surface):
        if self.life > 0:
            size = max(1, int(4 * self.life / self.total))
            pygame.draw.circle(surface, self.color,
                               (int(self.x), int(self.y)), size)


class FlightGame:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.w, self.h = screen.get_size()
        self.home = Button(10, 10, 100, 100,
                           "assets/retBut.png", "assets/retBut_clicked.png",
                           self.leave)
        self.running = True
        self.state = "select"
        self.helicopter = 0
        self.course_index = 0
        self.map_image = load_image("assets/wastePilot/map_lrg.jpg", False)
        self.map_array = pygame.surfarray.array3d(self.map_image)
        self.map_w, self.map_h = self.map_image.get_size()
        # Fixed geometry avoids building a full (800x600) Python pixel grid.
        self.scan_step = 2
        self.x_rays = np.linspace(-1.0, 1.0, self.w, dtype=np.float32)[None, :]
        self.sky = load_image("assets/wastePilot/sky.png", False)
        self.sky_strip = pygame.transform.smoothscale(
            self.sky, (max(self.w, 1), max(1, int(self.h * .43))))
        self.cockpit = load_image("assets/wastePilot/cockpit_2.png")
        if self.cockpit.get_size() != (self.w, self.h):
            self.cockpit = pygame.transform.smoothscale(self.cockpit,
                                                        (self.w, self.h))
        self.coin_frames = [load_image(
            "assets/wastePilot/coin/star coin rotate %d.png" % i)
            for i in range(1, 6)]
        self.coin_cache = {}
        self.pointers = {}
        self.down_keys = set()
        self.mouse_down = False
        self.mouse_pos = (0, 0)
        self.anim = 0.0
        self.ui_pressed = set()
        self.notice = ""
        self.notice_timer = 0.0
        self.sparks = []
        self.popups = []
        self.setup_flight(0)

    def leave(self):
        self.running = False

    @property
    def accent(self):
        return HELICOPTERS[self.helicopter]["color"]

    @property
    def mission(self):
        return COURSES[self.course_index]

    def setup_flight(self, index):
        self.course_index = index
        self.px = 800.0
        self.py = 600.0
        self.angle = -90.0
        self.alt = START_ALT
        self.speed = BASE_SPEED * .75
        self.elapsed = 0.0
        self.score = 0
        self.coins_collected = 0
        self.coins_total = 0
        self.coin_streak = 0
        self.streak_timer = 0.0
        self.gates_passed = 0
        self.gates_missed = 0
        self.next_gate = 0
        self.rings = []
        self.coins = []
        self.sparks = []
        self.popups = []
        self.notice = "LINE UP WITH THE FIRST RING"
        self.notice_timer = 3.4
        self.pointers.clear()
        self.mouse_down = False
        self.make_course()

    def make_course(self):
        conf = self.mission
        start_x, start_y = self.px, self.py
        previous_x, previous_y, previous_z = start_x, start_y, START_ALT
        # Course geometry is in continuous world space. Only the terrain
        # texture wraps; waypoint placement never jumps across map seams.
        for i in range(conf["gates"]):
            x = start_x + conf["side"][i]
            y = start_y - 760 - 600 * i
            z = conf["alt"][i]
            ring = Ring(x, y, z, conf["ring_radius"], conf["ring_alt"])
            self.rings.append(ring)
            # A staggered 3D approach trail nudges pilots towards the ring
            # while demanding that they match its height to earn coins.
            for step in range(1, 6):
                t = step / 6.0
                cx = mix(previous_x, x, t)
                cy = mix(previous_y, y, t)
                cz = mix(previous_z, z, t)
                self.coins.append(Coin(cx, cy, cz,
                                       valuable=(step == 5)))
            # Two optional coins are deliberately off the ideal line, at
            # different heights. A perfect line cannot collect every coin.
            if i > 0:
                self.coins.append(Coin(x + (-105 if i % 2 else 105),
                                       y + 190, clamp(z + 39, MIN_ALT, MAX_ALT),
                                       valuable=True))
                self.coins.append(Coin(x + (125 if i % 2 else -125),
                                       y + 255, clamp(z - 37, MIN_ALT, MAX_ALT),
                                       valuable=True))
            previous_x, previous_y, previous_z = x, y, z
        self.coins_total = len(self.coins)

    def horizon(self):
        return int(self.h * .34)

    def project(self, x, y, z):
        """Perspective: x/y world bearing and *actual* z altitude."""
        dx, dy = x - self.px, y - self.py
        rad = math.radians(self.angle)
        ca, sa = math.cos(rad), math.sin(rad)
        ahead = ca * dx + sa * dy
        side = -sa * dx + ca * dy
        if ahead <= 15:
            return None
        focal = self.w * .5
        sx = self.w * .5 + focal * side / ahead
        sy = self.horizon() + (self.alt - z) * ALT_SCALE / ahead
        return sx, sy, ahead, side

    def add_notice(self, message, duration=1.65):
        self.notice = message
        self.notice_timer = duration

    def burst(self, x, y, color, amount=10):
        for _ in range(amount):
            self.sparks.append(Spark(x, y, color))

    def popup(self, value, x, y, color):
        self.popups.append([str(value), float(x), float(y), 1.1, color])

    def get_control_rects(self):
        # Wide, bottom-anchored targets work with both fingers and mice.
        width = min(self.w * .176, 126)
        height = clamp(self.h * .126, 56, 83)
        bottom = self.h - height - 10
        centers = [.09, .285, .5, .715, .91]
        names = ("left", "up", "boost", "down", "right")
        result = {}
        for name, center in zip(names, centers):
            result[name] = pygame.Rect(int(self.w * center - width / 2),
                                       int(bottom), int(width), int(height))
        return result

    def all_pointer_positions(self):
        points = list(self.pointers.values())
        if self.mouse_down:
            points.append(self.mouse_pos)
        return points

    def controls(self, keys):
        rects = self.get_control_rects()
        held = set()
        for point in self.all_pointer_positions():
            for name, rect in rects.items():
                if rect.collidepoint(point):
                    held.add(name)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            held.add("left")
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            held.add("right")
        if keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_f]:
            held.add("up")
        if keys[pygame.K_s] or keys[pygame.K_DOWN] or keys[pygame.K_r]:
            held.add("down")
        if keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT]:
            held.add("boost")
        self.ui_pressed = held
        return held

    def update_flight(self, dt, keys):
        self.anim += dt
        self.elapsed += dt
        self.notice_timer = max(0.0, self.notice_timer - dt)
        self.streak_timer -= dt
        if self.streak_timer <= 0:
            self.coin_streak = 0
        held = self.controls(keys)
        turn = int("right" in held) - int("left" in held)
        lift = int("up" in held) - int("down" in held)
        self.angle += turn * TURN_SPEED * dt
        self.alt = clamp(self.alt + lift * CLIMB_SPEED * dt, MIN_ALT, MAX_ALT)
        target_speed = BOOST_SPEED if "boost" in held else BASE_SPEED
        self.speed += (target_speed - self.speed) * min(1.0, dt * 2.8)
        rad = math.radians(self.angle)
        self.px += math.cos(rad) * self.speed * dt
        self.py += math.sin(rad) * self.speed * dt
        self.update_collectibles()
        self.update_particles(dt)
        if self.next_gate >= len(self.rings) or self.elapsed >= self.mission["time"]:
            # Remaining gates count as misses on a timed-out run.
            if self.elapsed >= self.mission["time"]:
                self.gates_missed += len(self.rings) - self.next_gate
                self.next_gate = len(self.rings)
            self.state = "results"
            self.mouse_down = False
            self.pointers.clear()

    def update_collectibles(self):
        # Collect by 3D proximity, not by touching an arbitrary 2D sprite.
        for coin in self.coins:
            if coin.taken:
                continue
            dx, dy = coin.x - self.px, coin.y - self.py
            if dx * dx + dy * dy > COLLECT_RADIUS ** 2:
                continue
            if abs(self.alt - coin.z) > COIN_ALT_TOLERANCE:
                continue
            coin.taken = True
            self.coins_collected += 1
            self.coin_streak += 1
            self.streak_timer = 3.2
            multiplier = min(5, 1 + self.coin_streak // 4)
            points = coin.value * multiplier
            self.score += points
            position = self.project(coin.x, coin.y, coin.z)
            fx, fy = (position[0], position[1]) if position else (self.w // 2, self.horizon())
            fx, fy = clamp(fx, 0, self.w), clamp(fy, 85, self.h - 120)
            hue = (255, 218, 91) if coin.valuable else (255, 245, 174)
            self.burst(fx, fy, hue, 13 if coin.valuable else 8)
            self.popup("+%d  x%d" % (points, multiplier), fx, fy - 20, hue)
            if coin.valuable:
                self.add_notice("GOLD COIN!  +%d" % points, 1.0)

        if self.next_gate >= len(self.rings):
            return
        gate = self.rings[self.next_gate]
        dx = gate.x - self.px
        dy = gate.y - self.py
        # Success requires lateral AND altitude precision, with forward
        # motion through the ring. Intersecting its display sprite is not enough.
        # Gates face north because each predefined course advances north.
        north_distance = -dy
        lateral_distance = abs(dx)
        altitude_distance = abs(gate.z - self.alt)
        if abs(north_distance) < 48 and lateral_distance <= gate.radius and altitude_distance <= gate.vertical:
            gate.resolved = True
            gate.passed = True
            self.gates_passed += 1
            self.next_gate += 1
            bonus = 350 + 50 * self.course_index
            if lateral_distance < gate.radius * .45 and altitude_distance < gate.vertical * .45:
                bonus += 200
                self.add_notice("PERFECT RING  +%d" % bonus, 2.0)
            else:
                self.add_notice("RING CLEAR  +%d" % bonus, 1.7)
            self.score += bonus
            self.burst(self.w / 2, self.horizon(), self.mission["accent"], 26)
            self.popup("+%d" % bonus, self.w / 2, self.horizon() + 30,
                       self.mission["accent"])
        elif self.py < gate.y - 145:
            # The course continues after a missed ring, so one error never
            # forces players into a tedious U-turn around the entire map.
            gate.resolved = True
            self.gates_missed += 1
            self.next_gate += 1
            self.coin_streak = 0
            self.add_notice("RING MISSED - LINE UP THE NEXT ONE", 1.8)

    def update_particles(self, dt):
        for spark in self.sparks:
            spark.update(dt)
        self.sparks = [p for p in self.sparks if p.life > 0]
        for popup in self.popups:
            popup[2] -= 37 * dt
            popup[3] -= dt
        self.popups = [p for p in self.popups if p[3] > 0]

    def draw_terrain(self):
        self.screen.fill((119, 169, 214))
        horizon = self.horizon()
        # Keep the original sky texture while avoiding per-scanline slicing.
        offset = int((self.angle + 90) / 360.0 * self.w) % self.w
        self.screen.blit(self.sky_strip, (-offset, 0))
        self.screen.blit(self.sky_strip, (self.w - offset, 0))
        pygame.draw.line(self.screen, (193, 214, 218),
                         (0, horizon), (self.w, horizon), 2)
        if horizon >= self.h:
            return
        scanlines = np.arange(horizon, self.h, self.scan_step)
        rel = np.maximum(1, scanlines - horizon + 1).astype(np.float32)
        distance = (self.alt * ALT_SCALE / rel)[:, None]
        theta = math.radians(self.angle)
        forward_x, forward_y = math.cos(theta), math.sin(theta)
        right_x, right_y = -forward_y, forward_x
        # At the screen edges the ray is +/-45 degrees from the bearing.
        positions_x = (self.px + distance *
                       (forward_x + right_x * self.x_rays))
        positions_y = (self.py + distance *
                       (forward_y + right_y * self.x_rays))
        xs = np.mod(positions_x.astype(np.int32), self.map_w)
        ys = np.mod(positions_y.astype(np.int32), self.map_h)
        colors = self.map_array[xs, ys]  # (number of rows, width, RGB)
        surface_array = pygame.surfarray.pixels3d(self.screen)
        try:
            for i, sy in enumerate(scanlines):
                surface_array[:, sy] = colors[i]
                if sy + 1 < self.h:
                    surface_array[:, sy + 1] = colors[i]
        finally:
            del surface_array

    def draw_coin(self, coin):
        projected = self.project(coin.x, coin.y,
                                 coin.z + math.sin(self.anim * 3 + coin.phase) * 2.3)
        if projected is None:
            return
        x, y, ahead, _ = projected
        if ahead > 2100 or x < -90 or x > self.w + 90 or y < -85 or y > self.h + 95:
            return
        size = int(clamp(16000 / ahead, 8, 76))
        frame = int(self.anim * 11 + coin.phase) % len(self.coin_frames)
        key = (frame, size)
        image = self.coin_cache.get(key)
        if image is None:
            original = self.coin_frames[frame]
            width, height = original.get_size()
            new_w = max(1, round(size * width / max(width, height)))
            new_h = max(1, round(size * height / max(width, height)))
            image = pygame.transform.smoothscale(original, (new_w, new_h))
            if len(self.coin_cache) > 300:
                self.coin_cache.clear()
            self.coin_cache[key] = image
        if coin.valuable:
            pygame.draw.circle(self.screen, (255, 197, 50), (int(x), int(y)),
                               int(size * .58), max(1, int(size / 13)))
        self.screen.blit(image, image.get_rect(center=(int(x), int(y))))
        # Nearby altitude markers make a high or low coin visually distinct.
        if ahead < 850 and size >= 15:
            text(self.screen, "%dm" % round(coin.z), x, y + size * .54 + 2,
                 max(15, min(19, size // 2)), (229, 251, 255), center=True)

    def draw_ring(self, ring, active):
        projected = self.project(ring.x, ring.y, ring.z)
        if projected is None:
            return
        x, y, ahead, _ = projected
        if ahead > 3000:
            return
        xr = clamp(self.w * .5 * ring.radius / ahead, 8, 350)
        yr = clamp(ALT_SCALE * ring.vertical / ahead, 8, 300)
        if x + xr < -30 or x - xr > self.w + 30 or y + yr < -35 or y - yr > self.h + 35:
            return
        accent = self.mission["accent"] if active else (116, 169, 179)
        outline = (26, 74, 96)
        points = []
        for n in range(33):
            theta = math.tau * n / 32
            points.append((int(x + math.cos(theta) * xr),
                           int(y + math.sin(theta) * yr)))
        thick = int(clamp(xr / 18, 2, 10))
        pygame.draw.lines(self.screen, outline, True, points, thick + 4)
        pygame.draw.lines(self.screen, accent, True, points, thick)
        pygame.draw.lines(self.screen, brighten(accent, 1.38), False,
                          points[16:29], max(1, thick // 2))
        if active:
            # Central aiming cross only on the current ring.
            center = (int(x), int(y))
            pygame.draw.circle(self.screen, brighten(accent, 1.2), center,
                               max(3, int(min(xr, yr) * .13)), 1)
            if 55 < ahead < 1300:
                info = "%dm" % round(ring.z)
                text(self.screen, info, x, y - yr - 25, 21, accent, center=True)

    def draw_world_objects(self):
        objects = []
        # Sort far to near so coins and rings occlude each other coherently.
        for coin in self.coins:
            if not coin.taken:
                projected = self.project(coin.x, coin.y, coin.z)
                if projected and projected[2] < 2150:
                    objects.append((projected[2], 0, coin))
        for n, ring in enumerate(self.rings):
            if not ring.resolved and n <= self.next_gate + 2:
                projected = self.project(ring.x, ring.y, ring.z)
                if projected and projected[2] < 3000:
                    objects.append((projected[2], 1, (ring, n == self.next_gate)))
        objects.sort(key=lambda obj: -obj[0])
        for _, kind, obj in objects:
            if kind == 0:
                self.draw_coin(obj)
            else:
                self.draw_ring(obj[0], obj[1])

    def draw_helicopter(self, surface, center, size, index):
        """Asset-free vector helicopter for selection and cockpit insignia."""
        scheme = HELICOPTERS[index]
        color = scheme["color"]
        trim = scheme["trim"]
        x, y = center
        scale = size / 150.0

        def p(dx, dy):
            return int(x + dx * scale), int(y + dy * scale)

        pygame.draw.line(surface, (36, 54, 72), p(-80, -15), p(80, -15),
                         max(3, int(8 * scale)))
        pygame.draw.line(surface, (30, 51, 65), p(-73, -52), p(73, 22),
                         max(1, int(4 * scale)))
        pygame.draw.line(surface, (30, 51, 65), p(-73, 22), p(73, -52),
                         max(1, int(4 * scale)))
        pygame.draw.polygon(surface, (24, 39, 52),
                            [p(-14, 0), p(14, 0), p(6, 87), p(-6, 87)])
        pygame.draw.polygon(surface, color,
                            [p(0, -52), p(19, -38), p(25, 19),
                             p(13, 48), p(-13, 48), p(-25, 19), p(-19, -38)])
        pygame.draw.polygon(surface, trim,
                            [p(-20, 10), p(20, 10), p(17, 23), p(-17, 23)])
        pygame.draw.ellipse(surface, (24, 62, 84),
                            pygame.Rect(p(-16, -43), (int(32 * scale), int(36 * scale))))
        pygame.draw.line(surface, brighten(color, .7), p(-20, -34), p(20, -34),
                         max(2, int(3 * scale)))
        pygame.draw.line(surface, (28, 45, 60), p(-22, 58), p(22, 58),
                         max(1, int(4 * scale)))

    def draw_rotor(self):
        # Subtle translucent sweep instead of the original huge opaque circles.
        width = self.w
        layer = pygame.Surface((width, 24), pygame.SRCALPHA)
        r = int((self.anim * 11) % 80)
        pygame.draw.ellipse(layer, (213, 232, 239, 36),
                            (-40 + r, 0, width + 80, 10), 2)
        pygame.draw.line(layer, (194, 219, 227, 25), (0, 8), (width, 8), 2)
        self.screen.blit(layer, (0, 0))

    def draw_compass(self):
        if self.next_gate >= len(self.rings):
            return
        ring = self.rings[self.next_gate]
        dx, dy = ring.x - self.px, ring.y - self.py
        angle_to = math.degrees(math.atan2(dy, dx))
        error = (angle_to - self.angle + 180) % 360 - 180
        # Heading cue is useful even while the target is out of view.
        cx, y = self.w // 2, int(self.h * .17)
        panel(self.screen, (cx - 111, y - 18, 222, 36),
              (13, 37, 58), 193, 14)
        for offset in (-60, -30, 0, 30, 60):
            xp = cx + offset
            pygame.draw.line(self.screen, (104, 155, 174),
                             (xp, y - 5), (xp, y + 6), 1)
        target_x = cx + clamp(error * 1.35, -95, 95)
        pygame.draw.polygon(self.screen, self.mission["accent"],
                            [(int(target_x), y - 13),
                             (int(target_x) - 7, y - 2),
                             (int(target_x) + 7, y - 2)])
        pygame.draw.line(self.screen, (244, 247, 250),
                         (cx, y + 4), (cx, y + 12), 2)

    def draw_altitude_gauge(self):
        if self.next_gate >= len(self.rings):
            return
        ring = self.rings[self.next_gate]
        diff = round(ring.z - self.alt)
        gauge_h = max(103, int(self.h * .23))
        x = self.w - 77
        y = int(self.h * .30)
        panel(self.screen, (x - 12, y - 38, 75, gauge_h + 65),
              (10, 28, 49), 206, 13, (73, 128, 151))
        text(self.screen, "ALT", x + 25, y - 30, 20,
             (217, 234, 243), center=True)
        pygame.draw.line(self.screen, (76, 116, 137),
                         (x + 16, y + 5), (x + 16, y + gauge_h - 3), 4)
        def alt_y(alt):
            return int(y + gauge_h - 4 - (alt - MIN_ALT) /
                       (MAX_ALT - MIN_ALT) * (gauge_h - 8))
        ty = alt_y(ring.z)
        py = alt_y(self.alt)
        pygame.draw.line(self.screen, self.mission["accent"],
                         (x + 5, ty), (x + 29, ty), 4)
        pygame.draw.polygon(self.screen, (255, 255, 255),
                            [(x + 16, py - 6), (x + 29, py), (x + 16, py + 6)])
        text(self.screen, "%dm" % round(self.alt), x + 25, y + gauge_h + 12,
             17, (255, 255, 255), center=True)
        if abs(diff) <= ring.vertical:
            guide, color = "LEVEL", (99, 245, 183)
        elif diff > 0:
            guide, color = "+%dm" % diff, (255, 208, 84)
        else:
            guide, color = "%dm" % diff, (255, 147, 125)
        text(self.screen, guide, x + 25, y - 8, 19, color, center=True)

    def draw_hud(self):
        w = self.w
        accent = self.mission["accent"]
        panel(self.screen, (124, 6, w - 136, 66), (12, 28, 48), 223, 12)
        text(self.screen, "GATE %d/%d" % (self.next_gate + 1 if self.next_gate < len(self.rings) else len(self.rings),
                                          len(self.rings)), 140, 12, 28, accent)
        text(self.screen, self.mission["name"], 140, 42, 18,
             (201, 225, 239))
        # The right-hand score is anchored independently of mission length.
        right_mask = pygame.Rect(w - 212, 8, 199, 32)
        panel(self.screen, right_mask, (12, 28, 48), 249, 8)
        score_img = font(28).render("%d PTS" % self.score, True, (255, 230, 159))
        self.screen.blit(score_img,
                         (w - 24 - score_img.get_width(), 12))
        clock_x = int(w * .46)
        remaining = max(0.0, self.mission["time"] - self.elapsed)
        text(self.screen, "TIME %02d" % int(math.ceil(remaining)),
             clock_x, 41, 20, (246, 247, 253))
        text(self.screen, "COINS %d" % self.coins_collected,
             int(w * .63), 41, 20, (255, 222, 124))
        if self.coin_streak >= 4:
            text(self.screen, "COMBO x%d" % min(5, 1 + self.coin_streak // 4),
                 int(w * .76), 41, 20, (123, 244, 196))
        self.draw_compass()
        self.draw_altitude_gauge()
        if self.notice_timer > 0:
            width = min(w - 170, 490)
            y = int(self.h * .25)
            panel(self.screen, (w / 2 - width / 2, y - 17, width, 38),
                  (12, 34, 50), 195, 9)
            text(self.screen, self.notice, w / 2, y + 2,
                 min(23, int(w / max(19, len(self.notice)) * 1.3)),
                 (249, 246, 221), center=True)
        # Camera reticle shows the actual flight path through the ring.
        cy = self.horizon()
        pygame.draw.line(self.screen, (255, 252, 222),
                         (w // 2 - 14, cy), (w // 2 - 5, cy), 1)
        pygame.draw.line(self.screen, (255, 252, 222),
                         (w // 2 + 5, cy), (w // 2 + 14, cy), 1)
        pygame.draw.line(self.screen, (255, 252, 222),
                         (w // 2, cy - 11), (w // 2, cy - 4), 1)
        pygame.draw.line(self.screen, (255, 252, 222),
                         (w // 2, cy + 4), (w // 2, cy + 11), 1)

    def draw_controls(self):
        names = ("left", "up", "boost", "down", "right")
        labels = ("TURN L", "CLIMB", "BOOST", "DIVE", "TURN R")
        symbols = ("<", "+", ">>", "-", ">")
        for name, label, symbol in zip(names, labels, symbols):
            rect = self.get_control_rects()[name]
            pressed = name in self.ui_pressed
            fill = self.accent if pressed else (15, 39, 61)
            outline = brighten(self.accent, .95) if pressed else (84, 141, 171)
            panel(self.screen, rect, fill, 233 if pressed else 215, 15, outline)
            ink = (17, 45, 58) if pressed else (242, 251, 255)
            text(self.screen, symbol, rect.centerx, rect.y + rect.h * .34,
                 int(clamp(rect.h * .47, 23, 39)), ink, center=True)
            text(self.screen, label, rect.centerx, rect.y + rect.h * .80,
                 17, ink, center=True)

    def draw_flight(self):
        self.draw_terrain()
        self.screen.blit(self.cockpit, (0, 0))
        self.draw_world_objects()
        self.draw_rotor()
        # Actual paint scheme visible through consistent panel trim / badge.
        pygame.draw.rect(self.screen, self.accent,
                         pygame.Rect(0, self.h - 9, self.w, 9))
        self.draw_helicopter(self.screen, (self.w - 120, self.h - 114), 45,
                             self.helicopter)
        for part in self.sparks:
            part.draw(self.screen)
        for message, x, y, life, color in self.popups:
            text(self.screen, message, x, y, 25, color, center=True)
        self.draw_hud()
        self.draw_controls()

    def selection_rects(self):
        pad = 28
        usable = self.w - pad * 2
        gap = 16
        card_w = (usable - gap * 2) / 3
        y = int(self.h * .27)
        height = int(self.h * .47)
        return [pygame.Rect(int(pad + i * (card_w + gap)), y,
                            int(card_w), height) for i in range(3)]

    def draw_select(self):
        self.draw_terrain()
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((5, 23, 41, 128))
        self.screen.blit(overlay, (0, 0))
        text(self.screen, "WASTE PILOT", self.w // 2, int(self.h * .10),
             58, (250, 252, 254), center=True)
        text(self.screen, "CHOOSE YOUR HELICOPTER", self.w // 2,
             int(self.h * .19), 25, (197, 225, 237), center=True)
        for index, rect in enumerate(self.selection_rects()):
            helicopter = HELICOPTERS[index]
            chosen = index == self.helicopter
            border = helicopter["color"] if chosen else (98, 141, 165)
            panel(self.screen, rect, (15, 42, 63), 239, 17, border)
            self.draw_helicopter(self.screen,
                                 (rect.centerx, int(rect.y + rect.h * .44)),
                                 min(rect.w * .52, rect.h * .60), index)
            text(self.screen, helicopter["name"], rect.centerx,
                 rect.y + 19, 26, helicopter["color"], center=True)
            text(self.screen, helicopter["detail"], rect.centerx,
                 rect.bottom - 39, 16, (213, 232, 238), center=True)
            if chosen:
                text(self.screen, "SELECTED", rect.centerx,
                     rect.bottom - 66, 17, (255, 255, 255), center=True)
        button = self.start_rect()
        panel(self.screen, button, self.accent, 245, 14)
        text(self.screen, "START FLIGHT", button.centerx, button.centery,
             29, (20, 39, 49), center=True)
        text(self.screen, "3 ring courses   /   Collect coins   /   Match altitude",
             self.w // 2, self.h - 20, 20, (223, 238, 241), center=True)

    def start_rect(self):
        return pygame.Rect(self.w // 2 - 128, int(self.h * .78), 256, 60)

    def grade(self):
        rate = self.gates_passed / max(1, len(self.rings))
        coin_rate = self.coins_collected / max(1, self.coins_total)
        time_ratio = min(1, self.elapsed / self.mission["time"])
        rating = rate * .77 + coin_rate * .15 + (1 - time_ratio) * .08
        if rate == 1 and rating >= .83:
            return "S", (255, 227, 113)
        if rate >= .8 and rating >= .69:
            return "A", (125, 234, 185)
        if rate >= .65 and rating >= .54:
            return "B", (112, 197, 249)
        if rate >= .45:
            return "C", (251, 178, 101)
        return "D", (252, 139, 135)

    def result_buttons(self):
        button_w, button_h = 180, 54
        y = int(self.h * .79)
        gap = 16
        x = self.w // 2 - button_w * 1.5 - gap
        return [pygame.Rect(int(x + i * (button_w + gap)), y,
                            button_w, button_h) for i in range(3)]

    def draw_results(self):
        self.draw_terrain()
        veil = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        veil.fill((5, 22, 41, 163))
        self.screen.blit(veil, (0, 0))
        main_rect = pygame.Rect(int(self.w * .12), int(self.h * .12),
                                int(self.w * .76), int(self.h * .75))
        panel(self.screen, main_rect, (12, 34, 53), 242, 20,
              self.mission["accent"])
        text(self.screen, "FLIGHT COMPLETE" if self.elapsed < self.mission["time"]
             else "TIME'S UP", self.w // 2, int(self.h * .18),
             35, (246, 250, 251), center=True)
        text(self.screen, self.mission["name"], self.w // 2,
             int(self.h * .245), 22, (185, 219, 233), center=True)
        tier, hue = self.grade()
        text(self.screen, tier, self.w // 2, int(self.h * .39), 119,
             hue, center=True)
        text(self.screen, "%d POINTS" % self.score,
             self.w // 2, int(self.h * .50), 38, (255, 231, 145), center=True)
        text(self.screen, "RINGS  %d/%d" %
             (self.gates_passed, len(self.rings)), self.w // 2,
             int(self.h * .59), 24, (233, 246, 250), center=True)
        text(self.screen, "COINS  %d/%d" %
             (self.coins_collected, self.coins_total), self.w // 2,
             int(self.h * .65), 23, (249, 219, 121), center=True)
        text(self.screen, "TIME  %.1fs" % self.elapsed,
             self.w // 2, int(self.h * .71), 23, (200, 221, 231), center=True)
        labels = ("NEXT COURSE" if self.course_index < len(COURSES) - 1
                  else "COURSE 1", "RETRY", "HANGAR")
        for label, rect in zip(labels, self.result_buttons()):
            panel(self.screen, rect, (27, 67, 88), 248, 11, hue)
            text(self.screen, label, rect.centerx, rect.centery,
                 22, (251, 251, 251), center=True)

    def on_click(self, pos):
        if self.state == "select":
            for n, rect in enumerate(self.selection_rects()):
                if rect.collidepoint(pos):
                    self.helicopter = n
                    return
            if self.start_rect().collidepoint(pos):
                self.setup_flight(0)
                self.state = "play"
        elif self.state == "results":
            for n, rect in enumerate(self.result_buttons()):
                if not rect.collidepoint(pos):
                    continue
                if n == 0:
                    self.setup_flight((self.course_index + 1) % len(COURSES))
                    self.state = "play"
                elif n == 1:
                    self.setup_flight(self.course_index)
                    self.state = "play"
                else:
                    self.state = "select"
                return

    def handle_events(self, events):
        finger_event_in_batch = any(event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)
                                    for event in events)
        for event in events:
            if event.type == pygame.QUIT:
                self.leave()
            elif event.type == pygame.FINGERDOWN:
                pos = (event.x * self.w, event.y * self.h)
                self.pointers[event.finger_id] = pos
                if self.state != "play":
                    self.on_click(pos)
            elif event.type == pygame.FINGERMOTION:
                if event.finger_id in self.pointers:
                    self.pointers[event.finger_id] = (event.x * self.w,
                                                       event.y * self.h)
            elif event.type == pygame.FINGERUP:
                self.pointers.pop(event.finger_id, None)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Most browsers synthesize mouse clicks for taps. Ignore
                # those when a real touch event is already being handled.
                if not (getattr(event, "touch", False) and finger_event_in_batch):
                    self.mouse_down = True
                    self.mouse_pos = event.pos
                    if self.state != "play":
                        self.on_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_down = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.leave()
                elif self.state == "select" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.setup_flight(0)
                    self.state = "play"
                elif self.state == "select" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self.helicopter = event.key - pygame.K_1
                elif self.state == "results" and event.key == pygame.K_RETURN:
                    self.setup_flight((self.course_index + 1) % len(COURSES))
                    self.state = "play"
                elif self.state == "results" and event.key == pygame.K_r:
                    self.setup_flight(self.course_index)
                    self.state = "play"

    async def run(self):
        while self.running:
            dt = clamp(self.clock.tick(TARGET_FPS) / 1000.0, 0.0, .05)
            events = pygame.event.get()
            self.handle_events(events)
            if not self.running:
                break
            if self.state == "play":
                self.update_flight(dt, pygame.key.get_pressed())
                if self.state == "play":
                    self.draw_flight()
                else:
                    self.draw_results()
            elif self.state == "select":
                self.anim += dt
                self.draw_select()
            else:
                self.anim += dt
                self.draw_results()
            self.home.update(events)
            self.home.draw(self.screen)
            pygame.display.flip()
            await asyncio.sleep(0)


async def main(screen, clock):
    """The original GameHub entry point; returns to the hub on Home."""
    game = FlightGame(screen, clock)
    await game.run()
