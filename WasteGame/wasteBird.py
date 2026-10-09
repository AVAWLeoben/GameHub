# -*- coding: utf-8 -*-
"""
Created on Sun Nov  9 16:14:33 2025

@author: Admin
"""

import pygame
import asyncio
from GUI import Button
import time
import random as rd
import math

def scale_by(rect, scale_x, scale_y):
    # Compute new width/height as integers
    new_w = int(rect.width * scale_x)
    new_h = int(rect.height * scale_y)    
    # Copy the original rect
    new_rect = rect.copy()    
    # Update size
    new_rect.width = new_w
    new_rect.height = new_h    
    # Keep center the same
    new_rect.center = rect.center    
    return new_rect


class Coin:
    IMAGES = [
        pygame.image.load("assets/wastePilot/coin/star coin rotate 1.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 2.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 3.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 4.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 5.png"),
    ]

    def __init__(self, x=900, y=300):
        self.x = x
        self.y = y
        self.vx = PLAYER.vx
        
        self.image = self.IMAGES[0]
        self.draw_image = self.image.copy()
        self.rect = self.draw_image.get_rect()
        self.frame_counter = 0  # frame counter to track animation progress
        self.bob_phase = rd.uniform(0, 2 * math.pi)  # random phase between 0 and 2π
        self.collected = False
        
        
    def update(self):
        self.x -= self.vx
        self.frame_counter += 1

        # Number of frames per image (change this to speed up/down animation)
        frames_per_image = 5

        # Calculate current image index based on frame_counter
        current_image_index = (self.frame_counter // frames_per_image) % len(self.IMAGES)
        self.image = self.IMAGES[current_image_index]
        self.rect = self.image.get_rect(center=(self.x, self.y))
        
        if self.rect.colliderect(PLAYER.rect) and not self.collected:
            PLAYER.score += 10
            self.collected = True
            self.x = -100

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if DEBUG:
            pygame.draw.rect(SCREEN,pygame.Color("yellow"),self.rect,1)
        

class Menu:
    def __init__(self, w, h, title_text="Game Menu", prompt="Click to Start"):
        self.w = w
        self.h = h
        self.title_text = title_text
        self.prompt = prompt
        self.buttons = []

        # Example scores
        self.todays_high_score = rd.randint(1000, 10000)
        self.last_highscore = PLAYER.score  # replace with PLAYER.score if defined

        # Preload fonts
        self.title_font = pygame.font.SysFont("arialblack", 60)
        self.text_font = pygame.font.SysFont("arial", 30)
        self.prompt_font = pygame.font.SysFont("arial", 25)

        # Background colors
        self.bg_color = (25, 25, 40)
        self.window_color = (40, 40, 70)
        self.border_color = (200, 200, 255)
        self.shadow_color = (10, 10, 20)

        # Get screen rect
        self.screen_rect = SCREEN.get_rect()

    def restart_game(self):
        global PLAYER
        PLAYER = Player()
        
        global BACKGROUNDS
        BACKGROUNDS = []
        BG1 = Background()
        BG2 = Background(x=SCREEN.get_width())
        BACKGROUNDS.append(BG1)
        BACKGROUNDS.append(BG2)
        
        global ENTITY_MANAGER
        ENTITY_MANAGER = EntityManager()

    def update(self):
        global STATE        
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                STATE = "Game"
                self.restart_game()

    def draw(self):
        # Draw darkened background
        BACKGROUNDS[0].draw()

        # Centered window
        win_rect = pygame.Rect(0, 0, self.w, self.h)
        win_rect.center = self.screen_rect.center

        # Shadow
        shadow_rect = win_rect.copy()
        shadow_rect.move_ip(5, 5)
        pygame.draw.rect(SCREEN, self.shadow_color, shadow_rect, border_radius=20)

        # Main window
        pygame.draw.rect(SCREEN, self.window_color, win_rect, border_radius=20)
        pygame.draw.rect(SCREEN, self.border_color, win_rect, 3, border_radius=20)

        # Title
        title_surf = self.title_font.render(self.title_text, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.screen_rect.centerx, win_rect.top + 70))
        SCREEN.blit(title_surf, title_rect)

        # High scores
        score_text = self.text_font.render(f"High Score: {self.todays_high_score}", True, (200, 200, 200))
        score_rect = score_text.get_rect(center=(self.screen_rect.centerx, win_rect.centery - 40))
        SCREEN.blit(score_text, score_rect)

        last_text = self.text_font.render(f"Last Score: {self.last_highscore}", True, (200, 200, 200))
        last_rect = last_text.get_rect(center=(self.screen_rect.centerx, win_rect.centery))
        SCREEN.blit(last_text, last_rect)

        # Prompt
        prompt_surf = self.prompt_font.render(self.prompt, True, (180, 220, 255))
        prompt_rect = prompt_surf.get_rect(center=(self.screen_rect.centerx, win_rect.bottom - 60))
        SCREEN.blit(prompt_surf, prompt_rect)

