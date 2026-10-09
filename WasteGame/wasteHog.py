# -*- coding: utf-8 -*-
"""
Created on Sun Nov  9 16:14:33 2025

@author: Admin
"""

import pygame
import asyncio
from math import copysign 
from GUI import Button
import random as rd
import math

class Background:
    image = pygame.image.load("assets/wasteHog/BG.jpg")
    def __init__(self, screen, scroll_speed=2):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.scroll_speed = scroll_speed
        
        # Layers for parallax
        self.layers = []
        # Example: 3 layers with different colors and speeds
        self.layers.append(self.create_layer(color=(200, 220, 255), num_stars=50))
        self.layers.append(self.create_layer(color=(180, 200, 255), num_stars=30))
        self.layers.append(self.create_layer(color=(150, 180, 255), num_stars=20))
        
        # Track offset for each layer
        self.offsets = [0 for _ in self.layers]

    def create_layer(self, color, num_stars):
        """Create a list of stars or simple shapes for a layer"""
        stars = []
        for _ in range(num_stars):
            x = rd.randint(0, self.width)
            y = rd.randint(0, self.height)
            radius = rd.randint(1, 4)
            stars.append({'x': x, 'y': y, 'radius': radius, 'color': color})
        return stars

    def update(self):
        """Scroll each layer at its speed"""
        for i, layer in enumerate(self.layers):
            self.offsets[i] += self.scroll_speed * (i + 1) * 0.3  # parallax factor
            if self.offsets[i] > self.height:
                self.offsets[i] -= self.height  # loop

    def draw(self):
        SCREEN.blit(Background.image,(0,0))
        for i, layer in enumerate(self.layers):
            offset = self.offsets[i]
            for star in layer:
                # Draw star with offset
                y = (star['y'] + offset) % self.height
                pygame.draw.circle(self.screen, star['color'], (star['x'], int(y)), star['radius'])

class Santas_Bag:
    def __init__(self):
        self.image = pygame.image.load("assets/hungryHedgie/sack.png")
        self.x = SCREEN.get_width() - self.image.get_width()
        self.y = 0
        self.rect = self.image.get_rect(topleft=(self.x, self.y))
        self.counter = 0

        # Create a festive-looking font (standard Pygame font)
        # You can change the font type if you have a TTF for a Christmas style
        self.font = pygame.font.SysFont("comicsansms", 28, bold=True)  

    def update(self):
        pass

    def draw(self):
        if not DEBUG:
            SCREEN.blit(self.image, self.rect)
        else:
            pygame.draw.rect(SCREEN, pygame.Color("brown"), self.rect, 1)

        # Draw player points on top of the sack
        points_text = self.font.render(str(PLAYER.points), True, pygame.Color("red"))  # red for festive feel
        text_rect = points_text.get_rect(center=self.rect.center)  # center on the sack
        SCREEN.blit(points_text, text_rect)


class Present:
    image = pygame.image.load("assets/wasteHog/gift.png")
    image = pygame.transform.scale(image,(60,60))
    def __init__(self,owner):
        self.owner = owner
        self.x = owner.x
        self.start_y = owner.y
        self.y = self.start_y
        self.amplitude = rd.uniform(4,6)
        self.frequency = rd.uniform(0.002,0.006)
        
        
        self.image = Present.image
        self.w = 60
        self.h = 60
        self.rect = self.image.get_rect()
        self.rect.center = (self.x,self.y)
        
        self.collected = False
        self.target_x = SACK.rect.centerx
        self.target_y = SACK.rect.centery+5
        self.lerp_speed = 0.1
        
        self.to_delete = False
        self.worth = rd.randint(1,3)
        
    
    def update(self):        
        if self.rect.colliderect(PLAYER.rect) and not self.collected:
            self.collected = True
        
        if not self.collected:
            self.rect.bottom = self.owner.rect.top
            self.x,self.y = self.rect.center
        else:
            self.x = self.x + (self.target_x-self.x)*self.lerp_speed
            self.y = self.y + (self.target_y-self.y)*self.lerp_speed
            self.rect.center = (self.x, self.y)
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            
            if abs(dx) < 2 and abs(dy) < 2:
                self.to_delete = True
                PLAYER.points += self.worth
            
        self.y = self.y + self.amplitude * math.sin(pygame.time.get_ticks() * self.frequency)
        self.rect.centery = self.y
        
    def draw(self):
        if rd.randint(1, 99) > 98:
            self.image = pygame.transform.flip(self.image,True,False)
            
        SCREEN.blit(self.image,self.rect)
        
        
        

