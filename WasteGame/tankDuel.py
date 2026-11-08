"""Tank Duel: local two-player pygame/pygbag artillery. await run(screen).

Keep this file beside the existing tank_game_assets folder.
Includes destructible height-map terrain, tank destruction effects, and a
compact victory card that leaves the battlefield visible.
"""
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
GREEN = (113, 210, 140)
GO_FILL = (40, 112, 74)
RED = (245, 100, 92)
DIM = (105, 121, 133)
COLORS = [(79,195,235),(241,112,97),(148,206,113),(187,146,234),(244,191,75),(223,224,220)]
BODIES = {'scout': (0,100,150,1.0), 'heavy': (1200,155,90,1.0), 'artillery': (900,110,110,1.15)}
WEAPONS = {'cannon': (0,36,56,1,1.0), 'twin_cannon': (1000,24,48,2,1.0),
           'mortar': (800,49,85,1,1.15), 'rocket_pod': (1600,22,62,3,.8),
           'plasma_gun': (2000,62,43,1,.65)}
ASSETS = Path(__file__).resolve().parent / 'tank_game_assets'
PHYSICS_DT = 1 / 240
TERRAIN_BOTTOM = 642


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
                for y in range(s.get_height()):
                    for x in range(s.get_width()):
                        r, g, b, a = s.get_at((x, y))
                        lum = min(255, int((.2126*r + .7152*g + .0722*b) * 1.5))
                        s.set_at((x,y), (*(int(lum*c/255) for c in color), a))
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
                origin, angle, color = pos['weapon_slot'], p.angle, None
            else:
                n = next(n for n in rig['nodes'] if n['id'] == ident)
                origin = pos[ident]
                angle = p.wheel if ident.startswith('wheel') else 0
                color = COLORS[p.color] if ident in ('hull','turret') else None
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
        self.texts = []
        self.font_cache = {}
        self.aim_touch = None
        self.aim_pos = None
        self.aim_hint = True
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
        self.floaters = []
        self.notice = ''
        self.paused = False
        self.grounds = [575,575]
        self.obstacle = pygame.Rect(580,340,120,300)
        self.tower = True
        self.winner = None
        self.payout = [0,0]
        self.wind = 0
        self.accum = 0
        self.settle = 0
        self.build_player = 0
        self.charge_owner = None
        self.charge_time = 0.
        self.t = 0.
        self.denied = 0.
        self.tutorial = True
        self.terrain = None
        self.terrain_surface = None
        self.terrain_dirty = True
        self.debris = []
        self.destroyed = set()
        self.destruction_age = 99.
        self.smoke = []
        self.smoke_timer = 0.
        self.shake = 0.
        self.result_time = 0.
        rng = random.Random(71)
        self.leaves = [[rng.uniform(0,W),rng.uniform(165,470),rng.uniform(0,6.28),rng.uniform(.7,1.3)] for _ in range(14)]

    def wave(self, speed=4.):
        return (math.sin(self.t*speed)+1)/2

    def text(self, text, x, y, size=28, color=WHITE, center=False):
        self.texts.append((str(text),x,y,size,color,center))

    def clip_texts(self, rect):
        r = pygame.Rect(rect)
        self.texts = [t for t in self.texts if not r.collidepoint(t[1],t[2])]

    def blit_text(self, target, scale, ox, oy):
        for s,x,y,size,color,center in self.texts:
            px = max(8,round(size*scale))
            font = self.font_cache.get(px)
            if font is None:
                font = self.font_cache[px] = pygame.font.Font(None,px)
            surf = font.render(s,True,color)
            pos = (ox+x*scale,oy+y*scale)
            target.blit(surf,surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos))

    def box(self, rect, color=PANEL, radius=16):
        pygame.draw.rect(self.canvas,color,rect,border_radius=radius)

    def button(self, rect, label, action, selected=False, enabled=True, pulse=False, tint=None):
        r = pygame.Rect(rect)
        d = r
        if pulse and enabled:
            g = round(self.wave(5)*5)
            d = r.inflate(g*2,g*2)
        glow = selected or (pulse and enabled)
        self.box(d,tint if tint else ((56,99,112) if selected else PANEL))
        pygame.draw.rect(self.canvas,GOLD if glow else (65,86,102),d,4 if glow else 2,border_radius=14)
        if label:
            self.text(label,r.centerx,r.centery,24,WHITE if enabled else DIM,True)
        self.buttons.append((r,action,enabled))

    def star(self, center, big, small, n, color, width=0):
        pts = [pygame.Vector2(big if k%2==0 else small,0).rotate(-90+k*180/n)+pygame.Vector2(center) for k in range(n*2)]
        pygame.draw.polygon(self.canvas,color,pts,width)

    def badge(self, p, center, r=24):
        x,y = center
        pygame.draw.circle(self.canvas,COLORS[p.color],(x,y),r)
        pygame.draw.circle(self.canvas,BG,(x,y),r,3)
        n = p.index+1
        for k in range(n):
            pygame.draw.circle(self.canvas,BG,(round(x+(k-(n-1)/2)*r*.62),y),max(3,round(r*.2)))

    def icon(self, kind, center, color=WHITE, size=30):
        x,y = center
        c = self.canvas
        if kind in ('left','right','up','down','play'):
            points = [(-size/2,-size),(size/2,0),(-size/2,size)]
            angle = {'left':180,'right':0,'up':-90,'down':90,'play':0}[kind]
            pygame.draw.polygon(c,color,[pygame.Vector2(v).rotate(angle)+pygame.Vector2(x,y) for v in points])
        elif kind=='fire':
            pygame.draw.circle(c,color,(x,y),size,4)
            pygame.draw.circle(c,color,(x,y),size//3)
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                pygame.draw.line(c,color,(x+dx*(size-7),y+dy*(size-7)),(x+dx*(size+9),y+dy*(size+9)),5)
        elif kind=='armor':
            pygame.draw.polygon(c,color,[(x-size,y-size),(x+size,y-size),(x+size*.8,y+size*.4),(x,y+size),(x-size*.8,y+size*.4)],4)
        elif kind=='engine':
            pygame.draw.circle(c,color,(x,y),size,5)
            for angle in range(0,360,60):
                v=pygame.Vector2(size-5,0).rotate(angle)
                pygame.draw.line(c,color,(x,y),(x+v.x,y+v.y),4)
        elif kind=='pause':
            for dx in (-12,8): pygame.draw.rect(c,color,(x+dx,y-size,7,size*2),border_radius=3)
        elif kind=='fuel':
            pygame.draw.rect(c,color,(x-size*.6,y-size*.65,size*1.2,size*1.5),3,border_radius=4)
            pygame.draw.rect(c,color,(x-size*.3,y-size,size*.6,size*.35),3)
            pygame.draw.line(c,color,(x-size*.35,y),(x+size*.35,y+size*.5),3)
        elif kind=='coin':
            pygame.draw.circle(c,color if color!=WHITE else GOLD,(x,y),size)
            pygame.draw.circle(c,BG,(x,y),max(2,size-6),3)
        elif kind=='check':
            pygame.draw.lines(c,color,False,[(x-size,y),(x-size/4,y+size*.7),(x+size,y-size)],5)
        elif kind=='heart':
            r=size*.55
            pygame.draw.circle(c,color,(round(x-r),round(y-r*.45)),round(r))
            pygame.draw.circle(c,color,(round(x+r),round(y-r*.45)),round(r))
            pygame.draw.polygon(c,color,[(x-size*1.05,y-r*.2),(x+size*1.05,y-r*.2),(x,y+size)])
        elif kind=='star':
            self.star((x,y),size,size*.45,5,color)
        elif kind=='boom':
            self.star((x,y),size,size*.55,8,(255,150,60))
            self.star((x,y),size*.6,size*.3,8,(255,225,120))
        elif kind=='trophy':
            pygame.draw.polygon(c,color,[(x-size*.7,y-size),(x+size*.7,y-size),(x+size*.5,y+size*.25),(x-size*.5,y+size*.25)])
            pygame.draw.circle(c,color,(round(x-size*.78),round(y-size*.5)),round(size*.34),4)
            pygame.draw.circle(c,color,(round(x+size*.78),round(y-size*.5)),round(size*.34),4)
            pygame.draw.rect(c,color,(x-size*.13,y+size*.2,size*.26,size*.5))
            pygame.draw.rect(c,color,(x-size*.5,y+size*.68,size,size*.28),border_radius=4)
        elif kind=='lock':
            pygame.draw.arc(c,color,(x-size*.45,y-size*.95,size*.9,size*1.1),0,math.pi,5)
            pygame.draw.rect(c,color,(x-size*.7,y-size*.15,size*1.4,size*1.05),border_radius=5)
            pygame.draw.circle(c,BG,(round(x),round(y+size*.3)),max(2,round(size*.16)))
        elif kind=='hand':
            pygame.draw.rect(c,color,(x-size*.22,y-size,size*.44,size*1.15),border_radius=round(size*.22))
            pygame.draw.rect(c,color,(x-size*.6,y-size*.05,size*1.2,size*.95),border_radius=round(size*.3))
            pygame.draw.rect(c,BG,(x-size*.22,y-size,size*.44,size*1.15),2,border_radius=round(size*.22))
        elif kind=='home':
            pygame.draw.polygon(c,color,[(x-size,y-size*.05),(x,y-size),(x+size,y-size*.05)])
            pygame.draw.rect(c,color,(x-size*.7,y-size*.05,size*1.4,size*.95))
            pygame.draw.rect(c,BG,(x-size*.17,y+size*.25,size*.34,size*.65))
        elif kind=='replay':
            pygame.draw.arc(c,color,(x-size,y-size,size*2,size*2),.9,5.7,6)
            ex,ey=x+size*math.cos(.9),y-size*math.sin(.9)
            pygame.draw.polygon(c,color,[(ex-9,ey-12),(ex+13,ey+2),(ex-12,ey+9)])
        elif kind=='menu':
            for dx in (-1,1):
                for dy in (-1,1):
                    pygame.draw.rect(c,color,(x+dx*size*.55-size*.4,y+dy*size*.55-size*.4,size*.8,size*.8),border_radius=4)
        elif kind=='plus':
            pygame.draw.line(c,color,(x-size,y),(x+size,y),7)
            pygame.draw.line(c,color,(x,y-size),(x,y+size),7)
        elif kind=='equals':
            pygame.draw.line(c,color,(x-size,y-size*.4),(x+size,y-size*.4),7)
            pygame.draw.line(c,color,(x-size,y+size*.4),(x+size,y+size*.4),7)

    def pips(self,n,center,color,r=7,gap=18,off=(70,87,103),total=None):
        total=total or n
        x,y=center
        for k in range(total):
            pygame.draw.circle(self.canvas,color if k<n else off,(round(x+(k-(total-1)/2)*gap),y),r)

    def cancel_input(self):
        self.holds.clear()
        self.charge_owner=None
        self.charge_time=0.
        self.aim_touch=None
        self.aim_pos=None

    def charge(self,ident):
        if self.state=='battle' and not self.paused and self.charge_owner is None:
            self.charge_owner=ident
            self.charge_time=0.
            self.players[self.active].power=10.

    def release(self,ident):
        self.holds.pop(ident,None)
        if ident==self.aim_touch:
            self.aim_touch=None
        if ident==self.charge_owner:
            self.charge_owner=None
            if self.state=='battle' and not self.paused:
                self.fire()

    def limits(self,p):
        rig=self.art.rig['tanks'][p.body]
        slot=next(n for n in rig['nodes'] if n['id']=='weapon_slot')['joint']['rotation']
        amin,amax=self.art.rig['weapons'][p.weapon]['aimRange']
        return max(5,-min(slot['max'],amax)),min(-slot['min'],-amin)

    def new_campaign(self,mode):
        self.cancel_input()
        self.mode=mode
        self.players=[Player(0),Player(1)]
        self.round=0
        self.build_player=0
        self.state='build'
        self.notice=''
        self.denied=0.
        self.tutorial=True
        self.aim_hint=True
        self.paused=False

    def deny(self,message=''):
        self.notice=message
        self.denied=.6

    def buy(self,kind,item):
        p=self.players[self.build_player]
        if kind=='fuel':
            if self.mode!='money' or self.state!='build': return
            missing=max(0.,p.movement-p.fuel)
            amount=min(missing,p.money/2.)
            if amount<=0:
                if missing>=.01: self.deny('Need coins')
                return
            p.money-=math.ceil(amount*2)
            p.fuel=min(p.movement,p.fuel+amount)
            self.notice=''
            return
        if kind in ('body','weapon'):
            price=(BODIES if kind=='body' else WEAPONS)[item][0]
            if self.mode=='money' and item not in p.owned:
                if p.money<price:
                    self.deny('Save up for this part.')
                    return
                p.money-=price
                p.owned.add(item)
            setattr(p,kind,item)
        else:
            level=getattr(p,kind)
            if level>=3:
                if self.mode=='free': setattr(p,kind,0)
                return
            price=500+level*350
            if self.mode=='money':
                if p.money<price:
                    self.deny('Not enough money yet.')
                    return
                p.money-=price
            setattr(p,kind,level+1)
        p.fuel=min(p.fuel,p.movement)
        p.angle=clamp(p.angle,*self.limits(p))
        self.notice=''

    def start_round(self):
        self.cancel_input()
        self.round+=1
        left=random.choice([510,550,590])
        self.grounds=[left,clamp(left+random.choice([-80,0,80]),490,610)]
        self.obstacle=pygame.Rect(575,random.choice([325,365,405]),130,400)
        self.tower=random.choice([True,False])
        self.terrain=None
        self.terrain=[self.ground_at(x) for x in range(W)]
        self.terrain_dirty=True
        self.shots,self.fx,self.floaters=[],[],[]
        self.debris,self.smoke=[],[]
        self.destroyed.clear()
        self.destruction_age=99.
        self.shake=0.
        self.smoke_timer=0.
        self.winner=None
        self.result_time=0.
        for p in self.players:
            p.x=210 if p.index==0 else 1070
            p.hp=p.max_hp
            p.angle=clamp(p.angle,*self.limits(p))
        self.settle_tanks()
        self.active=(self.round-1)%2
        self.state='battle'
        self.begin_turn()

    def begin_turn(self):
        if self.mode=='free':
            self.players[self.active].fuel=self.players[self.active].movement
        self.wind=random.randint(-35,35)
        self.state='handoff'
        self.cancel_input()

    def launch(self,p,angle,power):
        w=self.art.rig['weapons'][p.weapon]
        origin=self.art.mount(p,self.grounds[p.index])
        direction=1 if p.index==0 else -1
        rad=math.radians(angle)
        vec=pygame.Vector2(direction*math.cos(rad),-math.sin(rad))
        muzzle=origin+vec*((w['muzzle'][0]-w['pivot'][0])*.8)
        return muzzle,vec*(310+power*5.1)

    def fire(self):
        if self.state!='battle' or self.shots: return
        p=self.players[self.active]
        spec=WEAPONS[p.weapon]
        for i in range(spec[3]):
            angle=p.angle+(i-(spec[3]-1)/2)*2
            muzzle,velocity=self.launch(p,angle,p.power)
            self.shots.append({'pos':muzzle,'vel':velocity,'age':0.,'trail':[],
                               'owner':p.index,'weapon':p.weapon,'damage':spec[1]*BODIES[p.body][3]})
        self.state='flight'
        self.tutorial=False
        self.aim_hint=False
        self.cancel_input()
        self.accum=self.settle=0.

    def ground_at(self,x):
        if self.terrain is not None:
            return self.terrain[int(clamp(x,0,W-1))]
        if self.obstacle.left<=x<=self.obstacle.right:
            if self.tower: return self.obstacle.top
            return self.obstacle.top+(45 if abs(x-640)>40 else 0)
        return self.grounds[0 if x<640 else 1]

    def tank_rect(self,p):
        width=self.art.rig['tanks'][p.body]['nodes'][0]['size'][0]*.8
        return pygame.Rect(p.x-width/2,self.grounds[p.index]-72,width,72)

    def settle_tanks(self):
        if self.terrain is None: return
        for p in self.players:
            half=self.tank_rect(p).width*.38
            self.grounds[p.index]=min(self.ground_at(p.x+half*k/4) for k in range(-4,5))

    def carve_crater(self,x,y,radius):
        if self.terrain is None: return
        changed=False
        for px in range(max(0,int(x-radius)),min(W,int(x+radius)+1)):
            depth=math.sqrt(max(0.,radius*radius-(px-x)**2))
            # A height map has no caves: side hits collapse the exposed column.
            bottom=min(TERRAIN_BOTTOM,y+depth)
            if bottom>self.terrain[px]:
                self.terrain[px]=bottom
                changed=True
        if changed: self.terrain_dirty=True

    def destroy_tank(self,p):
        if p.index in self.destroyed: return
        self.destroyed.add(p.index)
        self.destruction_age=0.
        self.shake=max(self.shake,.65)
        r=self.tank_rect(p)
        for dx,dy,delay,radius in [(0,-10,0.,120),(-32,0,-.10,78),(34,-28,-.22,90)]:
            self.fx.append([r.centerx+dx,r.centery+dy,delay,radius])
        for _ in range(28):
            angle=random.uniform(math.pi*1.08,math.pi*1.92)
            speed=random.uniform(110,350)
            self.debris.append({'pos':pygame.Vector2(r.center),
                'vel':pygame.Vector2(math.cos(angle)*speed,math.sin(angle)*speed),
                'life':random.uniform(1.2,2.1),'size':random.randint(3,9),
                'color':random.choice([COLORS[p.color],GOLD,(55,62,67)])})

    def explode(self,shot):
        x,y=shot['pos']
        radius=WEAPONS[shot['weapon']][2]
        self.fx.append([x,y,0.,radius])
        self.shake=max(self.shake,.16)
        for p in self.players:
            if p.hp<=0: continue
            r=self.tank_rect(p)
            nearest=pygame.Vector2(clamp(x,r.left,r.right),clamp(y,r.top,r.bottom))
            dist=nearest.distance_to((x,y))
            if dist<radius:
                damage=round(shot['damage']*(1-.65*dist/radius))
                lost=min(p.hp,damage)
                p.hp-=lost
                if lost>0: self.floaters.append([r.centerx,r.top-10,0.,lost])
                if p.hp==0: self.destroy_tank(p)
        self.carve_crater(x,y,radius*.85)
        self.settle_tanks()
        for _ in range(10):
            self.debris.append({'pos':pygame.Vector2(x,y),
                'vel':pygame.Vector2(random.uniform(-110,110),random.uniform(-190,-65)),
                'life':random.uniform(.35,.8),'size':random.randint(2,5),'color':(143,139,104)})

    def advance_projectile(self,pos,vel,weapon,dt):
        vel.x+=self.wind*dt
        vel.y+=400*WEAPONS[weapon][4]*dt
        pos+=vel*dt

    def projectile_hit(self,pos,owner,age):
        x,y=pos
        terrain_hit=0<=x<W and y>=self.ground_at(x)
        tank_hit=any(p.hp>0 and self.tank_rect(p).collidepoint(x,y)
                     for p in self.players if p.index!=owner or age>.25)
        return terrain_hit or tank_hit

    def physics(self,dt):
        for s in self.shots[:]:
            s['age']+=dt
            self.advance_projectile(s['pos'],s['vel'],s['weapon'],dt)
            x,y=s['pos']
            if self.projectile_hit(s['pos'],s['owner'],s['age']):
                self.explode(s)
                self.shots.remove(s)
            elif x<-200 or x>W+200 or y>H+100 or s['age']>12:
                self.shots.remove(s)
            else:
                s['trail'].append((int(x),int(y)))
                s['trail']=s['trail'][-65:]

    def finish_round(self):
        alive=[p for p in self.players if p.hp>0]
        self.winner=alive[0].index if len(alive)==1 else None
        if self.winner is not None: self.players[self.winner].wins+=1
        self.payout=[0,0]
        if self.mode=='money':
            for p in self.players:
                self.payout[p.index]=1200 if p.index==self.winner else 700
                p.money+=self.payout[p.index]
        self.state='result'
        self.result_time=0.
        self.cancel_input()

    def update(self,dt):
        if self.paused: return
        self.t+=dt
        self.denied=max(0.,self.denied-dt)
        self.shake=max(0.,self.shake-dt)
        self.destruction_age+=dt
        if self.state=='result': self.result_time+=dt
        for f in self.floaters: f[2]+=dt
        self.floaters=[f for f in self.floaters if f[2]<1.2]
        for fx in self.fx: fx[2]+=dt
        self.fx=[f for f in self.fx if f[2]<.6]
        for piece in self.debris:
            piece['life']-=dt
            piece['vel'].y+=500*dt
            piece['pos']+=piece['vel']*dt
            x,y=piece['pos']
            if 0<=x<W and y>=self.ground_at(x):
                piece['pos'].y=self.ground_at(x)-1
                piece['vel'].x*=.7
                piece['vel'].y=-abs(piece['vel'].y)*.28
        self.debris=[p for p in self.debris if p['life']>0]
        for puff in self.smoke:
            puff[0]+=self.wind*dt*.25
            puff[1]-=24*dt
            puff[2]+=dt
        self.smoke=[p for p in self.smoke if p[2]<2.2]
        if self.state in ('battle','flight','handoff','result'):
            self.smoke_timer+=dt
            if self.destroyed and self.smoke_timer>=.12:
                self.smoke_timer=0.
                for index in self.destroyed:
                    p=self.players[index]
                    self.smoke.append([p.x+random.uniform(-15,15),self.grounds[index]-24,0.,random.randint(8,15)])
            for leaf in self.leaves:
                leaf[2]+=dt*2
                leaf[0]=(leaf[0]+self.wind*2.8*leaf[3]*dt)%W
                leaf[1]+=(8+math.sin(leaf[2])*5)*dt
                if leaf[1]>min(620,self.ground_at(leaf[0])-10): leaf[1]=155
        if self.state=='battle':
            p=self.players[self.active]
            actions=set(self.holds.values())
            direction=int('right' in actions)-int('left' in actions)
            distance=min(p.fuel,dt*100)*direction
            old=p.x
            p.x=clamp(p.x+distance,90 if p.index==0 else 805,475 if p.index==0 else 1190)
            p.fuel=max(0.,p.fuel-abs(p.x-old))
            p.wheel-=(p.x-old)*4
            self.settle_tanks()
            p.angle=clamp(p.angle+dt*45*(int('up' in actions)-int('down' in actions)),*self.limits(p))
            if self.charge_owner is not None:
                self.charge_time+=dt
                p.power=min(100.,10.+90.*self.charge_time/2.)
        elif self.state=='flight':
            self.accum+=min(dt,.05)
            while self.accum>=PHYSICS_DT:
                self.physics(PHYSICS_DT)
                self.accum-=PHYSICS_DT
            if not self.shots:
                self.settle+=dt
                if self.settle>.7 and (not self.destroyed or self.destruction_age>1.8):
                    if any(p.hp<=0 for p in self.players): self.finish_round()
                    else:
                        self.active=1-self.active
                        self.begin_turn()

    def action(self,a):
        if a=='pause': self.paused=True; self.cancel_input()
        elif a=='resume': self.paused=False
        elif a=='exit': self.running=False
        elif a=='menu': self.paused=False; self.state='menu'; self.cancel_input()
        elif a.startswith('mode:'): self.new_campaign(a.split(':')[1])
        elif a.startswith('buy:'):
            _,kind,item=a.split(':'); self.buy(kind,item)
        elif a.startswith('color:'): self.players[self.build_player].color=int(a.split(':')[1])
        elif a=='ready':
            if self.build_player==0: self.build_player=1; self.notice=''
            else: self.start_round()
        elif a=='begin': self.state='battle'; self.cancel_input()
        elif a=='next': self.state='build'; self.build_player=0; self.notice=''; self.cancel_input()

    def press(self,ident,pos):
        for rect,action,enabled in reversed(self.buttons):
            if rect.collidepoint(pos):
                if not enabled: return
                if action=='fire': self.charge(ident)
                elif action in ('left','right','up','down'):
                    if self.state=='battle' and not self.paused:
                        self.holds[ident]=action
                        if action in ('up','down'): self.aim_hint=False
                else: self.action(action)
                return
        if self.state=='battle' and not self.paused and 142<pos[1]<650 and self.aim_touch is None:
            self.aim_touch=ident
            self.drag(ident,pos)

    def drag(self,ident,pos):
        if ident!=self.aim_touch or self.state!='battle' or self.paused: return
        p=self.players[self.active]
        m=self.art.mount(p,self.grounds[p.index])
        d=1 if p.index==0 else -1
        dx,dy=(pos[0]-m.x)*d,m.y-pos[1]
        self.aim_pos=(pos[0],pos[1])
        if abs(dx)+abs(dy)<12: return
        p.angle=clamp(math.degrees(math.atan2(dy,dx)),*self.limits(p))
        self.aim_hint=False

    def draw_menu(self):
        self.text('TANK DUEL',640,110,76,WHITE,True)
        for i,p in enumerate(self.players):
            old,oldangle=p.x,p.angle
            p.x=330+i*620
            p.angle=45
            self.art.tank(self.canvas,p,330+round(math.sin(self.t*3+i*2)*3),1.3)
            p.x,p.angle=old,oldangle
        for k in range(7):
            f=k/6
            pygame.draw.circle(self.canvas,GOLD if k%2 else WHITE,(round(470+f*340),round(215-math.sin(f*math.pi)*70)),5)
        self.button((180,430,420,250),'','mode:free',pulse=True)
        self.icon('engine',(300,540),GOLD,46)
        self.icon('armor',(390,540),GOLD,38)
        self.icon('play',(500,540),GREEN,34)
        self.text('Build & play',390,640,24,MUTED,True)
        self.button((680,430,420,250),'','mode:money')
        self.icon('coin',(790,540),GOLD,44)
        self.icon('plus',(880,540),WHITE,20)
        self.icon('trophy',(970,540),GOLD,38)
        self.text('Win coins',890,640,24,MUTED,True)
        self.button((24,24,96,96),'','exit')
        self.icon('home',(72,76),WHITE,28)

    def price_badge(self,rect,name,price):
        if self.mode!='money': return
        p=self.players[self.build_player]
        r=pygame.Rect(rect)
        if name in p.owned:
            self.icon('check',(r.right-24,r.top+24),GREEN,10)
        else:
            afford=p.money>=price
            col=GOLD if afford else DIM
            if not afford: self.icon('lock',(r.left+24,r.top+24),DIM,12)
            self.icon('coin',(r.right-82,r.top+24),col,11)
            self.text(price,r.right-66,r.top+14,24,col)

    def draw_build(self):
        p=self.players[self.build_player]
        self.box((36,20,250,76),COLORS[p.color],38)
        for k in range(p.index+1):
            pygame.draw.circle(self.canvas,BG,(round(161+(k-p.index/2)*50),58),16)
        if self.mode=='money':
            shake=round(math.sin(self.t*60)*6) if self.denied>0 else 0
            col=RED if self.denied>0 else GOLD
            self.icon('coin',(1090+shake,58),col,26)
            self.text(p.money,1130+shake,42,40,col)
        for i,(name,spec) in enumerate(BODIES.items()):
            x=36+i*202
            rect=(x,112,190,162)
            self.button(rect,'','buy:body:'+name,p.body==name)
            demo=Player(0); demo.body=name; demo.color=p.color; demo.x=x+95; demo.angle=25
            self.art.tank(self.canvas,demo,214,.7)
            for k in range(round(spec[1]/50)): self.icon('heart',(x+22+k*22,254),RED,8)
            for k in range(round(spec[2]/50)): self.icon('right',(x+168-k*20,254),GREEN,7)
            self.price_badge(rect,name,spec[0])
        for i,(name,spec) in enumerate(WEAPONS.items()):
            x=36+(i%3)*202; y=286+(i//3)*116
            rect=(x,y,190,108)
            self.button(rect,'','buy:weapon:'+name,p.weapon==name)
            w=self.art.rig['weapons'][name]
            pic=self.art.sprite(w['sprite'],[v*.95 for v in w['size']])
            self.canvas.blit(pic,pic.get_rect(center=(x+95,y+46)))
            self.pips(spec[3],(x+34+(spec[3]-1)*7,y+90),WHITE,5,14)
            pygame.draw.circle(self.canvas,(245,130,92),(x+158,y+90),round(spec[2]/7),3)
            self.price_badge(rect,name,spec[0])
        for i,c in enumerate(COLORS):
            x=36+i*101
            self.button((x,526,88,80),'','color:'+str(i),p.color==i)
            pygame.draw.circle(self.canvas,c,(x+44,566),26)
            if p.color==i: self.icon('check',(x+44,566),BG,15)
        self.box((680,112,564,326))
        old=p.x; p.x=960
        self.art.tank(self.canvas,p,330,1.5); p.x=old
        for i in range(round(p.max_hp/25)): self.icon('heart',(716+i*26,380),COLORS[p.color],9)
        for i in range(round(p.movement/35)): self.icon('right',(716+i*26,414),GREEN,8)
        for i,kind in enumerate(('armor','engine')):
            y=447+i*83; level=getattr(p,kind)
            self.button((680,y,564,76),'','buy:'+kind+':upgrade')
            self.icon(kind,(722,y+38),GOLD,23)
            self.pips(level,(870,y+38),GOLD,12,42,total=3)
            maxed=level>=3
            if maxed and self.mode=='free': self.icon('replay',(1198,y+38),GOLD,20)
            elif maxed: self.icon('check',(1198,y+38),GREEN,16)
            else:
                self.icon('plus',(1198,y+38),GOLD,16)
                if self.mode=='money':
                    afford=p.money>=500+level*350
                    self.icon('coin',(1020,y+38),GOLD if afford else DIM,13)
                    self.text(500+level*350,1040,y+27,28,GOLD if afford else DIM)
        if self.mode=='money':
            cost=math.ceil(max(0.,p.movement-p.fuel)*2)
            self.button((680,615,564,72),'','buy:fuel:refill',enabled=cost>0 and p.money>0)
            self.icon('fuel',(721,651),GOLD,22)
            self.box((768,642,232,16),(60,78,90),6)
            if p.fuel>0: self.box((768,642,max(1,round(232*p.fuel/p.movement)),16),GREEN,6)
            if cost==0: self.icon('check',(1100,651),GREEN,15)
            else:
                self.icon('coin',(1060,651),GOLD,13)
                self.text(min(cost,p.money),1080,639,28,GOLD)
            self.icon('plus',(1205,651),GOLD,14)
        self.button((36,700,120,76),'','menu')
        self.icon('home',(96,738),WHITE,24)
        self.button((680,694,564,88),'','ready',tint=GO_FILL,pulse=True)
        self.icon('check',(930,738),WHITE,28)
        self.icon('play',(1010,738),GOLD,26)

    def aim_preview(self,p):
        # Use exactly the same launch and integration as live projectiles.
        power=p.power if self.charge_owner is not None else 55.
        count=WEAPONS[p.weapon][3]
        for shot_index in range(count):
            angle=p.angle+(shot_index-(count-1)/2)*2
            pos,vel=self.launch(p,angle,power)
            for k in range(192):
                self.advance_projectile(pos,vel,p.weapon,PHYSICS_DT)
                if self.projectile_hit(pos,p.index,(k+1)*PHYSICS_DT): break
                if (k+1)%24==0 and 142<pos.y<650:
                    radius=max(2,6-k//48) if shot_index==count//2 else 2
                    color=WHITE if (k//24)%2==0 else GOLD
                    pygame.draw.circle(self.canvas,color,(round(pos.x),round(pos.y)),radius)

    def draw_aim_help(self,p):
        m=self.art.mount(p,self.grounds[p.index])
        d=1 if p.index==0 else -1
        lo,hi=self.limits(p)
        def at(a,r):
            return round(m.x+d*math.cos(math.radians(a))*r),round(m.y-math.sin(math.radians(a))*r)
        if self.aim_hint or self.aim_touch is not None:
            for k in range(11): pygame.draw.circle(self.canvas,(235,240,230),at(lo+(hi-lo)*k/10,120),4)
        if self.aim_hint and self.aim_touch is None:
            a=lo+(hi-lo)*(math.sin(self.t*1.8)+1)/2
            x,y=at(a,120)
            pygame.draw.circle(self.canvas,GOLD,(x,y),round(18+self.wave(6)*8),4)
            self.icon('hand',(x+4,y+22),WHITE,24)
        if self.aim_touch is not None and self.aim_pos:
            pygame.draw.circle(self.canvas,GOLD,(round(self.aim_pos[0]),round(self.aim_pos[1])),30,4)

    def protractor(self,center,p):
        x,y=center
        d=1 if p.index==0 else -1
        base=(x-d*18,y+14)
        pygame.draw.line(self.canvas,(90,108,120),(base[0]-d*8,base[1]),(base[0]+d*46,base[1]),3)
        rad=math.radians(p.angle)
        tip=(base[0]+d*math.cos(rad)*40,base[1]-math.sin(rad)*40)
        pygame.draw.line(self.canvas,GOLD,base,tip,6)
        pygame.draw.circle(self.canvas,WHITE,base,6)

    def draw_terrain(self):
        # Cached layer is rebuilt only after an impact or a new round.
        if self.terrain_surface is None or self.terrain_dirty:
            layer=pygame.Surface((W,H),pygame.SRCALPHA)
            for x in range(W):
                top=round(self.ground_at(x))
                stone=self.obstacle.left<=x<=self.obstacle.right
                color=(66,80,91) if stone and self.tower else (99,110,100) if stone else (61,81,78)
                pygame.draw.line(layer,color,(x,top),(x,H-1))
                rim=(116,132,142) if stone and self.tower else (143,159,105)
                pygame.draw.line(layer,rim,(x,top),(x,top+5))
            for x in range(20,W,42):
                for y in range(180,H,36):
                    if y>max(self.ground_at(xx) for xx in range(x,min(W,x+15)))+14:
                        pygame.draw.line(layer,(81,100,88),(x,y),(min(W-1,x+14),y),3)
            if self.tower:
                for y in range(self.obstacle.top+14,650,32):
                    for x in range(self.obstacle.left,self.obstacle.right):
                        if y>self.ground_at(x)+7:
                            layer.set_at((x,y),(92,106,113))
            self.terrain_surface=layer
            self.terrain_dirty=False
        self.canvas.blit(self.terrain_surface,(0,0))

    def draw_wreck(self,p):
        x,y=round(p.x),round(self.grounds[p.index])
        pygame.draw.ellipse(self.canvas,(36,39,42),(x-44,y-12,88,18))
        pygame.draw.polygon(self.canvas,(66,67,64),[(x-32,y),(x-22,y-22),(x+12,y-15),(x+33,y)])
        pygame.draw.line(self.canvas,(91,85,73),(x-15,y-20),(x+18,y-36),7)
        # Small colour-and-dot badge identifies the wreck too.
        self.badge(p,(x,y-10),10)
        for k in range(3):
            flame=round(6+self.wave(8+k)*8)
            self.star((x-15+k*15,y-20),flame,flame*.45,5,(245,142,58))

    def draw_field(self):
        self.canvas.fill((107,155,176))
        pygame.draw.circle(self.canvas,(245,221,167),(1030,225),46)
        for x,y in [(140,205),(890,310),(370,265)]:
            pygame.draw.rect(self.canvas,(184,207,211),(x,y,110,13),border_radius=6)
        self.draw_terrain()
        for x,y,phase,scale in self.leaves:
            if y>=self.ground_at(x): continue
            angle=math.sin(phase)*35+(20 if self.wind>=0 else -20)
            center=pygame.Vector2(x,y)
            pts=[center+pygame.Vector2(v).rotate(angle)*scale for v in [(-7,0),(-2,-4),(7,0),(2,4)]]
            pygame.draw.polygon(self.canvas,(184,182,93),pts)
            pygame.draw.line(self.canvas,(105,126,73),pts[0],pts[2],1)
        for p in self.players:
            if p.hp>0: self.art.tank(self.canvas,p,self.grounds[p.index])
            else: self.draw_wreck(p)
        for x,y,age,size in self.smoke:
            shade=round(70+age*16)
            pygame.draw.circle(self.canvas,(shade,shade+6,shade+9),(round(x),round(y)),round(size+age*7))
        if self.state=='battle' and not self.paused:
            self.aim_preview(self.players[self.active])
            self.draw_aim_help(self.players[self.active])
        if self.state in ('battle','handoff'):
            p=self.players[self.active]
            bob=round(math.sin(self.t*6)*8)
            self.icon('down',(round(p.x),round(self.grounds[p.index]-128+bob)),COLORS[p.color],20)
        if self.state=='battle':
            p=self.players[self.active]
            half=self.art.rig['tanks'][p.body]['nodes'][0]['size'][0]*.4
            for direction,offset in [('left',-1),('right',1)]:
                cx=round(clamp(p.x+offset*(half+56),56,W-56))
                cy=round(self.grounds[p.index]-30)
                rect=pygame.Rect(cx-48,cy-52,96,104)
                self.buttons.append((rect,direction,p.fuel>0))
                ok=p.fuel>0
                held=direction in self.holds.values()
                col=(217,228,213) if ok else (122,140,132)
                pygame.draw.circle(self.canvas,GO_FILL if held else ((40,60,70) if ok else (70,82,86)),(cx,cy),42)
                pygame.draw.circle(self.canvas,GOLD if held else col,(cx,cy),42,4)
                self.icon(direction,(cx+(-4 if direction=='left' else 4),cy),col,19)
        for s in self.shots:
            if len(s['trail'])>1: pygame.draw.lines(self.canvas,(242,223,164),False,s['trail'],2)
            spec=self.art.rig['projectiles'][self.art.rig['weapons'][s['weapon']]['projectile']]
            pic=self.art.sprite(spec['sprite'],[v*.55 for v in spec['size']])
            pic=pygame.transform.rotate(pic,-math.degrees(math.atan2(s['vel'].y,s['vel'].x)))
            self.canvas.blit(pic,pic.get_rect(center=s['pos']))
            if s['pos'].y<142:
                self.icon('down',(round(clamp(s['pos'].x,30,1250)),158),GOLD,14)
        for piece in self.debris:
            pygame.draw.circle(self.canvas,piece['color'],(round(piece['pos'].x),round(piece['pos'].y)),piece['size'])
        for x,y,t,r in self.fx:
            if t<0: continue
            pic=self.art.sprite(f'png/fx/explosion_{min(7,int(t*14))}.png',(r*2,r*2))
            self.canvas.blit(pic,pic.get_rect(center=(x,y)))
        for x,y,t,dmg in self.floaters:
            fy=round(y-t*70)
            self.icon('heart',(round(x-24),fy),RED,13)
            self.text(f'-{dmg}',round(x-4),fy-12,40,WHITE)
        # Shake only the battlefield; controls and status remain stable.
        if self.shake>0 and not self.paused:
            amount=round(9*min(1.,self.shake/.65))
            dx=round(math.sin(self.t*91)*amount)
            dy=round(math.cos(self.t*79)*amount*.6)
            field=self.canvas.subsurface((0,142,W,508)).copy()
            previous=self.canvas.get_clip()
            self.canvas.set_clip((0,142,W,508))
            self.canvas.blit(field,(dx,142+dy))
            self.canvas.set_clip(previous)
        if self.state in ('battle','flight','handoff'):
            pygame.draw.rect(self.canvas,COLORS[self.players[self.active].color],(0,142,W,508),10)
        self.box((0,0,W,142),BG,0)
        for i,p in enumerate(self.players):
            x=28 if i==0 else 902
            if i==self.active and self.state in ('battle','flight'):
                pygame.draw.rect(self.canvas,GOLD,(x-14,8,378,126),4,border_radius=16)
            self.badge(p,(x+28,40),24)
            slots=min(5,max(3,p.wins))
            for k in range(slots): self.icon('star',(x+80+k*34,40),GOLD if k<p.wins else (60,78,90),15)
            w=self.art.rig['weapons'][p.weapon]
            pic=self.art.sprite(w['sprite'],[v*.62 for v in w['size']])
            self.canvas.blit(pic,pic.get_rect(center=(x+318,40)))
            self.icon('heart',(x+16,98),RED,13)
            self.box((x+40,84,310,28),(55,66,78),10)
            if p.hp>0: self.box((x+40,84,max(1,int(310*p.hp/p.max_hp)),28),COLORS[p.color],10)
            self.text(p.hp,x+195,98,24,WHITE,True)
        if self.wind: self.icon('left' if self.wind<0 else 'right',(640,50),GOLD,16+round(abs(self.wind)/35*12))
        else: pygame.draw.circle(self.canvas,GOLD,(640,50),14,4)
        self.pips(sum(abs(self.wind)>k*7 for k in range(5)),(640,102),GOLD,8,26,(60,78,90),5)
        self.box((0,650,1280,150),BG,0)
        if self.state in ('battle','flight'):
            p=self.players[self.active]
            enabled=self.state=='battle'
            pygame.draw.rect(self.canvas,COLORS[p.color],(0,650,W,6))
            self.icon('fuel',(40,674),MUTED,12)
            pygame.draw.rect(self.canvas,(60,78,90),(70,668,194,10),border_radius=5)
            pygame.draw.rect(self.canvas,GOLD,(70,668,round(194*p.fuel/p.movement),10),border_radius=5)
            self.protractor((416,664),p)
            for x,a in [(24,'left'),(156,'right'),(290,'down'),(422,'up')]:
                self.button((x,698,120,86),'',a,enabled=enabled)
                self.icon(a,(x+60,741),WHITE if enabled else MUTED,23)
            idle_hint=self.tutorial and enabled and self.charge_owner is None
            self.button((570,698,510,86),'','fire',self.charge_owner is not None,enabled,pulse=idle_hint)
            self.icon('fire',(622,741),GOLD,22)
            power=p.power if self.charge_owner is not None or self.state=='flight' else 0
            for i in range(10):
                color=GREEN if i<5 else GOLD if i<8 else (245,130,92)
                pygame.draw.rect(self.canvas,color if power>i*10 else (57,75,89),(675+i*36,722,28,40),border_radius=6)
            if enabled:
                hy=670
                if self.charge_owner is not None:
                    bob=round(math.sin(self.t*14)*5)
                    self.icon('up',(825,hy-2+bob),GREEN,17)
                else:
                    self.icon('hand',(825,hy+4),WHITE,15)
                    pygame.draw.circle(self.canvas,GOLD,(825,hy-8),round(6+self.wave(6)*9),3)
            self.button((1110,698,145,86),'','pause')
            self.icon('pause',(1182,741),WHITE,23)

    def draw_steps(self,cy):
        xs=[430,570,710,850]
        lit=int(self.t*1.4)%4
        for k,x in enumerate(xs):
            r=pygame.Rect(0,0,104,104); r.center=(x,cy)
            self.box(r,(40,60,80) if k==lit else PANEL,14)
            pygame.draw.rect(self.canvas,GOLD if k==lit else (65,86,102),r,3,border_radius=14)
            if k<3: self.icon('right',(x+70,cy),MUTED,9)
            if k==0:
                self.box((x-30,cy+6,60,30),(240,120,70),14)
                self.icon('hand',(x+8,cy-4+round(self.wave(6)*6)),WHITE,17)
            elif k==1:
                fill=(self.t*1.4)%4-1 if lit==1 else 1.
                n=5 if lit!=1 else clamp(int(fill*5)+1,1,5)
                for b in range(5):
                    h=12+b*9
                    pygame.draw.rect(self.canvas,GREEN if b<n else (57,75,89),(x-40+b*17,cy+34-h,13,h),border_radius=3)
            elif k==2:
                self.icon('up',(x,cy-22),GREEN,16)
                self.icon('hand',(x,cy+14),WHITE,17)
            else: self.icon('boom',(x,cy),GOLD,40)

    def draw_handoff(self):
        self.buttons=[]
        p=self.players[self.active]
        panel=pygame.Rect(300,160,680,480)
        self.clip_texts(panel)
        self.box(panel,BG)
        pygame.draw.rect(self.canvas,COLORS[p.color],panel,8,border_radius=16)
        self.badge(p,(360,222),30)
        old,oldangle=p.x,p.angle
        p.x=700; p.angle=40
        self.art.tank(self.canvas,p,330,1.5)
        p.x,p.angle=old,oldangle
        self.draw_steps(410)
        self.button((440,500,400,110),'','begin',tint=GO_FILL,pulse=True)
        self.icon('play',(640,555),WHITE,38)

    def draw_result(self):
        self.buttons=[]
        panel=pygame.Rect(360,164,560,230)
        self.clip_texts(panel)
        self.box(panel,BG)
        winner=self.players[self.winner] if self.winner is not None else None
        color=COLORS[winner.color] if winner else GOLD
        pygame.draw.rect(self.canvas,color,panel,5,border_radius=16)
        if winner:
            self.badge(winner,(425,223),30)
            bounce=round(math.sin(self.t*5)*4)
            self.icon('trophy',(640,222+bounce),GOLD,37)
            self.icon('star',(565,218),GOLD,18)
            self.icon('star',(715,218),GOLD,18)
            self.badge(winner,(855,223),24)
            # The surviving tank remains on the field, highlighted in gold.
            r=self.tank_rect(winner).inflate(24,22)
            pygame.draw.rect(self.canvas,GOLD,r,3,border_radius=12)
            self.icon('star',(round(winner.x),round(self.grounds[winner.index]-102)),GOLD,21)
        else:
            self.badge(self.players[0],(545,222),29)
            self.icon('equals',(640,222),GOLD,22)
            self.badge(self.players[1],(735,222),29)
        if self.mode=='money':
            for p,x in zip(self.players,(510,770)):
                self.badge(p,(x-65,280),16)
                self.icon('coin',(x-27,280),GOLD,12)
                self.text(f'+{self.payout[p.index]}',x-7,269,27,GOLD)
        elif winner:
            for k in range(min(7,winner.wins)):
                self.icon('star',(640+round((k-(min(7,winner.wins)-1)/2)*30),280),GOLD,11)
        self.button((425,315,100,62),'','menu')
        self.icon('home',(475,346),WHITE,21)
        self.button((555,315,300,62),'','next',tint=GO_FILL,pulse=True)
        self.icon('replay',(675,346),WHITE,21)
        self.icon('play',(745,346),GOLD,18)

    def draw_pause(self):
        self.buttons=[]
        self.clip_texts((340,230,600,340))
        self.box((340,230,600,340),BG)
        pygame.draw.rect(self.canvas,(65,86,102),(340,230,600,340),3,border_radius=16)
        self.icon('pause',(640,272),MUTED,20)
        for x,a,ic,col,tint in [(380,'resume','play',WHITE,GO_FILL),(560,'menu','menu',WHITE,None),(740,'exit','home',WHITE,None)]:
            self.button((x,310,160,160),'',a,tint=tint,pulse=(a=='resume'))
            self.icon(ic,(x+80,390),col,40)
        self.text('Resume',460,500,24,MUTED,True)
        self.text('Menu',640,500,24,MUTED,True)
        self.text('Home',820,500,24,MUTED,True)

    def draw(self):
        self.buttons=[]
        self.texts=[]
        self.canvas.fill(BG)
        if self.state=='menu': self.draw_menu()
        elif self.state=='build': self.draw_build()
        else:
            self.draw_field()
            if self.state=='handoff': self.draw_handoff()
            elif self.state=='result': self.draw_result()
        if self.paused: self.draw_pause()
        return self.canvas


def draw_rotate_hint(screen):
    sw,sh=screen.get_size()
    u=max(16,min(sw,sh)//10)
    cx,cy=sw//2,sh//2
    pygame.draw.rect(screen,WHITE,(cx-u*3-u//2,cy-u,u,u*2),4,border_radius=8)
    pygame.draw.polygon(screen,GOLD,[(cx-u//2,cy-u//2),(cx+u//2,cy),(cx-u//2,cy+u//2)])
    pygame.draw.rect(screen,WHITE,(cx+u*2-u//2,cy-u//2,u*2,u),4,border_radius=8)


async def run(screen=None,clock=None):
    """GameHub entry point. Returns without quitting pygame or the hub."""
    pygame.init()
    if screen is None:
        screen=pygame.display.set_mode((W,H),pygame.RESIZABLE)
    game=Game()
    if clock is None: clock=pygame.time.Clock()
    while game.running:
        dt=min(clock.tick(60)/1000,.05)
        sw,sh=screen.get_size()
        if sw<=0 or sh<=0:
            await asyncio.sleep(0)
            continue
        scale=min(sw/W,sh/H)
        vw,vh=max(1,round(W*scale)),max(1,round(H*scale))
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
                game.draw()  # Refresh targets if this press changed the screen.
            elif not portrait and e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and not getattr(e,'touch',False):
                game.press('mouse',((e.pos[0]-ox)/scale,(e.pos[1]-oy)/scale))
                game.draw()
            elif not portrait and e.type==pygame.FINGERMOTION:
                game.drag(e.finger_id,((e.x*sw-ox)/scale,(e.y*sh-oy)/scale))
            elif not portrait and e.type==pygame.MOUSEMOTION and e.buttons[0] and not getattr(e,'touch',False):
                game.drag('mouse',((e.pos[0]-ox)/scale,(e.pos[1]-oy)/scale))
            elif e.type==pygame.KEYDOWN and not portrait and not game.paused and game.state=='battle':
                keys={pygame.K_LEFT:'left',pygame.K_RIGHT:'right',pygame.K_UP:'up',pygame.K_DOWN:'down'}
                if e.key in keys:
                    game.holds[e.key]=keys[e.key]
                    if keys[e.key] in ('up','down'): game.aim_hint=False
                elif e.key==pygame.K_SPACE: game.charge('space')
            elif e.type==pygame.KEYUP: game.release('space' if e.key==pygame.K_SPACE else e.key)
        if portrait: game.cancel_input()
        else: game.update(dt)
        screen.fill(BG)
        screen.blit(pygame.transform.smoothscale(game.draw(),(vw,vh)),(ox,oy))
        if not portrait: game.blit_text(screen,scale,ox,oy)
        else:
            screen.fill(BG)
            draw_rotate_hint(screen)
        pygame.display.flip()
        await asyncio.sleep(0)
    return None


async def main(screen=None,clock=None):
    await run(screen,clock)


if __name__=='__main__':
    asyncio.run(main())
