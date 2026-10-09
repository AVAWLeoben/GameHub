# -*- coding: utf-8 -*-
"""
Created on Sun Nov  9 16:14:33 2025

@author: Admin
"""

import pygame
import asyncio
import math
from GUI import Button
import random as rd

def ret():
    global RUNNING
    RUNNING = False

class Sack:
    image = pygame.image.load("assets/hungryHedgie/sack.png")
    image = pygame.transform.scale(image, (50, 50))
    
    def __init__(self):
        self.image = Sack.image
        self.rect = self.image.get_rect()
        self.rect.bottomright = BURROW.rect.bottomright
        self.animating_berries = []  # berries flying into sack
    
    def spawn_berry_animation(self, start_pos, count=1):
        """Spawn berry(s) flying from start_pos into the sack."""
        for _ in range(count):
            self.animating_berries.append({
                'pos': list(start_pos),
                'target': list(self.rect.center),
                'progress': 0.0,  # 0.0 -> 1.0 lerp progress
                'scale': 1.0
            })
    
    def update(self):
        # Animate berries flying into the sack
        remove_list = []
        for berry in self.animating_berries:
            # Lerp towards target
            berry['progress'] += 0.05  # speed of lerp
            t = min(1, berry['progress'])
            berry['pos'][0] = berry['pos'][0] + (berry['target'][0] - berry['pos'][0]) * t
            berry['pos'][1] = berry['pos'][1] + (berry['target'][1] - berry['pos'][1]) * t
            
            # Shrink as it approaches for a visual effect
            berry['scale'] = max(0.2, 1 - t)
            
            # When it reaches close enough, count it
            if t >= 1.0 or (abs(berry['pos'][0] - berry['target'][0]) < 2 and abs(berry['pos'][1] - berry['target'][1]) < 2):
                HEDGIE.carrying -= 1
                remove_list.append(berry)
        
        # Remove counted berries
        for berry in remove_list:
            self.animating_berries.remove(berry)
    
    def draw(self):
        SCREEN.blit(self.image, self.rect)
        
        # Draw flying berries
        for berry in self.animating_berries:
            size = int(Berry.image.get_width() * berry['scale'])
            img = pygame.transform.scale(Berry.image, (size, size))
            draw_rect = img.get_rect(center=berry['pos'])
            SCREEN.blit(img, draw_rect)

class Burrow:
    image = pygame.image.load("assets/hungryHedgie/burrow.png")
    image = pygame.transform.scale(image, (250, 200))
    
    def __init__(self):
        self.image = Burrow.image
        self.rect = self.image.get_rect()
        self.rect.topright = (SCREEN.get_width(),0)
    
    def update(self):
        HEDGIE.in_burrow = self.rect.contains(HEDGIE.rect)
        
        if HEDGIE.in_burrow:
            HEDGIE.sight_distance = self.rect.width
        else:
            if not TORCH.collected:
                HEDGIE.sight_distance = 150
                
        # SPAWN berries only ONCE when entering
        if HEDGIE.in_burrow and not HEDGIE.sent_to_sack and HEDGIE.carrying > 0:
            SACK.spawn_berry_animation(HEDGIE.rect.center, count=HEDGIE.carrying)
            HEDGIE.carrying = 0
            HEDGIE.sent_to_sack = True
            HEDGIE.carrying = 0
    
        # Reset flag when leaving
        if not HEDGIE.in_burrow:
            HEDGIE.sent_to_sack = False
    
    def draw(self):
        SCREEN.blit(self.image,self.rect)
        if HEDGIE.in_burrow:
            pygame.draw.rect(SCREEN,pygame.Color("gold"),self.rect,2)

