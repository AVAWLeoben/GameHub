# -*- coding: utf-8 -*-
"""Waste Jump — dusk-city runner for GameHub (startup reliability 2.0.1).

GameHub invokes ``await main(screen, clock)``. The game is self-contained,
uses existing wasteJump truck/obstacle art and the standard retBut home asset.
No external Python packages, GUI.Button dependency, or online services.
"""

import asyncio
import math
import os
import random
import traceback
import pygame

W, H = 800, 600
FPS = 60
ROAD_Y = 483
TRUCK_X = 118
TRUCK_W, TRUCK_H = 114, 108
JUMP_SPEED = 755.0
GRAVITY = 1920.0

INK = (27, 35, 61)
PAPER = (255, 248, 233)
MUTED = (220, 213, 217)
AMBER = (255, 204, 112)
CORAL = (245, 117, 101)
MINT = (125, 228, 185)

# Remember the record while moving between GameHub games in one session.
SESSION_BEST = 0


def _asset_candidates(name):
    """Try both GameHub cwd and module-relative paths (Pygbag or desktop).

    Checking os.path.isfile is intentionally avoided: assets inside some web
    filesystems can be readable by pygame.image.load despite unreliable stat.
    """
    root = os.path.dirname(os.path.abspath(__file__))
    return (
        os.path.join('assets', name),
        os.path.join(root, 'assets', name),
        os.path.join('WasteGame', 'assets', name),
    )


def _img(name, size=None):
    """Load art without requiring conversion or smoothscale to succeed."""
    last_error = None
    for path in _asset_candidates(name):
        try:
            image = pygame.image.load(path)
            try:
                image = image.convert_alpha()
            except (pygame.error, AttributeError, ValueError):
                # Some browser renderers do not support format conversion yet.
                pass
            if size and image.get_size() != tuple(map(int, size)):
                # Standard scale is supported by both pygame-ce and Pygbag.
                image = pygame.transform.scale(image, tuple(map(int, size)))
            return image
        except (OSError, pygame.error, FileNotFoundError, ValueError) as exc:
            last_error = exc
    raise FileNotFoundError('Could not load '+name+': '+str(last_error))


def _optional_img(name, size=None):
    try:
        return _img(name, size)
    except Exception as exc:
        print('[WasteJump] Using built-in art for '+name+': '+str(exc))
        return None


def _skyline_fallback():
    """Original dusk-city look built once, no newly added PNGs required."""
    width = 1600
    sky = pygame.Surface((width, H))
    top = (39, 36, 79)
    bottom = (227, 122, 111)
    for y in range(H):
        t = min(1., y / 525.)
        c = tuple(round(a * (1 - t) + b * t) for a, b in zip(top, bottom))
        pygame.draw.line(sky, c, (0, y), (width, y))
    pygame.draw.circle(sky, (253, 184, 142), (1150, 265), 82)
    pygame.draw.circle(sky, (251, 200, 152), (1150, 265), 58)
    far = pygame.Surface((width, H), pygame.SRCALPHA)
    near = pygame.Surface((width, H), pygame.SRCALPHA)
    rng = random.Random(21)
    for layer, floor, shades, step in (
        (far, 463, ((65, 61, 104), (78, 66, 112)), 76),
        (near, 490, ((40, 45, 80), (45, 50, 85)), 97),
    ):
        for x in range(-10, width + step, step):
            ht = rng.randint(120, 245) if layer is far else rng.randint(100, 195)
            bw = rng.randint(step - 18, step + 15)
            color = shades[rng.randrange(len(shades))]
            pygame.draw.rect(layer, color, (x, floor - ht, bw, ht))
            for xx in range(x + 11, x + bw - 6, 18):
                for yy in range(floor - ht + 16, floor - 9, 22):
                    if rng.random() < .55:
                        pygame.draw.rect(layer, (238, 183, 131), (xx, yy, 6, 9))
    return sky, far, near


def _truck_fallback():
    result = pygame.Surface((TRUCK_W, TRUCK_H), pygame.SRCALPHA)
    pygame.draw.ellipse(result, (20, 21, 41, 100), (5, TRUCK_H - 15, TRUCK_W - 10, 12))
    pygame.draw.rect(result, (242, 153, 77), (10, 31, 75, 50), border_radius=12)
    pygame.draw.rect(result, (84, 177, 183), (70, 47, 38, 35), border_radius=9)
    pygame.draw.rect(result, (40, 88, 109), (79, 51, 22, 18), border_radius=5)
    for cx in (31, 91):
        pygame.draw.circle(result, (26, 36, 54), (cx, 82), 13)
        pygame.draw.circle(result, (189, 202, 209), (cx, 82), 6)
    return result


