# -*- coding: utf-8 -*-
"""WasteHockey: one-player / two-player air hockey for Pygame and Pygbag.

GameHub entry point: await wasteHockey.main(screen, clock)
Art assets: assets/wastehockey/{field,pusher1,pusher2,puck}.png
"""
import asyncio
import math
import os
import random

import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60

# The original field is 1280 x 673. Display it at its native aspect ratio.
FIELD_SOURCE_SIZE = (1280, 673)
FIELD_RECT = pygame.Rect(0, 96, 800, round(800 * 673 / 1280))
# Geometry derived from the visible ice surface in the image, not from the canvas edges.
TABLE_LEFT, TABLE_RIGHT = 25.0, 775.0
TABLE_TOP, TABLE_BOTTOM = 116.0, 500.0
MID_X = (TABLE_LEFT + TABLE_RIGHT) / 2
MID_Y = (TABLE_TOP + TABLE_BOTTOM) / 2
GOAL_HALF_HEIGHT = 61.0
PADDLE_RADIUS = 36.0
PUCK_RADIUS = 20.0
PUCK_MAX_SPEED = 1050.0
INITIAL_PUCK_SPEED = 365.0
PADDLE_MAX_SPEED = 2450.0
AI_MAX_SPEED = 680.0
KEYBOARD_SPEED = 900.0
WALL_BOUNCE = 0.95
PADDLE_BOUNCE = 0.88
GOAL_CELEBRATION_DURATION = 1.6
HOME_RECT = pygame.Rect(12, 12, 72, 63)

C_DARK = (15, 39, 66)
C_PANEL = (20, 53, 86)
C_ICE = (240, 251, 255)
C_YELLOW = (249, 206, 55)
C_BLUE = (65, 157, 238)
C_RED = (238, 83, 94)
C_GREEN = (79, 180, 133)
C_TEXT = (248, 250, 255)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def image_or_none(path, size):
    try:
        image = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(image, size)
    except (FileNotFoundError, pygame.error):
        return None


def font(size, bold=False):
    f = pygame.font.Font(None, size)
    f.set_bold(bold)
    return f


def browser_touch_mode(enabled):
    # Keep one finger per paddle and avoid Safari scrolling the canvas.
    try:
        import js
        if enabled:
            js.eval("""(() => {const c=document.querySelector('canvas');if(!c)return;
              if(c.__wasteHockeyBackup===undefined)
                c.__wasteHockeyBackup=[c.style.touchAction,c.style.overscrollBehavior];
              c.style.touchAction='none';c.style.overscrollBehavior='contain';})();""")
        else:
            js.eval("""(() => {const c=document.querySelector('canvas');
              if(!c||c.__wasteHockeyBackup===undefined)return;
              c.style.touchAction=c.__wasteHockeyBackup[0];
              c.style.overscrollBehavior=c.__wasteHockeyBackup[1];
              delete c.__wasteHockeyBackup;})();""")
    except Exception:
        pass


