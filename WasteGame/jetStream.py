# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import math
import random as rd

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


class Background:
    def __init__(self):
        self.nRects = 15
        self.hRect = SCREEN.get_height() // self.nRects
        self.wRect = SCREEN.get_width()

        self.colormaps = {
            "Sea": [pygame.Color("blue4"), pygame.Color("cadetblue")],
            "Desert": [pygame.Color("olive"), pygame.Color("olivedrab")],
            "Snow": [pygame.Color("gainsboro"), pygame.Color("floralwhite")],
        }
        self.colors = self.colormaps["Sea"]

        self.offset = 0
        self.scroll_speed = PLAYER.airspeed

    def update(self):
        mission_map = {0: "Sea", 1: "Desert", 2: "Snow"}
        self.colors = self.colormaps.get(mission_map.get(nMISSION, "Sea"), self.colors)

        self.scroll_speed = PLAYER.airspeed
        self.offset -= self.scroll_speed
        self.offset %= self.hRect * 2  # ensures perfect wrap every 2 stripes
        if PLAYER.aircraftcarrier and self.scroll_speed > CARRIER.vy:
            self.scroll_speed -= 0.5

    def draw(self):
        for i in range(self.nRects + 2):  # +2 to cover gaps when offset > 0
            y = i * self.hRect - self.offset
            color = self.colors[i % 2]
            pygame.draw.rect(SCREEN, color, pygame.Rect(0, y, self.wRect, self.hRect))


class Bullet:
    IMAGE = pygame.image.load("assets/jetStream/Missile.png")

    def __init__(self, caller):
        self.caller = caller
        self.x = caller.x
        self.y = caller.y
        self.vy = -10
        self.w = 5
        self.h = 7
        self.image = Bullet.IMAGE
        self.mask = pygame.mask.from_surface(self.image)
        self.rect = self.image.get_rect()
        self.rect.center = (self.x, self.y)
        self.color = pygame.Color("firebrick1")
        self.damage = 1
        self.has_hit = False
        self.death_count = 0

    def update(self):
        if not self.has_hit:
            self.y += self.vy
            self.rect.center = (self.x, self.y)
            if self.y < 0 or self.y > SCREEN.get_height():
                self.caller.bullets.remove(self)
                return
            for e in ENEMIES:
                if self.rect.colliderect(e.rect):
                    offset = (e.rect.left - self.rect.left, e.rect.top - self.rect.top)
                    if self.mask.overlap(e.mask, offset):
                        e.health -= self.damage
                        self.has_hit = True
                        self.death_count = 0  # reset counter when explosion starts
        else:
            frame_size = EXPLOSION_IMAGES.get_height()  # Assuming square frames stacked horizontally
            total_frames = EXPLOSION_IMAGES.get_width() // frame_size

            if self.death_count < total_frames:
                frame_rect = pygame.Rect(frame_size * self.death_count, 0, frame_size, frame_size)
                self.image = EXPLOSION_IMAGES.subsurface(frame_rect)
                self.rect = self.image.get_rect(center=(self.x, self.y))
                self.death_count += 1
            else:
                # Animation done, remove bullet
                self.caller.bullets.remove(self)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Carrier:
    IMAGE = pygame.image.load("assets/jetStream/ShipCarrierHull.png")
    IMAGE2 = pygame.image.load("assets/jetStream/runway.png")
    BATTLESHIP_IMAGE = pygame.image.load("assets/jetStream/ShipBattleshipHull.png")
    CRUISER_IMAGE = pygame.image.load("assets/jetStream/ShipCruiserHull.png")
    DESTROYER_IMAGE = pygame.image.load("assets/jetStream/ShipDestroyerHull.png")
    PATROLBOAT_IMAGE = pygame.image.load("assets/jetStream/ShipPatrolHull.png")

    h = IMAGE.get_height()
    w = IMAGE.get_width()
    scale_factor = 3
    new_h = h * scale_factor
    new_w = w * scale_factor
    IMAGE = pygame.transform.smoothscale(IMAGE, (new_w, new_h))
    IMAGE = pygame.transform.rotate(IMAGE, -9)
    IMAGE2 = pygame.transform.smoothscale(IMAGE2, (new_w, new_h))
    IMAGES = {"Sea": IMAGE, "Desert": IMAGE2, "Snow": IMAGE2}

    def __init__(self):
        self.x = SCREEN.get_width() // 2
        self.y = -10
        self.vy = PLAYER.airspeed

        self.mission_map = {0: "Sea", 1: "Desert", 2: "Snow"}
        self.mission_type = self.mission_map.get(nMISSION, "Sea")
        self.image = Carrier.IMAGES[self.mission_type]

        self.rect = self.image.get_rect()
        self.rect.center = (self.x, self.y)

        PLAYER.x = self.x
        PLAYER.y = self.y + 300  # adjust until it looks right
        PLAYER.rect.center = (PLAYER.x, PLAYER.y)

    def update(self):
        self.vy = PLAYER.airspeed
        self.y = self.y + self.vy
        self.rect.top = self.y
        print(self.y)

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if self.mission_type == "Sea":
            cx, cy = self.rect.center  # Carrier center
            # Vertical and horizontal spacing (based on scaled size)
            horiz_offset = 200
            vert_offset = 150
            # Cruiser: ahead of the carrier
            cruiser_pos = (cx, cy - vert_offset - 250)
            cruiser2_pos = (cx - 60, cy - vert_offset - 300)
            # Battleship: front-left
            battleship_pos = (cx - horiz_offset, cy - vert_offset)
            battleship2_pos = (cx + horiz_offset, cy - vert_offset)
            # Destroyer: front-right
            destroyer_pos = (cx + horiz_offset, cy - vert_offset)
            # Patrol boat: behind the carrier
            patrolboat_pos = (cx, cy + vert_offset)
            # Blit all ships
            SCREEN.blit(Carrier.CRUISER_IMAGE, Carrier.CRUISER_IMAGE.get_rect(center=cruiser_pos))
            SCREEN.blit(Carrier.CRUISER_IMAGE, Carrier.CRUISER_IMAGE.get_rect(center=cruiser2_pos))
            SCREEN.blit(Carrier.BATTLESHIP_IMAGE, Carrier.BATTLESHIP_IMAGE.get_rect(center=battleship_pos))
            SCREEN.blit(Carrier.BATTLESHIP_IMAGE, Carrier.BATTLESHIP_IMAGE.get_rect(center=battleship2_pos))
            SCREEN.blit(Carrier.DESTROYER_IMAGE, Carrier.DESTROYER_IMAGE.get_rect(center=destroyer_pos))
            SCREEN.blit(Carrier.PATROLBOAT_IMAGE, Carrier.PATROLBOAT_IMAGE.get_rect(center=patrolboat_pos))


