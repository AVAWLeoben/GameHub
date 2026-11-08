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
        self.angle, self.power = 55., 65.
        self.x = 210 if index == 0 else 1070
        self.hp = self.max_hp
        self.fuel = 0
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
        self.players[self.active].fuel = self.players[self.active].movement
        self.wind = random.randint(-35,35)
        self.state = 'handoff'
        self.holds.clear()

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
        self.holds.clear()
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
        self.holds.clear()

    def update(self,dt):
        if self.paused:
            return
        for fx in self.fx: fx[2] += dt
        self.fx = [f for f in self.fx if f[2]<.6]
        if self.state=='battle':
            p = self.players[self.active]
            actions = set(self.holds.values())
            direction = int('right' in actions)-int('left' in actions)
            distance = min(p.fuel,dt*100)*direction
            old = p.x
            p.x = clamp(p.x+distance,90 if p.index==0 else 805,475 if p.index==0 else 1190)
            p.fuel -= abs(p.x-old)
            p.wheel -= (p.x-old)*4
            p.angle = clamp(p.angle+dt*32*(int('up' in actions)-int('down' in actions)),*self.limits(p))
            p.power = clamp(p.power+dt*30*(int('power+' in actions)-int('power-' in actions)),10,100)
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
        if a=='pause': self.paused=True; self.holds.clear()
        elif a=='resume': self.paused=False
        elif a=='exit': self.running=False
        elif a=='menu': self.paused=False; self.state='menu'; self.holds.clear()
        elif a.startswith('mode:'): self.new_campaign(a.split(':')[1])
        elif a.startswith('buy:'):
            _,kind,item = a.split(':'); self.buy(kind,item)
        elif a.startswith('color:'): self.players[self.build_player].color=int(a.split(':')[1])
        elif a=='ready':
            if self.build_player==0: self.build_player=1; self.notice=''
            else: self.start_round()
        elif a=='begin': self.state='battle'
        elif a=='fire': self.fire()
        elif a=='next': self.state='build'; self.build_player=0; self.notice=''

    def press(self,ident,pos):
        for rect,action,enabled in reversed(self.buttons):
            if rect.collidepoint(pos) and enabled:
                if action in ('left','right','up','down','power+','power-'):
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
        self.button((240,475,380,88),'FREE MODE','mode:free')
        self.button((660,475,380,88),'MONEY MODE','mode:money')
        self.text('All parts unlocked',430,594,28,MUTED,True)
        self.text('Win rounds. Buy upgrades.',850,594,28,MUTED,True)
        self.text('Shared iPad  |  Landscape  |  One shot per turn',640,675,28,MUTED,True)
        self.button((530,716,220,56),'Return to GameHub','exit')

    def draw_build(self):
        p = self.players[self.build_player]
        self.text('WORKSHOP',42,28,56)
        self.text(f'PLAYER {p.index+1}  /  '+('EVERYTHING UNLOCKED' if self.mode=='free' else f'${p.money}'),44,87,28,GOLD)
        self.text('Choose a body',44,144,28)
        for i,(name,spec) in enumerate(BODIES.items()):
            cost = 'Owned' if name in p.owned else '$'+str(spec[0])
            self.button((44+i*192,183,180,68),title(name),'buy:body:'+name,p.body==name)
            if self.mode=='money': self.text(cost,52+i*192,232,20,MUTED)
        self.text('Choose a weapon',44,278,28)
        for i,(name,spec) in enumerate(WEAPONS.items()):
            x=44+(i%3)*192; y=318+(i//3)*82
            cost = 'Owned' if name in p.owned else '$'+str(spec[0])
            self.button((x,y,180,68),title(name),'buy:weapon:'+name,p.weapon==name)
            if self.mode=='money': self.text(cost,x+8,y+49,20,MUTED)
        self.text('Paint / desaturated body tint',44,510,28)
        for i,c in enumerate(COLORS):
            self.button((44+i*90,550,74,58),'','color:'+str(i),p.color==i)
            pygame.draw.circle(self.canvas,c,(81+i*90,579),17)
        self.box((670,145,566,335))
        old = p.x; p.x=955
        self.art.tank(self.canvas,p,350,1.6); p.x=old
        self.text(title(p.body)+' / '+title(p.weapon),953,411,32,WHITE,True)
        self.text(f'Health {p.max_hp}    Move {p.movement}    Hit {round(WEAPONS[p.weapon][1]*BODIES[p.body][3])} x {WEAPONS[p.weapon][3]}',695,445,24,MUTED)
        for i,kind in enumerate(('armor','engine')):
            level = getattr(p,kind)
            suffix = ('MAX' if level==3 else '$'+str(500+level*350)) if self.mode=='money' else 'tap to cycle'
            self.button((680,510+i*85,546,68),f'{title(kind)} {level}/3  /  {suffix}','buy:'+kind+':upgrade')
        self.text(self.notice or 'Armor adds health. Engine adds movement per turn.',44,650,24,GOLD)
        self.button((44,709,230,62),'Main menu','menu')
        self.button((800,709,426,62),'Ready / '+('Player 2 builds next' if p.index==0 else 'Start round'),'ready',True)

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
        for p in self.players: self.art.tank(self.canvas,p,self.grounds[p.index])
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
        self.text(f'{arrow} WIND {abs(self.wind)}',640,62,32,GOLD,True)
        self.text(f'PLAYER {self.active+1}'+(' / SHOT IN FLIGHT' if self.state=='flight' else ' / YOUR TURN'),640,105,24,WHITE,True)
        self.box((0,650,1280,150),BG,0)
        if self.state in ('battle','flight'):
            p=self.players[self.active]
            self.text(f'MOVE {round(p.fuel)}',112,674,24,MUTED,True)
            self.text(f'AIM {round(p.angle)} deg',370,674,24,MUTED,True)
            self.text(f'POWER {round(p.power)}%',650,674,24,MUTED,True)
            enabled=self.state=='battle'
            for x,label,a in [(24,'<','left'),(122,'>','right'),(280,'-','down'),(378,'+','up'),(560,'-','power-'),(658,'+','power+')]:
                self.button((x,706,88,70),label,a,enabled=enabled)
            self.button((792,698,292,82),'FIRE','fire',True,enabled)
            self.button((1110,706,145,70),'Pause','pause')

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
                    self.text('Move, aim, set power, then fire.',640,353,28,MUTED,True)
                    self.text('Wind is fixed for your shot.',640,393,24,MUTED,True)
                    self.button((435,450,410,74),'Start my turn','begin',True)
                else:
                    self.text('DRAW' if self.winner is None else f'PLAYER {self.winner+1} WINS',640,290,56,GOLD,True)
                    self.text('Winner +$1200 / Other player +$700' if self.mode=='money' else 'Rebuild your tanks for the next round.',640,353,28,MUTED,True)
                    self.text('New terrain next round. Equipment is retained.',640,393,24,MUTED,True)
                    self.button((435,450,410,74),'Next round / Workshop','next',True)
        if self.paused:
            self.buttons=[]
            self.box((390,210,500,400),BG)
            self.text('PAUSED',640,264,56,WHITE,True)
            self.button((450,320,380,64),'Resume','resume',True)
            self.button((450,410,380,64),'End match / Main menu','menu')
            self.button((450,500,380,64),'Return to GameHub','exit')
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
        game.draw()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: game.running=False
            elif e.type==pygame.WINDOWFOCUSLOST: game.holds.clear(); game.paused=True
            elif e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:
                game.paused=not game.paused; game.holds.clear()
            elif e.type==pygame.FINGERUP: game.holds.pop(e.finger_id,None)
            elif e.type==pygame.MOUSEBUTTONUP: game.holds.pop('mouse',None)
            elif not portrait and e.type==pygame.FINGERDOWN:
                game.press(e.finger_id,((e.x*sw-ox)/scale,(e.y*sh-oy)/scale))
            elif not portrait and e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and not getattr(e,'touch',False):
                game.press('mouse',((e.pos[0]-ox)/scale,(e.pos[1]-oy)/scale))
            elif e.type==pygame.KEYDOWN and not portrait and not game.paused:
                keys={pygame.K_LEFT:'left',pygame.K_RIGHT:'right',pygame.K_UP:'up',pygame.K_DOWN:'down',pygame.K_q:'power-',pygame.K_e:'power+'}
                if e.key in keys: game.holds[e.key]=keys[e.key]
                elif e.key==pygame.K_SPACE: game.fire()
            elif e.type==pygame.KEYUP: game.holds.pop(e.key,None)
        if portrait:
            game.holds.clear()
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
