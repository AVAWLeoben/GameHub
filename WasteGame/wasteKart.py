"""WasteKart 1.0 - draw your own racing line, then race one lap.

Pygame-ce / Pygbag compatible GameHub entry point:
    await wasteKart.main(screen, clock)

Original four-cup, sixteen-course art resides in assets/WasteKart.
The first version intentionally contains no items, collisions, or reflex buttons.
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
    """Gently complete an unfinished line along the track, so everyone races.

    The drawn portion stays untouched, including imaginative off-road shortcuts.
    Only the missing return to the checkered line is assisted.
    """
    start = tuple(centerline[0])
    if len(raw) < 2 or sum(length(a, b) for a, b in zip(raw, raw[1:])) < 28:
        return catmull_rom(list(centerline) + [start])
    drawing = list(raw)
    if length(drawing[0], start) > 1:
        drawing.insert(0, start)
    lap_length = sum(length(a, b) for a, b in zip(centerline, centerline[1:]+centerline[:1]))
    # A child may keep drawing after coming back to the checkered flag. End at
    # their FIRST completed lap rather than racing multiple drawn laps.
    walked = 0.0
    for i in range(1, len(drawing)):
        walked += length(drawing[i-1], drawing[i])
        if walked > lap_length * .62 and length(drawing[i], start) < 43:
            drawing = drawing[:i+1]
            break
        if walked > lap_length * 2.2:
            drawing = drawing[:i+1]
            break
    drawn_length = sum(length(a, b) for a, b in zip(drawing, drawing[1:]))
    last = drawing[-1]
    # Near the checkered flag after approximately one lap: connect directly.
    if length(last, start) < 100 and drawn_length > lap_length * .62:
        drawing.append(start)
    else:
        index = min(range(len(centerline)), key=lambda j: length(last, centerline[j]))
        # Very short scribbles near the starting gate shouldn't skip the whole lap.
        if index < 18 and drawn_length < .5 * lap_length:
            index = 0
        drawing.append(tuple(centerline[index]))
        drawing.extend(tuple(centerline[j]) for j in range(index+3, len(centerline), 3))
        drawing.append(start)
    result = catmull_rom(drawing)
    return result if len(result) >= 2 else catmull_rom(list(centerline) + [start])


class Route:
    def __init__(self, points):
        self.points = list(points)
        self.accumulated = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.accumulated.append(self.accumulated[-1]+length(a, b))
        self.length = self.accumulated[-1] if self.accumulated else 0.0
        self.curve_factors = []
        for i in range(len(self.points)):
            a = self.points[max(0, i-5)]
            b = self.points[i]
            c = self.points[min(len(self.points)-1, i+5)]
            ab = math.atan2(b[1]-a[1], b[0]-a[0]) if length(a,b)>1 else 0
            bc = math.atan2(c[1]-b[1], c[0]-b[0]) if length(b,c)>1 else ab
            theta = abs(angle_delta(ab, bc))
            radius = max(3.0, (length(a,b)+length(b,c))/max(theta, .007))
            self.curve_factors.append(.42+.58*min(1.0, radius/140.0))

    def sample(self, distance):
        if not self.points:
            return ((0.0, 0.0), 0.0, .7)
        if len(self.points) == 1:
            return (self.points[0], 0.0, .7)
        d = clamp(distance, 0.0, self.length)
        j = min(len(self.points)-2, max(0,bisect.bisect_right(self.accumulated,d)-1))
        a, b = self.points[j], self.points[j+1]
        t = (d-self.accumulated[j])/max(.0001,self.accumulated[j+1]-self.accumulated[j])
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        bend = self.curve_factors[j]*(1-t)+self.curve_factors[j+1]*t
        return lerp(a,b,t), angle, bend


class Track:
    def __init__(self, entry):
        self.entry=entry
        geom_path=os.path.join(ASSET_ROOT,*entry['geometry'].split('/'))
        with open(geom_path,encoding='utf8') as stream:
            data=json.load(stream)
        self.name=data['name']
        self.centerline=[tuple(p) for p in data['centerline']]
        self.road_half_width=float(data['road_half_width'])
        self.road_radius_sq=self.road_half_width**2
        self.image_path=os.path.join(ASSET_ROOT,*entry['image'].split('/'))
        self.centerline_route=Route(self.centerline+[self.centerline[0]])
        self.road_buckets={}
        grid=64
        # Spatial cells contain sampled road points within 2 neighbouring cells.
        for pt in self.centerline:
            bx,by=int(pt[0]//grid),int(pt[1]//grid)
            self.road_buckets.setdefault((bx,by),[]).append(pt)

    def on_road(self, point):
        bx,by=int(point[0]//64),int(point[1]//64)
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for p in self.road_buckets.get((bx+dx,by+dy),()):
                    if (p[0]-point[0])**2+(p[1]-point[1])**2 <= self.road_radius_sq:
                        return True
        return False


class Racer:
    def __init__(self, index, kart_id, route):
        self.index=index
        self.kart_id=kart_id
        self.route=route
        self.distance=0.0
        self.speed=0.0
        self.finished=False
        self.finish_time=None
        self.pos,self.heading,_=route.sample(0)
        self.on_track=True
        self.trail=[]

    def update(self, dt, elapsed, track):
        if self.finished:
            return
        pos,heading,bend=self.route.sample(self.distance)
        on_road=track.on_road(pos)
        # Both bend radius and road surface affect speed; a straight shortcut
        # may still be fun, but loses significant speed in the rough.
        desired=235.0*bend*(1.0 if on_road else .54)
        reaction=3.1 if desired>self.speed else 5.2
        self.speed+=(desired-self.speed)*min(1.0,dt*reaction)
        self.distance=min(self.route.length,self.distance+self.speed*dt)
        self.pos,self.heading,_=self.route.sample(self.distance)
        self.on_track=track.on_road(self.pos)
        if self.distance>=self.route.length-1e-3:
            self.finished=True
            self.finish_time=round(elapsed,2)


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
        self.draw_seconds=60
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
        self.title('WASTE KART!','Draw a racing line. Watch your karts zoom!')
        self.panel((56,124,688,149))
        self.text('HOW MANY RACERS?',(400,148),30,YELLOW)
        for i in range(4):
            self.button((94+i*158,177,135,75),str(i+1),('players',i+1),selected=self.players==i+1,size=50)
        self.panel((56,287,688,135))
        self.text('TIME TO DRAW EACH ROAD',(400,311),30,YELLOW)
        for j,seconds in enumerate((20,40,60)):
            self.button((116+j*192,339,180,62),f'{seconds} sec',('time',seconds),selected=self.draw_seconds==seconds,size=34)
        self.text('Everyone draws their own route, one at a time.',(400,449),25,MUTED)
        self.button((214,483,372,79),'CHOOSE A TRACK  >',('state','tracks'),selected=True,size=34)
        self.home()

    def tracks_page(self):
        self.draw_bg()
        self.title('PICK A TRACK','Choose one of 4 cups and 16 original courses!')
        for cup in range(4):
            names=('MEADOW','COAST','DESERT','STAR')
            self.button((29+cup*192,121,169,61),names[cup],('cup',cup),selected=cup==self.cup,size=28)
        for j in range(4):
            x=21+j*195
            area=pygame.Rect(x,214,176,185)
            selected=j==self.track_index
            self.panel(area,(66,100,114) if selected else (43,56,81),YELLOW if selected else (89,119,146))
            thumb=self.track_thumb(self.cup*4+j,(164,105))
            self.canvas.blit(thumb,(x+6,220))
            pygame.draw.rect(self.canvas,(253,238,193) if selected else (117,145,162), (x+5,219,166,107),2,border_radius=5)
            name=self.catalog['tracks'][self.cup*4+j]['name']
            # fit long names to 2 lines by using smaller type
            self.text(name,(x+88,359),22,WHITE)
            if selected:self.text('SELECTED',(x+88,384),19,YELLOW)
            self.action_buttons.append((area,('track',j)))
        self.text(f'Cup {self.cup+1}  -  Track {self.track_index+1}',(400,439),29,WHITE)
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

    def draw_route(self,pts,color,width=4,alpha=255):
        if len(pts)<2:return
        # Pygame's AA is not needed for 4-pixel colored roads, keep line drawing cheap.
        points=[self.world_to_screen(p) for p in pts]
        pygame.draw.lines(self.canvas,color,False,points,width)
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
        self.title('YOUR TURN!','Pass the screen to the next racer.')
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
                self.draw_route(route.points,PALETTE[self.kart_ids[idx]],3)
        color=PALETTE[self.kart_ids[self.draw_player]]
        if len(self.draft)>1:self.draw_route(self.draft,color,6)
        self.draw_start()
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,72))
        self.text(f'PLAYER {self.draw_player+1} - DRAW!',(285,31),38,color)
        self.text(f'{max(0,math.ceil(self.time_left))}s',(713,30),44,YELLOW)
        self.text('Draw around the track and back to green!',(380,59),22,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,545,LOGICAL_W,55))
        self.button((25,550,160,43),'CLEAR',('clear',None),size=25)
        self.text('Lift and continue if you need to.',(392,571),22,MUTED)
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
        for r in self.racers:
            xy=self.world_to_screen(r.pos)
            # Shadows, outlined friendly cartoon karts and a player number.
            pygame.draw.ellipse(self.canvas,(21,28,38),(xy[0]-23,xy[1]+6,46,15))
            img=self.racer_image(r.kart_id,r.heading)
            center=(int(xy[0]),int(xy[1]))
            self.canvas.blit(img,img.get_rect(center=center))
            dot=(center[0],center[1]-23)
            pygame.draw.circle(self.canvas,(20,31,52),dot,11)
            pygame.draw.circle(self.canvas,PALETTE[r.kart_id],dot,9)
            self.text(str(r.index+1),dot,19,(23,28,41))

    def race_page(self):
        self.map_base()
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
            self.text('ONE LAP  -  DRAWN ROADS',(396,58),24,MUTED)
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
        overlay=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
        overlay.fill((15,25,49,217));self.canvas.blit(overlay,(0,0))
        for x,y,vx,vy,c,r in self.confetti:
            pygame.draw.circle(self.canvas,c,(round(x),round(y)),r)
        self.text('FINISH!',(400,71),72,YELLOW)
        self.text(f'ONE LAP  -  {self.elapsed:.1f} seconds',(400,114),30,WHITE)
        ordered=sorted(self.racers,key=lambda racer:racer.finish_time or 100000)
        if ordered:
            if len(ordered)==1:
                self.text('YOU DID IT!',(400,165),50,PALETTE[ordered[0].kart_id])
            else:
                self.text(f'PLAYER {ordered[0].index+1} WINS!',(400,165),50,PALETTE[ordered[0].kart_id])
        for place,r in enumerate(ordered):
            rect=pygame.Rect(155,202+place*58,490,51)
            self.panel(rect,(42,56,78),(251,220,126) if place==0 else (102,130,166),10)
            self.text(f'{place+1}.',(195,rect.centery),34,YELLOW if place==0 else WHITE)
            self.kart_preview(r.kart_id,(264,rect.centery),.49)
            self.text(f'PLAYER {r.index+1}',(313,rect.centery),26,PALETTE[r.kart_id],align='left')
            self.text(f'{r.finish_time:.1f}s',(608,rect.centery),26,WHITE,align='right')
        if len(ordered)<=2:
            start_y=410
        else:
            start_y=465
        self.button((32,524,237,58),'RACE AGAIN',('rematch',None),selected=True,size=27)
        self.button((288,524,237,58),'NEW RACE',('newrace',None),size=27)
        self.button((543,524,225,58),'HOME',('home',None),size=27)

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

    def go_ready(self):
        self.state='ready'
        self.draft=[]
        self.draw_pointer=None

    def begin_draw(self):
        self.state='draw'
        self.time_left=float(self.draw_seconds)
        self.draft=[tuple(self.track.centerline[0])]
        self.draw_pointer=None

    def finish_draw(self):
        if self.state!='draw':return
        self.draw_pointer=None
        result=complete_drawn_loop(self.draft,self.track.centerline)
        route=Route(result)
        if route.length<100:
            route=Route(catmull_rom(self.track.centerline+[self.track.centerline[0]]))
        self.routes.append(route)
        self.draw_player+=1
        if self.draw_player>=self.players:
            self.begin_countdown()
        else:
            self.go_ready()

    def begin_countdown(self):
        self.state='countdown'
        self.countdown=0.0
        self.elapsed=0.0
        self.paused=False
        self.racers=[Racer(i,self.kart_ids[i],self.routes[i]) for i in range(self.players)]

    def begin_new_race(self):
        self.load_track()
        self.routes=[]
        self.draw_player=0
        self.go_ready()

    def handle_button(self,action):
        name,value=action
        if name=='home':
            self.running=False
        elif name=='players':
            self.players=value
            self.kart_player=0
        elif name=='time':self.draw_seconds=value
        elif name=='state':
            self.state=value
            if value=='karts':self.kart_player=0
        elif name=='cup':self.cup=value;self.track_index=0
        elif name=='track':self.track_index=value
        elif name=='kart':
            self.kart_ids[self.kart_player]=value
            # Reserved karts stay unique in this version.
        elif name=='kart_next':
            if self.kart_player+1<self.players:
                self.kart_player+=1
                if self.kart_ids[self.kart_player] in self.kart_ids[:self.kart_player]:
                    self.kart_ids[self.kart_player]=next(k for k in range(8) if k not in self.kart_ids[:self.kart_player])
            else:self.begin_new_race()
        elif name=='start_draw':self.begin_draw()
        elif name=='clear':
            self.draft=[self.track.centerline[0]]
            self.draw_pointer=None
        elif name=='draw_done':self.finish_draw()
        elif name=='pause':self.paused=not self.paused
        elif name=='rematch':self.begin_countdown()
        elif name=='newrace':self.state='menu';self.kart_player=0

    def finger_press(self,pointer,pos):
        for rect,action in reversed(self.action_buttons):
            if rect.collidepoint(pos):
                self.handle_button(action)
                return
        if self.state=='draw' and TRACK_RECT.collidepoint(pos) and self.draw_pointer is None:
            self.draw_pointer=pointer
            self.draft.append(self.screen_to_world(pos))

    def finger_motion(self,pointer,pos):
        if self.state=='draw' and self.draw_pointer==pointer:
            xy=self.screen_to_world(pos)
            if len(self.draft)<1100 and self.draft and length(self.draft[-1],xy)>=4:
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
                if self.racers and all(r.finished for r in self.racers):
                    self.state='results'
                    self.celebrate()
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
