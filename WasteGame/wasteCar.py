# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
from helper import whiteToTransparent
import pygame
import asyncio
import math
import random as rd

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None
WIDTH, HEIGHT = 800, 600


def ret():
    global RUNNING
    RUNNING = False


home_button = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

ROADMAP = pygame.image.load("assets/road.png")
factor = 2
w, h = ROADMAP.get_size()
ROADMAP = pygame.transform.scale(ROADMAP, (int(w * factor), int(h * factor)))

ROADMAP_DRIVEABLE = pygame.image.load("assets/road_driveable.png")
ROADMAP_BINS = pygame.image.load("assets/road_bins.png")
ROADMAP_DRIVEABLE = pygame.transform.scale(ROADMAP_DRIVEABLE, (int(w * factor), int(h * factor)))

ROADMAP_NPC = pygame.image.load("assets/road_driveable - NPC.png")
ROADMAP_NPC = pygame.transform.scale(ROADMAP_NPC, (int(w * factor), int(h * factor)))


class Wastebin:
    def __init__(self, x, y):
        self.full = True
        self.x = x
        self.y = y
        self.image_full = pygame.image.load("assets/wasteBin_full.png")
        self.image_empty = pygame.image.load("assets/wasteBin_empty.png")
        self.image = self.image_full
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.area = 150

    def update(self):
        dx = self.x - PLAYER.x
        dy = self.y - PLAYER.y
        dist = math.hypot(dx, dy)
        if dist < self.area:
            self.full == False
            self.image = self.image_empty
            self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self, offset_x, offset_y):
        draw_pos = (self.rect.x - offset_x, self.rect.y - offset_y)
        SCREEN.blit(self.image, draw_pos)


class Player:
    def __init__(self, x, y, image_path):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.speed = 0
        self.vMax = 2
        self.acc = 1
        self.drag = 1
        self.angle = 0
        self.original_image = pygame.image.load(image_path)
        self.max_x = ROADMAP.get_width()
        self.max_y = ROADMAP.get_height()
        self.mass = 3
        factor = 0.5
        w, h = self.original_image.get_size()
        self.original_image = pygame.transform.scale(self.original_image, (int(w * factor), int(h * factor)))

        self.image = self.original_image
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.vMax = 10
        self.driving = False

    def check_collision(self):
        for other in CARS:
            self.vx = math.cos(math.radians(self.angle)) * self.speed
            self.vy = -math.sin(math.radians(self.angle)) * self.speed
            dx = other.x - self.x
            dy = other.y - self.y
            distance = math.hypot(dx, dy)
            min_distance = (self.rect.width + other.rect.width) / 2

            if distance < min_distance:
                # Unit normal and tangent vectors
                nx, ny = dx / distance, dy / distance
                tx, ty = -ny, nx

                # Project velocities onto normal and tangent vectors
                v1n = self.vx * nx + self.vy * ny
                v1t = self.vx * tx + self.vy * ty
                v2n = other.vx * nx + other.vy * ny
                v2t = other.vx * tx + other.vy * ty

                # Compute new normal velocities using elastic collision formula
                v1n_post = (v1n * (self.mass - other.mass) + 2 * other.mass * v2n) / (self.mass + other.mass)
                v2n_post = (v2n * (other.mass - self.mass) + 2 * self.mass * v1n) / (self.mass + other.mass)

                # Convert scalar normal and tangential velocities into vectors
                self.vx = v1n_post * nx + v1t * tx
                self.vy = v1n_post * ny + v1t * ty
                other.vx = v2n_post * nx + v2t * tx
                other.vy = v2n_post * ny + v2t * ty

                # Optional: Push them apart slightly to prevent sticking
                overlap = min_distance - distance
                self.x -= overlap / 2 * nx
                self.y -= overlap / 2 * ny
                other.x += overlap / 2 * nx
                other.y += overlap / 2 * ny

    def update(self, events):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - WIDTH // 2
        dy = mouse_y - HEIGHT // 2
        dist = math.hypot(dx, dy)
        for event in events:
            if event.type == pygame.MOUSEBUTTONUP:
                self.driving = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.driving = True

        if self.driving:
            if dist > 100:
                self.speed = self.speed + self.acc
                self.speed = min(self.speed, self.vMax)
            else:
                self.speed = self.speed - self.drag
                self.speed = max(self.speed, 0)
        else:
            self.speed = self.speed - self.drag
            self.speed = max(self.speed, 0)

        next_x = self.x + self.speed * dx / dist
        next_y = self.y + self.speed * dy / dist
        next_x = max(0, min(next_x, self.max_x - 1))
        next_y = max(0, min(next_y, self.max_y - 1))
        if ROADMAP_DRIVEABLE.get_at((int(next_x), int(next_y)))[0:3] == (255, 255, 255):
            self.x = next_x
            self.y = next_y

        self.x = max(0, min(self.x, self.max_x))
        self.y = max(0, min(self.y, self.max_y))

        self.check_collision()
        self.angle = math.degrees(math.atan2(-dy, dx))
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self, offset_x, offset_y):
        draw_pos = (self.rect.x - offset_x, self.rect.y - offset_y)
        SCREEN.blit(self.image, draw_pos)


