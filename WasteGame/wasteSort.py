# -*- coding: utf-8 -*-
"""WasteSort — six-room sorting game, child-friendly Pygame/Pygbag update.

Drop-in GameHub entry point: await wasteSort.main(screen, clock)
Uses the existing assets in WasteGame/assets/; no new graphics required.
"""

import asyncio
import math
import os
import random

import pygame

FPS = 60
GAME_W, GAME_H = 800, 600
ROOM_COUNT = 6
OBJECT_MARGIN = 9
ITEM_SPAWN_LEFT = 18
ITEM_SPAWN_RIGHT = 645
ITEM_SPAWN_TOP = 118
ITEM_SPAWN_BOTTOM = 585
HOME_RECT = pygame.Rect(10, 10, 88, 88)

COLORS = {
    'Plastik': (255, 215, 28),
    'Bio': (139, 69, 19),
    'Papier': (223, 69, 61),
    'Glas': (46, 158, 56),
}

# Original objects, names, counts and sorting rules are preserved.
OBJECT_SPECS = (
    ('paperbox.png', 'Papier', (64, 64)),
    ('banana.png', 'Bio', (64, 64)),
    ('can3.png', 'Plastik', (32, 60)),
    ('can4.png', 'Plastik', (32, 60)),
    ('glass.png', 'Glas', (37, 87)),
)
BIN_SPECS = (
    ('Plastik', 48, 'trashBin_yellow.png', 'trashBin_yellow_open.png'),
    ('Papier', 196, 'trashBin_red.png', 'trashBin_red_open.png'),
    ('Bio', 344, 'trashBin_brown.png', 'trashBin_brown_open.png'),
    ('Glas', 492, 'trashBin_green.png', 'trashBin_green_open.png'),
)


def clamp(value, low, high):
    return max(low, min(high, value))


def asset_path(name):
    """Both Pygbag's cwd and local GameHub launches are supported."""
    directory = os.path.dirname(os.path.abspath(__file__))
    options = (
        os.path.join('assets', name),
        os.path.join(directory, 'assets', name),
        os.path.join('WasteGame', 'assets', name),
    )
    for path in options:
        if os.path.isfile(path):
            return path
    return options[0]


def load_image(name, size=None, alpha=True):
    try:
        image = pygame.image.load(asset_path(name))
        image = image.convert_alpha() if alpha else image.convert()
        if size and image.get_size() != size:
            image = pygame.transform.smoothscale(image, size)
        return image
    except (OSError, pygame.error):
        print('WasteSort: missing optional image', name)
        return None


class WasteItem:
    def __init__(self, filename, group, size, image, pos):
        self.filename = filename
        self.group = group
        self.rect = pygame.Rect(pos, size)
        self.img = image
        self.sorted = False
        self.phase = random.random() * math.tau
        # Drag grabbing uses an offset, so an object never jumps under a finger.
        self.grab_offset = (0.0, 0.0)
        self.image_cache = {}

    def grab(self, pos):
        self.grab_offset = (self.rect.x - pos[0], self.rect.y - pos[1])

    def move_to(self, pointer):
        """Restrict the *whole sprite*, not just its centre, to the screen."""
        x = pointer[0] + self.grab_offset[0]
        y = pointer[1] + self.grab_offset[1]
        self.rect.x = round(clamp(x, OBJECT_MARGIN, GAME_W - self.rect.width - OBJECT_MARGIN))
        self.rect.y = round(clamp(y, OBJECT_MARGIN, GAME_H - self.rect.height - OBJECT_MARGIN))

    def draw(self, surface, ticks, dragging=False):
        if self.sorted:
            return
        if self.img is None:
            pygame.draw.rect(surface, COLORS[self.group], self.rect, border_radius=7)
            pygame.draw.rect(surface, (255, 255, 255), self.rect, 3, border_radius=7)
            return
        # Pulse softly, but render from a cached set of sizes rather than
        # smoothscaling the PNG at 60 FPS on slower Pygbag/iPad devices.
        scale = 1.0 + 0.04 * math.sin(ticks / 300.0 + self.phase)
        frame = round((scale - 0.96) / 0.01)
        frame = int(clamp(frame, 0, 8))
        image = self.image_cache.get(frame)
        if image is None:
            factor = 0.96 + frame * 0.01
            dimensions = (max(1, round(self.rect.width * factor)),
                          max(1, round(self.rect.height * factor)))
            image = pygame.transform.smoothscale(self.img, dimensions)
            self.image_cache[frame] = image
        surface.blit(image, image.get_rect(center=self.rect.center))
        if dragging:
            pygame.draw.rect(surface, (255, 236, 118), self.rect.inflate(8, 8), 3,
                             border_radius=8)


