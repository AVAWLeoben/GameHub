# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import random as rd

# from pathfinding.core.grid import Grid as PFGrid
# from pathfinding.finder.a_star import AStarFinder
# from pathfinding.finder.breadth_first import BreadthFirstFinder
# from numpy import zeros
import math
import heapq
from collections import deque

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None
TILESIZE = 50
EVENTS = None
N_TILES_HORZ = 0
N_TILES_VERT = 0
TILES = []

# Images
# BACKGROUND = None


def ret():
    global RUNNING
    RUNNING = False


def neighbors(pos, matrix):
    x, y = pos
    results = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < len(matrix[0]) and 0 <= ny < len(matrix):
            if matrix[ny][nx]:  # walkable
                results.append((nx, ny))
    return results


def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(matrix, start, goal):
    open_set = []
    heapq.heappush(open_set, (0 + heuristic(start, goal), 0, start, [start]))
    visited = set()

    while open_set:
        _, cost, current, path = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            return path

        for neighbor in neighbors(current, matrix):
            if neighbor not in visited:
                heapq.heappush(open_set, (cost + 1 + heuristic(neighbor, goal), cost + 1, neighbor, path + [neighbor]))

    return []  # no path found


def bfs(matrix, start, goal):
    queue = deque([(start, [start])])
    visited = set([start])

    while queue:
        current, path = queue.popleft()

        if current == goal:
            return path

        for neighbor in neighbors(current, matrix):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return []  # no path found


home_button = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


class Tile:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.nx = x // TILESIZE
        self.ny = y // TILESIZE
        self.w = TILESIZE
        self.h = TILESIZE
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.hovered = False
        self.clicked = False
        self.color = pygame.Color(230, 230, 230)
        self.type = None
        self.image = None

    def checkNeighbor(self, nx, ny):
        if 0 <= nx < N_TILES_HORZ and 0 <= ny < N_TILES_VERT:
            return TILES[ny][nx].clicked
        return None

    def isPlaceable(self):
        results = [
            self.checkNeighbor(self.nx, self.ny - 1),
            self.checkNeighbor(self.nx, self.ny + 1),
            self.checkNeighbor(self.nx + 1, self.ny),
            self.checkNeighbor(self.nx - 1, self.ny),
            self.checkNeighbor(self.nx - 1, self.ny - 1),
            self.checkNeighbor(self.nx + 1, self.ny - 1),
            self.checkNeighbor(self.nx - 1, self.ny + 1),
            self.checkNeighbor(self.nx + 1, self.ny + 1),
        ]
        num_occupied = sum(1 for r in results if r is True)
        return num_occupied <= 9

    def updateType(self):
        if self.clicked:
            up = self.checkNeighbor(self.nx, self.ny - 1)
            down = self.checkNeighbor(self.nx, self.ny + 1)
            right = self.checkNeighbor(self.nx + 1, self.ny)
            left = self.checkNeighbor(self.nx - 1, self.ny)
            # Now determine the tile type
            if up and down and left and right:
                self.type = "crossing"
            elif left and right and not up and not down:
                self.type = "straight-horizontal"
            elif up and down and not left and not right:
                self.type = "straight-vertical"
            elif up and right:
                self.type = "curve-ur"
            elif up and left:
                self.type = "curve-ul"
            elif down and right:
                self.type = "curve-dr"
            elif down and left:
                self.type = "curve-dl"
            elif self.clicked:
                self.type = "crossing"
            else:
                self.type = None  # fallback

    def update(self):
        global GRID
        mousePos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mousePos):
            self.hovered = True
            self.color = pygame.Color("black")
        else:
            self.hovered = False
            self.color = pygame.Color(230, 230, 230)
        for event in EVENTS:
            in_station = (self.nx in STATIONTILES_X) and (self.ny in STATIONTILES_Y)
            if event.type == pygame.MOUSEBUTTONDOWN and not in_station:
                if self.rect.collidepoint(event.pos) and self.isPlaceable() and self.clicked is False:
                    self.clicked = True
                    self.color = pygame.Color("red")
                    self.type = "RailCrossing"
                    self.image = pygame.transform.scale(RAILROAD_CROSSING_IMAGE, (TILESIZE, TILESIZE))
                elif self.rect.collidepoint(event.pos) and self.clicked is True:
                    self.clicked = False
                    self.type = None

        self.updateType()
        if self.type is not None:
            self.image = RAILROAD_IMAGES[self.type]

        # Update NavGrid
        if self.type is not None:
            GRID[self.ny][self.nx] = 1
        else:
            GRID[self.ny][self.nx] = 0

        if self.clicked:
            print(GRID)

    def draw(self):
        if self.hovered:
            pygame.draw.rect(SCREEN, self.color, self.rect, 1)  # 1 = border thickness
        if self.type is not None:
            SCREEN.blit(self.image, self.rect)
        if TRAIN:
            if TRAIN.target[0] == self.nx and TRAIN.target[1] == self.ny:
                pygame.draw.circle(SCREEN, pygame.Color("green"), self.rect.center, 5)


