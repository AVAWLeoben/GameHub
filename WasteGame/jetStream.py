# -*- coding: utf-8 -*-
"""JetStream - GameHub arcade shooter. Pygame/Pygbag compatible.

Three missions: Carrier Strike, Desert Offensive (two bosses), Frozen Front.
All terrain, ground targets, and new bosses are drawn in Pygame: no new
asset files are required. GameHub entry point: await jetStream.main(screen, clock).
"""

import asyncio
import math
import random

import pygame
from GUI import Button

FPS = 60
RUNNING = True
SCREEN = None
CLOCK = None
EVENTS = []

ASSET = "assets/jetStream/"
MISSION_NAMES = ("CARRIER STRIKE", "DESERT OFFENSIVE", "FROZEN FRONT")
MISSION_LOCATIONS = ("OPEN SEA", "DUNE BADLANDS", "ARCTIC FRONT")
MISSION_OBJECTIVES = (
    "Break the enemy air and naval blockade.",
    "Destroy the Dune Fortress and Desert Ace.",
    "Clear the ice fields and defeat the Frost Gunship.",
)
BOSS_NAMES = {
    "Spacecraft": "ENEMY FLAGSHIP",
    "DuneFortress": "DUNE FORTRESS",
    "DesertAce": "DESERT ACE",
    "FrostGunship": "FROST GUNSHIP",
}
GROUND_TYPES = ("Tank", "AA", "SAM")
BOSS_TYPES = tuple(BOSS_NAMES)
SCORES = {"Plane": 100, "UBoat": 180, "Tank": 140, "AA": 170,
          "SAM": 220, "B17": 400, "Spacecraft": 2500,
          "DuneFortress": 3500, "DesertAce": 4000, "FrostGunship": 5000}
MAX_MISSIONS = 3
MISSION_BOSS_DESCRIPTIONS = (
    "ENEMY FLAGSHIP",
    "DUNE FORTRESS + DESERT ACE",
    "FROST GUNSHIP",
)
MISSION_COLORS = (
    (102, 209, 234),
    (245, 190, 107),
    (178, 225, 242),
)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def load_image(name, alpha=True):
    img = pygame.image.load(ASSET + name)
    return img.convert_alpha() if alpha else img.convert()


def fit_image(img, max_w, max_h):
    ratio = min(max_w / max(1, img.get_width()), max_h / max(1, img.get_height()))
    if ratio >= 0.999:
        return img.copy()
    return pygame.transform.smoothscale(img, (
        max(1, round(img.get_width() * ratio)),
        max(1, round(img.get_height() * ratio)),
    ))


def font(size):
    return pygame.font.Font(ASSET + "font.ttf", max(12, int(size)))


def text(surface, message, size, color, center=None, topleft=None, shadow=True):
    if size not in FONT_CACHE:
        FONT_CACHE[size] = font(size)
    img = FONT_CACHE[size].render(message, True, color)
    r = img.get_rect()
    if center is not None:
        r.center = (int(center[0]), int(center[1]))
    elif topleft is not None:
        r.topleft = (int(topleft[0]), int(topleft[1]))
    if shadow:
        shade = FONT_CACHE[size].render(message, True, (12, 17, 22))
        surface.blit(shade, r.move(2, 2))
    surface.blit(img, r)
    return r


def panel(surface, rect, color=(10, 21, 31, 205), radius=11):
    shade = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
    pygame.draw.rect(shade, color, shade.get_rect(), border_radius=radius)
    pygame.draw.rect(shade, (149, 189, 193, 105), shade.get_rect(), 2, border_radius=radius)
    surface.blit(shade, rect.topleft)


def draw_button(label, center, width=None, active=False):
    size = max(17, min(31, SCREEN.get_width() // 31))
    if size not in FONT_CACHE:
        FONT_CACHE[size] = font(size)
    label_img = FONT_CACHE[size].render(label, True, (235, 251, 247))
    w = min(SCREEN.get_width() - 35, width or label_img.get_width() + 64)
    compact = SCREEN.get_height() < 520
    min_h = 41 if compact else 49
    r = pygame.Rect(0, 0, w, max(min_h, label_img.get_height() + (12 if compact else 22)))
    r.center = (int(center[0]), int(center[1]))
    panel(SCREEN, r, (15, 61, 67, 239) if active else (12, 30, 43, 228), 10)
    pygame.draw.rect(SCREEN, (79, 235, 194) if active else (77, 149, 157), r, 2, border_radius=10)
    SCREEN.blit(label_img, label_img.get_rect(center=r.center))
    return r


def clicked(rect):
    return any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and rect.collidepoint(e.pos)
               or e.type == pygame.FINGERDOWN and rect.collidepoint(
                   int(e.x * SCREEN.get_width()), int(e.y * SCREEN.get_height()))
               for e in EVENTS)


def enter_pressed():
    return any(e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE)
               for e in EVENTS)


