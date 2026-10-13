# -*- coding: utf-8 -*-
"""Waste Fork — pallet stacking with scored deliveries for GameHub.

Retains the original GameHub entry point ``await main(screen, clock)`` and
loads the existing forklift, pallet, floor and Home button artwork.

Hold mouse/touch to drive toward the pointer. A pallet is collected when the
fork tips touch it. Release inside the marked bay, or press Space/Up, to drop.
Driving to the centre of the bay also automatically unloads after a short
hold. The level ends on a results screen; it does not auto-advance.
"""
import asyncio
import math
import os
import random
import pygame

W, H = 800, 600
FPS = 60
COLORS = {
    'ink': (25, 32, 48), 'paper': (250, 249, 239),
    'mint': (116, 234, 166), 'yellow': (255, 203, 102),
    'border': (217, 237, 224),
}


def _asset(name, size=None):
    root = os.path.dirname(os.path.abspath(__file__))
    paths = (os.path.join('assets', name),
             os.path.join(root, 'assets', name),
             os.path.join('WasteGame', 'assets', name))
    for path in paths:
        try:
            image = pygame.image.load(path)
            try:
                image = image.convert_alpha()
            except (pygame.error, AttributeError, ValueError):
                pass
            if size is not None and image.get_size() != size:
                image = pygame.transform.scale(image, size)
            return image
        except (pygame.error, OSError, ValueError):
            pass
    return None


def _fallback_fork():
    surf = pygame.Surface((240, 86), pygame.SRCALPHA)
    for x in (32, 142):
        pygame.draw.rect(surf, (34, 38, 42), (x, 11, 34, 14), border_radius=4)
        pygame.draw.rect(surf, (34, 38, 42), (x, 65, 34, 14), border_radius=4)
    pygame.draw.rect(surf, (238, 171, 61), (26, 20, 158, 48), border_radius=9)
    pygame.draw.rect(surf, (66, 98, 111), (105, 27, 64, 34), border_radius=4)
    for y in (29, 56):
        pygame.draw.line(surf, (205, 217, 209), (175, y), (237, y), 5)
    return surf


def _fallback_pallet():
    surf = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.rect(surf, (128, 84, 45), (6, 12, 84, 70), border_radius=4)
    for x in (16, 39, 62):
        pygame.draw.rect(surf, (193, 143, 86), (x, 10, 17, 74), border_radius=2)
    for y in (26, 64):
        pygame.draw.line(surf, (95, 65, 39), (12, y), (88, y), 3)
    return surf


def _draw_text(screen, font, s, center, color=None):
    img = font.render(str(s), True, color or COLORS['paper'])
    screen.blit(img, img.get_rect(center=center))


def _panel(screen, rect, fill=(30, 43, 55), border=(170, 209, 194)):
    pygame.draw.rect(screen, (13, 21, 30), rect.move(0, 7), border_radius=19)
    pygame.draw.rect(screen, fill, rect, border_radius=19)
    pygame.draw.rect(screen, border, rect, 3, border_radius=19)


class Pallet:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.state = 'loose'  # loose -> carried -> stacked; stacked never collectable
        self.level_index = -1
        self.dx = 0.0
        self.dy = 0.0
        self.accuracy = 0.0


