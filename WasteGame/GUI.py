# -*- coding: utf-8 -*-
"""
Created on Sun May 25 16:45:13 2025

@author: Lenovo Yoga
"""

import pygame
from helper import whiteToTransparent
import asyncio


class Button:
    def __init__(self, x, y, w, h, image_path, image_path_clicked, callback):
        self.x = x
        self.y = y
        self.image = pygame.transform.scale(pygame.image.load(image_path), (w, h))
        self.image = whiteToTransparent(self.image)
        self.image_clicked = pygame.transform.scale(pygame.image.load(image_path_clicked), (w, h))
        self.currImage = self.image.copy()
        self.rect = self.currImage.get_rect(topleft=(x, y))
        self.isPressed = False
        self.callback = callback
        self.is_hovered = False

    def update(self, events):
        mouse_pos = pygame.mouse.get_pos()
        self.is_hovered = self.rect.collidepoint(mouse_pos)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                self.currImage = self.image_clicked
                self.callback()  # Don't await here — just set a flag
            elif event.type == pygame.MOUSEBUTTONUP:
                self.currImage = self.image
            else:
                self.currImage = self.image
        self.rect.topleft = (self.x, self.y)

    def draw(self, screen):
        screen.blit(self.currImage, self.rect)
        if self.is_hovered:
            pygame.draw.rect(screen, (255, 255, 255), self.rect, 3)


class Toggle_Button:
    def __init__(self, x, y, w, h, image_path, image_path_clicked, callback):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.image = pygame.transform.scale(pygame.image.load(image_path), (w, h))
        self.image = whiteToTransparent(self.image)
        self.image_clicked = pygame.transform.scale(pygame.image.load(image_path_clicked), (w, h))
        self.currImage = self.image.copy()
        self.rect = self.currImage.get_rect(topleft=(x, y))
        self.isPressed = False
        self.callback = callback
        self.is_hovered = False
        self.color = None

    def update(self, events):
        mouse_pos = pygame.mouse.get_pos()
        self.is_hovered = self.rect.collidepoint(mouse_pos)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                self.currImage = self.image_clicked
                if self.color is None:
                    self.callback()  # Don't await here — just set a flag
                else:
                    self.callback(self)  # Don't await here — just set a flag
                self.isPressed = True
            elif event.type == pygame.MOUSEBUTTONUP:
                self.currImage = self.image
            else:
                self.currImage = self.image

    def draw(self, screen):
        if self.isPressed:
            self.currImage = self.image_clicked
        else:
            self.currImage = self.image
        screen.blit(self.currImage, self.rect)
        if self.color is not None and self.isPressed:
            pygame.draw.rect(screen, self.color, self.rect, 2)

class Slider:
    def __init__(self, x, y, width, height, min_val, max_val, start_val):
        self.rect = pygame.Rect(x, y, width, height)
        self.bar_rect = pygame.Rect(x, y + height//2 - 2, width, 4)  # slider bar
        self.min_val = min_val
        self.max_val = max_val
        self.value = start_val
        self.handle_radius = height // 2
        self.dragging = False

    def update(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()[0]

        # Check if handle is being dragged
        handle_x = self.get_handle_pos()
        handle_rect = pygame.Rect(handle_x - self.handle_radius, self.rect.y, 
                                  self.handle_radius*2, self.rect.height)
        if mouse_pressed and handle_rect.collidepoint(mouse_pos):
            self.dragging = True
        if not mouse_pressed:
            self.dragging = False

        # Update value while dragging
        if self.dragging:
            rel_x = mouse_pos[0] - self.rect.x
            rel_x = max(0, min(rel_x, self.rect.width))
            t = rel_x / self.rect.width
            self.value = self.min_val + t * (self.max_val - self.min_val)

    def get_handle_pos(self):
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        return self.rect.x + int(t * self.rect.width)

    def draw(self, screen):
        # Draw bar
        pygame.draw.rect(screen, pygame.Color("gray"), self.bar_rect)
        # Draw handle
        handle_x = self.get_handle_pos()
        handle_y = self.rect.y + self.rect.height // 2
        pygame.draw.circle(screen, pygame.Color("yellow"), (handle_x, handle_y), self.handle_radius)

