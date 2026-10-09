# -*- coding: utf-8 -*-
"""WasteTrain: touch-friendly railway sandbox and delivery missions.

Entry point used by GameHub: await wasteTrain.main(screen, clock).
No additional artwork or third-party pathfinding packages are needed.
"""
import asyncio
import heapq
import math
import random
import pygame

FPS = 60
COLS, ROWS = 20, 14
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
PALETTE = ((238, 113, 88), (92, 171, 234), (246, 193, 76), (167, 124, 219))
GRASS = (113, 166, 108)
DARK = (34, 54, 51)
WHITE = (250, 247, 230)


def route(start, end, allowed):
    """A* on four-directional, player-built track cells."""
    if start not in allowed or end not in allowed:
        return []
    heap = [(abs(start[0]-end[0])+abs(start[1]-end[1]), 0, start)]
    parent = {start: None}
    costs = {start: 0}
    while heap:
        _, cost, pos = heapq.heappop(heap)
        if cost != costs.get(pos):
            continue
        if pos == end:
            result = []
            while pos is not None:
                result.append(pos)
                pos = parent[pos]
            return result[::-1]
        for dx, dy in DIRS:
            nxt = (pos[0]+dx, pos[1]+dy)
            if nxt not in allowed:
                continue
            new_cost = cost+1
            if new_cost < costs.get(nxt, 10**9):
                costs[nxt] = new_cost
                parent[nxt] = pos
                h = abs(nxt[0]-end[0])+abs(nxt[1]-end[1])
                heapq.heappush(heap, (new_cost+h, new_cost, nxt))
    return []


