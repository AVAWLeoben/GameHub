# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import math  # At the top of your file
import random

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


class Ball:
    def __init__(self, x=None, y=None):
        if x is None or y is None:
            x, y = playfield_rect.centerx, playfield_rect.centery
        self.x = x
        self.y = y
        self.vx = 5
        self.vy = 1
        self.size = 20
        self.rect = pygame.Rect(self.x, self.y, self.size, self.size)
        self.rect.center = (self.x, self.y)

        self.trail = []

    def update(self):
        global PLAYER1_SCORE, PLAYER2_SCORE

        if self.rect.top <= playfield_rect.top or self.rect.bottom >= playfield_rect.bottom:
            self.vy = -self.vy

        if self.rect.right >= playfield_rect.right:
            self.x = playfield_rect.centerx
            self.y = playfield_rect.centery
            self.vx = -5
            self.vy = random.uniform(-2, 2)
            PLAYER1_SCORE += 1

        elif self.rect.left <= playfield_rect.left:
            self.x = playfield_rect.centerx
            self.y = playfield_rect.centery
            self.vx = 5
            self.vy = random.uniform(-2, 2)
            PLAYER2_SCORE += 1

        elif self.rect.right >= PLAYER1.rect.left and PLAYER1.rect.top <= self.rect.centery <= PLAYER1.rect.bottom:
            self.vx = -abs(self.vx)  # ensure leftward
            self.vy = random.uniform(-4, 4)

        elif self.rect.left <= PLAYER2.rect.right and PLAYER2.rect.top <= self.rect.centery <= PLAYER2.rect.bottom:
            self.vx = abs(self.vx)  # ensure rightward
            self.vy = random.uniform(-4, 4)

        # Move ball
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (self.x, self.y)

        self.trail.append([self.x, self.y, self.size])
        for puff in self.trail:
            puff[2] *= 0.90
        self.trail = [p for p in self.trail if p[2] > 1]

    def draw(self):
        for i, (tx, ty, radius) in enumerate(self.trail):
            # Wiggle effect
            wiggle_x = 4 * math.sin(FRAMECOUNT * 0.3 + i)
            wiggle_y = 3 * math.cos(FRAMECOUNT * 0.2 + i * 0.5)
            pos = (int(tx + wiggle_x), int(ty + wiggle_y))

            # Draw puff with black edge and red fill
            pygame.draw.circle(SCREEN, pygame.Color("black"), pos, int(radius + 2))

        for i, (tx, ty, radius) in enumerate(self.trail):
            # Wiggle effect
            wiggle_x = 4 * math.sin(FRAMECOUNT * 0.3 + i)
            wiggle_y = 3 * math.cos(FRAMECOUNT * 0.2 + i * 0.5)
            pos = (int(tx + wiggle_x), int(ty + wiggle_y))

            # Draw puff with black edge and red fill
            pygame.draw.circle(SCREEN, (255, 0, 0), pos, int(radius))

        # Draw the actual ball
        pygame.draw.circle(SCREEN, pygame.Color("white"), self.rect.center, self.size)


class Player1:
    def __init__(self):
        self.h = 150
        self.w = 30

        self.x = playfield_rect.right - self.w - 5
        self.y = playfield_rect.centery

        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.rect.center = (self.x, self.y)

    def update(self):
        finger_down = pygame.mouse.get_pressed()[0]
        if finger_down:
            finger_pos = pygame.mouse.get_pos()[1]
            self.y = finger_pos
            self.rect.center = (self.x, self.y)
        if self.rect.top < playfield_rect.top:
            self.rect.top = playfield_rect.top
            self.y = playfield_rect.centery
        elif self.rect.bottom > playfield_rect.bottom:
            self.rect.bottom = playfield_rect.bottom
            self.y = playfield_rect.centery

    def draw(self):
        pygame.draw.rect(SCREEN, pygame.Color("white"), self.rect)


class Player2:
    def __init__(self):
        self.h = 150
        self.w = 30

        self.x = playfield_rect.left + self.w + 5
        self.y = playfield_rect.centery

        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.rect.center = (self.x, self.y)

        self.speed = 4  # Max speed of paddle per frame

    def update(self):
        target_y = BALL.y
        dy = target_y - self.y

        # Clamp the movement speed
        if abs(dy) > self.speed:
            dy = self.speed * math.copysign(1, dy)

        self.y += dy
        self.rect.center = (self.x, self.y)

        # Keep paddle within playfield bounds
        if self.rect.top < playfield_rect.top:
            self.rect.top = playfield_rect.top
            self.y = self.rect.centery
        elif self.rect.bottom > playfield_rect.bottom:
            self.rect.bottom = playfield_rect.bottom
            self.y = self.rect.centery

    def draw(self):
        pygame.draw.rect(SCREEN, pygame.Color("white"), self.rect)


def ret():
    global RUNNING
    RUNNING = False


HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


def setup():
    global playfield_rect, playfield_draw_rect
    playfield_draw_rect = pygame.Rect(25, 130, 800 - 55, 440)
    playfield_rect = pygame.Rect(30, 135, 800 - 55 - 5 - 5, 440 - 5 - 5)
    global PLAYER1_SCORE, PLAYER2_SCORE
    PLAYER1_SCORE, PLAYER2_SCORE = 0, 0
    global PLAYER1
    PLAYER1 = Player1()
    global PLAYER2
    PLAYER2 = Player2()
    global BALL
    BALL = Ball()
    global FRAMECOUNT
    FRAMECOUNT = 0


def update():
    global RUNNING
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    PLAYER1.update()
    PLAYER2.update()
    BALL.update()


def draw_scores():
    # Draw the scores
    font = pygame.font.SysFont("Arial", 64, bold=True)
    score1_surf = font.render(str(PLAYER1_SCORE), True, pygame.Color("white"))
    score2_surf = font.render(str(PLAYER2_SCORE), True, pygame.Color("white"))

    # Position scores in top third of playfield
    spacing = 50
    center_x = playfield_rect.centerx
    top_y = playfield_rect.top + 30  # padding from top

    SCREEN.blit(score1_surf, (center_x - spacing - score1_surf.get_width(), top_y))
    SCREEN.blit(score2_surf, (center_x + spacing, top_y))


def draw_center_line():
    nLines = 17

    center_x = playfield_rect.centerx
    line_width = 4  # adjust as needed
    hLine = playfield_rect.height / nLines  # float division

    for i in range(nLines):
        if i % 2 == 0:
            y = playfield_rect.top + int(i * hLine)
            pygame.draw.rect(SCREEN, pygame.Color("white"), pygame.Rect(center_x - line_width // 2, y, line_width, int(hLine)))


def draw():
    SCREEN.fill((10, 10, 30))

    BALL.draw()
    PLAYER1.draw()
    PLAYER2.draw()
    pygame.draw.rect(SCREEN, pygame.Color("white"), playfield_draw_rect, 5)
    pygame.draw.rect(SCREEN, pygame.Color("red"), playfield_rect, 1)

    draw_center_line()
    draw_scores()

    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()
    global FRAMECOUNT
    FRAMECOUNT += 1


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
