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


class Piece:
    def __init__(self, x, y, w, h, image, id=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.image = pygame.transform.scale(image, (self.w, self.h))
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.selected = False
        self.offset_x = 0
        self.offset_y = 0
        self.id = id
        self.border_color = pygame.Color("black")
        self.correct = False

    def update(self):
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                for piece in PIECES:
                    piece.selected = False
                self.selected = True
                mouse_x, mouse_y = event.pos
                self.offset_x = self.rect.x - mouse_x
                self.offset_y = self.rect.y - mouse_y

            elif event.type == pygame.MOUSEBUTTONUP:
                for tile in TILES:
                    tile.correct = False
                    if tile.rect.collidepoint(event.pos) and self.selected:
                        self.x = tile.x
                        self.y = tile.y
                        self.rect.x = tile.rect.x
                        self.rect.y = tile.rect.y
                        if self.id == tile.id:
                            tile.correct = True
                            self.correct = True
                            print(tile.correct)
                        else:
                            tile.correct = False
                            print(tile.correct)
                            print(f"Tile:", {tile.id})
                            print(self.id)
                self.selected = False

        if self.selected:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.rect.x = mouse_x + self.offset_x
            self.rect.y = mouse_y + self.offset_y
            # Set self to last position in PIECES list, so the selected piece drawn last(on top)
            PIECES.remove(self)
            PIECES.append(self)

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if self.selected:
            pygame.draw.rect(SCREEN, self.border_color, self.rect, 2)
        if self.correct:
            pygame.draw.rect(SCREEN, (0, 255, 0), self.rect, 1)
            pygame.draw.circle(SCREEN, (0, 255, 0), self.rect.center, 5)
        pygame.draw.circle(SCREEN, (0, 255 * self.correct, 0), self.rect.center, 5)


RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


def ret():
    global RUNNING
    RUNNING = False


def loadImage():
    global IMAGE, CURR_IMAGE, BACKGROUND, CURR_IMAGE
    imagePaths = [
        "assets/wastePuzzle/image1.png",
        "assets/wastePuzzle/image2.png",
        "assets/wastePuzzle/image3.png",
        "assets/wastePuzzle/image4.png",
    ]
    path = rd.choice(imagePaths)
    IMAGE = pygame.image.load(path)
    IMAGE = pygame.transform.scale(IMAGE, (400, 400))

    CURR_IMAGE = pygame.transform.grayscale(IMAGE)
    BACKGROUND = pygame.image.load("assets/wastePuzzle/background.jpg")


class Balloon:
    images = [
        pygame.image.load("assets/wastePuzzle/balloon_black.png").convert_alpha(),
        pygame.image.load("assets/wastePuzzle/balloon_blue.png").convert_alpha(),
        pygame.image.load("assets/wastePuzzle/balloon_green.png").convert_alpha(),
        pygame.image.load("assets/wastePuzzle/balloon_red.png").convert_alpha(),
    ]
    popped_image = pygame.image.load("assets/wastePuzzle/balloon_popped.png").convert_alpha()

    def __init__(self):
        self.image = rd.choice(Balloon.images)
        scale_factor = rd.uniform(0.25, 0.75)  # Random scale between 50% and 150%
        self.image = pygame.transform.scale_by(self.image, scale_factor)
        self.image_popped = pygame.transform.scale(Balloon.popped_image, (self.image.get_width(), self.image.get_height()))
        self.rect = self.image.get_rect()
        self.start_x = rd.randint(0, SCREEN.get_width() - self.rect.width)
        self.y = SCREEN.get_height() + rd.randint(50, 200)  # Start offscreen (below)
        self.vy = rd.choice([-1, -2, -3])  # Move upwards
        self.angle_offset = rd.uniform(0, math.pi * 2)  # Randomize sine wave phase
        self.frequency = 0.02  # Controls wave width
        self.amplitude = rd.randint(10, 30)  # Wave height
        self.popped = False
        self.popped_at = None
        self.popped_time = 300

    def pop(self):
        self.popped = True
        self.vy = 0
        self.image = self.image_popped
        self.popped_at = pygame.time.get_ticks()

    def update(self):
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    self.pop()

        if self.popped:
            if pygame.time.get_ticks() > self.popped_at + self.popped_time:
                self.y = -1000

        self.y += self.vy
        self.x = self.start_x + math.sin(self.y * self.frequency + self.angle_offset) * self.amplitude
        self.rect.center = (self.x, self.y)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Tile:
    def __init__(self, x, y, w, h, image, id=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(x, y, w, h)
        self.image = image
        self.correct = False
        self.id = id

    def update(self):
        pass

    def draw_dashed_line(self, surface, color, start_pos, end_pos, dash_length=5, space_length=5):
        x1, y1 = start_pos
        x2, y2 = end_pos
        dx, dy = x2 - x1, y2 - y1
        distance = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)

        steps = int(distance // (dash_length + space_length))
        for i in range(steps):
            start_x = x1 + (dash_length + space_length) * i * math.cos(angle)
            start_y = y1 + (dash_length + space_length) * i * math.sin(angle)
            end_x = start_x + dash_length * math.cos(angle)
            end_y = start_y + dash_length * math.sin(angle)
            pygame.draw.line(surface, color, (start_x, start_y), (end_x, end_y), 1)

    def draw(self):
        col = (0, 255, 0) if self.correct else (0, 0, 0)
        pygame.draw.rect(SCREEN, col, self.rect, 1)
        for piece in PIECES:
            if piece.id == self.id and piece.selected:
                pygame.draw.circle(SCREEN, (0, 0, 0), self.rect.center, 4)
                self.draw_dashed_line(
                    SCREEN, pygame.Color("darkgray"), self.rect.center, piece.rect.center, dash_length=5, space_length=5
                )


def createSubimages():
    global PIECES, SUBIMAGES, WIDTH_PIECE, HEIGHT_PIECE, TILES
    width, height = 400, 400
    n = 4
    WIDTH_PIECE = width // n
    HEIGHT_PIECE = height // n
    SUBIMAGES = []
    TILES = []
    i = 0
    for x in range(n):
        for y in range(n):
            left = WIDTH_PIECE * x
            right = left + WIDTH_PIECE
            top = HEIGHT_PIECE * y
            bottom = top + HEIGHT_PIECE

            # Define crop area (x, y, width, height)
            crop_rect = pygame.Rect(left, top, right - left, bottom - top)
            # Create cropped image
            cropped_image = IMAGE.subsurface(crop_rect).copy()
            # Shows the image in image viewer
            SUBIMAGES.append((cropped_image, i))
            # Define Target Tile
            TILES.append(Tile(IM_POS[0] + left, IM_POS[1] + top, right - left, bottom - top, cropped_image, i))
            i = i + 1


def createPieces():
    global PIECES
    PIECES = []
    x = 100  # Start on the left
    i = 0  # Vertical index
    column = 0  # 0 = left, 1 = right

    for im, id in SUBIMAGES:
        if column <= 1:
            y = 25 + i * 105
        else:
            x = x + 100 + 5
            y = 500
        piece = Piece(x, y, WIDTH_PIECE, HEIGHT_PIECE, im, id)
        PIECES.append(piece)
        i += 1

        if y + 100 > 600:  # If the next piece would overflow the screen vertically
            i = 0
            column += 1
            x = 100 if column == 0 else 700
            if column == 2:
                x = 140


def setup():
    global IM_POS, PIECES
    IM_POS = (200, 50)
    loadImage()
    createSubimages()
    createPieces()
    rd.shuffle(PIECES)

    global BALLOONS
    BALLOONS = []


HOME_BUTTON = Button(10, 10, 75, 75, "assets/retBut.png", "assets/retBut_clicked.png", ret)
RESTART_BUTTON = Button(690, 10, 75, 75, "assets/retryBut.png", "assets/retryBut.png", setup)


def checkWin():
    for piece in PIECES:
        if piece.correct == False:
            return False
    return True


def update():
    global RUNNING
    HOME_BUTTON.update(EVENTS)
    RESTART_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    for tile in TILES:
        tile.update()
    for piece in PIECES:
        piece.update()

    for balloon in BALLOONS:
        balloon.update()
    if checkWin() and len(BALLOONS) == 0:
        for i in range(rd.randint(8, 14)):
            BALLOONS.append(Balloon())


def draw():
    SCREEN.fill((255, 255, 255))
    SCREEN.blit(BACKGROUND, (0, 0))
    SCREEN.blit(CURR_IMAGE, IM_POS)
    for piece in PIECES:
        piece.draw()
    for tile in TILES:
        tile.draw()
    for balloon in BALLOONS:
        balloon.draw()
    HOME_BUTTON.draw(SCREEN)
    RESTART_BUTTON.draw(SCREEN)
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
