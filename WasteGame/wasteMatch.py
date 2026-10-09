"""WasteGame memory game: Pygbag-friendly, one or two players.

Two-player rules: +1 per pair, a correct match grants another turn,
otherwise the turn passes to the other player.
"""
import asyncio
import math
import os
import random
import pygame
from GUI import Button

WIDTH, HEIGHT = 800, 600
ROWS = COLS = 4
CARD_SIZE, PADDING = 100, 15
GRID_X, GRID_Y = 58, 24
FPS = 60
MISS_DELAY = 1100
MATCH_DELAY = 550
COLORS = ((75, 175, 255), (255, 164, 83))

RUNNING = False


def ret():
    global RUNNING
    RUNNING = False


class Card:
    def __init__(self, pair_id, position):
        self.pair_id = pair_id
        self.rect = pygame.Rect(*position, CARD_SIZE, CARD_SIZE)
        self.face_up = False
        self.matched = False
        self.progress = 0.0
        self.target = 0.0

    def reveal(self):
        self.target = 1.0

    def hide(self):
        self.target = 0.0

    def update(self, dt):
        direction = 1 if self.target > self.progress else -1
        if self.progress != self.target:
            self.progress = max(0.0, min(1.0, self.progress + direction * 5.5 * dt))
            if direction > 0:
                self.progress = min(self.target, self.progress)
            else:
                self.progress = max(self.target, self.progress)
        self.face_up = self.progress >= 0.5

    def draw(self, screen, fronts, back):
        w = max(1, round(CARD_SIZE * abs(1 - 2 * self.progress)))
        face = fronts[self.pair_id] if self.face_up or self.matched else back
        image = pygame.transform.scale(face, (w, CARD_SIZE))
        screen.blit(image, (self.rect.centerx - w // 2, self.rect.y))
        if self.matched:
            pygame.draw.rect(screen, (122, 231, 129), self.rect, 3, border_radius=5)
        elif self.progress in (0.0, 1.0):
            pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=4)


class Particle:
    def __init__(self, x, y):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(70, 205)
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed - 75
        self.life = random.uniform(0.45, 0.95)
        self.max_life = self.life
        self.color = random.choice(((255, 226, 93), (116, 242, 151), (255, 143, 190), (113, 211, 255)))
        self.radius = random.randint(3, 7)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 260 * dt
        self.life -= dt

    def draw(self, screen):
        if self.life > 0:
            radius = max(1, round(self.radius * self.life / self.max_life))
            pygame.draw.circle(screen, self.color, (round(self.x), round(self.y)), radius)


def load_images():
    fronts = []
    for i in range(1, 9):
        image = pygame.image.load(os.path.join('assets', f'card_{i}.png')).convert_alpha()
        fronts.append(pygame.transform.scale(image, (CARD_SIZE, CARD_SIZE)))
    back = pygame.transform.scale(pygame.image.load('assets/card_back.png').convert_alpha(), (CARD_SIZE, CARD_SIZE))
    background = pygame.transform.scale(pygame.image.load('assets/wasteMatchBackground.PNG').convert(), (WIDTH, HEIGHT))
    return fronts, back, background


def create_board():
    ids = list(range(8)) * 2
    random.shuffle(ids)
    return [Card(ids[row * COLS + col], (GRID_X + col * (CARD_SIZE + PADDING), GRID_Y + row * (CARD_SIZE + PADDING)))
            for row in range(ROWS) for col in range(COLS)]


class MemoryGame:
    def __init__(self):
        self.cards = create_board()
        self.players = 0  # 0 = choose number of players
        self.turn = 0
        self.scores = [0, 0]
        self.selected = []
        self.state = 'choose'  # choose / first / second / resolve / finished
        self.resolve_at = 0
        self.is_match = False
        self.particles = []
        self.matches = 0

    def choose(self, players):
        self.__init__()
        self.players = players
        self.state = 'first'

    def click_card(self, pos, now):
        if self.state not in ('first', 'second'):
            return False
        for card in self.cards:
            if not card.rect.collidepoint(pos) or card.target != 0.0 or card.matched:
                continue
            card.reveal()
            self.selected.append(card)
            if len(self.selected) == 1:
                self.state = 'second'
            else:
                # Lock immediately: no third click can be processed in this frame.
                self.is_match = self.selected[0].pair_id == self.selected[1].pair_id
                self.resolve_at = now + (MATCH_DELAY if self.is_match else MISS_DELAY)
                self.state = 'resolve'
                if self.is_match:
                    for selected in self.selected:
                        cx, cy = selected.rect.center
                        self.particles.extend(Particle(cx, cy) for _ in range(22))
            return True
        return False

    def update(self, dt, now):
        for card in self.cards:
            card.update(dt)
        for particle in self.particles:
            particle.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        if self.state == 'resolve' and now >= self.resolve_at:
            if self.is_match:
                for card in self.selected:
                    card.matched = True
                self.scores[self.turn] += 1
                self.matches += 1
            else:
                for card in self.selected:
                    card.hide()
                if self.players == 2:
                    self.turn = 1 - self.turn
            self.selected.clear()
            self.state = 'finished' if self.matches == 8 else ('closing' if not self.is_match else 'first')
        if self.state == 'closing' and all(c.progress == 0 for c in self.cards if not c.matched):
            self.state = 'first'


def text(screen, font, message, center, color=(255, 255, 255)):
    image = font.render(message, True, color)
    screen.blit(image, image.get_rect(center=center))


def draw_button(screen, rect, label, font, fill):
    pygame.draw.rect(screen, (20, 40, 49), rect.move(0, 4), border_radius=13)
    pygame.draw.rect(screen, fill, rect, border_radius=13)
    pygame.draw.rect(screen, (255, 255, 255), rect, 3, border_radius=13)
    text(screen, font, label, rect.center)


def draw(screen, game, fronts, back, background, fonts, home_button):
    big, medium, small = fonts
    screen.blit(background, (0, 0))
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 66))
    screen.blit(shade, (0, 0))
    for card in game.cards:
        card.draw(screen, fronts, back)
    for particle in game.particles:
        particle.draw(screen)
    hud = pygame.Rect(540, 17, 248, 470)
    pygame.draw.rect(screen, (18, 44, 59), hud, border_radius=16)
    pygame.draw.rect(screen, (163, 207, 216), hud, 2, border_radius=16)
    text(screen, medium, 'MEMORY', (hud.centerx, 53))
    if game.players:
        if game.players == 2:
            for player in (0, 1):
                y = 135 + 99 * player
                color = COLORS[player] if game.turn == player else (140, 154, 163)
                pygame.draw.rect(screen, color, pygame.Rect(551, y - 33, 224, 77), 3 if game.turn == player else 1, border_radius=10)
                text(screen, small, f'Player {player + 1}', (665, y - 11), color)
                text(screen, medium, str(game.scores[player]), (665, y + 20), (255, 255, 255))
            if game.state != 'finished':
                text(screen, small, f'Player {game.turn + 1} turn', (664, 348), COLORS[game.turn])
        else:
            text(screen, small, 'Pairs found', (664, 137))
            text(screen, big, f'{game.matches} / 8', (664, 190))
        if game.state == 'resolve':
            text(screen, small, 'Match!' if game.is_match else 'Try again!', (664, 394))
        if game.state == 'finished':
            if game.players == 2:
                if game.scores[0] == game.scores[1]:
                    message = 'It is a tie!'
                else:
                    message = f'Player {1 if game.scores[0] > game.scores[1] else 2} wins!'
            else:
                message = 'Well done!'
            text(screen, small, message, (664, 370), (255, 237, 126))
            draw_button(screen, pygame.Rect(558, 415, 211, 53), 'Play again', small, (39, 133, 89))
    if game.state == 'choose':
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 25, 35, 205))
        screen.blit(overlay, (0, 0))
        pygame.draw.rect(screen, (29, 64, 78), (160, 140, 480, 322), border_radius=22)
        pygame.draw.rect(screen, (194, 232, 224), (160, 140, 480, 322), 3, border_radius=22)
        text(screen, big, 'Memory Game', (400, 203))
        text(screen, small, 'How many players?', (400, 253))
        draw_button(screen, pygame.Rect(195, 300, 185, 85), '1 Player', medium, COLORS[0])
        draw_button(screen, pygame.Rect(420, 300, 185, 85), '2 Players', medium, COLORS[1])
        text(screen, small, 'Match pairs to score points!', (400, 425))
    home_button.draw(screen)
    pygame.display.flip()