class Pipe:
    images_low = pygame.image.load("assets/wasteBird/pipe.png")
    image_up = pygame.transform.flip(images_low,False,True)
    def __init__(self):
        self.x = 1000
        self.y = rd.randint(200,400)       
        self.image_low = Pipe.images_low
        self.image_up = Pipe.image_up
        self.w = self.images_low.get_width()
        self.savespace = rd.randint(100, 300)
        self.save_rect = pygame.Rect(self.x,self.y,self.w,self.savespace)
        self.save_rect.center = (self.x,self.y)
        self.rect = self.save_rect
        
        self.upper_rect = pygame.Rect(self.x,0,self.w,self.save_rect.top)
        self.lower_rect = pygame.Rect(self.x,self.save_rect.bottom,self.w,SCREEN.get_height()-self.save_rect.bottom)
        
        self.counted = False
       
        self.vx = -PLAYER.vx
        
    def update(self):
        self.x += self.vx
        self.save_rect.center = (self.x,self.y)
        self.rect = self.save_rect
        
        self.upper_rect.left = self.rect.left
        self.lower_rect.left = self.rect.left
        
        if self.upper_rect.colliderect(PLAYER.rect) or self.lower_rect.colliderect(PLAYER.rect) and PLAYER.alive:
            PLAYER.alive = False
            PLAYER.vy = PLAYER.max_v_up
        elif self.save_rect.right < PLAYER.hitbox.left and PLAYER.alive and not self.counted:
            PLAYER.score += 5
            self.counted = True
        
            print(f"PIPE:{self.x}")
        
    def draw(self):
        SCREEN.blit(self.image_up,self.upper_rect.move(0, self.upper_rect.bottom-self.image_up.get_height()))
        SCREEN.blit(self.image_low,self.lower_rect)
        if DEBUG:
            pygame.draw.rect(SCREEN,pygame.Color("green"),self.save_rect,1)
            pygame.draw.rect(SCREEN,pygame.Color("red"),self.upper_rect,1)
            pygame.draw.rect(SCREEN,pygame.Color("red"),self.lower_rect,1)

class Smoke():
    def __init__(self, x, y, radius=30):
        self.radius = radius
        self.x = x
        self.y = y           # Use exact center of BulletBill
        self.start_x = x
        self.start_y = y     # baseline for sine wave
        self.amplitude = 5   # small vertical wiggle
        self.frequency = 0.1

    def update(self):
        self.radius -= 1
        # small sine-wave wiggle for natural smoke
        self.y = self.start_y + self.amplitude * math.sin(self.frequency * self.x)

    def draw_black(self):        
        pygame.draw.circle(SCREEN, pygame.Color("grey"), (int(self.x), int(self.y)), int(self.radius+1))
    def draw_gray(self):
        pygame.draw.circle(SCREEN, pygame.Color("black"), (int(self.x), int(self.y)), int(self.radius))
    def draw_red(self):
        pygame.draw.circle(SCREEN, pygame.Color("red"), (int(self.x), int(self.y)), int(self.radius/3))

    
        
        
