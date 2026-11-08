"""Tank Duel: local two-player pygame/pygbag artillery. await run(screen)."""
import asyncio
import json
import math
import random
from pathlib import Path
import pygame

W, H = 1280, 800
BG = (18, 29, 45)
PANEL = (29, 44, 62)
WHITE = (234, 241, 244)
MUTED = (159, 181, 193)
GOLD = (255, 204, 99)
COLORS = [(79, 195, 235), (241, 112, 97), (148, 206, 113), (187, 146, 234), (244, 191, 75), (223, 224, 220)]
# price, health, turn movement, damage multiplier
BODIES = {'scout': (0, 100, 150, 1.0), 'heavy': (1200, 155, 90, 1.0), 'artillery': (900, 110, 110, 1.15)}
# price, damage per projectile, blast radius, count, gravity multiplier
WEAPONS = {'cannon': (0, 36, 56, 1, 1.0), 'twin_cannon': (1000, 24, 48, 2, 1.0),
           'mortar': (800, 49, 85, 1, 1.15), 'rocket_pod': (1600, 22, 62, 3, .8),
           'plasma_gun': (2000, 62, 43, 1, .65)}
ASSETS = Path(__file__).resolve().parent / 'tank_game_assets'

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def title(s):
    return s.replace('_', ' ').title()

class Player:
    def __init__(self, index):
        self.index = index
        self.color = index
        self.body = 'scout'
        self.weapon = 'cannon'
        self.armor = self.engine = 0
        self.owned = {'scout', 'cannon'}
        self.money = 1000
        self.wins = 0
        self.angle, self.power = 55., 10.
        self.x = 210 if index == 0 else 1070
        self.hp = self.max_hp
        self.fuel = float(self.movement)
        self.wheel = 0

    @property
    def max_hp(self):
        return BODIES[self.body][1] + self.armor * 25

    @property
    def movement(self):
        return BODIES[self.body][2] + self.engine * 35

class Art:
    def __init__(self):
        self.rig = json.loads((ASSETS / 'rig/tank_rig.json').read_text())
        self.cache = {}

    def sprite(self, path, size, color=None):
        key = (path, tuple(size), color)
        if key not in self.cache:
            s = pygame.image.load(str(ASSETS / path)).convert_alpha()
            s = pygame.transform.smoothscale(s, [max(1, round(v)) for v in size])
            if color is not None:
                # True luminance desaturation before tinting; preserve alpha and shading.
                for y in range(s.get_height()):
                    for x in range(s.get_width()):
                        r, g, b, a = s.get_at((x, y))
                        lum = min(255, int((.2126*r + .7152*g + .0722*b) * 1.5))
                        s.set_at((x, y), (*(int(lum*c/255) for c in color), a))
            self.cache[key] = s
        return self.cache[key]

    def pose(self, p, ground, scale=.8):
        rig = self.rig['tanks'][p.body]
        positions = {}
        for n in rig['nodes']:
            parent = positions.get(n['parent'], pygame.Vector2())
            positions[n['id']] = parent + pygame.Vector2(n['position'])
        root = pygame.Vector2(p.x, ground - rig['groundContacts'][0][1] * scale)
        return rig, positions, root

    def mount(self, p, ground, scale=.8):
        _, pos, root = self.pose(p, ground, scale)
        v = pos['weapon_slot'] * scale
        v.x *= 1 if p.index == 0 else -1
        return root + v

    def tank(self, target, p, ground, scale=.8):
        rig, pos, root = self.pose(p, ground, scale)
        facing = 1 if p.index == 0 else -1
        for ident in rig['drawOrder']:
            if ident == 'weapon_slot/weapon':
                n = self.rig['weapons'][p.weapon]
                origin = pos['weapon_slot']
                angle = p.angle
                color = None
            else:
                n = next(n for n in rig['nodes'] if n['id'] == ident)
                origin = pos[ident]
                angle = p.wheel if ident.startswith('wheel') else 0
                color = COLORS[p.color] if ident in ('hull', 'turret') else None
            s = self.sprite(n['sprite'].format(color='green'), [v*scale for v in n['size']], color)
            offset = (pygame.Vector2(n['size'])/2 - pygame.Vector2(n['pivot'])) * scale
            offset = offset.rotate(-angle)
            s = pygame.transform.rotate(s, angle)
            v = origin*scale + offset
            v.x *= facing
            if facing == -1:
                s = pygame.transform.flip(s, True, False)
            target.blit(s, s.get_rect(center=root+v))