class Forest:
    image = pygame.image.load("assets/hungryHedgie/tree.png")
    image = pygame.transform.scale(image, (90, 120))

    def __init__(self, count=25):
        """Create N random tree positions."""
        self.trees = []
        valid_rect = SCREEN.get_rect().scale_by(0.9, 0.9)

        for _ in range(count):
            x = rd.randint(valid_rect.left, valid_rect.right)
            y = rd.randint(valid_rect.top, valid_rect.bottom)
            rect = Forest.image.get_rect(center=(x, y))
            self.trees.append(rect)
            
        self.trees = [t for t in self.trees if not BURROW.rect.colliderect(t)]

    def draw(self):
        for rect in self.trees:
            SCREEN.blit(Forest.image, rect)


class Enemy:
    image = pygame.image.load("assets/hungryHedgie/enemy.png")
    image = pygame.transform.scale(image, (70, 90))

    def __init__(self):
        # Keep enemy inside spawnable area
        self.valid_rect = SCREEN.get_rect().scale_by(0.4, 0.8)

        # Random spawn position
        self.x = rd.randint(self.valid_rect.left, self.valid_rect.right)
        self.y = rd.randint(self.valid_rect.top,  self.valid_rect.bottom)

        # Setup sprite rect
        self.image = Enemy.image
        self.rect = self.image.get_rect()
        self.rect.center = (self.x, self.y)

        # Movement
        self.speed = 1.0
        self.dir_x = rd.uniform(-1, 1)
        self.dir_y = rd.uniform(-1, 1)
        self.change_dir_timer = rd.randint(30, 120)   # change direction after some frames

        # Behavior
        self.hit_cooldown = 60   # 1 second cooldown (60 FPS)
        
        self.last_hit_timer = 0

    def randomize_direction(self):
        angle = rd.uniform(0, math.pi * 2)
        self.dir_x = math.cos(angle)
        self.dir_y = math.sin(angle)
        self.change_dir_timer = rd.randint(30, 120)
    
    def aim_for_player(self,dx,dy):        
        # Calculate angle toward player
        angle = math.atan2(dy, dx)
    
        # Convert angle to movement direction
        self.dir_x = math.cos(angle)
        if HEDGIE.in_burrow:
            self.dir_x = -1*self.dir_x
        self.dir_y = math.sin(angle)
    
    def update(self):
        # aimed at player
        dx = HEDGIE.rect.centerx - self.rect.centerx
        dy = HEDGIE.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist < HEDGIE.sight_distance:
            self.aim_for_player(dx, dy)
            self.speed = self.speed*1.01
        else:
            # random wandering
            self.speed = 1.0
            self.change_dir_timer -= 1
            if self.change_dir_timer <= 0:
                self.randomize_direction()

        # move
        self.x += self.dir_x * self.speed
        self.y += self.dir_y * self.speed
        self.rect.center = (self.x, self.y)

        # keep inside allowed area
        if not self.valid_rect.contains(self.rect):
            self.randomize_direction()

        # collision with hedgie
        if self.rect.colliderect(HEDGIE.rect) and self.hit_cooldown <= 0:
            print("⚠ Hedgie got hit!")
            self.do_bad_thing()
            self.hit_cooldown = 60

        if self.hit_cooldown > 0:
            self.hit_cooldown -= 1

        # random sprite flip
        if rd.randint(0, 100) > 95:
            self.image = pygame.transform.flip(self.image, True, False)

    def do_bad_thing(self):
        """Called when enemy hits the hedgehog."""
        HEDGIE.carrying = 0
        
        HEDGIE.x = BURROW.rect.centerx
        HEDGIE.y = BURROW.rect.centery
        HEDGIE.rect.center = (HEDGIE.x, HEDGIE.y)
            
        self.last_hit_timer = 30

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if self.last_hit_timer > 0:
            self.last_hit_timer -= 1
            SCREEN.fill(pygame.Color("red"))


