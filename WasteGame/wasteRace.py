import pygame
import math
from itertools import permutations
import asyncio
from GUI import Button as Homebutton


def ret():
    global RUNNING
    RUNNING = False


class Button:
    def start():
        global STARTED
        STARTED = True

    def stop():
        global STARTED
        STARTED = False

    def reset():
        setup()

    def __init__(self, x, y, w=200, h=80, callback=print, text="Button"):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.rect.center = (self.x, self.y)
        self.hovered = False
        self.clicked = False
        self.callback = callback
        self.text = text

        # Set up font (you can use a global FONT if defined elsewhere)
        self.font = pygame.font.SysFont(None, 32)
        self.text_surf = self.font.render(self.text, True, (255, 255, 255))
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

        BUTTONS.append(self)

    def update(self):
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)

        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN and not self.clicked:
                if self.rect.collidepoint(event.pos):
                    self.clicked = True
                    self.callback()
                    for b in BUTTONS:
                        if b is not self:
                            b.clicked = False

    def draw(self):
        color = (200, 0, 0) if not self.clicked else (0, 200, 0)
        pygame.draw.rect(SCREEN, color, self.rect)

        # Re-center text in case button moves
        self.text_rect.center = self.rect.center
        SCREEN.blit(self.text_surf, self.text_rect)


# --------------------------
# Wastebin and Point Classes
# --------------------------
class Wastebin:
    IMAGES = {"full": pygame.image.load("assets/wasteRace/full.png"), "empty": pygame.image.load("assets/wasteRace/empty.png")}

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.emptied = False
        self.state = "full"
        self.image = Wastebin.IMAGES["full"]
        self.image = pygame.transform.scale(self.image, (45, 60))
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def update(self):
        self.state = "empty" if self.emptied else "full"
        self.image = Wastebin.IMAGES[self.state]
        self.image = pygame.transform.scale(self.image, (45, 60))
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw(self, surface):
        SCREEN.blit(self.image, self.rect)
        pygame.draw.circle(surface, (0, 255, 0) if self.emptied else (255, 0, 0), (self.x, self.y - 40), 6)


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


# --------------------------
# TSP Solver
# --------------------------
def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def tsp_route(wastebins, start):
    shortest_path = None
    min_dist = float("inf")

    for perm in permutations(wastebins):
        current = start
        total = 0
        for bin in perm:
            total += distance(current, bin)
            current = bin
        total += distance(current, start)  # back to start

        if total < min_dist:
            min_dist = total
            shortest_path = list(perm)

    return shortest_path


# --------------------------
# Load Walkable Grid
# --------------------------
def load_walkable_grid(path):
    img = pygame.image.load(path).convert()
    width, height = img.get_size()
    grid = []

    for y in range(height):
        row = []
        for x in range(width):
            color = img.get_at((x, y))
            row.append(1 if color == (255, 255, 255) else 0)
        grid.append(row)

    return grid


class UserTruck:
    IMAGE = pygame.image.load("assets/wasteRace/truck.png")

    def __init__(self, x, y, max_speed=3.0, acceleration=0.2, deceleration=0.1, screen_width=800, screen_height=600):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.acceleration = acceleration
        self.deceleration = deceleration
        self.max_speed = max_speed
        self.radius = 6
        self.collected = []
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.image = Truck.IMAGE.copy()
        self.image = pygame.transform.scale(self.image, (50, 25))
        self.draw_image = self.image.copy()
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.draw_rect = self.rect.copy()

    def update(self):
        dx, dy = 0, 0

        keys_pressed = pygame.key.get_pressed()

        # Keyboard input
        if keys_pressed[pygame.K_w]:
            dy -= 1
        if keys_pressed[pygame.K_s]:
            dy += 1
        if keys_pressed[pygame.K_a]:
            dx -= 1
        if keys_pressed[pygame.K_d]:
            dx += 1

        mouse_clicked = pygame.mouse.get_pressed()[0]
        if mouse_clicked:
            mx, my = pygame.mouse.get_pos()

            # Check if click is near the truck (optional, radius check)
            dist = math.hypot(mx - self.x, my - self.y)
            if dist < 400:  # example threshold, adjust as needed
                rel_x = mx - self.x
                rel_y = my - self.y

                # Override keyboard input with mouse direction
                if abs(rel_x) > abs(rel_y):
                    dy = 0
                    dx = 1 if rel_x > 0 else -1
                else:
                    dx = 0
                    dy = 1 if rel_y > 0 else -1

        if dx != 0 or dy != 0:
            # Normalize vector
            length = math.hypot(dx, dy)
            dx /= length
            dy /= length

            # Accelerate in direction
            self.vx += dx * self.acceleration
            self.vy += dy * self.acceleration

            # Clamp speed
            speed = math.hypot(self.vx, self.vy)
            if speed > self.max_speed:
                scale = self.max_speed / speed
                self.vx *= scale
                self.vy *= scale
        else:
            # Friction / deceleration
            self.vx *= 1 - self.deceleration
            self.vy *= 1 - self.deceleration

            if abs(self.vx) < 0.05:
                self.vx = 0
            if abs(self.vy) < 0.05:
                self.vy = 0

        # Update position
        self.x += self.vx
        self.y += self.vy

        # Clamp to screen bounds
        self.x = max(self.radius, min(self.screen_width - self.radius, self.x))
        self.y = max(self.radius, min(self.screen_height - self.radius, self.y))

        global TIME
        if GRID_MAP.get_at((int(self.x), int(self.y))) == (0, 0, 0):
            TIME += 0.1

        # Rotate image to match movement direction
        if self.vx != 0 or self.vy != 0:
            angle_rad = math.atan2(-self.vy, self.vx)
            angle_deg = math.degrees(angle_rad)
            self.draw_image = pygame.transform.rotate(self.image, angle_deg)
            self.draw_rect = self.draw_image.get_rect(center=(self.x, self.y))

    def draw(self):
        pygame.draw.rect(SCREEN, (255, 100, 0), (self.x - 5, self.y - 5, 10, 10))
        SCREEN.blit(self.draw_image, self.draw_rect)

    def check_bin_collision(self, bins):
        for wb in bins:
            if wb not in self.collected:
                dist = math.hypot(self.x - wb.x, self.y - wb.y)
                if dist < self.radius + 30:
                    self.collected.append(wb)