class BulletBill():
    image = pygame.image.load("assets/wasteBird/bullet_bill.png")
    def __init__(self,x,y):
        self.x = x
        self.y = y
        self.start_x = x
        self.start_y = y
        self.vx = -PLAYER.vx*rd.uniform(1.5, 3)
        self.amplitude = 0
        self.frequency = 0
        if rd.randint(0,100) > 80:
            self.amplitude = rd.randint(20,40)
            self.frequency = rd.uniform(0.005,0.02)
        
        self.image = BulletBill.image
        self.image = pygame.transform.scale_by(self.image,rd.uniform(0.1,0.2))
        
        self.rect = self.image.get_rect(topleft=(self.x,self.y))
        self.hitbox_x_scale = 0.9
        self.hitbox_y_scale = 0.9
        self.hitbox = scale_by(self.rect,self.hitbox_x_scale,self.hitbox_y_scale)
        self.counted = False
        self.smokes = []
        
    def update(self):
        self.x = self.x+self.vx
        if self.amplitude > 0:
            self.y = self.start_y + self.amplitude * math.sin(self.frequency*self.x)
        else:
            self.y = self.start_y
            
        self.rect.center = (self.x,self.y)
        self.hitbox = scale_by(self.rect,self.hitbox_x_scale,self.hitbox_y_scale)
        
        self.smokes.append(Smoke(self.hitbox.right,self.hitbox.centery,self.image.get_height()//2))
        self.smokes = [smoke for smoke in self.smokes if smoke.radius > 1]
        
        for smoke in self.smokes:
            smoke.update()
        
        if self.hitbox.colliderect(PLAYER.rect) and PLAYER.alive:
            PLAYER.alive = False
            PLAYER.vy = PLAYER.max_v_up
        elif self.hitbox.right < PLAYER.hitbox.left and PLAYER.alive and not self.counted:
            PLAYER.score += 5
            self.counted = True
        
    def draw(self):
        for smoke in self.smokes:
            smoke.draw_black()
        for smoke in self.smokes:
            smoke.draw_gray()
        # for smoke in self.smokes:
        #     smoke.draw_red()    
            
        SCREEN.blit(self.image,self.rect)
        if DEBUG:
            pygame.draw.rect(SCREEN,pygame.Color("red"),self.hitbox,1)

        
        
class EntityManager():
    def __init__(self):
        self.enemy_spacing = 300
        self.max_enemies = rd.randint(1,100)
        self.enemies = []
        self.max_pipes = rd.randint(1,100)
        self.pipe_spacing = 200
        self.pipes = []
        
        self.max_coins = 1
        self.coin_spacing = self.pipe_spacing
        self.coins = []
        
    def get_max_pipe_x(self):
        max_x = 0
        for pipe in self.pipes:
            x = pipe.rect.right
            if x > max_x:
                max_x = x    
        return max_x < SCREEN.get_width()-self.pipe_spacing
    
    def get_max_bullet_bill_x(self):
        max_x = 0
        for enemy in self.enemies:
            x = enemy.rect.right
            if x > max_x:
                max_x = x    
        return max_x < SCREEN.get_width()-self.enemy_spacing
    
    def get_max_coin_x(self):
        max_x = 0
        for coin in self.coins:
            x = coin.rect.right
            if x > max_x:
                max_x = x    
        return max_x < SCREEN.get_width()-self.coin_spacing
        
    def update(self):
        self.enemies = [enemy for enemy in self.enemies if enemy.rect.x > -enemy.rect.width]
                
        if len(self.enemies) < self.max_enemies and self.get_max_bullet_bill_x():
            if rd.randint(0, 100) > 40:
                new_enemy = BulletBill(SCREEN.get_width()+30, rd.randint(40, SCREEN.get_height()))
                self.enemies.append(new_enemy)
            
        for enemy in self.enemies:
            enemy.update()
            
        self.pipes = [pipe for pipe in self.pipes if pipe.rect.x > -pipe.rect.width]
        if len(self.pipes) < self.max_pipes and self.get_max_pipe_x():
            new_pipe = Pipe()
            self.pipes.append(new_pipe)
             
        for pipe in self.pipes:
            pipe.update()    
            
        self.coins = [coin for coin in self.coins if coin.rect.x > -coin.rect.width]
        if len(self.coins) < self.max_coins and self.get_max_coin_x() and rd.randint(0,100) > 50:
            new_coin = Coin(*self.pipes[-1].save_rect.center)
            self.coins.append(new_coin)
        
             
        for coin in self.coins:
            coin.update()    
        
    def draw(self):
        for coin in self.coins:
            coin.draw()
        
        for pipe in self.pipes:
            pipe.draw()
        
        for enemy in self.enemies:
            enemy.draw()
            

class Background():
    def __init__(self,x=0,y=0):
        self.vx = PLAYER.vx/10
        self.x = x
        self.y = y
        self.image = pygame.image.load("assets/wasteBird/BG.png")
        self.image = pygame.transform.scale(self.image,(800,600))
        
    def update(self):
        self.x = self.x-self.vx
        if self.x <= -SCREEN.get_width():
            self.x = SCREEN.get_width()
            
    def draw(self):
        SCREEN.blit(self.image,(self.x,self.y))

class Player():    
    def __init__(self):
        self.x = 10
        self.y = SCREEN.get_height()//2
        self.w = 50
        self.h = 50
        self.angle = 0
        
        self.gravity = 2
        self.flap = -16
        self.vx = 4
        self.vy = 0
        self.max_v_up = -32
        self.max_v_down = 8
        
        self.flapping = False
        
        self.debounce = 0.1
        self.last_flap = 0
        
        im1 = pygame.image.load("assets/wasteBird/frame-1.png").convert_alpha()
        im2 = pygame.image.load("assets/wasteBird/frame-2.png").convert_alpha()
        im_dead = pygame.image.load("assets/wasteBird/dead.png").convert_alpha()
        self.im_dead = pygame.transform.scale(im_dead,(self.w,self.h))
        self.ims = {False: im1, True: im2}
        for key,im in self.ims.items():
            self.ims[key] = pygame.transform.scale(im,(self.w,self.h))
            
            
        self.curr_im = self.ims.get(self.flapping)
        self.rect = self.curr_im.get_rect(topleft = (self.x,self.y))
        
        self.hitbox_x_scale = 0.9
        self.hitbox_y_scale = 0.6
        self.hitbox = scale_by(self.rect,self.hitbox_x_scale,self.hitbox_y_scale)
        
        self.score = 0
        
        self.alive = True
        
        self.text_font = pygame.font.SysFont("arial", 30)
        
    def update(self):
        global STATE
        flap = False
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:  
                if time.time() > self.last_flap + self.debounce and self.alive:
                    flap = True
                    self.last_flap = time.time()
    
        
        if flap:
            self.vy = self.vy + self.flap            
        else:
            self.vy = self.vy + self.gravity
        
        self.flapping = flap
        
        self.vy = min(self.max_v_down,self.vy)
        self.vy = max(self.max_v_up,self.vy)
        
        if self.alive:
            if self.rect.top < 0:
                self.vy = self.max_v_down
            if self.rect.bottom > SCREEN.get_height():
                self.vy = self.max_v_up
        
        self.y = self.y + self.vy
        
        self.rect = self.curr_im.get_rect(topleft = (self.x,self.y))
        self.hitbox = scale_by(self.rect,self.hitbox_x_scale,self.hitbox_y_scale)
        
        if self.alive:
            self.score += 0.25
        
        if self.y > SCREEN.get_height() and not self.alive:
            MENU.last_highscore = round(self.score)
            STATE = "Menu"
        
    def draw(self):
        self.curr_im = self.ims.get(self.flapping)
        if not self.alive:
            self.curr_im = self.im_dead
            self.angle +=1
            self.curr_im = pygame.transform.rotate(self.curr_im,self.angle)
            self.curr_im = pygame.transform.flip(self.curr_im,False,True)
        
        SCREEN.blit(self.curr_im,self.rect)
        
        # High scores
        score_text = self.text_font.render(f"High Score: {round(self.score)}", True, (200, 200, 200))
        score_rect = score_text.get_rect(topleft=(0,0))
        SCREEN.blit(score_text, score_rect)
        
        if DEBUG:
            pygame.draw.rect(SCREEN,pygame.Color("red"),self.hitbox,1)
            print(self.score)

def ret():
    global RUNNING
    RUNNING = False

def setup(screen,clock):
    global SCREEN, CLOCK, RUNNING, FPS, DEBUG
    RUNNING = True
    SCREEN = screen
    CLOCK = clock
    FPS = 30
    DEBUG = False
    
    global HOME_BUTTON
    HOME_BUTTON = Button(690, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    
    global PLAYER
    PLAYER = Player()
    
    global BACKGROUNDS
    BACKGROUNDS = []
    BG1 = Background()
    BG2 = Background(x=SCREEN.get_width())
    BACKGROUNDS.append(BG1)
    BACKGROUNDS.append(BG2)
    
    global ENTITY_MANAGER
    ENTITY_MANAGER = EntityManager()
    
    global STATE
    STATE = "Menu"
    
    global MENU
    MENU = Menu(500,380)

def update():
    global EVENTS, DEBUG
    EVENTS = pygame.event.get()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            ret()           
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                DEBUG = not DEBUG
                print(f"Debug: {DEBUG}")
            
        
    HOME_BUTTON.update(EVENTS)   
    if STATE == "Menu":
        MENU.update()
    else:
        for bg in BACKGROUNDS:
            bg.update()              
        ENTITY_MANAGER.update()    
        PLAYER.update()
    
def draw():
    SCREEN.fill(pygame.Color("gray"))
    
    
    
    if STATE == "Menu":
        for bg in BACKGROUNDS:
            bg.draw() 
        MENU.draw()
    else:    
        for bg in BACKGROUNDS:
            bg.draw()         
        ENTITY_MANAGER.draw()
        PLAYER.draw()
    
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