"""WasteKart 1.1 - draw-to-race with Single Race, Cup and best-lap ghost.

Pygame-ce / Pygbag compatible GameHub entry point:
    await wasteKart.main(screen, clock)

Original four-cup, sixteen-course art resides in assets/WasteKart.
Races use 16 original tracks. Reflex, items and kart collisions are future additions.
"""
import asyncio
import bisect
import json
import math
import os
import random

import pygame

FPS = 60
LOGICAL_W, LOGICAL_H = 800, 600
MAP_W, MAP_H = 960, 600
TRACK_RECT = pygame.Rect(30, 79, 740, 462)  # Exactly 960:600 aspect ratio.
ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET_ROOT = os.path.join(ROOT, 'assets', 'WasteKart')
PALETTE = [(241, 81, 100), (75, 157, 237), (84, 200, 122), (255, 191, 67),
           (175, 128, 238), (252, 143, 83), (84, 218, 213), (246, 128, 187)]
INK = (23, 29, 49)
WHITE = (253, 253, 247)
MUTED = (182, 199, 213)
YELLOW = (255, 209, 92)
FONT_SCALE = 1.0
CUP_POINTS = (9, 6, 3, 1)
DRAW_TIMES = (15, 30, 60, None)  # None means unlimited.
ROAD_FACTOR = 1.0
GRASS_FACTOR = 0.55


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def length(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def lerp(a, b, t):
    return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)


def angle_delta(a, b):
    return (b-a+math.pi) % (2*math.pi)-math.pi


def catmull_rom(points, step=6.0):
    """Sample a child-drawn polyline into a smooth path, preserving its endpoints."""
    controls = []
    for point in points:
        p = (float(point[0]), float(point[1]))
        if not controls or length(p, controls[-1]) > 5.0:
            controls.append(p)
    if len(controls) < 2:
        return controls
    # Limit expensive spline interpolation even if a browser provides many events.
    if len(controls) > 420:
        stride = math.ceil(len(controls) / 420)
        controls = controls[::stride] + ([controls[-1]] if controls[-1] != controls[::stride][-1] else [])
    dense = [controls[0]]
    for i in range(len(controls)-1):
        a = controls[max(0, i-1)]
        b = controls[i]
        c = controls[i+1]
        d = controls[min(len(controls)-1, i+2)]
        subdivisions = max(2, math.ceil(length(b, c)/4))
        for j in range(1, subdivisions+1):
            t = j/subdivisions
            t2, t3 = t*t, t*t*t
            x = .5*(2*b[0]+(-a[0]+c[0])*t+(2*a[0]-5*b[0]+4*c[0]-d[0])*t2+(-a[0]+3*b[0]-3*c[0]+d[0])*t3)
            y = .5*(2*b[1]+(-a[1]+c[1])*t+(2*a[1]-5*b[1]+4*c[1]-d[1])*t2+(-a[1]+3*b[1]-3*c[1]+d[1])*t3)
            dense.append((clamp(x, 5, MAP_W-5), clamp(y, 5, MAP_H-5)))
    result = [controls[0]]
    remain = float(step)
    for a, b in zip(dense, dense[1:]):
        span = length(a, b)
        if span < .0001:
            continue
        while remain <= span + 1e-6:
            a2 = lerp(a, b, remain/span)
            result.append(a2)
            a = a2
            span -= remain
            remain = step
            if span <= 1e-5:
                break
        remain -= span
        if remain <= 1e-5:
            remain = step
    if length(result[-1], controls[-1]) > .5:
        result.append(controls[-1])
    else:
        result[-1] = controls[-1]
    if len(result) == 1:
        result.append(controls[-1])
    return result


def complete_drawn_loop(raw, centerline):
    """Smooth a child-drawn route; connect its endpoint DIRECTLY to the flag.

    Deliberately do not auto-complete along the centerline: crossing grass is
    meant to be slower, not secretly corrected to the ideal racing route.
    The trailing straight is added AFTER spline smoothing, so Catmull-Rom does
    not curve it into an unintended shortcut.
    """
    start = tuple(centerline[0])
    points = [start]
    for p in raw[1:] if raw else ():
        p = (clamp(float(p[0]), 5.0, MAP_W-5.0),
             clamp(float(p[1]), 5.0, MAP_H-5.0))
        if length(p, points[-1]) >= 5.0:
            points.append(p)
    if len(points) > 500:
        stride = math.ceil(len(points)/500)
        points = points[::stride] + [points[-1]]
    drawn_length = sum(length(a,b) for a,b in zip(points,points[1:]))
    center_length = sum(length(a,b) for a,b in zip(centerline,centerline[1:]+centerline[:1]))
    # The earliest legitimate return to the checkered line finishes the lap.
    if drawn_length > center_length*.65:
        walked = 0.0
        for i in range(1,len(points)):
            walked += length(points[i-1],points[i])
            if walked > center_length*.65 and length(points[i],start) < 38:
                points = points[:i+1]
                break
    # With no real stroke, add a slow, short fallback tour so the one-lap race
    # cannot become a 0-second win. Empty drawings are still allowed to finish.
    if drawn_length < 28.0:
        fallback = (clamp(start[0]+110,10,MAP_W-10),
                    clamp(start[1]+115,10,MAP_H-10))
        points = [start,fallback]
    smoothed = catmull_rom(points,step=6.0)
    if length(smoothed[-1],start) > .5:
        # Equal arc-length samples of a true STRAIGHT finish connection.
        last=smoothed[-1]
        segments=max(1,math.ceil(length(last,start)/6.0))
        smoothed.extend(lerp(last,start,i/segments) for i in range(1,segments+1))
    else:
        smoothed[-1]=start
    return smoothed