# --------------------------
# Truck Class with A* Pathing
# --------------------------
from collections import deque


def bfs_next_step(grid, start, goal, max_search=1000):
    """Returns the first step toward goal using BFS from start."""
    width = len(grid[0])
    height = len(grid)
    visited = set()
    queue = deque()
    came_from = {}

    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))

    queue.append(start)
    visited.add(start)

    while queue and len(visited) < max_search:
        current = queue.popleft()

        if current == goal:
            # Reconstruct path
            path = []
            while current != start:
                path.append(current)
                current = came_from[current]
            path.reverse()
            if path:
                return path[0]  # First step only
            else:
                return goal  # Already at target

        x, y = current
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                if grid[ny][nx] == 1:
                    neighbor = (nx, ny)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        came_from[neighbor] = current
                        queue.append(neighbor)

    return None  # No path found


class Truck:
    IMAGE = pygame.image.load("assets/wasteRace/truck.png")

    def __init__(self, x, y, speed=2):
        self.x = x
        self.y = y
        self.speed = speed
        self.route = tsp_route(WASTEBINS, Point(x, y))
        self.route.append(Point(x, y))  # return to start
        self.current_target_index = 0
        self.radius = 5
        self.path = []
        self.image = Truck.IMAGE.copy()
        self.image = pygame.transform.scale(self.image, (50, 25))
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.draw_image = self.image.copy()
        self.draw_rect = self.rect.copy()
        self.last_direction = (0, 0)

    def copy(self):
        return self.copy()

    def update(self):
        if self.current_target_index >= len(self.route):
            return  # Done

        target = self.route[self.current_target_index]
        tx, ty = int(target.x), int(target.y)

        # If already close to target, go to next
        if math.hypot(self.x - tx, self.y - ty) < self.radius:
            self.x = tx
            self.y = ty
            if self.current_target_index < len(self.route) - 1:
                self.route[self.current_target_index].emptied = True
            self.current_target_index += 1
            self.path = []
            return

        min_dist = float("inf")
        neighbours = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        best_n = (0, 0)

        for n in neighbours:
            # Skip the exact opposite of last move if avoidable
            if n[0] == -self.last_direction[0] and n[1] == -self.last_direction[1]:
                continue

            next_loc_x = int(self.x + self.speed * n[0])
            next_loc_y = int(self.y + self.speed * n[1])
            dt_x = tx - next_loc_x
            dt_y = ty - next_loc_y
            dist = math.hypot(dt_x, dt_y)

            if dist < min_dist and GRID_MAP.get_at((next_loc_x, next_loc_y)) == (255, 255, 255):
                min_dist = dist
                best_n = n

        # If no non-reverse option found, allow reverse
        if best_n == (0, 0):
            for n in neighbours:
                next_loc_x = int(self.x + self.speed * n[0])
                next_loc_y = int(self.y + self.speed * n[1])
                dt_x = tx - next_loc_x
                dt_y = ty - next_loc_y
                dist = math.hypot(dt_x, dt_y)
                if dist < min_dist and GRID_MAP.get_at((next_loc_x, next_loc_y)) == (255, 255, 255):
                    min_dist = dist
                    best_n = n

        # Update position and last_direction
        self.x += self.speed * best_n[0]
        self.y += self.speed * best_n[1]
        self.last_direction = best_n  # store last move

        self.rect.center = (self.x, self.y)

        # Compute angle (direction vector)
        angle_rad = math.atan2(-best_n[1], best_n[0])  # Negative Y because pygame y-axis is down
        angle_deg = math.degrees(angle_rad)

        # Rotate image
        self.draw_image = pygame.transform.rotate(self.image, angle_deg)
        self.draw_rect = self.draw_image.get_rect(center=(self.x, self.y))

    def draw(self):
        self.draw_image.blit(FONT.render("AI", True, (255, 255, 255)), (0, 0))
        SCREEN.blit(self.draw_image, self.draw_rect)


