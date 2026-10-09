# Library Imports
import pygame
import numpy as np
import asyncio

# Game Imports
import wasteMatch
import wasteSort
import wasteCar
import wasteTrain
import wastePaint
import wasteCollect
import wasteJump
import wasteFork
import wastePuzzle
import wasteTower
import jetStream
import wasteTacToe
import climbingHog
import wasteTeroids
import wasteRace
import wastePilot
import wastePong
import wastePizza
import wasteHockey
import wasteGOL
import wasteBird
import wasteHog
import hungryHedgie
from GUI import Button

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Game Hub")
font = pygame.font.SysFont(None, 48)
clock = pygame.time.Clock()

# Games
GAMES = [
    ("Memory Game", wasteMatch.main),
    ("Sort Game", wasteSort.main),
    ("Waste Car", wasteCar.main),
    ("Rail Game", wasteTrain.main),
    ("Paint Game", wastePaint.main),
    ("Collect Game", wasteCollect.main),
    ("Jump Game", wasteJump.main),
    ("Fork Game", wasteFork.main),
    ("Puzzle Game", wastePuzzle.main),
    ("Tower Game", wasteTower.main),
    ("Jet Stream", jetStream.main),
    ("Tic Tac Toe", wasteTacToe.main),
    ("Scary Hog", climbingHog.main),
    ("WasteTeroids", wasteTeroids.main),
    ("WasteRace", wasteRace.main),
    ("WastePilot", wastePilot.main),
    ("WastePong", wastePong.main),
    ("WastePizza", wastePizza.main),
    ("WasteHockey", wasteHockey.main),
    ("WasteGOL", wasteGOL.main),
    ("WasteBird", wasteBird.main),
    ("WasteHog",wasteHog.main),
    ("HungryHog",hungryHedgie.main)
]

# Global to hold selected game
selected_game_func = None


# Button callbacks just set the selected game
def but1():
    global selected_game_func
    selected_game_func = GAMES[0][1]


def but2():
    global selected_game_func
    selected_game_func = GAMES[1][1]


def but3():
    global selected_game_func
    selected_game_func = GAMES[2][1]


def but4():
    global selected_game_func
    selected_game_func = GAMES[3][1]


def but5():
    global selected_game_func
    selected_game_func = GAMES[4][1]


def but6():
    global selected_game_func
    selected_game_func = GAMES[5][1]


def but7():
    global selected_game_func
    selected_game_func = GAMES[6][1]


def but8():
    global selected_game_func
    selected_game_func = GAMES[7][1]


def but9():
    global selected_game_func
    selected_game_func = GAMES[8][1]


def but10():
    global selected_game_func
    selected_game_func = GAMES[9][1]


def but11():
    global selected_game_func
    selected_game_func = GAMES[10][1]


def but12():
    global selected_game_func
    selected_game_func = GAMES[11][1]


def but13():
    global selected_game_func
    selected_game_func = GAMES[12][1]


def but14():
    global selected_game_func
    selected_game_func = GAMES[13][1]


def but15():
    global selected_game_func
    selected_game_func = GAMES[14][1]


def but16():
    global selected_game_func
    selected_game_func = GAMES[15][1]


def but17():
    global selected_game_func
    selected_game_func = GAMES[16][1]


def but18():
    global selected_game_func
    selected_game_func = GAMES[17][1]


def but19():
    global selected_game_func
    selected_game_func = GAMES[18][1]
    
def but20():
    global selected_game_func
    selected_game_func = GAMES[19][1]

def but21():
    global selected_game_func
    selected_game_func = GAMES[20][1]
    
def but22():
    global selected_game_func
    selected_game_func = GAMES[21][1]

def but23():
    global selected_game_func
    selected_game_func = GAMES[22][1]

