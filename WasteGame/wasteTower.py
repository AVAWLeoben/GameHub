# -*- coding: utf-8 -*-
"""
Created on Mon Jun  2 12:43:57 2025

@author: GKoinig
"""

import pygame
import math
import random as rd

from GUI import Button
import asyncio

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


def ret():
    global RUNNING
    RUNNING = False


HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


class Aircraft:
    def selectImage(self):
        if TOWER_HEIGHT >= 400 and TOWER_HEIGHT <= 1200:
            self.orig_image = AIRCRAFT_IMAGES[0]  # Draw Helicopter
        elif TOWER_HEIGHT > 1200 and TOWER_HEIGHT <= 1500:
            self.orig_image = AIRCRAFT_IMAGES[rd.choice([0, 1])]  # Draw Helicopter and Planes
        elif TOWER_HEIGHT > 1500 and TOWER_HEIGHT < 4000:
            self.orig_image = AIRCRAFT_IMAGES[1]  # Draw Planes
        else:
            self.orig_image = AIRCRAFT_IMAGES[2]  # Draw Spacecraft
        self.orig_image = pygame.transform.scale(self.orig_image, (self.w, self.h))
        self.image = self.orig_image.copy()

    def __init__(self):
        self.x = rd.choice([-50, 850])
        self.y = rd.randint(0, 300)
        self.vx = int(math.copysign(rd.choice([1, 2]), -self.x))
        self.w = 100
        self.h = 50
        self.selectImage()

        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.facingLeft = False

    def respawn(self):
        self.selectImage()
        self.facingLeft = False
        self.x = rd.choice([-50, 850])
        self.y = rd.randint(0, 100)
        self.vx = int(math.copysign(1, -self.x))

        if self.vx < 0:
            self.image = pygame.transform.flip(self.orig_image, True, False)
            self.facingLeft = True

        self.rect = self.image.get_rect(center=(self.x, self.y))

    def update(self):
        self.x += self.vx

        # Add subtle vertical oscillation
        time_now = pygame.time.get_ticks() / 1000.0  # seconds
        bob_amplitude = 5
        bob_speed = 2
        self.y_bob = self.y + math.sin(time_now * bob_speed + self.x * 0.01) * bob_amplitude

        self.rect = self.image.get_rect(center=(self.x, self.y_bob))

        if self.vx < 0 and not self.facingLeft:
            self.image = pygame.transform.flip(self.orig_image, True, False)
            self.facingLeft = True
        elif self.vx > 0 and self.facingLeft:
            self.image = pygame.transform.flip(self.orig_image, True, False)
            self.facingLeft = False

        if self.x > 850 and self.vx > 0:
            self.respawn()
        elif self.x < -50 and self.vx < 0:
            self.respawn()

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Crate:
    def __init__(self, x, y, h=100, w=100, onCrane=True, onFloor=False):
        self.x = x
        self.y = y
        self.vx = 0
        self.drag = 0.75
        self.vy = 0
        self.width = rd.randint(w - 10, w + 10)
        self.h = rd.randint(h - 25, h + 10)
        self.original_image = CRATE_IM
        self.original_image = pygame.transform.scale(self.original_image, (self.width, self.h))
        self.rect = self.original_image.get_rect(center=(self.x, self.y))
        self.image = self.original_image.copy()
        self.onCrane = onCrane
        self.g = 1
        self.maxPhi = 30
        self.phi = rd.randint(-self.maxPhi, self.maxPhi)
        self.w = rd.randint(1, 2)
        self.wMax = self.w

        self.onFloor = onFloor
        self.beingHoisted = False
        self.hoist_phase = 0
        self.origin_x, self.origin_y = rd.randint(300, 500), 70
        self.creationTime = pygame.time.get_ticks()
        if len(CRATES) > 0:
            self.x = 700
            self.y = 800
            self.beingHoisted = True

        self.flash_timer = 0  # Duration of the visual flash

    def update(self):
        self.image = self.original_image.copy()
        if self.beingHoisted:
            target_x = self.origin_x
            top_y = self.origin_y + CABLE_LENGTH // 2
            final_y = self.origin_y + CABLE_LENGTH  # Lower slightly below cable

            # Phase 0: Go up
            if self.hoist_phase == 0:
                if self.y > top_y:
                    self.y -= 10
                else:
                    self.hoist_phase = 1

            # Phase 1: Slide left
            elif self.hoist_phase == 1:
                if self.x > target_x:
                    self.x -= 10
                else:
                    self.x = target_x
                    self.hoist_phase = 2

            # Phase 2: Lower down from crane
            elif self.hoist_phase == 2:
                if self.y < final_y:
                    self.y += 5  # Slower descent looks more natural
                else:
                    # Done hoisting
                    self.beingHoisted = False
                    rad_phi = math.radians(self.phi)
                    self.x = target_x
                    self.phi = 0
                    self.y = self.origin_y + CABLE_LENGTH * math.cos(rad_phi)

            self.rect = self.image.get_rect(center=(self.x, self.y))
            return

        if FLOOR.colliderect(self.rect):
            self.y = FLOOR.top - self.h // 2
            self.vx = 0
            self.vy = 0
            self.onCrane = False
            self.onFloor = True

        # Check collision with any crate below
        elif not self.onFloor:
            for other in reversed(CRATES):  # Iterate from topmost to bottommost
                if other is not self and other.onFloor and self.rect.colliderect(other.rect.move(0, -20)) and self.y < other.y:
                    self.y = other.rect.top - self.h // 2
                    if abs(self.vx) < 0.2:
                        self.vx = 0
                        self.onFloor = True
                        self.vy = 0
                        self.onCrane = False
                        self.flash_timer = 12  # Show flash for 10 frames
                        break
                    else:
                        self.vx = self.vx * self.drag
                        self.vy = 0
                        self.onCrane = False
                        break

        if self.onCrane:
            if self.phi >= self.maxPhi:
                self.phi = self.maxPhi
                self.w = -self.wMax
            if self.phi <= -self.maxPhi:
                self.phi = -self.maxPhi
                self.w = +self.wMax
            self.phi = self.phi + self.w
            rad_phi = math.radians(self.phi)
            self.y = self.origin_y + CABLE_LENGTH * math.cos(rad_phi)
            self.x = self.origin_x + CABLE_LENGTH * math.sin(rad_phi)

            tangential_speed = math.radians(self.w) * CABLE_LENGTH
            self.vx = tangential_speed * math.cos(rad_phi)
            self.vy = -tangential_speed * math.sin(rad_phi)
            self.image = pygame.transform.rotate(self.image, self.phi)
        else:
            if not self.onFloor:
                self.vy = self.vy + self.g
                if self.phi > 0:
                    self.phi = self.phi - 1
                if self.phi < 0:
                    self.phi = self.phi + 1
                self.x = self.x + self.vx
                self.y = self.y + self.vy
                self.image = pygame.transform.rotate(self.image, self.phi)

        self.rect = self.image.get_rect(center=(self.x, self.y))

        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.onCrane = False

    def draw(self):
        if self.onCrane and not self.beingHoisted:
            pygame.draw.line(SCREEN, (0, 0, 0), (self.x, self.y), (self.origin_x, self.origin_y), 4)
        if self.onCrane and self.beingHoisted:
            pygame.draw.line(SCREEN, (0, 0, 0), (self.x, self.y), (self.x, self.origin_y), 4)

        # SCREEN.blit(self.image,self.rect.move(0,0))
        try:
            if self.flash_timer > 0:
                tinted = self.image.copy()
                tint_color = (30 + 10 - self.flash_timer, 30 + 10 - self.flash_timer, 0)  # Subtle yellow tint
                tint_surface = pygame.Surface((self.width, self.h))
                tint_surface.fill(tint_color)
                tinted.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                SCREEN.blit(tinted, self.rect)
                self.flash_timer -= 1
            else:
                SCREEN.blit(self.image, self.rect)
        except Exception as e:
            print(e)


