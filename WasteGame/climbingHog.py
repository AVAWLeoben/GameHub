# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 21:20:21 2025

@author: GKoinig
"""

import pygame
import asyncio
import random as rd
from GUI import Button as Homebutton


class Button:
    def __init__(self, x, y, w, h, text="", callback=print):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)

        self.text = text
        self.font = pygame.font.Font(None, 30)
        self.text_surface = self.font.render(self.text, False, (0, 0, 0))
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)
        self.callback = callback
        self.clicked = False
        self.hovered = False

    def translateEventPos(self, event_pos):
        return (event_pos[0] - self.rect.x, event_pos[1] - self.rect.y)

    def update(self, translated_events):
        mouse_pos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mouse_pos):
            self.hovered = True
        else:
            self.hovered = False

        for event in translated_events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    if self.clicked == False:
                        self.clicked = True
                        self.callback()
                else:
                    self.clicked = False
            elif event.type == pygame.MOUSEBUTTONUP:
                self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, pygame.Color("lightgreen") if self.clicked else pygame.Color("darkgreen"), self.rect)
        if self.hovered:
            pygame.draw.rect(screen, pygame.Color("white"), self.rect, 3)
        screen.blit(self.text_surface, self.text_rect)


class Menu:
    def __init__(self):
        self.w = 800
        self.h = 600
        self.x = 0
        self.y = 0
        self.screen = pygame.Surface((self.w, self.h))
        self.rect = self.screen.get_rect(topleft=(self.x, self.y))
        self.buttons = []

    def translateEvents(self):
        translated_events = []
        for event in EVENTS:
            if hasattr(event, "pos"):
                translated_pos = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)
                new_event = pygame.event.Event(event.type, {"pos": translated_pos})
                translated_events.append(new_event)
            else:
                translated_events.append(event)
        return translated_events

    def addButton(self, Button):
        self.buttons.append(Button)

    def update(self):
        for button in self.buttons:
            button.update(self.translateEvents())

    def draw(self):
        for button in self.buttons:
            button.draw(self.screen)
        SCREEN.blit(self.screen, self.rect)
        pygame.draw.rect(SCREEN, pygame.Color("white"), self.rect, 2)


class Platform:
    def __init__(self, x, y, w, h, createdByClick=False, floor=False):
        global PLATFORMS
        self.x = x
        self.y = y
        check = rd.uniform(0, 1)
        self.moving = False
        self.vx = 0
        if check > 0.8 and createdByClick == False and floor == False:
            self.origin_x = x
            self.origin_y = y
            self.range = rd.uniform(50, 150)
            self.vx = rd.choice([-1, 1])
            self.moving = True
        if check > 0.1 and createdByClick == False and floor == False:
            Enemy(self.x, self.y - 64)
        self.w = w
        self.h = h
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.draw_rect = self.rect.move(0, 0)
        PLATFORMS.append(self)
        self.createdByClick = createdByClick
        self.lifespan = 60 * 5

    def update(self):
        if self.moving:
            self.x = self.x + self.vx
            if abs(self.x - self.origin_x) > self.range:
                self.vx = -self.vx
            self.rect.topleft = (self.x, self.y)

        self.draw_rect = self.rect.move(0, CAMERA_OFFSET)
        if self.createdByClick:
            self.lifespan = self.lifespan - 1
        if self.lifespan <= 0:
            PLATFORMS.remove(self)

    def draw(self):
        if not self.createdByClick:
            pygame.draw.rect(SCREEN, pygame.Color("lightgreen"), self.draw_rect)
            p1 = self.draw_rect.bottomleft
            p2 = self.draw_rect.topleft
            p3 = self.draw_rect.topright
            p4 = self.draw_rect.bottomright
            linewidth = 4
            linecolor = pygame.Color("white")
            pygame.draw.line(SCREEN, linecolor, p1, p2, linewidth)
            pygame.draw.line(SCREEN, linecolor, p2, p3, linewidth)
            pygame.draw.line(SCREEN, linecolor, p3, p4, linewidth)
        else:
            if self.lifespan > 60 * 2:
                # Solid color for most of the time
                pygame.draw.rect(SCREEN, pygame.Color("lightgreen"), self.draw_rect)
            else:
                # Flicker during the last 15 frames
                if self.lifespan % 10 < 5:
                    pygame.draw.rect(SCREEN, pygame.Color("lightgreen"), self.draw_rect)
                else:
                    # Flicker to invisible or different color
                    pygame.draw.rect(SCREEN, pygame.Color("cornsilk1"), self.draw_rect)


class Enemy:
    IMAGES = [pygame.image.load("assets/ClimbingHog/ghost.png").convert_alpha()]

    def __init__(self, x, y):
        global ENEMIES
        self.x = x
        self.w = 64
        self.h = 64
        self.y = y
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.draw_rect = self.rect.move(0, 0)
        self.image = Enemy.IMAGES[0]
        self.image = pygame.transform.scale(self.image, (self.w, self.h))
        self.draw_image = self.image.copy()

        self.origin = self.x
        self.vx = rd.uniform(2, 4) * rd.choice([-1, 1])
        self.range = 300
        ENEMIES.append(self)
        self.facingRight = True

    def update(self):
        # Check for horizontal colision with obstacles
        for p in PLATFORMS:
            if p.rect.colliderect(self.rect):
                # Colision hapened
                if p.rect.left <= self.rect.right:
                    self.vx = -self.vx
                elif p.rect.right >= self.rect.left:
                    self.vx = -self.vx
                break

        # Check if there is a floor beneath the enemy
        # Check for floor ahead of enemy
        look_ahead_x = self.rect.centerx + (self.vx * 2)  # a little ahead of current direction
        look_ahead_y = self.rect.bottom + 15  # just below feet
        ray = (look_ahead_x, look_ahead_y)

        on_floor = False
        for p in PLATFORMS:
            if p.rect.collidepoint(ray):
                on_floor = True
                break

        if not on_floor:
            self.vx = -self.vx  # turn around

        self.x = self.x + self.vx
        if abs(self.x - self.origin) > self.range:
            self.vx = -self.vx
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.draw_rect = self.rect.move(0, CAMERA_OFFSET)

        if self.vx < 0 and self.facingRight:
            self.draw_image = pygame.transform.flip(self.image, 1, 0)
            self.facingRight = False
        elif self.vx > 0 and self.facingRight == False:
            self.draw_image = pygame.transform.flip(self.image, 0, 0)
            self.facingRight = True

        for p in PLAYERS:
            if self.rect.colliderect(p.rect):
                if p.vy > 0:
                    ENEMIES.remove(self)
                    p.vy = -5
                    break
                else:
                    p.vx = self.vx * 2

    def draw(self):
        # pygame.draw.rect(SCREEN, pygame.Color("chocolate1"), self.draw_rect)
        SCREEN.blit(self.draw_image, self.draw_rect)


class Projectile:
    def __init__(self, player):
        self.owner = player
        self.x = self.owner.x
        self.w = 8
        self.h = 8
        self.y = self.owner.y
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.draw_rect = self.rect.move(0, 0)

        # Movement
        self.g = self.owner.g
        self.ax = 0
        self.vx = 15 * self.owner.faceDir
        self.drag = 0.9
        self.vy = -abs(self.vx) / 2

        # Lifecycle
        self.lifespan = 4000
        self.createtime = pygame.time.get_ticks()

    def update(self):
        if pygame.time.get_ticks() > self.createtime + self.lifespan or self.x > SCREEN.get_width() or self.x < -10:
            self.owner.projectiles.remove(self)
            return
        # Horizontal collision
        temp_rect = self.rect.move(self.vx, 0)
        collided = False
        for platform in PLATFORMS:
            if temp_rect.colliderect(platform.rect):
                collided = True
                if self.vx > 0:
                    self.rect.right = platform.rect.left
                elif self.vx < 0:
                    self.rect.left = platform.rect.right
                self.vx = 0
                break
        if not collided:
            self.rect = temp_rect
            self.x += self.vx

        # Apply gravity to vy
        self.vy += self.g

        # Vertical collision
        temp_rect = self.rect.move(0, self.vy)
        collided = False
        self.onFloor = False  # assume airborne unless we land

        for platform in PLATFORMS:
            if temp_rect.colliderect(platform.rect):
                collided = True
                if self.vy > 0:
                    # Falling down, land on top
                    self.rect.bottom = platform.rect.top
                    self.y = self.rect.centery
                    self.vy = -0.95 * self.vy
                    # Apply drag to vx
                    self.vx *= self.drag
                    self.onFloor = True
                elif self.vy < 0:
                    # Moving up, hit underside
                    self.rect.top = platform.rect.bottom
                    self.y = self.rect.centery
                    self.vy = -0.5 * self.vy
                break

        if not collided:
            self.rect = temp_rect
            self.y += self.vy

        self.rect.center = (self.x, self.y)
        self.draw_rect = self.rect.move(0, CAMERA_OFFSET)
        if abs(self.vx) < 0.1:
            self.owner.projectiles.remove(self)
        for e in ENEMIES:
            if self.rect.colliderect(e.rect):
                ENEMIES.remove(e)
                self.owner.projectiles.remove(self)

    def draw(self):
        pygame.draw.rect(SCREEN, pygame.Color("brown2"), self.draw_rect)


class Player:
    IMAGES = {
        "Idle": pygame.transform.scale_by(pygame.image.load("assets/ClimbingHog/Player/idle/idle.png"), (2, 2)),
        "Moving": pygame.transform.scale_by(pygame.image.load("assets/ClimbingHog/Player/move/move.png"), (2, 2)),
    }

    def __init__(self):
        self.x = SCREEN.get_width() // 2
        self.w = 64
        self.h = 64
        self.y = PLATFORMS[0].rect.top - self.h
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.draw_rect = self.rect.move(0, 0)

        # Display
        self.state = "Idle"
        self.image = Player.IMAGES[self.state]
        # Extract current frame
        self.frame = 0
        self.image = self.image.subsurface(
            pygame.Rect(self.frame * self.image.get_height(), 0, self.image.get_height(), self.image.get_height())
        )
        self.rect = self.image.get_rect()
        self.anim_dur = 30
        self.time_since_last_frame = 0
        self.facing_right = True

        # Movement
        self.ax = 1
        self.vx = 0
        self.vx_max = 5
        self.vx_min = -self.vx_max
        self.drag = 0.9
        self.touch_start_time = 0
        self.touch_start_pos = None

        # Shooting
        self.faceDir = 1  # 1 for right, -1 for left
        self.shooting_cooldown = 250
        self.last_shot_time = 0

        self.jumpV0 = -30
        self.vy = 0
        self.vy_max = 10
        self.vy_min = self.jumpV0  # allow negative jump velocity
        self.g = 1.5
        self.jumpV0 = -20  # negative because Y increases downward in Pygame
        self.jumping = False
        self.onFloor = False

        # Attack
        self.projectiles = []

    def update(self):
        global CAMERA_OFFSET

        # Touch input (using mouse input as proxy)
        touch = None
        for event in pygame.event.get():
            if event.type == pygame.FINGERDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                touch = event
                self.touch_start_time = pygame.time.get_ticks()
                self.touch_start_pos = pygame.mouse.get_pos()

            elif event.type == pygame.FINGERUP or event.type == pygame.MOUSEBUTTONUP:
                self.touch_start_time = 0
                self.touch_start_pos = None

            elif event.type == pygame.MOUSEMOTION:
                touch = event  # use motion for continuous movement

        # Default no movement
        move_left = False
        move_right = False
        jump = False
        shoot = False

        # Handle touch position logic
        if pygame.mouse.get_pressed()[0]:  # Single touch active
            x, y = pygame.mouse.get_pos()
            screen_width, screen_height = pygame.display.get_surface().get_size()

            if x < screen_width * 0.33:
                move_left = True
            elif x > screen_width * 0.66:
                move_right = True

            if y < screen_height * 0.33:
                jump = True

            # Detect tap for shooting
            current_time = pygame.time.get_ticks()
            if self.touch_start_time and current_time - self.touch_start_time < 200:
                shoot = True
                self.touch_start_time = 0  # reset after firing

        # Apply movement
        if move_right:
            self.vx += self.ax
        elif move_left:
            self.vx -= self.ax

        # Jumping
        if jump and self.onFloor:
            self.vy = self.jumpV0
            self.onFloor = False

        # Firing projectile
        if shoot and len(self.projectiles) < 3 and pygame.time.get_ticks() > self.last_shot_time + self.shooting_cooldown:
            self.projectiles.append(Projectile(self))
            self.last_shot_time = pygame.time.get_ticks()

        # Apply drag to vx
        self.vx *= self.drag
        self.vx = max(self.vx_min, min(self.vx, self.vx_max))

        # Horizontal collision
        temp_rect = self.rect.move(self.vx, 0)
        collided = False
        for platform in PLATFORMS:
            if temp_rect.colliderect(platform.rect):
                collided = True
                if self.vx > 0:
                    self.rect.right = platform.rect.left
                elif self.vx < 0:
                    self.rect.left = platform.rect.right
                self.vx = 0
                self.state = "Idle"
                break
        if not collided:
            self.rect = temp_rect
            self.x += self.vx
            self.state = "Moving"

        if self.vx > 0:
            self.faceDir = 1
        elif self.vx < 0:
            self.faceDir = -1

        # Apply gravity to vy
        self.vy += self.g
        self.vy = max(self.vy_min, min(self.vy, self.vy_max))

        # Vertical collision
        temp_rect = self.rect.move(0, self.vy)
        collided = False
        self.onFloor = False  # assume airborne unless we land

        for platform in PLATFORMS:
            if temp_rect.colliderect(platform.rect):
                collided = True
                if self.vy > 0:
                    # Falling down, land on top
                    self.rect.bottom = platform.rect.top
                    self.y = self.rect.centery
                    self.vy = 0
                    self.onFloor = True
                    if abs(platform.vx) > 0:
                        self.vx = platform.vx
                elif self.vy < 0:
                    collided = False

                    # Moving up, hit underside
                    # self.rect.top = platform.rect.bottom
                    # self.y = self.rect.centery
                    # self.vy = 0
                break

        if not collided:
            self.rect = temp_rect
            self.y += self.vy

        self.rect.center = (self.x, self.y)
        self.draw_rect = self.rect.move(0, CAMERA_OFFSET)

        for projectile in self.projectiles:
            projectile.update()

        if self.draw_rect.top < 200:
            CAMERA_OFFSET = CAMERA_OFFSET + 1
        elif self.draw_rect.bottom > SCREEN.get_height():
            CAMERA_OFFSET = CAMERA_OFFSET - 3

        if self.x > SCREEN.get_width():
            self.x = 0
        if self.x < 0:
            self.x = SCREEN.get_width()

        if abs(self.vx) < 0.1:
            self.state = "Idle"

    def animate(self):
        self.facing_right = True
        # Update the sprite sheet based on current state
        self.sprite_sheet = Player.IMAGES[self.state]

        sheet_width = self.sprite_sheet.get_width()
        sheet_height = self.sprite_sheet.get_height()

        # Assumes square frames arranged horizontally
        frame_width = frame_height = sheet_height
        total_frames = sheet_width // frame_width

        # Update animation timer
        self.time_since_last_frame += 1
        if self.time_since_last_frame >= self.anim_dur:
            self.time_since_last_frame = 0
            self.frame = (self.frame + 1) % total_frames

        # Compute the rectangle for the current frame safely
        frame_rect = pygame.Rect(self.frame * frame_width, 0, frame_width, frame_height)

        # Make sure we don't go out of bounds
        if frame_rect.right <= sheet_width:
            self.image = self.sprite_sheet.subsurface(frame_rect)
        else:
            # fallback to first frame if something goes wrong
            self.image = self.sprite_sheet.subsurface(pygame.Rect(0, 0, frame_width, frame_height))
        if self.vx < 0 and self.facing_right:
            self.facing_right = False
            self.image = pygame.transform.flip(self.image, 1, 0)

    def draw(self):
        self.animate()
        for projectile in self.projectiles:
            projectile.draw()
        # pygame.draw.rect(SCREEN, pygame.Color("brown1"), self.draw_rect)
        SCREEN.blit(self.image, self.draw_rect)


def createMainMenu():
    global STARTMENU
    STARTMENU = Menu()

    def start():
        global STATE
        STATE = "Game"

    startbutton = Button(300, 300, 200, 100, "Start", start)
    STARTMENU.addButton(startbutton)


def generatePlatformsAbove(buffer_height=600):
    global LAST_PLATFORM_Y

    # Only generate if the player has climbed high enough
    while LAST_PLATFORM_Y > PLAYERS[0].y - buffer_height:
        num_platforms = rd.choice([1, 2, 3])  # sometimes multiple platforms at same height
        y = LAST_PLATFORM_Y - rd.randint(90, 150)  # vertical spacing upwards

        for _ in range(num_platforms):
            x = rd.randint(0, SCREEN.get_width() - 100)
            platform = Platform(x, y, 100, 20)
            PLATFORMS.append(platform)

        LAST_PLATFORM_Y = y  # update the highest platform created


def ret():
    global RUNNING
    RUNNING = False


def setup():
    pygame.font.init()
    global HOME_BUTTON
    HOME_BUTTON = Homebutton(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    global BACKGROUND
    BACKGROUND = pygame.image.load("assets/ClimbingHog/background.png")
    global CAMERA_OFFSET
    CAMERA_OFFSET = 0
    global CLOCK
    CLOCK = pygame.time.Clock()
    global RUNNING
    RUNNING = True
    global STATE
    STATE = "Start Menu"
    createMainMenu()
    global STATES
    STATES = {"Start Menu": STARTMENU.update, "Game": update}
    global PLATFORMS, LAST_PLATFORM_Y
    global ENEMIES
    ENEMIES = []
    PLATFORMS = []
    Platform(-100, SCREEN.get_height() - 20, SCREEN.get_width() + 100, 20, False, True)
    LAST_PLATFORM_Y = PLATFORMS[0].rect.top  # highest (smallest y) platform created

    global PLAYERS
    PLAYERS = []
    PLAYERS.append(Player())
    generatePlatformsAbove(buffer_height=600)

    Enemy(PLAYERS[0].x + 100, PLATFORMS[0].rect.top - 64)


def update():
    global EVENTS, RUNNING, PLATFORMS
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False

    if STATE == "Start Menu":
        STARTMENU.update()
    elif STATE == "Game":
        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                collides = False
                temp_rect = pygame.Rect(event.pos[0] - 16, event.pos[1] - CAMERA_OFFSET - 16, 32, 32)
                if temp_rect.colliderect(PLAYERS[0].rect):
                    collides = True
                if collides == False:
                    for p in PLATFORMS:
                        if temp_rect.colliderect(p.rect):
                            collides = True
                            break
                if collides == False:
                    PLATFORMS.append(Platform(event.pos[0] - 16, event.pos[1] - CAMERA_OFFSET - 16, 32, 32, True))
        generatePlatformsAbove()
        for platform in PLATFORMS:
            platform.update()
        for player in PLAYERS:
            player.update()
        for enemy in ENEMIES:
            enemy.update()

    CLOCK.tick(60)


def draw():
    SCREEN.fill(pygame.Color("black"))
    SCREEN.blit(BACKGROUND, (0, 600 - 1061 + CAMERA_OFFSET * 0.01))
    if STATE == "Start Menu":
        STARTMENU.draw()
    elif STATE == "Game":
        for platform in PLATFORMS:
            platform.draw()
        for player in PLAYERS:
            player.draw()
        for enemy in ENEMIES:
            enemy.draw()
    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()
    while RUNNING:
        CLOCK.tick(120)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
