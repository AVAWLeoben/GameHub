# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button, Toggle_Button, Slider
import pygame
import asyncio
import time

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


class Cell:
    def __init__(self,x,y,cell_size,owner,alive=False):
        self.x = x
        self.y = y
        self.grid_x = x//cell_size
        self.grid_y = y//cell_size
        
        self.size = cell_size
        self.rect = pygame.Rect(x,y,cell_size,cell_size)
        self.owner = owner
        self.alive = alive
        self.next_alive = alive
        self.n_alive_neighbours = 0
        
        self.colors = {True: pygame.Color("white"), False: pygame.Color("black")}
        self.color = self.colors.get(self.alive)
        self.hovered = False
        
        self.last_clicked = 0
        self.debounce = 0.3
        
        
    
    
    
    def get_n_live_neighbours(self):
        x = self.grid_x
        y = self.grid_y
        n_alive_neighbours = 0
        for x_offset in [-1,0,1]:
            for y_offset in [-1,0,1]:
                if x_offset == 0 and y_offset == 0:
                    continue
                neighbour_x = x+x_offset
                neighbour_y = y+y_offset
                neighbour_pos = (neighbour_x,neighbour_y)
                neighbour = self.owner.cells.get(neighbour_pos)
                if neighbour:
                    if neighbour.alive:
                        n_alive_neighbours += 1
        self.n_alive_neighbours = n_alive_neighbours               
    
    def compute_next_state(self):
        # Only compute alive_myself without changing self.alive
        
            if self.alive:
                if self.n_alive_neighbours < 2 or self.n_alive_neighbours > 3:
                    self.next_alive = False
                else:
                    self.next_alive = True
            else:
                if self.n_alive_neighbours == 3:
                    self.next_alive = True
                else:
                    self.next_alive = False
            
    def apply_next_state(self):
        self.alive = self.next_alive
        self.color = self.colors[self.alive]    
    
    def update(self):
                
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()[0]
        self.hovered = self.rect.collidepoint(mouse_pos)
        
        
        if SIMULATING == False:            
            if self.rect.collidepoint(mouse_pos):
                if mouse_pressed:
                    if self.last_clicked + self.debounce < time.time():
                        self.alive = not self.alive
                        self.last_clicked = time.time()
                    
        self.color = self.colors.get(self.alive)
            
        
    
    def draw(self):
        pygame.draw.rect(SCREEN,self.color,self.rect)
        pygame.draw.rect(SCREEN,pygame.Color("white"),self.rect,1)
        if self.hovered:
            pygame.draw.rect(SCREEN,pygame.Color("white"),self.rect,2)
    

class Grid:
    def __init__(self,cell_size=16):
        self.cell_size = cell_size
        self.cells = {}
        n_cells = SCREEN.get_width()//cell_size
        self.last_update = 0
        
        for x in range(n_cells):
            for y in range(n_cells):
                pos = (x,y)
                self.cells[pos] = Cell(x*cell_size,y*cell_size,self.cell_size,self)
    
    def update(self):
        if SIMULATING:
            if time.time() - self.last_update > 1/SPEED_SLIDER.value: 
                # 1️⃣ compute number of neighbors for all cells
                for cell in self.cells.values():
                    cell.get_n_live_neighbours()
                # 2️⃣ compute next state for all cells
                for cell in self.cells.values():
                    cell.compute_next_state()
                # 3️⃣ apply next state for all cells
                for cell in self.cells.values():
                    cell.apply_next_state()
                self.last_update = time.time()

        else:
            # manual cell toggling
            for cell in self.cells.values():
                cell.update()  # handle mouse click

            
    def draw(self):
        for _,c in self.cells.items():
            c.draw()

def ret():
    global RUNNING
    RUNNING = False



def toggle_simulation():
    global SIMULATING
    SIMULATING = not SIMULATING

def restart_simulation():
    global GRID
    GRID = Grid()

def setup():
    global SIMULATING
    SIMULATING = False 
    global SPEED_SLIDER
    SPEED_SLIDER = Slider(350, 10, 300, 20, 1, 120, FPS)  # min 1 FPS, max 60 FPS
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
    global START_BUTTON
    START_BUTTON = Button(690, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", toggle_simulation)
    global RESTART_BUTTON
    RESTART_BUTTON = Button(690, 490, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", restart_simulation)
    
    
    global BUTTONS
    BUTTONS = []
    BUTTONS.append(HOME_BUTTON)
    BUTTONS.append(START_BUTTON)
    BUTTONS.append(RESTART_BUTTON)
    
    global GRID    
    GRID = Grid()
    

def update():
    global RUNNING
    for b in BUTTONS:
        b.update(EVENTS)
    
    SPEED_SLIDER.update(EVENTS)
    print(SIMULATING)
        
        
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    GRID.update()


def draw():
    SCREEN.fill((10, 10, 30))
    GRID.draw()
    for b in BUTTONS:
        b.draw(SCREEN)
    SPEED_SLIDER.draw(SCREEN)
    pygame.display.flip()


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    
    setup()
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
        await asyncio.sleep(0)

    return

async def run_locally():
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Game Hub")
    font = pygame.font.SysFont(None, 48)
    clock = pygame.time.Clock()
    await main(screen,clock)
    
if __name__ == "__main__":
    asyncio.run(run_locally())