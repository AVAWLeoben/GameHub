# -*- coding: utf-8 -*-
"""Two-player air hockey for Pygbag / Pygame (no Pymunk).

Drop-in replacement for wasteHockey.py. The game hub calls:
    await wasteHockey.main(screen, clock)

On tablets, each player controls the paddle on their half with one finger.
Desktop: drag with the mouse, or use WASD (left) and arrow keys (right).
Physics uses circles, velocity, friction, and simple collision impulses.
"""

import asyncio
import math
import random

import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60
TABLE_LEFT, TABLE_RIGHT = 36, WIDTH - 36
TABLE_TOP, TABLE_BOTTOM = 88, HEIGHT - 60
MID_X, MID_Y = WIDTH // 2, (TABLE_TOP + TABLE_BOTTOM) // 2
GOAL_HALF_HEIGHT = 95
PADDLE_RADIUS = 42
PUCK_RADIUS = 23
PADDLE_MAX_SPEED = 1150.0        # px / second: avoid teleporting paddles
PUCK_MAX_SPEED = 850.0          # px / second
INITIAL_PUCK_SPEED = 320.0
KEYBOARD_SPEED = 780.0
WALL_BOUNCE = 0.96
PADDLE_BOUNCE = 0.92
HOME_RECT = pygame.Rect(12, 12, 58, 56)


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def load_image(path, size, white_transparent=False):
    """Artwork is optional; circles and a drawn field work without assets."""
    try:
        image = pygame.image.load(path).convert_alpha()
        image = pygame.transform.smoothscale(image, size)
        if white_transparent:
            image.set_colorkey((255, 255, 255))
        return image
    except (FileNotFoundError, pygame.error):
        return None


def browser_touch_mode(enabled):
    """Keep touches on the canvas from triggering normal page gestures.

    We restore the previous CSS when returning to the game menu. Safari's
    system-level gestures cannot be disabled by a webpage.
    """
    try:
        import js
        if enabled:
            js.eval("""(function () {
                const c = document.querySelector('canvas');
                if (!c) return;
                if (c.__hockeyTouchBackup === undefined) {
                    c.__hockeyTouchBackup = [c.style.touchAction, c.style.overscrollBehavior];
                }
                c.style.touchAction = 'none';
                c.style.overscrollBehavior = 'contain';
            })();""")
        else:
            js.eval("""(function () {
                const c = document.querySelector('canvas');
                if (!c || c.__hockeyTouchBackup === undefined) return;
                c.style.touchAction = c.__hockeyTouchBackup[0];
                c.style.overscrollBehavior = c.__hockeyTouchBackup[1];
                delete c.__hockeyTouchBackup;
            })();""")
    except Exception:
        # On desktop Python there is no browser; touch inputs still work.
        pass