class Route:
    """Precompute arc lengths and smoothed circumradius-based bend factors."""
    def __init__(self, points):
        self.points = list(points)
        self.accumulated = [0.0]
        for a,b in zip(self.points,self.points[1:]):
            self.accumulated.append(self.accumulated[-1]+length(a,b))
        self.length = self.accumulated[-1]
        raw=[]
        # Circumradius = abc/(4*triangle area). Sample about 30px on either side
        # and average 5 successive radii to reject finger input jitter.
        for i in range(len(self.points)):
            a=self.points[max(0,i-5)]
            b=self.points[i]
            c=self.points[min(len(self.points)-1,i+5)]
            ab,bc,ac=length(a,b),length(b,c),length(a,c)
            twice_area=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            radius=ab*bc*ac/(2.0*twice_area) if twice_area>1e-4 else 1e6
            raw.append(radius)
        self.curve_factors=[]
        for i in range(len(raw)):
            radius=sum(raw[max(0,i-2):min(len(raw),i+3)])/len(raw[max(0,i-2):min(len(raw),i+3)])
            self.curve_factors.append(.40+.60*min(1.0,radius/180.0))

    def sample(self,distance):
        if not self.points:return ((0.0,0.0),0.0,.4)
        if len(self.points)==1:return (self.points[0],0.0,.4)
        d=clamp(distance,0.0,self.length)
        j=min(len(self.points)-2,max(0,bisect.bisect_right(self.accumulated,d)-1))
        a,b=self.points[j],self.points[j+1]
        t=(d-self.accumulated[j])/max(1e-6,self.accumulated[j+1]-self.accumulated[j])
        angle=math.atan2(b[1]-a[1],b[0]-a[0])
        bend=self.curve_factors[j]*(1-t)+self.curve_factors[j+1]*t
        return lerp(a,b,t),angle,bend

class Track:
    def __init__(self,entry):
        self.entry=entry
        geom_path=os.path.join(ASSET_ROOT,*entry['geometry'].split('/'))
        with open(geom_path,encoding='utf8') as stream:
            data=json.load(stream)
        self.name=data['name']
        self.centerline=[tuple(p) for p in data['centerline']]
        self.road_half_width=float(data['road_half_width'])
        self.max_speed=float(data.get('v_max',235.0))
        self.image_path=os.path.join(ASSET_ROOT,*entry['image'].split('/'))
        self.centerline_route=Route(self.centerline+[self.centerline[0]])
        mask_path=os.path.join(ASSET_ROOT,*entry['road_mask'].split('/'))
        self.mask=pygame.image.load(mask_path).convert()

    def on_road(self,point):
        x,y=int(point[0]),int(point[1])
        if not (0<=x<MAP_W and 0<=y<MAP_H):return False
        # A single O(1) lookup, even with four karts on iPad.
        return self.mask.get_at((x,y))[0] > 127

class Racer:
    def __init__(self,index,kart_id,route,is_ghost=False):
        self.index=index
        self.kart_id=kart_id
        self.route=route
        self.is_ghost=is_ghost
        self.distance=0.0
        self.speed=0.0
        self.start_modifier=1.0  # Future reflex-start input hook.
        self.modifiers=[]       # Future pickups/slipstreaming hook.
        self.finished=False
        self.finish_time=None
        self.pos,self.heading,_=route.sample(0)
        self.on_track=True

    def update(self,dt,elapsed,track):
        if self.finished:return
        pos,heading,bend=self.route.sample(self.distance)
        road=track.on_road(pos)
        desired=track.max_speed*bend*(ROAD_FACTOR if road else GRASS_FACTOR)*self.start_modifier
        for modifier in self.modifiers:
            desired*=modifier
        reaction=3.1 if desired>self.speed else 5.2
        self.speed+=(desired-self.speed)*min(1.0,dt*reaction)
        advance=self.speed*dt
        previous=self.distance
        self.distance=min(self.route.length,self.distance+advance)
        self.pos,self.heading,_=self.route.sample(self.distance)
        self.on_track=track.on_road(self.pos)
        if self.distance>=self.route.length-1e-3:
            self.finished=True
            # Subframe finish time avoids a player advantage due to update order.
            fraction=(self.route.length-previous)/max(advance,1e-6)
            self.finish_time=round(elapsed-dt+dt*clamp(fraction,0,1),3)

def browser_touch_mode(enabled):
    """Keep canvas finger drawing from scrolling the web page on iPad."""
    try:
        import js
        if enabled:
            js.eval("""(function(){const c=document.querySelector('canvas');if(!c)return;
                if(c.__wasteKartBackup===undefined)
                  c.__wasteKartBackup=[c.style.touchAction,c.style.overscrollBehavior];
                c.style.touchAction='none';c.style.overscrollBehavior='contain';})()""")
        else:
            js.eval("""(function(){const c=document.querySelector('canvas');
                if(!c||c.__wasteKartBackup===undefined)return;
                c.style.touchAction=c.__wasteKartBackup[0];
                c.style.overscrollBehavior=c.__wasteKartBackup[1];
                delete c.__wasteKartBackup;})()""")
    except Exception:
        pass  # Desktop pygame does not provide the browser's js module.