def loadImages():
    global BACKGROUND_IM, BACKGROUND_OFFSET_Y, CRATE_IM, CRANE_IMG, AIRCRAFT_IMAGES, BACKGROUND_IM_WHOLE
    BACKGROUND_IM = pygame.image.load("assets/BuildTower/background.png")
    BACKGROUND_IM_WHOLE = pygame.transform.scale(BACKGROUND_IM, (80, 250))
    BACKGROUND_OFFSET_Y = HEIGHT - BACKGROUND_IM.get_height()
    CRATE_IM = pygame.image.load("assets/BuildTower/crate.png")
    CRANE_IMG = pygame.image.load("assets/BuildTower/crane.png")
    AIRCRAFT_IMAGES = [
        pygame.image.load("assets/BuildTower/heli.png"),
        pygame.image.load("assets/BuildTower/plane.png"),
        pygame.image.load("assets/BuildTower/shuttle.png"),
    ]


def createCrates():
    global CRATES
    if all(crate.onFloor for crate in CRATES) and not any(crate.onCrane for crate in CRATES):
        CRATES.append(Crate(900, 900, CRATE_SIZE, CRATE_SIZE, True))


def setup():
    global CRATES, CRATE_SIZE, CABLE_LENGTH, FLOOR, TOP_Y, WIDTH, HEIGHT, AIRCRAFTS, TOWER_HEIGHT
    TOWER_HEIGHT = 0
    WIDTH = 800
    HEIGHT = 600
    CRATE_SIZE = 75
    CABLE_LENGTH = 150
    FLOOR = pygame.Rect(0, 525, 800, 600)
    loadImages()
    AIRCRAFTS = []

    CRATES = []
    # CRATES.append(Truck())
    CRATES.append(Crate(400, FLOOR.top + CRATE_SIZE, CRATE_SIZE, CRATE_SIZE, False, True))
    CRATES[0].beingHoisted = False
    CRATES.append(Crate(400, 250, CRATE_SIZE, CRATE_SIZE, True))
    grounded_crates = [crate for crate in CRATES if not crate.onCrane and crate.onFloor]
    if grounded_crates:
        TOP_Y = min(crate.y for crate in grounded_crates)


