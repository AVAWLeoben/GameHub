# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Button
import pygame
import asyncio
import random as rd

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None


def ret():
    global RUNNING
    RUNNING = False


class Recipe:
    def __init__(self, x=700, y=125):
        self.x = x
        self.y = y
        self.image = RECIPE_IMAGE
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.nIngredients = rd.randint(1, len(INGREDIENT_IMAGES))
        self.ingredients = []
        self.amount_ingredients = []
        self.ingredients.clear()
        self.amount_ingredients.clear()
        self.ncorrect_ingredients = 0
        self.correct_ingredients = []
        self.ingredient_counts = {ingredient: 0 for ingredient in INGREDIENT_IMAGES}
        PIZZA.ingredient_counts = {ingredient: 0 for ingredient in INGREDIENT_IMAGES}
        self.correct = False
        INGREDIENTS.clear()
        for i in range(self.nIngredients):
            try:
                new_ingredient = rd.choice(list(set(INGREDIENT_IMAGES.keys()) - set(self.ingredients)))
            except Exception as e:
                print(e)
                new_ingredient = "Tomato"
            self.ingredients.append(new_ingredient)
            self.amount_ingredients.append(rd.randint(2, 5))

    def checkWin(self):
        # Reset counts
        self.ingredient_counts = {ingredient: 0 for ingredient in INGREDIENT_IMAGES}
        self.correct_ingredients.clear()
        self.ncorrect_ingredients = 0

        # Count all placed ingredients on the pizza
        for ingredient in INGREDIENTS:
            if ingredient.placed:
                self.ingredient_counts[ingredient.typ] += 1

        # Compare with recipe
        for ingredient, required_amount in zip(self.ingredients, self.amount_ingredients):
            if self.ingredient_counts.get(ingredient, 0) == required_amount:
                self.correct_ingredients.append(ingredient)
                self.ncorrect_ingredients += 1

        # Final check for full correctness
        self.correct = self.ncorrect_ingredients == self.nIngredients
        print(self.correct)
        global WINSCREEN
        if self.correct:
            WINSCREEN = Winscreen()

    def update(self):
        for e in EVENTS:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    self.__init__()

        # Check if recipe is correct
        self.checkWin()

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        # Set the starting Y position slightly below the top of the recipe sheet
        start_x = self.rect.left + 20  # Margin from the left edge
        start_y = self.rect.top + 40

        for index, (ingredient, amount) in enumerate(zip(self.ingredients, self.amount_ingredients)):
            text = f"{amount}x {ingredient.capitalize()}"
            text = f"{amount}x "
            rendered_text = FONT.render(text, True, (0, 0, 0))  # Black text
            SCREEN.blit(rendered_text, (start_x, start_y + index * 40))  # 40px vertical spacing
            ingredient_image = INGREDIENT_IMAGES.get(ingredient)
            ingredient_image = pygame.transform.scale(ingredient_image, (60, 60))
            SCREEN.blit(ingredient_image, (start_x + 80, start_y + index * 40))
            if ingredient in self.correct_ingredients:
                SCREEN.blit(CHECKMARK_IMAGE, (start_x + 80, start_y + index * 40))


class IngredientButton:
    def __init__(self, x, y, typ):
        self.x = x
        self.y = y
        self.typ = typ
        self.size = 75
        self.image = INGREDIENT_IMAGES.get(self.typ)
        self.image = pygame.transform.scale(self.image, (self.size, self.size))
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def update(self):
        for e in EVENTS:
            if e.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if self.rect.collidepoint(pos):
                    Ingredient(self.rect.centerx, self.rect.centery, self.typ)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Cuttingboard:
    def __init__(self, x=700, y=450):
        self.x = x
        self.y = y
        self.image = CUTTINGBOARD_IMAGE
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.ingredient_buttons = []

        # Grid settings
        cols = 2
        padding = 10
        button_width = 75
        button_height = 75
        spacing_x = 10
        spacing_y = 20

        ingredients = list(INGREDIENT_IMAGES.keys())

        for idx, ingredient in enumerate(ingredients):
            row = idx // cols
            col = idx % cols

            # Calculate button position
            start_x = self.rect.left + 10 + padding
            start_y = self.rect.top + 10 + padding

            btn_x = start_x + col * (button_width + spacing_x)
            btn_y = start_y + row * (button_height + spacing_y)

            button = IngredientButton(btn_x, btn_y, ingredient)
            self.ingredient_buttons.append(button)

    def update(self):
        for button in self.ingredient_buttons:
            button.update()

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        for button in self.ingredient_buttons:
            button.draw()