class WasteTrain:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        # Reserve a toolbar on the right, keeping the board readable on iPads.
        self.cell = max(12, min((self.w-185)//COLS, (self.h-85)//ROWS))
        self.ox = max(8, (self.w-180-COLS*self.cell)//2)
        self.oy = max(52, (self.h-ROWS*self.cell)//2)
        self.font = pygame.font.Font(None, max(18, min(27, self.cell)))
        self.small = pygame.font.Font(None, max(16, min(22, self.cell-2)))
        self.big = pygame.font.Font(None, 34)
        self.rng = random.Random()
        self.tool = "build"
        self.dragging = False
        self.drag_last = None
        self.train = None
        self.train_path = []
        self.train_progress = 0.0
        self.deliveries = 0
        self.score = 0
        self.message = ""
        self.message_until = 0
        self.buttons = {}
        self.exit_requested = False
        self.home_rect = pygame.Rect(0, 0, 0, 0)
        self.new_world()

    def new_world(self):
        self.obstacles = set()
        self.stations = []
        self.tracks = set()
        self.train = None
        self.train_path = []
        self.train_progress = 0
        self.deliveries = 0
        self.score = 0
        self.tool = "build"
        # Keep station positions apart; reserve their immediate neighbors.
        for i in range(4):
            for _ in range(400):
                pos = (self.rng.randrange(1, COLS-1), self.rng.randrange(1, ROWS-1))
                if all(abs(pos[0]-p[0])+abs(pos[1]-p[1]) >= 8 for p in self.stations):
                    self.stations.append(pos)
                    break
        if len(self.stations) < 4:
            self.stations = [(2, 2), (COLS-3, 2), (2, ROWS-3), (COLS-3, ROWS-3)]
        reserved = set(self.stations)
        for x, y in self.stations:
            reserved.update((x+dx, y+dy) for dx, dy in DIRS)
        for y in range(ROWS):
            for x in range(COLS):
                pos = (x, y)
                if pos not in reserved and self.rng.random() < 0.13:
                    self.obstacles.add(pos)
        self.source = 0
        self.dest = 1
        self.tracks.update(self.stations)
        self.say("Connect the highlighted stations, then SEND TRAIN!")

    def say(self, msg):
        self.message = msg
        self.message_until = pygame.time.get_ticks()+3500

    def cell_rect(self, pos):
        x, y = pos
        return pygame.Rect(self.ox+x*self.cell, self.oy+y*self.cell, self.cell, self.cell)

    def point_cell(self, pos):
        x = (pos[0]-self.ox)//self.cell
        y = (pos[1]-self.oy)//self.cell
        if 0 <= x < COLS and 0 <= y < ROWS:
            return int(x), int(y)
        return None

    def edit(self, pos):
        if self.train is not None or pos is None:
            return
        if pos in self.obstacles or pos in self.stations:
            return
        if self.tool == "build":
            self.tracks.add(pos)
        else:
            self.tracks.discard(pos)

    def send(self):
        if self.train is not None:
            return
        path = route(self.stations[self.source], self.stations[self.dest], self.tracks)
        if len(path) < 2:
            self.say("No connection yet! Build a track between the stations.")
            return
        self.train_path = path
        self.train_progress = 0.0
        self.train = True
        self.say("Delivery underway!")

    def next_mission(self):
        self.deliveries += 1
        self.score += 100
        self.source = self.dest
        candidates = [i for i in range(len(self.stations)) if i != self.source]
        self.dest = self.rng.choice(candidates)
        self.train = None
        self.train_path = []
        self.train_progress = 0.0
        self.say("Delivered! +100 points. New destination highlighted.")

    def update(self, dt):
        if self.train is not None:
            # Move at ~3 cells per second, independent of frame rate.
            self.train_progress += 3.0 * dt
            if self.train_progress >= len(self.train_path)-1:
                self.next_mission()

    def train_position(self, offset=0.0):
        progress = max(0, self.train_progress-offset)
        a = min(int(progress), len(self.train_path)-1)
        b = min(a+1, len(self.train_path)-1)
        t = progress-a
        ax, ay = self.cell_rect(self.train_path[a]).center
        bx, by = self.cell_rect(self.train_path[b]).center
        return ax+(bx-ax)*t, ay+(by-ay)*t, math.atan2(by-ay, bx-ax)

    def draw_train(self, center, angle, wagon=False):
        size = self.cell*0.70
        # Shape is constructed in local coordinates, then rotated to match travel.
        ca, sa = math.cos(angle), math.sin(angle)
        def pt(x, y):
            return (int(center[0]+x*ca-y*sa), int(center[1]+x*sa+y*ca))
        color = (247, 191, 80) if wagon else (218, 68, 63)
        pygame.draw.polygon(self.screen, (39, 42, 44),
                            [pt(-size*.48, -size*.34), pt(size*.48, -size*.34),
                             pt(size*.48, size*.34), pt(-size*.48, size*.34)])
        pygame.draw.polygon(self.screen, color,
                            [pt(-size*.42, -size*.27), pt(size*.38, -size*.27),
                             pt(size*.45, 0), pt(size*.38, size*.27),
                             pt(-size*.42, size*.27)])
        if not wagon:
            pygame.draw.polygon(self.screen, (151, 224, 233),
                                [pt(size*.05, -size*.20), pt(size*.30, -size*.20),
                                 pt(size*.30, size*.20), pt(size*.05, size*.20)])
            pygame.draw.circle(self.screen, (253, 243, 169), pt(size*.45, 0), max(2, self.cell//12))
        else:
            pygame.draw.line(self.screen, (114, 78, 38), pt(-size*.25, 0), pt(size*.25, 0), 3)

    def draw(self):
        s = self.screen
        s.fill((215, 228, 203))
        pygame.draw.rect(s, DARK, (0, 0, self.w, 43))
        header = self.big.render("WASTE TRAIN", True, WHITE)
        s.blit(header, (12, 7))
        self.home_rect = pygame.Rect(self.w-112, 3, 105, 36)
        pygame.draw.rect(s, (87, 117, 107), self.home_rect, border_radius=7)
        home_label = self.small.render("HOME", True, WHITE)
        s.blit(home_label, home_label.get_rect(center=self.home_rect.center))
        board = pygame.Rect(self.ox, self.oy, COLS*self.cell, ROWS*self.cell)
        pygame.draw.rect(s, GRASS, board, border_radius=7)
        for y in range(ROWS):
            for x in range(COLS):
                pos = (x, y)
                r = self.cell_rect(pos)
                if (x+y)%2:
                    pygame.draw.rect(s, (119, 174, 113), r)
                pygame.draw.rect(s, (92, 146, 93), r, 1)
                if pos in self.obstacles:
                    cx, cy = r.center
                    if (x*7+y)%3 == 0:
                        pygame.draw.ellipse(s, (90, 98, 100), r.inflate(-self.cell*.18, -self.cell*.30))
                        pygame.draw.ellipse(s, (140, 150, 146),
                                            (cx-self.cell*.25, cy-self.cell*.25, self.cell*.35, self.cell*.22))
                    else:
                        pygame.draw.rect(s, (102, 74, 48),
                                         (cx-self.cell*.06, cy, self.cell*.12, self.cell*.29))
                        pygame.draw.circle(s, (40, 116, 69), (cx, cy-self.cell*.12), int(self.cell*.32))
                        pygame.draw.circle(s, (55, 137, 76), (cx-self.cell*.12, cy-self.cell*.21), int(self.cell*.22))
        # Track joins use the actual four-neighbor connections.
        width = max(5, self.cell//5)
        for pos in self.tracks:
            cx, cy = self.cell_rect(pos).center
            pygame.draw.circle(s, (78, 67, 58), (cx, cy), width//2+1)
            for dx, dy in ((1, 0), (0, 1)):
                other = (pos[0]+dx, pos[1]+dy)
                if other in self.tracks:
                    ex, ey = self.cell_rect(other).center
                    pygame.draw.line(s, (75, 67, 62), (cx, cy), (ex, ey), width+4)
                    pygame.draw.line(s, (210, 205, 178), (cx, cy), (ex, ey), max(2, width-3))
                    for k in (0.2, 0.5, 0.8):
                        mx, my = cx+(ex-cx)*k, cy+(ey-cy)*k
                        nx, ny = -dy, dx
                        pygame.draw.line(s, (104, 70, 49),
                                         (mx-nx*width*.8, my-ny*width*.8),
                                         (mx+nx*width*.8, my+ny*width*.8), max(2, self.cell//14))
        for i, pos in enumerate(self.stations):
            r = self.cell_rect(pos)
            cx, cy = r.center
            c = PALETTE[i]
            pygame.draw.circle(s, (255, 255, 220) if i in (self.source, self.dest) else DARK,
                               (cx, cy), int(self.cell*.47))
            pygame.draw.circle(s, c, (cx, cy), int(self.cell*.39))
            pygame.draw.rect(s, (247, 244, 220),
                             (cx-self.cell*.22, cy-self.cell*.08, self.cell*.44, self.cell*.29),
                             border_radius=2)
            pygame.draw.polygon(s, DARK, [(cx-self.cell*.29, cy-self.cell*.08),
                                          (cx, cy-self.cell*.32),
                                          (cx+self.cell*.29, cy-self.cell*.08)])
            label = self.small.render("ABCD"[i], True, DARK)
            s.blit(label, label.get_rect(center=(cx, cy+self.cell*.12)))
            if i == self.dest:
                pygame.draw.circle(s, (255, 238, 90), (cx, cy), int(self.cell*.48), 3)
        if self.train is not None and self.train_path:
            for offset in (1.1, 0.55):
                if self.train_progress > offset:
                    x, y, a = self.train_position(offset)
                    self.draw_train((x, y), a, wagon=True)
            x, y, a = self.train_position()
            self.draw_train((x, y), a)
        # Right-hand toolbar.
        px = max(self.ox+COLS*self.cell+10, self.w-169)
        bw = min(158, self.w-px-7)
        self.buttons = {}
        def button(name, label, top, selected=False):
            r = pygame.Rect(px, top, bw, 43)
            self.buttons[name] = r
            pygame.draw.rect(s, (76, 132, 109) if selected else (49, 77, 77), r, border_radius=8)
            pygame.draw.rect(s, (220, 238, 212), r, 2, border_radius=8)
            txt = self.small.render(label, True, WHITE)
            s.blit(txt, txt.get_rect(center=r.center))
        y0 = self.oy
        button("build", "BUILD TRACK", y0, self.tool=="build")
        button("erase", "ERASE TRACK", y0+49, self.tool=="erase")
        button("send", "SEND TRAIN", y0+108)
        button("reset", "NEW MAP", y0+165)
        info = [
            "MISSION",
            "ABCD"[self.source] + "  ->  " + "ABCD"[self.dest],
            "Score: " + str(self.score),
            "Trips: " + str(self.deliveries),
        ]
        for i, line in enumerate(info):
            txt = self.small.render(line, True, DARK)
            s.blit(txt, (px, y0+230+i*29))
        if pygame.time.get_ticks() < self.message_until:
            text = self.small.render(self.message, True, WHITE)
            box = text.get_rect()
            box.topleft = (max(10, self.ox), self.h-31)
            bg = box.inflate(16, 8)
            pygame.draw.rect(s, DARK, bg, border_radius=5)
            s.blit(text, box)
        pygame.display.flip()

    def click(self, pos):
        if self.home_rect.collidepoint(pos):
            self.exit_requested = True
            return False
        for key, rect in self.buttons.items():
            if rect.collidepoint(pos):
                if key in ("build", "erase"):
                    self.tool = key
                elif key == "send":
                    self.send()
                elif key == "reset":
                    self.new_world()
                return False
        cell = self.point_cell(pos)
        if cell is not None:
            self.edit(cell)
            self.drag_last = cell
            return True
        return False

    def drag(self, pos):
        cell = self.point_cell(pos)
        if cell is None or cell == self.drag_last:
            return
        # Fill skipped cells when a finger moves quickly.
        if self.drag_last is not None:
            x0, y0 = self.drag_last
            x1, y1 = cell
            steps = max(abs(x1-x0), abs(y1-y0))
            for k in range(1, steps+1):
                x = round(x0+(x1-x0)*k/steps)
                y = round(y0+(y1-y0)*k/steps)
                self.edit((x, y))
        else:
            self.edit(cell)
        self.drag_last = cell


async def main(screen, clock):
    game = WasteTrain(screen)
    running = True
    finger_id = None
    while running:
        dt = min(clock.tick(FPS)/1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.dragging = game.click(event.pos)
            elif event.type == pygame.MOUSEMOTION and game.dragging and event.buttons[0]:
                game.drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                game.dragging = False
                game.drag_last = None
            elif event.type == pygame.FINGERDOWN and finger_id is None:
                finger_id = event.finger_id
                game.dragging = game.click((int(event.x*game.w), int(event.y*game.h)))
            elif event.type == pygame.FINGERMOTION and event.finger_id == finger_id and game.dragging:
                game.drag((int(event.x*game.w), int(event.y*game.h)))
            elif event.type == pygame.FINGERUP and event.finger_id == finger_id:
                finger_id = None
                game.dragging = False
                game.drag_last = None
        if game.exit_requested:
            running = False
        game.update(dt)
        game.draw()
        await asyncio.sleep(0)