def update():
    global RUNNING, BACKGROUND_OFFSET_Y, TOP_Y, TOWER_HEIGHT
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
            pygame.quit()

    for crate in CRATES:
        crate.update()

    # Only consider grounded crates for scroll decision
    grounded_crates = [crate for crate in CRATES if not crate.onCrane and crate.onFloor]

    if grounded_crates:
        TOP_Y = min(crate.y for crate in grounded_crates)

        if TOP_Y < 380:
            FLOOR.top += 2
            BACKGROUND_OFFSET_Y += 2
            TOWER_HEIGHT += 2
            print(TOWER_HEIGHT)
            # Move only the grounded crates
            for crate in grounded_crates:
                crate.y += 2
                crate.rect.center = (crate.x, crate.y)

            for ac in AIRCRAFTS:
                ac.y += 2
                ac.rect.center = (ac.x, ac.y)

    createCrates()
    if TOWER_HEIGHT > 400 and len(AIRCRAFTS) == 0:
        AIRCRAFTS.append(Aircraft())

    for ac in AIRCRAFTS:
        ac.update()
    HOME_BUTTON.update(EVENTS)


def drawScore():
    if TOWER_HEIGHT > 0:
        font = pygame.font.SysFont("Comic Sans MS", 24)
        text = font.render(f"HEIGHT: {TOWER_HEIGHT / 10:.1f} m", True, (0, 0, 0))

        # Background box size and position
        padding = 10
        text_rect = text.get_rect()
        text_rect.bottomleft = (10 + padding, 500 - padding)

        box_rect = pygame.Rect(
            text_rect.left - padding,
            text_rect.top - padding,
            text_rect.width + 2 * padding,
            text_rect.height + 2 * padding,
        )

        # Draw background (soft yellow with some transparency)
        box_surface = pygame.Surface((box_rect.width, box_rect.height), pygame.SRCALPHA)
        box_surface.fill((255, 255, 200, 200))  # Light yellow, slightly transparent

        SCREEN.blit(box_surface, (box_rect.left, box_rect.top))
        SCREEN.blit(text, text_rect)


def draw():
    SCREEN.fill((255, 255, 255))
    SCREEN.blit(BACKGROUND_IM, (0, BACKGROUND_OFFSET_Y))
    for ac in AIRCRAFTS:
        ac.draw()
    SCREEN.blit(CRANE_IMG, (0, 0))
    for crate in CRATES:
        crate.draw()
    HOME_BUTTON.draw(SCREEN)
    mini_bg_x = 5
    mini_bg_y = 120
    SCREEN.blit(BACKGROUND_IM_WHOLE, (mini_bg_x, mini_bg_y))
    for crate in CRATES:
        small_img = pygame.transform.scale(crate.original_image, (crate.width // 10, crate.h // 10))
        small_rect = small_img.get_rect(center=(crate.x // 10, (crate.y - TOWER_HEIGHT) // 10 + 291 + 20))
        SCREEN.blit(small_img, small_rect)
    drawScore()
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    setup()
    RUNNING = True
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
