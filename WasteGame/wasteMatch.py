# wasteMatch.py

import pygame
import random
import os
import asyncio
from GUI import Button

WIDTH, HEIGHT = 800, 600
ROWS, COLS = 4, 4
CARD_SIZE = 100
PADDING = 20
FPS = 60
RUNNING = True


def load_images():
    images = []
    for i in range(1, 9):
        img = pygame.image.load(os.path.join("assets", f"card_{i}.png"))
        img = pygame.transform.scale(img, (CARD_SIZE, CARD_SIZE))
        images.append(img)
    back = pygame.image.load(os.path.join("assets", "card_back.png"))
    back = pygame.transform.scale(back, (CARD_SIZE, CARD_SIZE))
    background = pygame.image.load("assets/wasteMatchBackground.PNG")
    background = pygame.transform.scale(background, (WIDTH, HEIGHT))
    return images, back, background


card_images, card_back, BACKGROUND = load_images()


class Truck:
    def __init__(self, image):
        self.image = pygame.image.load("assets/wasteTruck_leftFacing.png")
        self.image = pygame.transform.flip(self.image, True, False)
        self.x = -100
        self.y = 540
        self.vx = 1
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def update(self):
        self.x = self.x + self.vx
        if self.x > 900 and self.vx > 0:
            self.vx = self.vx * -1
            self.image = pygame.transform.flip(self.image, True, False)
            self.x = random.randint(900, 1100)
        if self.x < -100 and self.vx < 0:
            self.vx = self.vx * -1
            self.image = pygame.transform.flip(self.image, True, False)
            self.x = random.randint(-300, -100)

        self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Card:
    def __init__(self, image, position):
        self.original_image = image
        self.rect = pygame.Rect(position[0], position[1], CARD_SIZE, CARD_SIZE)
        self.flipped = False
        self.matched = False
        self.animating = False
        self.flip_progress = 0.0
        self.flip_forward = True
        self.showing_back = True

    def start_flip(self):
        if not self.animating:
            self.animating = True
            self.flip_progress = 0.0
            self.flip_forward = True

    def update(self):
        if self.animating:
            self.flip_progress += 0.15
            if self.flip_progress >= 1.0:
                self.flip_progress = 1.0
                if self.flip_forward:
                    self.flip_forward = False
                    self.flip_progress = 0.0
                    self.showing_back = not self.showing_back
                else:
                    self.animating = False
                    self.flipped = not self.showing_back

    def draw(self, surface):
        image = self.original_image if not self.showing_back else card_back
        if self.animating:
            scale = abs(1.0 - 2.0 * self.flip_progress)
            width = max(1, int(CARD_SIZE * scale))
            scaled = pygame.transform.scale(image, (width, CARD_SIZE))
            draw_x = self.rect.x + (CARD_SIZE - width) // 2
            surface.blit(scaled, (draw_x, self.rect.y))
            # pygame.draw.rect(surface, (255, 255, 255), self.rect, 3)
        else:
            surface.blit(image, self.rect)
            pygame.draw.rect(surface, (255, 255, 255), self.rect, 3)


def create_board():
    images = card_images * 2
    random.shuffle(images)
    cards = []
    for row in range(ROWS):
        for col in range(COLS):
            x = col * (CARD_SIZE + PADDING) + PADDING
            y = row * (CARD_SIZE + PADDING) + PADDING
            card = Card(images.pop(), (x + 50, y))
            cards.append(card)
    return cards


def draw(screen, cards, win):
    screen.fill((30, 30, 30))
    screen.blit(BACKGROUND, (0, 0))
    for card in cards:
        card.draw(screen)
    if win:
        font = pygame.font.Font("assets/font.ttf", 60)
        text = font.render("You Win!", True, (255, 255, 255))
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT - 80))
    truck.draw(screen)
    home_button.draw(screen)
    pygame.display.flip()


def ret():
    global RUNNING
    RUNNING = False


home_button = Button(10, 500, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
truck = Truck("assets/wasteTruck_leftFacing.png")


# ✅ Main game function now accepts screen and clock
async def main(screen, clock):
    global RUNNING
    RUNNING = True

    cards = create_board()
    flipped_cards = []
    waiting = False
    wait_start = 0
    win = False

    while RUNNING:
        clock.tick(FPS)
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.MOUSEBUTTONDOWN and not waiting and not win:
                pos = pygame.mouse.get_pos()
                for card in cards:
                    if card.rect.collidepoint(pos) and not card.flipped and not card.matched and not card.animating:
                        card.start_flip()
                        flipped_cards.append(card)
                        break

        for card in cards:
            card.update()

        if not waiting and len(flipped_cards) == 2:
            if not any(card.animating for card in flipped_cards):
                if flipped_cards[0].original_image == flipped_cards[1].original_image:
                    flipped_cards[0].matched = True
                    flipped_cards[1].matched = True
                    flipped_cards.clear()
                    if all(c.matched for c in cards):
                        win = True
                else:
                    waiting = True
                    wait_start = pygame.time.get_ticks()

        if waiting and pygame.time.get_ticks() - wait_start > 1000:
            for card in flipped_cards:
                card.start_flip()
            flipped_cards.clear()
            waiting = False
        truck.update()
        home_button.update(events)
        draw(screen, cards, win)

        pygame.display.flip()

        await asyncio.sleep(0)
        if win:
            return
    return
