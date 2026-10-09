# -*- coding: utf-8 -*-
"""
Created on Mon May  5 14:22:03 2025

@author: GKoinig
"""

import asyncio
import pygame
import random
from GUI import Button

running = True
pygame.init()
# screen = pygame.display.set_mode((800, 640))
# clock = pygame.time.Clock()

objects = []
bins = []
background = None
currLevel = -1
nLevels = 5

colours = {"Plastik": (255, 255, 0), "Bio": (139, 69, 19), "Papier": (255, 0, 0), "Glas": (46, 158, 56)}

selected_obj = None
dragging = False
last_mouse_pos = (0, 0)
nObjects = 0
correctObjects = 0
data_folder = "assets/"


class Object:
    def __init__(self, x, y, w, h, colour, thickness=-1, img_path=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.col = colour
        self.xm = int(x + w / 2)
        self.ym = int(y + h / 2)
        if img_path:
            self.img = pygame.image.load(img_path).convert_alpha()
            self.img = pygame.transform.scale(self.img, (self.w, self.h))
        else:
            self.img = None

        if thickness == -1:
            self.thickness = 0
        else:
            self.thickness = thickness
        self.rect = pygame.Rect(x, y, w, h)

        self.scale_direction = random.choice([-1, 1])
        self.max_scale = 1.1
        self.min_scale = 0.95
        self.scale = random.uniform(self.min_scale, self.max_scale)  # Start at a random point
        self.scale_speed = random.uniform(0.002, 0.01)  # Different speed per object
        self.scale_speed = 0.003  # How fast it scales

    def update(self):
        self.scale += self.scale_direction * self.scale_speed
        if self.scale >= self.max_scale:
            self.scale = self.max_scale
            self.scale_direction = -1
        elif self.scale <= self.min_scale:
            self.scale = self.min_scale
            self.scale_direction = 1

    def draw(self, screen):
        if self.img:
            self.update()
            original_size = self.img.get_size()
            scaled_size = (int(original_size[0] * self.scale), int(original_size[1] * self.scale))
            scaled_img = pygame.transform.scale(self.img, scaled_size)
            new_rect = scaled_img.get_rect(center=self.rect.center)
            screen.blit(scaled_img, new_rect.topleft)
            # pygame.draw.rect(screen,self.col,self.rect,self.thickness)

    def get_collission(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)

    def get_dragged(self, event, last_mouse_pos):
        dx = event.pos[0] - last_mouse_pos[0]
        dy = event.pos[1] - last_mouse_pos[1]
        self.x = self.x + dx
        self.y = self.y + dy
        self.rect.topleft = (self.x, self.y)
        for bin in bins:
            if bin.get_collission(event.pos) and bin.col == self.col:
                bin.open()
            else:
                bin.close()
        return event.pos

    def get_dropped(self, event, bin):
        global correctObjects
        if bin.rect.collidepoint(event.pos) and bin.col == self.col:
            self.rect.topleft = (2000, 2000)
            bin.close()
            correctObjects = correctObjects + 1


class Bin:
    def __init__(self, x, y, w, h, colour, thickness=-1, img_closed_path=None, img_open_path=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.col = colour
        self.xm = int(x + w / 2)
        self.ym = int(y + h / 2)
        self.opened = 0
        self.angle = 0
        self.rotate_speed = 0.25
        self.rotate_direction = random.choice([-1, 1])
        self.maxAngle = 5

        if img_closed_path:
            self.img_closed = pygame.image.load(img_closed_path).convert_alpha()
            self.img_closed = pygame.transform.scale(self.img_closed, (self.w, self.h))
            self.img_curr = self.img_closed
        else:
            self.img_curr = None
        if img_open_path:
            self.img_open = pygame.image.load(img_open_path).convert_alpha()
            # self.img_open = pygame.transform.scale(self.img_open,(self.w,self.h))
        else:
            self.img_open = None
        if thickness == -1:
            self.thickness = 0
        else:
            self.thickness = thickness
        self.rect = pygame.Rect(x, y, w, h)

    def update(self):
        if self.angle >= self.maxAngle:
            self.rotate_direction = -1
        if self.angle <= -self.maxAngle:
            self.rotate_direction = 1

        self.angle = self.angle + self.rotate_speed * self.rotate_direction

    def draw(self, screen):
        if self.img_curr:
            self.update()
            rotated_image = pygame.transform.rotate(self.img_curr, self.angle)
            if self.opened:
                screen.blit(rotated_image, (self.rect.topleft[0], self.rect.topleft[1] - 25))
            else:
                screen.blit(rotated_image, self.rect.topleft)
        # pygame.draw.rect(screen,self.col,self.rect,self.thickness)

    def get_collission(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)

    def get_dropped(self, event, contrahent):
        if contrahent.rect.collidepoint(event.pos) and contrahent.col == self.col:
            self.rect.topleft = (2000, 2000)

    def open(self):
        self.img_curr = self.img_open
        self.opened = 1

    def close(self):
        self.img_curr = self.img_closed
        self.opened = 0


class Level:
    def __init__(self, figures, bins, background):
        self.figures = figures
        self.bins = bins
        self.background = background


def load_level_1():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 1
    objects = []
    obj1 = Object(11, 458, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(241, 378, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(404, 367, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(397, 237, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(588, 239, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level1.png")
    correctObjects = 0


def load_level_2():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 2
    objects = []
    obj1 = Object(550, 492, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(366, 548, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(388, 285, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(453, 290, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(4, 520, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level2.png").convert()
    correctObjects = 0


def load_level_3():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 3
    objects = []
    obj1 = Object(550, 492, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(366, 548, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(388, 285, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(453, 290, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(4, 520, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level3.png").convert()
    correctObjects = 0


def load_level_4():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 4
    objects = []
    obj1 = Object(550, 492, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(366, 548, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(388, 285, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(453, 290, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(4, 520, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level4.png").convert()
    correctObjects = 0


def load_level_5():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 5
    objects = []
    obj1 = Object(550, 492, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(366, 548, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(388, 285, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(453, 290, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(4, 520, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level5.png").convert()
    correctObjects = 0


def load_level_6():
    global objects, bins, background, nObjects, currLevel, correctObjects
    currLevel = 6
    objects = []
    obj1 = Object(550, 492, 64, 64, colour=colours["Papier"], thickness=2, img_path=data_folder + "paperbox.png")
    obj2 = Object(366, 548, 64, 64, colour=colours["Bio"], thickness=2, img_path=data_folder + "banana.png")
    obj3 = Object(388, 285, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can3.png")
    obj4 = Object(453, 290, 32, 60, colour=colours["Plastik"], thickness=2, img_path=data_folder + "can4.png")
    obj5 = Object(4, 520, 37, 87, colour=colours["Glas"], thickness=2, img_path=data_folder + "glass.png")
    objects.extend([obj1, obj2, obj3, obj4, obj5])
    nObjects = len(objects)

    bins = []
    bin_yellow = Bin(
        700,
        48,
        100,
        100,
        colours["Plastik"],
        2,
        img_closed_path=data_folder + "trashBin_yellow.png",
        img_open_path=data_folder + "trashBin_yellow_open.png",
    )
    bin_red = Bin(
        700,
        196,
        100,
        100,
        colours["Papier"],
        2,
        img_closed_path=data_folder + "trashBin_red.png",
        img_open_path=data_folder + "trashBin_red_open.png",
    )
    bin_brown = Bin(
        700,
        344,
        100,
        100,
        colours["Bio"],
        2,
        img_closed_path=data_folder + "trashBin_brown.png",
        img_open_path=data_folder + "trashBin_brown_open.png",
    )
    bin_green = Bin(
        700,
        492,
        100,
        100,
        colours["Glas"],
        2,
        img_closed_path=data_folder + "trashBin_green.png",
        img_open_path=data_folder + "trashBin_green_open.png",
    )

    bins.extend([bin_yellow, bin_red, bin_brown, bin_green])

    background = pygame.image.load(data_folder + "Level6.png").convert()
    correctObjects = 0


def setup():
    pygame.display.set_caption("Unser Abfall Sortier Spiel")
    load_level_1()


def quit_game():
    global running
    running = False
    pygame.quit()


def update_screen(screen):
    global objects, bins, background
    # Spielfeld löschen
    screen.fill((255, 255, 255))  # Fills the screen with black (can choose any color you want)
    # Spielfeld zeichnen
    screen.blit(background, (0, 0))

    # Giguren zeichnen
    for bin in bins:
        bin.draw(screen)
    for obj in objects:
        obj.draw(screen)

    home_button.draw(screen)
    # Fenster aktualisieren
    pygame.display.flip()


async def get_input(events):
    global objects, bins, last_mouse_pos, dragging, selected_obj
    for event in events:
        if event.type == pygame.QUIT:
            quit_game()

        elif event.type == pygame.KEYDOWN:
            print("Key Pressed")
            if event.key == pygame.K_ESCAPE:
                quit_game()
            elif event.key == pygame.K_SPACE:
                await win()

        elif event.type == pygame.MOUSEBUTTONUP:
            dragging = False
            if selected_obj:
                for contrahent in bins:
                    selected_obj.get_dropped(event, contrahent)
                    print(selected_obj.rect.topleft)
            selected_obj = None

        elif event.type == pygame.MOUSEBUTTONDOWN:
            for obj in objects:
                if obj.get_collission(event.pos):
                    selected_obj = obj
                    dragging = True
                    last_mouse_pos = event.pos
                    break

        elif event.type == pygame.MOUSEMOTION and dragging and selected_obj:
            last_mouse_pos = selected_obj.get_dragged(event, last_mouse_pos)


async def win(screen):
    global nLevels, currLevel
    star = pygame.image.load(data_folder + "star.png").convert_alpha()
    font = pygame.font.Font(data_folder + "font.ttf", 60)
    text = font.render("All Sorted!", True, (0, 0, 0))

    # Center the text on the screen
    text_rect = text.get_rect(center=(400, 25))

    screen.fill((255, 255, 255))  # Optional: clear screen

    for angle in range(0, 361, 10):
        screen.fill((255, 255, 255))  # Optional: clear screen
        screen.blit(background, (0, 0))
        rotated_star = pygame.transform.rotate(star, angle)
        star_rect = rotated_star.get_rect(center=(400, 320))
        screen.blit(rotated_star, star_rect)
        screen.blit(text, text_rect)
        pygame.display.flip()
        await asyncio.sleep(0.003)

    for angle in range(0, -361, -10):
        screen.fill((255, 255, 255))  # Optional: clear screen
        screen.blit(background, (0, 0))
        rotated_star = pygame.transform.rotate(star, angle)
        star_rect = rotated_star.get_rect(center=(400, 320))
        screen.blit(rotated_star, star_rect)
        screen.blit(text, text_rect)
        pygame.display.flip()
        await asyncio.sleep(0.003)

    currLevel = currLevel + 1
    if currLevel == 2:
        load_level_2()
    elif currLevel == 3:
        load_level_3()
    elif currLevel == 4:
        load_level_4()
    elif currLevel == 5:
        load_level_5()
    elif currLevel == 6:
        load_level_6()
    elif currLevel == 7:
        ret()
    else:
        # pygame.quit()
        return


def ret():
    global running
    running = False


home_button = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)


async def main(screen, clock):
    global running
    running = True
    setup()

    while running:
        events = pygame.event.get()
        action = await get_input(events)
        if action == "win" or nObjects == correctObjects:
            await win(screen)
        if running:
            update_screen(screen)
            home_button.update(events)

            pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)
    return


# asyncio.run(main())