class Torch:
    image = pygame.image.load("assets/hungryHedgie/torch.png")
    image = pygame.transform.scale(image,(12,30))
    
    def __init__(self):
        self.image = Torch.image
        self.valid_rect = SCREEN.get_rect().scale_by(0.8,0.8)
        self.x = rd.randint(self.valid_rect.left, self.valid_rect.right)
        self.y = rd.randint(self.valid_rect.top, self.valid_rect.bottom)
        self.rect = self.image.get_rect()
        self.rect.center = (self.x,self.y)
        self.collected = False
        self.duration = 180 # FPS = 60 -> 120 / FPS = dur in seconds
        
    
    def respawn(self):
        self.image = Torch.image
        self.x = rd.randint(self.valid_rect.left, self.valid_rect.right)
        self.y = rd.randint(self.valid_rect.top, self.valid_rect.bottom)
        self.rect = self.image.get_rect()
        self.rect.center = (self.x,self.y)
        self.collected = False
        self.duration = 120 # FPS = 60 -> 120 / FPS = dur in seconds
        HEDGIE.sight_distance -= 100
        
    def update(self):
        if self.rect.colliderect(HEDGIE.rect) and not self.collected:
            self.collected = True
            HEDGIE.sight_distance += 100
        
        if self.collected:            
            self.rect.center = HEDGIE.rect.center
            self.rect.bottom = HEDGIE.rect.bottom
            self.x = self.rect.centerx
            self.y = self.rect.centery
            self.duration -= 1
        
        if self.duration <= 0:
            self.respawn()
            
        if rd.randint(0,99) > 90:
            self.image = pygame.transform.flip(self.image,True,False)
            
    def draw(self):
        if self.collected:
            draw_image = pygame.transform.scale(self.image,(24,50))
            draw_rect = draw_image.get_rect(center=(self.x,self.y))
            draw_rect.bottom = HEDGIE.rect.bottom
            SCREEN.blit(draw_image,draw_rect)
        else:
            draw_image = self.image
            SCREEN.blit(draw_image,self.rect)
class GUI:
    """Display the hedgehog's carried berries as a number with an icon."""
    
    def __init__(self):
        self.berry_image = pygame.transform.scale(Berry.image, (25, 25))
        self.pos = (700, 10)  # top-right corner
        self.font = pygame.font.SysFont(None, 30)  # default font, size 30
        self.color = (255, 255, 255)  # white text
    
    def draw(self):
        # Draw berry icon
        SCREEN.blit(self.berry_image, self.pos)
        
        # Draw number next to the berry
        count_text = self.font.render(str(HEDGIE.carrying), True, self.color)
        text_x = self.pos[0] + self.berry_image.get_width() + 5  # 5 px margin
        text_y = self.pos[1] + (self.berry_image.get_height() - count_text.get_height()) // 2
        SCREEN.blit(count_text, (text_x, text_y))
    
    
class Berry:
    image = pygame.image.load("assets/hungryHedgie/berry.png")
    image = pygame.transform.scale(image,(25,25))
    
    def __init__(self):
        self.image = Berry.image
        self.valid_rect = SCREEN.get_rect().scale_by(0.8,0.8)
        self.x = rd.randint(self.valid_rect.left, self.valid_rect.right)
        self.y = rd.randint(self.valid_rect.top, self.valid_rect.bottom)
        self.rect = self.image.get_rect()
        self.rect.center = (self.x,self.y)
        self.eaten = False
    
    def respawn(self):
        self.x = rd.randint(self.valid_rect.left, self.valid_rect.right)
        self.y = rd.randint(self.valid_rect.top, self.valid_rect.bottom)
        self.rect = self.image.get_rect()
        self.rect.center = (self.x,self.y)
        self.eaten = False
        
    def update(self):
        if self.rect.colliderect(HEDGIE.rect) and not self.eaten:
            self.eaten = True
            HEDGIE.carrying = max(1,HEDGIE.carrying*2)
            self.respawn()            
            print("eeaten")
            
    def draw(self):
        SCREEN.blit(self.image,self.rect)

