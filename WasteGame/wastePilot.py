import pygame
import math
import asyncio
import pygame.surfarray
import random as rd
import numpy as np
from GUI import Button


def tint_image(image, tint_color):
    """Returns a new image tinted with the given RGB color."""
    tinted_image = image.copy()
    tinted_image.fill((0, 0, 0, 255), None, pygame.BLEND_RGBA_MULT)  # remove original color
    tinted_image.fill(tint_color[0:3] + (0,), None, pygame.BLEND_RGBA_ADD)  # apply tint
    return tinted_image


class Coin:
    IMAGES = [
        pygame.image.load("assets/wastePilot/coin/star coin rotate 1.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 2.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 3.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 4.png"),
        pygame.image.load("assets/wastePilot/coin/star coin rotate 5.png"),
    ]

    def __init__(self, x=900, y=700):

        self.x = x
        self.y = y
        self.z = 200000
        self.image = self.IMAGES[0]
        self.draw_image = self.image.copy()
        self.rect = self.draw_image.get_rect()
        self.draw_dist = 40000000000
        self.frame_counter = 0  # frame counter to track animation progress
        self.distance_to_player = 0
        self.bob_phase = rd.uniform(0, 2 * math.pi)  # random phase between 0 and 2π

    def update(self):
        self.frame_counter += 1

        # Number of frames per image (change this to speed up/down animation)
        frames_per_image = 5

        # Calculate current image index based on frame_counter
        current_image_index = (self.frame_counter // frames_per_image) % len(self.IMAGES)
        self.image = self.IMAGES[current_image_index]

        dx = self.x - player_x
        dy = self.y - player_y

        # Distance from player to sprite
        distance = math.sqrt(dx * dx + dy * dy)
        self.distance_to_player = distance
        if distance < 0.1:
            # Avoid division by zero or too close
            self.rect.topleft = (-9999, -9999)
            return

        if distance < 150:
            # Get coin screen position
            coin_screen_pos = self.rect.center
            target_pos = (750, 40)  # Position of COIN_COUNT on screen

            for i in range(10):
                delay = i * 2  # Stagger animation
                FLYING_COINS.append(FlyingCoin(coin_screen_pos, target_pos, delay_frames=delay))

            COINS.remove(self)
            return  # Skip rest

        # Player's view direction vector
        player_dir_x = math.cos(math.radians(player_angle))
        player_dir_y = math.sin(math.radians(player_angle))

        # Angle between player direction and sprite vector
        sprite_angle = math.degrees(math.atan2(dy, dx))
        player_angle_deg = player_angle % 360

        # Calculate relative angle between player's view and sprite
        relative_angle = (sprite_angle - player_angle_deg + 360) % 360
        if relative_angle > 180:
            relative_angle -= 360  # Normalize to [-180, 180]

        # Field of View (FOV) in degrees, say 60 degrees total (±30)
        FOV = 60
        half_FOV = FOV / 2

        if abs(relative_angle) > half_FOV:
            # Sprite outside player's FOV, don't draw
            self.rect.topleft = (-9999, -9999)
            return

        # Screen projection
        screen_width = SCREEN.get_width()
        screen_center_x = screen_width / 2

        # Horizontal position: map relative_angle to screen_x
        screen_x = screen_center_x - (relative_angle / half_FOV) * (screen_width / 2)

        # Vertical position - simple projection based on distance and sprite height
        # Add bobbing using a sine wave
        bob_offset = int(5 * math.sin(pygame.time.get_ticks() * 0.005 + self.bob_phase))
        screen_y = 200 + int(player_v) + bob_offset

        # Size scaling factor based on distance
        size = max(5, min(100, 30000 / distance))

        # Get original image size
        orig_width, orig_height = self.image.get_size()

        # Calculate new width and height preserving aspect ratio
        if orig_width >= orig_height:
            new_width = int(size)
            new_height = int(orig_height * size / orig_width)
        else:
            new_height = int(size)
            new_width = int(orig_width * size / orig_height)

        self.draw_image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.draw_image.get_rect(center=(int(screen_x), int(screen_y)))

    def draw(self):
        SCREEN.blit(self.draw_image, self.rect)


class FlyingCoin:
    IMAGE = pygame.transform.scale(Coin.IMAGES[0], (16, 16))  # Small version

    def __init__(self, start_pos, target_pos, delay_frames=0):
        self.x, self.y = start_pos
        self.target_x, self.target_y = target_pos
        self.progress = 0.0
        self.speed = 0.03  # Speed of animation
        self.arrived = False
        self.delay_frames = delay_frames  # For staggered animation
        self.current_frame = 0

    def update(self):
        global COIN_COUNT
        if self.arrived:
            COIN_COUNT += 1
            return

        if self.current_frame < self.delay_frames:
            self.current_frame += 1
            return

        self.progress += self.speed
        if self.progress >= 1.0:
            self.arrived = True
            return

        # Lerp to target
        self.x = self.x * (1 - self.progress) + self.target_x * self.progress
        self.y = self.y * (1 - self.progress) + self.target_y * self.progress

    def draw(self):
        if not self.arrived and self.current_frame >= self.delay_frames:
            SCREEN.blit(self.IMAGE, (int(self.x), int(self.y)))


def ret():
    global RUNNING
    RUNNING = False


def drawSky():
    global x_offset
    horizon_y = 200 + int(player_v)
    screen_w = SCREEN.get_width()
    # Parallax offset: shift horizontally based on vertical movement
    if abs(player_v) >= 0:
        x_offset += 1
    if x_offset > 800:
        x_offset = 0
    for line in range(0, horizon_y):
        scalefactor = 1 + (line / 500)

        # Wrap around the sky texture horizontally (parallax wrap)
        line_x_start = x_offset % SKYIMAGE.get_width()
        drawline = SKYIMAGE.subsurface((line_x_start, line), (min(800, SKYIMAGE.get_width() - line_x_start), 1))

        # In case we wrapped, concatenate two pieces
        if drawline.get_width() < 800:
            remainder = 800 - drawline.get_width()
            second_piece = SKYIMAGE.subsurface((0, line), (remainder, 1))
            drawline = pygame.Surface((800, 1))
            drawline.blit(SKYIMAGE, (0, 0), (line_x_start, line, 800 - remainder, 1))
            drawline.blit(second_piece, (800 - remainder, 0))

        # Scale line width for perspective effect
        drawline_scaled = pygame.transform.scale_by(drawline, (scalefactor, 1))

        # Center horizontally on screen
        drawline_rect = drawline_scaled.get_rect(center=(screen_w // 2, line))
        SCREEN.blit(drawline_scaled, drawline_rect)


def draw_mode7_ground(surface, player_x, player_y, player_angle):
    width, height = surface.get_size()
    map_w, map_h = map_image_orig.get_size()
    horizon_y = 200 + int(player_v)
    drawSky()
    angle_rad = math.radians(player_angle)
    left_angle = angle_rad + math.pi / 4
    right_angle = angle_rad - math.pi / 4

    cos_left, sin_left = math.cos(left_angle), math.sin(left_angle)
    cos_right, sin_right = math.cos(right_angle), math.sin(right_angle)

    screen_array = pygame.surfarray.pixels3d(surface)

    # Vectorize across all scanlines
    screen_ys = np.arange(horizon_y, height, 2)
    rel_ys = screen_ys - horizon_y + 1
    distances = player_height / rel_ys

    # Interpolated left/right world positions
    lx = player_x + distances * cos_left
    ly = player_y + distances * sin_left
    rx = player_x + distances * cos_right
    ry = player_y + distances * sin_right

    # Normalized horizontal positions
    t = np.linspace(0, 1, width).reshape((1, -1))  # Shape (1, width)
    lx = lx.reshape((-1, 1))  # Shape (n, 1)
    ly = ly.reshape((-1, 1))
    rx = rx.reshape((-1, 1))
    ry = ry.reshape((-1, 1))

    # Interpolated map coords for each screen row
    xs = ((lx + t * (rx - lx)) % map_w).astype(int)
    ys = ((ly + t * (ry - ly)) % map_h).astype(int)

    # Fill screen lines in batches
    colors = map_array[xs, ys]

    for i, screen_y in enumerate(screen_ys):
        screen_array[:, screen_y] = colors[i]
        if screen_y + 1 < height:
            screen_array[:, screen_y + 1] = colors[i]

    del screen_array


def setup():
    global HOME_BUTTON, player_x, player_y, player_angle, player_v, player_a, map_image_orig, map_width, cockpit
    global stick_L, stick_R, stick_M, player_height, frame, map_height
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    global COIN_IMAGE
    COIN_IMAGE = pygame.image.load("assets/wastePilot/coin/star coin rotate 1.png")

    global SKYIMAGE
    SKYIMAGE = pygame.image.load("assets/wastePilot/sky.png")
    global x_offset
    x_offset = 0
    global COIN_COUNT
    COIN_COUNT = 0

    global FLYING_COINS
    FLYING_COINS = []

    # Player starting position and angle
    player_x = 800
    player_y = 600
    player_angle = -90
    player_v = 0
    player_a = 5

    # Load map
    map_image_orig = pygame.image.load("assets/wastePilot/map_lrg.png").convert()
    map_image_orig = pygame.transform.scale_by(map_image_orig, (1, 1))
    map_width, map_height = map_image_orig.get_size()

    # Create minimap
    global minimap
    minimap = pygame.transform.scale(map_image_orig, (map_width // 10, map_height // 10))

    global map_array
    map_array = pygame.surfarray.array3d(map_image_orig)

    # Load Cockpit
    cockpit = pygame.image.load("assets/wastePilot/cockpit_2.png").convert_alpha()
    stick_L = pygame.image.load("assets/wastePilot/stick.png").convert_alpha()
    stick_R = pygame.transform.flip(stick_L, 1, 0)
    stick_M = pygame.image.load("assets/wastePilot/stick_M.png").convert_alpha()

    player_height = 200000
    frame = 0

    # Create Coins
    create_coins()


def create_coins(num_coins=100):
    global COINS
    COINS = []
    for _ in range(num_coins):
        coin = Coin()
        coin.x = rd.randint(0, map_width - 1)
        coin.y = rd.randint(0, map_height - 1)
        COINS.append(coin)


def draw_coin_count():
    # Blit the coin image at (700, 0)
    coin_pos = (700, 0)
    SCREEN.blit(COIN_IMAGE, coin_pos)

    # Prepare font for drawing coin count (adjust size as needed)
    font = pygame.font.SysFont(None, 30)  # None = default font, 30 = font size

    # Render the coin count text
    coin_text = font.render(str(COIN_COUNT), True, pygame.Color("white"))

    # Center the text on the coin image
    coin_rect = COIN_IMAGE.get_rect(topleft=coin_pos)
    text_rect = coin_text.get_rect(center=coin_rect.center)

    # Optionally add a shadow for better visibility
    shadow = font.render(str(COIN_COUNT), True, pygame.Color("black"))
    shadow_rect = shadow.get_rect(center=text_rect.center)
    shadow_rect.move_ip(1, 1)
    SCREEN.blit(shadow, shadow_rect)

    # Blit the text
    SCREEN.blit(coin_text, text_rect)


def draw_minimap():
    if 1 == 2:
        # Create minimap
        minimap_scale = 20
        global minimap
        minimap = pygame.transform.scale(map_image_orig, (map_width // minimap_scale, map_height // minimap_scale))
        # # Draw player dot
        px = int(player_x // minimap_scale)
        py = int(player_y // minimap_scale)
        pygame.draw.circle(minimap, pygame.Color("red"), (px, py), 5)
        # Draw viewing direction lines
        dir_length = 15  # Length of the direction line
        angle_rad = math.radians(player_angle)

        # Forward line
        fx = int(px + math.cos(angle_rad) * dir_length)
        fy = int(py + math.sin(angle_rad) * dir_length)
        pygame.draw.line(minimap, pygame.Color("yellow"), (px, py), (fx, fy), 2)

        # Left "shoulder" line (FOV indicator)
        left_angle = angle_rad + math.radians(30)
        lx = int(px + math.cos(left_angle) * dir_length)
        ly = int(py + math.sin(left_angle) * dir_length)
        pygame.draw.line(minimap, pygame.Color("gray"), (px, py), (lx, ly), 1)

        # Right "shoulder" line (FOV indicator)
        right_angle = angle_rad - math.radians(30)
        rx = int(px + math.cos(right_angle) * dir_length)
        ry = int(py + math.sin(right_angle) * dir_length)
        pygame.draw.line(minimap, pygame.Color("gray"), (px, py), (rx, ry), 1)
        SCREEN.blit(minimap, (800 - minimap.get_width(), 0))


def draw_cockpit():
    global player_angle, player_v, player_height
    SCREEN.blit(cockpit, (0, 0))

    draw_coin_count()

    # Positions for each control
    pos_L = (0, 600 - stick_L.get_height())
    pos_LM = (200, 600 - stick_L.get_height())
    pos_R = (800 - stick_R.get_width(), 600 - stick_R.get_height())
    pos_RM = (600, 600 - stick_R.get_height())
    pos_M = (SCREEN.get_rect().centerx - stick_M.get_width() // 2, 600 - stick_M.get_height())

    # Get actual button rects
    rect_L = stick_L.get_rect(topleft=pos_L)
    rect_R = stick_R.get_rect(topleft=pos_R)
    rect_M = stick_M.get_rect(topleft=pos_M)
    rect_RM = stick_R.get_rect(topleft=pos_RM)
    rect_LM = stick_L.get_rect(topleft=pos_LM)

    # Input handling
    mouse_pos = pygame.mouse.get_pos()
    finger_down = pygame.mouse.get_pressed()[0]

    # Flags to indicate pressed state
    pressed_L = pressed_R = pressed_M = pressed_LM = pressed_RM = False

    if finger_down:
        if rect_L.collidepoint(mouse_pos):
            player_angle += 2
            pressed_L = True
        elif rect_R.collidepoint(mouse_pos):
            player_angle -= 2
            pressed_R = True
        elif rect_M.collidepoint(mouse_pos):
            player_v = player_v - +player_a
            pressed_M = True
        elif rect_LM.collidepoint(mouse_pos):
            player_height -= 10000
            pressed_LM = True
        elif rect_RM.collidepoint(mouse_pos):
            player_height += 10000
            pressed_RM = True

    # Scaling factor when pressed
    scale_pressed = 0.9

    # Clamp Player Height
    player_height = max(10000, player_height)

    # Function to blit with optional scaling
    def blit_button(image, pos, pressed):
        if pressed:
            scaled = pygame.transform.rotozoom(image, 0, scale_pressed)
            new_rect = scaled.get_rect(center=(pos[0] + image.get_width() // 2, pos[1] + image.get_height() // 2))
            SCREEN.blit(scaled, new_rect.topleft)
        else:
            SCREEN.blit(image, pos)

    # Draw buttons (shrink if pressed)
    blit_button(stick_L, pos_L, pressed_L)
    blit_button(stick_R, pos_R, pressed_R)
    blit_button(stick_M, pos_M, pressed_M)
    blit_button(stick_L, pos_LM, pressed_LM)
    blit_button(stick_R, pos_RM, pressed_RM)


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS, COIN_COUNT
    global HOME_BUTTON, player_x, player_y, player_angle, player_v, player_a, map_image_orig, map_width, cockpit
    global stick_L, stick_R, stick_M, player_height, frame

    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()

    while RUNNING:
        CLOCK.tick(120)
        EVENTS = pygame.event.get()

        for event in EVENTS:
            if event.type == pygame.QUIT:
                RUNNING = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            player_v -= player_a
        if keys[pygame.K_s]:
            player_v += player_a
        if keys[pygame.K_d]:
            player_angle -= 2
        if keys[pygame.K_a]:
            player_angle += 2
        if keys[pygame.K_f]:
            player_height += 10000
        if keys[pygame.K_r]:
            player_height -= 10000

        # Add Drag
        player_v = player_v * 0.95
        if abs(player_v) < 0.5:
            player_v = 0

        rad = math.radians(player_angle)
        player_x -= player_v * math.cos(rad)
        player_y -= player_v * math.sin(rad)

        # Wrap player position on map
        player_x %= map_width
        player_y %= map_height

        if len(COINS) <= 1:
            create_coins()

        # Clear screen sky
        screen.fill((100, 120, 255))

        # Draw mode7 ground
        draw_mode7_ground(screen, player_x, player_y, player_angle)

        # Draw Rotor
        if frame % 3 == 0:
            pygame.draw.circle(SCREEN, pygame.Color("lightgray"), (400, -850), 900)
        if frame % 6 == 0:
            pygame.draw.circle(SCREEN, pygame.Color("lightblue"), (400, -850), 900)

        draw_minimap()

        for fc in FLYING_COINS[:]:
            fc.update()
            if fc.arrived:
                COIN_COUNT += 1
                draw_coin_count()
                FLYING_COINS.remove(fc)
            else:
                fc.draw()

        draw_cockpit()

        for c in COINS:
            c.update()
        # Then draw them sorted by distance (furthest first)
        for c in sorted(COINS, key=lambda coin: coin.distance_to_player, reverse=True):
            c.draw()

        HOME_BUTTON.update(EVENTS)
        HOME_BUTTON.draw(screen)
        pygame.display.flip()
        frame += 1

        # print(clock.get_fps())
        # print(f"{player_x} _ {player_y}")
        await asyncio.sleep(0)
    return
