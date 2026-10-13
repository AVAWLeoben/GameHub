# -*- coding: utf-8 -*-
"""Waste Jump — dusk-city runner for GameHub (quality update 2.0).

GameHub invokes ``await main(screen, clock)``. The game is self-contained,
uses existing wasteJump truck/obstacle art and the standard retBut home asset.
No external Python packages, GUI.Button dependency, or online services.
"""

import asyncio
import math
import os
import random
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


def _asset(name):
    """Works from GameHub's WasteGame directory and as an imported module."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, 'assets', name),
        os.path.join('assets', name),
        os.path.join('WasteGame', 'assets', name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError('Waste Jump asset not found: ' + name)


def _img(path, size=None):
    surface = pygame.image.load(_asset(path)).convert_alpha()
    if size:
        surface = pygame.transform.smoothscale(surface, tuple(map(int, size)))
    return surface


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
        self.canvas = (screen if screen.get_size() == (W, H)
                       else pygame.Surface((W, H)).convert())
        self.scale_area = None
        sw,sh = screen.get_size()
        scale = min(sw/W, sh/H)
        self.scale_area = pygame.Rect(round((sw-W*scale)/2),round((sh-H*scale)/2),
                                      round(W*scale),round(H*scale))
        self.rng = random.Random()
        self.sky = _img('wasteJump/city_dusk_sky.png')
        self.city_far = _img('wasteJump/city_dusk_far.png')
        self.city_near = _img('wasteJump/city_dusk_near.png')
        self.home = _img('retBut.png', (100,100))
        self.home_pressed = _img('retBut_clicked.png', (100,100))
        self.truck = _img('wasteJump/player.png', (TRUCK_W,TRUCK_H))
        self.rotate_cache = {0: self.truck}
        self.obstacle_images = [
            _img('wasteJump/obstacle%d.png'%(i+1),Obstacle.SIZES[i]) for i in range(6)
        ]
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
                scaled=pygame.transform.smoothscale(self.canvas,self.scale_area.size)
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


async def main(screen, clock):
    """GameHub-compatible, asynchronous entry point."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    await WasteJump(screen,clock).run()


if __name__=='__main__':
    pygame.init()
    asyncio.run(main(pygame.display.set_mode((W,H)),pygame.time.Clock()))
