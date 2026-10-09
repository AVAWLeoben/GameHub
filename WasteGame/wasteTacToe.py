# -*- coding: utf-8 -*-
"""
Created on Tue Jun 17 14:25:26 2025

@author: GKoinig
"""

import pygame
import asyncio
import random
from GUI import Button


class Board:
    def __init__(self):
        self.size = 600
        self.cells = []
        self.players = ["X", "O"]
        self.currPlayer = 0
        self.count = 0
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.gameOver = False
        self.end_message = None
        self.show_end_time = 0  # Timer countdown in ms

        # Calculate top-left corner to center the board
        screen_w, screen_h = SCREEN.get_size()
        board_x = (screen_w - self.size) // 2
        board_y = (screen_h - self.size) // 2

        for row in range(3):
            for col in range(3):
                cell_x = board_x + col * (self.size // 3)
                cell_y = board_y + row * (self.size // 3)
                self.cells.append(Cell(cell_x, cell_y, self.size // 3, self.size // 3, row, col))

    def checkForWin(self):
        b = self.board
        # Check rows and columns
        for i in range(3):
            if b[i][0] == b[i][1] == b[i][2] != "":
                return b[i][0]
            if b[0][i] == b[1][i] == b[2][i] != "":
                return b[0][i]
        # Check diagonals
        if b[0][0] == b[1][1] == b[2][2] != "":
            return b[0][0]
        if b[0][2] == b[1][1] == b[2][0] != "":
            return b[0][2]
        return None  # No winner

    def ai_move(self):
        empty_cells = [cell for cell in self.cells if cell.sign == ""]
        if empty_cells:
            cell = random.choice(empty_cells)
            cell.sign = self.players[self.currPlayer]
            self.board[cell.xPos][cell.yPos] = cell.sign
            self.currPlayer = (self.currPlayer + 1) % len(self.players)
            self.count += 1

    def update(self):

        for event in EVENTS:
            if event.type == pygame.MOUSEBUTTONDOWN:
                for cell in self.cells:
                    if cell.rect.collidepoint(event.pos):
                        if cell.sign == "":
                            cell.sign = self.players[self.currPlayer]
                            self.board[cell.xPos][cell.yPos] = cell.sign
                            self.currPlayer = (self.currPlayer + 1) % len(self.players)
                            self.count += 1

                            if self.count < 9 and NPLAYERS == 1 and not self.checkForWin():
                                self.ai_move()
                            return  # Stop after first valid move

    def draw(self):
        global MAIN_MENU
        for cell in self.cells:
            cell.draw()

        winner = self.checkForWin()
        if winner and not self.end_message:
            self.end_message = f"{winner} has won!"
            self.show_end_time = pygame.time.get_ticks() + 2000  # 2 second display
        elif self.count == 9 and not winner and not self.end_message:
            self.end_message = "It's a draw!"
            self.show_end_time = pygame.time.get_ticks() + 2000

        if self.end_message:
            font = pygame.font.Font(None, 48)
            font_surface = font.render(self.end_message, True, (255, 255, 255))
            font_rect = font_surface.get_rect(center=(400, 400))
            SCREEN.blit(font_surface, font_rect)

            # Check if 2 seconds have passed
            if pygame.time.get_ticks() >= self.show_end_time:
                MAIN_MENU = True
                self.__init__()


class Cell:
    def __init__(self, x, y, w, h, xPos, yPos):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.xPos = xPos
        self.yPos = yPos
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.rect.topleft = (self.x, self.y)
        self.sign = ""

    def update(self):
        pass

    def draw(self):
        pygame.draw.rect(SCREEN, (255, 255, 255), self.rect, 1)
        if self.sign:
            font = pygame.font.Font(None, 72)  # Bigger font for better visibility
            font_surface = font.render(self.sign, True, (255, 255, 255))  # Add anti-aliasing and color
            font_rect = font_surface.get_rect(center=self.rect.center)  # Use rect.center for centering
            SCREEN.blit(font_surface, font_rect)


def ret():
    global RUNNING
    RUNNING = False


def setup():
    global RUNNING
    RUNNING = True

    global CLOCK
    CLOCK = pygame.Clock()

    global SCREEN
    pygame.init()
    SCREEN = pygame.display.set_mode((800, 600))

    global BOARD
    BOARD = Board()

    global MAIN_MENU
    MAIN_MENU = True

    global FONT
    FONT = pygame.font.Font(None, 48)

    global NPLAYERS
    NPLAYERS = 0

    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


def startMenu():
    global MAIN_MENU, NPLAYERS, RUNNING
    SCREEN.fill(pygame.Color("Black"))
    rects = [pygame.Rect(100, 100, 600, 300), pygame.Rect(100, 400, 600, 300)]
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            for idx, r in enumerate(rects):
                if r.collidepoint(event.pos):
                    MAIN_MENU = False
                    NPLAYERS = idx + 1

    for idx, r in enumerate(rects):
        pygame.draw.rect(SCREEN, pygame.Color("white"), r, 2)
        text = FONT.render(str(idx + 1), True, (255, 255, 255))
        text_rect = text.get_rect(center=r.center)
        SCREEN.blit(text, text_rect)

    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


def update():
    global EVENTS, RUNNING
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False
    BOARD.update()


def draw():
    SCREEN.fill((0, 0, 0))
    BOARD.draw()
    HOME_BUTTON.draw(SCREEN)
    pygame.display.flip()


async def main(screen=None, clock=None):
    global EVENTS
    global RUNNING, SCREEN, CLOCK, EVENTS
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    try:
        setup()
        while RUNNING:
            EVENTS = pygame.event.get()
            HOME_BUTTON.update(EVENTS)

            if MAIN_MENU:
                startMenu()
            else:
                update()
                draw()
            await asyncio.sleep(0)
    except Exception as e:
        print(e)
    pygame.quit()


# Run main loop
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio

        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