class Hedgie:
    image = pygame.image.load("assets/hungryHedgie/hedgie.png")
    image = pygame.transform.scale(image,(50,40))
    def __init__(self):
        self.image = Hedgie.image
        self.rect = self.image.get_rect()
        self.x = 675
        self.y = 200
        self.rect.center = (self.x,self.y)
        self.target_x = self.x
        self.target_y = self.y
        self.draw_image = pygame.transform.flip(self.image,self.target_x < self.x,False)
        self.sight_distance = 150
        self.carrying = 0
        self.in_burrow = False
        self.sent_to_sack = False
        self.in_sack = 0         # deposited berries
        
    def update(self):
        if MOUSE_PRESSED:
            self.target_x, self.target_y = MOUSE_POS
            self.x = self.x + (self.target_x - self.x)*0.05
            self.y = self.y + (self.target_y - self.y)*0.05
            self.rect.center = (self.x,self.y)
        else:
            self.target_x, self.target_y = self.x,self.y
            
        self.carrying = max(0,self.carrying)
    
    def draw(self):        
        if MOUSE_PRESSED:
            self.draw_image = pygame.transform.flip(self.image,self.target_x < self.x,False)
        SCREEN.blit(self.draw_image,self.rect)
        

def setup(screen,clock):
    global SCREEN, CLOCK, RUNNING, FPS, DEBUG
    RUNNING = True
    SCREEN = screen
    CLOCK = clock
    FPS = 60
    DEBUG = False
    global BG 
    BG = pygame.image.load("assets/hungryHedgie/grass.png")
    
    global BAD_HEDGIE
    BAD_HEDGIE = Enemy()
    
    global HEDGIE
    HEDGIE = Hedgie()
     
    global BERRIES
    n_berries = 4
    BERRIES = []
    for _ in range(n_berries):
        BERRIES.append(Berry())
    global TORCH
    TORCH = Torch()
    
    
    
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    global GUI_DISPLAY
    GUI_DISPLAY = GUI()
    
    global BURROW
    BURROW = Burrow()
    global SACK
    SACK = Sack()
    
    global FOREST
    FOREST = Forest(count=30)

def update():
    global EVENTS, DEBUG
    EVENTS = pygame.event.get()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            ret()           
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                DEBUG = not DEBUG
    global MOUSE_POS
    MOUSE_POS = pygame.mouse.get_pos()
    
    global MOUSE_PRESSED
    MOUSE_PRESSED = pygame.mouse.get_pressed()[0]
        
    HOME_BUTTON.update(EVENTS)
       
    HEDGIE.update()
    for BERRY in BERRIES:
        BERRY.update()
    TORCH.update()
    BURROW.update()
    BAD_HEDGIE.update()
    SACK.update()

def draw_fog():
    # Create a temporary fog surface
    fog = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
    fog.fill((0, 0, 0, 250))  # base fog opacity

    # Create gradient circle
    gradient_size = HEDGIE.sight_distance * 2
    gradient = pygame.Surface((gradient_size, gradient_size), pygame.SRCALPHA)

    center = HEDGIE.sight_distance
    for r in range(HEDGIE.sight_distance, 0, -1):
        alpha = int(255 * (1 - r / HEDGIE.sight_distance))  # transparent near hedgehog, opaque far
        pygame.draw.circle(gradient, (0, 0, 0, alpha), (center, center), r)

    # Calculate position
    x, y = HEDGIE.rect.center
    gradient_pos = (x - HEDGIE.sight_distance, y - HEDGIE.sight_distance)

    # Blit gradient onto fog
    fog.blit(gradient, gradient_pos, special_flags=pygame.BLEND_RGBA_SUB)

    # Blit fog onto screen
    SCREEN.blit(fog, (0, 0))
    
def draw():
    SCREEN.fill(pygame.Color("gray"))    
    SCREEN.blit(BG,(0,0))
    
    
    
    BAD_HEDGIE.draw()
    HEDGIE.draw()
    
    
    
    FOREST.draw()
    TORCH.draw()
    for BERRY in BERRIES:
        BERRY.draw()
    BURROW.draw()
    SACK.draw()
    draw_fog()
        
    HOME_BUTTON.draw(SCREEN)
    GUI_DISPLAY.draw()
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