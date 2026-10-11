# -*- coding: utf-8 -*-
"""WasteCar — a gentle top-down waste-collection driving game.

Drop-in GameHub entry point: await wasteCar.main(screen, clock)
Pygame / Pygbag compatible. No new Python dependencies.

Touch: hold a finger to drive directly toward it; release to brake.
Desktop: hold left mouse button. WASD/arrows drive, Space brakes.
"""
import asyncio
import bisect
import json
import math
import os
import random

import pygame

FPS = 60
MAP_SCALE = 2.0  # Original artwork is 2064x1456; physics uses 2x map coordinates.
TRUCK_MAX_SPEED = 450.0
TRUCK_ACCEL = 415.0
TRUCK_BRAKE = 570.0
CAR_RADIUS = 41.0
TRUCK_RADIUS = 51.0
PICKUP_RADIUS = 142.0
PURPLE = (195, 91, 252)
WHITE = (250, 248, 238)
DARK = (20, 39, 53)
BASE = os.path.dirname(os.path.abspath(__file__))
ASSET_ROOT = os.path.join(BASE, 'assets')


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def lerp(a, b, t):
    return a + (b-a)*t


def approach(a, b, step):
    if a < b:
        return min(a+step, b)
    return max(a-step, b)


def load_asset(name, alpha=True):
    # Try paths both relative to the GameHub module and to Pygbag's cwd.
    candidates = (
        os.path.join(ASSET_ROOT, name),
        os.path.join('assets', name),
        os.path.join('WasteGame', 'assets', name),
    )
    for path in candidates:
        try:
            image = pygame.image.load(path)
            return image.convert_alpha() if alpha else image.convert()
        except (OSError, pygame.error):
            continue
    return None


def map_json():
    for path in (
        os.path.join(ASSET_ROOT, 'wasteCar', 'mapdata.json'),
        os.path.join('assets', 'wasteCar', 'mapdata.json'),
        os.path.join('WasteGame', 'assets', 'wasteCar', 'mapdata.json'),
    ):
        try:
            with open(path, 'r', encoding='utf-8') as stream:
                return json.load(stream)
        except (OSError, ValueError):
            continue
    raise FileNotFoundError('Missing assets/wasteCar/mapdata.json')


class TrafficMap:
    """A pre-extracted graph of the real pink traffic lanes in road_driveable - NPC.png.

    The JSON is generated at build time. No skimage/cv2 is used in the game.
    """
    def __init__(self, data):
        self.edges = []
        self.connections = {}
        for i, entry in enumerate(data['edges']):
            points = [tuple(map(float, p)) for p in entry['points']]
            lengths = [0.0]
            for a, b in zip(points, points[1:]):
                lengths.append(lengths[-1]+distance(a,b))
            if lengths[-1] < 2:
                continue
            edge = {'a':int(entry['a']), 'b':int(entry['b']),
                    'points':points, 'cum':lengths, 'length':lengths[-1]}
            eid = len(self.edges)
            self.edges.append(edge)
            self.connections.setdefault(edge['a'], []).append(eid)
            self.connections.setdefault(edge['b'], []).append(eid)
        if not self.edges:
            raise ValueError('Traffic route graph is empty')

    def sample(self, edge_id, progress, direction=1):
        edge = self.edges[edge_id]
        progress = clamp(progress, 0.0, edge['length'])
        j = min(len(edge['points'])-2, bisect.bisect_right(edge['cum'],progress)-1)
        a, b = edge['points'][j:j+2]
        span = max(0.0001, edge['cum'][j+1]-edge['cum'][j])
        t = clamp((progress-edge['cum'][j])/span,0.0,1.0)
        x,y = lerp(a[0],b[0],t), lerp(a[1],b[1],t)
        heading = math.atan2((b[1]-a[1])*direction,(b[0]-a[0])*direction)
        return x,y,heading

    def continuation(self, node, last_edge, incoming_angle, rng):
        choices = self.connections.get(node,[])
        allowed = [eid for eid in choices if eid != last_edge]
        if not allowed:
            return last_edge, 1 if self.edges[last_edge]['a']==node else -1
        # Prefer roughly straight-on travel but sometimes turn at a junction.
        weighted=[]
        for eid in allowed:
            edge = self.edges[eid]
            direction = 1 if edge['a']==node else -1
            progress = 0.0 if direction==1 else edge['length']
            _,_,heading = self.sample(eid,progress+direction*min(12.0,edge['length']*.6),direction)
            dot = math.cos(heading-incoming_angle)
            weighted.append((eid,direction,0.5 + 3.2*max(0.0,dot)**2))
        total=sum(w for _,_,w in weighted)
        pick=rng.uniform(0,total)
        for eid,direction,weight in weighted:
            pick-=weight
            if pick<=0:
                return eid,direction
        return weighted[-1][:2]


