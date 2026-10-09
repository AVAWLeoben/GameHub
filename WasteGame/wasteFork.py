# -*- coding: utf-8 -*-
"""
Created on Fri May 30 19:53:37 2025

@author: Admin
"""

import pygame
import math
import asyncio
from GUI import Button
from helper import drawFPS

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


def ret():
    global RUNNING
    RUNNING = False


HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


class Forklift:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.liftspeed = 0.250
        self.orig_image = FORKLIFTIMAGE
        self.orig_image = pygame.transform.scale(self.orig_image, (self.w, self.h))
        self.image = self.orig_image.copy()
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.angle = 0
        self.speed = 4
        self.driving = False
        self.forkDown = True

    def update(self):
        mousePos = pygame.mouse.get_pos()

        dx = mousePos[0] - self.x
        dy = mousePos[1] - self.y
        dist = math.hypot(dx, dy)
        self.angle = math.degrees(math.atan2(-dy, dx))
        self.image = pygame.transform.rotate(self.orig_image, self.angle)

        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.driving = True
            if event.type == pygame.MOUSEBUTTONUP:
                self.driving = False
        if self.driving and dist > 50:
            dx = mousePos[0] - self.x
            dy = mousePos[1] - self.y
            next_x = self.x + self.speed * dx / dist
            next_y = self.y + self.speed * dy / dist
            self.x = min(next_x, 800)
            self.x = max(next_x, 0)
            self.y = min(next_y, 600)
            self.y = max(next_y, 0)

        self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Target:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self):
        pygame.draw.rect(SCREEN, (0, 255, 0), self.rect, 1)


class Palette:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.minW = w
        self.minH = h
        self.maxW = w * 1.25
        self.maxH = h * 1.25

        self.orig_image = pygame.transform.scale(PALETTENIMAGE, (w, h))
        self.base_image = self.orig_image.copy()  # Original unrotated scaled version

        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.floorRect = self.rect.inflate(self.minW, self.minH)

        self.beingLifted = False
        self.beingLowered = False
        self.lifted = False
        self.angle = 0
        self.onForklift = False
        self.correct = False

    def update(self):
        # Check for lift position
        if (
            FORKLIFT.rect.contains(self.floorRect)
            and not TARGET.rect.contains(self.floorRect)
            and not any(p.onForklift for p in PALETTEN)
        ):
            self.beingLifted = True
            self.angle = FORKLIFT.angle
            self.onForklift = True

        if TARGET.rect.contains(self.floorRect) and self.onForklift:
            self.beingLowered = True
        if TARGET.rect.contains(self.floorRect) and self.lifted == False:
            self.correct = True

        # Handle input
        for event in EVENTS:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    if not self.lifted:
                        self.beingLifted = True
                    else:
                        self.beingLowered = True

        # Handle lift and scale
        if self.beingLifted:
            self.w = min(self.maxW, self.w + FORKLIFT.liftspeed)
            self.h = min(self.maxH, self.h + FORKLIFT.liftspeed)
            if self.h >= self.maxH:
                self.beingLifted = False
                self.lifted = True

        elif self.beingLowered:
            self.w = max(self.minW, self.w - FORKLIFT.liftspeed)
            self.h = max(self.minH, self.h - FORKLIFT.liftspeed)
            if self.h <= self.minH:
                self.beingLowered = False
                self.lifted = False
                self.onForklift = False
                self.angle = FORKLIFT.angle

        # Always scale from the original image
        self.base_image = pygame.transform.scale(PALETTENIMAGE, (int(self.w), int(self.h)))

        if self.onForklift:
            # Calculate rotated offset using Vector2
            self.angle = FORKLIFT.angle
            offset = pygame.math.Vector2(100, 0).rotate(-FORKLIFT.angle)  # 50 pixels in front
            pos = pygame.math.Vector2(FORKLIFT.x, FORKLIFT.y) + offset

            self.x, self.y = pos.x, pos.y

            # Rotate image from base_image
            self.image = pygame.transform.rotate(self.base_image, FORKLIFT.angle)

            # Center the rect at the rotated position
            self.rect = self.image.get_rect(center=(self.x, self.y))
        else:
            self.image = self.base_image.copy()
            self.image = pygame.transform.rotate(self.base_image, self.angle)
            self.rect = self.image.get_rect(center=(self.x, self.y))

        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.floorRect = pygame.Rect(0, 0, self.minW, self.minH)
        self.floorRect.center = (self.x, self.y)
        if TARGET.rect.contains(self.floorRect) and self.onForklift:
            self.beingLowered = True

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if DRAW_RECTS:
            pygame.draw.rect(SCREEN, (255, 0, 0), self.floorRect, 1)
            pygame.draw.rect(SCREEN, (0, 0, 255), self.rect, 1)