class Enemy:
    class Bullet:
        IMAGE = pygame.image.load("assets/jetStream/Missile.png")

        def __init__(self, caller):
            self.caller = caller
            self.x = caller.x
            self.y = caller.y
            self.vy = 5
            self.w = 5
            self.h = 7
            self.image = Enemy.Bullet.IMAGE
            self.mask = pygame.mask.from_surface(self.image)
            self.rect = self.image.get_rect()
            self.rect.center = (self.x, self.y)
            self.caller.bullets.append(self)
            damages = {"UBoat": 3, "Plane": 1, "B17": 4, "Spacecraft": 8}
            self.damage = damages.get(self.caller.typ, "Plane")
            self.has_hit = False
            self.death_count = 0

        def update(self):
            if not self.has_hit:
                self.y += self.vy
                self.rect.center = (self.x, self.y)
                if self.y < 0 or self.y > SCREEN.get_height():
                    self.caller.bullets.remove(self)
                    return
                if self.rect.colliderect(PLAYER.rect):
                    offset = (PLAYER.rect.left - self.rect.left, PLAYER.rect.top - self.rect.top)
                    if self.mask.overlap(PLAYER.mask, offset):
                        PLAYER.health -= self.damage
                        self.has_hit = True
                        self.death_count = 0  # reset counter when explosion starts
            else:
                frame_size = EXPLOSION_IMAGES.get_height()  # Assuming square frames stacked horizontally
                total_frames = EXPLOSION_IMAGES.get_width() // frame_size

                if self.death_count < total_frames:
                    frame_rect = pygame.Rect(frame_size * self.death_count, 0, frame_size, frame_size)
                    self.image = EXPLOSION_IMAGES.subsurface(frame_rect)
                    self.rect = self.image.get_rect(center=(self.x, self.y))
                    self.death_count += 1
                else:
                    # Animation done, remove bullet
                    self.caller.bullets.remove(self)

        def draw(self):
            SCREEN.blit(self.image, self.rect)

    IMAGES = {
        "UBoat": pygame.image.load("assets/jetStream/ShipSubMarineHull.png"),
        "Plane": pygame.transform.scale_by(pygame.image.load("assets/jetStream/PlaneF-35Lightning2.png"), (2, 2)),
        "B17": pygame.image.load("assets/jetStream/B17.png"),
        "Spacecraft": pygame.transform.scale_by(pygame.image.load("assets/jetStream/Battleplane.png"), (0.5, 0.5)),
    }

    def __init__(self, x, y, typ="Plane", target_y=100):
        self.x = x
        self.vx = 2
        self.y = y
        self.target_y = target_y
        self.typ = typ
        self.image = Enemy.IMAGES.get(self.typ, "Plane")
        self.mask = pygame.mask.from_surface(self.image)
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.recovering = False  # Flag to control dodge vs. recovery
        self.center_x = SCREEN.get_width() // 2

        self.shootInterval = 72
        self.lastShot = 0
        self.bullets = []

        healths = {"UBoat": 15, "Plane": 5, "B17": 30, "Spacecraft": 60}
        self.maxHealth = healths.get(self.typ, "Plane")
        self.health = self.maxHealth

        self.is_dead = False
        self.death_count = 0

        self.temperament = rd.choice(["aggressive", "defensive"])
        ENEMIES.append(self)

        self.frame_counter = 0
        self.warning_text_appeared = None

    def shoot(self):
        if self.lastShot > self.shootInterval and not PLAYER.aircraftcarrier and not PLAYER.landing:
            self.bullets.append(Enemy.Bullet(self))
            if self.typ == "Spacecraft":
                self.bullets[0].y = self.rect.bottom
                bullet_left = Enemy.Bullet(self)
                bullet_left.x = bullet_left.x - 50
                bullet_right = Enemy.Bullet(self)
                bullet_right.x = bullet_right.x + 50
                self.bullets.append(bullet_right)
                self.bullets.append(bullet_left)
            self.lastShot = 0
        self.lastShot = self.lastShot + 1

    def update(self):

        # Chance to change temperament
        if rd.random() < 0.005:
            self.temperament = rd.choice(["aggressive", "defensive"])

        # Check for collission with other enemies and move out of the way:
        for e in ENEMIES:
            if self.rect.colliderect(e.rect) and e is not self:
                if self.rect.centerx < e.rect.centerx:
                    self.x = self.x - self.vx
                else:
                    self.x = self.x + self.vx
                # Optional: Also adjust vertical position
                if self.rect.centery < e.rect.centery:
                    self.y -= 1
                else:
                    self.y += 1

        if self.y < self.target_y:
            self.y = self.y + PLAYER.airspeed - 1

        if self.health <= 0:
            self.is_dead = True

        if not self.is_dead:
            self.shoot()
            dodge_speed = self.vx
            danger_zone = 100
            screen_width = SCREEN.get_width()

            if self.recovering:
                # Move toward center while recovering
                if abs(self.x - self.center_x) < 100:
                    self.recovering = False  # Done recovering
                elif self.x < self.center_x:
                    self.x += dodge_speed
                else:
                    self.x -= dodge_speed
            else:
                # Normal dodge logic
                if self.temperament == "defensive":
                    for b in PLAYER.bullets:
                        if abs(b.rect.centery - self.rect.centery) < 150:
                            dx = b.rect.centerx - self.rect.centerx
                            if abs(dx) < danger_zone:
                                if dx < 0:
                                    self.x += dodge_speed
                                else:
                                    self.x -= dodge_speed
                elif self.temperament == "aggressive":
                    if self.rect.centerx < PLAYER.rect.centerx:
                        self.x += dodge_speed
                    else:
                        self.x -= dodge_speed
                else:  # "static" temperament e.g. for SHIPS
                    pass

                # Teleport if off screen
                if self.rect.centerx < 0:
                    self.x = screen_width - self.rect.width
                    self.recovering = True
                elif self.rect.centerx > screen_width - self.rect.width:
                    self.x = self.rect.width
                    self.recovering = True

            # Apply position
            self.rect.centerx = self.x
            self.rect.centery = self.y
            # Update Self Bullets
            for b in self.bullets:
                b.update()
        else:
            frame_size = EXPLOSION_IMAGES.get_height()  # Assuming square frames stacked horizontally
            total_frames = EXPLOSION_IMAGES.get_width() // frame_size

            if self.death_count < total_frames:
                frame_rect = pygame.Rect(frame_size * self.death_count, 0, frame_size, frame_size)
                self.image = pygame.transform.scale_by(EXPLOSION_IMAGES.subsurface(frame_rect), (2.5, 2.5))
                self.rect = self.image.get_rect(center=(self.x, self.y))
                self.death_count += 1
            else:
                # Animation done, remove bullet
                ENEMIES.remove(self)

    def drawHealthBar(self):
        # === HEALTH BAR (Military Style) ===
        bar_width = 60
        bar_height = 12
        bar_border = 2
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - 20  # Just above the enemy

        # Background (bordered box)
        pygame.draw.rect(
            SCREEN,
            pygame.Color("black"),
            (bar_x - bar_border, bar_y - bar_border, bar_width + 2 * bar_border, bar_height + 2 * bar_border),
        )

        # Fill based on health
        health_ratio = self.health / self.maxHealth
        fill_width = int(bar_width * health_ratio)
        colors = {"aggressive": pygame.Color("darkred"), "defensive": pygame.Color("darkblue")}
        pygame.draw.rect(SCREEN, colors.get(self.temperament), (bar_x, bar_y, fill_width, bar_height))

        # Tick marks (for a military segmented look)
        segment_width = 10
        for i in range(0, bar_width, segment_width):
            pygame.draw.line(SCREEN, pygame.Color("black"), (bar_x + i, bar_y), (bar_x + i, bar_y + bar_height), 1)

        # Optional: health number in military font style (optional aesthetic)
        # health_text = FONT.render(f"{self.health}/{self.maxHealth}", True, pygame.Color("green"))
        # SCREEN.blit(health_text, (bar_x, bar_y - 16))

    def draw(self):
        # Update Self Bullets
        for b in self.bullets:
            b.draw()
        self.drawHealthBar()
        SCREEN.blit(self.image, self.rect)
        if (self.typ == "Spacecraft" or self.typ == "B17") and self.y > -1500 and self.y < 0:
            if self.warning_text_appeared == None:
                self.warning_text_appeared = self.frame_counter
            st = {"B17": "TARGET APPROACHING", "Spacecraft": "ENEMY APPROACHING"}
            text = FONT.render(st.get(self.typ), True, pygame.Color("green"), pygame.Color("black"))
            text_rect = text.get_rect()
            text_rect.center = SCREEN.get_rect().center
            SCREEN.blit(text, text_rect)
        self.frame_counter += 1