class Wagon:
    def __init__(self, offset):
        self.image = pygame.transform.scale(WAGON_IMAGE, (TILESIZE, TILESIZE))
        self.rect = self.image.get_rect()
        self.offset = offset  # how many trail steps behind the train
        self.x, self.y = 0, 0

    def update(self, trail):
        if len(trail) > self.offset:
            self.x, self.y = trail[-self.offset]
            self.rect.topleft = (int(self.x), int(self.y))

    def draw(self, screen, faceLeft):
        img = pygame.transform.flip(self.image, 1, 0) if faceLeft else self.image
        screen.blit(img, self.rect)


class Train:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.image = pygame.transform.scale(pygame.image.load("assets/wasteTrain/train.png"), (TILESIZE, TILESIZE))
        self.rect = self.image.get_rect()
        self.onGrid = False
        self.start = (self.x // TILESIZE, self.y // TILESIZE)
        endtile = self.find_end_tile()
        self.target = (endtile.nx, endtile.ny)
        self.path = self.find_path(self.start, self.target)
        self.speed = 4
        self.faceLeft = False

        self.trail = []  # Keep track of previous positions
        self.max_trail_length = 100  # Ensure trail doesn't grow too big
        self.num_wagons = sum(sum(row) for row in GRID) // 4
        self.wagons = [Wagon((i + 1) * 10) for i in range(self.num_wagons)]

    def find_end_tile(self):
        for row in reversed(TILES):
            for tile in reversed(row):
                if tile.clicked:
                    return tile
        return None

    # Your modified method:
    def find_path(self, start, end):
        matrix = [[1 if cell == 1 else 0 for cell in row] for row in GRID]

        if sum(sum(row) for row in GRID) < 15:
            path = astar(matrix, start, end)
        else:
            path = bfs(matrix, start, end)

        self.path = path[1:]  # skip starting tile
        return self.path

    # def find_path_offline(self, start, end):
    #     matrix = [[1 if cell == 1 else 0 for cell in row] for row in GRID.tolist()]
    #     pf_grid = PFGrid(matrix=matrix)
    #     start_node = pf_grid.node(start[0], start[1])
    #     end_node = pf_grid.node(end[0], end[1])

    #     if GRID.sum() < 15:
    #         finder = AStarFinder()
    #     else:
    #         finder = BreadthFirstFinder()
    #     path, _ = finder.find_path(start_node, end_node, pf_grid)
    #     self.path = path[1:]  # exclude start node
    #     return self.path

    def findNewTargetTile(self):
        clicked_tiles = [tile for row in TILES for tile in row if tile.clicked]
        if clicked_tiles:
            return rd.choice(clicked_tiles)
        return None

    def update(self):
        self.num_wagons = sum(sum(row) for row in GRID) // 4
        self.wagons = [Wagon((i + 1) * 10) for i in range(self.num_wagons)]
        if self.path:
            target_x, target_y = self.path[0]
            target_x = target_x * TILESIZE
            target_y = target_y * TILESIZE
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy)  # Fixed: swapped dx, dy
            if dist > 0:
                self.faceLeft = dx <= 0
            if dist < self.speed:
                self.x, self.y = target_x, target_y
                self.path.pop(0)
            else:
                self.x += self.speed * dx / dist
                self.y += self.speed * dy / dist
            if len(self.path) == 0:
                self.start = (self.x // TILESIZE, self.y // TILESIZE)
                newTargetTile = self.findNewTargetTile()
                self.target = (newTargetTile.x // TILESIZE, newTargetTile.y // TILESIZE)
                self.path = self.find_path(self.start, self.target)
        else:
            print("No PATH FOUND")
            # Try another tile
            newTargetTile = self.findNewTargetTile()
            if newTargetTile:
                self.target = (newTargetTile.x // TILESIZE, newTargetTile.y // TILESIZE)
                self.path = self.find_path(self.start, self.target)

        self.rect.topleft = (int(self.x), int(self.y))

        # Update trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)

        # Update wagons
        for wagon in self.wagons:
            wagon.update(self.trail)

    def draw(self):
        # Draw wagons first so they appear behind the train
        for wagon in self.wagons:
            wagon.draw(SCREEN, self.faceLeft)

        if self.faceLeft:
            draw_image = pygame.transform.flip(self.image, 1, 0)
        else:
            draw_image = self.image.copy()
        SCREEN.blit(draw_image, self.rect)


def loadImages():
    global BACKGROUND, RAILROAD_CROSSING_IMAGE, RAILROAD_IMAGES, STATION_IMAGE, WAGON_IMAGE
    BACKGROUND = pygame.image.load("assets/hungryHedgie/grass.png")
    RAILROAD_CROSSING_IMAGE = pygame.image.load("assets/wasteTrain/rail_Crossing.png")
    RAILROAD_VERTICAL_IMAGE = pygame.image.load("assets/wasteTrain/track.png")
    RAILROAD_HORIZONTAL_IMAGE = pygame.transform.rotate(RAILROAD_VERTICAL_IMAGE, 90)
    RAILROAD_CURVE_UL_IMAGE = pygame.image.load("assets/wasteTrain/rail_Crossing.png")
    RAILROAD_CURVE_UR_IMAGE = pygame.transform.rotate(RAILROAD_CURVE_UL_IMAGE, -90)
    RAILROAD_CURVE_DR_IMAGE = pygame.transform.rotate(RAILROAD_CURVE_UL_IMAGE, 180)
    RAILROAD_CURVE_DL_IMAGE = pygame.transform.rotate(RAILROAD_CURVE_UL_IMAGE, 90)

    RAILROAD_IMAGES = {
        "crossing": pygame.transform.scale(RAILROAD_CROSSING_IMAGE, (TILESIZE, TILESIZE)),
        "straight-horizontal": pygame.transform.scale(RAILROAD_HORIZONTAL_IMAGE, (TILESIZE, TILESIZE)),
        "straight-vertical": pygame.transform.scale(RAILROAD_VERTICAL_IMAGE, (TILESIZE, TILESIZE)),
        "curve-ur": pygame.transform.scale(RAILROAD_CURVE_UR_IMAGE, (TILESIZE, TILESIZE)),
        "curve-ul": pygame.transform.scale(RAILROAD_CURVE_UL_IMAGE, (TILESIZE, TILESIZE)),
        "curve-dr": pygame.transform.scale(RAILROAD_CURVE_DR_IMAGE, (TILESIZE, TILESIZE)),
        "curve-dl": pygame.transform.scale(RAILROAD_CURVE_DL_IMAGE, (TILESIZE, TILESIZE)),
    }

    STATION_IMAGE = pygame.transform.scale(
        pygame.image.load("assets/wasteTrain/station.png").convert_alpha(), (TILESIZE * 4, TILESIZE * 3)
    )
    WAGON_IMAGE = pygame.image.load("assets/wasteTrain/wagon.png")


def createTiles():
    global TILES, N_TILES_HORZ, N_TILES_VERT
    N_TILES_HORZ = 800 // TILESIZE
    N_TILES_VERT = 600 // TILESIZE

    TILES = []
    for y in range(N_TILES_VERT):
        row = []
        for x in range(N_TILES_HORZ):
            row.append(Tile(x * TILESIZE, y * TILESIZE))
        TILES.append(row)


def find_start_tile():
    for row in TILES:
        for tile in row:
            if tile.clicked:
                return tile
    return None


def update():
    global RUNNING, EVENTS, TRAIN
    EVENTS = pygame.event.get()
    home_button.update(EVENTS)
    for row in TILES:
        for tile in row:
            tile.update()
    if TRAIN is None:
        track_tiles = [tile for row in TILES for tile in row if tile.clicked]
        if len(track_tiles) >= 10:
            first_track = find_start_tile()
            TRAIN = Train(first_track.x, first_track.y)
    if TRAIN is not None:
        TRAIN.update()
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False


def draw():
    SCREEN.fill((10, 10, 30))
    SCREEN.blit(BACKGROUND, (0, 0))
    for row in TILES:
        for tile in row:
            tile.draw()
    if TRAIN is not None:
        TRAIN.draw()

    SCREEN.blit(STATION_IMAGE, (TILESIZE * 3, TILESIZE * 2))
    home_button.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, TILES, TRAIN
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    TRAIN = None

    loadImages()
    global STATIONTILES_X, STATIONTILES_Y
    STATIONTILES_X = [3, 4, 5, 6]
    STATIONTILES_Y = [3, 4]

    global GRID
    # GRID = zeros((600//TILESIZE,800//TILESIZE), dtype=int)
    GRID = [[0 for _ in range(800 // TILESIZE)] for _ in range(600 // TILESIZE)]

    print(GRID)
    TILES = []
    createTiles()

    while RUNNING:
        CLOCK.tick(FPS)
        update()
        draw()
        await asyncio.sleep(0)

    return