class ForkGame:
    HOME = pygame.Rect(10, 10, 100, 100)
    NEXT = pygame.Rect(245, 446, 310, 66)
    AGAIN = pygame.Rect(310, 522, 180, 40)

    def __init__(self, screen, clock):
        self.screen, self.clock = screen, clock
        self.canvas = screen if screen.get_size() == (W, H) else pygame.Surface((W, H))
        sw, sh = screen.get_size()
        scale = min(sw/W, sh/H)
        self.scale_area = pygame.Rect(round((sw-W*scale)/2),
                                      round((sh-H*scale)/2),
                                      max(1, round(W*scale)), max(1, round(H*scale)))
        self.scaled_canvas = (pygame.Surface(self.scale_area.size)
                              if self.canvas is not screen and self.scale_area.size != (W,H)
                              else None)
        self.floor = _asset('wasteFork/floor.png', (W, H))
        self.target_overlay = pygame.Surface((150,150), pygame.SRCALPHA)
        self.target_overlay.fill((55,190,112,65))
        self.fork_image = _asset('wasteFork/forklift_whole.png', (240, 86)) or _fallback_fork()
        self.pallet_image = _asset('wasteFork/palette.png', (96, 96)) or _fallback_pallet()
        self.carry_image = pygame.transform.scale(self.pallet_image, (108, 108))
        self.home_image = _asset('retBut.png', (100, 100))
        self.home_pressed = _asset('retBut_clicked.png', (100, 100)) or self.home_image
        self.f_tiny = pygame.font.Font(None, 24)
        self.f_small = pygame.font.Font(None, 30)
        self.f_medium = pygame.font.Font(None, 40)
        self.f_large = pygame.font.Font(None, 84)
        self.rotation_cache = {}
        self.running = True
        self.dragging = False
        self.pointer = (0, 0)
        self.touch_id = None
        self.last_pointer_event = 0
        self.level = 1
        self.total_score = 0
        self.start_level()

    def start_level(self):
        self.state = 'PLAYING'
        self.dragging = False
        self.carried = None
        self.near_target_secs = 0.0
        self.elapsed = 0.0
        self.tier = None
        self.bonus = 0
        self.level_score = 0
        self.streak = 0
        self.total_alignment = 0.0
        self.message = 'HOLD MOUSE / TOUCH TO DRIVE  •  LIFT AT THE FORKS'
        self.message_time = 6.0
        self.target = (pygame.Rect(600, 385, 150, 150)
                       if self.level % 2 else pygame.Rect(72, 125, 150, 150))
        self.truck_x, self.truck_y = ((105.0, 116.0) if self.level % 2
                                     else (695.0, 493.0))
        self.angle = 0.0 if self.level % 2 else 180.0
        self.quantity = min(10, 6 + (self.level - 1))
        self.par_time = self.quantity * 9.0 + 8.0
        originals = [(100,300), (250,500), (400,150), (550,300),
                     (150,160), (320,395)]
        alternatives = [(600,145), (405,305), (245,505), (100,400),
                        (700,295), (525,490)]
        initial = originals if self.level % 2 else alternatives
        candidates = initial + [(x,y) for y in (150,285,410,505)
                                for x in (110,250,400,540,690)]
        rng = random.Random(1229+self.level*3301)
        positions = []
        for x, y in candidates:
            if self.target.inflate(85, 85).collidepoint(x,y):
                continue
            if math.hypot(x-self.truck_x,y-self.truck_y) < 120:
                continue
            if not any(math.hypot(x-a,y-b)<100 for a,b in positions):
                positions.append((x,y))
        if len(positions) < self.quantity:
            raise ValueError('Not enough pallet spawn locations')
        self.pallets = [Pallet(*pos) for pos in positions[:self.quantity]]
        self.placed = 0
        self.stack = []

    def note(self, msg, duration=1.75):
        self.message = msg
        self.message_time = duration

    def fork_tip(self):
        rad = math.radians(self.angle)
        return self.truck_x + math.cos(rad)*114, self.truck_y - math.sin(rad)*114

    def pickup(self):
        if self.carried is not None or self.state != 'PLAYING':
            return False
        x, y = self.fork_tip()
        loose = [p for p in self.pallets if p.state == 'loose']
        if not loose:
            return False
        pallet = min(loose, key=lambda p: math.hypot(p.x-x,p.y-y))
        if math.hypot(pallet.x-x, pallet.y-y) > 57:
            return False
        self.carried = pallet
        pallet.state = 'carried'
        self.near_target_secs = 0.0
        self.note('PALLET LIFTED  •  GUIDE IT TO THE GREEN BAY')
        return True

    def drop(self):
        if self.carried is None or self.state != 'PLAYING':
            return False
        tx, ty = self.target.center
        x, y = self.fork_tip()
        dist = math.hypot(x-tx, y-ty)
        # Only release pallets inside the designated target area.
        if dist > 58:
            self.note('MOVE THE FORK TIPS INTO THE GREEN BAY')
            return False
        pallet = self.carried
        self.carried = None
        pallet.state = 'stacked'
        pallet.level_index = len(self.stack)
        # Visible placement error, limited so the column cannot hover in air.
        pallet.dx = max(-14.0, min(14.0, (x-tx)*0.32))
        pallet.dy = max(-11.0, min(11.0, (y-ty)*0.28))
        pallet.accuracy = max(0.0, 1.0 - dist / 58.0)
        self.total_alignment += pallet.accuracy
        self.stack.append(pallet)
        self.placed += 1
        if dist <= 15:
            self.streak += 1
        else:
            self.streak = 0
        base = 100
        neat = round(170 * pallet.accuracy)
        combo = min(150, max(0, self.streak - 1) * 30)
        self.level_score += base + neat + combo
        self.near_target_secs = 0.0
        self.note(f'+{base + neat + combo}  •  ALIGNMENT {round(pallet.accuracy*100)}%')
        if self.placed == self.quantity:
            self.finish_level()
        return True

    def finish_level(self):
        self.state = 'RESULTS'
        mean = self.total_alignment / self.quantity
        speed = max(0.0, min(1.0, self.par_time/max(1.0, self.elapsed)))
        overall = 0.72*mean + 0.28*speed
        if overall >= 0.91 and mean >= 0.86:
            self.tier = 'S'
        elif overall >= 0.78:
            self.tier = 'A'
        elif overall >= 0.64:
            self.tier = 'B'
        elif overall >= 0.49:
            self.tier = 'C'
        else:
            self.tier = 'D'
        self.bonus = round(600 * speed)
        self.level_score += self.bonus
        self.total_score += self.level_score
        self.dragging = False

    def _sprite(self):
        # Rotation quantization avoids allocating a new rotated surface every frame.
        key = round(self.angle / 4.0) * 4 % 360
        if key not in self.rotation_cache:
            self.rotation_cache[key] = pygame.transform.rotate(self.fork_image, key)
        return self.rotation_cache[key]

    def _move(self, dt):
        keys = pygame.key.get_pressed()
        turn = (keys[pygame.K_a] or keys[pygame.K_LEFT]) - (keys[pygame.K_d] or keys[pygame.K_RIGHT])
        throttle = (keys[pygame.K_w]) - (keys[pygame.K_s] or keys[pygame.K_DOWN])
        if turn:
            self.angle = (self.angle + float(turn)*145*dt) % 360
        if throttle:
            rad = math.radians(self.angle)
            self.truck_x += math.cos(rad)*205*dt*throttle
            self.truck_y -= math.sin(rad)*205*dt*throttle
        elif self.dragging:
            dx, dy = self.pointer[0]-self.truck_x, self.pointer[1]-self.truck_y
            d = math.hypot(dx,dy)
            # Carrying a pallet: the pointer designates where the FORKS go.
            # Otherwise the pointer steers the forklift's centre. This makes
            # auto-unloading at the bay centre reliable, not a timed pixel hunt.
            stop_distance = 114 if self.carried is not None else 10
            if d > stop_distance:
                self.angle = math.degrees(math.atan2(-dy,dx))%360
                step = min(d-stop_distance, 225*dt)
                self.truck_x += step*dx/d
                self.truck_y += step*dy/d
        self.truck_x = max(36, min(764, self.truck_x))
        self.truck_y = max(102, min(563, self.truck_y))
        if self.carried is None:
            if self.dragging or throttle:
                self.pickup()
        else:
            tx, ty = self.target.center
            x, y = self.fork_tip()
            if math.hypot(x-tx, y-ty) < 20:
                self.near_target_secs += dt
                if self.near_target_secs >= 0.30:
                    self.drop()
            else:
                self.near_target_secs = 0.0

    def update(self, dt):
        if self.state != 'PLAYING':
            return
        self.elapsed += dt
        self.message_time = max(0, self.message_time - dt)
        self._move(dt)

    def to_world(self, pos, touch=False):
        x, y = (pos[0]*self.screen.get_width(), pos[1]*self.screen.get_height()) if touch else pos
        if not self.scale_area.collidepoint(int(x),int(y)):
            return (-1000,-1000)
        return ((x-self.scale_area.x)*W/max(1,self.scale_area.width),
                (y-self.scale_area.y)*H/max(1,self.scale_area.height))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif self.state == 'RESULTS':
                if event.key in (pygame.K_RETURN,pygame.K_SPACE):
                    self.level += 1
                    self.start_level()
                elif event.key == pygame.K_r:
                    self.start_level()
            elif event.key in (pygame.K_SPACE, pygame.K_UP):
                if self.carried is None:
                    self.pickup()
                else:
                    self.drop()
            elif event.key == pygame.K_r:
                self.start_level()
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            if event.type == pygame.MOUSEBUTTONDOWN and getattr(event,'button',1)!=1:
                return
            touch = event.type == pygame.FINGERDOWN
            pos = self.to_world((event.x,event.y) if touch else event.pos, touch)
            if self.HOME.collidepoint(pos):
                self.running = False
            elif self.state == 'RESULTS':
                if self.NEXT.collidepoint(pos):
                    self.level += 1
                    self.start_level()
                elif self.AGAIN.collidepoint(pos):
                    self.start_level()
            elif self.state == 'PLAYING' and pos != (-1000,-1000):
                self.pointer = pos
                self.dragging = True
                if touch:
                    self.touch_id = event.finger_id
        elif event.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION):
            if event.type == pygame.FINGERMOTION:
                if self.touch_id == event.finger_id:
                    self.pointer = self.to_world((event.x,event.y),True)
            elif self.dragging and self.touch_id is None:
                self.pointer = self.to_world(event.pos)
        elif event.type in (pygame.MOUSEBUTTONUP,pygame.FINGERUP):
            if event.type == pygame.MOUSEBUTTONUP and getattr(event,'button',1)!=1:
                return
            if event.type == pygame.FINGERUP:
                if self.touch_id != event.finger_id:
                    return
                self.touch_id = None
            elif self.touch_id is not None:
                return   # browser-synthesized mouse after a touch
            if self.dragging and self.carried is not None:
                x, y = self.fork_tip()
                if math.hypot(x-self.target.centerx,y-self.target.centery) <= 58:
                    self.drop()
            self.dragging = False

    def draw(self):
        surf = self.canvas
        if self.floor is not None:
            surf.blit(self.floor,(0,0))
        else:
            surf.fill((105,110,107))
            for y in range(115,H,60):
                pygame.draw.line(surf,(112,118,115),(0,y),(W,y))
        # Target is behind loose and stacked pallets, not painted over them.
        surf.blit(self.target_overlay,self.target.topleft)
        pygame.draw.rect(surf,(45,234,114),self.target,4)
        pygame.draw.line(surf,(90,235,146),
                         (self.target.centerx-18,self.target.centery),
                         (self.target.centerx+18,self.target.centery),2)
        pygame.draw.line(surf,(90,235,146),
                         (self.target.centerx,self.target.centery-18),
                         (self.target.centerx,self.target.centery+18),2)
        for pallet in sorted((p for p in self.pallets if p.state=='loose'),key=lambda p:p.y):
            surf.blit(self.pallet_image,self.pallet_image.get_rect(center=(round(pallet.x),round(pallet.y))))
        # Lower layers are drawn FIRST. Each higher layer is shifted up and has
        # a visible underside, so pallets never appear to float in wrong order.
        for i, pallet in enumerate(self.stack):
            x = round(self.target.centerx + pallet.dx)
            y = round(self.target.centery + pallet.dy - i*12)
            pygame.draw.rect(surf,(92,70,47),(x-43,y-40,86,90),border_radius=5)
            pygame.draw.rect(surf,(66,47,34),(x-43,y+36,86,10),border_radius=3)
            surf.blit(self.pallet_image,self.pallet_image.get_rect(center=(x,y)))
        sprite = self._sprite()
        surf.blit(sprite,sprite.get_rect(center=(round(self.truck_x),round(self.truck_y))))
        if self.carried is not None:
            x,y = self.fork_tip()
            shadow = pygame.Rect(0,0,82,16)
            shadow.center=(round(x),round(y)+27)
            pygame.draw.ellipse(surf,(62,57,52),shadow)
            surf.blit(self.carry_image,self.carry_image.get_rect(center=(round(x),round(y)-8)))
        # Dark HUD improves readability on the existing floor artwork.
        pygame.draw.rect(surf,(27,42,48),pygame.Rect(111,10,678,82),border_radius=12)
        pygame.draw.rect(surf,(96,170,137),pygame.Rect(111,10,678,82),2,border_radius=12)
        _draw_text(surf,self.f_small,f'LEVEL {self.level}',(197,35),COLORS['yellow'])
        _draw_text(surf,self.f_small,f'PALLETS {self.placed}/{self.quantity}',(384,35))
        _draw_text(surf,self.f_small,f'{self.elapsed:.1f}s',(560,35))
        _draw_text(surf,self.f_small,f'{self.level_score} PTS',(703,35),COLORS['mint'])
        if self.message_time > 0 and self.state == 'PLAYING':
            _draw_text(surf,self.f_tiny,self.message,(410,75))
        if self.state == 'RESULTS':
            shade = pygame.Surface((W,H),pygame.SRCALPHA)
            shade.fill((8,16,26,204))
            surf.blit(shade,(0,0))
            _panel(surf,pygame.Rect(172,89,456,478))
            _draw_text(surf,self.f_medium,f'LEVEL {self.level} COMPLETE',(400,126),COLORS['yellow'])
            tier_color = {'S':(243,208,102),'A':(119,232,167),'B':(149,192,255),
                          'C':(220,205,185),'D':(231,142,132)}[self.tier]
            _draw_text(surf,self.f_large,self.tier,(400,211),tier_color)
            _draw_text(surf,self.f_small,f'Pallets stacked: {self.placed}',(400,280))
            _draw_text(surf,self.f_small,f'Alignment: {round(100*self.total_alignment/self.quantity)}%',(400,315))
            _draw_text(surf,self.f_small,f'Time: {self.elapsed:.1f}s  /  Target: {self.par_time:.0f}s',(400,349))
            _draw_text(surf,self.f_small,f'Time bonus: +{self.bonus}',(400,385),COLORS['mint'])
            _draw_text(surf,self.f_medium,f'LEVEL SCORE  {self.level_score}',(400,414))
            pygame.draw.rect(surf,(58,169,122),self.NEXT,border_radius=14)
            pygame.draw.rect(surf,(179,245,205),self.NEXT,3,border_radius=14)
            _draw_text(surf,self.f_medium,'NEXT LEVEL',(400,478))
            pygame.draw.rect(surf,(49,67,73),self.AGAIN,border_radius=9)
            _draw_text(surf,self.f_tiny,'REPLAY LEVEL',(400,541),COLORS['yellow'])
        if self.home_image is not None:
            surf.blit(self.home_image,self.HOME.topleft)
        else:
            pygame.draw.rect(surf,(42,64,70),self.HOME,border_radius=12)
            _draw_text(surf,self.f_small,'HOME',self.HOME.center)
        if self.canvas is not self.screen:
            if self.scaled_canvas is None:
                self.screen.blit(self.canvas,self.scale_area.topleft)
            else:
                self.screen.fill((20,29,35))
                pygame.transform.scale(self.canvas,self.scale_area.size,self.scaled_canvas)
                self.screen.blit(self.scaled_canvas,self.scale_area.topleft)

    async def run(self):
        # A bounded frame interval avoids severe browser tab-switch jumps.
        while self.running:
            dt = min(0.05,self.clock.tick(FPS)/1000.0)
            for event in pygame.event.get():
                self.handle_event(event)
            if not self.running:
                break
            self.update(dt)
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)


async def main(screen, clock):
    """Used by GameHub: do not quit or recreate the shared display."""
    await ForkGame(screen,clock).run()