class Player:
    def __init__(self):
        self.x = SCREEN.get_width() // 2
        self.y = 700

        self.vx = 0
        self.ax = 3
        self.vx_max = 10
        self.x_drag = 0.95
        self.airspeed = 3
        self.distance = 0

        self.vy = 10
        self.ay = 3
        self.vy_max = 10
        self.y_drag = 0.95

        self.base_image = FIGHTER_IMAGES[SELECTED_AIRPLANE]
        self.image = self.base_image.copy()
        self.mask = pygame.mask.from_surface(self.image)
        self.rect = self.image.get_rect(center=(self.x, self.y))

        self.shootInterval = 6
        self.lastShot = 0
        self.bullets = []

        self.aircraftcarrier = True
        self.takeoff_time = 180
        self.takeoff_timer = self.takeoff_time  # frames until control unlocks (~1.5 seconds)

        self.landing_time = 270  # frames for smooth landing transition
        self.landing_timer = self.landing_time  # frames for smooth landing transition
        self.distance_to_carrier = 0
        self.landing_distance = 1000

        self.landing = False
        self.landed = False

        self.health = 1000
        self.maxHealth = 1000

    def changeImage(self):
        self.base_image = FIGHTER_IMAGES[SELECTED_AIRPLANE]
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.mask = pygame.mask.from_surface(self.image)

    def shoot(self):
        if self.lastShot > self.shootInterval and not self.aircraftcarrier and not self.landing:
            self.bullets.append(Bullet(self))
            self.lastShot = 0
        self.lastShot = self.lastShot + 1

    def decreaseSpriteSize(self):
        self.image = pygame.transform.scale_by(self.base_image, 0.5 + 0.5 * self.landing_timer / self.landing_time)

    def increaseSpriteSize(self):
        self.image = pygame.transform.scale_by(
            self.base_image, 0.5 + 0.5 * (self.takeoff_time - self.takeoff_timer) / self.takeoff_time
        )

    def update(self):

        self.distance = self.distance + self.airspeed

        if self.aircraftcarrier and self.landed == False:
            self.takeoff_timer -= 1
            self.vy -= 0.3  # launch upward
            self.increaseSpriteSize()
            self.rect = self.image.get_rect(center=(self.x, self.y))
            self.airspeed = self.airspeed + 9 / 180
            if self.takeoff_timer <= 0:
                self.aircraftcarrier = False
                self.vy = max(self.vy, -5)  # ensure decent speed
        else:
            mouse_pos = pygame.mouse.get_pos()
            button_down = pygame.mouse.get_pressed()[0]
            self.shoot()
            if button_down:
                dx = mouse_pos[0] - self.x
                dy = mouse_pos[1] - self.y
                dist = math.hypot(dx, dy)
                if button_down and dist > 5:  # only accelerate if far enough
                    self.vx += self.ax * (dx / dist)
                    self.vy += self.ay * (dy / dist)
                elif dist < 50:
                    self.vx *= 0.8
                    self.vy *= 0.8

        # Landing Check
        dx = abs(self.x - CARRIER.x)
        dy = abs(self.y - (CARRIER.y + 300))  # offset to deck height
        self.distance_to_carrier = dy

        if self.distance_to_carrier < self.landing_distance and self.aircraftcarrier == False:

            self.landing = True
            self.vx = 0
            self.vy = 0

        if self.landing:
            self.landing_timer -= 1
            self.x += (CARRIER.x - self.x) * 0.1
            self.y += SCREEN.get_height() - 100
            self.rect.center = (self.x, self.y)
            self.decreaseSpriteSize()
            self.airspeed = self.airspeed * (self.distance_to_carrier / self.landing_distance)
            if not self.landed:
                self.airspeed = max(3, self.airspeed)

            if self.distance_to_carrier <= 25:
                self.aircraftcarrier = True
                self.landing = False
                self.takeoff_timer = self.takeoff_time
                self.vx = 0
                self.vy = 0
                self.airspeed = 0
                self.landed = True

        if self.landed:
            self.vx = 0
            self.vy = 0
            self.airspeed = 0
            self.rect.center = CARRIER.rect.center
            self.x = self.rect.center[0]
            self.y = self.rect.center[1]

        # Cap velocities
        self.vx = max(self.vx, -self.vx_max)
        self.vx = min(self.vx, self.vx_max)
        self.vy = max(self.vy, -self.vy_max)
        self.vy = min(self.vy, self.vy_max)
        self.airspeed = min(self.airspeed, 12)

        # Apply drag to v
        self.vx = self.vx * self.x_drag
        self.vy = self.vy * self.y_drag

        # Apply velocity to position
        self.x = self.x + self.vx
        self.y = self.y + self.vy
        self.rect.center = (self.x, self.y)

        # Cap Position
        self.rect.top = max(self.rect.top, 0)
        self.rect.bottom = min(self.rect.bottom, SCREEN.get_height())
        self.rect.left = max(self.rect.left, 0)
        self.rect.right = min(self.rect.right, SCREEN.get_width())
        self.x = self.rect.center[0]
        self.y = self.rect.center[1]

        # Update Self Bullets
        for b in self.bullets:
            b.update()

    def drawHealthBar(self):
        # === HEALTH BAR (Military Style) ===
        bar_width = 120
        bar_height = 12
        bar_border = 2
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.bottom + 20  # Just above the enemy

        # Background (bordered box)
        pygame.draw.rect(
            SCREEN,
            pygame.Color("black"),
            (bar_x - bar_border, bar_y - bar_border, bar_width + 2 * bar_border, bar_height + 2 * bar_border),
        )

        # Fill based on health
        health_ratio = self.health / self.maxHealth
        fill_width = int(bar_width * health_ratio)
        pygame.draw.rect(SCREEN, pygame.Color("darkgreen"), (bar_x, bar_y, fill_width, bar_height))

        # Tick marks (for a military segmented look)
        segment_width = 10
        for i in range(0, bar_width, segment_width):
            pygame.draw.line(SCREEN, pygame.Color("black"), (bar_x + i, bar_y), (bar_x + i, bar_y + bar_height), 1)

        # Optional: health number in military font style (optional aesthetic)
        # health_text = FONT.render(f"{self.health}/{self.maxHealth}", True, pygame.Color("green"))
        # SCREEN.blit(health_text, (bar_x, bar_y - 16))

    def draw(self):
        # Draw Self Bullets
        for b in self.bullets:
            b.draw()

        self.draw_rect = self.rect.copy()
        SCREEN.blit(self.image, self.draw_rect)

        distance_surf = FONT.render(
            "Delta Carrier: " + str(round(self.distance_to_carrier)), True, pygame.Color("green"), pygame.Color("black")
        )
        SCREEN.blit(distance_surf, (0, 580))

        airspeed_surf = FONT.render(
            "Airspeed: " + str(round(self.airspeed * 100)) + " kt", True, pygame.Color("green"), pygame.Color("black")
        )
        airspeed_rect = airspeed_surf.get_rect()
        SCREEN.blit(airspeed_surf, (SCREEN.get_width() - airspeed_rect.w, 580))

        self.drawHealthBar()


