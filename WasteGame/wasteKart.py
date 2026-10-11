"""WasteKart 1.4.1 - optional subtle racing lines and pictorial power-up HUD.

Pygame-ce / Pygbag compatible GameHub entry point:
    await wasteKart.main(screen, clock)

Original four-cup, sixteen-course art resides in assets/WasteKart.
Races use 16 original tracks. Kart-to-kart interactions are future additions.
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
GREEN_AT = 3.0
REACTION_WINDOW = 1.5       # Seconds after green; no penalty if a child simply waits.
REACTION_EFFECT_SECONDS = 3.0
EARLY_START_MODIFIER = 0.82 # A gentle, temporary false-start penalty.
TRAIL_CHUNK_WORLD = 240.0  # Pre-render short route spans, not whole paths every frame.
POWERUP_RESPAWN = 7.0      # Same shared box disappears temporarily for all players.
POWERUP_PICKUP_RADIUS = 23.0  # World pixels: must draw near a box, not just follow road center.
POWERUP_DURATION = {'turbo': 3.2, 'tailwind': 6.0}
POWERUP_MULTIPLIER = {'turbo': 1.48, 'tailwind': 1.20}
POWERUP_COLORS = {'turbo': (255, 169, 59), 'tailwind': (91, 239, 240)}
# A deliberately subtle overlay: RGB colors keep each player's identity,
# while SRCALPHA layers make the one-pixel dashes blend into the road.
RACE_LINE_OPACITY = 67
GHOST_LINE_OPACITY = 42


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


def combine_drawn_laps(raw_laps, centerline):
    """Join distinct child-drawn laps into ONE non-repeating race spline.

    Each individual lap is Catmull-Rom smoothed and, if unfinished, connects
    straight to the flag. Boundaries are measured arc distances and retained
    for the race HUD and ghost playback. No lap is duplicated or looped.
    """
    if not raw_laps:
        raw_laps = [[centerline[0]]]
    combined=[]
    boundaries=[]
    distance=0.0
    for raw in raw_laps:
        lap=complete_drawn_loop(raw,centerline)
        if combined:
            lap=lap[1:]  # same start/finish point; don't duplicate a vertex
        if not lap:
            continue
        if combined:
            distance+=length(combined[-1],lap[0])
        for a,b in zip(lap,lap[1:]):
            distance+=length(a,b)
        combined.extend(lap)
        boundaries.append(distance)
    return combined,boundaries


def segment_near_point(a,b,p):
    """Distance to a line segment, robust to fast touch movements."""
    dx=b[0]-a[0];dy=b[1]-a[1]
    span=dx*dx+dy*dy
    t=clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/span,0,1) if span>1e-7 else 0.0
    return length(lerp(a,b,t),p)


class Route:
    """Precompute arc lengths and smoothed circumradius-based bend factors."""
    def __init__(self, points, lap_boundaries=None):
        self.points = list(points)
        self.accumulated = [0.0]
        for a,b in zip(self.points,self.points[1:]):
            self.accumulated.append(self.accumulated[-1]+length(a,b))
        self.length = self.accumulated[-1]
        self.lap_boundaries = (list(lap_boundaries) if lap_boundaries is not None
                               else [self.length])
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


def subroute_points(route, start_distance, end_distance):
    """Exact route portion [start, end] by arc length, with interpolated ends.

    Keeping slices separate preserves future portions of a three-lap route,
    even if a later lap drives exactly on top of an earlier one.
    """
    if len(route.points)<2 or route.length<1e-5:
        return []
    start=clamp(float(start_distance),0.0,route.length)
    end=clamp(float(end_distance),start,route.length)
    if end-start<1e-5:
        return []
    lo=bisect.bisect_right(route.accumulated,start)
    hi=bisect.bisect_left(route.accumulated,end)
    return ([route.sample(start)[0]] +
            route.points[lo:hi] +
            [route.sample(end)[0]])


def paint_trail_section(surface, points, color, width, dashed=False, phase=0.0):
    """Paint a screen-space path segment, respecting dashed distance phase."""
    if len(points)<2:return
    if not dashed:
        pygame.draw.lines(surface,color,False,points,width)
        return
    walked=float(phase)
    dash_length=11.0
    for a,b in zip(points,points[1:]):
        span=length(a,b)
        if span<1e-5:continue
        used=0.0
        while used<span-1e-5:
            remainder=dash_length-(walked%dash_length)
            step=min(span-used,max(1e-4,remainder))
            if int(walked/dash_length)%2==0:
                pygame.draw.line(surface,color,lerp(a,b,used/span),
                                 lerp(a,b,(used+step)/span),width)
            used+=step
            walked+=step


class AheadTrail:
    """Cache the faint, dashed route still ahead of a moving kart.

    Short spans are baked once to small transparent images. Only the span
    containing the kart is repainted onto a reusable *transparent* scratch
    image. Painting its alpha lines directly on the opaque screen would ignore
    their transparency, making the leading section conspicuously bright.
    Overlapping future laps remain independent from already driven laps.
    """
    def __init__(self,route,color,to_screen,ghost=False):
        self.route=route
        self.ghost=ghost
        self.width=1
        self.ink=tuple(color)+(GHOST_LINE_OPACITY if ghost else RACE_LINE_OPACITY,)
        self.to_screen=to_screen
        self.spans=[]
        self.partial_surface=None
        if len(route.points)<2 or route.length<1e-5:
            return
        count=math.ceil(route.length/TRAIL_CHUNK_WORLD)
        for i in range(count):
            start=i*TRAIL_CHUNK_WORLD
            end=min(route.length,(i+1)*TRAIL_CHUNK_WORLD)
            world_points=subroute_points(route,start,end)
            screen_points=[to_screen(point) for point in world_points]
            if len(screen_points)<2:continue
            padding=3
            xmin=math.floor(min(point[0] for point in screen_points))-padding
            ymin=math.floor(min(point[1] for point in screen_points))-padding
            xmax=math.ceil(max(point[0] for point in screen_points))+padding
            ymax=math.ceil(max(point[1] for point in screen_points))+padding
            image=pygame.Surface((max(1,xmax-xmin+1),max(1,ymax-ymin+1)),pygame.SRCALPHA)
            shifted=[(x-xmin,y-ymin) for x,y in screen_points]
            phase=start*TRACK_RECT.width/MAP_W
            paint_trail_section(image,shifted,self.ink,self.width,True,phase)
            self.spans.append((start,end,image,(xmin,ymin)))

    def draw(self,surface,travelled):
        if not self.spans:return
        pos=clamp(travelled,0.0,self.route.length)
        if pos>=self.route.length-1e-4:return
        first=min(len(self.spans)-1,int(pos/TRAIL_CHUNK_WORLD))
        for i in range(first,len(self.spans)):
            start,end,image,screen_xy=self.spans[i]
            if end<=pos+1e-5:continue
            if pos<=start+1e-5:
                surface.blit(image,screen_xy)
            else:
                # Reuse an alpha scratch image rather than allocating a new
                # full-screen layer or drawing opaque lines every frame.
                if (self.partial_surface is None or
                        self.partial_surface.get_size()!=image.get_size()):
                    self.partial_surface=pygame.Surface(image.get_size(),pygame.SRCALPHA)
                self.partial_surface.fill((0,0,0,0))
                points=subroute_points(self.route,pos,end)
                screen_points=[self.to_screen(point) for point in points]
                local=[(x-screen_xy[0],y-screen_xy[1]) for x,y in screen_points]
                phase=pos*TRACK_RECT.width/MAP_W
                paint_trail_section(self.partial_surface,local,self.ink,self.width,
                                    True,phase)
                surface.blit(self.partial_surface,screen_xy)

class PowerupBox:
    """Shared road pickup: collecting it hides it even when the kart is full."""
    def __init__(self, pos, slot):
        self.pos=tuple(pos)
        self.slot=slot
        self.hidden_until=0.0
        self.picked_at=-100.0

    def available(self, now):
        return now >= self.hidden_until

    def collect(self, now):
        if not self.available(now):
            return False
        self.picked_at=now
        self.hidden_until=now+POWERUP_RESPAWN
        return True


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
        self.pickup_positions=self.find_pickup_positions()

    def on_road(self,point):
        x,y=int(point[0]),int(point[1])
        if not (0<=x<MAP_W and 0<=y<MAP_H):return False
        # A single O(1) lookup, even with four karts on iPad.
        return self.mask.get_at((x,y))[0] > 127

    def find_pickup_positions(self):
        """Offset boxes from the ideal line but keep them ON the road.

        Fixed fractions and alternating sides mean predictable, fair positions
        across all drawing turns and a replay. Road mask validates each site.
        """
        route=self.centerline_route
        spots=[]
        for slot,fraction in enumerate((.09,.21,.34,.47,.60,.73,.86)):
            p,angle,_=route.sample(route.length*fraction)
            nx,ny=-math.sin(angle),math.cos(angle)
            # 70-79% of road half-width: centerline misses each pickup.
            side=1 if slot%2==0 else -1
            found=None
            for sign in (side,-side):
                for factor in (.77,.71,.65):
                    lateral=self.road_half_width*factor*sign
                    candidate=(p[0]+nx*lateral,p[1]+ny*lateral)
                    if (28<candidate[0]<MAP_W-28 and
                            28<candidate[1]<MAP_H-28 and
                            self.on_road(candidate) and
                            all(length(candidate,other)>70 for other in spots)):
                        found=candidate
                        break
                if found is not None:break
            if found is not None:spots.append(found)
        return spots


class Racer:
    """One vehicle drives its entire child-drawn multi-lap spline ONCE."""
    def __init__(self,index,kart_id,route,is_ghost=False,laps=1):
        self.index=index
        self.kart_id=kart_id
        self.route=route
        self.is_ghost=is_ghost
        self.laps=laps
        self.total_length=route.length
        # The three lap boundaries can be different lengths and shapes.
        self.lap_boundaries = list(route.lap_boundaries)
        self.distance=0.0
        self.completed_laps=0
        self.lap_times=[]
        self.lap_crossing_times=[]
        self.speed=0.0
        self.start_modifier=1.0
        self.start_effect_left=0.0
        self.modifiers=[]       # Future slipstreaming / kart interaction hook.
        self.held_powerup=None
        self.powerup_kind=None
        self.powerup_left=0.0
        self.used_powerups=[]
        self.ghost_powerups=[]
        self.ghost_powerups_index=0
        self.finished=False
        self.finish_time=None
        self.pos,self.heading,_=route.sample(0)
        self.on_track=True
        # Ghost uses the recorded reaction, including an early-press penalty.
        self.ghost_reaction=None
        self.ghost_reaction_applied=False

    def apply_start_reaction(self, reaction):
        """Negative reaction means false start; None means no manual boost."""
        if reaction is None:
            return
        if reaction < 0:
            self.start_modifier=EARLY_START_MODIFIER
        else:
            quickness=1.0-clamp(reaction/REACTION_WINDOW,0.0,1.0)
            self.start_modifier=1.12+0.33*quickness
        self.start_effect_left=REACTION_EFFECT_SECONDS

    def activate_powerup(self, when):
        """Spend one held power-up; a second pickup can be saved for later."""
        if self.finished or self.held_powerup is None or self.powerup_left>0:
            return False
        kind=self.held_powerup
        self.held_powerup=None
        self.start_powerup(kind)
        self.used_powerups.append((round(when,3),kind))
        return True

    def start_powerup(self, kind):
        if kind not in POWERUP_DURATION or self.finished:
            return
        self.powerup_kind=kind
        self.powerup_left=POWERUP_DURATION[kind]

    def route_sample(self, distance):
        """Traverse the entire unique drawing, never wrap or teleport."""
        return self.route.sample(distance)

    def update(self,dt,elapsed,track):
        if self.finished:return
        if self.is_ghost and not self.ghost_reaction_applied and self.ghost_reaction is not None:
            if self.ghost_reaction < 0 or elapsed >= self.ghost_reaction:
                self.apply_start_reaction(self.ghost_reaction)
                self.ghost_reaction_applied=True
        if self.is_ghost:
            # Replay item activations at their original times, but do not
            # touch shared boxes or alter other players' inventories.
            while self.ghost_powerups_index<len(self.ghost_powerups):
                trigger,kind=self.ghost_powerups[self.ghost_powerups_index]
                if elapsed < trigger:break
                self.start_powerup(kind)
                self.ghost_powerups_index+=1
        pos,heading,bend=self.route_sample(self.distance)
        road=track.on_road(pos)
        temporary=1.0
        if self.start_effect_left>0:
            temporary+=((self.start_modifier-1.0)
                        * self.start_effect_left/REACTION_EFFECT_SECONDS)
            self.start_effect_left=max(0.0,self.start_effect_left-dt)
        if self.powerup_left>0 and self.powerup_kind in POWERUP_MULTIPLIER:
            temporary*=POWERUP_MULTIPLIER[self.powerup_kind]
            self.powerup_left=max(0.0,self.powerup_left-dt)
        desired=track.max_speed*bend*(ROAD_FACTOR if road else GRASS_FACTOR)*min(1.95,temporary)
        for modifier in self.modifiers:
            desired*=modifier
        response=3.1 if desired>self.speed else 5.2
        self.speed+=(desired-self.speed)*min(1.0,dt*response)
        advance=self.speed*dt
        previous=self.distance
        self.distance=min(self.total_length,self.distance+advance)
        self.pos,self.heading,_=self.route_sample(self.distance)
        self.on_track=track.on_road(self.pos)
        if self.route.length>1e-5 and advance>1e-7:
            while self.completed_laps<self.laps:
                boundary=self.lap_boundaries[self.completed_laps]
                if self.distance<boundary-1e-4:
                    break
                fraction=clamp((boundary-previous)/advance,0.0,1.0)
                lap_end=round(elapsed-dt+dt*fraction,3)
                previous_end=self.lap_crossing_times[-1] if self.lap_crossing_times else 0.0
                self.lap_times.append(round(lap_end-previous_end,3))
                self.lap_crossing_times.append(lap_end)
                self.completed_laps+=1
        if self.distance>=self.total_length-1e-3:
            self.finished=True
            self.finish_time=round(elapsed-dt+dt*clamp(
                (self.total_length-previous)/max(advance,1e-6),0,1),3)

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
        self.laps=1
        self.reflex_start=True
        self.powerups_enabled=False  # Independent of the reflex start toggle.
        self.show_racing_lines=False  # Default uncluttered, especially for 4 players.
        self.reaction_status=[]
        self.reaction_times=[]
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
        self.drawn_laps=[]
        self.draw_lap_distance=0.0
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
        self.race_routes_layer=None  # Legacy field; used only during transition.
        self.race_trails=[]      # AheadTrail for each player (+ optional ghost).
        self.pickups=[]          # Fresh shared boxes for each race; stable during drawing.
        self.item_box_clock=0.0
        self.question_mark=None
        self.draw_routes_layer=None
        self.draw_routes_layer_key=None
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
        self.draw_routes_layer_key=None
        index=self.cup*4+self.track_index
        if index not in self.track_cache:
            self.track_cache[index]=Track(self.catalog['tracks'][index])
        self.track=self.track_cache[index]
        self.pickups=([PowerupBox(p,i) for i,p in enumerate(self.track.pickup_positions)]
                      if self.powerups_enabled else [])
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
        self.title('WASTE KART!', 'Draw a racing line. Race it together!')
        self.panel((40,98,720,91))
        self.text('PICK YOUR RACE',(400,111),25,YELLOW)
        self.button((76,134,311,45),'SINGLE RACE',('mode','single'),selected=self.race_mode=='single',size=26)
        self.button((413,134,311,45),'4-TRACK CUP',('mode','cup'),selected=self.race_mode=='cup',size=26)

        self.panel((40,197,720,87))
        self.text('HOW MANY RACERS?',(400,213),25,YELLOW)
        for i in range(4):
            self.button((85+i*158,233,144,43),str(i+1),('players',i+1),selected=self.players==i+1,size=31)

        self.panel((40,293,720,86))
        self.text('TIME TO DRAW',(400,309),25,YELLOW)
        for i,(seconds,label) in enumerate(((15,'15 SEC'),(30,'30 SEC'),(60,'60 SEC'),(None,'NO LIMIT'))):
            self.button((60+i*174,330,156,41),label,('time',seconds),selected=self.draw_seconds==seconds,size=23)

        self.panel((40,389,347,85))
        self.text('HOW MANY LAPS?',(213,404),24,YELLOW)
        self.button((54,426,154,40),'1 LAP',('laps',1),selected=self.laps==1,size=27)
        self.button((219,426,154,40),'3 LAPS',('laps',3),selected=self.laps==3,size=27)

        self.panel((399,389,361,85))
        self.text('REFLEX START?',(579,404),24,YELLOW)
        self.button((412,426,156,40),'OFF',('reflex',False),selected=not self.reflex_start,size=27)
        self.button((582,426,165,40),'ON!',('reflex',True),selected=self.reflex_start,size=27)

        # Independent switches fit above the original NEXT button, without
        # crowding or shrinking any touch target on the 800x600 canvas.
        self.panel((40,480,347,54))
        self.text('POWER-UPS',(127,506),23,YELLOW)
        self.button((216,486,76,41),'OFF',('powerups',False),
                    selected=not self.powerups_enabled,size=23)
        self.button((300,486,76,41),'ON',('powerups',True),
                    selected=self.powerups_enabled,size=23)
        self.panel((399,480,361,54))
        self.text('RACE LINES',(466,506),22,YELLOW)
        self.button((537,486,91,41),'HIDE',('lines',False),
                    selected=not self.show_racing_lines,size=23)
        self.button((646,486,101,41),'SHOW',('lines',True),
                    selected=self.show_racing_lines,size=23)
        self.button((255,543,290,46),'CHOOSE CUP  >',('state','tracks'),selected=True,size=26)
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

    def draw_powerup_boxes(self, race=False):
        """Lightweight rotating / bobbing MK-style cubes, drawn procedurally.

        No textures loaded, no per-frame rotation or scaling allocations.
        The shared respawn clock is race elapsed time, NOT drawing time.
        """
        if not self.powerups_enabled or not self.pickups:return
        if self.question_mark is None:
            self.question_mark=self.font(30).render('?',True,(255,251,220))
        t=self.item_box_clock
        for box in self.pickups:
            x,y=self.world_to_screen(box.pos)
            if race and not box.available(self.elapsed):
                age=self.elapsed-box.picked_at
                if 0<=age<.48:
                    radius=round(8+age*48)
                    pygame.draw.circle(self.canvas,(255,226,130),(round(x),round(y)),radius,3)
                    pygame.draw.circle(self.canvas,(147,237,248),(round(x),round(y)),max(3,radius-6),2)
                continue
            phase=t*3.0+box.slot*.91
            bob=math.sin(phase)*3.2
            cx,cy=round(x),round(y+bob)
            # Fake 3D rotating cube: face narrows and grows while a side face
            # flips from left to right. All colors contrast with the road.
            spin=math.sin(phase)
            wide=10+round(7*abs(math.cos(phase)))
            depth=7 if spin>=0 else -7
            pts=[(cx-wide,cy-13),(cx+wide,cy-13),(cx+wide,cy+13),(cx-wide,cy+13)]
            side=[pts[1],(pts[1][0]+depth,pts[1][1]-5),
                  (pts[2][0]+depth,pts[2][1]-5),pts[2]] if spin>=0 else [
                  pts[0],(pts[0][0]+depth,pts[0][1]-5),
                  (pts[3][0]+depth,pts[3][1]-5),pts[3]]
            pygame.draw.ellipse(self.canvas,(37,35,71),(cx-17,cy+14,34,8))
            pygame.draw.polygon(self.canvas,(67,187,228),side)
            pygame.draw.polygon(self.canvas,(144,86,211),pts)
            pygame.draw.polygon(self.canvas,(218,176,255),pts,3)
            pygame.draw.line(self.canvas,(255,238,173),(cx-wide+4,cy-9),(cx+wide-3,cy-9),2)
            mark=self.question_mark
            self.canvas.blit(mark,mark.get_rect(center=(cx,cy+1)))
            glint=(cx+wide+depth+3,cy-15)
            pygame.draw.circle(self.canvas,(255,251,177),glint,2+(int(t*5+box.slot)%2))

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
        self.text(f'Draw {self.laps} lap'+('s' if self.laps>1 else '')+' - each one is different!',(400,385),32,WHITE)
        self.text('Start at the green dot. Your finger is the pencil.',(400,424),25,MUTED)
        self.button((220,473,360,79),'READY TO DRAW!',('start_draw',None),selected=True,size=37)
        self.home()

    def ensure_draw_routes_layer(self):
        """Cache completed players' and completed laps' dashed routes.

        Only the active finger stroke must be redrawn at frame rate. This keeps
        three-lap multiplayer drawing responsive on iPad/Pygbag.
        """
        cache_key=(self.cup,self.track_index,self.draw_player,
                   len(self.routes),len(self.drawn_laps))
        if self.draw_routes_layer_key==cache_key and self.draw_routes_layer is not None:
            return
        previous=self.canvas
        self.draw_routes_layer=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
        self.canvas=self.draw_routes_layer
        try:
            for idx,route in enumerate(self.routes):
                if route is not None:
                    self.draw_route(route.points,PALETTE[self.kart_ids[idx]],3,dashed=True)
            color=PALETTE[self.kart_ids[self.draw_player]]
            for prior in self.drawn_laps:
                if len(prior)>1:self.draw_route(prior,color,3,dashed=True)
        finally:
            self.canvas=previous
        self.draw_routes_layer_key=cache_key

    def draw_page(self):
        self.map_base()
        self.ensure_draw_routes_layer()
        self.canvas.blit(self.draw_routes_layer,(0,0))
        self.draw_powerup_boxes()
        color=PALETTE[self.kart_ids[self.draw_player]]
        if len(self.draft)>1:self.draw_route(self.draft,color,6)
        self.draw_start()
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,72))
        self.text(f'P{self.draw_player+1} - DRAW LAP {len(self.drawn_laps)+1}/{self.laps}',(306,31),34,color)
        self.text(('\u221e' if self.time_left is None else f'{max(0,math.ceil(self.time_left))}s'),(713,30),44,YELLOW)
        self.text('Draw to the green dot. Every lap gets its OWN line!',(380,59),22,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,545,LOGICAL_W,55))
        self.button((25,550,160,43),'CLEAR',('clear',None),size=25)
        self.text(f'LAPS DONE: {len(self.drawn_laps)}/{self.laps}   -   Lift to pause. CLEAR to retry.',(397,571),21,MUTED)
        self.button((624,550,150,43),'FINISH LAP',('draw_done',None),selected=True,size=23)
        self.home()

    def racer_image(self,kart_id,angle):
        quant=(int(round(math.degrees(angle)/6))*6)%360
        key=('race',kart_id,quant)
        if key not in self.kart_rotation_cache:
            img=self.kart_images[kart_id]
            scaled=pygame.transform.smoothscale(img,(47,34))
            self.kart_rotation_cache[key]=pygame.transform.rotate(scaled,-quant)
        return self.kart_rotation_cache[key]

    def boost_flame(self,r,center):
        """Cartoon exhaust behind a successful reflex start, not a false start.

        Procedural polygons add no artwork files or per-frame image transforms.
        The flame points backwards along the kart's spline tangent, and its
        length flickers while the three-second start modifier is active.
        """
        if (r.is_ghost or r.finished or self.state!='race' or
                r.start_modifier<=1.0 or r.start_effect_left<=0.0):
            return
        ux,uy=math.cos(r.heading),math.sin(r.heading)
        nx,ny=-uy,ux
        # The kart artwork points toward +x before rotating with the tangent.
        base=(center[0]-ux*20,center[1]-uy*20)
        power=clamp((r.start_modifier-1.0)/0.45,0.0,1.0)
        life=clamp(r.start_effect_left/REACTION_EFFECT_SECONDS,0.0,1.0)
        flicker=math.sin(self.elapsed*29.0+r.index*2.4)*3.0
        extent=(14.0+17.0*power+flicker)*(0.55+0.45*life)
        breadth=6.5+2.0*power
        def at(back,side):
            return (round(base[0]-ux*back+nx*side),
                    round(base[1]-uy*back+ny*side))
        pygame.draw.polygon(self.canvas,(246,91,48),
            [at(-3,-breadth),at(extent,0),at(-3,breadth)])
        pygame.draw.polygon(self.canvas,(255,165,55),
            [at(-1,-breadth*.63),at(extent*.72,0),at(-1,breadth*.63)])
        pygame.draw.polygon(self.canvas,(255,241,129),
            [at(-1,-breadth*.33),at(extent*.45,0),at(-1,breadth*.33)])
        # Two small trailing sparks make the movement visible even at 1x.
        spark=extent+5.0+4.0*abs(math.sin(self.elapsed*18.0+r.index))
        pygame.draw.circle(self.canvas,(255,186,74),at(spark,breadth*.6),2)
        pygame.draw.circle(self.canvas,(255,212,93),at(spark+6,-breadth*.45),2)

    def powerup_visuals(self,r,center):
        """Distinct continuous effects make both boost types unambiguous."""
        if (r.is_ghost or r.finished or self.state!='race' or
                r.powerup_left<=0 or r.powerup_kind not in POWERUP_DURATION):
            return
        ux,uy=math.cos(r.heading),math.sin(r.heading)
        nx,ny=-uy,ux
        t=self.elapsed
        if r.powerup_kind=='turbo':
            # Strong, hot exhaust flames with gold sparks behind the bumper.
            for side in (-7,7):
                root=(center[0]-ux*19+nx*side,center[1]-uy*19+ny*side)
                flick=math.sin(t*29+side+r.index)*5
                def at(back,width):
                    return (round(root[0]-ux*back+nx*width),
                            round(root[1]-uy*back+ny*width))
                pygame.draw.polygon(self.canvas,(247,70,43),
                    [at(0,-5),at(31+flick,0),at(0,5)])
                pygame.draw.polygon(self.canvas,(255,209,61),
                    [at(0,-2.5),at(21+flick*.5,0),at(0,2.5)])
                pygame.draw.circle(self.canvas,(255,244,133),at(38+flick,0),3)
        else:
            # Tailwind is a cool turquoise airflow, NOT another orange flame.
            for side in (-1,1):
                for k in range(3):
                    shift=(t*47+k*20+r.index*9)%59
                    side_dist=side*(17+math.sin(t*8+k)*3)
                    a=(round(center[0]-ux*(10+shift)+nx*side_dist),
                       round(center[1]-uy*(10+shift)+ny*side_dist))
                    b=(round(a[0]-ux*(11+k*2)),round(a[1]-uy*(11+k*2)))
                    pygame.draw.line(self.canvas,(74,235,234),a,b,3 if k==0 else 2)
            pygame.draw.circle(self.canvas,(161,255,243),center,27,2)

    def draw_powerup_icon(self,kind,center,size=34):
        """Recognizable, text-free icons for children who cannot read yet.

        Fire = TURBO; turquoise wind trails = TAILWIND; ? = empty slot.
        Icons are drawn directly with Pygame and don't require extra PNGs.
        """
        x,y=round(center[0]),round(center[1])
        r=max(11,round(size*.49))
        if kind=='turbo':
            pygame.draw.circle(self.canvas,(92,43,30),(x,y),r)
            pygame.draw.circle(self.canvas,(255,174,56),(x,y),r,2)
            def coords(points):
                scale=size/34.0
                return [(round(x+px*scale),round(y+py*scale)) for px,py in points]
            pygame.draw.polygon(self.canvas,(255,112,33),coords([
                (-9,11),(-11,0),(-5,-4),(0,-13),(5,-6),(9,-8),(11,2),(7,12)]))
            pygame.draw.polygon(self.canvas,(255,217,75),coords([
                (-5,10),(-6,3),(-1,-4),(2,-1),(5,1),(5,10)]))
            pygame.draw.polygon(self.canvas,(255,248,165),coords([
                (-2,10),(-2,5),(1,2),(3,6),(2,10)]))
        elif kind=='tailwind':
            pygame.draw.circle(self.canvas,(22,74,88),(x,y),r)
            pygame.draw.circle(self.canvas,(86,242,233),(x,y),r,2)
            scale=size/34.0
            def pt(dx,dy):return (round(x+dx*scale),round(y+dy*scale))
            for points in (
                    [(-12,-7),(-5,-7),(3,-7),(10,-11),(13,-8)],
                    [(-13,0),(-4,0),(8,0),(11,-3)],
                    [(-9,7),(-2,7),(5,7),(9,10),(13,8)]):
                pygame.draw.lines(self.canvas,(158,255,247),False,
                                  [pt(dx,dy) for dx,dy in points],3)
            for dx,dy in ((-12,-7),(-13,0),(-9,7)):
                pygame.draw.circle(self.canvas,(84,221,240),pt(dx,dy),2)
        else:
            pygame.draw.circle(self.canvas,(53,67,96),(x,y),r)
            pygame.draw.circle(self.canvas,(124,142,163),(x,y),r,2)
            self.text('?',(x,y-1),30,(214,224,231))

    def draw_item_buttons(self):
        """One big pictorial item button per child, always in their kart color."""
        gap=7
        width=int((780-gap*(self.players-1))/self.players)
        for index,racer in enumerate(self.racers):
            x=10+index*(width+gap)
            rect=pygame.Rect(x,547,width,47)
            held=racer.held_powerup
            active=(racer.powerup_kind if racer.powerup_left>0 else None)
            kind=held if held is not None else active
            border=POWERUP_COLORS[kind] if kind else PALETTE[racer.kart_id]
            pygame.draw.rect(self.canvas,(31,44,67),rect,border_radius=11)
            pygame.draw.rect(self.canvas,border,rect,3,border_radius=11)
            self.text(f'P{index+1}',(rect.left+27,rect.centery-3),23,
                      PALETTE[racer.kart_id])
            icon_center=(rect.centerx+9,rect.centery-3)
            self.draw_powerup_icon(kind,icon_center,34)
            if held is not None:
                # Small pulsing spark: a collected item is ready to tap.
                beat=math.sin(self.elapsed*9+index)*3
                pygame.draw.circle(self.canvas,(255,251,172),
                    (round(icon_center[0]+18+beat),round(icon_center[1]-13)),3)
            elif active is not None:
                # Clockwise remaining-duration halo around the active icon.
                fraction=clamp(racer.powerup_left/POWERUP_DURATION[active],0,1)
                ring=pygame.Rect(icon_center[0]-20,icon_center[1]-20,40,40)
                if fraction>.01:
                    pygame.draw.arc(self.canvas,border,ring,
                                    -math.pi/2,-math.pi/2+2*math.pi*fraction,3)
            progress=clamp(racer.distance/max(1,racer.total_length),0,1)
            pygame.draw.line(self.canvas,(70,83,112),(rect.left+11,rect.bottom-7),
                             (rect.right-11,rect.bottom-7),3)
            if progress>0:
                pygame.draw.line(self.canvas,PALETTE[racer.kart_id],
                                 (rect.left+11,rect.bottom-7),
                                 (round(rect.left+11+(rect.width-22)*progress),rect.bottom-7),3)
            self.action_buttons.append((rect,('powerup_press',index)))

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
            self.boost_flame(r,center)
            self.powerup_visuals(r,center)
            self.canvas.blit(img,img.get_rect(center=center))
            if r.is_ghost:continue
            dot=(center[0],center[1]-23)
            pygame.draw.circle(self.canvas,(20,31,52),dot,11)
            pygame.draw.circle(self.canvas,PALETTE[r.kart_id],dot,9)
            self.text(str(r.index+1),dot,19,(23,28,41))

    def race_page(self):
        self.map_base()
        # Draw each kart's untraveled route separately. Previously driven
        # sections disappear immediately, including during lap 2 and lap 3.
        if self.show_racing_lines:
            for racer,trail in self.race_trails:
                trail.draw(self.canvas,racer.distance)
        self.draw_powerup_boxes(race=self.state=='race')
        self.draw_start()
        self.display_racers()
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,73))
        self.text('WASTE KART', (234,27),38,YELLOW)
        if self.state=='countdown':
            self.text('TAP YOUR COLOR ON GREEN!' if self.reflex_start else 'START YOUR ENGINES!',(425,60),24,WHITE)
        else:
            self.text(f'{self.elapsed:05.1f}s',(704,28),38,WHITE)
            self.text(f'{self.laps} LAP'+('S' if self.laps>1 else '')+(' - GHOST' if self.active_ghost else ''),(396,58),24,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,544,LOGICAL_W,56))
        item_buttons=(self.powerups_enabled and self.state=='race' and
                      not self.paused and (not self.reflex_start or self.elapsed>=REACTION_WINDOW))
        if item_buttons:
            self.draw_item_buttons()
        w=(LOGICAL_W-24)/max(1,len(self.racers))
        for index,r in enumerate(self.racers):
            left=10+index*w
            label=f'P{index+1}  '+('FINISH!' if r.finished else f'LAP {min(self.laps,r.completed_laps+1)}/{self.laps}')
            if item_buttons:continue
            self.text(label,(left+8,552),22,PALETTE[r.kart_id],align='left')
            trackrect=pygame.Rect(round(left+6),574,round(w-22),12)
            pygame.draw.rect(self.canvas,(57,72,100),trackrect,border_radius=6)
            progress=clamp(r.distance/max(1,r.total_length),0,1)
            if progress>0:
                fill=pygame.Rect(trackrect.x,trackrect.y,max(1,int(trackrect.width*progress)),12)
                pygame.draw.rect(self.canvas,PALETTE[r.kart_id],fill,border_radius=6)
        self.home()
        if self.state=='countdown':
            self.draw_lights()
        elif self.state=='race' and self.elapsed<0.75:
            # Keep GO visible when the race actually starts, not before.
            pygame.draw.rect(self.canvas,(42,153,87),(281,117,238,89),border_radius=20)
            pygame.draw.rect(self.canvas,(242,226,135),(281,117,238,89),4,border_radius=20)
            self.text('GO!',(400,159),72,WHITE)
        if self.reflex_start and (self.state=='countdown' or
                                  (self.state=='race' and self.elapsed<REACTION_WINDOW)):
            self.draw_reflex_buttons()
        if self.paused:
            panel=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
            panel.fill((11,19,37,185));self.canvas.blit(panel,(0,0))
            self.text('PAUSED',(400,230),72,YELLOW)
            self.button((250,322,300,80),'RESUME',('pause',None),selected=True,size=38)
        elif self.state=='race':
            self.button((668,11,120,48),'PAUSE',('pause',None),size=22)

    def draw_lights(self):
        r=pygame.Rect(209,181,382,192)
        pygame.draw.rect(self.canvas,(22,28,43),r,border_radius=30)
        pygame.draw.rect(self.canvas,(250,219,148),r,5,border_radius=30)
        # One new red light per second, then race begins at GREEN_AT.
        stages=min(3,int(self.countdown)+1)
        for i in range(3):
            active=stages>=i+1
            c=(240,65,71) if active else (75,42,48)
            pygame.draw.circle(self.canvas,(8,12,24),(285+i*115,272),42)
            pygame.draw.circle(self.canvas,c,(285+i*115,272),34)
            if active:pygame.draw.circle(self.canvas,(255,183,153),(276+i*115,263),9)
        self.text(f'{max(1,math.ceil(GREEN_AT-self.countdown))}',(400,358),56,YELLOW)

    def draw_reflex_buttons(self):
        """Large, independent, color-coded buttons for 1–4 local players."""
        gap=10
        width=min(182,int((766-(self.players-1)*gap)/self.players))
        total=self.players*width+(self.players-1)*gap
        left=(LOGICAL_W-total)//2
        for player in range(self.players):
            rect=(left+player*(width+gap),454,width,79)
            color=PALETTE[self.kart_ids[player]]
            status=self.reaction_status[player]
            if status=='early':label=f'P{player+1} EARLY'
            elif status=='boost':label=f'P{player+1} BOOST!'
            elif status=='late':label=f'P{player+1} OK'
            else:label=f'P{player+1} TAP!'
            disabled=status!='waiting'
            # Retain each player's color after a press; do not gray out the button.
            self.button(rect,label,('reflex_press',player) if not disabled else None,
                        color=color,selected=False,size=25)
        if self.state=='countdown':
            self.text('WAIT FOR GREEN!',(400,431),27,YELLOW)
        else:
            self.text('TAP NOW FOR A BOOST!',(400,431),27,YELLOW)

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
            champions=self.cup_winners() if final else []
            self.text(('CUP CHAMPIONS!' if len(champions)>1 else 'CUP CHAMPION!')
                      if final else 'RACE FINISHED!',(400,43),56,YELLOW)
            subtitle=f'{self.catalog["cups"][self.cup]}  -  RACE {self.cup_stage+1} / 4'
            self.text(subtitle,(400,90),28,WHITE)
            if final and champions:
                if len(champions)==1:
                    champion=champions[0]
                    self.text(f'PLAYER {champion+1} TAKES THE CUP!',(400,129),35,
                              PALETTE[self.kart_ids[champion]])
                elif len(champions)==self.players:
                    self.text('ALL PLAYERS SHARE THE CUP!',(400,129),34,YELLOW)
                else:
                    names=[str(i+1) for i in champions]
                    winners=', '.join(names[:-1])+' & '+names[-1]
                    self.text(f'PLAYERS {winners} SHARE THE CUP!',(400,129),30,YELLOW)
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
                place=self.cup_rank(who)
                self.text(f'{place}.',(450,y),30,YELLOW if place==1 else WHITE)
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
            self.text(f'{self.track.name}  -  {self.laps} LAP'+('S' if self.laps>1 else ''),(400,119),30,WHITE)
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
                else:self.text('Your first race on this track!',(400,477),26,MUTED)
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
        """Sort by championship points; player number only stabilizes display order.

        Equal points always mean an equal place. Lap times do not break ties.
        """
        return sorted(range(self.players), key=lambda i:(-self.cup_scores[i],i))

    def cup_rank(self, player):
        """Competition rank: 30, 30, 18 points => places 1, 1, 3."""
        return 1 + sum(self.cup_scores[other] > self.cup_scores[player]
                       for other in range(self.players))

    def cup_winners(self):
        """All players tied for the highest point total share the cup."""
        if self.players < 1:
            return []
        best=max(self.cup_scores[:self.players])
        return [i for i in range(self.players) if self.cup_scores[i]==best]

    def go_ready(self):
        self.state='ready'
        self.draft=[]
        self.drawn_laps=[]
        self.draw_lap_distance=0.0
        self.draw_pointer=None

    def new_lap_timer(self):
        # Timer is per lap, so selecting three laps never forces a child
        # to draw three circuits in the time intended for just one.
        self.time_left=None if self.draw_seconds is None else float(self.draw_seconds)

    def begin_draw(self):
        self.state='draw'
        self.drawn_laps=[]
        self.draw_lap_distance=0.0
        self.new_lap_timer()
        self.draft=[tuple(self.track.centerline[0])]
        self.draw_pointer=None

    def append_draft(self,xy):
        """Record input and notice each REAL return to the finish marker."""
        if self.state!='draw' or not self.draft:
            return
        if len(self.draft)>=1250 or length(self.draft[-1],xy)<8:
            return
        previous=self.draft[-1]
        self.draft.append(xy)
        self.draw_lap_distance+=length(previous,xy)
        circumference=self.track.centerline_route.length
        if (self.draw_lap_distance>=circumference*.65 and
                segment_near_point(previous,xy,self.track.centerline[0])<34):
            # A route can pass the flag several times: one actual drawn
            # circuit at a time. Gate distance prevents repeated tap loops.
            self.seal_lap(reached_flag=True)

    def seal_lap(self,reached_flag=False):
        """Close one hand-drawn lap; move to drawing the NEXT distinct lap."""
        if self.state!='draw':
            return
        raw=list(self.draft)
        if reached_flag:
            # Exact shared junction between loops, independent of touch jitter.
            if length(raw[-1],self.track.centerline[0])>0.5:
                raw.append(tuple(self.track.centerline[0]))
            else:
                raw[-1]=tuple(self.track.centerline[0])
        self.drawn_laps.append(raw)
        self.draw_lap_distance=0.0
        if len(self.drawn_laps)<self.laps:
            # Keep the finger active across the start line for a truly
            # uninterrupted three-lap drawing; a lift is also allowed.
            self.draft=[tuple(self.track.centerline[0])]
            self.new_lap_timer()
            return
        # All requested laps are uniquely drawn. Build one continuous spline.
        self.draw_pointer=None
        points,boundaries=combine_drawn_laps(self.drawn_laps,self.track.centerline)
        self.routes.append(Route(points,boundaries))
        self.draw_player+=1
        if self.draw_player>=self.players:
            self.begin_countdown()
        else:
            self.go_ready()

    def finish_draw(self):
        # A DONE press or timeout finishes only the CURRENT drawing lap,
        # not an entire three-lap race. Partial laps connect straight to flag.
        self.seal_lap(reached_flag=False)

    def begin_countdown(self):
        self.state='countdown'
        self.countdown=0.0
        self.elapsed=0.0
        self.paused=False
        self.new_best=False
        self.ghost_target_time=None
        self.racers=[Racer(i,self.kart_ids[i],self.routes[i],laps=self.laps)
                     for i in range(self.players)]
        # Respawn each box for each new race; all players share each box.
        for box in self.pickups:
            box.hidden_until=0.0
            box.picked_at=-100.0
        self.reaction_status=['waiting']*self.players
        self.reaction_times=[None]*self.players
        self.active_ghost=None
        if self.players==1:
            record=self.ghost_records.get(self.ghost_key())
            if record is not None:
                self.ghost_target_time=record['time']
                self.active_ghost=Racer(-1,record['kart_id'],Route(record['points'],record.get('lap_boundaries')),True,laps=self.laps)
                self.active_ghost.ghost_reaction=record.get('reaction')
                self.active_ghost.ghost_powerups=list(record.get('powerup_uses',[]))
        # Cached cropped route spans: only the current span is dynamically
        # drawn each frame, and traveled geometry is never displayed again.
        self.race_routes_layer=None
        self.race_trails=[]
        if self.show_racing_lines:
            if self.active_ghost is not None:
                self.race_trails.append((self.active_ghost,AheadTrail(
                    self.active_ghost.route,(176,194,218),self.world_to_screen,ghost=True)))
            for racer in self.racers:
                self.race_trails.append((racer,AheadTrail(
                    racer.route,PALETTE[racer.kart_id],self.world_to_screen)))

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

    def ghost_key(self):
        # Runs with power-ups ON are not compared with item-free time trials.
        return (self.cup*4+self.track_index,self.laps,
                bool(self.powerups_enabled),bool(self.reflex_start))

    def try_collect_powerups(self, racer, previous):
        """Fast moving karts cannot skip a box between two 60FPS frames."""
        if not self.powerups_enabled or racer.is_ghost or racer.finished:
            return
        for box in self.pickups:
            if (box.available(self.elapsed) and
                    segment_near_point(previous,racer.pos,box.pos)<=POWERUP_PICKUP_RADIUS):
                box.collect(self.elapsed)
                if racer.held_powerup is None:
                    racer.held_powerup=self.rng.choice(('turbo','tailwind'))
                # If the kart is already carrying an item, the box STILL
                # despawns but the existing inventory is never replaced.

    def activate_held_powerup(self, player):
        if (not self.powerups_enabled or self.state!='race' or self.paused or
                not 0<=player<len(self.racers)):
            return False
        # Reuse the same button as the reflex test AFTER its timing window.
        if self.reflex_start and self.elapsed<REACTION_WINDOW:
            return False
        return self.racers[player].activate_powerup(self.elapsed)

    def finish_race(self):
        self.state='results'
        # A frozen finish order is used to award 9/6/3/1 exactly once.
        order=sorted(self.racers,key=lambda r:(r.finish_time if r.finish_time is not None else 1e9,r.index))
        if self.race_mode=='cup':
            for place,r in enumerate(order):self.cup_scores[r.index]+=CUP_POINTS[place]
            self.cup_history.append([next(r.finish_time for r in self.racers if r.index==i) for i in range(self.players)])
        # Ghost is the best previous race in this session, not stored on disk.
        if self.players==1:
            key=self.ghost_key()
            r=self.racers[0]
            best=self.ghost_records.get(key)
            if best is None or r.finish_time<best['time']:
                self.ghost_records[key]={'time':r.finish_time,'points':list(r.route.points),
                                         'lap_boundaries':list(r.route.lap_boundaries),
                                         'kart_id':r.kart_id,'reaction':self.reaction_times[0],
                                         'powerup_uses':list(r.used_powerups)}
                self.new_best=True
        self.celebrate()

    def press_reflex(self, player):
        """Register one press per player; a miss never blocks the race.

        Before green: short false-start penalty. After green: reaction-sized
        boost, with no penalty for a child who never presses.
        """
        if not self.reflex_start or not 0<=player<self.players:
            return
        if self.state not in ('countdown','race'):
            return
        if not self.reaction_status or self.reaction_status[player]!='waiting':
            return
        if self.state=='countdown' and self.countdown<GREEN_AT:
            reaction=-1.0
            self.reaction_status[player]='early'
        else:
            reaction=max(0.0,self.elapsed) if self.state=='race' else 0.0
            if reaction>REACTION_WINDOW:
                return
            self.reaction_status[player]='boost'
        self.reaction_times[player]=reaction
        self.racers[player].apply_start_reaction(reaction)

    def handle_button(self,action):
        name,value=action
        if name=='home':self.running=False
        elif name=='mode':self.race_mode=value
        elif name=='players':self.players=value;self.kart_player=0
        elif name=='time':self.draw_seconds=value
        elif name=='laps':self.laps=value
        elif name=='reflex':self.reflex_start=bool(value)
        elif name=='powerups':self.powerups_enabled=bool(value)
        elif name=='lines':self.show_racing_lines=bool(value)
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
        elif name=='reflex_press':self.press_reflex(value)
        elif name=='powerup_press':self.activate_held_powerup(value)
        elif name=='start_draw':self.begin_draw()
        elif name=='clear':
            self.draft=[self.track.centerline[0]]
            self.draw_lap_distance=0.0
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
            self.append_draft(self.screen_to_world(pos))

    def finger_motion(self,pointer,pos):
        if self.state=='draw' and self.draw_pointer==pointer:
            xy=self.screen_to_world(pos)
            self.append_draft(xy)

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
            elif event.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):
                # Desktop accessibility/testing: number keys mirror each
                # player's colored action button (iPad still uses touch).
                player=event.key-pygame.K_1
                if self.state=='countdown' or (self.reflex_start and self.state=='race'
                                                and self.elapsed<REACTION_WINDOW):
                    self.press_reflex(player)
                else:self.activate_held_powerup(player)
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
        self.item_box_clock+=dt
        if self.state=='draw':
            if self.time_left is not None:
                self.time_left-=dt
                if self.time_left<=0:self.finish_draw()
        elif self.state=='countdown':
            if not self.paused:
                self.countdown+=dt
                if self.countdown>=GREEN_AT:
                    self.state='race'
                    self.elapsed=0.0
        elif self.state=='race':
            if not self.paused:
                self.elapsed+=dt
                for racer in self.racers:
                    before=racer.pos
                    racer.update(dt,self.elapsed,self.track)
                    self.try_collect_powerups(racer,before)
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