class Ingredient:
    def __init__(self, x, y, typ):
        self.x = x
        self.y = y
        self.typ = typ
        self.size = 100
        self.image = INGREDIENT_IMAGES.get(self.typ)
        self.image = pygame.transform.scale(self.image, (self.size, self.size))
        self.mask = pygame.mask.from_surface(self.image)
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.placed = False
        self.counted = False
        INGREDIENTS.append(self)

    def checkCollisionWithPizza(self):
        offset_x = PIZZA.rect.left - self.rect.left
        offset_y = PIZZA.rect.top - self.rect.top
        return self.mask.overlap(PIZZA.mask, (offset_x, offset_y))

    def update(self):
        global PICKED_INGREDIENT
        mouse_pressed = pygame.mouse.get_pressed()[0]  # Left mouse button
        mouse_pos = pygame.mouse.get_pos()

        if not self.placed or self.placed:
            if (
                mouse_pressed
                and (self.rect.collidepoint(mouse_pos) or PICKED_INGREDIENT == self)
                and (PICKED_INGREDIENT == None or PICKED_INGREDIENT == self)
            ):
                self.x, self.y = mouse_pos
                PICKED_INGREDIENT = self
            elif not mouse_pressed:
                PICKED_INGREDIENT = None
                if self.checkCollisionWithPizza():
                    self.placed = True
                else:
                    INGREDIENTS.remove(self)  # Discard if not on pizza

        self.rect.center = (self.x, self.y)

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class Pizza:
    def __init__(self, x=300, y=300):
        self.x = x
        self.y = y
        self.image = PIZZA_IMAGE
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.mask = pygame.mask.from_surface(self.image)
        self.ingredient_counts = {ingredient: 0 for ingredient in INGREDIENT_IMAGES}

    def update(self):
        pass

    def draw(self):
        SCREEN.blit(self.image, self.rect)


class ResetPizzaButton:
    def __init__(self, x=10, y=500):
        self.x = x
        self.y = y
        self.image = pygame.transform.scale(PIZZA_IMAGE, (75, 75))
        self.rect = self.image.get_rect(topleft=(self.x, self.y))
        self.pressed = False

    def update(self):
        for e in EVENTS:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(e.pos):
                    INGREDIENTS.clear()

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        mouse_pos = pygame.mouse.get_pos()

        border_color = pygame.Color("white") if self.rect.collidepoint(mouse_pos) else pygame.Color("black")

        pygame.draw.rect(SCREEN, border_color, self.rect, width=2, border_radius=12)


class Winscreen:
    def __init__(self):
        self.image = PIZZACHEF_IMAGE
        self.rect = self.image.get_rect(centerx=400)
        self.rect.top = SCREEN.get_rect().bottom  # Start off-screen at bottom

        # Create styled text manually with outline and shadow
        self.text = "GREAT PIZZA"
        self.font = pygame.font.Font("assets/wastePizza/Italiana.ttf", 72)

        self.winmessage = self.render_styled_text(self.text)
        self.winmessage_rect = self.winmessage.get_rect(center=(400, 300))

        self.framecounter = 0
        self.animation_phase = 0  # 0 = slide in, 1 = message & stars, 2 = reset
        self.stars_displayed = []

    def render_styled_text(self, text):
        """Render text with shadow and outline."""
        base_color = pygame.Color("white")
        shadow_color = pygame.Color("black")
        outline_color = pygame.Color("darkred")

        # Render shadow
        shadow = self.font.render(text, True, shadow_color)

        # Render outline by blitting multiple layers
        outline = pygame.Surface((shadow.get_width() + 4, shadow.get_height() + 4), pygame.SRCALPHA)
        for dx in [-2, 0, 2]:
            for dy in [-2, 0, 2]:
                if dx != 0 or dy != 0:
                    temp = self.font.render(text, True, outline_color)
                    outline.blit(temp, (dx + 2, dy + 2))

        # Render main text
        main = self.font.render(text, True, base_color)
        outline.blit(main, (2, 2))
        outline.blit(shadow, (4, 4))  # optional: add shadow offset

        return outline

    def update(self):
        if self.animation_phase == 0:
            self.rect.centery -= 3
            if self.rect.bottom <= SCREEN.get_rect().bottom:
                self.rect.bottom = SCREEN.get_rect().bottom
                self.animation_phase = 1
                self.framecounter = 0

        elif self.animation_phase == 1:
            self.framecounter += 1
            star_timing = {
                20: [(400, 10)],
                40: [(300, 50), (500, 50)],
                60: [(200, 100), (600, 100)],
                80: [(100, 150), (700, 150)],
            }
            if self.framecounter in star_timing:
                self.stars_displayed.extend(star_timing[self.framecounter])

            if self.framecounter >= 120:
                self.animation_phase = 2

        elif self.animation_phase == 2:
            RECIPE.__init__()  # Reset recipe
            self.animation_phase = 3  # Prevent re-triggering

    def draw(self):
        SCREEN.blit(self.image, self.rect)
        if self.animation_phase >= 1:
            SCREEN.blit(self.winmessage, self.winmessage_rect)
            for pos in self.stars_displayed:
                SCREEN.blit(STAR_IMAGE, pos)