def ret():
    global RUNNING
    RUNNING = False


def setup():
    global FONT, WINFONT, MAINMENUFONT_LARGE, MAINMENUFONT_MEDIUM, nMISSION
    nMISSION = 0
    FONT = pygame.font.Font("assets/jetStream/font.ttf", 24)
    WINFONT = pygame.font.Font("assets/jetStream/font.ttf", 68)
    MAINMENUFONT_LARGE = pygame.font.Font("assets/jetStream/font.ttf", 50)
    MAINMENUFONT_MEDIUM = pygame.font.Font("assets/jetStream/font.ttf", 34)

    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    global BACKGROUNDS
    BACKGROUNDS = {"Sea": pygame.image.load("assets/jetStream/sea.png"), "Grass": pygame.image.load("assets/jetStream/grass.png")}

    global FIGHTER_IMAGES
    FIGHTER_IMAGES = {
        "f1": pygame.transform.scale_by(pygame.image.load("assets/jetStream/f1.png").convert_alpha(), (1.5, 1.5)),
        "f2": pygame.transform.scale_by(pygame.image.load("assets/jetStream/f2.png").convert_alpha(), (1.5, 1.5)),
        "f3": pygame.transform.scale_by(pygame.image.load("assets/jetStream/f3.png").convert_alpha(), (1.5, 1.5)),
        "f4": pygame.transform.scale_by(pygame.image.load("assets/jetStream/f4.png").convert_alpha(), (1.5, 1.5)),
        "f5": pygame.image.load("assets/jetStream/combatjet-highres.png").convert_alpha(),
        "f6": pygame.transform.scale_by(pygame.image.load("assets/jetStream/f5.png").convert_alpha(), (0.75, 0.75)),
    }

    global EXPLOSION_IMAGES
    EXPLOSION_IMAGES = pygame.image.load("assets/jetStream/Explosion.png").convert_alpha()

    global SELECTED_AIRPLANE
    SELECTED_AIRPLANE = "f5"

    global PLAYER
    PLAYER = Player()

    global BACKGROUND
    BACKGROUND = Background()

    global CARRIER
    CARRIER = Carrier()

    global MISSION_STARTED
    MISSION_STARTED = False

    global MAIN_MENU_BG, MAIN_MENU_BG2
    MAIN_MENU_BG = pygame.image.load("assets/jetStream/mainMenu.png")
    MAIN_MENU_BG = pygame.transform.smoothscale(MAIN_MENU_BG, (SCREEN.get_width(), SCREEN.get_height()))
    MAIN_MENU_BG2 = pygame.image.load("assets/jetStream/mainMenu2.png")
    MAIN_MENU_BG2 = pygame.transform.smoothscale(MAIN_MENU_BG2, (SCREEN.get_width(), SCREEN.get_height()))

    global WINBG, WINBG2
    WINBG = pygame.image.load("assets/jetStream/beatgame.png")
    WINBG = pygame.transform.smoothscale(WINBG, (SCREEN.get_width(), SCREEN.get_height()))
    WINBG2 = pygame.image.load("assets/jetStream/beatgame2.png")
    WINBG2 = pygame.transform.smoothscale(WINBG2, (SCREEN.get_width(), SCREEN.get_height()))

    global MENU_COUNTER
    MENU_COUNTER = 0

    global MISSION_PRE_BRIEF
    MISSION_PRE_BRIEF = False

    global ENEMIES
    ENEMIES = []