class AirHockey:
    def __init__(self, screen):
        self.screen = screen
        self.running = True
        self.score = [0, 0]
        self.paddles = [
            {"pos": [155.0, float(MID_Y)], "target": [155.0, float(MID_Y)], "vel": [0.0, 0.0]},
            {"pos": [645.0, float(MID_Y)], "target": [645.0, float(MID_Y)], "vel": [0.0, 0.0]},
        ]
        self.puck = {"pos": [float(MID_X), float(MID_Y)], "vel": [0.0, 0.0]}
        self.serve_timer = 0.8
        self.serve_direction = random.choice((-1, 1))

        # finger_id -> player index; different fingers can operate concurrently
        self.fingers = {}
        self.player_finger = [None, None]
        self.mouse_player = None

        self.field_image = load_image("assets/wastehockey/field.png", (WIDTH, HEIGHT))
        self.paddle_images = [
            load_image("assets/wastehockey/pusher1.png", (PADDLE_RADIUS * 2,) * 2, True),
            load_image("assets/wastehockey/pusher2.png", (PADDLE_RADIUS * 2,) * 2, True),
        ]
        self.puck_image = load_image("assets/wastehockey/puck.png", (PUCK_RADIUS * 2,) * 2, True)
        self.home_image = load_image("assets/retBut.png", HOME_RECT.size)
        self.score_font = pygame.font.Font(None, 46)
        self.small_font = pygame.font.Font(None, 25)

    def bounds_for(self, player):
        # Paddles never cross the center line or exit the inset play area.
        gap = PADDLE_RADIUS + PUCK_RADIUS + 8
        lo = TABLE_LEFT + PADDLE_RADIUS + 4
        hi = TABLE_RIGHT - PADDLE_RADIUS - 4
        if player == 0:
            return lo, MID_X - gap
        return MID_X + gap, hi

    def target_paddle(self, player, x, y):
        left, right = self.bounds_for(player)
        self.paddles[player]["target"] = [
            clamp(x, left, right),
            clamp(y, TABLE_TOP + PADDLE_RADIUS + 3, TABLE_BOTTOM - PADDLE_RADIUS - 3),
        ]

    def player_for(self, pos):
        x, y = pos
        if not (TABLE_LEFT <= x <= TABLE_RIGHT and TABLE_TOP <= y <= TABLE_BOTTOM):
            return None
        return 0 if x < MID_X else 1

    def handle_event(self, event):
        kind = event.type
        if kind == pygame.QUIT:
            self.running = False
            return
        if kind == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.running = False
            return

        # SDL2 finger coordinates are normalized to 0..1 for each screen axis.
        if kind in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            finger_id = event.finger_id
            pos = (event.x * WIDTH, event.y * HEIGHT)
            if kind == pygame.FINGERDOWN:
                if HOME_RECT.collidepoint(pos):
                    self.running = False
                    return
                player = self.player_for(pos)
                if player is not None and self.player_finger[player] is None:
                    self.fingers[finger_id] = player
                    self.player_finger[player] = finger_id
                    self.target_paddle(player, *pos)
            elif kind == pygame.FINGERMOTION:
                player = self.fingers.get(finger_id)
                if player is not None:
                    self.target_paddle(player, *pos)
            else:  # FINGERUP
                player = self.fingers.pop(finger_id, None)
                if player is not None:
                    self.player_finger[player] = None
            return

        # Some platforms send a synthetic mouse event with each touch; ignore it.
        if kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            if getattr(event, "touch", False) or getattr(event, "which", None) == getattr(pygame, "TOUCH_MOUSEID", -1):
                return
            if kind == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if HOME_RECT.collidepoint(event.pos):
                    self.running = False
                    return
                player = self.player_for(event.pos)
                if player is not None and self.player_finger[player] is None:
                    self.mouse_player = player
                    self.target_paddle(player, *event.pos)
            elif kind == pygame.MOUSEMOTION and self.mouse_player is not None:
                self.target_paddle(self.mouse_player, *event.pos)
            elif kind == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_player = None

    def update_keyboard(self, dt):
        pressed = pygame.key.get_pressed()
        mapping = (
            (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s),
            (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN),
        )
        for player, (left, right, up, down) in enumerate(mapping):
            if self.player_finger[player] is not None or self.mouse_player == player:
                continue
            dx = float(bool(pressed[right])) - float(bool(pressed[left]))
            dy = float(bool(pressed[down])) - float(bool(pressed[up]))
            if dx or dy:
                length = math.hypot(dx, dy)
                p = self.paddles[player]
                self.target_paddle(
                    player, p["pos"][0] + dx / length * KEYBOARD_SPEED * dt,
                    p["pos"][1] + dy / length * KEYBOARD_SPEED * dt,
                )

    def move_paddles(self, dt):
        for paddle in self.paddles:
            dx = paddle["target"][0] - paddle["pos"][0]
            dy = paddle["target"][1] - paddle["pos"][1]
            distance = math.hypot(dx, dy)
            fraction = min(1.0, (PADDLE_MAX_SPEED * dt) / distance) if distance > 0 else 1.0
            move_x, move_y = dx * fraction, dy * fraction
            paddle["pos"][0] += move_x
            paddle["pos"][1] += move_y
            paddle["vel"] = [move_x / dt, move_y / dt]

    def collide_paddle(self, paddle):
        dx = self.puck["pos"][0] - paddle["pos"][0]
        dy = self.puck["pos"][1] - paddle["pos"][1]
        radius = PADDLE_RADIUS + PUCK_RADIUS
        distance_sq = dx * dx + dy * dy
        if distance_sq >= radius * radius:
            return

        distance = math.sqrt(distance_sq)
        if distance > 0.0001:
            nx, ny = dx / distance, dy / distance
        else:
            # Rare case: same exact center; choose a reliable separation axis.
            nx, ny = (1.0, 0.0) if paddle is self.paddles[0] else (-1.0, 0.0)
        # Resolve overlap first so the puck cannot get stuck inside a paddle.
        self.puck["pos"][0] = paddle["pos"][0] + nx * (radius + 0.01)
        self.puck["pos"][1] = paddle["pos"][1] + ny * (radius + 0.01)

        # Reflect relative velocity so moving paddles transfer momentum.
        rvx = self.puck["vel"][0] - paddle["vel"][0]
        rvy = self.puck["vel"][1] - paddle["vel"][1]
        normal_speed = rvx * nx + rvy * ny
        if normal_speed < 0:
            impulse = -(1.0 + PADDLE_BOUNCE) * normal_speed
            self.puck["vel"][0] += impulse * nx
            self.puck["vel"][1] += impulse * ny
            self.cap_puck_speed()

    def cap_puck_speed(self):
        vx, vy = self.puck["vel"]
        speed = math.hypot(vx, vy)
        if speed > PUCK_MAX_SPEED:
            scale = PUCK_MAX_SPEED / speed
            self.puck["vel"] = [vx * scale, vy * scale]

    def goal(self, scoring_player):
        self.score[scoring_player] += 1
        self.puck["pos"] = [float(MID_X), float(MID_Y)]
        self.puck["vel"] = [0.0, 0.0]
        self.serve_timer = 0.85
        # Send the restart toward the player who conceded the point.
        self.serve_direction = 1 if scoring_player == 0 else -1

    def handle_walls_and_goals(self):
        px, py = self.puck["pos"]
        vx, vy = self.puck["vel"]
        r = PUCK_RADIUS
        if py - r < TABLE_TOP:
            py = TABLE_TOP + r
            vy = abs(vy) * WALL_BOUNCE
        elif py + r > TABLE_BOTTOM:
            py = TABLE_BOTTOM - r
            vy = -abs(vy) * WALL_BOUNCE

        # The entire puck must fit between the goal posts to pass through.
        inside_goal = abs(py - MID_Y) < GOAL_HALF_HEIGHT - r
        if px - r < TABLE_LEFT:
            if inside_goal:
                if px + r < TABLE_LEFT:
                    self.goal(1)
                    return
            else:
                px = TABLE_LEFT + r
                vx = abs(vx) * WALL_BOUNCE
        elif px + r > TABLE_RIGHT:
            if inside_goal:
                if px - r > TABLE_RIGHT:
                    self.goal(0)
                    return
            else:
                px = TABLE_RIGHT - r
                vx = -abs(vx) * WALL_BOUNCE
        self.puck["pos"] = [px, py]
        self.puck["vel"] = [vx, vy]

    def step(self, dt):
        # Substeps reduce missed collisions on slower tablets.
        subdivisions = max(1, math.ceil(dt / (1.0 / 120.0)))
        h = dt / subdivisions
        for _ in range(subdivisions):
            self.move_paddles(h)
            if self.serve_timer > 0:
                self.serve_timer -= h
                if self.serve_timer <= 0:
                    angle = random.uniform(-0.32, 0.32)
                    self.puck["vel"] = [
                        INITIAL_PUCK_SPEED * self.serve_direction * math.cos(angle),
                        INITIAL_PUCK_SPEED * math.sin(angle),
                    ]
                continue

            # Time-based motion and mild friction (independent of frame rate).
            self.puck["pos"][0] += self.puck["vel"][0] * h
            self.puck["pos"][1] += self.puck["vel"][1] * h
            drag = 0.996 ** (h * FPS)
            self.puck["vel"][0] *= drag
            self.puck["vel"][1] *= drag
            for paddle in self.paddles:
                self.collide_paddle(paddle)
            self.handle_walls_and_goals()

    def draw(self):
        screen = self.screen
        if self.field_image is None:
            screen.fill((19, 83, 113))
        else:
            screen.blit(self.field_image, (0, 0))
        table_rect = pygame.Rect(TABLE_LEFT, TABLE_TOP, TABLE_RIGHT - TABLE_LEFT, TABLE_BOTTOM - TABLE_TOP)
        pygame.draw.rect(screen, (227, 240, 244), table_rect, 4)
        pygame.draw.line(screen, (223, 235, 241), (MID_X, TABLE_TOP), (MID_X, TABLE_BOTTOM), 3)
        pygame.draw.circle(screen, (223, 235, 241), (MID_X, MID_Y), 75, 3)
        for x in (TABLE_LEFT, TABLE_RIGHT):
            pygame.draw.line(screen, (111, 240, 146),
                             (x, MID_Y - GOAL_HALF_HEIGHT), (x, MID_Y + GOAL_HALF_HEIGHT), 9)
            for y in (MID_Y - GOAL_HALF_HEIGHT, MID_Y + GOAL_HALF_HEIGHT):
                pygame.draw.circle(screen, (255, 234, 130), (x, y), 8)

        for player, paddle in enumerate(self.paddles):
            pos = tuple(round(v) for v in paddle["pos"])
            image = self.paddle_images[player]
            if image is None:
                color = (62, 176, 255) if player == 0 else (255, 103, 89)
                pygame.draw.circle(screen, color, pos, PADDLE_RADIUS)
                pygame.draw.circle(screen, (244, 246, 252), pos, PADDLE_RADIUS, 4)
            else:
                screen.blit(image, image.get_rect(center=pos))

        pos = tuple(round(v) for v in self.puck["pos"])
        if self.puck_image is None:
            pygame.draw.circle(screen, (28, 34, 42), pos, PUCK_RADIUS)
            pygame.draw.circle(screen, (246, 246, 250), pos, PUCK_RADIUS, 3)
        else:
            screen.blit(self.puck_image, self.puck_image.get_rect(center=pos))

        pygame.draw.rect(screen, (12, 40, 59), (0, 0, WIDTH, TABLE_TOP))
        score_text = self.score_font.render(f"{self.score[0]}  :  {self.score[1]}", True, (255, 255, 255))
        screen.blit(score_text, score_text.get_rect(center=(MID_X, 31)))
        hint_left = self.small_font.render("BLUE - left side", True, (138, 207, 255))
        hint_right = self.small_font.render("RED - right side", True, (255, 168, 155))
        screen.blit(hint_left, (90, 26))
        screen.blit(hint_right, (WIDTH - 90 - hint_right.get_width(), 26))
        if self.home_image:
            screen.blit(self.home_image, HOME_RECT)
        else:
            pygame.draw.rect(screen, (45, 91, 121), HOME_RECT, border_radius=10)
            arrow = self.small_font.render("<", True, (255, 255, 255))
            screen.blit(arrow, arrow.get_rect(center=HOME_RECT.center))
        pygame.display.flip()


async def main(screen=None, clock=None):
    """Entry point used by the game menu and compatible with Pygbag."""
    if screen is None:
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    if clock is None:
        clock = pygame.time.Clock()
    game = AirHockey(screen)
    browser_touch_mode(True)
    try:
        while game.running:
            dt = min(clock.tick(FPS) / 1000.0, 1.0 / 30.0)
            for event in pygame.event.get():
                game.handle_event(event)
            if not game.running:
                break
            game.update_keyboard(dt)
            game.step(dt)
            game.draw()
            await asyncio.sleep(0)
    finally:
        browser_touch_mode(False)


if __name__ == "__main__":
    asyncio.run(main())