class Car:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.orig_image = pygame.image.load("assets/car" + str(rd.randint(1, 3)) + ".png").convert_alpha()
        self.orig_image = pygame.transform.scale(self.orig_image, (100, 50))
        self.image = self.orig_image
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.angle = rd.uniform(0, 360)
        self.speed = 2
        self.mass = 1

    def update(self):
        # Length of lookahead feelers
        look_aheads = [50, 100, 200, 1000]
        turn_rate = 0.1  # degrees to adjust per frame
        found_road = False

        # Check 3 directions: center, slight left, slight right
        directions = [0, -15, 15]  # relative angle offsets
        best_direction = None

        for look_ahead in look_aheads:
            if found_road:
                break
            for offset in directions:
                test_angle = self.angle + offset
                dx = math.cos(math.radians(test_angle)) * look_ahead
                dy = math.sin(math.radians(test_angle)) * look_ahead
                test_x = int(self.x + dx)
                test_y = int(self.y + dy)

                try:
                    pixel = ROADMAP_NPC.get_at((test_x, test_y))[0:3]
                    if pixel == (255, 159, 253):  # on pink path
                        best_direction = test_angle
                        found_road = True
                        break  # prefer first matching direction (center > left > right)
                except IndexError:
                    continue  # skip out-of-bounds

            # If path found, steer gradually toward it
            if found_road and best_direction is not None:
                angle_diff = (best_direction - self.angle + 180) % 360 - 180  # shortest angle
                self.angle += max(min(angle_diff, turn_rate), -turn_rate)
                self.angle %= 360

                # Move forward
                dx = math.cos(math.radians(self.angle)) * self.speed
                dy = math.sin(math.radians(self.angle)) * self.speed
                self.x += dx
                self.y += dy
            else:
                # If no path detected, spin randomly
                # self.angle += rd.uniform(-90, 90)
                # self.angle %= 360
                self.angle = self.angle + turn_rate
                self.angle = self.angle % 360

            self.vx = math.cos(math.radians(self.angle)) * self.speed
            self.vy = -math.sin(math.radians(self.angle)) * self.speed
            # Rotate and update position
            self.image = pygame.transform.rotate(self.orig_image, -self.angle)
            self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self, offset_x, offset_y):
        draw_pos = (self.rect.x - offset_x, self.rect.y - offset_y)
        SCREEN.blit(self.image, draw_pos)


def update(events):
    global RUNNING
    home_button.update(events)
    PLAYER.update(events)
    for curr_bin in BINS:
        curr_bin.update()

    for car in CARS:
        car.update()

    for event in events:
        if event.type == pygame.QUIT:
            RUNNING = False


def drawHUD():
    xLoc = 150
    yLoc = 10
    for wasteBin in BINS:
        binImage = pygame.transform.scale(wasteBin.image, (40, 40))
        SCREEN.blit(binImage, (xLoc, yLoc))
        xLoc = xLoc + 50
        if xLoc > 800:
            xLoc = 150
            yLoc = yLoc + 50


def draw():
    SCREEN.fill((10, 10, 30))
    offset_x = PLAYER.x - WIDTH // 2
    offset_y = PLAYER.y - HEIGHT // 2
    SCREEN.blit(ROADMAP, (-offset_x, -offset_y))

    for curr_bin in BINS:
        curr_bin.draw(offset_x, offset_y)

    for car in CARS:
        car.draw(offset_x, offset_y)

    PLAYER.draw(offset_x, offset_y)
    drawHUD()
    home_button.draw(SCREEN)
    pygame.display.flip()


BINS = []


def placeWasteBins():
    global BINS
    BINS = []
    width, height = ROADMAP_BINS.get_size()
    lastX, lastY = 0, 0
    for x in range(width):
        for y in range(height):
            if ROADMAP_BINS.get_at((x, y))[0:3] == (255, 100, 100) and math.hypot(x - lastX, y - lastY) > 100:
                BINS.append(Wastebin(x * factor, y * factor))
                lastX, lastY = x, y


CARS = []


def placeRandomCars():
    global CARS
    CARS = []
    width, height = ROADMAP_NPC.get_size()
    while len(CARS) < 10:
        x = rd.randint(0, width - 1)
        y = rd.randint(100, height - 1)
        if ROADMAP_NPC.get_at((x, y))[0:3] == (255, 159, 253):
            too_close = False
            for car in CARS:
                if math.hypot(car.x - x, car.y - y) < 100:
                    too_close = True
                    break
            if not too_close:
                CARS.append(Car(x, y))


PLAYER = None


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, PLAYER
    PLAYER = Player(1110 * factor, 750 * factor, "assets/truck.png")
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    placeWasteBins()
    placeRandomCars()
    while RUNNING:
        CLOCK.tick(FPS)
        events = pygame.event.get()
        update(events)
        draw()
        await asyncio.sleep(0)

    return