def startMenu():
    global MAINMENUFONT_LARGE, MAINMENUFONT_MEDIUM, MENU_COUNTER, MISSION_STARTED, MISSION_PRE_BRIEF
    MENU_COUNTER += 1

    SCREEN.fill(pygame.Color("black"))

    if (MENU_COUNTER // 30) % 2 == 0:
        SCREEN.blit(MAIN_MENU_BG, (0, 0))
    else:
        SCREEN.blit(MAIN_MENU_BG2, (0, 0))

    mainrect = pygame.Rect(0, 0, 400, 300)
    mainrect.center = (SCREEN.get_width() // 2, SCREEN.get_height() // 2 - 150)
    main_text_surf = MAINMENUFONT_LARGE.render("WELCOME COMMANDER", True, pygame.Color("green"), pygame.Color("black"))
    main_text_rect = main_text_surf.get_rect()
    main_text_rect.center = mainrect.center
    SCREEN.blit(main_text_surf, main_text_rect)

    startrect = pygame.Rect(0, 0, 400, 300)
    startrect.center = (SCREEN.get_width() // 2, 500)
    start_text_surf = MAINMENUFONT_LARGE.render("START MISSION", True, pygame.Color("green"), pygame.Color("black"))
    start_text_rect = start_text_surf.get_rect()
    start_text_rect.center = startrect.center
    SCREEN.blit(start_text_surf, start_text_rect)

    mouse_pos = pygame.mouse.get_pos()
    if start_text_rect.collidepoint(mouse_pos):
        pygame.draw.rect(SCREEN, pygame.Color("green"), start_text_rect, 4)
    if (MENU_COUNTER // 25) % 2 == 0:
        pygame.draw.rect(SCREEN, pygame.Color("green"), start_text_rect, 2)
    for e in EVENTS:
        if e.type == pygame.MOUSEBUTTONDOWN:
            if start_text_rect.collidepoint(e.pos):
                MISSION_PRE_BRIEF = True


def renderText(text, x, y):
    startrect = pygame.Rect(0, 0, 400, 300)
    startrect.center = (x, y)
    start_text_surf = MAINMENUFONT_LARGE.render(text, True, pygame.Color("green"), pygame.Color("black"))
    start_text_rect = start_text_surf.get_rect()
    start_text_rect.center = startrect.center
    SCREEN.blit(start_text_surf, start_text_rect)


def missionPreBrief():
    global SELECTED_AIRPLANE, MENU_COUNTER, MISSION_PRE_BRIEF, MISSION_STARTED
    MENU_COUNTER = MENU_COUNTER + 1

    SCREEN.fill(pygame.Color("black"))
    renderText("MISSION PRE-BRIEF", SCREEN.get_width() // 2, 200)
    renderText("SELECT AIRPLANE", SCREEN.get_width() // 2, 300)

    startrect = pygame.Rect(0, 0, 400, 500)
    startrect.center = (SCREEN.get_width() // 2, 500)
    start_text_surf = MAINMENUFONT_LARGE.render("DEPART", True, pygame.Color("green"), pygame.Color("black"))
    start_text_rect = start_text_surf.get_rect()
    start_text_rect.center = startrect.center
    SCREEN.blit(start_text_surf, start_text_rect)
    if (MENU_COUNTER // 25) % 2 == 0:
        pygame.draw.rect(SCREEN, pygame.Color("green"), start_text_rect, 2)

    y = 350  # Vertical position
    spacing = 20
    image_scale = 0.75
    x = 15  # Starting x position
    rects = []
    for key in FIGHTER_IMAGES:
        original = FIGHTER_IMAGES[key]
        img = pygame.transform.scale_by(original, image_scale)
        SCREEN.blit(img, (x, y))
        if key == SELECTED_AIRPLANE:
            pygame.draw.rect(SCREEN, pygame.Color("green"), img.get_rect(topleft=(x, y)), 2)
        rects.append(pygame.Rect(img.get_rect(topleft=(x, y))))
        x += img.get_width() + spacing  # Advance x by image width + spacing

    for e in EVENTS:
        if e.type == pygame.MOUSEBUTTONDOWN:
            for idx, r in enumerate(rects):
                if r.collidepoint(e.pos):
                    SELECTED_AIRPLANE = list(FIGHTER_IMAGES.keys())[idx]
                    PLAYER.changeImage()
            if start_text_rect.collidepoint(e.pos):
                MISSION_PRE_BRIEF = False
                MISSION_STARTED = True
                if nMISSION == 0:
                    Enemy(400, -2000)
                    Enemy(400, -2200)
                    Enemy(400, -9000, "UBoat", 150)
                    Enemy(400, -10000, "UBoat", 150)
                    Enemy(400, -15000, target_y=200)
                    Enemy(400, -17000)
                    Enemy(400, -20000, "B17")
                    Enemy(400, -19000)
                    Enemy(400, -18000)
                    Enemy(400, -17500)
                    Enemy(400, -33000, "Spacecraft")
                    Enemy(400, -31000)
                    Enemy(200, -33000)
                    Enemy(500, -33000)


def update():
    global RUNNING, EVENTS
    EVENTS = pygame.event.get()
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False

    if MISSION_STARTED:
        PLAYER.update()
        BACKGROUND.update()
        CARRIER.update()
        for e in ENEMIES:
            e.update()

        # Move Carrier after start
        if CARRIER.y > SCREEN.get_height():
            CARRIER.y = -50000
    elif MISSION_PRE_BRIEF:
        missionPreBrief()
    else:
        startMenu()


def draw():
    global MENU_COUNTER, nMISSION, MISSION_STARTED, MISSION_PRE_BRIEF
    if MISSION_STARTED:
        SCREEN.fill((255, 250, 0))
        SCREEN.fill(pygame.Color("lightblue"))

        BACKGROUND.draw()
        CARRIER.draw()
        PLAYER.draw()
        for e in ENEMIES:
            e.draw()

        if PLAYER.landed:
            MENU_COUNTER += 1
            fade_duration = 60 * 7  # 60*x seconds  # number of frames to fully fade in

            # Clamp MENU_COUNTER so alpha never exceeds 255
            alpha = min(int((MENU_COUNTER / fade_duration) * 255), 255)

            winbg_copy = WINBG.copy()
            winbg2_copy = WINBG2.copy()

            # Set both images' alpha to fade in smoothly
            winbg_copy.set_alpha(alpha)
            winbg2_copy.set_alpha(alpha)

            if (MENU_COUNTER // 30) % 2 == 0:
                SCREEN.blit(winbg_copy, (0, 0))
            else:
                SCREEN.blit(winbg2_copy, (0, 0))

            winrect = pygame.Rect(0, 0, 400, 300)
            winrect.center = (SCREEN.get_width() // 2, SCREEN.get_height() // 2 - 150)
            win_text_surf = WINFONT.render("MISSION COMPLETE", True, pygame.Color("green"), pygame.Color("black"))
            win_text_rect = win_text_surf.get_rect()
            win_text_rect.center = winrect.center
            SCREEN.blit(win_text_surf, win_text_rect)

            next_surf = WINFONT.render("NEXT MISSION", True, pygame.Color("green"), pygame.Color("black"))
            nextrect = next_surf.get_rect()
            nextrect.center = (SCREEN.get_width() // 2, 400)
            SCREEN.blit(next_surf, nextrect)
            if (MENU_COUNTER // 25) % 2 == 0:
                pygame.draw.rect(SCREEN, pygame.Color("green"), nextrect, 2)

            for e in EVENTS:
                if e.type == pygame.MOUSEBUTTONDOWN:
                    nMISSION = nMISSION + 1
                    MISSION_STARTED = False
                    MISSION_PRE_BRIEF = True
                    PLAYER.__init__()
                    CARRIER.__init__()

    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()
    while RUNNING:
        update()
        draw()
        CLOCK.tick(FPS)
        await asyncio.sleep(0)

    return