# Setup
def setup():
    global HOME_BUTTON
    HOME_BUTTON = Homebutton(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    global TIME
    TIME = 0
    global AI_TIME
    AI_TIME = 0
    global STARTED
    STARTED = False

    global START_X, START_Y, GRID_MAP, MAP_IMAGE, START_POINT
    START_X, START_Y = 433, 265
    START_POINT = Point(START_X, START_Y)
    GRID_MAP = pygame.image.load("assets/wasteRace/driveable_mask.png")
    GRID_MAP = pygame.transform.scale(GRID_MAP, (800, 600))
    MAP_IMAGE = pygame.image.load("assets/wasteRace/road.png").convert()
    MAP_IMAGE = pygame.transform.scale(MAP_IMAGE, (800, 600))
    # Buttons
    global BUTTONS
    BUTTONS = []  # Buttons append themselves to BUTTONS
    Button(400, 500, 200, 80, Button.start, "START")
    Button(700, 500, 200, 80, Button.stop, "STOP")
    Button(100, 500, 200, 80, Button.reset, "RESET")

    # Bins
    global WASTEBINS
    WASTEBINS = [
        Wastebin(385, 350),
        Wastebin(390, 450),
        Wastebin(398, 560),
        Wastebin(638, 528),
        Wastebin(659, 317),
        Wastebin(190, 534),
        Wastebin(752, 507),
        Wastebin(384, 138),
        Wastebin(40, 131),
    ]

    # AI Truck (algorithm controlled)
    global AI_TRUCK
    AI_TRUCK = Truck(START_X, START_Y)
    # AI_TRUCK2 = Truck(START_X, START_Y)
    # User Truck (WASD control)
    global USER_TRUCK
    USER_TRUCK = UserTruck(START_X, START_Y)

    global FONT
    FONT = pygame.font.SysFont(None, 24)


def update():
    global TIME, AI_TIME, RUNNING

    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False

    if STARTED:
        USER_TRUCK.update()
        AI_TRUCK.update()
        USER_TRUCK.check_bin_collision(WASTEBINS)

        for wb in WASTEBINS:
            wb.update()

        if len(USER_TRUCK.collected) < len(WASTEBINS):
            TIME = TIME + 1
        if AI_TRUCK.current_target_index < len(WASTEBINS):
            AI_TIME = AI_TIME + 1

    for b in BUTTONS:
        b.update()
    HOME_BUTTON.update(EVENTS)


def draw():
    SCREEN.fill((30, 30, 30))
    SCREEN.blit(MAP_IMAGE, (0, 0))
    # Draw wastebins (green if not collected, gray if collected by user)
    for wb in WASTEBINS:
        if wb in USER_TRUCK.collected:
            pygame.draw.circle(SCREEN, (100, 100, 100), (wb.x, wb.y), 6)
        else:
            wb.draw(SCREEN)

    # Draw trucks
    AI_TRUCK.draw()
    USER_TRUCK.draw()

    if STARTED == False:
        start_rect = pygame.Rect(400, 400, 300, 50)
        start_rect.center = (400, 400)
        pygame.draw.rect(SCREEN, (0, 0, 0), start_rect)

        # Render the text
        text_surf = FONT.render("Can You Beat The AI Truck?", True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=start_rect.center)

        # Blit the text centered in the black rect
        SCREEN.blit(text_surf, text_rect)

        for b in BUTTONS:
            b.draw()

    # Show info
    SCREEN.blit(FONT.render("WASD to control orange truck!", True, (255, 255, 255)), (600, 10))
    SCREEN.blit(FONT.render(f"User bins: {len(USER_TRUCK.collected)}", True, (255, 255, 255)), (600, 30))
    if STARTED:
        # Prepare the texts first
        your_time_text = FONT.render(f"Your Time: {round(TIME/60,2)}s", True, (255, 255, 255))
        ai_time_text = FONT.render(f"AI Time: {round(AI_TIME/60,2)}s", True, (255, 255, 255))

        # Get their rects for positioning
        your_time_rect = your_time_text.get_rect(topleft=(600, 550))
        ai_time_rect = ai_time_text.get_rect(topleft=(600, 500))

        # Define padding around text inside the rect
        padding = 6

        # Draw rounded rects behind the texts
        pygame.draw.rect(
            SCREEN,
            (0, 0, 0),
            (your_time_rect.x - padding, your_time_rect.y - padding, 200, your_time_rect.height + 2 * padding),
            border_radius=10,
        )

        pygame.draw.rect(
            SCREEN,
            (0, 0, 0),
            (ai_time_rect.x - padding, ai_time_rect.y - padding, 200, ai_time_rect.height + 2 * padding),
            border_radius=10,
        )
        # Blit the text on top
        SCREEN.blit(your_time_text, your_time_rect)
        SCREEN.blit(ai_time_text, ai_time_rect)

    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()
    while RUNNING:
        CLOCK.tick(60)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return