class Background:
    """Two repeating, pre-rendered terrain tiles; no per-frame random draw cost."""

    def __init__(self, mission):
        self.mission = mission
        self.w, self.h = SCREEN.get_size()
        self.tile_h = max(800, self.h * 2)
        self.offset = 0.0
        self.tile = pygame.Surface((self.w, self.tile_h)).convert()
        rng = random.Random(79001 + mission)
        surf = self.tile
        if mission == 0:
            surf.fill((24, 69, 101))
            for _ in range(140):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                length = rng.randrange(12, 66)
                pygame.draw.line(surf, (36, 91, 123), (x, y), (x + length, y + 15), rng.randrange(1, 4))
            for _ in range(65):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                pygame.draw.arc(surf, (61, 129, 152), (x, y, rng.randrange(28, 90), 22),
                                0, math.pi * 0.85, 2)
        elif mission == 1:
            surf.fill((172, 131, 78))
            for _ in range(75):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                rx, ry = rng.randrange(28, 135), rng.randrange(12, 45)
                pygame.draw.ellipse(surf, (192, 152, 91), (x-rx, y-ry, rx*2, ry*2))
                pygame.draw.arc(surf, (133, 98, 60), (x-rx, y-ry, rx*2, ry*2),
                                0.2, 2.9, 2)
            for _ in range(50):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                size = rng.randrange(7, 22)
                pygame.draw.polygon(surf, (113, 89, 66),
                                    [(x, y-size), (x+size, y-4), (x+size//2, y+size), (x-size, y+4)])
                pygame.draw.line(surf, (218, 179, 110), (x-size, y+4), (x, y-size), 2)
            # Parallel tracks: subtle evidence of a mechanized front.
            for x in (round(self.w*.21), round(self.w*.76)):
                pygame.draw.line(surf, (151, 112, 73), (x, 0), (x, self.tile_h), 7)
                pygame.draw.line(surf, (194, 154, 101), (x+10, 0), (x+10, self.tile_h), 4)
        else:
            surf.fill((191, 216, 225))
            for _ in range(100):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                rx, ry = rng.randrange(20, 135), rng.randrange(10, 45)
                pygame.draw.ellipse(surf, rng.choice(((223, 236, 237), (207, 228, 232),
                                                      (174, 204, 217))), (x, y, rx*2, ry*2))
            for _ in range(50):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                length = rng.randrange(20, 95)
                pygame.draw.lines(surf, (115, 163, 190), False,
                                  [(x, y), (x + length//3, y + length//2),
                                   (x + length, y + length)], 2)
            for _ in range(62):
                x, y = rng.randrange(self.w), rng.randrange(self.tile_h)
                r = rng.randrange(9, 22)
                pygame.draw.ellipse(surf, (163, 191, 202), (x-9, y+8, 23, 11))
                pygame.draw.polygon(surf, (45, 92, 101),
                                    [(x, y-r*2), (x-r, y+r), (x+r, y+r)])
                pygame.draw.polygon(surf, (221, 242, 243),
                                    [(x, y-r*2), (x-r//2, y-r//3), (x+r//2, y-r//3)])

    def update(self):
        self.offset = (self.offset + max(2.0, PLAYER.airspeed)) % self.tile_h

    def draw(self):
        top = round(self.offset) - self.tile_h
        SCREEN.blit(self.tile, (0, top))
        SCREEN.blit(self.tile, (0, top + self.tile_h))
        if self.h > self.tile_h:
            SCREEN.blit(self.tile, (0, top + self.tile_h*2))


def generate_ground_image(typ):
    size = {"Tank": (65, 86), "AA": (70, 80), "SAM": (73, 97)}[typ]
    s = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size
    pygame.draw.ellipse(s, (0, 0, 0, 65), (9, h-15, w-15, 11))
    pygame.draw.rect(s, (37, 50, 43), (7, 12, 14, h-24), border_radius=5)
    pygame.draw.rect(s, (37, 50, 43), (w-21, 12, 14, h-24), border_radius=5)
    pygame.draw.rect(s, (97, 108, 81), (15, 8, w-30, h-18), border_radius=7)
    pygame.draw.rect(s, (140, 148, 105), (19, 15, w-38, h-33), 2, border_radius=5)
    if typ == "Tank":
        pygame.draw.circle(s, (64, 76, 64), (w//2, h//2), 18)
        pygame.draw.rect(s, (50, 62, 55), (w//2-5, 1, 10, h//2), border_radius=3)
        pygame.draw.circle(s, (158, 156, 115), (w//2, h//2), 8)
    elif typ == "AA":
        pygame.draw.circle(s, (50, 74, 70), (w//2, h//2), 18)
        for dx in (-11, 11):
            pygame.draw.rect(s, (30, 49, 53), (w//2+dx-4, 0, 8, h//2))
        pygame.draw.circle(s, (136, 151, 111), (w//2, h//2), 8)
    else:
        for dx in (-12, 12):
            pygame.draw.polygon(s, (52, 73, 65),
                                [(w//2+dx-8, h-26), (w//2+dx, 6), (w//2+dx+8, h-26)])
            pygame.draw.line(s, (218, 192, 131), (w//2+dx, 11), (w//2+dx, h-27), 2)
    return s


def generate_boss_image(typ):
    if typ == "DuneFortress":
        w, h = 235, 185
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 80), (20, 150, 196, 28))
        pygame.draw.polygon(s, (81, 72, 57), [(48, 19), (186, 19), (228, 143), (8, 143)])
        pygame.draw.polygon(s, (135, 111, 77), [(56, 24), (178, 24), (202, 134), (28, 134)])
        for cx in (48, 188):
            pygame.draw.rect(s, (48, 57, 51), (cx-12, 3, 24, 92), border_radius=5)
            pygame.draw.circle(s, (45, 53, 48), (cx, 80), 23)
            pygame.draw.circle(s, (184, 152, 99), (cx, 80), 12)
        pygame.draw.rect(s, (58, 68, 59), (78, 55, 80, 71), border_radius=7)
        pygame.draw.rect(s, (32, 48, 45), (106, 1, 22, 88))
        pygame.draw.circle(s, (166, 135, 89), (118, 91), 30)
        pygame.draw.circle(s, (72, 77, 63), (118, 91), 18)
        for x in (57, 179):
            pygame.draw.rect(s, (233, 117, 69), (x-9, 114, 18, 9))
        return s
    if typ == "DesertAce":
        w, h = 235, 165
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(s, (66, 70, 75),
                            [(117, 5), (144, 65), (225, 110), (226, 142),
                             (137, 127), (117, 160), (97, 127), (9, 142),
                             (10, 110), (91, 65)])
        pygame.draw.polygon(s, (157, 79, 66),
                            [(117, 6), (132, 87), (119, 141), (102, 87)])
        pygame.draw.polygon(s, (49, 50, 58),
                            [(56, 105), (91, 87), (144, 87), (179, 105),
                             (179, 116), (56, 116)])
        pygame.draw.ellipse(s, (55, 186, 189), (108, 64, 18, 42))
        for x in (39, 184):
            pygame.draw.circle(s, (205, 117, 73), (x, 119), 10)
        return s
    w, h = 254, 175  # Frost Gunship
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(s, (39, 68, 88),
                        [(127, 9), (164, 67), (239, 86), (251, 135),
                         (155, 145), (127, 165), (99, 145), (3, 135),
                         (15, 86), (90, 67)])
    pygame.draw.polygon(s, (102, 163, 181),
                        [(127, 17), (145, 73), (139, 141), (115, 141), (109, 73)])
    for x in (42, 212):
        pygame.draw.circle(s, (26, 49, 67), (x, 101), 32)
        pygame.draw.circle(s, (94, 155, 176), (x, 101), 19, 5)
        pygame.draw.line(s, (156, 221, 231), (x-23, 101), (x+23, 101), 3)
        pygame.draw.line(s, (156, 221, 231), (x, 78), (x, 124), 3)
    pygame.draw.ellipse(s, (34, 225, 242), (115, 61, 24, 44))
    return s


class Carrier:
    """Ground-anchored launch platform and automatic extraction target.

    On land the runway must travel with the scrolling terrain from frame one;
    it must never remain attached to the aircraft during takeoff.
    """

    def __init__(self, mission):
        self.mission = mission
        self.image = CARRIER_IMAGES["Sea" if mission == 0 else "Land"]
        self.x = SCREEN.get_width() // 2
        self.y = SCREEN.get_height() * .65
        # Sea carrier waits until the jet climbs away. The desert/snow runway
        # is stationary in the world and therefore scrolls offscreen at once.
        self.departure = mission != 0
        self.extraction = False
        self.rect = self.image.get_rect(center=(self.x, round(self.y)))

    def launch(self):
        self.departure = True

    def recall(self):
        self.extraction = True
        self.y = -self.rect.height/2

    def update(self):
        if self.extraction:
            self.y = min(SCREEN.get_height() * .71, self.y + 5.7)
        elif self.departure:
            # Same rate as Background.update: a land runway stays attached
            # to the ground while the aircraft gains separation from it.
            self.y += max(2.0, PLAYER.airspeed)
        self.rect.center = (self.x, round(self.y))

    def draw(self):
        if not self.extraction and self.y > SCREEN.get_height() + self.rect.height:
            return
        SCREEN.blit(self.image, self.rect)
        if self.mission == 0 and not self.extraction and self.y < SCREEN.get_height():
            for kind, dx, dy in (("Cruiser", -150, -160), ("Cruiser", 150, -160),
                                 ("Destroyer", -200, 120), ("Battleship", 195, 100)):
                img = SHIP_IMAGES[kind]
                SCREEN.blit(img, img.get_rect(center=(self.x + dx, round(self.y + dy))))


class Explosion:
    def __init__(self, pos, scale=1.0):
        self.x, self.y = pos
        self.age = 0
        self.scale = scale

    def update(self):
        self.age += 1
        return self.age < EXPLOSION_FRAMES * 3

    def draw(self):
        idx = min(EXPLOSION_FRAMES-1, self.age//3)
        r = pygame.Rect(idx*EXPLOSION_SIZE, 0, EXPLOSION_SIZE, EXPLOSION_SIZE)
        frame = EXPLOSION_IMAGES.subsurface(r)
        size = max(8, round(EXPLOSION_SIZE * self.scale))
        if size != EXPLOSION_SIZE:
            frame = pygame.transform.scale(frame, (size, size))
        SCREEN.blit(frame, frame.get_rect(center=(round(self.x), round(self.y))))


class Bullet:
    """Straight player projectile; one collision per bullet."""

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vy = -13.5
        self.damage = 2
        self.rect = pygame.Rect(round(x)-4, round(y)-14, 8, 20)

    def update(self):
        self.y += self.vy
        self.rect.center = (round(self.x), round(self.y))
        if self.y < -30:
            return False
        for enemy in ENEMIES:
            if enemy.health > 0 and enemy.rect.colliderect(self.rect):
                enemy.health -= self.damage
                if len(EXPLOSIONS) < 35:
                    EXPLOSIONS.append(Explosion((self.x, self.y), 0.45))
                return False
        return True

    def draw(self):
        pygame.draw.line(SCREEN, (249, 163, 54), (round(self.x), round(self.y)+11),
                         (round(self.x), round(self.y)-10), 5)
        pygame.draw.line(SCREEN, (255, 251, 205), (round(self.x), round(self.y)+4),
                         (round(self.x), round(self.y)-13), 2)


class EnemyBullet:
    """Enemy-only hazard shot, conspicuous on sea, sand and bright snow."""

    def __init__(self, x, y, vx, vy, damage=7, color=None, size=6):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        # A uniform magenta hazard colour replaces the old desert orange and
        # arctic cyan, which were difficult to see against the terrain.
        # Bosses may still pass their older colour arguments; they are ignored
        # intentionally to keep all enemy shots instantly recognisable.
        self.damage, self.color, self.size = damage, (255, 42, 178), size
        self.rect = pygame.Rect(round(x)-size, round(y)-size, size*2, size*2)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (round(self.x), round(self.y))
        if not SCREEN.get_rect().inflate(50, 100).colliderect(self.rect):
            return False
        if PLAYER.vulnerable and self.rect.colliderect(PLAYER.hitbox):
            PLAYER.hit(self.damage)
            EXPLOSIONS.append(Explosion((self.x, self.y), .6))
            return False
        return True

    def draw(self):
        px, py = round(self.x), round(self.y)
        # Solid dark outline ensures contrast against both snow and dunes.
        # The magenta interior and white centre distinguish hostile shots
        # from the player's yellow/orange projectiles at a glance.
        radius = max(5, self.size)
        tail = (px-round(self.vx*3), py-round(self.vy*3))
        pygame.draw.line(SCREEN, (24, 12, 44), tail, (px, py), radius+5)
        pygame.draw.line(SCREEN, self.color, tail, (px, py), max(3, radius-1))
        pygame.draw.circle(SCREEN, (24, 12, 44), (px, py), radius+3)
        pygame.draw.circle(SCREEN, self.color, (px, py), radius+1)
        pygame.draw.circle(SCREEN, (255, 253, 255), (px, py), max(2, radius//2))


class Player:
    def __init__(self):
        self.base_image = FIGHTER_IMAGES[SELECTED_AIRPLANE]
        # Every mission begins with a half-size aircraft on the launch strip.
        # Cached growth stages avoid scaling surfaces inside the game loop.
        self.takeoff_images = self.make_takeoff_images()
        self.image = self.takeoff_images[0]
        self.x = SCREEN.get_width() / 2
        self.takeoff_start_y = SCREEN.get_height() * .76
        self.takeoff_end_y = SCREEN.get_height() * .42
        self.y = self.takeoff_start_y
        self.vx = self.vy = 0.0
        self.airspeed = 3.7
        self.health = self.maxHealth = 100
        self.invulnerable = 0
        self.shot_timer = 0
        self.bullets = []
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        self.hitbox = self.rect.inflate(-int(self.rect.w*.38), -int(self.rect.h*.25))

    def make_takeoff_images(self):
        frames = []
        for index in range(25):
            scale = .5 + .5 * (index / 24.0)
            size = (max(1, round(self.base_image.get_width() * scale)),
                    max(1, round(self.base_image.get_height() * scale)))
            frames.append(pygame.transform.smoothscale(self.base_image, size))
        frames[-1] = self.base_image
        return frames

    @property
    def vulnerable(self):
        return STATE == "ACTIVE" and self.invulnerable == 0

    def changeImage(self):
        self.base_image = FIGHTER_IMAGES[SELECTED_AIRPLANE]
        self.takeoff_images = self.make_takeoff_images()
        self.image = self.takeoff_images[0] if STATE == "TAKEOFF" else self.base_image
        self.sync_rect()

    def sync_rect(self):
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        self.hitbox = self.rect.inflate(-int(self.rect.w*.38), -int(self.rect.h*.25))

    def hit(self, damage):
        if not self.vulnerable:
            return
        self.health = max(0, self.health-damage)
        self.invulnerable = 48

    def update(self):
        if self.invulnerable > 0:
            self.invulnerable -= 1
        self.shot_timer += 1
        if STATE == "ACTIVE":
            # Absolute touch/pointer tracking is deliberately responsive:
            # the jet closes 52% of the remaining distance each frame, so a
            # new finger position is followed within a handful of frames.
            # No momentum or long, speed-capped chase after the finger.
            min_x = self.rect.w/2 + 7
            max_x = SCREEN.get_width()-self.rect.w/2-7
            min_y = max(self.rect.h/2+6, min(95, SCREEN.get_height()*.15))
            max_y = SCREEN.get_height()-self.rect.h/2-12
            if INPUT_DOWN:
                target_x = clamp(INPUT_POS[0], min_x, max_x)
                target_y = clamp(INPUT_POS[1], min_y, max_y)
                self.x += (target_x-self.x)*.52
                self.y += (target_y-self.y)*.52
                if abs(target_x-self.x) < .6:
                    self.x = target_x
                if abs(target_y-self.y) < .6:
                    self.y = target_y
                self.vx = self.vy = 0.0
            else:
                keys = pygame.key.get_pressed()
                dx = (1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else 0) - (
                    1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 0)
                dy = (1 if keys[pygame.K_DOWN] or keys[pygame.K_s] else 0) - (
                    1 if keys[pygame.K_UP] or keys[pygame.K_w] else 0)
                dist = math.hypot(dx, dy)
                if dist:
                    # Immediate, predictable keyboard movement without inertia.
                    self.x += dx / dist * 11.5
                    self.y += dy / dist * 11.5
                self.vx = self.vy = 0.0
            self.x = clamp(self.x, min_x, max_x)
            self.y = clamp(self.y, min_y, max_y)
            if self.shot_timer >= 7:
                for shift in (-self.rect.width*.21, self.rect.width*.21):
                    self.bullets.append(Bullet(self.x+shift, self.y-self.rect.height*.38))
                self.shot_timer = 0
        elif STATE == "TAKEOFF":
            progress = clamp(MISSION_FRAME / 105.0, 0.0, 1.0)
            # The jet advances visibly north while its sprite grows from 50%
            # to 100%, mimicking liftoff and the climb away from the runway.
            smooth = progress * progress * (3.0 - 2.0 * progress)
            self.y = self.takeoff_start_y + (self.takeoff_end_y-self.takeoff_start_y)*smooth
            frame = round(smooth * (len(self.takeoff_images)-1))
            self.image = self.takeoff_images[frame]
        elif STATE == "EXTRACTION":
            target_y = SCREEN.get_height()*.70
            self.x += (SCREEN.get_width()/2-self.x)*.065
            self.y += (target_y-self.y)*.055
        self.sync_rect()
        self.bullets = [b for b in self.bullets if b.update()]

    def draw(self):
        for b in self.bullets:
            b.draw()
        if self.invulnerable > 0 and (self.invulnerable // 5) % 2:
            return
        # Do not draw a synthetic engine flame here; at this sprite size it
        # appeared as an orange bar protruding from the aircraft's tail.
        SCREEN.blit(self.image, self.rect)


class Enemy:
    def __init__(self, x, typ="Plane", target_y=None):
        self.typ = typ
        self.image = ENEMY_IMAGES[typ]
        self.x, self.y = float(x), -self.image.get_height()/2-12
        self.target_y = target_y if target_y is not None else SCREEN.get_height() * .22
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        self.is_boss = typ in BOSS_TYPES
        self.ground = typ in GROUND_TYPES
        self.age = 0
        self.shot_timer = random.randrange(25, 75)
        self.phase = random.uniform(-math.pi, math.pi)
        self.maxHealth = {
            "Plane": 11, "UBoat": 22, "Tank": 16, "AA": 19, "SAM": 22,
            "B17": 46, "Spacecraft": 220, "DuneFortress": 255,
            "DesertAce": 300, "FrostGunship": 370,
        }[typ]
        self.health = self.maxHealth
        self.last_health = self.health
        self.dead = False
        self.vx = {"DesertAce": 2.8, "FrostGunship": 2.0}.get(typ, 1.35)
        self.x_origin = self.x
        ENEMIES.append(self)

    def fire(self, vx, vy, damage=7, color=None, size=6, x=None, y=None):
        if len(ENEMY_BULLETS) >= 180:
            return
        if color is None:
            color = (117, 222, 250) if nMISSION == 2 else (255, 110, 65)
        ENEMY_BULLETS.append(EnemyBullet(self.x if x is None else x,
                                         self.rect.bottom-9 if y is None else y,
                                         vx, vy, damage, color, size))

    def aim(self, speed, adjust=0):
        dx, dy = PLAYER.x-self.x, PLAYER.y-(self.y+40)
        angle = math.atan2(dy, dx)+adjust
        return math.cos(angle)*speed, math.sin(angle)*speed

    def shoot(self):
        if self.y < self.rect.h*.1 or STATE != "ACTIVE":
            return
        advanced = self.is_boss and self.health <= self.maxHealth * .5
        if self.typ == "DuneFortress":
            for a in range(-3 if advanced else -2, 4 if advanced else 3):
                angle = math.pi/2 + a*.16
                self.fire(math.cos(angle)*4.1, math.sin(angle)*4.1,
                          8, (245, 159, 63), 6)
            if advanced:
                for dx in (-70, 70):
                    vx, vy = self.aim(5.3)
                    self.fire(vx, vy, 9, (255, 88, 72), 7, x=self.x+dx)
            self.shot_timer = 43 if advanced else 58
        elif self.typ == "DesertAce":
            for a in (-.26, 0, .26) if advanced else (-.16, .16):
                vx, vy = self.aim(5.8, a)
                self.fire(vx, vy, 10, (255, 77, 107), 6, x=self.x)
            if advanced:
                for dx in (-85, 85):
                    self.fire(0, 5.2, 8, (244, 193, 85), 6, x=self.x+dx)
            self.shot_timer = 31 if advanced else 46
        elif self.typ == "FrostGunship":
            count = 13 if advanced else 9
            base = self.age * .035
            for j in range(count):
                a = base + j * 2*math.pi/count
                if math.sin(a) > -.65:  # omit bullets that mostly fly off the top
                    self.fire(math.cos(a)*4.3, math.sin(a)*4.3,
                              9, (58, 211, 247), 6)
            if advanced:
                vx, vy = self.aim(5.6)
                for shift in (-.18, .0, .18):
                    angle = math.atan2(vy, vx)+shift
                    self.fire(math.cos(angle)*5.6, math.sin(angle)*5.6,
                              10, (235, 247, 254), 7)
            self.shot_timer = 44 if advanced else 62
        elif self.typ == "Spacecraft":
            for a in (-.42, -.21, 0, .21, .42):
                vx, vy = self.aim(4.6, a)
                self.fire(vx, vy, 9, (255, 86, 106), 6)
            self.shot_timer = 46 if advanced else 66
        elif self.typ == "B17":
            for a in (-.2, 0, .2):
                vx, vy = self.aim(4, a)
                self.fire(vx, vy, 7)
            self.shot_timer = 86
        elif self.typ in ("SAM", "AA"):
            vx, vy = self.aim(4.6 if self.typ == "SAM" else 3.8)
            self.fire(vx, vy, 9 if self.typ == "SAM" else 6)
            self.shot_timer = 105 if self.typ == "SAM" else 67
        else:
            vx, vy = self.aim(3.7)
            self.fire(vx, vy, 5)
            self.shot_timer = random.randrange(75, 125)

    def update(self):
        self.age += 1
        if self.health <= 0:
            if not self.dead:
                self.dead = True
                on_enemy_destroyed(self)
            return False
        if self.y < self.target_y:
            self.y = min(self.target_y, self.y + (4.0 if self.is_boss else 3.6))
        elif self.ground:
            self.y += max(2.4, PLAYER.airspeed * .7)
        elif self.typ == "UBoat":
            self.y += 1.65
        elif self.is_boss:
            amp = max(28, min(135, SCREEN.get_width()*.16))
            self.x = clamp(SCREEN.get_width()/2 + math.sin(self.age * .016 + self.phase)*amp,
                           self.rect.width*.5, SCREEN.get_width()-self.rect.width*.5)
            self.y = self.target_y + math.sin(self.age * .035)*12
        else:
            sway = 70 if self.typ == "B17" else 130
            self.x = clamp(self.x_origin + math.sin(self.age*.018+self.phase)*sway,
                           self.rect.width*.5, SCREEN.get_width()-self.rect.width*.5)
        self.rect.center = (round(self.x), round(self.y))
        if self.rect.top > SCREEN.get_height()+25 or (not self.is_boss and self.age > 435):
            return False
        self.shot_timer -= 1
        if self.shot_timer <= 0:
            self.shoot()
        if PLAYER.vulnerable and self.rect.colliderect(PLAYER.hitbox):
            PLAYER.hit(16 if self.is_boss else 9)
        return True

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if not self.is_boss and self.health < self.maxHealth and self.rect.bottom > 0:
            width = max(24, self.rect.w)
            x, y = self.rect.centerx-width//2, self.rect.top-9
            pygame.draw.rect(SCREEN, (33, 37, 36), (x, y, width, 5))
            pygame.draw.rect(SCREEN, (115, 231, 158),
                             (x, y, round(width*max(0, self.health)/self.maxHealth), 5))


def on_enemy_destroyed(enemy):
    global SCORE, KILLS, BOSS_KILLS, LAST_BOSS_KILL_FRAME
    SCORE += SCORES.get(enemy.typ, 100)
    KILLS += 1
    EXPLOSIONS.append(Explosion((enemy.x, enemy.y), 2.9 if enemy.is_boss else 1.2))
    if enemy.is_boss:
        BOSS_KILLS += 1
        LAST_BOSS_KILL_FRAME = MISSION_FRAME
        SCORE += int(PLAYER.health*10)
        ENEMY_BULLETS.clear()


def scripted_wave(spawns):
    w = SCREEN.get_width()
    for typ, fraction in spawns:
        img = ENEMY_IMAGES[typ]
        x = clamp(w*fraction, img.get_width()/2+8, w-img.get_width()/2-8)
        Enemy(x, typ, SCREEN.get_height()*(.19 if typ in BOSS_TYPES else .23))


def mission_script(mission):
    """Each episode starts its own frame clock; bosses must die to advance."""
    if mission == 0:
        return [
            [(60, "wave", (("Plane", .28), ("Plane", .72))),
             (230, "wave", (("UBoat", .28), ("UBoat", .72))),
             (390, "wave", (("Plane", .18), ("Plane", .50), ("Plane", .82))),
             (590, "wave", (("B17", .5), ("Plane", .18), ("Plane", .82))),
             (810, "wave", (("Plane", .35), ("Plane", .65))),
             (1050, "boss", ("Spacecraft", .5))],
        ]
    if mission == 1:
        return [
            [(60, "wave", (("Tank", .25), ("Tank", .75))),
             (190, "wave", (("Plane", .2), ("Plane", .8))),
             (320, "wave", (("AA", .18), ("SAM", .5), ("AA", .82))),
             (470, "wave", (("Tank", .30), ("Plane", .70))),
             (590, "boss", ("DuneFortress", .5))],
            [(65, "wave", (("AA", .3), ("AA", .7))),
             (210, "wave", (("Plane", .16), ("Plane", .5), ("Plane", .84))),
             (370, "wave", (("SAM", .2), ("Tank", .5), ("SAM", .8))),
             (550, "boss", ("DesertAce", .5))],
        ]
    return [
        [(60, "wave", (("Tank", .24), ("Tank", .76))),
         (220, "wave", (("Plane", .20), ("Plane", .80))),
         (380, "wave", (("SAM", .2), ("SAM", .8))),
         (540, "wave", (("AA", .15), ("B17", .5), ("AA", .85)))],
        [(65, "wave", (("Plane", .25), ("Plane", .75))),
         (230, "wave", (("SAM", .15), ("SAM", .85))),
         (370, "wave", (("Plane", .12), ("Plane", .5), ("Plane", .88))),
         (530, "boss", ("FrostGunship", .5))],
    ]


def launch_mission():
    global PLAYER, CARRIER, BACKGROUND, MISSION_STARTED, MISSION_PRE_BRIEF
    global STATE, MISSION_FRAME, PHASE_FRAME, PHASE, EVENT_INDEX, SCRIPT
    global ENEMIES, ENEMY_BULLETS, EXPLOSIONS, INPUT_DOWN, INPUT_POS
    global BOSS_KILLS, LAST_BOSS_KILL_FRAME, KILLS, SCORE, EXTRACT_TIMER
    ENEMIES = []
    ENEMY_BULLETS = []
    EXPLOSIONS = []
    PLAYER = Player()
    CARRIER = Carrier(nMISSION)
    BACKGROUND = Background(nMISSION)
    INPUT_DOWN = False
    INPUT_POS = (SCREEN.get_width()//2, SCREEN.get_height()//2)
    SCORE = 0
    KILLS = 0
    BOSS_KILLS = 0
    LAST_BOSS_KILL_FRAME = -999999
    SCRIPT = mission_script(nMISSION)
    MISSION_FRAME = 0
    PHASE_FRAME = 0
    PHASE = 0
    EVENT_INDEX = 0
    EXTRACT_TIMER = 0
    STATE = "TAKEOFF"
    MISSION_STARTED = True
    MISSION_PRE_BRIEF = False


def next_mission():
    global nMISSION, MISSION_PRE_BRIEF, MISSION_STARTED, STATE, CAMPAIGN_SCORE
    CAMPAIGN_SCORE += SCORE + int(PLAYER.health*20)
    if nMISSION == MAX_MISSIONS-1:
        nMISSION = 0
        CAMPAIGN_SCORE = 0
        STATE = "MENU"
        MISSION_PRE_BRIEF = False
        MISSION_STARTED = False
    else:
        nMISSION += 1
        STATE = "BRIEF"
        MISSION_PRE_BRIEF = True
        MISSION_STARTED = False


def setup():
    global nMISSION, STATE, HOME_BUTTON, FONT_CACHE, FIGHTER_IMAGES, ENEMY_IMAGES
    global CARRIER_IMAGES, SHIP_IMAGES, EXPLOSION_IMAGES, EXPLOSION_SIZE, EXPLOSION_FRAMES
    global MAIN_MENU_BG, MAIN_MENU_BG2, WINBG, WINBG2, SELECTED_AIRPLANE
    global MISSION_STARTED, MISSION_PRE_BRIEF, INPUT_DOWN, INPUT_POS
    global ENEMIES, ENEMY_BULLETS, EXPLOSIONS, MENU_COUNTER, CAMPAIGN_SCORE
    global SELECTED_MISSION_SLOT
    nMISSION = 0
    SELECTED_MISSION_SLOT = 0
    CAMPAIGN_SCORE = 0
    STATE = "MENU"
    MISSION_STARTED = False
    MISSION_PRE_BRIEF = False
    MENU_COUNTER = 0
    INPUT_DOWN = False
    INPUT_POS = (0, 0)
    FONT_CACHE = {}
    SELECTED_AIRPLANE = "f5"
    HOME_BUTTON = Button(10, 10, 88, 88, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    w, h = SCREEN.get_size()
    fmax_w = max(54, min(112, round(w*.105)))
    fmax_h = max(60, min(115, round(h*.16)))
    filenames = ("f1.png", "f2.png", "f3.png", "f4.png", "combatjet-highres.png", "f5.png")
    FIGHTER_IMAGES = {"f"+str(i+1): fit_image(load_image(name), fmax_w, fmax_h)
                      for i, name in enumerate(filenames)}
    ENEMY_IMAGES = {
        "Plane": fit_image(load_image("PlaneF-35Lightning2.png"), 88, 103),
        "UBoat": fit_image(load_image("ShipSubMarineHull.png"), 90, 140),
        "B17": fit_image(load_image("B17.png"), 140, 145),
        "Spacecraft": fit_image(load_image("Battleplane.png"), min(210, int(w*.33)), 190),
    }
    for kind in GROUND_TYPES:
        ENEMY_IMAGES[kind] = generate_ground_image(kind)
    for kind in ("DuneFortress", "DesertAce", "FrostGunship"):
        ENEMY_IMAGES[kind] = fit_image(generate_boss_image(kind), min(245, int(w*.38)), 190)
    SHIP_IMAGES = {
        "Cruiser": fit_image(load_image("ShipCruiserHull.png"), 80, 145),
        "Battleship": fit_image(load_image("ShipBattleshipHull.png"), 90, 145),
        "Destroyer": fit_image(load_image("ShipDestroyerHull.png"), 80, 125),
    }
    sea = fit_image(load_image("ShipCarrierHull.png"), max(165, int(w*.3)), max(210, int(h*.5)))
    land = fit_image(load_image("runway.png"), max(170, int(w*.33)), max(250, int(h*.6)))
    CARRIER_IMAGES = {"Sea": sea, "Land": land}
    EXPLOSION_IMAGES = load_image("Explosion.png")
    EXPLOSION_SIZE = EXPLOSION_IMAGES.get_height()
    EXPLOSION_FRAMES = max(1, EXPLOSION_IMAGES.get_width() // max(1, EXPLOSION_SIZE))
    MAIN_MENU_BG = pygame.transform.smoothscale(load_image("mainMenu.png"), (w, h))
    MAIN_MENU_BG2 = pygame.transform.smoothscale(load_image("mainMenu2.png"), (w, h))
    WINBG = pygame.transform.smoothscale(load_image("beatgame.png"), (w, h))
    WINBG2 = pygame.transform.smoothscale(load_image("beatgame2.png"), (w, h))
    ENEMIES = []
    ENEMY_BULLETS = []
    EXPLOSIONS = []


def ret():
    global RUNNING
    RUNNING = False


def show_mission_select():
    """Open the unlocked mission list without starting or resetting the game."""
    global STATE, SELECTED_MISSION_SLOT, MISSION_STARTED, MISSION_PRE_BRIEF
    STATE = "SELECT"
    SELECTED_MISSION_SLOT = nMISSION
    MISSION_STARTED = False
    MISSION_PRE_BRIEF = False


def choose_mission(mission):
    """Start a fresh campaign at any mission (useful for level debugging)."""
    global nMISSION, CAMPAIGN_SCORE, STATE, MISSION_STARTED, MISSION_PRE_BRIEF
    nMISSION = int(clamp(mission, 0, MAX_MISSIONS - 1))
    CAMPAIGN_SCORE = 0
    STATE = "BRIEF"
    MISSION_STARTED = False
    MISSION_PRE_BRIEF = True


def missionSelect():
    """Choose a mission first, then explicitly confirm with CONTINUE."""
    global STATE, SELECTED_MISSION_SLOT, MENU_COUNTER
    MENU_COUNTER += 1
    w, h = SCREEN.get_size()
    SCREEN.fill((10, 24, 37))
    pygame.draw.rect(SCREEN, (16, 42, 57), (0, 0, w, round(h*.23)))
    pygame.draw.line(SCREEN, (63, 114, 122), (0, round(h*.23)),
                     (w, round(h*.23)), 2)
    text(SCREEN, "MISSION SELECT", max(25, min(48, w//22)),
         (228, 251, 242), center=(w/2, h*.095))
    text(SCREEN, "ALL MISSIONS UNLOCKED FOR TESTING",
         max(12, min(20, w//47)), (130, 223, 195), center=(w/2, h*.174))

    gap = max(7, round(h*.015))
    card_top = round(h*.255)
    compact = h < 520
    card_bottom = round(h*(.705 if compact else .735))
    card_height = max(52, (card_bottom-card_top-gap*2)//3)
    card_width = min(w-20, round(w*.86))
    left = (w-card_width)//2
    card_rects = []
    for index in range(MAX_MISSIONS):
        top = card_top+index*(card_height+gap)
        rect = pygame.Rect(left, top, card_width, card_height)
        card_rects.append(rect)
        color = MISSION_COLORS[index]
        selected = index == SELECTED_MISSION_SLOT
        panel(SCREEN, rect, (37, 93, 92, 246) if selected else (16, 37, 50, 227), 11)
        pygame.draw.rect(SCREEN, (146, 251, 195) if selected else (67, 102, 111),
                         rect, 4 if selected else 1, border_radius=11)
        pygame.draw.rect(SCREEN, color, (rect.left+4, rect.top+9, 5, max(3, rect.h-18)),
                         border_radius=3)
        badge_x = rect.left+max(27, min(43, round(w*.047)))
        text(SCREEN, "%02d" % (index+1), max(22, min(33, w//31)),
             color, center=(badge_x, rect.centery))
        label_x = rect.left+max(65, min(93, round(w*.115)))
        label_size = max(14, min(25, w//39))
        detail_size = max(12, min(17, w//55))
        label_y = rect.top+max(5, round(card_height*.12))
        text(SCREEN, MISSION_NAMES[index], label_size, (239, 250, 242),
             topleft=(label_x, label_y))
        # Keep description lines within the card on narrow mobile layouts.
        detail = MISSION_LOCATIONS[index]
        available = max(40, rect.right-label_x-10)
        if available >= 370:
            detail += "  |  " + MISSION_BOSS_DESCRIPTIONS[index]
        text(SCREEN, detail, detail_size, color,
             topleft=(label_x, rect.top+max(24, round(card_height*.42))))
        if card_height >= 87 and available >= 230:
            objective = MISSION_OBJECTIVES[index]
            obj_size = detail_size
            if obj_size not in FONT_CACHE:
                FONT_CACHE[obj_size] = font(obj_size)
            if FONT_CACHE[obj_size].size(objective)[0] > available:
                while objective and FONT_CACHE[obj_size].size(objective + "...")[0] > available:
                    objective = objective[:-1]
                objective = objective.rstrip() + "..."
            text(SCREEN, objective, obj_size, (199, 219, 218),
                 topleft=(label_x, rect.top+max(44, round(card_height*.69))))
        if selected:
            # Graphic check indicator: readable even without font glyph support.
            sx, sy = rect.right-18, rect.centery
            pygame.draw.circle(SCREEN, (135, 248, 186), (sx, sy), 9)
            pygame.draw.lines(SCREEN, (15, 55, 48), False,
                              [(sx-5, sy), (sx-1, sy+4), (sx+6, sy-5)], 2)

    text(SCREEN, "TAP TO HIGHLIGHT  /  KEYS 1, 2, 3",
         max(12, min(18, w//55)), (185, 221, 225),
         center=(w/2, h*(.74 if compact else .76)))
    continue_rect = draw_button("CONTINUE", (w/2, h*(.825 if compact else .84)),
                                width=min(320, w*.62), active=True)
    back_rect = draw_button("BACK TO MENU", (w/2, h*(.935 if compact else .94)),
                            width=min(290, w*.60))

    # Key shortcuts and card taps only modify the highlight; confirmation
    # comes solely from CONTINUE, Enter or Space.
    for e in EVENTS:
        if e.type == pygame.KEYDOWN:
            if pygame.K_1 <= e.key <= pygame.K_3:
                SELECTED_MISSION_SLOT = e.key-pygame.K_1
            elif pygame.K_KP1 <= e.key <= pygame.K_KP3:
                SELECTED_MISSION_SLOT = e.key-pygame.K_KP1
            elif e.key in (pygame.K_DOWN, pygame.K_RIGHT):
                SELECTED_MISSION_SLOT = (SELECTED_MISSION_SLOT + 1) % MAX_MISSIONS
            elif e.key in (pygame.K_UP, pygame.K_LEFT):
                SELECTED_MISSION_SLOT = (SELECTED_MISSION_SLOT - 1) % MAX_MISSIONS
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                choose_mission(SELECTED_MISSION_SLOT)
                return
            elif e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                STATE = "MENU"
                return

    if clicked(back_rect):
        STATE = "MENU"
        return
    if clicked(continue_rect):
        choose_mission(SELECTED_MISSION_SLOT)
        return
    for index, rect in enumerate(card_rects):
        if clicked(rect):
            SELECTED_MISSION_SLOT = index
            return


def startMenu():
    global MENU_COUNTER, STATE, MISSION_PRE_BRIEF
    MENU_COUNTER += 1
    SCREEN.blit(MAIN_MENU_BG if (MENU_COUNTER//35)%2 == 0 else MAIN_MENU_BG2, (0, 0))
    w, h = SCREEN.get_size()
    panel(SCREEN, pygame.Rect(round(w*.1), round(h*.23), round(w*.8), round(h*.52)), (8, 17, 27, 211))
    text(SCREEN, "JETSTREAM", max(31, min(65, w//14)), (179, 247, 208), center=(w/2, h*.32))
    text(SCREEN, "THREE FRONT CAMPAIGN", max(16, min(27, w//35)), (217, 229, 230), center=(w/2, h*.44))
    rect = draw_button("SELECT MISSION", (w/2, h*.60), active=True)
    if clicked(rect) or enter_pressed():
        show_mission_select()


def missionPreBrief():
    global SELECTED_AIRPLANE, STATE, MENU_COUNTER
    MENU_COUNTER += 1
    w, h = SCREEN.get_size()
    SCREEN.fill((11, 25, 38))
    if nMISSION == 1:
        SCREEN.fill((54, 43, 28))
    elif nMISSION == 2:
        SCREEN.fill((26, 49, 65))
    title_size = max(24, min(48, w//21))
    text(SCREEN, "MISSION %02d" % (nMISSION+1), 22, (107, 230, 178), center=(w/2, h*.115))
    text(SCREEN, MISSION_NAMES[nMISSION], title_size, (235, 247, 232), center=(w/2, h*.19))
    text(SCREEN, MISSION_LOCATIONS[nMISSION], 18, (157, 201, 208), center=(w/2, h*.27))
    text(SCREEN, MISSION_OBJECTIVES[nMISSION], max(14, min(22, w//46)),
         (222, 231, 233), center=(w/2, h*.34))
    text(SCREEN, "SELECT AIRCRAFT", 18, (129, 225, 182), center=(w/2, h*.45))

    # Six aircraft are arranged by slot, not raw sprite dimensions.
    item_width = min(135, (w-24)//6)
    slot_y = round(h*.58)
    for index, (name, img) in enumerate(FIGHTER_IMAGES.items()):
        cx = w/2 + (index-2.5)*item_width
        rect = pygame.Rect(0, 0, item_width-6, min(135, h*.19))
        rect.center = (round(cx), slot_y)
        panel(SCREEN, rect, (32, 84, 86, 225) if name == SELECTED_AIRPLANE else (14, 38, 48, 200), 8)
        display = fit_image(img, rect.w-17, rect.h-24)
        SCREEN.blit(display, display.get_rect(center=rect.center))
        if name == SELECTED_AIRPLANE:
            pygame.draw.rect(SCREEN, (119, 247, 185), rect, 3, border_radius=8)
        if clicked(rect):
            SELECTED_AIRPLANE = name

    rect = draw_button("DEPART", (w/2, h*.79), active=True)
    change_rect = draw_button("CHANGE MISSION", (w/2, h*.91),
                              width=min(320, w*.60))
    if clicked(change_rect) or any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE
                                   for e in EVENTS):
        show_mission_select()
    elif clicked(rect) or enter_pressed():
        launch_mission()


def update_script():
    global PHASE, PHASE_FRAME, EVENT_INDEX, STATE, EXTRACT_TIMER
    if PHASE >= len(SCRIPT):
        return
    events = SCRIPT[PHASE]
    if EVENT_INDEX < len(events):
        trigger_time, kind, payload = events[EVENT_INDEX]
        if PHASE_FRAME >= trigger_time:
            scripted_wave((payload,) if kind == "boss" else payload)
            EVENT_INDEX += 1
    # Boss episodes end only AFTER defeating their boss, not on a timer.
    if EVENT_INDEX >= len(events):
        final_kind = events[-1][1]
        if final_kind == "boss":
            boss_is_alive = any(e.is_boss for e in ENEMIES)
            can_advance = (not boss_is_alive and LAST_BOSS_KILL_FRAME >= 0
                           and MISSION_FRAME - LAST_BOSS_KILL_FRAME >= 100)
        else:
            can_advance = PHASE_FRAME > events[-1][0]+150 and not ENEMIES
        if can_advance:
            PHASE += 1
            PHASE_FRAME = 0
            EVENT_INDEX = 0
            if PHASE >= len(SCRIPT):
                STATE = "EXTRACTION"
                CARRIER.recall()
                EXTRACT_TIMER = 0


def update_input():
    global INPUT_DOWN, INPUT_POS
    for e in EVENTS:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            INPUT_DOWN = True
            INPUT_POS = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            INPUT_DOWN = False
        elif e.type == pygame.MOUSEMOTION and INPUT_DOWN:
            INPUT_POS = e.pos
        elif e.type == pygame.FINGERDOWN:
            INPUT_DOWN = True
            INPUT_POS = (e.x*SCREEN.get_width(), e.y*SCREEN.get_height())
        elif e.type == pygame.FINGERMOTION and INPUT_DOWN:
            INPUT_POS = (e.x*SCREEN.get_width(), e.y*SCREEN.get_height())
        elif e.type == pygame.FINGERUP:
            INPUT_DOWN = False


def update():
    global EVENTS, RUNNING, STATE, MISSION_FRAME, PHASE_FRAME, EXTRACT_TIMER
    EVENTS = pygame.event.get()
    HOME_BUTTON.update(EVENTS)
    for e in EVENTS:
        if e.type == pygame.QUIT:
            RUNNING = False
    update_input()

    if STATE in ("MENU", "SELECT", "BRIEF", "COMPLETE", "FAILED", "CAMPAIGN_COMPLETE"):
        return
    MISSION_FRAME += 1
    BACKGROUND.update()
    CARRIER.update()
    if STATE == "TAKEOFF" and MISSION_FRAME >= 105:
        CARRIER.launch()
        # The final cached ascent frame is exactly the normal flight image.
        PLAYER.image = PLAYER.base_image
        STATE = "ACTIVE"
    if STATE == "ACTIVE":
        PHASE_FRAME += 1
        update_script()
    PLAYER.update()
    if STATE == "ACTIVE":
        # Work on snapshots: deaths and explosions may change the collections.
        ENEMIES[:] = [e for e in ENEMIES[:] if e.update()]
        ENEMY_BULLETS[:] = [b for b in ENEMY_BULLETS[:] if b.update()]
        if PLAYER.health <= 0:
            STATE = "FAILED"
            ENEMY_BULLETS.clear()
    else:
        # No hostile fire during launch or extraction.
        ENEMY_BULLETS.clear()
    EXPLOSIONS[:] = [x for x in EXPLOSIONS[:] if x.update()]
    if STATE == "EXTRACTION":
        EXTRACT_TIMER += 1
        if EXTRACT_TIMER >= 205:
            STATE = "CAMPAIGN_COMPLETE" if nMISSION == MAX_MISSIONS-1 else "COMPLETE"


def draw_hud():
    w, h = SCREEN.get_size()
    hud_x = min(115, max(94, int(w*.1)))
    bar_w = max(110, min(205, int(w*.18)))
    panel(SCREEN, pygame.Rect(hud_x, 10, bar_w+36, 83), (10, 28, 38, 221), 8)
    text(SCREEN, "HULL", 16, (201, 229, 223), topleft=(hud_x+12, 18))
    pygame.draw.rect(SCREEN, (71, 70, 68), (hud_x+12, 49, bar_w, 16), border_radius=4)
    amount = max(0, int(bar_w*PLAYER.health/PLAYER.maxHealth))
    if amount:
        color = (71, 223, 150) if PLAYER.health > 35 else (241, 109, 76)
        pygame.draw.rect(SCREEN, color, (hud_x+12, 49, amount, 16), border_radius=4)
    text(SCREEN, "%d%%" % PLAYER.health, 14, (245, 246, 229),
         topleft=(hud_x+17, 47), shadow=False)
    right_w = min(244, int(w*.27))
    panel(SCREEN, pygame.Rect(w-right_w-9, 10, right_w, 83), (10, 28, 38, 221), 8)
    text(SCREEN, "SCORE  %06d" % SCORE, max(13, min(20, w//57)),
         (235, 244, 227), topleft=(w-right_w+3, 18))
    text(SCREEN, "STAGE %d/3  |  KILLS %d" % (nMISSION+1, KILLS),
         max(12, min(17, w//68)), (122, 227, 202),
         topleft=(w-right_w+3, 51))
    bosses = [e for e in ENEMIES if e.is_boss and e.health > 0]
    if bosses:
        boss = bosses[0]
        # Small, boss-attached indicator; never cover its artwork with a
        # giant screen-centred health panel.
        bw = max(76, min(168, int(w*.22), boss.rect.width))
        bx = round(clamp(boss.rect.centerx-bw/2, 8, w-bw-8))
        by = boss.rect.bottom + 7
        if by > h-38:
            by = boss.rect.top-32
        text(SCREEN, BOSS_NAMES[boss.typ], 13, (255, 222, 183),
             center=(bx+bw/2, by+7))
        pygame.draw.rect(SCREEN, (16, 29, 36), (bx-2, by+18, bw+4, 10), border_radius=3)
        pygame.draw.rect(SCREEN, (86, 77, 78), (bx, by+20, bw, 6), border_radius=2)
        current = max(0, round(bw*boss.health/boss.maxHealth))
        if current:
            pygame.draw.rect(SCREEN, (242, 102, 91), (bx, by+20, current, 6), border_radius=2)


def draw_stage_overlay():
    w, h = SCREEN.get_size()
    if STATE == "TAKEOFF" or MISSION_FRAME < 145:
        headline = MISSION_NAMES[nMISSION]
        subline = "LAUNCHING" if STATE == "TAKEOFF" else MISSION_LOCATIONS[nMISSION]
        panel(SCREEN, pygame.Rect(round(w*.18), round(h*.30), round(w*.64), 102),
              (15, 28, 36, 201))
        text(SCREEN, headline, max(19, min(37, w//27)), (244, 239, 207),
             center=(w/2, h*.35))
        text(SCREEN, subline, 16, (138, 237, 216), center=(w/2, h*.41))
    elif STATE == "ACTIVE" and PHASE < len(SCRIPT):
        events = SCRIPT[PHASE]
        if EVENT_INDEX < len(events):
            t, kind, payload = events[EVENT_INDEX]
            if kind == "boss" and t-105 <= PHASE_FRAME < t:
                if (PHASE_FRAME//15)%2 == 0:
                    text(SCREEN, "WARNING - " + BOSS_NAMES[payload[0]],
                         max(16, min(32, w//31)), (255, 229, 159), center=(w/2, h*.39))
    if STATE == "EXTRACTION":
        text(SCREEN, "OBJECTIVE COMPLETE", max(20, min(38, w//28)),
             (155, 249, 194), center=(w/2, h*.33))
        text(SCREEN, "RETURNING TO BASE", 19, (234, 239, 221), center=(w/2, h*.4))


def draw_game():
    BACKGROUND.draw()
    CARRIER.draw()
    for enemy in ENEMIES:
        enemy.draw()
    for bullet in ENEMY_BULLETS:
        bullet.draw()
    PLAYER.draw()
    for explosion in EXPLOSIONS:
        explosion.draw()
    draw_hud()
    draw_stage_overlay()


def draw_results():
    w, h = SCREEN.get_size()
    SCREEN.blit(WINBG if (MENU_COUNTER//36)%2 == 0 else WINBG2, (0, 0))
    panel(SCREEN, pygame.Rect(round(w*.12), round(h*.17), round(w*.76), round(h*.68)), (8, 22, 31, 235))
    failed = STATE == "FAILED"
    headline = ("MISSION FAILED" if failed else
                "CAMPAIGN COMPLETE" if STATE == "CAMPAIGN_COMPLETE" else "MISSION COMPLETE")
    text(SCREEN, headline, max(21, min(51, w//20)),
         (255, 122, 98) if failed else (162, 246, 188), center=(w/2, h*.27))
    text(SCREEN, MISSION_NAMES[nMISSION], max(16, min(25, w//42)),
         (231, 241, 237), center=(w/2, h*.36))
    if not failed:
        score_bonus = int(PLAYER.health*20)  # rewarded at debrief; not during combat
        text(SCREEN, "TARGETS %d   |   BOSSES %d" % (KILLS, BOSS_KILLS),
             20, (190, 224, 222), center=(w/2, h*.47))
        text(SCREEN, "SURVIVAL BONUS  +%d" % score_bonus,
             20, (190, 224, 222), center=(w/2, h*.52))
        title = "CAMPAIGN SCORE" if STATE == "CAMPAIGN_COMPLETE" else "MISSION SCORE"
        amount = CAMPAIGN_SCORE+SCORE+score_bonus if STATE == "CAMPAIGN_COMPLETE" else SCORE+score_bonus
        text(SCREEN, "%s  %06d" % (title, amount),
             24, (248, 226, 145), center=(w/2, h*.60))
        label = "FINISH CAMPAIGN" if STATE == "CAMPAIGN_COMPLETE" else "NEXT MISSION"
    else:
        text(SCREEN, "TARGETS DESTROYED  %d" % KILLS,
             20, (190, 224, 222), center=(w/2, h*.49))
        text(SCREEN, "SCORE  %06d" % SCORE,
             24, (248, 226, 145), center=(w/2, h*.60))
        label = "RETRY MISSION"
    rect = draw_button(label, (w/2, h*.70), active=True)
    select_rect = draw_button("SELECT MISSION", (w/2, h*.80), width=min(330, w*.61))
    if clicked(select_rect):
        show_mission_select()
    elif clicked(rect) or enter_pressed():
        if failed:
            launch_mission()
        else:
            next_mission()


def draw():
    global MENU_COUNTER
    if STATE == "MENU":
        startMenu()
    elif STATE == "SELECT":
        missionSelect()
    elif STATE == "BRIEF":
        missionPreBrief()
    elif STATE in ("TAKEOFF", "ACTIVE", "EXTRACTION"):
        draw_game()
    else:
        MENU_COUNTER += 1
        draw_results()
    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    EVENTS = []
    setup()
    while RUNNING:
        update()
        draw()
        CLOCK.tick(FPS)
        await asyncio.sleep(0)