def update():
    global RUNNING, DRAW_RECTS, WIN, WIN_TIME, CURRLEVEL
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                DRAW_RECTS = not DRAW_RECTS
    FORKLIFT.update()
    for p in PALETTEN:
        p.update()
    if all(p.correct for p in PALETTEN):
        CURRLEVEL = CURRLEVEL + 1
        createLevel2()


def draw():
    SCREEN.fill((125, 125, 125))
    SCREEN.blit(FLOORIMAGE, (0, 0))
    FORKLIFT.draw()
    for p in PALETTEN:
        p.draw()
    TARGET.draw()
    HOME_BUTTON.draw(SCREEN)
    drawFPS(SCREEN, CLOCK)
    pygame.display.flip()


def win():
    global RUNNING
    if WIN:
        font = pygame.font.SysFont(None, 72)
        text = font.render("You Win!", True, (255, 255, 0))
        SCREEN.blit(text, (800 // 2 - text.get_width() // 2, 600 // 2))
        if WIN_TIME + 1000 < pygame.time.get_ticks():
            RUNNING = False


def createLevel1():
    global TARGET, WIN, FORKLIFT, PALETTEN, CURRLEVEL
    CURRLEVEL = 1
    WIN = False

    TARGET = Target(600, 400, 150, 150)
    FORKLIFT = Forklift(100, 100, 300, 100)
    PALETTEN = []

    # Six well-spaced pallet positions, avoiding TARGET and FORKLIFT
    positions = [
        (100, 300),  # Left center
        (250, 500),  # Bottom left
        (400, 150),  # Top middle
        (550, 300),  # Center right
        (150, 150),  # Top left
        (300, 400),  # Lower center-left
    ]

    for x, y in positions:
        PALETTEN.append(Palette(x, y, 100, 100))


def createLevel2():
    global TARGET, WIN, FORKLIFT, PALETTEN
    CURRLEVEL = 2
    WIN = False

    TARGET = Target(100, 100, 150, 150)  # Move target to top-left
    FORKLIFT = Forklift(700, 500, 300, 100)  # Start forklift in bottom-right
    PALETTEN = []

    # Pallet layout for Level 2 - spread across diagonals and edges
    positions = [
        (600, 100),  # Top-right
        (400, 300),  # Center
        (200, 500),  # Bottom-left
        (100, 400),  # Left edge
        (700, 200),  # Right edge
        (500, 500),  # Bottom center
    ]

    for x, y in positions:
        PALETTEN.append(Palette(x, y, 100, 100))


def loadImages():
    global PALETTENIMAGE, FORKLIFTIMAGE, FLOORIMAGE
    FLOORIMAGE = pygame.image.load("assets/wasteFork/floor.png").convert()
    PALETTENIMAGE = pygame.image.load("assets/wasteFork/palette.png")
    FORKLIFTIMAGE = pygame.image.load("assets/wasteFork/forklift_whole.png")


def setup():
    global RUNNING, DRAW_RECTS
    DRAW_RECTS = False
    RUNNING = True

    loadImages()
    createLevel1()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    EVENTS = pygame.event.get()
    setup()
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
