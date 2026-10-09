# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import random as rd
import math

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None
PLAYER = None


class Player:
    def __init__(self, x, y, w, h, image):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.vy = 0
        self.g = 2

        self.image = pygame.transform.scale(image, (self.w, self.h))
        self.original_image = self.image.copy()
        self.currImage = self.image.copy()
        self.rect = self.currImage.get_rect(topleft=(self.x, self.y))

        self.jumping = False
        self.pre_jump = False
        self.jumpStart = None
        self.jumpAnimationTime = 125  # ms
        self.angle = 0
        self.rotDir = 1
        self.lastAnim = pygame.time.get_ticks()
        self.large = True

        self.hit = False

    def animateJump(self):
        # Squash animation before jump
        elapsed = pygame.time.get_ticks() - self.jumpStart
        if elapsed < self.jumpAnimationTime:
            squashed_height = int(self.h * 0.8)
            y_offset = self.h - squashed_height
            self.currImage = pygame.transform.scale(self.original_image, (self.w, squashed_height))
            self.rect = self.currImage.get_rect(topleft=(self.x, self.y + y_offset))
            return False  # Not ready to jump yet
        else:
            self.currImage = self.original_image.copy()
            self.rect = self.currImage.get_rect(topleft=(self.x, self.y))
            return True  # Time to jump

    def animateDrive(self):
        if not self.jumping and not self.pre_jump:
            # Time-based sine wave oscillation
            time = pygame.time.get_ticks() / 100  # Adjust speed here
            bounce = math.sin(time) * 0.05  # Bounce intensity (5% up and down)

            scale_y = int(self.h * (1 - bounce))
            y_offset = self.h - scale_y

            self.currImage = pygame.transform.scale(self.original_image, (self.w, scale_y))
            self.rect = self.currImage.get_rect(topleft=(self.x, self.y + y_offset))

    def update(self):
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN and not self.jumping and not self.pre_jump:
                self.pre_jump = True
                self.jumpStart = pygame.time.get_ticks()

        if self.pre_jump:
            if self.animateJump():
                self.vy = -30
                self.jumping = True
                self.pre_jump = False
                self.angle = 0  # reset rotation at jump start
                self.rotDir = rd.choice([-1, 1])

        if self.jumping:
            self.vy += self.g
            nextY = self.y + self.vy
            future_rect = pygame.Rect(self.x, nextY, self.w, self.h)

            if not future_rect.colliderect(FLOOR):
                self.y = nextY

                # Increment angle for spinning
                self.angle -= 12 * self.rotDir  # adjust spin speed here

                # Rotate from original image
                center = (self.x + self.w // 2, self.y + self.h // 2)
                self.currImage = pygame.transform.rotate(self.original_image, self.angle)
                self.rect = self.currImage.get_rect(center=center)
            else:
                self.jumping = False
                self.vy = 0
                self.y = FLOOR.y - self.h
                self.currImage = self.original_image.copy()
                self.rect = self.currImage.get_rect(topleft=(self.x, self.y))

        elif not self.pre_jump:
            self.currImage = self.original_image.copy()
            self.rect = self.currImage.get_rect(topleft=(self.x, self.y))
            self.animateDrive()

    def draw(self):
        SCREEN.blit(self.currImage, self.rect)
        if self.hit:
            # Create a red-tinted version of the sprite
            tinted = self.image.copy()
            tinted.fill((255, 0, 0, 128), special_flags=pygame.BLEND_RGBA_MULT)  # Apply red tint with alpha blend
            SCREEN.blit(tinted, self.rect.topleft)


class Obstacle:
    def __init__(self, x, y, w, h, image):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.vx = rd.randint(-10, -8)
        self.image = image
        self.image = pygame.transform.scale(self.image, (self.w, self.h))
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.to_delete = False
        self.has_hit = False

    def checkColision(self, other):
        if self.rect.colliderect(other.rect):
            return True
        return False

    def update(self):
        global STATE, SCORE
        if self.checkColision(PLAYER) and PLAYER.jumping == False:
            PLAYER.hit = True
            if self.has_hit == False and SCORE > 0:
                SCORE = SCORE - 1
            self.has_hit = True
        else:
            PLAYER.hit = False
            # STATE = "Menu"

        self.x = self.x + self.vx
        self.rect = self.image.get_rect(center=(self.x, self.y))
        if self.x < 0:
            self.to_delete = True
            if self.has_hit == False:
                SCORE = SCORE + 1

    def draw(self):
        SCREEN.blit(self.image, self.rect)


def ret():
    global RUNNING
    RUNNING = False


def start_button():
    global STATE
    STATE = "Game"
    setup()


def createObstacles():
    global OBSTACLES
    if len(OBSTACLES) == 0:
        OBSTACLES.append(
            Obstacle(rd.randint(850, 1000), FLOOR.y, 100, 100, OBSTACLE_IMAGES[rd.randint(0, len(OBSTACLE_IMAGES) - 1)])
        )


def createPlayer():
    global PLAYER
    playerH = 100
    PLAYER = Player(10, FLOOR.y - playerH, 100, playerH, IMAGES["Player"])


def loadImages():
    global IMAGES, OBSTACLE_IMAGES
    IMAGES = {
        "Obstacle": pygame.image.load("assets/wasteJump/obstacle2.png"),
        "Player": pygame.image.load("assets/wasteJump/player.png").convert_alpha(),
    }
    OBSTACLE_IMAGES = [
        pygame.image.load("assets/wasteJump/obstacle1.png"),
        pygame.image.load("assets/wasteJump/obstacle2.png"),
        pygame.image.load("assets/wasteJump/obstacle3.png"),
        pygame.image.load("assets/wasteJump/obstacle4.png"),
        pygame.image.load("assets/wasteJump/obstacle5.png"),
        pygame.image.load("assets/wasteJump/obstacle6.png"),
    ]


def createStreetStripes():
    global STREETSTRIPES
    STREETSTRIPES = []
    length = 100
    width = 30
    x = 0
    y = 500
    padding = 80
    spacing = length + padding
    for i in range(6):
        STREETSTRIPE = pygame.Rect(x + i * spacing, y, length, width)
        STREETSTRIPES.append(STREETSTRIPE)


def setup():
    global START_BUTTON, HOME_BUTTON, IMAGES, FLOOR, FLOORUPPER, OBSTACLES, PLAYER, SCORE, BACKGROUND, BACKGROUND_OFFSET
    BACKGROUND_OFFSET = 0
    SCORE = 0
    START_BUTTON = Button(400, 400, 100, 100, "assets/star.png", "assets/star.png", start_button)
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    BACKGROUND = pygame.image.load("assets/wasteJump/background.png")
    FLOOR = pygame.Rect(0, 500, 800, 100)
    FLOORUPPER = pygame.Rect(0, 450, 800, 100)
    loadImages()
    PLAYER = None
    createPlayer()
    OBSTACLES = []
    createObstacles()
    createStreetStripes()


def cleanUpWaste():
    global OBSTACLES
    OBSTACLES = [obj for obj in OBSTACLES if not obj.to_delete]


def updateStripes():
    global STREETSTRIPES
    for stripe in STREETSTRIPES:
        stripe.x = stripe.x + OBSTACLES[0].vx
        if stripe.x < -stripe.w:
            stripe.x = 800 + stripe.w + 80


def updateGame():
    global BACKGROUND_OFFSET
    BACKGROUND_OFFSET = BACKGROUND_OFFSET - 1
    if BACKGROUND_OFFSET <= -BACKGROUND.get_width():
        BACKGROUND_OFFSET = 0
    cleanUpWaste()
    for obstacle in OBSTACLES:
        obstacle.update()
    PLAYER.update()
    createObstacles()
    updateStripes()


def updateMenu():
    START_BUTTON.update(EVENTS)


def update():
    global RUNNING, HIGHSCORE
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    if STATE == "Menu":
        updateMenu()
    elif STATE == "Game":
        updateGame()


def drawFloor():
    pygame.draw.rect(SCREEN, (0, 0, 0), FLOOR)
    pygame.draw.rect(SCREEN, (0, 0, 0), FLOORUPPER)
    for stripe in STREETSTRIPES:
        pygame.draw.rect(SCREEN, (255, 255, 255), stripe)


def drawScore():
    global HIGHSCORE
    x = 600
    y = 10
    font = pygame.font.SysFont(None, 48)  # Choose your font and size
    text_surface = font.render(f"Score: {SCORE}", True, (255, 255, 255))  # White text
    SCREEN.blit(text_surface, (x, y))  # Draw at (600, 10)
    if SCORE > HIGHSCORE:
        HIGHSCORE = SCORE
    text_surface = font.render(f"Highscore: {HIGHSCORE}", True, (255, 255, 255))  # White text
    SCREEN.blit(text_surface, (x, y + 25))  # Draw at (600, 10)


def drawGame():
    SCREEN.blit(BACKGROUND, (BACKGROUND_OFFSET, -FLOOR.y))
    SCREEN.blit(BACKGROUND, (BACKGROUND_OFFSET + BACKGROUND.get_width(), -FLOOR.y))
    drawFloor()
    for obstacle in OBSTACLES:
        obstacle.draw()
    drawScore()
    PLAYER.draw()


def drawMenu():
    SCREEN.blit(BACKGROUND, (0, -FLOOR.y))
    START_BUTTON.draw(SCREEN)


def draw():
    SCREEN.fill((255, 255, 255))
    drawFloor()
    if STATE == "Menu":
        drawMenu()
    elif STATE == "Game":
        drawGame()

    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS, START_BUTTON, STATE, BACKGROUND_OFFSET, HIGHSCORE
    HIGHSCORE = 0
    SCREEN = screen
    CLOCK = clock
    STATE = "Menu"
    RUNNING = True
    setup()
    BACKGROUND_OFFSET = 0
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