class WasteBin:
    def __init__(self, group, y, closed, opened):
        self.group = group
        self.rect = pygame.Rect(700, y, 100, 100)
        self.closed = closed
        self.opened = opened or closed
        self.highlight = False

    def draw(self, surface):
        image = self.opened if self.highlight else self.closed
        if image is not None:
            surface.blit(image, self.rect)
        else:
            pygame.draw.rect(surface, COLORS[self.group], self.rect, border_radius=12)
        if self.highlight:
            pygame.draw.rect(surface, (255, 240, 130), self.rect.inflate(4, 4), 4,
                             border_radius=12)


class WasteSortGame:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((GAME_W, GAME_H)).convert()
        self.viewport = pygame.Rect(0, 0, GAME_W, GAME_H)
        self.scale = 1.0
        self.running = True
        self.phase = 'playing'  # playing / room_clear / finished
        self.phase_seconds = 0.0
        self.room = 1
        self.rng = random.Random()
        self.active_pointer = None  # ('finger', finger_id) or ('mouse', 0)
        self.selected = None
        self.items = []
        self.bins = []
        self.sorted_count = 0
        self.background_cache = {}
        self.object_images = {
            name: load_image(name, size)
            for name, group, size in OBJECT_SPECS
        }
        self.bin_images = {}
        for group, y, closed, opened in BIN_SPECS:
            self.bin_images[group] = (
                load_image(closed, (100, 100)),
                load_image(opened, (100, 100)),
            )
        self.star = load_image('star.png', (160, 160))
        self.home_img = load_image('retBut.png', HOME_RECT.size)
        self.font_big = pygame.font.Font(None, 67)
        self.font_medium = pygame.font.Font(None, 38)
        self.font_small = pygame.font.Font(None, 27)
        self.end_play_button = pygame.Rect(175, 425, 210, 65)
        self.end_home_button = pygame.Rect(416, 425, 210, 65)
        self.confetti = [
            (self.rng.randrange(75, GAME_W - 75), self.rng.randrange(85, 500),
             self.rng.choice(((240, 94, 98), (255, 213, 71), (87, 186, 247),
                              (101, 203, 128), (191, 138, 241))))
            for _ in range(60)
        ]
        self.load_room(1)

    def load_room(self, index):
        """Every room gets a fresh randomized arrangement."""
        self.room = index
        self.phase = 'playing'
        self.phase_seconds = 0.0
        self.active_pointer = None
        self.selected = None
        self.sorted_count = 0
        if index not in self.background_cache:
            self.background_cache[index] = load_image(
                'Level%d.png' % index, (GAME_W, GAME_H), alpha=False
            )
        self.background = self.background_cache[index]
        self.bins = [
            WasteBin(group, y, *self.bin_images[group])
            for group, y, closed, opened in BIN_SPECS
        ]
        self.items = []
        # The original second-to-sixth-level coordinates were identical.
        # Choose non-overlapping positions anew for EVERY room and replay.
        shuffled = list(OBJECT_SPECS)
        self.rng.shuffle(shuffled)
        for filename, group, size in shuffled:
            pos = self.random_position(size)
            self.items.append(WasteItem(filename, group, size,
                                        self.object_images[filename], pos))

    def random_position(self, size):
        w, h = size
        left, top = ITEM_SPAWN_LEFT, ITEM_SPAWN_TOP
        right = ITEM_SPAWN_RIGHT - w
        bottom = ITEM_SPAWN_BOTTOM - h
        for _ in range(300):
            rect = pygame.Rect(self.rng.randint(left, right),
                               self.rng.randint(top, bottom), w, h)
            if all(not rect.inflate(28, 28).colliderect(other.rect)
                   for other in self.items):
                return rect.topleft
        # Extremely unlikely, but there is always a visible, selectable place.
        for y in range(top, bottom + 1, 12):
            for x in range(left, right + 1, 12):
                rect = pygame.Rect(x, y, w, h)
                if all(not rect.inflate(8, 8).colliderect(other.rect)
                       for other in self.items):
                    return rect.topleft
        return (left, top)

    def restart(self):
        self.load_room(1)

    def screen_to_game(self, coords):
        x = (coords[0] - self.viewport.x) / self.scale
        y = (coords[1] - self.viewport.y) / self.scale
        return x, y

    def update_viewport(self):
        sw, sh = self.screen.get_size()
        self.scale = min(sw / GAME_W, sh / GAME_H)
        w, h = round(GAME_W * self.scale), round(GAME_H * self.scale)
        self.viewport = pygame.Rect((sw-w)//2, (sh-h)//2, w, h)

    def set_bins_for(self, pointer):
        for bin_obj in self.bins:
            bin_obj.highlight = bool(self.selected and
                                     bin_obj.rect.collidepoint(pointer) and
                                     bin_obj.group == self.selected.group)

    def pointer_down(self, tag, pos):
        if self.phase == 'finished':
            if self.end_play_button.collidepoint(pos):
                self.restart()
            elif self.end_home_button.collidepoint(pos) or HOME_RECT.collidepoint(pos):
                self.running = False
            return
        if HOME_RECT.collidepoint(pos):
            self.running = False
            return
        if self.phase != 'playing' or self.active_pointer is not None:
            return
        for item in reversed(self.items):
            if not item.sorted and item.rect.collidepoint(pos):
                self.active_pointer = tag
                self.selected = item
                self.items.remove(item)
                self.items.append(item)  # lifted sprite paints on top
                item.grab(pos)
                break

    def pointer_move(self, tag, pos):
        if self.phase != 'playing' or self.active_pointer != tag or self.selected is None:
            return
        self.selected.move_to(pos)
        self.set_bins_for(pos)

    def pointer_up(self, tag, pos):
        if self.active_pointer != tag or self.selected is None:
            return
        item = self.selected
        # A quick tap, drag, or release outside the screen remains recoverable.
        item.move_to(pos)
        for bin_obj in self.bins:
            if bin_obj.rect.collidepoint(pos) and bin_obj.group == item.group:
                item.sorted = True
                self.sorted_count += 1
                break
        self.active_pointer = None
        self.selected = None
        for bin_obj in self.bins:
            bin_obj.highlight = False
        if self.sorted_count == len(self.items):
            self.phase = 'room_clear'
            self.phase_seconds = 0.0

    def input(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_r and self.phase == 'finished':
                self.restart()
            return
        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            pos = self.screen_to_game((event.x * self.screen.get_width(),
                                       event.y * self.screen.get_height()))
            tag = ('finger', event.finger_id)
            if event.type == pygame.FINGERDOWN:
                self.pointer_down(tag, pos)
            elif event.type == pygame.FINGERMOTION:
                self.pointer_move(tag, pos)
            else:
                self.pointer_up(tag, pos)
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            # Browsers may dispatch a synthetic mouse event for every finger.
            if getattr(event, 'touch', False) or getattr(event, 'which', None) == getattr(pygame, 'TOUCH_MOUSEID', -1):
                return
            pos = self.screen_to_game(event.pos)
            tag = ('mouse', 0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.pointer_down(tag, pos)
            elif event.type == pygame.MOUSEMOTION:
                self.pointer_move(tag, pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.pointer_up(tag, pos)

    def update(self, dt):
        if self.phase == 'room_clear':
            self.phase_seconds += dt
            if self.phase_seconds >= 1.8:
                if self.room < ROOM_COUNT:
                    self.load_room(self.room + 1)
                else:
                    # Keep the reward screen until Play Again or Home is tapped.
                    self.phase = 'finished'
                    self.phase_seconds = 0.0

    def draw_centered(self, message, font, color, pos):
        img = font.render(message, True, color)
        self.canvas.blit(img, img.get_rect(center=pos))

    def draw_star(self, center, size, phase):
        if self.star is not None:
            rotated = pygame.transform.rotozoom(self.star, math.sin(phase * 2) * 12,
                                                 size / 160.0)
            self.canvas.blit(rotated, rotated.get_rect(center=center))
            return
        # Procedural star if star.png isn't installed.
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            radius = size * (0.5 if i % 2 == 0 else 0.23)
            points.append((center[0] + radius * math.cos(angle),
                           center[1] + radius * math.sin(angle)))
        pygame.draw.polygon(self.canvas, (255, 209, 68), points)

    def dim_background(self):
        dim = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
        dim.fill((19, 46, 52, 165))
        self.canvas.blit(dim, (0, 0))

    def draw_room_clear(self):
        self.dim_background()
        self.draw_star((400, 280), 170, self.phase_seconds)
        self.draw_centered('Great job!', self.font_big, (255, 250, 205), (400, 130))
        self.draw_centered('Room %d is clean!' % self.room, self.font_medium,
                           (255, 255, 255), (400, 410))

    def draw_finished(self):
        self.dim_background()
        for x, y, color in self.confetti:
            pygame.draw.circle(self.canvas, color, (x, y), 5)
        self.draw_star((400, 230), 184, pygame.time.get_ticks() / 1800.0)
        self.draw_centered('Amazing!', self.font_big, (255, 250, 195), (400, 90))
        self.draw_centered('The whole house is clean!', self.font_medium,
                           (255, 255, 255), (400, 352))
        self.draw_centered('All 6 rooms sorted!', self.font_small,
                           (235, 250, 218), (400, 388))
        for rect, label, color in (
            (self.end_play_button, 'PLAY AGAIN', (61, 158, 105)),
            (self.end_home_button, 'HOME', (225, 130, 67)),
        ):
            pygame.draw.rect(self.canvas, color, rect, border_radius=15)
            pygame.draw.rect(self.canvas, (255, 255, 255), rect, 4, border_radius=15)
            self.draw_centered(label, self.font_medium, (255, 255, 255), rect.center)

    def draw(self):
        self.canvas.fill((239, 245, 230))
        if self.background is not None:
            self.canvas.blit(self.background, (0, 0))
        for bin_obj in self.bins:
            bin_obj.draw(self.canvas)
        tick = pygame.time.get_ticks()
        for item in self.items:
            item.draw(self.canvas, tick, dragging=(item is self.selected))
        # Unobtrusive progress indicator, clear of the home button and bins.
        badge = pygame.Rect(279, 13, 245, 42)
        pygame.draw.rect(self.canvas, (28, 75, 75), badge, border_radius=13)
        self.draw_centered('Room %d / %d     %d / %d' %
                           (self.room, ROOM_COUNT, self.sorted_count, len(self.items)),
                           self.font_small, (255, 255, 255), badge.center)
        if self.home_img is not None:
            self.canvas.blit(self.home_img, HOME_RECT)
        else:
            pygame.draw.rect(self.canvas, (227, 139, 73), HOME_RECT, border_radius=15)
            self.draw_centered('HOME', self.font_small, (255, 255, 255), HOME_RECT.center)
        if self.phase == 'room_clear':
            self.draw_room_clear()
        elif self.phase == 'finished':
            self.draw_finished()
        self.update_viewport()
        self.screen.fill((32, 54, 54))
        if self.viewport.size == (GAME_W, GAME_H):
            self.screen.blit(self.canvas, self.viewport.topleft)
        else:
            self.screen.blit(pygame.transform.smoothscale(self.canvas, self.viewport.size),
                             self.viewport.topleft)
        pygame.display.flip()


async def main(screen, clock):
    """Called by the existing GameHub launcher; no display or Pygame quit here."""
    game = WasteSortGame(screen)
    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        game.update_viewport()
        for event in pygame.event.get():
            game.input(event)
        game.update(dt)
        if game.running:
            game.draw()
        await asyncio.sleep(0)