def setup():
    global HOME_BUTTON
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    global BACKGROUND_IMAGE
    BACKGROUND_IMAGE = pygame.image.load("assets/wastePizza/kitchen.png")
    BACKGROUND_IMAGE = pygame.transform.scale(BACKGROUND_IMAGE, (800, 600))

    global PIZZA_IMAGE
    PIZZA_IMAGE = pygame.image.load("assets/wastePizza/pizza.png")
    PIZZA_IMAGE = pygame.transform.scale(PIZZA_IMAGE, (600, 600))

    global RECIPE_IMAGE
    RECIPE_IMAGE = pygame.image.load("assets/wastePizza/recipe_card.png")
    RECIPE_IMAGE = pygame.transform.scale(RECIPE_IMAGE, (200, 250))

    global CHECKMARK_IMAGE
    CHECKMARK_IMAGE = pygame.image.load("assets/wastePizza/checkmark.png")
    CHECKMARK_IMAGE = pygame.transform.scale(CHECKMARK_IMAGE, (50, 50))

    global CUTTINGBOARD_IMAGE
    CUTTINGBOARD_IMAGE = pygame.image.load("assets/wastePizza/cutting_board.png")
    CUTTINGBOARD_IMAGE = pygame.transform.scale_by(CUTTINGBOARD_IMAGE, (0.75, 0.75))

    global INGREDIENT_IMAGES
    INGREDIENT_IMAGES = {
        "Tomato": pygame.transform.scale(pygame.image.load("assets/wastePizza/tomato.png"), (100, 100)),
        "Cheese": pygame.transform.scale(pygame.image.load("assets/wastePizza/cheese.png"), (100, 100)),
        "Mushroom": pygame.transform.scale(pygame.image.load("assets/wastePizza/mushroom.png"), (100, 100)),
        "Mozzarella": pygame.transform.scale(pygame.image.load("assets/wastePizza/mozzarella.png"), (100, 100)),
    }

    global PIZZACHEF_IMAGE
    PIZZACHEF_IMAGE = pygame.image.load("assets/wastePizza/pizzachef.png")

    global STAR_IMAGE
    STAR_IMAGE = pygame.image.load("assets/wastePizza/star.png")

    global FONT
    # Initialize Pygame font module
    pygame.font.init()
    # Global font load
    FONT = pygame.font.Font("assets/wastePizza/Italiana.ttf", 36)  # Adjust size as needed

    global PIZZA
    PIZZA = Pizza()

    global INGREDIENTS
    INGREDIENTS = []

    global PICKED_INGREDIENT
    PICKED_INGREDIENT = None

    global RECIPE
    RECIPE = Recipe()

    global CUTTINGBOARD
    CUTTINGBOARD = Cuttingboard()

    global RESETPIZZABUTTON
    RESETPIZZABUTTON = ResetPizzaButton()


def update():
    global RUNNING
    HOME_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False

    if RECIPE.correct:
        WINSCREEN.update()
    else:
        PIZZA.update()
        RECIPE.update()
        CUTTINGBOARD.update()
        RESETPIZZABUTTON.update()
        for i in INGREDIENTS:
            i.update()


def draw():
    SCREEN.fill((10, 10, 30))
    SCREEN.blit(BACKGROUND_IMAGE, (0, 0))

    RESETPIZZABUTTON.draw()
    PIZZA.draw()
    RECIPE.draw()
    CUTTINGBOARD.draw()
    for i in INGREDIENTS:
        i.draw()
    if RECIPE.correct:
        WINSCREEN.draw()

    HOME_BUTTON.draw(SCREEN)
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


def main_test():
    global RUNNING, SCREEN, CLOCK, EVENTS
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Game Hub")
    CLOCK = pygame.time.Clock()
    setup()
    while RUNNING:
        CLOCK.tick(FPS)
        EVENTS = pygame.event.get()
        update()
        draw()
    pygame.quit()
    return


# main_test()