class Platform_Manager:
    def __init__(self):
        self.platforms = []
        ground = Platform(SCREEN.get_width()//2,SCREEN.get_height()-20,SCREEN.get_width()-50,20,ground=True)
        self.platforms.append(ground)
        
        ground2 = Platform(SCREEN.get_width()//2,SCREEN.get_height()-200,200,20,ground=True)
        self.platforms.append(ground2)
        
        ground3 = Platform(SCREEN.get_width()//2,SCREEN.get_height()-400,200,20,ground=True)
        self.platforms.append(ground3)
        
        ground4 = Platform(SCREEN.get_width()//2,SCREEN.get_height()-600,200,20,ground=True)
        self.platforms.append(ground4)
        
        self.presents = []
    
    def create_platforms(self):
        min_y = min(platform.rect.centery for platform in self.platforms)
        
        if min_y > 0:
            new_d_y = rd.uniform(75,200)
            new_p_w = rd.uniform(120,250)
            new_p_x = rd.uniform(new_p_w//2,SCREEN.get_width()-new_p_w//2)
            new_plat = Platform(new_p_x,min_y-new_d_y,new_p_w,20)
            self.platforms.append(new_plat)
            
            if rd.randint(0,99) > 60:
                new_present = Present(new_plat)
                self.presents.append(new_present)
        
        if DEBUG:
            print(f"Min Height of Platforms: {min_y}")
    
    def delete_platforms(self):
        self.presents = [p for p in self.presents if not p.to_delete]
            
    def update(self):
        self.create_platforms()
        self.delete_platforms()
        for platform in self.platforms:
            platform.update()
        for present in self.presents:
            present.update()
            
    def draw(self):
        for platform in self.platforms:
            platform.draw()
        for present in self.presents:
            present.draw()

class Camera:
    def __init__(self):
        self.scrollables = []
        self.center_y = 9*SCREEN.get_height()//10
        self.player_y_offset = self.center_y - PLAYER.rect.centery
        self.speed = 8
        self.smooth_factor = 0.05   # 0.1–0.2 is good
        self.scrolled = 0
        
    def update(self):
        self.scrollables.clear()
        self.scrollables.extend(PLATFORM_MANAGER.platforms)
        self.scrollables.append(PLAYER)
        if PLAYER.last_platform is not None:
            self.player_y_offset = self.center_y - PLAYER.last_platform.rect.centery
            
        if abs(self.player_y_offset) > 4:
            for scrollable in self.scrollables:
                dy = self.player_y_offset * self.smooth_factor
                #scrollable.rect.centery += copysign(self.speed,self.player_y_offset)
                scrollable.rect.centery += dy
                scrollable.y = scrollable.rect.centery
                self.scrolled += dy
    
    def draw(self):
        if DEBUG:
            pygame.draw.line(SCREEN,pygame.Color("green"),(0,self.center_y),(SCREEN.get_width(),self.center_y))
            pygame.draw.line(SCREEN,pygame.Color("green"),(PLAYER.rect.centerx,self.center_y),PLAYER.rect.center)
            print(f"Player_Offset: {self.player_y_offset}")
            print(f"Player Height: {self.scrolled}")


class Player:
    def __init__(self,x,y,w=80,h=60):
        self.image = pygame.image.load("assets/hungryHedgie/hedgie.png")
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.image = pygame.transform.scale(self.image,(w,h))
        self.y_scale = 1
        self.draw_image = pygame.transform.scale_by(self.image,(1,self.y_scale))
        self.rect = self.draw_image.get_rect(center=(x,y))
        self.vx = 0
        self.vx_max=6
        self.vy = 0
        self.a = 2
        self.drag = 0.80
        self.frame_counter_jump = 20
        
        self.on_ground = False
        self.platform = None
        self.last_platform = None
        self.dir = "right"
        self.flipped = False
        
        self.points = 0
        
    def update(self):
        # Gravity & drag
        self.vy += self.a
        if self.on_ground:
            self.vx = 0
    
        # Input
        mouse_pos = pygame.mouse.get_pos()
        clicked = pygame.mouse.get_pressed()[0]
        if clicked:
            if mouse_pos[0] < SCREEN.get_width() // 2:
                self.vx = -self.vx_max
                self.dir = "left"
            else:
                self.vx = self.vx_max
                self.dir = "right"
    
        # Store previous position for collision check
        prev_y = self.y
    
        # Move first
        self.x += self.vx
        if self.x > SCREEN.get_width():
            self.x = 0
        if self.x < 0:
            self.x = SCREEN.get_width()
        
        self.y += self.vy
        self.rect.center = (self.x, self.y)
    
        # Reset ground state
        self.on_ground = False
        self.platform = None
    
        # Check collision AFTER movement
        for platform in PLATFORM_MANAGER.platforms:
            # one-way platform: only collide if falling *onto* it
            if (self.vy >= 0 and
                prev_y + self.rect.height / 2 <= platform.rect.top and
                self.rect.colliderect(platform.rect)):
                
                # Land on top
                self.on_ground = True
                self.platform = platform
                self.last_platform = platform
                self.rect.bottom = platform.rect.top
                self.y = self.rect.centery
                self.vy = 0
                break
    
        # Squash/stretch animation
        if self.on_ground and self.frame_counter_jump > 0:
            self.frame_counter_jump -= 1
            self.y_scale -= 0.05
            self.draw_image = pygame.transform.scale_by(self.image, (1, self.y_scale))
            center = self.rect.center
            self.rect = self.draw_image.get_rect(center=center)
    
        # Auto jump after landing
        if self.on_ground and self.frame_counter_jump == 0:
            self.vy = -32
            self.on_ground = False
            self.frame_counter_jump = 10
            h_now = self.draw_image.get_height()
            self.y_scale = 1
            self.draw_image = self.image
            h_later = self.draw_image.get_height()
            center = self.rect.center
            self.rect = self.draw_image.get_rect(center=center)
            self.rect.centery -= h_later-h_now
            self.platform = None

                
    
    def draw(self):
        # Choose which image to draw based on direction
        if self.dir == "left":
            image_to_draw = pygame.transform.flip(self.draw_image, True, False)
        else:
            image_to_draw = self.draw_image
    
        SCREEN.blit(image_to_draw, self.rect)
    
        if DEBUG:
            pygame.draw.rect(SCREEN, pygame.Color("red"), self.rect, 1)
            print(self.dir)
        

class Platform:
    def __init__(self,x,y,w,h,ground=False):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(x,y,w,h)
        self.rect.center=(self.x,self.y)
        self.color = pygame.Color("blue")
        
        self.color = pygame.Color(rd.choice(list(pygame.colordict.THECOLORS)))
        self.outer_color = pygame.Color("black")
        self.to_delete = False
        self.ground = ground
        
    def update(self):
        self.to_delete = self.rect.top > SCREEN.get_height() and not self.ground
    
    def draw(self):        
        pygame.draw.rect(SCREEN,self.color,self.rect,border_radius=self.h//2)
        pygame.draw.rect(SCREEN,self.outer_color,self.rect,5,border_radius=self.h//2)
        if DEBUG:
            if self == PLAYER.platform:
                pygame.draw.rect(SCREEN,pygame.Color("green"),self.rect,1)
            else:
                pygame.draw.rect(SCREEN,pygame.Color("yellow"),self.rect,1)

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
    
    global PLATFORM_MANAGER
    PLATFORM_MANAGER = Platform_Manager()
    
    global PLAYER
    PLAYER = Player(40,300)
    
    global CAMERA
    CAMERA = Camera()
    
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    global BACKGROUND
    BACKGROUND = Background(SCREEN, scroll_speed=2)
    
    global SACK
    SACK = Santas_Bag()

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
    
    
    PLATFORM_MANAGER.update()        
    PLAYER.update()
    
    CAMERA.update()
    BACKGROUND.update()
    SACK.update()
    
    
def draw():
    SCREEN.fill(pygame.Color("gray"))
    BACKGROUND.draw()
    
    CAMERA.draw()
    
    PLATFORM_MANAGER.draw()
    
    PLAYER.draw()
    
    HOME_BUTTON.draw(SCREEN)
    SACK.draw()
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