class WasteKartGame:
    def __init__(self, screen, clock):
        self.screen=screen
        self.clock=clock
        self.canvas=pygame.Surface((LOGICAL_W,LOGICAL_H)).convert()
        self.fonts={size:pygame.font.Font(None,size) for size in (19,22,25,27,30,34,38,44,50,60,72)}
        self.running=True
        self.state='menu'
        self.players=2
        self.race_mode='single'
        self.draw_seconds=60
        self.cup_stage=0
        self.cup_scores=[0,0,0,0]
        self.cup_history=[]
        self.ghost_records={}  # Track index -> {time, points, kart_id}, RAM only.
        self.active_ghost=None
        self.new_best=False
        self.cup=0
        self.track_index=0
        self.kart_ids=[0,1,2,3]
        self.kart_player=0
        self.draw_player=0
        self.draft=[]
        self.draw_pointer=None
        self.time_left=self.draw_seconds
        self.routes=[]
        self.racers=[]
        self.elapsed=0.0
        self.countdown=0.0
        self.paused=False
        self.results_time=0.0
        self.kart_picks=[0,1,2,3]
        self.map_surface=None
        self.track=None
        self.track_cache={}
        self.thumb_cache={}
        self.kart_images=[]
        self.kart_rotation_cache={}
        self.confetti=[]
        self.rng=random.Random()
        self.home_rect=pygame.Rect(9,11,62,49)
        self.action_buttons=[]
        self.catalog=self.load_catalog()
        self.load_karts()

    def load_catalog(self):
        with open(os.path.join(ASSET_ROOT,'catalog.json'),encoding='utf8') as stream:
            return json.load(stream)

    def load_karts(self):
        for entry in self.catalog['karts']:
            path=os.path.join(ASSET_ROOT,*entry['image'].split('/'))
            image=pygame.image.load(path).convert_alpha()
            self.kart_images.append(image)

    def load_track(self):
        index=self.cup*4+self.track_index
        if index not in self.track_cache:
            self.track_cache[index]=Track(self.catalog['tracks'][index])
        self.track=self.track_cache[index]
        img=pygame.image.load(self.track.image_path).convert()
        self.map_surface=pygame.transform.smoothscale(img,TRACK_RECT.size)

    def font(self,size):
        return self.fonts[min(self.fonts,key=lambda k:abs(k-size))]

    def text(self,message,center,size=27,color=WHITE,align='center'):
        img=self.font(size).render(str(message),True,color)
        if align=='left':rect=img.get_rect(midleft=center)
        elif align=='right':rect=img.get_rect(midright=center)
        else:rect=img.get_rect(center=center)
        self.canvas.blit(img,rect)
        return rect

    def button(self,rect,label,value=None,color=(58,79,111),selected=False,disabled=False,size=27):
        r=pygame.Rect(rect)
        base=(54,62,81) if disabled else ((71,146,124) if selected else color)
        pygame.draw.rect(self.canvas,(13,22,38),r.move(0,4),border_radius=13)
        pygame.draw.rect(self.canvas,base,r,border_radius=13)
        pygame.draw.rect(self.canvas,(255,226,144) if selected else ((98,108,123) if disabled else (154,178,210)),r,3,border_radius=13)
        self.text(label,r.center,size,(167,172,183) if disabled else WHITE)
        if value is not None and not disabled:
            self.action_buttons.append((r,value))
        return r

    def panel(self,rect,bg=(33,45,73),border=(103,133,174),radius=18):
        r=pygame.Rect(rect)
        pygame.draw.rect(self.canvas,bg,r,border_radius=radius)
        pygame.draw.rect(self.canvas,border,r,2,border_radius=radius)

    def draw_bg(self):
        self.canvas.fill((25,35,61))
        for i in range(0,LOGICAL_H,30):
            tone=34+(i//30)%2*6
            pygame.draw.rect(self.canvas,(27,tone,69),(0,i,LOGICAL_W,30))
        # playful circuit marks, inexpensive fixed primitives
        for i in range(15):
            x=(i*137+42)%LOGICAL_W
            y=(i*89+19)%LOGICAL_H
            pygame.draw.circle(self.canvas,(52,66,101),(x,y),4+(i%3),2)

    def home(self):
        pygame.draw.rect(self.canvas,(30,48,76),self.home_rect,border_radius=10)
        pygame.draw.rect(self.canvas,(126,158,188),self.home_rect,2,border_radius=10)
        self.text('<',self.home_rect.center,38,WHITE)
        self.action_buttons.append((self.home_rect,('home',None)))

    def title(self,title,subtitle=''):
        self.text(title,(400,43),60,YELLOW)
        if subtitle:
            self.text(subtitle,(400,92),25,MUTED)

    def card_label(self,text,rect,color=WHITE):
        self.text(text,(rect.centerx,rect.bottom-18),27,color)

    def kart_preview(self,kart_id, center, scale=1.0):
        image=self.kart_images[kart_id]
        sz=(max(8,int(101*scale)),max(6,int(73*scale)))
        key=('preview',kart_id,sz)
        if key not in self.kart_rotation_cache:
            self.kart_rotation_cache[key]=pygame.transform.smoothscale(image,sz)
        sprite=self.kart_rotation_cache[key]
        self.canvas.blit(sprite,sprite.get_rect(center=center))

    def track_thumb(self,index,size):
        key=(index,tuple(size))
        if key not in self.thumb_cache:
            entry=self.catalog['tracks'][index]
            path=os.path.join(ASSET_ROOT,*entry['image'].split('/'))
            im=pygame.image.load(path).convert()
            self.thumb_cache[key]=pygame.transform.smoothscale(im,size)
        return self.thumb_cache[key]

    def menu_page(self):
        self.draw_bg()
        self.title('WASTE KART!','Draw a racing line. Race it together!')
        self.panel((42,112,716,119))
        self.text('WHAT SHALL WE RACE?',(400,132),28,YELLOW)
        self.button((81,161,307,54),'SINGLE RACE',('mode','single'),selected=self.race_mode=='single',size=29)
        self.button((411,161,307,54),'4-TRACK CUP',('mode','cup'),selected=self.race_mode=='cup',size=29)
        self.panel((42,244,716,109))
        self.text('HOW MANY RACERS?',(400,264),27,YELLOW)
        for i in range(4):
            self.button((90+i*158,287,145,56),str(i+1),('players',i+1),selected=self.players==i+1,size=39)
        self.panel((42,363,716,123))
        self.text('TIME TO DRAW EACH LINE',(400,383),27,YELLOW)
        for j,(seconds,label) in enumerate(((15,'15 sec'),(30,'30 sec'),(60,'60 sec'),(None,'NO LIMIT'))):
            self.button((60+j*174,406,156,59),label,('time',seconds),selected=self.draw_seconds==seconds,size=25)
        self.button((228,503,344,76),'CHOOSE CUP  >',('state','tracks'),selected=True,size=32)
        self.home()

    def tracks_page(self):
        self.draw_bg()
        self.title('PICK A CUP', 'Single Race: choose a track. Cup: all four tracks!')
        for cup in range(4):
            names=('MEADOW','COAST','DESERT','STAR')
            self.button((29+cup*192,121,169,61),names[cup],('cup',cup),selected=cup==self.cup,size=28)
        for j in range(4):
            x=21+j*195
            area=pygame.Rect(x,214,176,185)
            selected=j==self.track_index and self.race_mode=='single'
            self.panel(area,(66,100,114) if selected else (43,56,81),YELLOW if selected else (89,119,146))
            thumb=self.track_thumb(self.cup*4+j,(164,105))
            self.canvas.blit(thumb,(x+6,220))
            pygame.draw.rect(self.canvas,(253,238,193) if selected else (117,145,162), (x+5,219,166,107),2,border_radius=5)
            name=self.catalog['tracks'][self.cup*4+j]['name']
            # fit long names to 2 lines by using smaller type
            self.text(name,(x+88,359),22,WHITE)
            if selected:self.text('SELECTED',(x+88,384),19,YELLOW)
            elif self.race_mode=='cup':self.text(f'RACE {j+1}',(x+88,384),19,YELLOW)
            if self.race_mode=='single':self.action_buttons.append((area,('track',j)))
        self.text((f'Cup {self.cup+1}  -  Track {self.track_index+1}' if self.race_mode=='single'
                   else f'Cup {self.cup+1}  -  ALL 4 TRACKS'),(400,439),29,WHITE)
        self.button((200,478,400,75),'CHOOSE KARTS  >',('state','karts'),selected=True,size=38)
        self.button((26,540,156,47),'< BACK',('state','menu'),size=25)
        self.home()

    def karts_page(self):
        self.draw_bg()
        current=self.kart_player
        self.title('CHOOSE YOUR KART','Every racer gets a turn to pick a kart!')
        color=PALETTE[self.kart_ids[current]]
        self.text(f'PLAYER {current+1}',(400,129),50,color)
        for k in range(8):
            col=k%4;row=k//4
            r=pygame.Rect(56+col*176,172+row*139,158,121)
            taken=k in self.kart_ids[:current]
            selected=k==self.kart_ids[current]
            self.panel(r,(64,85,115) if selected else (42,52,75),YELLOW if selected else (89,113,151))
            self.kart_preview(k,(r.centerx,r.top+49),.85)
            self.text(self.catalog['karts'][k]['name'],(r.centerx,r.bottom-19),22,(154,160,171) if taken else WHITE)
            if taken:
                pygame.draw.line(self.canvas,(224,109,113),r.topleft,r.bottomright,5)
            else:self.action_buttons.append((r,('kart',k)))
        action='START DRAWING  >' if current==self.players-1 else 'NEXT PLAYER  >'
        self.button((222,472,356,75),action,('kart_next',None),selected=True,size=32)
        self.button((26,540,149,47),'< TRACKS',('state','tracks'),size=24)
        self.home()

    def world_to_screen(self,pos):
        return (TRACK_RECT.left+pos[0]*TRACK_RECT.width/MAP_W,
                TRACK_RECT.top+pos[1]*TRACK_RECT.height/MAP_H)

    def screen_to_world(self,pos):
        return (clamp((pos[0]-TRACK_RECT.left)*MAP_W/TRACK_RECT.width,0,MAP_W),
                clamp((pos[1]-TRACK_RECT.top)*MAP_H/TRACK_RECT.height,0,MAP_H))

    def map_base(self):
        self.canvas.fill((18,30,49))
        if self.map_surface is not None:
            self.canvas.blit(self.map_surface,TRACK_RECT.topleft)
        pygame.draw.rect(self.canvas,(130,151,172),TRACK_RECT,2,border_radius=3)

    def draw_route(self,pts,color,width=4,dashed=False):
        if len(pts)<2:return
        points=[self.world_to_screen(p) for p in pts]
        if dashed:
            # Draw using distance, not vertex index, so dashes remain even when
            # splines have unequal point spacing. Kept cheap by sampling 11px.
            if not points:return
            step=0.0
            for a,b in zip(points,points[1:]):
                span=length(a,b)
                if span < 1e-5:continue
                from_pos=0.0
                while from_pos<span:
                    take=min(span-from_pos,11.0-step%11.0)
                    if int(step//11)%2==0:
                        aa=lerp(a,b,from_pos/span)
                        bb=lerp(a,b,(from_pos+take)/span)
                        pygame.draw.line(self.canvas,color,aa,bb,width)
                    from_pos+=take
                    step+=take
        else:
            pygame.draw.lines(self.canvas,color,False,points,width)
        if not dashed:
            for p in (points[0],points[-1]):
                pygame.draw.circle(self.canvas,color,(round(p[0]),round(p[1])),5)

    def draw_start(self):
        if not self.track:return
        center=self.world_to_screen(self.track.centerline[0])
        pygame.draw.circle(self.canvas,(17,62,49),center,15)
        pygame.draw.circle(self.canvas,(106,255,159),center,12)
        pygame.draw.circle(self.canvas,(254,255,238),center,12,3)
        # Approach arrow near the flag, matching the track's directional tangent.
        first=self.world_to_screen(self.track.centerline[3]);dx=first[0]-center[0];dy=first[1]-center[1]
        mag=math.hypot(dx,dy) or 1
        vx,vy=dx/mag,dy/mag
        a=(center[0]+vx*31,center[1]+vy*31)
        b=(a[0]+vx*22,a[1]+vy*22)
        pygame.draw.line(self.canvas,(103,255,176),a,b,6)
        pygame.draw.polygon(self.canvas,(103,255,176),[(b[0]+vx*13,b[1]+vy*13),
            (b[0]-vy*8-vx*2,b[1]+vx*8-vy*2),(b[0]+vy*8-vx*2,b[1]-vx*8-vy*2)])

    def ready_page(self):
        self.draw_bg()
        self.title('YOUR TURN!',(f'{self.catalog["cups"][self.cup]} - TRACK {self.track_index+1}/4'
                         if self.race_mode=='cup' else f'{self.track.name} - Pass the screen'))
        p=self.draw_player
        self.text(f'PLAYER {p+1}',(400,165),72,PALETTE[self.kart_ids[p]])
        self.kart_preview(self.kart_ids[p],(400,296),2.3)
        self.text('Draw a road around the track!',(400,385),34,WHITE)
        self.text('Start at the green dot. Your finger is the pencil.',(400,424),25,MUTED)
        self.button((220,473,360,79),'READY TO DRAW!',('start_draw',None),selected=True,size=37)
        self.home()

    def draw_page(self):
        self.map_base()
        for idx,route in enumerate(self.routes):
            if route is not None:
                self.draw_route(route.points,PALETTE[self.kart_ids[idx]],3,dashed=True)
        color=PALETTE[self.kart_ids[self.draw_player]]
        if len(self.draft)>1:self.draw_route(self.draft,color,6)
        self.draw_start()
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,72))
        self.text(f'PLAYER {self.draw_player+1} - DRAW!',(285,31),38,color)
        self.text(('\u221e' if self.time_left is None else f'{max(0,math.ceil(self.time_left))}s'),(713,30),44,YELLOW)
        self.text('Draw around the track and back to green!',(380,59),22,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,545,LOGICAL_W,55))
        self.button((25,550,160,43),'CLEAR',('clear',None),size=25)
        self.text('Lift to pause your line. CLEAR to redraw.',(395,571),22,MUTED)
        self.button((624,550,150,43),'DONE >',('draw_done',None),selected=True,size=25)
        self.home()

    def racer_image(self,kart_id,angle):
        quant=(int(round(math.degrees(angle)/6))*6)%360
        key=('race',kart_id,quant)
        if key not in self.kart_rotation_cache:
            img=self.kart_images[kart_id]
            scaled=pygame.transform.smoothscale(img,(47,34))
            self.kart_rotation_cache[key]=pygame.transform.rotate(scaled,-quant)
        return self.kart_rotation_cache[key]

    def display_racers(self):
        ordered=([self.active_ghost] if self.active_ghost is not None else [])+self.racers
        for r in ordered:
            xy=self.world_to_screen(r.pos)
            # Shadows, outlined friendly cartoon karts and a player number.
            if not r.is_ghost:
                pygame.draw.ellipse(self.canvas,(21,28,38),(xy[0]-23,xy[1]+6,46,15))
            img=self.racer_image(r.kart_id,r.heading)
            if r.is_ghost:
                key=('ghost',r.kart_id,int(round(math.degrees(r.heading)/6))*6%360)
                if key not in self.kart_rotation_cache:
                    faded=img.copy();faded.set_alpha(95)
                    self.kart_rotation_cache[key]=faded
                img=self.kart_rotation_cache[key]
            center=(int(xy[0]),int(xy[1]))
            self.canvas.blit(img,img.get_rect(center=center))
            if r.is_ghost:continue
            dot=(center[0],center[1]-23)
            pygame.draw.circle(self.canvas,(20,31,52),dot,11)
            pygame.draw.circle(self.canvas,PALETTE[r.kart_id],dot,9)
            self.text(str(r.index+1),dot,19,(23,28,41))

    def race_page(self):
        self.map_base()
        if self.active_ghost is not None:
            self.draw_route(self.active_ghost.route.points,(176,194,218),2,dashed=True)
        for r in self.racers:
            self.draw_route(r.route.points,PALETTE[r.kart_id],3)
        self.draw_start()
        self.display_racers()
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,73))
        self.text('WASTE KART', (234,27),38,YELLOW)
        if self.state=='countdown':
            self.text('START YOUR ENGINES!',(425,60),24,WHITE)
        else:
            self.text(f'{self.elapsed:05.1f}s',(704,28),38,WHITE)
            self.text(('GHOST CHALLENGE' if self.active_ghost else 'ONE LAP - DRAWN ROADS'),(396,58),24,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,544,LOGICAL_W,56))
        w=(LOGICAL_W-24)/max(1,len(self.racers))
        for index,r in enumerate(self.racers):
            left=10+index*w
            label=f'P{index+1}  '+('FINISH!' if r.finished else f'{int(r.distance/max(1,r.route.length)*100)}%')
            self.text(label,(left+8,552),22,PALETTE[r.kart_id],align='left')
            trackrect=pygame.Rect(round(left+6),574,round(w-22),12)
            pygame.draw.rect(self.canvas,(57,72,100),trackrect,border_radius=6)
            progress=clamp(r.distance/max(1,r.route.length),0,1)
            if progress>0:
                fill=pygame.Rect(trackrect.x,trackrect.y,max(1,int(trackrect.width*progress)),12)
                pygame.draw.rect(self.canvas,PALETTE[r.kart_id],fill,border_radius=6)
        self.home()
        if self.state=='countdown':
            self.draw_lights()
        if self.paused:
            panel=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
            panel.fill((11,19,37,185));self.canvas.blit(panel,(0,0))
            self.text('PAUSED',(400,230),72,YELLOW)
            self.button((250,322,300,80),'RESUME',('pause',None),selected=True,size=38)
        elif self.state=='race':
            self.button((668,11,120,48),'PAUSE',('pause',None),size=22)

    def draw_lights(self):
        r=pygame.Rect(209,190,382,191)
        pygame.draw.rect(self.canvas,(22,28,43),r,border_radius=30)
        pygame.draw.rect(self.canvas,(250,219,148),r,5,border_radius=30)
        stages=math.floor(self.countdown)
        for i in range(3):
            active=stages>=i+1
            c=(240,65,71) if active else (75,42,48)
            pygame.draw.circle(self.canvas,(8,12,24),(285+i*115,276),42)
            pygame.draw.circle(self.canvas,c,(285+i*115,276),34)
            if active:pygame.draw.circle(self.canvas,(255,183,153),(276+i*115,267),9)
        if self.countdown>=3.0:
            pygame.draw.rect(self.canvas,(47,172,92),(236,339,328,85),border_radius=16)
            self.text('GO!',(400,381),72,WHITE)
        else:
            self.text(f'{max(1,3-stages)}',(400,370),60,YELLOW)

    def celebrate(self):
        self.confetti=[]
        for i in range(95):
            self.confetti.append([self.rng.uniform(0,800),self.rng.uniform(-700,0),
                  self.rng.uniform(-30,30),self.rng.uniform(80,185),self.rng.choice(PALETTE),self.rng.randint(3,8)])

    def results_page(self):
        self.map_base()
        self.display_racers()
        shade=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
        shade.fill((15,25,49,226))
        self.canvas.blit(shade,(0,0))
        for x,y,vx,vy,c,r in self.confetti:
            pygame.draw.circle(self.canvas,c,(round(x),round(y)),r)
        ordered=sorted(self.racers,key=lambda r:(r.finish_time if r.finish_time is not None else 1e9,r.index))
        if self.race_mode=='cup':
            final=self.cup_stage==3
            self.text('CUP CHAMPION!' if final else 'RACE FINISHED!',(400,43),56,YELLOW)
            subtitle=f'{self.catalog["cups"][self.cup]}  -  RACE {self.cup_stage+1} / 4'
            self.text(subtitle,(400,90),28,WHITE)
            if final and ordered:
                champion=self.cup_standings()[0]
                self.text(f'PLAYER {champion+1} TAKES THE CUP!',(400,129),35,PALETTE[self.kart_ids[champion]])
            else:
                self.text(f'{self.track.name}  -  {self.elapsed:.1f}s',(400,129),27,MUTED)
            self.panel((27,163,359,325),(40,57,80),(99,135,164))
            self.panel((414,163,359,325),(40,57,80),(99,135,164))
            self.text('THIS RACE',(206,187),29,YELLOW)
            self.text('CUP POINTS',(594,187),29,YELLOW)
            for place,r in enumerate(ordered):
                y=235+place*55
                self.text(f'{place+1}.', (65,y),30,WHITE)
                self.kart_preview(r.kart_id,(126,y),.42)
                self.text(f'P{r.index+1}',(173,y),28,PALETTE[r.kart_id],align='left')
                self.text(f'{r.finish_time:.1f}s',(353,y),24,WHITE,align='right')
            for rank,who in enumerate(self.cup_standings()):
                y=235+rank*55
                self.text(f'{rank+1}.',(450,y),30,YELLOW if rank==0 else WHITE)
                self.kart_preview(self.kart_ids[who],(507,y),.42)
                self.text(f'P{who+1}',(547,y),28,PALETTE[self.kart_ids[who]],align='left')
                self.text(f'{self.cup_scores[who]} pts',(747,y),26,WHITE,align='right')
            if final:
                self.button((66,517,310,64),'REPLAY CUP',('replay_cup',None),selected=True,size=30)
                self.button((430,517,310,64),'HOME',('home',None),size=30)
            else:
                self.button((166,517,467,64),'NEXT TRACK  >',('next_track',None),selected=True,size=33)
                self.button((13,12,103,47),'HOME',('home',None),size=22)
        else:
            self.text('FINISH!',(400,70),72,YELLOW)
            self.text(f'{self.track.name}  -  ONE LAP',(400,119),30,WHITE)
            if len(ordered)==1:
                message=('YOU DID IT!' if self.ghost_target_time is None else
                         ('YOU BEAT YOUR GHOST!' if ordered[0].finish_time<self.ghost_target_time else 'TRY THE GHOST AGAIN!'))
                self.text(message,(400,158),38,PALETTE[ordered[0].kart_id])
            elif ordered:
                self.text(f'PLAYER {ordered[0].index+1} WINS!',(400,158),43,PALETTE[ordered[0].kart_id])
            self.panel((120,190,560,268),(42,56,78),(251,220,126))
            for place,r in enumerate(ordered):
                y=229+place*53
                self.text(f'{place+1}.',(176,y),32,YELLOW if place==0 else WHITE)
                self.kart_preview(r.kart_id,(241,y),.49)
                self.text(f'PLAYER {r.index+1}',(302,y),27,PALETTE[r.kart_id],align='left')
                self.text(f'{r.finish_time:.2f}s',(645,y),27,WHITE,align='right')
            if self.players==1:
                if self.new_best:self.text('NEW PERSONAL BEST!',(400,477),29,YELLOW)
                elif self.ghost_target_time is not None:
                    self.text(f'GHOST BEST: {self.ghost_target_time:.2f}s',(400,477),28,MUTED)
                else:self.text('Your first lap on this track!',(400,477),26,MUTED)
            self.button((28,519,240,62),'RACE AGAIN',('rematch',None),selected=True,size=28)
            self.button((285,519,239,62),'CHOOSE TRACK',('newrace',None),size=27)
            self.button((540,519,230,62),'HOME',('home',None),size=28)

    def draw(self):
        self.action_buttons=[]
        if self.state=='menu':self.menu_page()
        elif self.state=='tracks':self.tracks_page()
        elif self.state=='karts':self.karts_page()
        elif self.state=='ready':self.ready_page()
        elif self.state=='draw':self.draw_page()
        elif self.state in ('countdown','race'):self.race_page()
        elif self.state=='results':self.results_page()
        if self.screen.get_size() == (LOGICAL_W,LOGICAL_H):
            self.screen.blit(self.canvas,(0,0))
        else:
            resized=pygame.transform.smoothscale(self.canvas,self.screen.get_size())
            self.screen.blit(resized,(0,0))
        pygame.display.flip()

    def cup_standings(self):
        # Points first; accumulated race time breaks a tie, then player number.
        totals={i:sum(row[i] for row in self.cup_history) for i in range(self.players)}
        return sorted(range(self.players),key=lambda i:(-self.cup_scores[i],totals[i],i))

    def go_ready(self):
        self.state='ready'
        self.draft=[]
        self.draw_pointer=None

    def begin_draw(self):
        self.state='draw'
        self.time_left=None if self.draw_seconds is None else float(self.draw_seconds)
        self.draft=[tuple(self.track.centerline[0])]
        self.draw_pointer=None

    def finish_draw(self):
        if self.state!='draw':return
        self.draw_pointer=None
        result=complete_drawn_loop(self.draft,self.track.centerline)
        self.routes.append(Route(result))
        self.draw_player+=1
        if self.draw_player>=self.players:
            self.begin_countdown()
        else:self.go_ready()

    def begin_countdown(self):
        self.state='countdown'
        self.countdown=0.0
        self.elapsed=0.0
        self.paused=False
        self.new_best=False
        self.ghost_target_time=None
        self.racers=[Racer(i,self.kart_ids[i],self.routes[i]) for i in range(self.players)]
        self.active_ghost=None
        if self.players==1:
            record=self.ghost_records.get(self.cup*4+self.track_index)
            if record is not None:
                self.ghost_target_time=record['time']
                self.active_ghost=Racer(-1,record['kart_id'],Route(record['points']),True)

    def begin_new_race(self):
        if self.race_mode=='cup':self.track_index=self.cup_stage
        self.load_track()
        self.routes=[]
        self.draw_player=0
        self.go_ready()

    def start_championship(self):
        self.cup_stage=0
        self.cup_scores=[0,0,0,0]
        self.cup_history=[]
        self.begin_new_race()

    def finish_race(self):
        self.state='results'
        # A frozen finish order is used to award 9/6/3/1 exactly once.
        order=sorted(self.racers,key=lambda r:(r.finish_time if r.finish_time is not None else 1e9,r.index))
        if self.race_mode=='cup':
            for place,r in enumerate(order):self.cup_scores[r.index]+=CUP_POINTS[place]
            self.cup_history.append([next(r.finish_time for r in self.racers if r.index==i) for i in range(self.players)])
        # Ghost is best previous lap in this session, not stored on disk.
        if self.players==1:
            key=self.cup*4+self.track_index
            r=self.racers[0]
            best=self.ghost_records.get(key)
            if best is None or r.finish_time<best['time']:
                self.ghost_records[key]={'time':r.finish_time,'points':list(r.route.points),'kart_id':r.kart_id}
                self.new_best=True
        self.celebrate()

    def handle_button(self,action):
        name,value=action
        if name=='home':self.running=False
        elif name=='mode':self.race_mode=value
        elif name=='players':self.players=value;self.kart_player=0
        elif name=='time':self.draw_seconds=value
        elif name=='state':
            self.state=value
            if value=='karts':self.kart_player=0
        elif name=='cup':self.cup=value;self.track_index=0
        elif name=='track':
            if self.race_mode=='single':self.track_index=value
        elif name=='kart':
            if value not in self.kart_ids[:self.kart_player]:
                self.kart_ids[self.kart_player]=value
        elif name=='kart_next':
            if self.kart_player+1<self.players:
                self.kart_player+=1
                if self.kart_ids[self.kart_player] in self.kart_ids[:self.kart_player]:
                    self.kart_ids[self.kart_player]=next(k for k in range(8) if k not in self.kart_ids[:self.kart_player])
            elif self.race_mode=='cup':self.start_championship()
            else:self.begin_new_race()
        elif name=='start_draw':self.begin_draw()
        elif name=='clear':
            self.draft=[self.track.centerline[0]]
            self.draw_pointer=None
        elif name=='draw_done':self.finish_draw()
        elif name=='pause':self.paused=not self.paused
        elif name=='rematch':self.begin_new_race()  # Replay must allow new drawing!
        elif name=='next_track' and self.race_mode=='cup' and self.cup_stage<3:
            self.cup_stage+=1
            self.begin_new_race()
        elif name=='replay_cup':self.start_championship()
        elif name=='newrace':self.state='tracks';self.kart_player=0

    def finger_press(self,pointer,pos):
        for rect,action in reversed(self.action_buttons):
            if rect.collidepoint(pos):
                self.handle_button(action)
                return
        if self.state=='draw' and TRACK_RECT.collidepoint(pos) and self.draw_pointer is None:
            self.draw_pointer=pointer
            if length(self.draft[-1],self.screen_to_world(pos))>=8:
                self.draft.append(self.screen_to_world(pos))

    def finger_motion(self,pointer,pos):
        if self.state=='draw' and self.draw_pointer==pointer:
            xy=self.screen_to_world(pos)
            if len(self.draft)<1100 and self.draft and length(self.draft[-1],xy)>=8:
                self.draft.append(xy)

    def finger_release(self,pointer,pos):
        if self.draw_pointer==pointer:
            self.finger_motion(pointer,pos)
            self.draw_pointer=None

    def process_event(self,event):
        t=event.type
        if t==pygame.QUIT:self.running=False;return
        if t==pygame.KEYDOWN:
            if event.key==pygame.K_ESCAPE:
                if self.state in ('race','countdown'):
                    self.paused=not self.paused
                else:self.running=False
            elif event.key==pygame.K_SPACE:
                if self.state=='draw':self.finish_draw()
                elif self.state in ('race','countdown'):self.paused=not self.paused
            return
        if t in (pygame.FINGERDOWN,pygame.FINGERMOTION,pygame.FINGERUP):
            pos=(event.x*LOGICAL_W,event.y*LOGICAL_H)
            pointer=('finger',event.finger_id)
            if t==pygame.FINGERDOWN:self.finger_press(pointer,pos)
            elif t==pygame.FINGERMOTION:self.finger_motion(pointer,pos)
            else:self.finger_release(pointer,pos)
            return
        if t not in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP,pygame.MOUSEMOTION):
            return
        if getattr(event,'touch',False) or getattr(event,'which',None)==getattr(pygame,'TOUCH_MOUSEID',-999):
            return
        mouse=('mouse',0)
        # We draw at logical 800x600 even if the host screen is larger.
        width,height=self.screen.get_size()
        pos=(event.pos[0]*LOGICAL_W/max(1,width),event.pos[1]*LOGICAL_H/max(1,height))
        if t==pygame.MOUSEBUTTONDOWN and getattr(event,'button',0)==1:self.finger_press(mouse,pos)
        elif t==pygame.MOUSEBUTTONUP and getattr(event,'button',0)==1:self.finger_release(mouse,pos)
        elif t==pygame.MOUSEMOTION:self.finger_motion(mouse,pos)

    def update(self,dt):
        if self.state=='draw':
            if self.time_left is not None:
                self.time_left-=dt
                if self.time_left<=0:self.finish_draw()
        elif self.state=='countdown':
            if not self.paused:
                self.countdown+=dt
                if self.countdown>=3.8:
                    self.state='race'
        elif self.state=='race':
            if not self.paused:
                self.elapsed+=dt
                for racer in self.racers:
                    racer.update(dt,self.elapsed,self.track)
                if self.active_ghost is not None:
                    self.active_ghost.update(dt,self.elapsed,self.track)
                if self.racers and all(r.finished for r in self.racers):
                    self.finish_race()
        elif self.state=='results':
            for flake in self.confetti:
                flake[0]+=flake[2]*dt
                flake[1]+=flake[3]*dt
                if flake[1]>610:
                    flake[1]=-40
                    flake[0]=self.rng.uniform(0,800)


async def main(screen=None,clock=None):
    """GameHub uses `await wasteKart.main(screen, clock)`. No display quit."""
    if screen is None:
        pygame.init()
        screen=pygame.display.set_mode((LOGICAL_W,LOGICAL_H))
    if clock is None:
        clock=pygame.time.Clock()
    game=WasteKartGame(screen,clock)
    browser_touch_mode(True)
    try:
        while game.running:
            dt=min(clock.tick(FPS)/1000.0,.05)
            for event in pygame.event.get():
                game.process_event(event)
            if not game.running:
                break
            game.update(dt)
            game.draw()
            await asyncio.sleep(0)
    finally:
        browser_touch_mode(False)
    return


if __name__=='__main__':
    asyncio.run(main())