class TrafficCar:
    def __init__(self, network, rng, sprite, edge_id, distance_along, direction=1):
        self.network=network
        self.rng=rng
        self.original=sprite
        self.edge_id=edge_id
        self.progress=distance_along
        self.direction=direction
        self.top_speed=rng.uniform(104,164)
        self.speed=self.top_speed
        self.stun=0.0
        self.impact_wobble=0.0
        self.x,self.y,self.heading=network.sample(edge_id,distance_along,direction)

    def update(self, dt):
        if self.stun>0:
            self.stun=max(0,self.stun-dt)
        target=self.top_speed*(0.22 if self.stun else 1.0)
        self.speed=approach(self.speed,target,160*dt)
        remaining=self.speed*dt
        for _ in range(6):
            if remaining<=0.001:
                break
            edge=self.network.edges[self.edge_id]
            available=(edge['length']-self.progress) if self.direction==1 else self.progress
            travelled=min(remaining,max(0,available))
            self.progress+=travelled*self.direction
            remaining-=travelled
            if available-travelled<=0.001:
                node=edge['b'] if self.direction==1 else edge['a']
                x,y,incoming=self.network.sample(self.edge_id,self.progress,self.direction)
                self.edge_id,self.direction=self.network.continuation(
                    node,self.edge_id,incoming,self.rng)
                edge=self.network.edges[self.edge_id]
                self.progress=0.0 if self.direction==1 else edge['length']
        self.x,self.y,self.heading=self.network.sample(self.edge_id,self.progress,self.direction)
        self.impact_wobble=max(0.0,self.impact_wobble-dt*5)