def positions_from_event(event, screen):
    if event.type == pygame.FINGERDOWN:
        w, h = screen.get_size()
        return (int(event.x * w), int(event.y * h))
    if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', 1) == 1:
        # SDL marks synthesized touch-to-mouse events with touch=True.
        if getattr(event, 'touch', False):
            return None
        return event.pos
    return None


async def main(screen, clock):
    global RUNNING
    RUNNING = True
    fronts, back, background = load_images()
    fonts = (pygame.font.Font(None, 51), pygame.font.Font(None, 37), pygame.font.Font(None, 28))
    home_button = Button(10, 500, 95, 95, 'assets/retBut.png', 'assets/retBut_clicked.png', ret)
    game = MemoryGame()
    # Prevent a tap from also selecting a card when returning to the menu.
    while RUNNING:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        now = pygame.time.get_ticks()
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                RUNNING = False
                break
            pos = positions_from_event(event, screen)
            if pos is None:
                continue
            if home_button.rect.collidepoint(pos):
                ret()
                break
            if game.state == 'choose':
                if pygame.Rect(195, 300, 185, 85).collidepoint(pos):
                    game.choose(1)
                elif pygame.Rect(420, 300, 185, 85).collidepoint(pos):
                    game.choose(2)
            elif game.state == 'finished':
                if pygame.Rect(558, 415, 211, 53).collidepoint(pos):
                    game = MemoryGame()
            else:
                game.click_card(pos, now)
        if not RUNNING:
            break
        game.update(dt, now)
        draw(screen, game, fronts, back, background, fonts, home_button)
        await asyncio.sleep(0)
