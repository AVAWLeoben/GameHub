# -*- coding: utf-8 -*-
"""
Created on Tue Jun 24 17:39:49 2025

@author: GKoinig
"""

import pygame
import asyncio
import math
import random as rd
from GUI import Button


def ret():
    global RUNNING
    RUNNING = False


class Target:
    IMAGES = [
        pygame.image.load("assets/Asteroid.png"),
        pygame.image.load("assets/wasteTeroids/Asteroid2.png"),
        pygame.image.load("assets/wasteTeroids/Asteroid3.png"),
        pygame.image.load("assets/wasteTeroids/Asteroid4.png"),
    ]

    def __init__(self, x=400, y=400, size=64):
        self.x = x
        self.y = y
        self.v = rd.uniform(2, 4)
        self.size = size
        self.angle = rd.uniform(0, 360)
        self.vx = self.v * math.sin(math.radians(self.angle))
        self.vy = self.v * math.cos(math.radians(self.angle))
        self.lt = pygame.Rect(8, 8, self.size, self.size, bottomright=(self.x, self.y))
        self.rt = pygame.Rect(8, 8, self.size, self.size, bottomleft=(self.x, self.y))
        self.lb = pygame.Rect(8, 8, self.size, self.size, topright=(self.x, self.y))
        self.rb = pygame.Rect(8, 8, self.size, self.size, topleft=(self.x, self.y))
        self.parts = [self.lt, self.rt, self.lb, self.rb]
        self.rect = pygame.Rect(self.x, self.y, self.size * 2, self.size * 2)
        self.rect.center = (self.x, self.y)
        self.creation_time = pygame.time.get_ticks()
        self.image = rd.choice(Target.IMAGES)
        self.image = pygame.transform.scale(self.image, (self.size * 2, self.size * 2))
        self.angle = 0
        TARGETS.append(self)

    def update(self):
        global POINTS
        # Update Rects
        self.x = self.x + self.vx
        self.y = self.y + self.vy
        self.lt.bottomright = (self.x, self.y)
        self.rt.bottomleft = (self.x, self.y)
        self.lb.topright = (self.x, self.y)
        self.rb.topleft = (self.x, self.y)
        # Respawn on edges
        if self.x > SCREEN.get_width():
            self.x = 0
            self.y = rd.uniform(0, SCREEN.get_height())
        elif self.x < 0:
            self.x = SCREEN.get_width()
            self.y = rd.uniform(0, SCREEN.get_height())
        # Respawn on edges
        if self.y > SCREEN.get_height():
            self.x = rd.uniform(0, SCREEN.get_width())
            self.y = 0
        elif self.y < 0:
            self.x = rd.uniform(0, SCREEN.get_width())
            self.y = SCREEN.get_height()

        # Update Rect
        self.rect.center = (self.x, self.y)

        # Check if hit
        for p in PROJECTILES:
            if p.rect.colliderect(self.rect):
                POINTS = POINTS + self.size
                try:
                    to_delete = rd.choice(range(0, len(self.parts)))
                    self.parts.remove(self.parts[to_delete])
                    Target(self.x, self.y, self.size // 2)
                except:
                    TARGETS.remove(self)

        # Remove Targets that were hit 4 times
        if len(self.parts) == 0:
            try:
                TARGETS.remove(self)
            except:
                self.size = 16

        # Remove small targets
        if self.size < 16 and self.creation_time + 750 < pygame.time.get_ticks():
            if self in TARGETS:
                TARGETS.remove(self)

    def draw(self):
        # pygame.draw.rect(SCREEN,(0,0,0),self.rect)
        for p in self.parts:
            pass
            # pygame.draw.rect(SCREEN,(125,125,125),p)
        if self.size >= 8:
            # Increment rotation angle
            self.angle = (self.angle + 1) % 360  # Rotate 1 degree per frame

            # Rotate image
            rotated_image = pygame.transform.rotate(self.image, self.angle)
            rotated_rect = rotated_image.get_rect(center=self.rect.center)

            # Draw rotated image
            SCREEN.blit(rotated_image, rotated_rect)


class Projectile:
    def __init__(self, creator):
        self.parent = creator
        self.x = self.parent.x
        self.y = self.parent.y
        self.w = 16
        self.h = 16
        self.color = (255, 0, 0)
        self.v = 10
        self.vx = self.v * math.cos(math.radians(self.parent.angle))
        self.vy = self.v * math.sin(math.radians(self.parent.angle))
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.rect.center = (self.x, self.y)
        PROJECTILES.append(self)

    def update(self):
        self.x = self.x + self.vx
        self.y = self.y + self.vy
        self.rect.center = (self.x, self.y)
        if not SCREEN.get_rect().collidepoint(self.rect.center):
            PROJECTILES.remove(self)

    def draw(self):
        pygame.draw.rect(SCREEN, self.color, self.rect)


class Player:
    IMAGE = pygame.image.load("assets/wasteTeroids/player.png").convert_alpha()

    def __init__(self):
        self.x = SCREEN.get_width() // 2
        self.y = SCREEN.get_height() // 2
        self.w = 32
        self.h = 32
        self.image = pygame.transform.scale(Player.IMAGE, (self.w * 3, self.h * 3))
        self.rect = self.image.get_rect()
        self.rect.topleft = (self.x, self.y)
        self.color = (255, 0, 0)
        self.shot_intervall = 250
        self.last_shot = 0
        self.angle = 0
        self.a = 3
        self.v = 0
        self.vMax = 10
        self.rotSpeed = 5
        self.drag = 0.9
        self.vx = 0
        self.vy = 0
        self.nextTarget = None

    def shoot(self):
        Projectile(self)
        self.v = self.v - 0.5

    def update(self):
        global SCREENOFFSET_x, SCREENOFFSET_y
        angle = self.angle
        nextTarget = None
        # Get current Time
        curr_time = pygame.time.get_ticks()

        # Get Mouse Location
        mouse_down = pygame.mouse.get_pressed()[0]
        if mouse_down:
            self.nextTarget = None
            mouse_pos = pygame.mouse.get_pos()
            mX = mouse_pos[0]
            mY = mouse_pos[1]
            dx = mX - self.x
            dy = mY - self.y
            if math.hypot(dx, dy) > 25:
                angle = math.degrees(math.atan2(dy, dx))
            if math.hypot(dx, dy) > 100:
                self.v = self.v + self.a

        else:
            minDist = 9999
            if len(TARGETS) > 0:
                for t in TARGETS:
                    dx = t.x - self.x
                    dy = t.y + t.vy - self.y
                    dist = math.hypot(dx, dy)
                    if dist < minDist and t.size >= 8:
                        minDist = dist
                        nextTarget = t
                if nextTarget:
                    timeToHit = dist / 10
                    dx = nextTarget.x + timeToHit * nextTarget.vx - self.x
                    dy = nextTarget.y + timeToHit * nextTarget.vy - self.y
                    angle = math.degrees(math.atan2(dy, dx))

        self.angle = angle

        if curr_time > self.last_shot + self.shot_intervall:
            self.shoot()
            self.last_shot = curr_time

        # Controls
        if KEYS[pygame.K_w]:
            self.v = self.v + self.a
        if KEYS[pygame.K_a]:
            self.angle = self.angle - self.rotSpeed
        if KEYS[pygame.K_d]:
            self.angle = self.angle + self.rotSpeed
        if KEYS[pygame.K_s]:
            self.v = self.v - self.a
        if KEYS[pygame.K_SPACE]:
            if curr_time > self.last_shot + self.shot_intervall:
                self.shoot()
                self.last_shot = curr_time

        # Clamp Speed
        if self.v > self.vMax:
            self.v = self.vMax
        elif self.v < -self.vMax:
            self.v = -self.vMax

        # Apply drag to speed
        self.v = self.v * self.drag
        if abs(self.v) < 0.1:
            self.v = 0

        # Calculate speed
        if abs(self.v) > 0:
            self.vx = self.v * math.cos(math.radians(self.angle))
            self.vy = self.v * math.sin(math.radians(self.angle))

        # Update Position
        self.x = self.x + self.vx
        self.y = self.y + self.vy

        # Clamp x-Position
        self.x = max(0, self.x)
        self.x = min(self.x, SCREEN.get_width())
        self.y = max(0, self.y)
        self.y = min(self.y, SCREEN.get_height())

        # Update Rectangle
        self.rect.center = (self.x, self.y)
        if nextTarget:
            self.nextTarget = nextTarget

        SCREENOFFSET_x = int(SCREENOFFSET_x + 0.1 * self.vx)
        SCREENOFFSET_y = int(SCREENOFFSET_y + 0.05 * self.vy)

    def draw(self):
        # pygame.draw.rect(SCREEN,pygame.Color("darkgreen"),self.rect)
        crossair_x = self.x + 20 * math.cos(math.radians(self.angle))
        crossair_y = self.y + 20 * math.sin(math.radians(self.angle))
        pygame.draw.circle(SCREEN, pygame.Color("black"), (crossair_x, crossair_y), 5)
        drawimage = self.image.copy()
        if abs(self.vx) > 0:
            if self.vx < 0:
                drawimage = pygame.transform.flip(self.image, 1, 0)
        SCREEN.blit(drawimage, self.rect)
        if self.nextTarget is not None and len(TARGETS) > 0:
            pygame.draw.circle(SCREEN, pygame.Color("red"), (self.nextTarget.x, self.nextTarget.y), self.nextTarget.size * 2, 1)


def setup():
    pygame.init()
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    global FONT
    pygame.font.init()
    FONT = pygame.font.SysFont("Arial", 24)
    global PLAYER
    PLAYER = Player()
    global PROJECTILES
    PROJECTILES = []
    global TARGETS
    TARGETS = []
    Target()
    global POINTS
    POINTS = 0
    global BACKGROUND
    BACKGROUND = pygame.image.load("assets/wasteTeroids/background.jpg")
    global SCREENOFFSET_x, SCREENOFFSET_y
    SCREENOFFSET_x, SCREENOFFSET_y = (
        -(BACKGROUND.get_width() - SCREEN.get_width()) // 2,
        -(BACKGROUND.get_height() - SCREEN.get_height()) // 2,
    )


def update():
    global EVENTS, KEYS, RUNNING
    EVENTS = pygame.event.get()
    HOME_BUTTON.update(EVENTS)
    KEYS = pygame.key.get_pressed()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    PLAYER.update()
    for p in PROJECTILES:
        p.update()
    for t in TARGETS:
        t.update()
    if len(TARGETS) == 0:
        Target(-100, -100)
        Target(1000, 1000)


def draw():
    SCREEN.fill(pygame.Color("black"))
    SCREEN.blit(BACKGROUND, (SCREENOFFSET_x, SCREENOFFSET_y))
    PLAYER.draw()
    for p in PROJECTILES:
        p.draw()
    for t in TARGETS:
        t.draw()
    # Render the points text
    points_text = FONT.render(f"Points: {POINTS}", True, pygame.Color("green"))
    text_rect = points_text.get_rect(topright=(SCREEN.get_width() - 10, 10))

    # Create a background rect slightly bigger than the text_rect
    padding = 6
    bg_rect = text_rect.inflate(padding * 2, padding * 2)  # wider and taller
    bg_rect.topright = text_rect.topright  # align the background rect with the text
    text_rect.center = bg_rect.center
    # Draw the rounded rectangle background (light gray color)
    pygame.draw.rect(SCREEN, (200, 200, 200), bg_rect, border_radius=8)

    # Blit the points text on top
    SCREEN.blit(points_text, text_rect)
    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()
    while RUNNING:
        CLOCK.tick(60)
        update()
        draw()
        await asyncio.sleep(0)

    return
