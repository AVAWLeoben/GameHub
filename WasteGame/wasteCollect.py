# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import random as rd
import os
import helper

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


def ret():
    global RUNNING
    RUNNING = False


HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


class Wastebin:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.image = pygame.image.load("assets/trashBin_green_open.png")
        self.image = pygame.transform.scale(self.image, (self.w, self.h))
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def update(self):
        mouse_held = pygame.mouse.get_pressed()[0]
        for event in EVENTS:
            if event.type == pygame.MOUSEMOTION and mouse_held:
                self.x = event.pos[0]
                self.rect = pygame.Rect(self.x - self.w // 2, self.y - self.h // 2, self.w, self.h)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


WASTEBIN = Wastebin(400, 500, 150, 150)
STARS = []
STAR_IMAGE = pygame.image.load("assets/star.png").convert_alpha()
STAR_IMAGE = pygame.transform.scale(STAR_IMAGE, (10, 10))


class Star:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vy = rd.uniform(-10, -20)
        self.ay = 1
        self.vx = rd.choice([-1, 1]) * rd.uniform(1, 10)
        self.creationTime = pygame.time.get_ticks()
        self.lifetime = 1000
        self.image = STAR_IMAGE
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.to_delete = False

    def update(self):
        currentTime = pygame.time.get_ticks()
        if currentTime - self.creationTime > self.lifetime:
            self.to_delete = True
            return
        self.x = self.x + self.vx
        self.vy = self.vy + self.ay
        self.y = self.y + self.vy
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Catchable:
    def __init__(self, x, y, w, h, image):
        self.x = x
        self.y = y
        self.w = rd.randint(w, w + 10)
        self.h = self.w
        self.vx = 0
        self.vy = 0
        self.vyMax = rd.randint(3, 5)
        self.ay = 1
        self.image = image
        self.image = pygame.transform.scale(self.image, (self.w, self.h))
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.caught = False
        self.to_delete = False

    def spawnStars(self):
        global STARS
        nStars = 18
        for i in range(nStars):
            STARS.append(Star(self.x, self.y))

    def checkIfCaught(self):
        global SCORE
        if WASTEBIN.rect.contains(self.rect):
            self.caught = True
            self.to_delete = True
            self.spawnStars()
            SCORE = SCORE + 1

    def update(self):
        global SCORE
        self.checkIfCaught()
        self.x = self.x
        self.vy = min(self.vy + self.ay, self.vyMax)
        self.y = self.y + self.vy
        if self.y > 700:
            self.to_delete = True
            SCORE = SCORE - 1
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


def cleanUpWaste():
    global OBJECTS, STARS
    OBJECTS = [obj for obj in OBJECTS if not obj.to_delete]
    STARS = [obj for obj in STARS if not obj.to_delete]


def spawnNewObjects():
    global OBJECTS, MAXOBJECTS
    MAXOBJECTS = max(1, max(SCORE, 1) // 10) + 2
    print(MAXOBJECTS)
    objectSize = 75
    nObjectsToSpawn = MAXOBJECTS - len(OBJECTS)
    for i in range(nObjectsToSpawn):
        newX = rd.randint(0, 700)
        newY = rd.randint(-1000, -5)
        newImage = IMAGES[rd.randint(0, len(IMAGES) - 1)]
        newObject = Catchable(newX, newY, objectSize, objectSize, newImage)

        if all(not obj.rect.colliderect(newObject.rect) for obj in OBJECTS):
            OBJECTS.append(newObject)


def updateObjects():
    for obj in OBJECTS:
        obj.update()
    for star in STARS:
        star.update()
    cleanUpWaste()
    spawnNewObjects()


def update():
    global RUNNING, SCORE
    HOME_BUTTON.update(EVENTS)
    updateObjects()
    WASTEBIN.update()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                SCORE = SCORE + 1


def drawScore():
    x = 600
    y = 10
    font = pygame.font.SysFont(None, 48)  # Choose your font and size
    text_surface = font.render(f"Score: {SCORE}", True, (255, 255, 255))  # White text
    SCREEN.blit(text_surface, (x, y))  # Draw at (600, 10)


def draw():
    SCREEN.fill((10, 10, 30))
    SCREEN.blit(BACKGROUND, (0, 0))
    for obj in OBJECTS:
        obj.draw()
    for star in STARS:
        star.draw()
    HOME_BUTTON.draw(SCREEN)
    drawScore()
    WASTEBIN.draw()
    # helper.drawFPS(SCREEN, CLOCK)
    pygame.display.flip()


def loadImages():
    global IMAGES
    IMAGES = []
    paths = [
        "banana.png",
        "can.png",
        "card_1.png",
        "card_2.png",
        "card_3.png",
        "card_4.png",
        "card_5.png",
        "card_6.png",
        "card_7.png",
        "card_8.png",
        "paperbox.png",
    ]
    for path in paths:
        if path.endswith(".png"):
            path = "assets/wasteCollect/" + path
            IMAGES.append(pygame.image.load(path))


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS, MAXOBJECTS, OBJECTS, IMAGES, BACKGROUND, SCORE
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    IMAGES = []
    loadImages()
    OBJECTS = []
    SCORE = 0
    MAXOBJECTS = max(1, max(SCORE, 1) // 10)
    spawnNewObjects()
    BACKGROUND = pygame.image.load("assets/wasteCollect/background/background.png")
    BACKGROUND = pygame.transform.scale(BACKGROUND, (800, 600))
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