def _obstacle_fallback(index, size):
    w, h = size
    result = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(result, (248, 162, 76), (6, h // 3, w - 12, h * 2 // 3 - 3), border_radius=8)
    for y in range(h // 3 + 9, h - 9, 18):
        pygame.draw.line(result, (237, 236, 212), (12, y), (w - 12, y), 6)
    pygame.draw.rect(result, (67, 75, 95), (5, h // 3, w - 10, h * 2 // 3), 3, border_radius=8)
    return result


def _home_fallback():
    result = pygame.Surface((100, 100), pygame.SRCALPHA)
    pygame.draw.rect(result, (136, 83, 48), (16, 38, 68, 53), border_radius=9)
    pygame.draw.polygon(result, (202, 128, 72), ((8, 47), (50, 10), (92, 47)))
    pygame.draw.rect(result, (246, 222, 152), (43, 59, 19, 32), border_radius=3)
    return result


def font(size, bold=False):
    f = pygame.font.Font(None, size)
    f.set_bold(bold)
    return f


def text(surf, message, f, colour, centre=None, topleft=None):
    image = f.render(str(message), True, colour)
    rect = image.get_rect()
    if centre is not None:
        rect.center = centre
    else:
        rect.topleft = topleft
    surf.blit(image, rect)
    return rect


def panel(surf, rect, fill=(36, 39, 70), edge=(250, 205, 170), alpha=237, radius=22):
    """Reusable clear, strong-contrast panel with shallow offset shadow."""
    shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(shadow, (11, 18, 39, 140), shadow.get_rect(), border_radius=radius)
    surf.blit(shadow, (rect.x, rect.y + 7))
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*fill, alpha), layer.get_rect(), border_radius=radius)
    pygame.draw.rect(layer, (*edge, 240), layer.get_rect(), 3, border_radius=radius)
    surf.blit(layer, rect.topleft)


def button(surf, rect, label, f, bg=CORAL, foreground=PAPER, style='play'):
    shadow = rect.move(0, 5)
    pygame.draw.rect(surf, (30, 29, 53), shadow, border_radius=19)
    pygame.draw.rect(surf, bg, rect, border_radius=19)
    pygame.draw.rect(surf, (255, 224, 188), rect, 3, border_radius=19)
    # High contrast circle carrying a recognisable play/pause/again icon.
    cx, cy = rect.x + 39, rect.centery
    pygame.draw.circle(surf, (36, 41, 70), (cx, cy), 23)
    if style == 'again':
        pygame.draw.arc(surf, AMBER, (cx-12,cy-12,24,24), 0.35, 5.5, 4)
        pygame.draw.polygon(surf, AMBER, [(cx+11,cy-11),(cx+17,cy),(cx+5,cy-1)])
    else:
        pygame.draw.polygon(surf, AMBER, [(cx-7,cy-11),(cx+12,cy),(cx-7,cy+11)])
    text(surf, label, f, foreground, centre=(rect.centerx+25,rect.centery-1))


class Obstacle:
    # Widths and heights are matched to the original six obstacle PNGs.
    SIZES = ((68,82), (116,81), (92,91), (94,77), (63,106), (110,79))

    def __init__(self, index, image, x):
        self.kind = index
        self.image = image
        self.w, self.h = image.get_size()
        self.x = float(x)
        self.passed = False
        self.spark_phase = random.uniform(0, 6.28)

    @property
    def rect(self):
        return pygame.Rect(round(self.x), ROAD_Y+8-self.h, self.w, self.h)

    @property
    def hitbox(self):
        r = self.rect
        # Forgiving body hitbox, but collision still depends on actual height.
        return pygame.Rect(r.x + round(self.w*.20), r.y + round(self.h*.20),
                           max(15,round(self.w*.60)), max(15,round(self.h*.69)))

    def update(self, dt, speed):
        self.x -= speed * dt
        self.spark_phase += 4 * dt

    def draw(self, screen):
        r = self.rect
        if r.right < -15 or r.left > W + 15:
            return
        pygame.draw.ellipse(screen, (14, 17, 28), (r.centerx-self.w//3,ROAD_Y+1,
                            self.w*2//3,10))
        screen.blit(self.image, r)
        # Roadwork warning sparkle, subtle enough not to hide obstacles.
        if self.kind in (2, 5):
            glow = 2 + math.sin(self.spark_phase)*1.5
            pygame.draw.circle(screen, AMBER, (r.centerx, r.y+13), max(2,round(glow)))


class WasteJump:
    START_RECT = pygame.Rect(281, 365, 238, 76)
    AGAIN_RECT = pygame.Rect(250, 394, 300, 80)
    PAUSE_RECT = pygame.Rect(735, 21, 51, 51)
    HOME_RECT = pygame.Rect(10, 10, 100, 100)

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        # Avoid convert() here; WebAssembly display formats differ by browser.
        self.canvas = (screen if screen.get_size() == (W, H)
                       else pygame.Surface((W, H)))
        self.scale_area = None
        sw,sh = screen.get_size()
        scale = min(sw/W, sh/H)
        self.scale_area = pygame.Rect(round((sw-W*scale)/2),round((sh-H*scale)/2),
                                      round(W*scale),round(H*scale))
        self.rng = random.Random()
        self.sky = _optional_img('wasteJump/city_dusk_sky.png')
        self.city_far = _optional_img('wasteJump/city_dusk_far.png')
        self.city_near = _optional_img('wasteJump/city_dusk_near.png')
        if self.sky is None or self.city_far is None or self.city_near is None:
            fallback_sky, fallback_far, fallback_near = _skyline_fallback()
            self.sky = self.sky if self.sky is not None else fallback_sky
            self.city_far = self.city_far if self.city_far is not None else fallback_far
            self.city_near = self.city_near if self.city_near is not None else fallback_near
        self.home = _optional_img('retBut.png', (100,100))
        if self.home is None:
            self.home = _home_fallback()
        self.home_pressed = _optional_img('retBut_clicked.png', (100,100))
        if self.home_pressed is None:
            self.home_pressed = self.home
        self.truck = _optional_img('wasteJump/player.png', (TRUCK_W,TRUCK_H))
        if self.truck is None:
            self.truck = _truck_fallback()
        self.rotate_cache = {0: self.truck}
        self.obstacle_images = []
        for i in range(6):
            image = _optional_img('wasteJump/obstacle%d.png' % (i+1), Obstacle.SIZES[i])
            self.obstacle_images.append(image if image is not None
                                        else _obstacle_fallback(i, Obstacle.SIZES[i]))
        self.f_big = font(72, True)
        self.f_title = font(43, True)
        self.f_large = font(42, True)
        self.f_button = font(36, True)
        self.f_small = font(28, True)
        self.f_hud = font(34, True)
        self.f_hint = font(25, True)
        self.state = 'MENU'
        self.running = True
        self.since = 0.0
        self.total_distance = 0.0
        self.home_down = False
        self.dedup_at = -9999
        self.dedup_pos = (-9999,-9999)
        self.dedup_type = None
        self.reset_round()

    def reset_round(self):
        self.score = 0
        self.lives = 3
        self.speed = 248.0
        self.spawn_timer = 1.65
        self.obstacles = []
        self.jump_height = 0.0
        self.vertical_speed = 0.0
        self.airtime = 0.0
        self.prejump = 0.0
        self.invincible = 0.0
        self.feedback_timer = 0.0
        self.feedback = ''
        self.game_seconds = 0.0
        self.last_kind = None
        self.since = 0.0

    def _rounded_angle(self):
        if self.jump_height <= 0 and self.prejump <= 0:
            return 0
        if self.prejump > 0:
            return 0
        flight = 2 * JUMP_SPEED / GRAVITY
        progress = min(1, self.airtime/flight)
        # Preserve original truck's playful barrel-roll jump; one full rotation.
        a = int(round((progress*360)/10)*10)%360
        return a

    def _truck_sprite(self):
        angle=self._rounded_angle()
        if angle not in self.rotate_cache:
            self.rotate_cache[angle]=pygame.transform.rotate(self.truck, -angle)
        return self.rotate_cache[angle]

    def truck_rect(self):
        y = ROAD_Y+7-TRUCK_H-round(self.jump_height)
        if self.prejump>0:
            y+=round(9*min(1,self.prejump/.09))
        return pygame.Rect(TRUCK_X,y,TRUCK_W,TRUCK_H)

    def truck_hitbox(self):
        r=self.truck_rect()
        return pygame.Rect(r.x+25,r.y+30, r.w-43, r.h-41)

    def jump(self):
        if self.state != 'PLAYING' or self.prejump>0 or self.jump_height>0 or self.vertical_speed>0:
            return
        self.prejump=.085
        self.airtime=0.0

    def _spawn(self):
        candidates=list(range(6))
        if self.last_kind is not None and self.last_kind in candidates:
            candidates.remove(self.last_kind)
        index=self.rng.choice(candidates)
        self.last_kind=index
        self.obstacles.append(Obstacle(index,self.obstacle_images[index],W+30))
        # Long enough to land between hazards even at the fastest speed.
        self.spawn_timer=self.rng.uniform(1.75,2.20)

    def _bonk(self):
        if self.invincible>0 or self.state!='PLAYING':
            return
        self.lives-=1
        self.invincible=1.65
        self.feedback_timer=.75
        self.feedback='BONK!'
        if self.lives <= 0:
            self.state='OVER'
            self.feedback_timer=0

    def update(self, dt):
        self.since+=dt
        self.home_down=False
        if self.state != 'PLAYING':
            return
        self.game_seconds+=dt
        self.speed=min(370., 248.0 + self.score*5.0)
        self.total_distance+=dt*self.speed
        self.spawn_timer-=dt
        if self.spawn_timer<=0:
            self._spawn()

        if self.prejump>0:
            self.prejump-=dt
            if self.prejump<=0:
                self.prejump=0
                self.vertical_speed=JUMP_SPEED
                self.airtime=0
        if self.vertical_speed>0 or self.jump_height>0:
            self.airtime+=dt
            self.jump_height+=self.vertical_speed*dt
            self.vertical_speed-=GRAVITY*dt
            if self.jump_height<=0:
                self.jump_height=0
                self.vertical_speed=0
                self.airtime=0

        self.invincible=max(0,self.invincible-dt)
        self.feedback_timer=max(0,self.feedback_timer-dt)
        me=self.truck_hitbox()
        for obstacle in self.obstacles:
            obstacle.update(dt,self.speed)
            if (obstacle.hitbox.colliderect(me) and self.invincible<=0):
                self._bonk()
            if not obstacle.passed and obstacle.rect.right < me.left:
                obstacle.passed=True
                self.score+=1
                global SESSION_BEST
                SESSION_BEST=max(SESSION_BEST,self.score)
        self.obstacles=[ob for ob in self.obstacles if ob.rect.right>-35]

    def _parallax(self,surface,layer,scroll):
        w=layer.get_width()
        offset=round(scroll)%w
        surface.blit(layer,(-offset,0))
        if w-offset<W:
            surface.blit(layer,(w-offset,0))

    def draw_road(self, surf):
        pygame.draw.rect(surf,(33,34,55),(0,ROAD_Y,W,H-ROAD_Y))
        pygame.draw.rect(surf,(247,184,130),(0,ROAD_Y-9,W,9))
        pygame.draw.rect(surf,(93,73,88),(0,ROAD_Y-6,W,5))
        pygame.draw.rect(surf,(26,29,46),(0,ROAD_Y+3,W,7))
        pygame.draw.line(surf,(69,67,84),(0,ROAD_Y+17),(W,ROAD_Y+17),2)
        # dashed road markings, continuous across the screen as world scrolls
        step=156
        off=round(self.total_distance)%step
        for x in range(-off-step,W+step,step):
            pygame.draw.rect(surf,(255,202,128),(x+10,545,78,7),border_radius=3)
        # subtle pavement highlights
        pygame.draw.line(surf,(50,47,69),(0,H-2),(W,H-2),3)

    def _backdrop(self,surf):
        surf.blit(self.sky,(0,0))
        self._parallax(surf,self.city_far,self.total_distance*.14)
        self._parallax(surf,self.city_near,self.total_distance*.27)
        self.draw_road(surf)

    def _draw_truck(self, surf,menu=False):
        rect=self.truck_rect()
        if menu:
            rect=pygame.Rect(88, ROAD_Y+7-TRUCK_H,TRUCK_W,TRUCK_H)
        # Contact shadow shrinks when airborne.
        lift=max(0.,float(self.jump_height))
        shw=max(29,round(76-lift*.14))
        pygame.draw.ellipse(surf,(20,23,40),(rect.centerx-shw//2,ROAD_Y+1,shw,12))
        if (self.invincible>0 and not menu and int(self.invincible*10)%2==0):
            return
        img=self._truck_sprite() if not menu else self.truck
        dest=img.get_rect(center=rect.center)
        surf.blit(img,dest)
        if not menu and self.feedback_timer>0:
            # Simple visual collision feedback.
            for i in range(5):
                angle=(i*72+self.since*150)*math.pi/180
                cx=rect.centerx+math.cos(angle)*65
                cy=rect.centery+math.sin(angle)*43
                pygame.draw.circle(surf,AMBER,(round(cx),round(cy)),3)

    def _draw_hud(self,surf):
        panel(surf,pygame.Rect(596,15,126,71),alpha=215,radius=16,edge=(239,168,139))
        text(surf,'SCORE',self.f_hint,AMBER,centre=(660,37))
        text(surf,f'{self.score:02d}',self.f_hud,PAPER,centre=(660,65))
        # small distinct pause area
        pygame.draw.rect(surf,(37,44,73),self.PAUSE_RECT,border_radius=14)
        pygame.draw.rect(surf,(250,215,170),self.PAUSE_RECT,2,border_radius=14)
        pygame.draw.rect(surf,PAPER,(752,36,6,22),border_radius=2)
        pygame.draw.rect(surf,PAPER,(765,36,6,22),border_radius=2)
        for i in range(3):
            cx=314+i*42
            colour=CORAL if i<self.lives else (87,85,107)
            pygame.draw.circle(surf,colour,(cx-6,48),9)
            pygame.draw.circle(surf,colour,(cx+6,48),9)
            pygame.draw.polygon(surf,colour,[(cx-15,49),(cx+15,49),(cx,69)])
        if self.feedback_timer>0:
            text(surf,self.feedback,self.f_large,AMBER,centre=(240,323))

    def _draw_menu(self,surf):
        self._draw_truck(surf,menu=True)
        panel(surf,pygame.Rect(228,131,344,321),fill=(36,43,74),alpha=241)
        text(surf,'WASTE JUMP',self.f_title,AMBER,centre=(400,190))
        pygame.draw.line(surf,(237,153,123),(279,218),(521,218),2)
        text(surf,'TAP TO JUMP',self.f_large,PAPER,centre=(400,271))
        text(surf,'Hop over roadworks!',self.f_small,MUTED,centre=(400,307))
        button(surf,self.START_RECT,'PLAY',self.f_button, bg=CORAL)
        text(surf,'ONE TAP  •  ONE JUMP',self.f_hint,(251,228,197),centre=(400,341))

    def _draw_pause(self,surf):
        panel(surf,pygame.Rect(241,165,318,267),alpha=246)
        text(surf,'PAUSED',self.f_big,AMBER,centre=(400,231))
        button(surf,pygame.Rect(284,319,231,73),'GO!',self.f_button,bg=(75,167,141))

    def _draw_over(self,surf):
        panel(surf,pygame.Rect(209,135,382,354),alpha=250)
        text(surf,'NICE TRY!',self.f_big,AMBER,centre=(400,199))
        text(surf,'SCORE',self.f_hint,MUTED,centre=(306,269))
        text(surf,str(self.score),self.f_large,PAPER,centre=(306,304))
        text(surf,'BEST',self.f_hint,MUTED,centre=(495,269))
        text(surf,str(SESSION_BEST),self.f_large,PAPER,centre=(495,304))
        button(surf,self.AGAIN_RECT,'AGAIN!',self.f_button,bg=CORAL,style='again')
        text(surf,'YOU CAN DO IT!',self.f_hint,MUTED,centre=(400,357))

    def draw(self):
        surf=self.canvas
        self._backdrop(surf)
        if self.state=='PLAYING':
            for obstacle in self.obstacles:
                obstacle.draw(surf)
            self._draw_truck(surf)
            self._draw_hud(surf)
        elif self.state=='PAUSED':
            for obstacle in self.obstacles:
                obstacle.draw(surf)
            self._draw_truck(surf)
            self._draw_hud(surf)
            self._draw_pause(surf)
        elif self.state=='OVER':
            for obstacle in self.obstacles:
                obstacle.draw(surf)
            self._draw_truck(surf)
            self._draw_over(surf)
        else:
            self._draw_menu(surf)
        # Standard GameHub Home button: original sprite, same 100px footprint.
        surf.blit(self.home_pressed if self.home_down else self.home,(10,10))
        if self.canvas is not self.screen:
            if self.scale_area.size==(W,H):
                self.screen.blit(self.canvas,self.scale_area.topleft)
            else:
                self.screen.fill((21,27,52))
                scaled=pygame.transform.scale(self.canvas,self.scale_area.size)
                self.screen.blit(scaled,self.scale_area.topleft)

    def to_world(self, pos, touch=False):
        if touch:
            sx=pos[0]*self.screen.get_width()
            sy=pos[1]*self.screen.get_height()
        else:
            sx,sy=pos
        if not self.scale_area.collidepoint(int(sx),int(sy)):
            return (-1000,-1000)
        return (int((sx-self.scale_area.x)*W/max(self.scale_area.width,1)),
                int((sy-self.scale_area.y)*H/max(self.scale_area.height,1)))

    def press(self, pos, source):
        tick=pygame.time.get_ticks()
        # Some iPad browsers emit BOTH touch and synthesized mouse events.
        # De-duplicate those while still allowing consecutive taps.
        if (self.dedup_type is not None and source!=self.dedup_type and
            tick-self.dedup_at<150 and
            abs(pos[0]-self.dedup_pos[0])<17 and abs(pos[1]-self.dedup_pos[1])<17):
            return
        self.dedup_type=source
        self.dedup_at=tick
        self.dedup_pos=pos
        if self.HOME_RECT.collidepoint(pos):
            self.running=False
            return
        if self.state=='MENU':
            if self.START_RECT.collidepoint(pos) or pygame.Rect(230,220,340,235).collidepoint(pos):
                self.reset_round()
                self.state='PLAYING'
            return
        if self.state=='OVER':
            if self.AGAIN_RECT.collidepoint(pos):
                self.reset_round()
                self.state='PLAYING'
            return
        if self.state=='PAUSED':
            if pygame.Rect(260,310,280,99).collidepoint(pos) or self.PAUSE_RECT.collidepoint(pos):
                self.state='PLAYING'
            return
        if self.state=='PLAYING':
            if self.PAUSE_RECT.collidepoint(pos):
                self.state='PAUSED'
            else:
                self.jump()

    async def run(self):
        try:
            while self.running:
                dt=min(.045,self.clock.tick(FPS)/1000.)
                for event in pygame.event.get():
                    if event.type==pygame.QUIT:
                        self.running=False
                    elif event.type==pygame.MOUSEBUTTONDOWN and getattr(event,'button',1)==1:
                        self.press(self.to_world(event.pos),'mouse')
                    elif event.type==pygame.FINGERDOWN:
                        self.press(self.to_world((event.x,event.y),touch=True),'touch')
                    elif event.type==pygame.KEYDOWN:
                        if event.key==pygame.K_ESCAPE:
                            self.running=False
                        elif event.key in (pygame.K_SPACE,pygame.K_UP,pygame.K_w):
                            if self.state in ('MENU','OVER'):
                                self.reset_round()
                                self.state='PLAYING'
                            elif self.state=='PLAYING':
                                self.jump()
                            elif self.state=='PAUSED':
                                self.state='PLAYING'
                        elif event.key==pygame.K_p and self.state in ('PLAYING','PAUSED'):
                            self.state='PAUSED' if self.state=='PLAYING' else 'PLAYING'
                self.update(dt)
                self.draw()
                pygame.display.flip()
                await asyncio.sleep(0)
        finally:
            # Leave the shared display and mixer alive for GameHub.
            pass


async def _startup_error_screen(screen, clock, exc):
    """Keep GameHub responsive and show the real cause rather than freeze."""
    print('[WasteJump] Fatal startup/runtime failure:')
    traceback.print_exc()
    f_title = pygame.font.Font(None, 48)
    f_small = pygame.font.Font(None, 28)
    reason = type(exc).__name__ + ': ' + str(exc)
    for _ in range(60 * 20):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or event.type in (pygame.MOUSEBUTTONDOWN,
                                                            pygame.FINGERDOWN):
                return
            if event.type == pygame.KEYDOWN:
                return
        screen.fill((34, 37, 61))
        title = f_title.render('Waste Jump could not start', True, (255, 215, 151))
        screen.blit(title, title.get_rect(center=(screen.get_width()//2, 190)))
        # Show a clipped diagnostic rather than a silent frozen GameHub menu.
        line = f_small.render(reason[:65], True, (255, 239, 226))
        screen.blit(line, line.get_rect(center=(screen.get_width()//2, 275)))
        hint = f_small.render('Tap anywhere to return to GameHub', True, (181, 223, 221))
        screen.blit(hint, hint.get_rect(center=(screen.get_width()//2, 365)))
        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)


async def main(screen, clock):
    """GameHub-compatible entry point: missing files never hang the main menu."""
    try:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        await WasteJump(screen, clock).run()
    except Exception as exc:
        await _startup_error_screen(screen, clock, exc)


if __name__ == '__main__':
    pygame.init()
    asyncio.run(main(pygame.display.set_mode((W,H)),pygame.time.Clock()))