class WasteCarGame:
    def __init__(self, screen):
        self.screen=screen
        self.w,self.h=screen.get_size()
        self.rng=random.Random()
        self.map=load_asset('road.png',alpha=False)
        self.road_mask=load_asset('road_driveable - NPC.png',alpha=False)
        if self.map is None or self.road_mask is None:
            raise FileNotFoundError('WasteCar requires assets/road.png and road_driveable - NPC.png')
        self.world_w=self.map.get_width()*MAP_SCALE
        self.world_h=self.map.get_height()*MAP_SCALE
        data=map_json()
        self.traffic_map=TrafficMap(data['traffic'])
        self.bin_positions=[tuple((float(x),float(y))) for x,y in data['bins']]
        self.truck_sprite=load_asset('truck.png')
        self.car_sprites=[load_asset('car%d.png'%i) for i in (1,2,3)]
        self.bin_full=load_asset('wasteBin_full.png')
        self.bin_empty=load_asset('wasteBin_empty.png')
        self.home_sprite=load_asset('retBut.png')
        self.font=pygame.font.Font(None,28)
        self.font_med=pygame.font.Font(None,40)
        self.font_big=pygame.font.Font(None,64)
        self.font_huge=pygame.font.Font(None,86)
        self.menu_road=pygame.transform.scale(self.map,(self.w,self.h))
        self.buttons={}
        self.sprite_cache={}
        self.running=True
        self.phase='menu'
        self.pointer=None
        self.pointer_id=None
        self.mouse_held=False
        self.key_heading=None
        self.best_time=None
        self.spawn_timer=0
        self.sparkles=[]
        self.confetti=[]
        self.shake=0.0
        self.shake_offset=(0.0,0.0)
        self.impact_text=0.0
        self.elapsed=0.0
        self.reset()
        self.phase='menu'

    def reset(self):
        self.x=1110*MAP_SCALE
        self.y=750*MAP_SCALE
        self.vx=0.0
        self.vy=0.0
        self.heading=0.0
        self.zoom=0.97
        self.camx,self.camy=self.x,self.y
        self.pointer=None
        self.pointer_id=None
        self.mouse_held=False
        self.elapsed=0.0
        self.bins=[{'pos':p,'full':True,'glow':0.0} for p in self.bin_positions]
        self.collected=0
        self.sparkles=[]
        self.confetti=[]
        self.shake=0.0
        self.shake_offset=(0.0,0.0)
        self.impact_text=0.0
        self.cars=[]
        for _ in range(10):
            for attempt in range(70):
                eid=self.rng.randrange(len(self.traffic_map.edges))
                e=self.traffic_map.edges[eid]
                along=self.rng.uniform(0,e['length'])
                direction=self.rng.choice((-1,1))
                x,y,_=self.traffic_map.sample(eid,along,direction)
                if distance((x,y),(self.x,self.y))<240:
                    continue
                if any(distance((x,y),(c.x,c.y))<155 for c in self.cars):
                    continue
                sprite=self.rng.choice([s for s in self.car_sprites if s is not None] or [None])
                car=TrafficCar(self.traffic_map,self.rng,sprite,eid,along,direction)
                car.sprite_key=('car%d'%(self.car_sprites.index(sprite)+1)) if sprite is not None else 'car_fallback'
                self.cars.append(car)
                break
        self.phase='playing'

    def world_to_screen(self,x,y):
        jitter=getattr(self,'shake_offset',(0.0,0.0))
        return ((x-self.camx)*self.zoom+self.w/2+jitter[0],
                (y-self.camy)*self.zoom+self.h/2+jitter[1])

    def screen_to_world(self,x,y):
        return ((x-self.w/2)/self.zoom+self.camx,
                (y-self.h/2)/self.zoom+self.camy)

    def nearest_bin(self):
        active=[b for b in self.bins if b['full']]
        return min(active,key=lambda b:distance(b['pos'],(self.x,self.y))) if active else None

    def is_road(self,x,y):
        sx,sy=int(x/MAP_SCALE),int(y/MAP_SCALE)
        if not (0<=sx<self.road_mask.get_width() and 0<=sy<self.road_mask.get_height()):
            return False
        r,g,b=self.road_mask.get_at((sx,sy))[:3]
        return min(r,g,b)>=236 or (r>=240 and b>=215 and b-g>=18)

    def emit(self,x,y,count,colors,velocity=110.0,lifetime=0.65):
        for _ in range(count):
            a=self.rng.uniform(0,math.tau)
            s=self.rng.uniform(.35,1.0)*velocity
            self.sparkles.append([x,y,math.cos(a)*s,math.sin(a)*s,
                                  self.rng.uniform(.45,lifetime),self.rng.choice(colors)])
        if len(self.sparkles)>240:
            del self.sparkles[:-240]

    def collection(self,bin_entry):
        bin_entry['full']=False
        bin_entry['glow']=1.15
        self.collected+=1
        x,y=bin_entry['pos']
        self.emit(x,y,24,((255,222,72),(79,227,141),(196,84,255),(255,129,92)),180,0.9)
        if self.collected==len(self.bins):
            self.phase='finished'
            self.pointer=None
            if self.best_time is None or self.elapsed<self.best_time:
                self.best_time=self.elapsed
            self.confetti=[[self.rng.randrange(self.w),self.rng.uniform(-self.h,0),
                           self.rng.uniform(55,160),self.rng.choice(((255,189,55),(122,233,171),
                             (203,101,252),(255,120,133),(91,183,252))),
                           self.rng.uniform(3,9)] for _ in range(100)]

    def update_truck(self,dt):
        accelerating=False
        if self.pointer is not None:
            sx,sy=self.world_to_screen(self.x,self.y)
            dx=self.pointer[0]-sx
            dy=self.pointer[1]-sy
            if math.hypot(dx,dy)>27:
                # Instant direction: no steering lag, suitable for a four-year-old.
                self.heading=math.atan2(dy,dx)
                accelerating=True
        else:
            keys=pygame.key.get_pressed()
            dx=float(bool(keys[pygame.K_d] or keys[pygame.K_RIGHT]))-float(bool(keys[pygame.K_a] or keys[pygame.K_LEFT]))
            dy=float(bool(keys[pygame.K_s] or keys[pygame.K_DOWN]))-float(bool(keys[pygame.K_w] or keys[pygame.K_UP]))
            if dx or dy:
                self.heading=math.atan2(dy,dx)
                accelerating=True
            if keys[pygame.K_SPACE]:
                accelerating=False
        vx_target=TRUCK_MAX_SPEED*math.cos(self.heading) if accelerating else 0.0
        vy_target=TRUCK_MAX_SPEED*math.sin(self.heading) if accelerating else 0.0
        # Heading changes instantly. Velocity retains some inertia when turning.
        response=TRUCK_ACCEL if accelerating else TRUCK_BRAKE
        delta_x=vx_target-self.vx
        delta_y=vy_target-self.vy
        mag=math.hypot(delta_x,delta_y)
        if mag>0:
            change=min(response*dt,mag)
            self.vx+=delta_x/mag*change
            self.vy+=delta_y/mag*change
        speed=math.hypot(self.vx,self.vy)
        if speed>TRUCK_MAX_SPEED:
            k=TRUCK_MAX_SPEED/speed
            self.vx*=k;self.vy*=k
        # Swept movement to avoid clipping through scenery at high speed.
        parts=max(1,math.ceil(speed*dt/12.0))
        step=dt/parts
        for _ in range(parts):
            xx=clamp(self.x+self.vx*step,25,self.world_w-25)
            yy=clamp(self.y+self.vy*step,25,self.world_h-25)
            if self.is_road(xx,yy):
                self.x,self.y=xx,yy
            elif self.is_road(xx,self.y):
                self.x=xx;self.vy*=.45
            elif self.is_road(self.x,yy):
                self.y=yy;self.vx*=.45
            else:
                self.vx*=-.13
                self.vy*=-.13
                break

    def resolve_collisions(self):
        for car in self.cars:
            d=distance((self.x,self.y),(car.x,car.y))
            if d>TRUCK_RADIUS+CAR_RADIUS or car.stun>0.28:
                continue
            nx=(self.x-car.x)/max(0.001,d)
            ny=(self.y-car.y)/max(0.001,d)
            other_vx=math.cos(car.heading)*car.speed
            other_vy=math.sin(car.heading)*car.speed
            relative=math.hypot(self.vx-other_vx,self.vy-other_vy)
            if relative<45:
                continue
            # Impulse and separation: the heavy truck retains some movement;
            # traffic slows but remains glued to its actual lane path.
            overlap=TRUCK_RADIUS+CAR_RADIUS-d
            self.x=clamp(self.x+nx*(overlap+2),25,self.world_w-25)
            self.y=clamp(self.y+ny*(overlap+2),25,self.world_h-25)
            old_vx,old_vy=self.vx,self.vy
            inward=min(0.0,self.vx*nx+self.vy*ny)
            self.vx=(self.vx-1.35*inward*nx)*0.65
            self.vy=(self.vy-1.35*inward*ny)*0.65
            car.stun=0.8
            car.impact_wobble=1.0
            self.shake=min(13,self.shake+relative/35)
            self.impact_text=0.6
            impact_x=(self.x+car.x)/2;impact_y=(self.y+car.y)/2
            self.emit(impact_x,impact_y,13,((255,229,95),(255,143,63),(238,245,242)),220,.46)
            # Avoid becoming embedded in a wall after the separation impulse.
            if not self.is_road(self.x,self.y):
                self.x-=nx*(overlap+2)
                self.y-=ny*(overlap+2)
                self.vx=old_vx*.25;self.vy=old_vy*.25

    def update_camera(self,dt):
        speed=math.hypot(self.vx,self.vy)
        fraction=clamp(speed/TRUCK_MAX_SPEED,0.0,1.0)
        target_zoom=lerp(1.08,0.63,fraction)
        self.zoom=lerp(self.zoom,target_zoom,1-math.exp(-2.6*dt))
        lead=lerp(5,210,fraction)
        heading=math.atan2(self.vy,self.vx) if speed>14 else self.heading
        aimx=self.x+math.cos(heading)*lead
        aimy=self.y+math.sin(heading)*lead
        smoothing=1-math.exp(-4.1*dt)
        self.camx=lerp(self.camx,aimx,smoothing)
        self.camy=lerp(self.camy,aimy,smoothing)
        halfw=self.w/(2*self.zoom);halfh=self.h/(2*self.zoom)
        self.camx=clamp(self.camx,halfw,self.world_w-halfw)
        self.camy=clamp(self.camy,halfh,self.world_h-halfh)

    def update(self,dt):
        if self.phase=='playing':
            self.elapsed+=dt
            self.update_truck(min(dt,1.0/30.0))
            for car in self.cars:
                car.update(min(dt,1.0/30.0))
            self.resolve_collisions()
            for b in self.bins:
                if b['full'] and distance(b['pos'],(self.x,self.y))<=PICKUP_RADIUS:
                    self.collection(b)
                    if self.phase=='finished':
                        break
        if self.phase in ('playing','finished'):
            self.update_camera(min(dt,1.0/30.0))
            self.shake=max(0.0,self.shake-dt*18)
            self.impact_text=max(0.0,self.impact_text-dt)
            for b in self.bins:
                b['glow']=max(0,b['glow']-dt)
            for particle in self.sparkles:
                particle[0]+=particle[2]*dt
                particle[1]+=particle[3]*dt
                particle[3]+=80*dt
                particle[4]-=dt
            self.sparkles=[p for p in self.sparkles if p[4]>0]
            if self.phase=='finished':
                for p in self.confetti:
                    p[1]+=p[2]*dt
                    if p[1]>self.h+12:
                        p[1]=-15
                        p[0]=self.rng.randrange(self.w)

    def button(self,key,text,rect,bg,fg=WHITE):
        self.buttons[key]=pygame.Rect(rect)
        pygame.draw.rect(self.screen,(19,42,50),pygame.Rect(rect).move(0,4),border_radius=13)
        pygame.draw.rect(self.screen,bg,rect,border_radius=13)
        pygame.draw.rect(self.screen,(248,244,219),rect,2,border_radius=13)
        label=self.font.render(text,True,fg)
        self.screen.blit(label,label.get_rect(center=pygame.Rect(rect).center))

    def label(self,text,center,font=None,color=WHITE):
        image=(font or self.font).render(text,True,color)
        self.screen.blit(image,image.get_rect(center=center))

    def draw_menu(self):
        self.screen.blit(self.menu_road,(0,0))
        veil=pygame.Surface((self.w,self.h),pygame.SRCALPHA)
        veil.fill((12,28,49,167))
        self.screen.blit(veil,(0,0))
        box=pygame.Rect(self.w//2-250,self.h//2-200,500,410)
        pygame.draw.rect(self.screen,(29,73,83),box,border_radius=22)
        pygame.draw.rect(self.screen,(244,235,175),box,4,border_radius=22)
        self.label('WASTE CAR', (self.w//2,box.y+61),self.font_huge,(255,221,79))
        self.label('Drive the truck. Collect every bin!',(self.w//2,box.y+128),self.font,(242,247,234))
        self.label('Touch and hold to drive toward your finger.',(self.w//2,box.y+170),self.font,(228,237,232))
        self.label('Follow the purple arrow!',(self.w//2,box.y+204),self.font,(217,151,255))
        self.buttons={}
        self.button('start','START DRIVING', (self.w//2-140,box.y+262,280,63),(62,163,110))
        self.button('home','HOME', (self.w//2-85,box.y+341,170,49),(202,108,65))

    def draw_road(self):
        # Only crop a small source area, then scale to the screen. Never resize
        # the full 2064x1456 map per frame (important for Pygbag/mobile).
        left=self.camx-self.w/(2*self.zoom)
        top=self.camy-self.h/(2*self.zoom)
        x0=max(0,int(math.floor(left/MAP_SCALE))-2)
        y0=max(0,int(math.floor(top/MAP_SCALE))-2)
        x1=min(self.map.get_width(),int(math.ceil((left+self.w/self.zoom)/MAP_SCALE))+2)
        y1=min(self.map.get_height(),int(math.ceil((top+self.h/self.zoom)/MAP_SCALE))+2)
        self.screen.fill((50,92,78))
        if x1<=x0 or y1<=y0:
            return
        src=pygame.Rect(x0,y0,x1-x0,y1-y0)
        scale=self.zoom*MAP_SCALE
        dw=max(1,round(src.width*scale))
        dh=max(1,round(src.height*scale))
        piece=self.map.subsurface(src)
        img=pygame.transform.scale(piece,(dw,dh))
        sx=round((x0*MAP_SCALE-left)*self.zoom+self.shake_offset[0])
        sy=round((y0*MAP_SCALE-top)*self.zoom+self.shake_offset[1])
        self.screen.blit(img,(sx,sy))

    def draw_vehicle(self,image,x,y,heading,size,name,shadow=True,wobble=0):
        sx,sy=self.world_to_screen(x,y)
        if sx<-140 or sx>self.w+140 or sy<-140 or sy>self.h+140:
            return
        if image is None:
            w=int(size[0]*self.zoom)
            h=int(size[1]*self.zoom)
            rect=pygame.Rect(0,0,max(15,w),max(10,h))
            rect.center=(round(sx),round(sy))
            pygame.draw.ellipse(self.screen,(229,83,66),rect)
            return
        if shadow:
            pygame.draw.ellipse(self.screen,(22,35,44,105),
                                (sx-size[0]*self.zoom*.33+6,sy+size[1]*self.zoom*.17,
                                 size[0]*self.zoom*.70,size[1]*self.zoom*.32))
        rotation=int(round((-math.degrees(heading)+wobble*5)/5))*5
        quantzoom=round(self.zoom/0.05)*0.05
        cache=(name,rotation,round(quantzoom,2))
        pic=self.sprite_cache.get(cache)
        if pic is None:
            srcw,srch=image.get_size()
            base_scale=min(size[0]/srcw,size[1]/srch)
            pic=pygame.transform.rotozoom(image,rotation,base_scale*quantzoom)
            if len(self.sprite_cache)>=500:
                self.sprite_cache.clear()
            self.sprite_cache[cache]=pic
        rect=pic.get_rect(center=(int(sx),int(sy)))
        self.screen.blit(pic,rect)

    def draw_bin(self,b):
        sx,sy=self.world_to_screen(*b['pos'])
        if not (-50<sx<self.w+50 and -60<sy<self.h+60):
            return
        image=self.bin_full if b['full'] else self.bin_empty
        if b['full']:
            radius=round(35*self.zoom)
            pygame.draw.circle(self.screen,(243,211,84),(round(sx),round(sy)),max(6,radius),3)
        if image is None:
            pygame.draw.rect(self.screen,(230,192,75),(sx-15,sy-20,30,40),border_radius=5)
            return
        width=max(10,round(image.get_width()*.66*self.zoom))
        height=max(12,round(image.get_height()*.66*self.zoom))
        key=('bin',b['full'],width,height)
        if key not in self.sprite_cache:
            self.sprite_cache[key]=pygame.transform.smoothscale(image,(width,height))
        out=self.sprite_cache[key]
        self.screen.blit(out,out.get_rect(center=(sx,sy)))

    def draw_chevron(self):
        b=self.nearest_bin()
        if b is None:return
        px,py=self.world_to_screen(self.x,self.y)
        bx,by=self.world_to_screen(*b['pos'])
        dx,dy=bx-px,by-py
        angle=math.atan2(dy,dx)
        inside=45<bx<self.w-45 and 96<by<self.h-43
        if inside:
            cx,cy=bx,by-65*self.zoom
            angle=math.pi/2  # point down onto the wastebin
        else:
            # Directional arrow lives at a safe point near the screen edge.
            cx=self.w/2+math.cos(angle)*min(self.w*.38,265)
            cy=self.h/2+math.sin(angle)*min(self.h*.34,192)
            cx=clamp(cx,36,self.w-36)
            cy=clamp(cy,108,self.h-40)
        # Purple V chevron, rotated to point toward its target.
        def rotate(u,v):
            return (round(cx+u*math.cos(angle)-v*math.sin(angle)),
                    round(cy+u*math.sin(angle)+v*math.cos(angle)))
        pts=[rotate(22,0),rotate(-8,-20),rotate(-1,0),rotate(-8,20)]
        pygame.draw.polygon(self.screen,(67,34,85),pts,0)
        pygame.draw.polygon(self.screen,PURPLE,pts,0)
        pygame.draw.lines(self.screen,(252,222,255),True,pts,3)

    def elapsed_text(self):
        seconds=max(0,int(self.elapsed))
        return '%02d:%02d'%(seconds//60,seconds%60)

    def draw_hud(self):
        self.buttons={}
        pygame.draw.rect(self.screen,(22,54,65),(0,0,self.w,76),border_radius=0)
        pygame.draw.line(self.screen,(225,217,167),(0,76),(self.w,76),3)
        self.button('home','HOME',(12,11,100,51),(188,104,58))
        self.button('pause','II',(self.w-66,11,53,51),(77,120,161))
        self.label('BINS  %d / %d'%(self.collected,len(self.bins)),(self.w*.36,38),self.font_med,(255,232,98))
        self.label(self.elapsed_text(),(self.w*.74,38),self.font_med,WHITE)
        self.draw_chevron()

    def draw_play(self):
        if self.shake>0:
            self.shake_offset=(self.rng.uniform(-self.shake,self.shake),
                               self.rng.uniform(-self.shake,self.shake))
        else:
            self.shake_offset=(0.0,0.0)
        self.draw_road()
        for b in self.bins:
            self.draw_bin(b)
        for i,car in enumerate(self.cars):
            self.draw_vehicle(car.original,car.x,car.y,car.heading,(110,51),car.sprite_key,wobble=car.impact_wobble)
        self.draw_vehicle(self.truck_sprite,self.x,self.y,self.heading,(172,60),'truck')
        for x,y,vx,vy,life,color in self.sparkles:
            sx,sy=self.world_to_screen(x,y)
            if 0<=sx<self.w and 0<=sy<self.h:
                pygame.draw.circle(self.screen,color,(round(sx),round(sy)),max(2,int(4*life)))
        self.draw_hud()
        if self.impact_text>0 and self.phase=='playing':
            self.label('BUMP!',(self.w//2,114),self.font_med,(255,230,117))

    def draw_overlay(self):
        dark=pygame.Surface((self.w,self.h),pygame.SRCALPHA)
        dark.fill((16,34,54,184))
        self.screen.blit(dark,(0,0))
        card=pygame.Rect(self.w//2-250,self.h//2-171,500,350)
        pygame.draw.rect(self.screen,(34,85,94),card,border_radius=18)
        pygame.draw.rect(self.screen,(251,225,134),card,4,border_radius=18)
        self.buttons={}
        if self.phase=='paused':
            self.label('PAUSED',(self.w//2,card.y+67),self.font_big,(249,216,100))
            self.label('Take your time!',(self.w//2,card.y+125),self.font,WHITE)
            self.button('resume','KEEP DRIVING',(self.w//2-153,card.y+165,306,62),(67,166,103))
            self.button('restart','RESTART',(self.w//2-153,card.y+239,143,54),(91,132,173))
            self.button('home','HOME',(self.w//2+10,card.y+239,143,54),(193,104,65))
        elif self.phase=='finished':
            for x,y,speed,color,size in self.confetti:
                pygame.draw.rect(self.screen,color,(x,y,size,size*1.45))
            self.label('ALL BINS COLLECTED!',(self.w//2,card.y+64),self.font_med,(255,224,104))
            self.label('Great driving!',(self.w//2,card.y+123),self.font_med,WHITE)
            self.label('Time: '+self.elapsed_text(),(self.w//2,card.y+167),self.font_med,(210,164,255))
            self.button('restart','PLAY AGAIN',(self.w//2-153,card.y+232,306,59),(67,166,103))
            self.button('home','HOME',(self.w//2-93,card.y+302,186,43),(193,104,65))

    def handle_click(self,p):
        for name,r in self.buttons.items():
            if r.collidepoint(p):
                if name=='home':
                    self.running=False
                elif name=='start' or name=='restart':
                    self.reset()
                elif name=='pause':
                    self.phase='paused';self.pointer=None
                elif name=='resume':
                    self.phase='playing';self.pointer=None
                return True
        return False

    def handle_event(self,event):
        if event.type==pygame.QUIT:
            self.running=False
        elif event.type==pygame.KEYDOWN:
            if event.key==pygame.K_ESCAPE:
                if self.phase=='playing':self.phase='paused';self.pointer=None
                elif self.phase=='paused':self.phase='playing'
                else:self.running=False
            elif event.key in (pygame.K_RETURN,pygame.K_KP_ENTER):
                if self.phase in ('menu','finished'):self.reset()
                elif self.phase=='paused':self.phase='playing'
            elif event.key==pygame.K_r and self.phase=='playing':
                self.reset()
        elif event.type==pygame.FINGERDOWN:
            p=(event.x*self.w,event.y*self.h)
            if self.handle_click(p):return
            if self.phase=='playing' and self.pointer_id is None and p[1]>78:
                self.pointer_id=event.finger_id
                self.pointer=p
        elif event.type==pygame.FINGERMOTION:
            if self.pointer_id==event.finger_id and self.phase=='playing':
                self.pointer=(event.x*self.w,event.y*self.h)
        elif event.type==pygame.FINGERUP:
            if self.pointer_id==event.finger_id:
                self.pointer=None;self.pointer_id=None
        elif event.type==pygame.MOUSEBUTTONDOWN and getattr(event,'button',0)==1:
            if getattr(event,'touch',False) or getattr(event,'which',None)==getattr(pygame,'TOUCH_MOUSEID',-1):
                return
            if self.handle_click(event.pos):return
            if self.phase=='playing' and self.pointer_id is None and event.pos[1]>78:
                self.mouse_held=True
                self.pointer=event.pos
        elif event.type==pygame.MOUSEMOTION:
            if self.mouse_held and self.phase=='playing':
                self.pointer=event.pos
        elif event.type==pygame.MOUSEBUTTONUP and getattr(event,'button',0)==1:
            if getattr(event,'touch',False) or getattr(event,'which',None)==getattr(pygame,'TOUCH_MOUSEID',-1):
                return
            if self.mouse_held:
                self.mouse_held=False
                self.pointer=None

    def draw(self):
        if self.phase=='menu':
            self.draw_menu()
        else:
            self.draw_play()
            if self.phase in ('paused','finished'):
                self.draw_overlay()
        pygame.display.flip()


async def main(screen=None,clock=None):
    """Called by GameHub; do not quit Pygame when returning to its menu."""
    if screen is None:
        pygame.init()
        screen=pygame.display.set_mode((800,600))
    if clock is None:
        clock=pygame.time.Clock()
    game=WasteCarGame(screen)
    while game.running:
        raw_dt=clock.tick(FPS)/1000.0
        for event in pygame.event.get():
            game.handle_event(event)
        if not game.running:
            break
        game.update(raw_dt)
        game.draw()
        await asyncio.sleep(0)


if __name__=='__main__':
    asyncio.run(main())
