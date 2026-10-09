# -*- coding: utf-8 -*-
"""
Created on Sun Nov  9 16:14:33 2025

@author: Admin
"""

import pygame
import asyncio
from GUI import Button


def ret():
    global RUNNING
    RUNNING = False

def setup(screen,clock):
    global SCREEN, CLOCK, RUNNING, FPS, DEBUG
    RUNNING = True
    SCREEN = screen
    CLOCK = clock
    FPS = 60
    DEBUG = False
    
    
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

def update():
    global EVENTS, DEBUG
    EVENTS = pygame.event.get()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            ret()           
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                DEBUG = not DEBUG
    
    
    HOME_BUTTON.update(EVENTS)
    
 
    
def draw():
    SCREEN.fill(pygame.Color("gray"))    
    
    
    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()

async def main(screen, clock):
    setup(screen,clock)
    while RUNNING:
        update()
        draw()
        CLOCK.tick(FPS)
        await asyncio.sleep(0)
    return

def debug_main():
    pygame.init()
    screen = pygame.display.set_mode((800,600))
    clock = pygame.Clock()
    setup(screen,clock)
    while RUNNING:
        update()
        draw()
        CLOCK.tick(FPS)
    pygame.quit()
    

if __name__ == "__main__":
    debug_main()