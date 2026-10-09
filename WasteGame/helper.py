# -*- coding: utf-8 -*-
"""
Created on Sun May 25 23:55:06 2025

@author: Lenovo Yoga
"""

import pygame

pygame.init()
pygame.display.set_mode((1, 1))  # Required for convert_alpha()


def whiteToTransparent(img):
    image = img.convert_alpha()
    # return image
    width, height = image.get_size()
    for x in range(width):
        for y in range(height):
            if image.get_at((x, y))[0:3] == (255, 255, 255):
                image.set_at((x, y), (255, 255, 255, 0))  # Transparent
    return image


def drawFPS(SCREEN, CLOCK):
    font = pygame.font.SysFont(None, 24)
    fps = CLOCK.get_fps()
    text = font.render(f"FPS: {fps:.2f}", True, (0, 0, 0))  # Green text
    SCREEN.blit(text, (400, 10))