class Game:
    def __init__(self):
        self.canvas = pygame.Surface((W,H))
        self.art = Art()
        self.fonts = {n: pygame.font.Font(None,n) for n in (20,24,28,32,40,56,76)}
        self.players = [Player(0), Player(1)]
        self.state = 'menu'
        self.mode = 'free'
        self.buttons = []
        self.holds = {}
        self.running = True
        self.round = 0
        self.active = 0
        self.shots = []
        self.fx = []
        self.notice = ''
        self.paused = False
        self.grounds = [575,575]
        self.obstacle = pygame.Rect(580,340,120,300)
        self.wind = 0
        self.accum = 0
        self.settle = 0
        self.build_player = 0
        self.charge_owner = None
        self.charge_time = 0.
        rng = random.Random(71)
        self.leaves = [[rng.uniform(0,W), rng.uniform(165,470), rng.uniform(0,6.28), rng.uniform(.7,1.3)] for _ in range(14)]

    def text(self, text, x, y, size=28, color=WHITE, center=False):
        s = self.fonts[size].render(str(text), True, color)
        self.canvas.blit(s, s.get_rect(center=(x,y)) if center else (x,y))

    def box(self, rect, color=PANEL, radius=16):
        pygame.draw.rect(self.canvas,color,rect,border_radius=radius)

    def button(self, rect, label, action, selected=False, enabled=True):
        r = pygame.Rect(rect)
        self.box(r, (56,99,112) if selected else PANEL)
        pygame.draw.rect(self.canvas, GOLD if selected else (65,86,102), r, 2, border_radius=14)
        self.text(label,r.centerx,r.centery,24,WHITE if enabled else (105,121,133),True)
        self.buttons.append((r, action, enabled))

    def icon(self, kind, center, color=WHITE, size=30):
        x,y = center
        if kind in ('left','right','up','down','play'):
            points = [(-size/2,-size),(size/2,0),(-size/2,size)]
            angle = {'left':180,'right':0,'up':-90,'down':90,'play':0}[kind]
            pts = [pygame.Vector2(v).rotate(angle)+pygame.Vector2(x,y) for v in points]
            pygame.draw.polygon(self.canvas,color,pts)
        elif kind=='fire':
            pygame.draw.circle(self.canvas,color,(x,y),size,4)
            pygame.draw.circle(self.canvas,color,(x,y),size//3)
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                pygame.draw.line(self.canvas,color,(x+dx*(size-7),y+dy*(size-7)),(x+dx*(size+9),y+dy*(size+9)),5)
        elif kind=='armor':
            pygame.draw.polygon(self.canvas,color,[(x-size,y-size),(x+size,y-size),(x+size*.8,y+size*.4),(x,y+size),(x-size*.8,y+size*.4)],4)
        elif kind=='engine':
            pygame.draw.circle(self.canvas,color,(x,y),size,5)
            for angle in range(0,360,60):
                v=pygame.Vector2(size-5,0).rotate(angle)
                pygame.draw.line(self.canvas,color,(x,y),(x+v.x,y+v.y),4)
        elif kind=='pause':
            for dx in (-12,8): pygame.draw.rect(self.canvas,color,(x+dx,y-size,7,size*2),border_radius=3)
        elif kind=='fuel':
            pygame.draw.rect(self.canvas,color,(x-size*.6,y-size*.65,size*1.2,size*1.5),3,border_radius=4)
            pygame.draw.rect(self.canvas,color,(x-size*.3,y-size,size*.6,size*.35),3)
            pygame.draw.line(self.canvas,color,(x-size*.35,y),(x+size*.35,y+size*.5),3)
        elif kind=='coin':
            pygame.draw.circle(self.canvas,GOLD,(x,y),size)
            pygame.draw.circle(self.canvas,BG,(x,y),size-6,3)
        elif kind=='check':
            pygame.draw.lines(self.canvas,color,False,[(x-size,y),(x-size/4,y+size*.7),(x+size,y-size)],5)

    def cancel_input(self):
        self.holds.clear()
        self.charge_owner = None
        self.charge_time = 0.

    def charge(self, ident):
        if self.state=='battle' and not self.paused and self.charge_owner is None:
            self.charge_owner = ident
            self.charge_time = 0.
            self.players[self.active].power = 10.

    def release(self, ident):
        self.holds.pop(ident,None)
        if ident == self.charge_owner:
            self.charge_owner = None
            if self.state=='battle' and not self.paused:
                self.fire()

    def limits(self, p):
        rig = self.art.rig['tanks'][p.body]
        slot = next(n for n in rig['nodes'] if n['id']=='weapon_slot')['joint']['rotation']
        amin,amax = self.art.rig['weapons'][p.weapon]['aimRange']
        return max(5,-min(slot['max'],amax)), min(-slot['min'],-amin)

    def new_campaign(self, mode):
        self.mode = mode
        self.players = [Player(0),Player(1)]
        self.round = 0
        self.build_player = 0
        self.state = 'build'
        self.notice = ''

    def buy(self, kind, item):
        p = self.players[self.build_player]
        if kind=='fuel':
            if self.mode!='money' or self.state!='build': return
            missing = max(0., p.movement-p.fuel)
            amount = min(missing, p.money/2.)
            if amount <= 0:
                self.notice = 'Full!' if missing < .01 else 'Need coins'
                return
            p.money -= math.ceil(amount*2)
            p.fuel = min(p.movement, p.fuel+amount)
            self.notice = ''
            return
        if kind in ('body','weapon'):
            price = (BODIES if kind=='body' else WEAPONS)[item][0]
            if self.mode=='money' and item not in p.owned:
                if p.money < price:
                    self.notice = 'Save up for this part.'
                    return
                p.money -= price
                p.owned.add(item)
            setattr(p,kind,item)
        else:
            level = getattr(p,kind)
            if level >= 3:
                if self.mode=='free': setattr(p,kind,0)
                return
            price = 500 + level*350
            if self.mode=='money':
                if p.money < price:
                    self.notice = 'Not enough money yet.'
                    return
                p.money -= price
            setattr(p,kind,level+1)
        p.fuel = min(p.fuel, p.movement)
        p.angle = clamp(p.angle,*self.limits(p))
        self.notice = ''

    def start_round(self):
        self.round += 1
        left = random.choice([510,550,590])
        self.grounds = [left, clamp(left+random.choice([-80,0,80]),490,610)]
        self.obstacle = pygame.Rect(575,random.choice([325,365,405]),130,400)
        self.tower = random.choice([True,False])
        self.shots, self.fx = [], []
        for p in self.players:
            p.x = 210 if p.index==0 else 1070
            p.hp = p.max_hp
            p.angle = clamp(p.angle,*self.limits(p))
        self.active = (self.round-1)%2
        self.state = 'battle'
        self.begin_turn()

    def begin_turn(self):
        if self.mode=='free':
            self.players[self.active].fuel = self.players[self.active].movement
        self.wind = random.randint(-35,35)
        self.state = 'handoff'
        self.cancel_input()

    def fire(self):
        if self.state != 'battle' or self.shots:
            return
        p = self.players[self.active]
        spec = WEAPONS[p.weapon]
        w = self.art.rig['weapons'][p.weapon]
        origin = self.art.mount(p,self.grounds[p.index])
        direction = 1 if p.index==0 else -1
        for i in range(spec[3]):
            angle = p.angle + (i-(spec[3]-1)/2)*2
            rad = math.radians(angle)
            vec = pygame.Vector2(direction*math.cos(rad), -math.sin(rad))
            muzzle = origin + vec*((w['muzzle'][0]-w['pivot'][0])*.8)
            speed = 310 + p.power*5.1
            self.shots.append({'pos':muzzle,'vel':vec*speed,'age':0.,'trail':[],
                               'owner':p.index,'weapon':p.weapon,'damage':spec[1]*BODIES[p.body][3]})
        self.state = 'flight'
        self.cancel_input()
        self.accum = self.settle = 0

    def ground_at(self,x):
        if self.obstacle.left <= x <= self.obstacle.right:
            if self.tower:
                return self.obstacle.top
            # Stepped mesa: no sloped ground.
            d = abs(x-640)
            return self.obstacle.top + (45 if d>40 else 0)
        return self.grounds[0 if x<640 else 1]

    def tank_rect(self,p):
        width = self.art.rig['tanks'][p.body]['nodes'][0]['size'][0]*.8
        return pygame.Rect(p.x-width/2,self.grounds[p.index]-72,width,72)

    def explode(self, shot):
        x,y = shot['pos']
        radius = WEAPONS[shot['weapon']][2]
        self.fx.append([x,y,0.,radius])
        for p in self.players:
            r = self.tank_rect(p)
            nearest = pygame.Vector2(clamp(x,r.left,r.right),clamp(y,r.top,r.bottom))
            dist = nearest.distance_to((x,y))
            # Central obstacle blocks splash between the two fields.
            blocked = (x<575 and p.x>705) or (x>705 and p.x<575)
            if dist<radius and not blocked:
                damage = round(shot['damage']*(1-.65*dist/radius))
                p.hp = max(0,p.hp-damage)

    def physics(self,dt):
        for s in self.shots[:]:
            s['age'] += dt
            s['vel'].x += self.wind*dt
            s['vel'].y += 400*WEAPONS[s['weapon']][4]*dt
            s['pos'] += s['vel']*dt
            x,y = s['pos']
            hit = any(self.tank_rect(p).collidepoint(x,y) for p in self.players if p.index!=s['owner'] or s['age']>.25)
            if (0<=x<=W and y>=self.ground_at(x)) or hit:
                self.explode(s)
                self.shots.remove(s)
            elif x < -200 or x > W+200 or y > H+100 or s['age']>12:
                self.shots.remove(s)
            else:
                s['trail'].append((int(x),int(y)))
                s['trail'] = s['trail'][-65:]

    def finish_round(self):
        alive = [p for p in self.players if p.hp>0]
        self.winner = alive[0].index if len(alive)==1 else None
        if self.winner is not None:
            self.players[self.winner].wins += 1
        if self.mode=='money':
            for p in self.players:
                p.money += 1200 if p.index==self.winner else 700
        self.state = 'result'
        self.cancel_input()

    def update(self,dt):
        if self.paused:
            return
        if self.state in ('battle','flight','handoff','result'):
            for leaf in self.leaves:
                leaf[2] += dt*2
                leaf[0] = (leaf[0] + self.wind*2.8*leaf[3]*dt) % W
                leaf[1] += (8 + math.sin(leaf[2])*5)*dt
                if leaf[1] > min(620,self.ground_at(leaf[0])-10):
                    leaf[1] = 155
        for fx in self.fx: fx[2] += dt
        self.fx = [f for f in self.fx if f[2]<.6]
        if self.state=='battle':
            p = self.players[self.active]
            actions = set(self.holds.values())
            direction = int('right' in actions)-int('left' in actions)
            distance = min(p.fuel,dt*100)*direction
            old = p.x
            p.x = clamp(p.x+distance,90 if p.index==0 else 805,475 if p.index==0 else 1190)
            p.fuel = max(0.,p.fuel-abs(p.x-old))
            p.wheel -= (p.x-old)*4
            p.angle = clamp(p.angle+dt*32*(int('up' in actions)-int('down' in actions)),*self.limits(p))
            if self.charge_owner is not None:
                self.charge_time += dt
                p.power = min(100., 10. + 90.*self.charge_time/2.)
        elif self.state=='flight':
            self.accum += min(dt,.05)
            while self.accum >= 1/240:
                self.physics(1/240)
                self.accum -= 1/240
            if not self.shots:
                self.settle += dt
                if self.settle>.7:
                    if any(p.hp<=0 for p in self.players):
                        self.finish_round()
                    else:
                        self.active = 1-self.active
                        self.begin_turn()

    def action(self,a):
        if a=='pause': self.paused=True; self.cancel_input()
        elif a=='resume': self.paused=False
        elif a=='exit': self.running=False
        elif a=='menu': self.paused=False; self.state='menu'; self.cancel_input()
        elif a.startswith('mode:'): self.new_campaign(a.split(':')[1])
        elif a.startswith('buy:'):
            _,kind,item = a.split(':'); self.buy(kind,item)
        elif a.startswith('color:'): self.players[self.build_player].color=int(a.split(':')[1])
        elif a=='ready':
            if self.build_player==0: self.build_player=1; self.notice=''
            else: self.start_round()
        elif a=='begin': self.state='battle'
        elif a=='fire': pass  # Fire is handled by press/release ownership.
        elif a=='next': self.state='build'; self.build_player=0; self.notice=''

    def press(self,ident,pos):
        for rect,action,enabled in reversed(self.buttons):
            if rect.collidepoint(pos) and enabled:
                if action=='fire':
                    self.charge(ident)
                elif action in ('left','right','up','down'):
                    if self.state=='battle' and not self.paused: self.holds[ident]=action
                else: self.action(action)
                break

    def draw_menu(self):
        self.text('GAMEHUB / LOCAL TWO PLAYER',640,110,24,MUTED,True)
        self.text('TANK DUEL',640,190,76,WHITE,True)
        self.text('Build your tank. Read the wind. Clear the ridge.',640,255,32,MUTED,True)
        for i,p in enumerate(self.players):
            old=p.x; p.x=360+i*560
            self.art.tank(self.canvas,p,425,1.3); p.x=old
        self.button((240,475,380,88),'Build & play','mode:free')
        self.button((660,475,380,88),'Win coins','mode:money')
        self.icon('engine',(430,607),GOLD,28)
        self.icon('coin',(850,607),GOLD,28)
        self.text('Shared iPad  |  Landscape  |  One shot per turn',640,675,28,MUTED,True)
        self.button((530,716,220,56),'Home','exit')

    def draw_build(self):
        p = self.players[self.build_player]
        self.text(f'PLAYER {p.index+1}',44,25,56,COLORS[p.color])
        self.text('Build your tank',44,80,28)
        if self.mode=='money':
            self.icon('coin',(1110,55),size=23)
            self.text(p.money,1150,40,40,GOLD)
        else: self.text('FREE',1130,45,32,GOLD)
        # Chassis cards use the actual assembled tanks instead of text-only choices.
        for i,(name,spec) in enumerate(BODIES.items()):
            x=36+i*202
            self.button((x,140,190,140),'','buy:body:'+name,p.body==name)
            demo=Player(0); demo.body=name; demo.color=p.color; demo.x=x+95; demo.angle=25
            self.art.tank(self.canvas,demo,230,.7)
            self.text(title(name),x+95,254,24,WHITE,True)
            if self.mode=='money':
                self.text('OK' if name in p.owned else str(spec[0]),x+95,158,20,GOLD,True)
        for i,(name,spec) in enumerate(WEAPONS.items()):
            x=36+(i%3)*202; y=298+(i//3)*118
            self.button((x,y,190,108),'','buy:weapon:'+name,p.weapon==name)
            w=self.art.rig['weapons'][name]
            pic=self.art.sprite(w['sprite'],[v*.95 for v in w['size']])
            self.canvas.blit(pic,pic.get_rect(center=(x+95,y+38)))
            self.text(title(name),x+95,y+76,24,WHITE,True)
            if self.mode=='money': self.text('OK' if name in p.owned else str(spec[0]),x+162,y+13,20,GOLD,True)
        for i,c in enumerate(COLORS):
            x=36+i*101
            self.button((x,549,88,80),'','color:'+str(i),p.color==i)
            pygame.draw.circle(self.canvas,c,(x+44,589),26)
            if p.color==i: self.icon('check',(x+44,589),BG,15)
        self.box((680,140,564,300))
        old=p.x; p.x=960
        self.art.tank(self.canvas,p,333,1.5); p.x=old
        # Heart-like health pips and wheel pips show the tradeoff without reading stats.
        self.icon('armor',(730,394),COLORS[p.color],18)
        for i in range(round(p.max_hp/25)):
            pygame.draw.circle(self.canvas,COLORS[p.color],(770+i*23,394),8)
        for i,kind in enumerate(('armor','engine')):
            y=447+i*83; level=getattr(p,kind)
            self.button((680,y,564,76),'','buy:'+kind+':upgrade')
            self.icon(kind,(722,y+41),GOLD,23)
            self.text('Armor' if kind=='armor' else 'Move',768,y+12,28)
            for j in range(3):
                pygame.draw.circle(self.canvas,GOLD if j<level else (70,87,103),(790+j*42,y+57),12)
            self.text('+' if level<3 or self.mode=='free' else 'OK',1198,y+40,40,GOLD,True)
            if self.mode=='money' and level<3: self.text(str(500+level*350),1060,y+30,28,GOLD)
        if self.mode=='money':
            cost = math.ceil(max(0.,p.movement-p.fuel)*2)
            self.button((680,615,564,72),'','buy:fuel:refill',enabled=cost>0 and p.money>0)
            self.icon('fuel',(721,650),GOLD,22)
            self.text('Fuel',767,625,28)
            self.box((768,656,232,12),(60,78,90),5)
            if p.fuel>0: self.box((768,656,max(1,round(232*p.fuel/p.movement)),12),(113,210,140),5)
            self.text('Full' if cost==0 else str(min(cost,p.money))+' coins',1040,638,28,GOLD)
            self.text('+',1205,650,32,GOLD,True)
        self.text(self.notice,40,654,28,GOLD)
        self.button((36,700,190,76),'Home','menu')
        self.button((680,694,564,88),'Ready','ready',True)
        self.icon('check',(1155,738),GOLD,23)

    def draw_field(self):
        self.canvas.fill((107,155,176))
        pygame.draw.circle(self.canvas,(245,221,167),(1030,225),46)
        for x,y in [(140,205),(890,310),(370,265)]:
            pygame.draw.rect(self.canvas,(184,207,211),(x,y,110,13),border_radius=6)
        for i,g in enumerate(self.grounds):
            pygame.draw.rect(self.canvas,(61,81,78),(i*640,g,640,H-g))
            pygame.draw.rect(self.canvas,(143,159,105),(i*640,g,640,9))
            for x in range(i*640+20,(i+1)*640,70):
                pygame.draw.rect(self.canvas,(81,100,88),(x,g+30,28,5))
        if self.tower:
            pygame.draw.rect(self.canvas,(66,80,91),self.obstacle)
            for y in range(self.obstacle.top+14,650,32):
                pygame.draw.line(self.canvas,(92,106,113),(575,y),(705,y),2)
            for x in range(575,705,26): pygame.draw.rect(self.canvas,(66,80,91),(x,self.obstacle.top-12,16,12))
        else:
            pygame.draw.rect(self.canvas,(99,110,100),(575,self.obstacle.top+45,130,450))
            pygame.draw.rect(self.canvas,(123,130,111),(600,self.obstacle.top,80,450))
        for x,y,phase,scale in self.leaves:
            if y >= self.ground_at(x): continue
            angle = math.sin(phase)*35 + (20 if self.wind>=0 else -20)
            center = pygame.Vector2(x,y)
            pts = [center+pygame.Vector2(v).rotate(angle)*scale for v in [(-7,0),(-2,-4),(7,0),(2,4)]]
            pygame.draw.polygon(self.canvas,(184,182,93),pts)
            pygame.draw.line(self.canvas,(105,126,73),pts[0],pts[2],1)
        for p in self.players: self.art.tank(self.canvas,p,self.grounds[p.index])
        if self.state in ('battle','handoff'):
            p=self.players[self.active]
            self.icon('down',(round(p.x),self.grounds[p.index]-124),GOLD,17)
        if self.state=='battle':
            p=self.players[self.active]
            half=self.art.rig['tanks'][p.body]['nodes'][0]['size'][0]*.4
            for direction,offset in [('left',-1),('right',1)]:
                cx=round(clamp(p.x+offset*(half+32),30,W-30))
                cy=self.grounds[p.index]-26
                rect=pygame.Rect(cx-28,cy-32,56,64)
                self.buttons.append((rect,direction,p.fuel>0))
                color=(217,228,213) if p.fuel>0 else (122,140,132)
                # Quiet outline chevrons with generous invisible touch areas.
                sign=-1 if direction=='left' else 1
                pygame.draw.lines(self.canvas,color,False,[(cx-sign*6,cy-12),(cx+sign*6,cy),(cx-sign*6,cy+12)],3)
        for s in self.shots:
            if len(s['trail'])>1: pygame.draw.lines(self.canvas,(242,223,164),False,s['trail'],2)
            spec = self.art.rig['projectiles'][self.art.rig['weapons'][s['weapon']]['projectile']]
            pic = self.art.sprite(spec['sprite'],[v*.55 for v in spec['size']])
            pic = pygame.transform.rotate(pic,-math.degrees(math.atan2(s['vel'].y,s['vel'].x)))
            self.canvas.blit(pic,pic.get_rect(center=s['pos']))
            if s['pos'].y<142:
                self.text('^',clamp(s['pos'].x,30,1250),155,32,GOLD,True)
        for x,y,t,r in self.fx:
            pic=self.art.sprite(f'png/fx/explosion_{min(7,int(t*14))}.png',(r*2,r*2))
            self.canvas.blit(pic,pic.get_rect(center=(x,y)))
        self.box((0,0,W,142),BG,0)
        for i,p in enumerate(self.players):
            x=28 if i==0 else 902
            self.text(f'P{i+1} / {title(p.body)}',x,18,28,COLORS[p.color])
            self.text(f'{p.wins} wins',x+240,20,24,MUTED)
            self.box((x,56,350,24),(55,66,78),8)
            if p.hp>0: self.box((x,56,max(1,int(350*p.hp/p.max_hp)),24),COLORS[p.color],8)
            self.text(f'{p.hp}/{p.max_hp} HP   |   {title(p.weapon)}',x,92,24)
        arrow = '<' if self.wind<0 else '>' if self.wind>0 else '-'
        self.text(f'ROUND {self.round}',640,25,24,MUTED,True)
        if self.wind:
            self.icon('left' if self.wind<0 else 'right',(575,60),GOLD,19)
        for i in range(5):
            pygame.draw.circle(self.canvas,GOLD if abs(self.wind)>i*7 else (60,78,90),(620+i*22,60),7)
        self.text(f'PLAYER {self.active+1}'+(' / SHOT IN FLIGHT' if self.state=='flight' else ' / YOUR TURN'),640,105,24,WHITE,True)
        self.box((0,650,1280,150),BG,0)
        if self.state in ('battle','flight'):
            p=self.players[self.active]
            enabled=self.state=='battle'
            self.text('Move',154,672,24,MUTED,True)
            self.text('Aim',420,672,24,MUTED,True)
            for x,a in [(24,'left'),(156,'right'),(290,'down'),(422,'up')]:
                self.button((x,698,120,86),'',a,enabled=enabled)
                self.icon(a,(x+60,741),WHITE if enabled else MUTED,23)
            # Fuel is a visual bar underneath the movement label.
            pygame.draw.rect(self.canvas,(60,78,90),(40,687,224,5))
            pygame.draw.rect(self.canvas,GOLD,(40,687,round(224*p.fuel/p.movement),5))
            self.button((570,698,510,86),'','fire',self.charge_owner is not None,enabled)
            self.icon('fire',(622,741),GOLD,22)
            power=p.power if self.charge_owner is not None or self.state=='flight' else 0
            for i in range(10):
                color=(113,210,140) if i<5 else GOLD if i<8 else (245,130,92)
                pygame.draw.rect(self.canvas,color if power>i*10 else (57,75,89),(675+i*36,722,28,40),border_radius=6)
            self.text('Release!' if self.charge_owner is not None else 'Hold to fire',825,672,28,GOLD,True)
            self.button((1110,698,145,86),'','pause')
            self.icon('pause',(1182,741),WHITE,23)

    def draw(self):
        self.buttons=[]
        self.canvas.fill(BG)
        if self.state=='menu': self.draw_menu()
        elif self.state=='build': self.draw_build()
        else:
            self.draw_field()
            if self.state in ('handoff','result'):
                self.box((325,235,630,320),BG)
                if self.state=='handoff':
                    self.text(f'PLAYER {self.active+1}',640,290,56,COLORS[self.players[self.active].color],True)
                    self.icon('left',(472,356),WHITE,22)
                    self.icon('up',(560,356),WHITE,22)
                    self.icon('fire',(704,356),GOLD,24)
                    self.icon('play',(810,356),GOLD,22)
                    self.text('Hold to charge. Let go to fire!',640,404,28,GOLD,True)
                    self.button((435,450,410,74),'Play!','begin',True)
                    self.icon('play',(785,487),GOLD,21)
                else:
                    self.text('DRAW' if self.winner is None else f'PLAYER {self.winner+1} WINS',640,290,56,GOLD,True)
                    self.icon('coin' if self.mode=='money' else 'check',(640,356),GOLD,28)
                    self.text('Build again!',640,404,28,MUTED,True)
                    self.button((435,450,410,74),'Play again','next',True)
        if self.paused:
            self.buttons=[]
            self.box((390,210,500,400),BG)
            self.text('PAUSED',640,264,56,WHITE,True)
            self.button((450,320,380,64),'Resume','resume',True)
            self.button((450,410,380,64),'End match / Main menu','menu')
            self.button((450,500,380,64),'Home','exit')
        return self.canvas

async def run(screen=None, clock=None):
    """GameHub entry point. Returns without pygame.quit or terminating the hub."""
    pygame.init()
    if screen is None:
        screen=pygame.display.set_mode((W,H),pygame.RESIZABLE)
    game=Game()
    if clock is None:
        clock=pygame.time.Clock()
    while game.running:
        dt=min(clock.tick(60)/1000,.05)
        sw,sh=screen.get_size()
        scale=min(sw/W,sh/H)
        vw,vh=round(W*scale),round(H*scale)
        ox,oy=(sw-vw)//2,(sh-vh)//2
        portrait=sh>sw
        if portrait: game.cancel_input()
        game.draw()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: game.running=False
            elif e.type==pygame.WINDOWFOCUSLOST: game.cancel_input(); game.paused=True
            elif e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:
                game.paused=not game.paused; game.cancel_input()
            elif e.type==pygame.FINGERUP: game.release(e.finger_id)
            elif e.type==pygame.MOUSEBUTTONUP and e.button==1 and not getattr(e,'touch',False): game.release('mouse')
            elif not portrait and e.type==pygame.FINGERDOWN:
                game.press(e.finger_id,((e.x*sw-ox)/scale,(e.y*sh-oy)/scale))
            elif not portrait and e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and not getattr(e,'touch',False):
                game.press('mouse',((e.pos[0]-ox)/scale,(e.pos[1]-oy)/scale))
            elif e.type==pygame.KEYDOWN and not portrait and not game.paused:
                keys={pygame.K_LEFT:'left',pygame.K_RIGHT:'right',pygame.K_UP:'up',pygame.K_DOWN:'down'}
                if e.key in keys: game.holds[e.key]=keys[e.key]
                elif e.key==pygame.K_SPACE: game.charge('space')
            elif e.type==pygame.KEYUP: game.release('space' if e.key==pygame.K_SPACE else e.key)
        if portrait:
            game.cancel_input()
        else:
            game.update(dt)
        screen.fill(BG)
        screen.blit(pygame.transform.smoothscale(game.draw(),(vw,vh)),(ox,oy))
        if portrait:
            screen.fill(BG)
            f=pygame.font.Font(None,max(18,min(38,sw//18)))
            msg=f.render('Rotate iPad to landscape',True,WHITE)
            screen.blit(msg,msg.get_rect(center=(sw//2,sh//2)))
        pygame.display.flip()
        await asyncio.sleep(0)
    return None

async def main(screen=None, clock=None):
    await run(screen, clock)

if __name__=='__main__':
    asyncio.run(main())