class Hockey:
    def __init__(self, screen):
        self.display = screen
        self.screen_size = screen.get_size()
        scale = min(self.screen_size[0] / WIDTH, self.screen_size[1] / HEIGHT)
        self.scale = scale
        self.dest_rect = pygame.Rect(round((self.screen_size[0] - WIDTH * scale) / 2),
                                     round((self.screen_size[1] - HEIGHT * scale) / 2),
                                     round(WIDTH * scale), round(HEIGHT * scale))
        self.screen = screen if self.screen_size == (WIDTH, HEIGHT) else pygame.Surface((WIDTH, HEIGHT)).convert()
        self.running = True
        self.scene = 'menu'
        self.mode = 2
        self.duration = 60
        self.time_remaining = 60.0
        self.score = [0, 0]
        self.paddles = []
        self.puck = {}
        self.finger_map = {}
        self.player_fingers = [None, None]
        self.mouse_player = None
        self.buttons = {}
        self.goal_player = None
        self.goal_elapsed = 0
        self.particles = []
        self.sparkle_seed = random.Random()
        self.serve_timer = 0.0
        self.serve_direction = -1
        self.text_big = font(60, True)
        self.text_med = font(36, True)
        self.text_mid = font(30, True)
        self.text_small = font(24, True)
        self.text_tiny = font(20)
        self.art = {}
        for name, size in [
            ('field', FIELD_RECT.size),
            ('pusher1', (80, 80)),
            ('pusher2', (80, 80)),
            ('puck', (44, 44)),
        ]:
            self.art[name] = image_or_none('assets/wastehockey/' + name + '.png', size)
        self.home_icon = image_or_none('assets/retBut.png', (54, 54))
        self.rink_background = self.create_background()
        self.new_positions()

    def create_background(self):
        surface = pygame.Surface((WIDTH, HEIGHT)).convert()
        surface.fill(C_DARK)
        if self.art['field'] is not None:
            surface.blit(self.art['field'], FIELD_RECT.topleft)
        else:
            pygame.draw.rect(surface, C_ICE, FIELD_RECT, border_radius=24)
            pygame.draw.rect(surface, C_BLUE, (25, 118, 750, 384), 6, border_radius=22)
            pygame.draw.line(surface, C_RED, (MID_X, TABLE_TOP), (MID_X, TABLE_BOTTOM), 5)
            pygame.draw.circle(surface, C_RED, (int(MID_X), int(MID_Y)), 65, 4)
        pygame.draw.rect(surface, C_DARK, (0, 0, WIDTH, 94))
        pygame.draw.rect(surface, C_DARK, (0, FIELD_RECT.bottom, WIDTH, HEIGHT - FIELD_RECT.bottom))
        return surface

    def new_positions(self):
        self.paddles = [
            {'pos': [175.0, MID_Y], 'target': [175.0, MID_Y], 'vel': [0.0, 0.0]},
            {'pos': [625.0, MID_Y], 'target': [625.0, MID_Y], 'vel': [0.0, 0.0]},
        ]
        self.puck = {'pos': [MID_X, MID_Y], 'vel': [0.0, 0.0]}
        self.serve_timer = 0.65
        self.serve_direction = random.choice((-1, 1))
        self.clear_input()

    def clear_input(self):
        self.finger_map.clear()
        self.player_fingers = [None, None]
        self.mouse_player = None

    def start(self):
        self.score = [0, 0]
        self.time_remaining = float(self.duration or 0)
        self.new_positions()
        self.scene = 'playing'
        self.goal_player = None
        self.particles = []

    def menu(self):
        self.scene = 'menu'
        self.clear_input()

    def time_label(self):
        if self.duration is None:
            return 'ENDLESS'
        seconds = max(0, math.ceil(self.time_remaining))
        return f'{seconds // 60}:{seconds % 60:02d}'

    def to_logical(self, pos):
        if not self.dest_rect.collidepoint(pos):
            return None
        x = (pos[0] - self.dest_rect.left) * WIDTH / self.dest_rect.width
        y = (pos[1] - self.dest_rect.top) * HEIGHT / self.dest_rect.height
        return (x, y)

    def bounds_for(self, player):
        # The head-on collider must never pass the center line or leave the rink.
        margin = PADDLE_RADIUS + 3
        if player == 0:
            return TABLE_LEFT + margin, MID_X - margin - 2
        return MID_X + margin + 2, TABLE_RIGHT - margin

    def target_paddle(self, player, x, y):
        lo, hi = self.bounds_for(player)
        self.paddles[player]['target'] = [
            clamp(x, lo, hi),
            clamp(y, TABLE_TOP + PADDLE_RADIUS + 2, TABLE_BOTTOM - PADDLE_RADIUS - 2),
        ]

    def player_for(self, pos):
        x, y = pos
        if not (TABLE_LEFT <= x <= TABLE_RIGHT and TABLE_TOP <= y <= TABLE_BOTTOM):
            return None
        player = 0 if x < MID_X else 1
        if self.mode == 1 and player == 1:
            return None
        return player

    def activate_button(self, pos):
        for name, rect in self.buttons.items():
            if rect.collidepoint(pos):
                if name == 'one':
                    self.mode = 1
                elif name == 'two':
                    self.mode = 2
                elif name == 'one_min':
                    self.duration = 60
                elif name == 'two_min':
                    self.duration = 120
                elif name == 'endless':
                    self.duration = None
                elif name == 'start':
                    self.start()
                elif name == 'home':
                    self.running = False
                elif name == 'again':
                    self.start()
                elif name == 'settings':
                    self.menu()
                return True
        return False

    def pointer_down(self, pos, source, ident=None):
        if pos is None:
            return
        if self.activate_button(pos):
            return
        if self.scene != 'playing':
            return
        player = self.player_for(pos)
        if player is None or self.player_fingers[player] is not None:
            return
        if source == 'finger':
            self.finger_map[ident] = player
            self.player_fingers[player] = ident
        elif source == 'mouse':
            self.mouse_player = player
        self.target_paddle(player, *pos)

    def pointer_move(self, pos, source, ident=None):
        if pos is None or self.scene != 'playing':
            return
        player = self.finger_map.get(ident) if source == 'finger' else self.mouse_player
        if player is not None:
            self.target_paddle(player, *pos)

    def pointer_up(self, source, ident=None):
        if source == 'finger':
            player = self.finger_map.pop(ident, None)
            if player is not None:
                self.player_fingers[player] = None
        else:
            self.mouse_player = None

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            # Some platforms normalize coordinates to the window including letterbox.
            pos = self.to_logical((event.x * self.screen_size[0], event.y * self.screen_size[1]))
            ident = event.finger_id
            if event.type == pygame.FINGERDOWN:
                self.pointer_down(pos, 'finger', ident)
            elif event.type == pygame.FINGERMOTION:
                self.pointer_move(pos, 'finger', ident)
            else:
                self.pointer_up('finger', ident)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            # Avoid synthetic mouse clicks arriving alongside multitouch events.
            if getattr(event, 'touch', False) or getattr(event, 'which', None) == getattr(pygame, 'TOUCH_MOUSEID', -999):
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.pointer_down(self.to_logical(event.pos), 'mouse')
            elif event.type == pygame.MOUSEMOTION and self.mouse_player is not None:
                self.pointer_move(self.to_logical(event.pos), 'mouse')
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.pointer_up('mouse')

    def update_keyboard(self, dt):
        if self.scene != 'playing':
            return
        keys = pygame.key.get_pressed()
        mappings = (
            (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s),
            (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN),
        )
        for player, (left, right, up, down) in enumerate(mappings):
            if player == 1 and self.mode == 1:
                continue
            if self.player_fingers[player] is not None or self.mouse_player == player:
                continue
            dx = int(keys[right]) - int(keys[left])
            dy = int(keys[down]) - int(keys[up])
            if dx or dy:
                magnitude = math.hypot(dx, dy)
                # Keyboard moves the target directly with responsiveness.
                paddle = self.paddles[player]
                self.target_paddle(player,
                                   paddle['pos'][0] + dx / magnitude * KEYBOARD_SPEED * dt,
                                   paddle['pos'][1] + dy / magnitude * KEYBOARD_SPEED * dt)

    def update_ai(self, dt):
        # Simple defender, intentionally beatable by younger children.
        x, y = self.puck['pos']
        vx = self.puck['vel'][0]
        if x > MID_X + 5 and vx > -70:
            target_x = clamp(x + 72, MID_X + 75, TABLE_RIGHT - 73)
            target_y = y
        else:
            target_x = TABLE_RIGHT - 120
            target_y = MID_Y + (y - MID_Y) * 0.65
        self.target_paddle(1, target_x, target_y)

    def move_paddles(self, h):
        for i, paddle in enumerate(self.paddles):
            dx = paddle['target'][0] - paddle['pos'][0]
            dy = paddle['target'][1] - paddle['pos'][1]
            dist = math.hypot(dx, dy)
            maxspeed = AI_MAX_SPEED if self.mode == 1 and i == 1 else PADDLE_MAX_SPEED
            factor = min(1.0, maxspeed * h / dist) if dist else 1.0
            mx, my = dx * factor, dy * factor
            paddle['pos'][0] += mx
            paddle['pos'][1] += my
            paddle['vel'] = [mx / h, my / h]

    def cap_puck_speed(self):
        vx, vy = self.puck['vel']
        speed = math.hypot(vx, vy)
        if speed > PUCK_MAX_SPEED:
            self.puck['vel'] = [vx * PUCK_MAX_SPEED / speed, vy * PUCK_MAX_SPEED / speed]

    def collide_paddle(self, paddle, player):
        dx = self.puck['pos'][0] - paddle['pos'][0]
        dy = self.puck['pos'][1] - paddle['pos'][1]
        radii = PADDLE_RADIUS + PUCK_RADIUS
        d2 = dx * dx + dy * dy
        if d2 >= radii * radii:
            return
        dist = math.sqrt(d2)
        if dist > 1e-6:
            nx, ny = dx / dist, dy / dist
        else:
            nx, ny = (1, 0) if player == 0 else (-1, 0)
        self.puck['pos'] = [paddle['pos'][0] + nx * (radii + .01),
                            paddle['pos'][1] + ny * (radii + .01)]
        rvx = self.puck['vel'][0] - paddle['vel'][0]
        rvy = self.puck['vel'][1] - paddle['vel'][1]
        approaching = rvx * nx + rvy * ny
        if approaching < 0:
            impulse = -(1 + PADDLE_BOUNCE) * approaching
            self.puck['vel'][0] += impulse * nx
            self.puck['vel'][1] += impulse * ny
            self.cap_puck_speed()

    def score_goal(self, player):
        if self.scene != 'playing':
            return
        self.score[player] += 1
        self.goal_player = player
        self.scene = 'goal'
        self.goal_elapsed = 0.0
        self.puck['vel'] = [0.0, 0.0]
        self.make_confetti(110)
        # Keep existing finger ownership across the short celebration. A child
        # can keep a finger on the glass and resume without lifting it.

    def walls(self):
        px, py = self.puck['pos']
        vx, vy = self.puck['vel']
        r = PUCK_RADIUS
        if py - r < TABLE_TOP:
            py = TABLE_TOP + r
            vy = abs(vy) * WALL_BOUNCE
        elif py + r > TABLE_BOTTOM:
            py = TABLE_BOTTOM - r
            vy = -abs(vy) * WALL_BOUNCE
        goal_open = abs(py - MID_Y) < GOAL_HALF_HEIGHT - r
        if px-r < TABLE_LEFT:
            if goal_open:
                if px+r < TABLE_LEFT:
                    self.score_goal(1)
                    return
            else:
                px = TABLE_LEFT + r
                vx = abs(vx) * WALL_BOUNCE
        elif px+r > TABLE_RIGHT:
            if goal_open:
                if px-r > TABLE_RIGHT:
                    self.score_goal(0)
                    return
            else:
                px = TABLE_RIGHT-r
                vx = -abs(vx) * WALL_BOUNCE
        self.puck['pos'] = [px, py]
        self.puck['vel'] = [vx, vy]

    def make_confetti(self, number):
        colors = (C_YELLOW, C_BLUE, C_RED, C_GREEN, (192, 136, 242), (255, 255, 255))
        self.particles = []
        for i in range(number):
            center_x = WIDTH * .5 + random.uniform(-90,90)
            center_y = HEIGHT * .37 + random.uniform(-30,30)
            ang = random.uniform(0, math.tau)
            speed = random.uniform(95, 390)
            self.particles.append([center_x, center_y,
                                   math.cos(ang)*speed, math.sin(ang)*speed-110,
                                   random.choice(colors), random.uniform(2.0, 5.0)])

    def update_particles(self, dt):
        for p in self.particles:
            p[0] += p[2]*dt
            p[1] += p[3]*dt
            p[3] += 320*dt

    def end_game(self):
        self.time_remaining = 0.0
        self.scene = 'final'
        self.clear_input()
        self.make_confetti(160)

    def update(self, dt):
        if self.scene == 'final':
            self.update_particles(dt)
            return
        if self.scene == 'goal':
            self.goal_elapsed += dt
            self.update_particles(dt)
            if self.goal_elapsed >= GOAL_CELEBRATION_DURATION:
                if self.duration is not None and self.time_remaining <= 0:
                    self.end_game()
                else:
                    self.scene = 'playing'
                    self.puck = {'pos': [MID_X, MID_Y], 'vel': [0.0, 0.0]}
                    self.serve_timer = 0.65
                    self.serve_direction = -1 if self.goal_player == 0 else 1
            return
        if self.scene != 'playing':
            return
        if self.duration is not None:
            self.time_remaining -= dt
            if self.time_remaining <= 0:
                self.end_game()
                return
        if self.mode == 1:
            self.update_ai(dt)
        physics_dt = min(dt, 1.0 / 30.0)
        subdivisions = max(1, math.ceil(physics_dt / (1.0 / 120.0)))
        h = physics_dt / subdivisions
        for _ in range(subdivisions):
            self.move_paddles(h)
            if self.serve_timer > 0:
                self.serve_timer -= h
                if self.serve_timer <= 0:
                    ang = random.uniform(-.30, .30)
                    self.puck['vel'] = [INITIAL_PUCK_SPEED*self.serve_direction*math.cos(ang),
                                        INITIAL_PUCK_SPEED*math.sin(ang)]
                continue
            self.puck['pos'][0] += self.puck['vel'][0]*h
            self.puck['pos'][1] += self.puck['vel'][1]*h
            friction = 0.997**(h*FPS)
            self.puck['vel'][0] *= friction
            self.puck['vel'][1] *= friction
            for player, paddle in enumerate(self.paddles):
                self.collide_paddle(paddle, player)
            self.walls()
            if self.scene != 'playing':
                break

    def centered(self, text, fnt, color, center):
        surf = fnt.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=(int(center[0]), int(center[1]))))

    def box(self, rect, color, radius=18, border=(252, 252, 255)):
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        pygame.draw.rect(self.screen, border, rect, 3, border_radius=radius)

    def button(self, ident, rect, text, selected=False, color=None, text_color=C_TEXT):
        self.buttons[ident] = rect
        bg = (62, 153, 193) if selected else (38, 94, 137)
        if color is not None:
            bg = color
        self.box(rect, bg, 12)
        self.centered(text, self.text_mid if rect.h>=50 else self.text_small, text_color, rect.center)

    def draw_home(self):
        self.buttons['home'] = HOME_RECT
        self.box(HOME_RECT, (233, 128, 68), 12)
        if self.home_icon is not None:
            self.screen.blit(self.home_icon, self.home_icon.get_rect(center=HOME_RECT.center))
        else:
            self.centered('HOME', self.text_small, C_TEXT, HOME_RECT.center)

    def draw_menu(self):
        # Slightly darken rink; children can still see what game they are choosing.
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((9, 31, 50, 175))
        self.screen.blit(shade, (0, 0))
        self.box(pygame.Rect(133, 82, 534, 457), C_PANEL, 25)
        self.centered('WASTE HOCKEY', self.text_big, C_YELLOW, (400, 126))
        self.centered('HOW MANY PLAYERS?', self.text_mid, C_TEXT, (400, 193))
        self.button('one', pygame.Rect(186, 219, 200, 56), '1 PLAYER', self.mode == 1,
                    C_GREEN if self.mode == 1 else None)
        self.button('two', pygame.Rect(413, 219, 200, 56), '2 PLAYERS', self.mode == 2,
                    C_GREEN if self.mode == 2 else None)
        self.centered('HOW LONG?', self.text_mid, C_TEXT, (400, 324))
        self.button('one_min', pygame.Rect(165, 351, 146, 52), '1 MIN', self.duration == 60,
                    C_GREEN if self.duration == 60 else None)
        self.button('two_min', pygame.Rect(326, 351, 146, 52), '2 MIN', self.duration == 120,
                    C_GREEN if self.duration == 120 else None)
        self.button('endless', pygame.Rect(487, 351, 146, 52), 'ENDLESS', self.duration is None,
                    C_GREEN if self.duration is None else None)
        self.button('start', pygame.Rect(280, 439, 240, 65), 'PLAY!', color=(225, 117, 63))
        self.draw_home()

    def draw_paddles_and_puck(self):
        for player, paddle in enumerate(self.paddles):
            pt = (round(paddle['pos'][0]),round(paddle['pos'][1]))
            img = self.art['pusher1' if player == 0 else 'pusher2']
            if img is not None:
                self.screen.blit(img, img.get_rect(center=pt))
            else:
                pygame.draw.circle(self.screen, C_YELLOW if player == 0 else C_BLUE, pt, int(PADDLE_RADIUS))
                pygame.draw.circle(self.screen, C_TEXT, pt, int(PADDLE_RADIUS), 3)
        pt = (round(self.puck['pos'][0]),round(self.puck['pos'][1]))
        img = self.art['puck']
        if img is not None:
            self.screen.blit(img, img.get_rect(center=pt))
        else:
            pygame.draw.circle(self.screen, C_RED, pt, int(PUCK_RADIUS))

    def draw_play(self):
        # No debug goal markers: goals are already part of the background picture.
        self.draw_paddles_and_puck()
        self.draw_home()
        pygame.draw.circle(self.screen, C_YELLOW, (135, 48), 12)
        pygame.draw.circle(self.screen, C_BLUE, (492, 48), 12)
        self.centered('YOU' if self.mode == 1 else 'P1', self.text_small, C_TEXT, (197, 48))
        self.centered('CPU' if self.mode == 1 else 'P2', self.text_small, C_TEXT, (545, 48))
        self.centered(str(self.score[0]), self.text_big, C_YELLOW, (311, 48))
        self.centered(':', self.text_big, C_TEXT, (392, 48))
        self.centered(str(self.score[1]), self.text_big, C_BLUE, (454, 48))
        self.centered(self.time_label(), self.text_med, C_TEXT, (700, 48))
        hint = 'Use your finger to move the yellow paddle' if self.mode == 1 else 'Each player uses one finger on their own half'
        self.centered(hint, self.text_small, C_TEXT, (WIDTH/2, 553))

    def draw_confetti(self):
        for x,y,vx,vy,color,r in self.particles:
            if -10 < x < WIDTH+10 and -10 < y < HEIGHT+10:
                pygame.draw.circle(self.screen, color, (round(x),round(y)), max(2,round(r)))

    def draw_goal_overlay(self):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((13, 35, 56, 95))
        self.screen.blit(shade, (0, 0))
        self.draw_confetti()
        self.box(pygame.Rect(230, 225, 340, 155), (20, 71, 113), 26)
        self.centered('GOAL!', self.text_big, C_YELLOW, (400, 279))
        player = 'YOU' if self.mode == 1 and self.goal_player == 0 else \
                 'COMPUTER' if self.mode == 1 else f'PLAYER {self.goal_player + 1}'
        self.centered(player + ' SCORES!', self.text_mid, C_TEXT, (400, 340))

    def draw_final(self):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((11, 34, 53, 196))
        self.screen.blit(shade, (0, 0))
        self.draw_confetti()
        self.box(pygame.Rect(145, 105, 510, 410), C_PANEL, 25)
        self.centered('TIME IS UP!', self.text_big, C_YELLOW, (400, 162))
        self.centered(f'{self.score[0]}  :  {self.score[1]}', self.text_big, C_TEXT, (400, 250))
        if self.score[0] == self.score[1]:
            winner = 'IT\'S A DRAW!'
        elif self.score[0] > self.score[1]:
            winner = 'YOU WIN!' if self.mode == 1 else 'PLAYER 1 WINS!'
        else:
            winner = 'COMPUTER WINS!' if self.mode == 1 else 'PLAYER 2 WINS!'
        self.centered(winner, self.text_med, C_YELLOW, (400, 325))
        self.button('again', pygame.Rect(172, 394, 213, 64), 'PLAY AGAIN', color=C_GREEN)
        self.button('settings', pygame.Rect(412, 394, 213, 64), 'CHANGE MODE')
        self.draw_home()

    def draw(self):
        self.screen.blit(self.rink_background, (0,0))
        self.buttons = {}
        if self.scene == 'menu':
            self.draw_menu()
        else:
            self.draw_play()
            if self.scene == 'goal':
                self.draw_goal_overlay()
            elif self.scene == 'final':
                self.draw_final()
        if self.screen is not self.display:
            # Use native dimensions when possible; letterbox if GameHub uses another size.
            self.display.fill(C_DARK)
            img = pygame.transform.smoothscale(self.screen, self.dest_rect.size)
            self.display.blit(img, self.dest_rect.topleft)
        pygame.display.flip()


async def main(screen=None, clock=None):
    """Drop-in entry point for the existing GameHub launcher."""
    standalone = screen is None
    if screen is None:
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    if clock is None:
        clock = pygame.time.Clock()
    game = Hockey(screen)
    browser_touch_mode(True)
    try:
        while game.running:
            # Count match time using elapsed time, even on slower devices;
            # the physics solver separately caps its integration step.
            dt = min(clock.tick(FPS)/1000.0, 0.15)
            for event in pygame.event.get():
                game.handle_event(event)
            if not game.running:
                break
            game.update_keyboard(min(dt, 1.0/30.0))
            game.update(dt)
            game.draw()
            await asyncio.sleep(0)
    finally:
        browser_touch_mode(False)
    return


if __name__ == '__main__':
    asyncio.run(main())