# Menu loop
async def game_menu():
    global selected_game_func
    buttons = [
        Button(100 - 50, 200, 100, 100, "assets/card_back.png", "assets/card_back.png", but1),
        Button(250 - 50, 200, 100, 100, "assets/banana.png", "assets/banana.png", but2),
        Button(400 - 50, 200, 100, 100, "assets/truck.png", "assets/truck.png", but3),
        Button(550 - 50, 200, 100, 100, "assets/train_button.png", "assets/train_button.png", but4),
        Button(700 - 50, 200, 100, 100, "assets/paint_button.png", "assets/paint_button.png", but5),
        Button(100 - 50, 400, 100, 100, "assets/trashBin_green.png", "assets/trashBin_green_open.png", but6),
        Button(250 - 50, 400, 100, 100, "assets/wasteJump/player.png", "assets/wasteJump/player.png", but7),
        Button(400 - 50, 400, 100, 100, "assets/wasteFork/forklift_whole.png", "assets/wasteFork/forklift_whole.png", but8),
        Button(550 - 50, 400, 100, 100, "assets/puzzlepiece.png", "assets/puzzlepiece.png", but9),
        Button(700 - 50, 400, 100, 100, "assets/BuildTower/crate.png", "assets/BuildTower/crate.png", but10),
        Button(100 - 50, 600, 100, 100, "assets/jetStream/combatjet-highres.png", "assets/jetStream/combatjet-highres.png", but11),
        Button(250 - 50, 600, 100, 100, "assets/wasteTacToe.png", "assets/wasteTacToe.png", but12),
        Button(400 - 50, 600, 100, 100, "assets/ClimbingHog/ghost.png", "assets/ClimbingHog/ghost.png", but13),
        Button(550 - 50, 600, 100, 100, "assets/Asteroid.png", "assets/Asteroid.png", but14),
        Button(700 - 50, 600, 100, 100, "assets/wasteBin_empty.png", "assets/wasteBin_empty.png", but15),
        Button(100 - 50, 800, 100, 100, "assets/wastePilot/stick.png", "assets/wastePilot/stick.png", but16),
        Button(250 - 50, 800, 100, 100, "assets/pong.jpg", "assets/pong.jpg", but17),
        Button(400 - 50, 800, 100, 100, "assets/wastePizza/pizza.png", "assets/wastePizza/pizza.png", but18),
        Button(550 - 50, 800, 100, 100, "assets/wastehockey/puck.png", "assets/wastehockey/puck.png", but19),
        Button(700 - 50, 800, 100, 100, "assets/wasteGOL/tree.png", "assets/wasteGOL/tree.png", but20),
        Button(100 - 50, 1000, 100, 100, "assets/wasteBird/frame-2.png", "assets/wasteBird/dead.png", but21),
        Button(250 - 50, 1000, 100, 100, "assets/wasteHog/gift.png", "assets/wasteHog/gift.png", but22),
        Button(400 - 50, 1000, 100, 100, "assets/hungryHedgie/hedgie.png", "assets/hungryHedgie/hedgie.png", but23),

    ]
    bg_im = pygame.image.load("assets/main_menu_background.png").convert_alpha()
    dragging = False
    start_pos = None
    while True:
        selected_game_func = None

        while not selected_game_func:
            screen.fill((10, 10, 30))
            screen.blit(bg_im, (0, 0))
            title = font.render("Game Menu", True, (255, 255, 255))
            screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

                if event.type == pygame.MOUSEBUTTONDOWN:
                    start_pos = event.pos
                    dragging = True

                if event.type == pygame.MOUSEBUTTONUP:
                    dragging = False

                if event.type == pygame.MOUSEMOTION and dragging:
                    dy = event.rel[1]
                    if dy < 0:
                        if not any(b.rect.centery < -300 for b in buttons):
                            for button in buttons:
                                button.y = button.y + dy
                    if dy > 0:
                        if not any(b.rect.centery > screen.get_height() + 300 for b in buttons):
                            for button in buttons:
                                button.y = button.y + dy

            for button in buttons:
                button.update(events)
                button.draw(screen)

            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0)

        # Run the selected game and wait for it to finish
        await selected_game_func(screen, clock)


# Run main loop
if __name__ == "__main__":
    try:
        asyncio.run(game_menu())
    except RuntimeError:
        import nest_asyncio

        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(game_menu())
