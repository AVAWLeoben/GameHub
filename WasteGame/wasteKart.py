"""WasteKart 2.7.0 - Rainbow Rocket, Star Cup 4/4, layered Cog Chompers and scaling.

Pygame-ce / Pygbag compatible GameHub entry point:
    await wasteKart.main(screen, clock)

Original four-cup, sixteen-course art resides in assets/WasteKart.
Races retain all original courses. Stars 1-3 have custom sprite hazards.
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
# A permanent, large circular amulet is allocated to each player. Coordinates
# are IDENTICAL on kart selection, route drawing, countdown and race screens.
# Retain the original buttons' centers so existing muscle memory still works.
AMULET_RADIUS = 39
AMULET_TOUCH_RADIUS = 41
PLAYER_AMULETS = (
    (TRACK_RECT.left + 74, TRACK_RECT.top + 45),    # P1: upper left
    (TRACK_RECT.right - 74, TRACK_RECT.top + 45),   # P2: upper right
    (TRACK_RECT.left + 74, TRACK_RECT.bottom - 45), # P3: lower left
    (TRACK_RECT.right - 74, TRACK_RECT.bottom - 45) # P4: lower right
)
# The original 56x42 karts looked oversized in four-player races. 38x28 is
# 68% of that footprint (about 50% *too large* means divide by 1.5).
RACE_KART_SIZE = (38, 28)
# Gameplay is world-coordinate based; these are NOT the sprite's pixel sizes.
DRAFT_MIN = 26.0
DRAFT_MAX = 102.0
DRAFT_HALF_WIDTH = 25.0
DRAFT_SPEED_FACTOR = 1.13
BUMP_DISTANCE = 29.0
BUMP_COOLDOWN = 0.65
BUMP_EFFECT_SECONDS = 0.44
BUMP_MIN_TIME = 1.0  # No impacts among karts still gathered at the starting grid.


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


def point_segment_projection(a,b,p):
    """Return distance, normalized t and closest point on segment a-b."""
    dx=b[0]-a[0];dy=b[1]-a[1]
    span=dx*dx+dy*dy
    t=clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/span,0,1) if span>1e-7 else 0.0
    closest=lerp(a,b,t)
    return length(closest,p),t,closest


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
        # Optional independent moving train hazard (no effect on other tracks).
        train_rel=data.get('train_manifest')
        self.train_manifest_path=(os.path.join(ASSET_ROOT,*train_rel.split('/'))
                                  if train_rel else None)
        tunnel_rel=data.get('train_tunnel_overlay')
        self.train_tunnel_overlay_path=(os.path.join(ASSET_ROOT,*tunnel_rel.split('/'))
                                         if tunnel_rel else None)
        # Independent cactus lane hazards; the manifest supplies the sprite,
        # lane and collision geometry. Only Cactus Corner opts in.
        cactus_rel=data.get('cactus_manifest')
        self.cactus_manifest_path=(os.path.join(ASSET_ROOT,*cactus_rel.split('/'))
                                  if cactus_rel else None)
        self.overlay_path=None
        overlay_rel=data.get('overlay_image')
        if overlay_rel:
            self.overlay_path=os.path.join(ASSET_ROOT,*overlay_rel.split('/'))
        self.overpasses=[]
        for bridge in data.get('overpasses',[]):
            a=tuple(bridge['a'])
            b=tuple(bridge['b'])
            width=float(bridge.get('width',self.road_half_width*2.0))
            tolerance=math.radians(float(bridge.get('heading_tolerance_degrees',42.0)))
            self.overpasses.append({'a':a,'b':b,'width':width,'tolerance':tolerance})
        gorge_rel=data.get('golden_gorge_manifest')
        self.gorge_manifest_path=(os.path.join(ASSET_ROOT,*gorge_rel.split('/'))
                                   if gorge_rel else None)
        canyon_rel=data.get('canyon_manifest')
        self.canyon_manifest_path=(os.path.join(ASSET_ROOT,*canyon_rel.split('/'))
                                   if canyon_rel else None)
        self.canyon_data=None
        self.canyon_masks={}
        self.canyon_bridges=[]
        self.canyon_hazards=None
        if self.canyon_manifest_path:
            with open(self.canyon_manifest_path,encoding='utf8') as source:
                self.canyon_data=json.load(source)
            base=os.path.dirname(self.canyon_manifest_path)
            for key,relative in self.canyon_data['masks'].items():
                self.canyon_masks[key]=pygame.image.load(
                    os.path.join(base,*relative.split('/'))).convert()
            for key,relative in (('ramp',self.canyon_data['jump']['ramp_mask']),
                                  ('landing',self.canyon_data['jump']['landing_mask'])):
                self.canyon_masks[key]=pygame.image.load(
                    os.path.join(base,*relative.split('/'))).convert()
            for deck in self.canyon_data['bridges'].values():
                if isinstance(deck,dict) and 'deck_bbox_px' in deck:
                    x1,y1,x2,y2=deck['deck_bbox_px']
                    self.canyon_bridges.append(pygame.Rect(
                        int(x1),int(y1),math.ceil(x2-x1),math.ceil(y2-y1)))
        # Star Cup 1: independent haunted boardwalk masks and animations.
        phantom_rel=data.get('phantom_manifest')
        self.phantom_manifest_path=(os.path.join(ASSET_ROOT,*phantom_rel.split('/'))
                                    if phantom_rel else None)
        self.phantom_data=None
        self.phantom_masks={}
        self.phantom_hazards=None
        if self.phantom_manifest_path:
            with open(self.phantom_manifest_path,encoding='utf8') as source:
                self.phantom_data=json.load(source)
            base=os.path.dirname(self.phantom_manifest_path)
            for key,relative in self.phantom_data['files'].items():
                if key in ('fall_zone_mask','ground_slow_mask','rail_wall_mask'):
                    self.phantom_masks[key]=pygame.image.load(
                        os.path.join(base,*relative.split('/'))).convert()
        # Star Cup 2/4: illuminated garden, animated fairies and tunnel roof.
        glow_rel=data.get('glow_manifest')
        self.glow_manifest_path=(os.path.join(ASSET_ROOT,*glow_rel.split('/'))
                                  if glow_rel else None)
        self.glow_data=None
        self.glow_hazards=None
        if self.glow_manifest_path:
            with open(self.glow_manifest_path,encoding='utf8') as source:
                self.glow_data=json.load(source)
        # Star Cup 3/4: at-grade star crossing, ribbon-tailed cats.
        spiral_rel=data.get('spiral_manifest')
        self.spiral_manifest_path=(os.path.join(ASSET_ROOT,*spiral_rel.split('/'))
                                    if spiral_rel else None)
        self.spiral_data=None
        self.spiral_hazards=None
        if self.spiral_manifest_path:
            with open(self.spiral_manifest_path,encoding='utf8') as source:
                self.spiral_data=json.load(source)
        # Star Cup 4/4: authored perspective, two overpasses and space fall zone.
        rocket_rel=data.get('rocket_manifest')
        self.rocket_manifest_path=(os.path.join(ASSET_ROOT,*rocket_rel.split('/'))
                                   if rocket_rel else None)
        self.rocket_data=None
        self.rocket_masks={}
        self.rocket_samples=[]
        self.rocket_s=[]
        self.rocket_grid={}
        self.rocket_hazards=None
        if self.rocket_manifest_path:
            with open(self.rocket_manifest_path,encoding='utf8') as source:
                self.rocket_data=json.load(source)
            base=os.path.dirname(self.rocket_manifest_path)
            for key in ('road_layer0','road_layer1_deck','road_all','fall_zone'):
                self.rocket_masks[key]=pygame.image.load(os.path.join(
                    base,*self.rocket_data['files'][key].split('/'))).convert()
            with open(os.path.join(base,self.rocket_data['files']['width_profile']),
                      encoding='utf8') as source:
                profile=json.load(source)
            self.rocket_samples=profile['samples']
            self.rocket_s=[float(a['s']) for a in self.rocket_samples]
            self.rocket_length=float(profile['lap_length_px'])
            # Compact spatial lookup: ~438 samples in 50px buckets. A heading
            # match disambiguates the two roads at each figure-eight crossing.
            for i,a in enumerate(self.rocket_samples):
                key=(int(a['x'])//50,int(a['y'])//50)
                self.rocket_grid.setdefault(key,[]).append(i)
        self.pickup_positions=self.find_pickup_positions()

    def on_road(self,point):
        x,y=int(point[0]),int(point[1])
        if not (0<=x<MAP_W and 0<=y<MAP_H):return False
        # A single O(1) lookup, even with four karts on iPad.
        if self.mask.get_at((x,y))[0] <= 127:
            return False
        # Comet Canyon's existing craters are slow like sand, not fast asphalt.
        if self.canyon_mask('permanent_crater_slow',point):
            return False
        return True

    def rocket_at_s(self,distance):
        """Linear interpolation of the authored kart-scale and height profile."""
        if not self.rocket_samples:return (1.0,0,0.0,43.0)
        s=float(distance)%self.rocket_length
        i=max(0,min(len(self.rocket_samples)-2,bisect.bisect_right(self.rocket_s,s)-1))
        a,b=self.rocket_samples[i:i+2]
        t=clamp((s-a['s'])/max(1e-6,b['s']-a['s']),0,1)
        f=lambda key:float(a[key])+(float(b[key])-float(a[key]))*t
        # Layers change at authored boundaries, not during interpolation.
        return (f('kart_scale'),int(a['layer'] if t<.5 else b['layer']),
                f('elevation'),f('half_width'))

    def rocket_nearest(self,point,heading=None):
        """Return track arc distance and local transverse gap, not screen depth.

        Heading is important: the same world pixel can be on two independently
        usable strands at the flat projection of an overpass.
        """
        if not self.rocket_samples:return (0.0,1e6)
        bx,by=int(point[0])//50,int(point[1])//50
        indices=[]
        for dx in (-2,-1,0,1,2):
            for dy in (-2,-1,0,1,2):
                indices.extend(self.rocket_grid.get((bx+dx,by+dy),()))
        if not indices:
            indices=range(len(self.rocket_samples))
        best=(float('inf'),0.0,1e6)
        for i in indices:
            a=self.rocket_samples[i]
            gap=math.hypot(a['x']-point[0],a['y']-point[1])
            turn=0.0
            if heading is not None:
                angle=math.atan2(a['ty'],a['tx'])
                turn=abs(angle_delta(heading,angle))
            # A perpendicular underpass must not become the nearest *route* just
            # because a drawn kart arrives 3px closer to the wrong strand.
            score=gap+turn*19.0
            if score<best[0]:best=(score,float(a['s']),gap)
        return (best[1],best[2])

    def rocket_state(self,point,heading=None):
        if not self.rocket_samples:return (0,1.0,0.0,43.0)
        distance,gap=self.rocket_nearest(point,heading)
        scale,layer,height,half_width=self.rocket_at_s(distance)
        return (layer,scale,height,half_width)

    def rocket_fall(self,point,heading=None):
        if not self.rocket_data:return False
        x,y=int(point[0]),int(point[1])
        if not (0<=x<MAP_W and 0<=y<MAP_H):return True
        layer,_,_,_=self.rocket_state(point,heading)
        key='road_layer1_deck' if layer else 'road_layer0'
        # An outside-road stroke is a fall, never a grass slowdown.
        return self.rocket_masks[key].get_at((x,y))[0]<=127

    def canyon_mask(self,key,point):
        surface=self.canyon_masks.get(key)
        if surface is None:return False
        x,y=int(point[0]),int(point[1])
        return (0<=x<MAP_W and 0<=y<MAP_H and
                surface.get_at((x,y))[0]>127)

    def canyon_bridge(self,point):
        # The supplied fall-zone mask already excludes the deck surfaces.
        # Keep an explicit deck check for safety at anti-aliased edges.
        return any(r.collidepoint((int(point[0]),int(point[1]))) for r in self.canyon_bridges) and \
               self.mask.get_at((int(clamp(point[0],0,MAP_W-1)),
                                 int(clamp(point[1],0,MAP_H-1))))[0]>127

    def phantom_mask(self,key,point):
        surface=self.phantom_masks.get(key)
        if surface is None:return False
        x,y=int(point[0]),int(point[1])
        return (0<=x<MAP_W and 0<=y<MAP_H and
                surface.get_at((x,y))[0]>127)

    def canyon_fall(self,point,heading=None):
        # Shared fall/rescue interface; Comet Canyon keeps its bridge protection.
        if self.rocket_data is not None:
            return self.rocket_fall(point,heading)
        if self.phantom_data is not None:
            return self.phantom_mask('fall_zone_mask',point)
        return self.canyon_mask('fall_zone',point) and not self.canyon_bridge(point)

    def has_overpasses(self):
        return bool(self.overpasses or self.canyon_bridges or self.rocket_data)

    def point_on_overpass(self, point, heading=None):
        if self.rocket_data:
            dist,gap=self.rocket_nearest(point,heading)
            scale,layer,z,half_width=self.rocket_at_s(dist)
            return bool(layer and gap<=half_width+12)
        if self.canyon_bridges and self.canyon_bridge(point):
            return True
        for bridge in self.overpasses:
            dist,t,_=point_segment_projection(bridge['a'],bridge['b'],point)
            if not (0.0 <= t <= 1.0):
                continue
            if dist > bridge['width']*0.48:
                continue
            if heading is None:
                return True
            bridge_angle=math.atan2(bridge['b'][1]-bridge['a'][1], bridge['b'][0]-bridge['a'][0])
            if abs(angle_delta(heading, bridge_angle)) <= bridge['tolerance']:
                return True
        return False

    def segment_layer(self, a, b):
        if not self.has_overpasses():
            return 0
        heading=math.atan2(b[1]-a[1], b[0]-a[0])
        mid=((a[0]+b[0])*0.5, (a[1]+b[1])*0.5)
        return 1 if self.point_on_overpass(mid, heading) else 0

    def find_pickup_positions(self):
        """Offset boxes from the ideal line but keep them ON the road.

        Fixed fractions and alternating sides mean predictable, fair positions
        across all drawing turns and a replay. Road mask validates each site.
        """
        route=self.centerline_route
        spots=[]
        for slot,fraction in enumerate((.09,.21,.34,.47,.60,.73,.86)):
            side=1 if slot%2==0 else -1
            found=None
            # Only bridge tracks need alternate fractions. Never place a box
            # right inside the two-level crossing where it would be ambiguous.
            for offset in ((0,.025,-.025,.055,-.055) if self.overpasses else (0,)):
                p,angle,_=route.sample(route.length*((fraction+offset)%1.0))
                nx,ny=-math.sin(angle),math.cos(angle)
                for sign in (side,-side):
                    for factor in (.77,.71,.65):
                        lateral=self.road_half_width*factor*sign
                        candidate=(p[0]+nx*lateral,p[1]+ny*lateral)
                        crossing_conflict=any(
                            length(candidate,((bridge['a'][0]+bridge['b'][0])*.5,
                                              (bridge['a'][1]+bridge['b'][1])*.5))<115
                            for bridge in self.overpasses)
                        if (28<candidate[0]<MAP_W-28 and
                                28<candidate[1]<MAP_H-28 and
                                not crossing_conflict and
                                (not self.canyon_data or not (190<candidate[0]<355)) and
                                self.on_road(candidate) and
                                all(length(candidate,other)>70 for other in spots)):
                            found=candidate
                            break
                    if found is not None:break
                if found is not None:break
            if found is not None:spots.append(found)
        return spots


class MovingTrain:
    """One westbound, continuously moving consist; geometry uses world px.

    Sprite centers, coupler spacing, portals and crossing positions are taken
    directly from the user-provided train_manifest.json. Images are scaled only
    once on load. Collision is positional; the train itself never slows down.
    """
    SPEED=118.0               # px/sec, westbound on 960x600 map
    RETURN_MARGIN=130.0       # time between trains after tail has left view
    KART_HALF_COLLISION=12.0 # generous for young players without early hits
    STUN_SECONDS=1.45
    HIT_IMMUNITY=3.7

    def __init__(self, track):
        assert track.train_manifest_path
        with open(track.train_manifest_path,encoding='utf8') as stream:
            self.manifest=json.load(stream)
        self.base=os.path.dirname(track.train_manifest_path)
        self.rail_y=float(self.manifest['rail']['y'])
        self.hidden_x=tuple(float(v) for v in self.manifest['tunnel']['hidden_between_x'])
        self.names=list(self.manifest['suggested_consist'])
        self.specs=self.manifest['sprites']
        self.gap=float(self.manifest['coupler_gap_px'])
        self.crossings=[tuple(float(v) for v in record['x_range'])
                        for record in self.manifest['road_crossings']]
        self.offsets=[]
        offset=0.0
        last=None
        for name in self.names:
            if last is not None:
                offset+=(self.specs[last]['body_length_px']+
                         self.specs[name]['body_length_px'])*.5+self.gap
            self.offsets.append(offset)
            last=name
        self.tail_length=self.offsets[-1]+self.specs[self.names[-1]]['body_length_px']*.5
        self.sprites=[]
        sx=TRACK_RECT.width/MAP_W
        sy=TRACK_RECT.height/MAP_H
        for name in self.names:
            record=self.specs[name]
            frames=[]
            for relative in (record['shadow'],record['file']):
                sprite=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
                size=(max(1,round(sprite.get_width()*sx)),
                      max(1,round(sprite.get_height()*sy)))
                frames.append(pygame.transform.smoothscale(sprite,size))
            self.sprites.append(tuple(frames))
        self.puffs=[]
        for relative in self.manifest.get('smoke_puffs',()):
            sprite=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
            size=(max(1,round(sprite.get_width()*sx)),
                  max(1,round(sprite.get_height()*sy)))
            self.puffs.append(pygame.transform.smoothscale(sprite,size))
        self.tunnel_overlay=None
        self.tunnel_xy=TRACK_RECT.topleft
        if track.train_tunnel_overlay_path:
            source=pygame.image.load(track.train_tunnel_overlay_path).convert_alpha()
            # Crop sparse tunnel art once: ~170x95 instead of blending an
            # almost-transparent 740x462 canvas every frame on an iPad.
            bounding=source.get_bounding_rect(min_alpha=1)
            if bounding.width>0 and bounding.height>0:
                cropped=source.subsurface(bounding).copy()
                sw=max(1,round(bounding.width*sx))
                sh=max(1,round(bounding.height*sy))
                self.tunnel_overlay=pygame.transform.smoothscale(cropped,(sw,sh))
                self.tunnel_xy=(TRACK_RECT.left+round(bounding.left*sx),
                                TRACK_RECT.top+round(bounding.top*sy))
        self.reset()

    def reset(self):
        # The locomotive enters shortly after green instead of already being
        # on a crossing while the children are waiting for the start lights.
        self.loco_x=MAP_W+415.0
        self.time=0.0

    def update(self,dt):
        self.time+=dt
        self.loco_x-=self.SPEED*dt
        if self.loco_x+self.tail_length < -24:
            self.loco_x=MAP_W+self.RETURN_MARGIN

    def car_positions(self):
        for name,offset in zip(self.names,self.offsets):
            yield name,self.loco_x+offset

    def hidden(self,x):
        return self.hidden_x[0]<x<self.hidden_x[1]

    def hit_test(self,kart_pos):
        """A car hits a real racer anywhere its physical track is exposed.

        A child can draw across the railway even off-road; such a shortcut
        must not bypass the hazard. No collision occurs under solid tunnel art.
        """
        x,y=kart_pos
        if self.hidden(x):
            return False
        for name,car_x in self.car_positions():
            spec=self.specs[name]
            if (abs(x-car_x)<=spec['body_length_px']*.5+self.KART_HALF_COLLISION
                    and abs(y-self.rail_y)<=spec['body_width_px']*.5+self.KART_HALF_COLLISION):
                return True
        return False

    def draw_crossing_signals(self,canvas,to_screen):
        """Flashing red crossing lights warn children before the train arrives."""
        for lo,hi in self.crossings:
            middle=(lo+hi)*.5
            approaching=(self.loco_x<=middle+220 and
                         self.loco_x+self.tail_length>=middle-35)
            if not approaching:
                continue
            bright=(int(self.time*5)%2)==0
            for side,x in enumerate((lo-14,hi+14)):
                xy=to_screen((x,self.rail_y-23))
                center=(round(xy[0]),round(xy[1]))
                color=(255,83,79) if bright==bool(side) else (114,55,56)
                pygame.draw.circle(canvas,(33,31,42),center,7)
                pygame.draw.circle(canvas,color,center,5)
                if color[0]>200:
                    pygame.draw.circle(canvas,(255,202,159),center,2)

    def draw(self,canvas,to_screen):
        """Track -> train shadows -> cars -> optional smoke -> tunnel overlay."""
        old_clip=canvas.get_clip()
        canvas.set_clip(TRACK_RECT)
        self.draw_crossing_signals(canvas,to_screen)
        car_positions=list(self.car_positions())
        # Render shadows first, so every car has the expected grounded look.
        for index,(name,car_x) in enumerate(car_positions):
            if -35<=car_x<=MAP_W+35:
                surf=self.sprites[index][0]
                xy=to_screen((car_x,self.rail_y))
                canvas.blit(surf,surf.get_rect(center=(round(xy[0]),round(xy[1]))))
        for index,(name,car_x) in enumerate(car_positions):
            if -35<=car_x<=MAP_W+35:
                surf=self.sprites[index][1]
                xy=to_screen((car_x,self.rail_y))
                canvas.blit(surf,surf.get_rect(center=(round(xy[0]),round(xy[1]))))
        # A few tiny puffs use cached art, not new surfaces every frame.
        if self.puffs and -15 < self.loco_x < MAP_W+15:
            for index,age in enumerate((.18,.56,1.0)):
                smoke_x=self.loco_x+12.5+self.SPEED*age*.42
                smoke_y=self.rail_y-13-age*19
                if self.hidden(smoke_x):
                    continue
                surf=self.puffs[min(index,len(self.puffs)-1)]
                xy=to_screen((smoke_x,smoke_y))
                canvas.blit(surf,surf.get_rect(center=(round(xy[0]),round(xy[1]))))
        if self.tunnel_overlay is not None:
            canvas.blit(self.tunnel_overlay,self.tunnel_xy)
        canvas.set_clip(old_clip)


class CactusLaneHazards:
    """Three staggered desert track hazards with shared safe-crossing gaps.

    The supplied cactus_manifest.json defines each lane, sprite anchor,
    collision radius and speed. Two saguaros use alternating walking frames;
    a barrel rolls through the middle lane. Only one lane traverses the road
    at a time, so children always have a safe opportunity to cross.
    """
    KART_RADIUS=10.0
    REST_SECONDS=0.95
    START_DELAY=0.65

    def __init__(self,track):
        with open(track.cactus_manifest_path,encoding='utf8') as source:
            self.manifest=json.load(source)
        self.base=os.path.dirname(track.cactus_manifest_path)
        specs=self.manifest['hazards']
        lanes=self.manifest['hazard_lanes']
        self.actors=[]
        sx=TRACK_RECT.width/MAP_W
        sy=TRACK_RECT.height/MAP_H
        for lane_index,lane in enumerate(lanes):
            kind='barrel_roller' if lane_index==1 else 'saguaro_walk'
            spec=specs[kind]
            file_names=(spec['frames'] if 'frames' in spec else [spec['image']])
            shadows=(spec['shadow'] if isinstance(spec['shadow'],list)
                     else [spec['shadow']])
            def load(relative):
                path=os.path.join(self.base,*relative.split('/'))
                sprite=pygame.image.load(path).convert_alpha()
                w=max(1,round(sprite.get_width()*sx))
                h=max(1,round(sprite.get_height()*sy))
                return pygame.transform.smoothscale(sprite,(w,h))
            frames=[load(relative) for relative in file_names]
            shadows=[load(relative) for relative in shadows]
            rotations=None
            if kind=='barrel_roller':
                rotations=[pygame.transform.rotate(frames[0],i*15)
                           for i in range(24)]
            self.actors.append({
                'kind':kind,'lane':lane,'spec':spec,'frames':frames,
                'shadows':shadows,'rotations':rotations,
                'speed':float(spec['suggested_speed_px_s']),
                'left':float(lane['desert_end'][0]),
                'right':float(lane['cactus_body_end'][0]),
                'y':float(lane['y']),
                'x':float(lane['desert_end'][0]),
                'direction':1,'moving':False,'angle':0.0,
            })
        self.reset()

    def reset(self):
        self.time=0.0
        self.active_lane=0
        self.rest_left=self.START_DELAY
        for lane in self.actors:
            lane['x']=lane['left']
            lane['direction']=1
            lane['moving']=False
            lane['angle']=0.0

    def update(self,dt):
        self.time+=dt
        if self.rest_left>0:
            self.rest_left=max(0.0,self.rest_left-dt)
            if self.rest_left>0:return
        actor=self.actors[self.active_lane]
        actor['moving']=True
        old_x=actor['x']
        target=actor['right'] if actor['direction']>0 else actor['left']
        actor['x']=min(target,old_x+actor['speed']*dt) if actor['direction']>0 \
                   else max(target,old_x-actor['speed']*dt)
        if actor['kind']=='barrel_roller':
            actor['angle']+=(actor['x']-old_x)/9.6
        if actor['x']==target:
            actor['moving']=False
            # Return from the far end on the next activation. The opposite
            # lanes are scheduled before this actor becomes active again.
            actor['direction']*=-1
            self.active_lane=(self.active_lane+1)%len(self.actors)
            self.rest_left=self.REST_SECONDS

    def actor_hitbox(self,actor):
        hit=actor['spec']['hitbox']
        ox,oy=hit['centre_offset']
        return (actor['x']+ox,actor['y']+oy,float(hit['radius']))

    def hit_test(self,point):
        x,y=point
        for actor in self.actors:
            cx,cy,radius=self.actor_hitbox(actor)
            if (x-cx)*(x-cx)+(y-cy)*(y-cy) <= (radius+self.KART_RADIUS)**2:
                return True
        return False

    def draw(self,canvas,to_screen):
        clip=canvas.get_clip()
        canvas.set_clip(TRACK_RECT)
        order=sorted(self.actors,key=lambda a:a['y'])
        sx=TRACK_RECT.width/MAP_W
        sy=TRACK_RECT.height/MAP_H
        # Shadows are drawn first; the user-supplied shadow files already
        # contain their intended 1px offset.
        for actor in order:
            frame=(int(self.time/actor['spec'].get('frame_time_s',.18)) % 2
                   if actor['moving'] and len(actor['frames'])>1 else 0)
            shadow=actor['shadows'][min(frame,len(actor['shadows'])-1)]
            self._blit_anchored(canvas,to_screen,actor,shadow,sx,sy)
        for actor in order:
            if actor['rotations'] is not None:
                # Barrel rotates about its center anchor.
                index=int(math.degrees(actor['angle'])/15)%24
                sprite=actor['rotations'][index]
                xy=to_screen((actor['x'],actor['y']))
                canvas.blit(sprite,sprite.get_rect(center=(round(xy[0]),round(xy[1]))))
            else:
                frame=(int(self.time/actor['spec'].get('frame_time_s',.18)) % 2
                       if actor['moving'] and len(actor['frames'])>1 else 0)
                self._blit_anchored(canvas,to_screen,actor,actor['frames'][frame],sx,sy)
        canvas.set_clip(clip)

    @staticmethod
    def _blit_anchored(canvas,to_screen,actor,image,sx,sy):
        # The actor anchor is world position; saguaros anchor at the feet.
        ax,ay=actor['spec']['anchor_px']
        x,y=to_screen((actor['x'],actor['y']))
        canvas.blit(image,(round(x-ax*sx),round(y-ay*sy)))



class GoldenGorgeLogs:
    """Downstream log traffic from the user's Golden Gorge manifest.

    Four water-animation frames are baked into the map once at load time, so
    rendering the river adds no full-screen alpha blend on every iPad frame.
    The three user-drawn log types keep their actual sprites, foam and shadows.
    Hazard collision applies ONLY inside the ford polygon, never elsewhere.
    """
    KART_RADIUS=10.0
    SPIN_SECONDS=0.9
    IMMUNITY_AFTER_SPIN=0.6
    MAX_LOGS=24

    def __init__(self,track,base_map):
        with open(track.gorge_manifest_path,encoding='utf8') as source:
            self.manifest=json.load(source)
        self.base=os.path.dirname(track.gorge_manifest_path)
        m=self.manifest
        self.flow=tuple(float(n) for n in m['gorge']['flow_direction_unit'])
        self.across=tuple(float(n) for n in m['gorge']['across_unit_vector_south_east'])
        self.origin=tuple(float(n) for n in m['gorge']['centre_line'][0])
        self.ford_polygon=[tuple(p) for p in m['crossings']['ford']['hit_zone_corners']]
        self.speeds=[float(n) for n in m['log_hazard']['speed_px_s']]
        self.lanes=[float(n) for n in m['log_hazard']['lanes_across_gorge_px']]
        self.gap_min,self.gap_max=(float(n) for n in m['log_hazard']['spawn_gap_s'])
        self.spawn_u=float(m['gorge']['spawn_at_u'])
        self.end_u=float(m['gorge']['despawn_at_u'])
        self.bob=float(m['log_hazard']['lateral_bob_px'])
        self.bob_period=float(m['log_hazard']['bob_period_s'])
        self.names=list(m['log_hazard']['sprites'])
        sx=TRACK_RECT.width/MAP_W
        sy=TRACK_RECT.height/MAP_H
        self.art={}
        for name,spec in m['log_hazard']['sprites'].items():
            def load(relative):
                path=os.path.join(self.base,*relative.split('/'))
                img=pygame.image.load(path).convert_alpha()
                size=(max(1,round(img.get_width()*sx)),max(1,round(img.get_height()*sy)))
                return pygame.transform.smoothscale(img,size)
            self.art[name]={
                'body':load(spec['flow_rotated']),
                'shadow':load(spec['shadow_flow_rotated']),
                'foam':[load(p) for p in spec['foam_flow_rotated']],
                'hitbox':spec['hitbox'],
            }
        # Precompose the four water images over the track once, removing a
        # 740x462 transparent blend from the hot draw loop.
        self.water_frames=[]
        for relative in m['water_ripples']['frames']:
            frame=base_map.copy()
            ripples=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
            ripples=pygame.transform.smoothscale(ripples,TRACK_RECT.size)
            frame.blit(ripples,(0,0))
            self.water_frames.append(frame)
        self.water_frame_seconds=float(m['water_ripples']['frame_time_s'])
        self.rng=random.Random(318731)
        self.reset()

    def reset(self):
        self.time=0.0
        self.spawn_left=2.2
        self.logs=[]
        # Place a spaced, visible initial stream throughout the gorge: a
        # child reaching the ford soon after green meets real moving logs.
        for index,u in enumerate((-55,52,145,245,340,445,543,639,737,830,935,1040,1134)):
            self.spawn(float(u),index)

    def spawn(self,u,index=None):
        if index is None:
            index=self.rng.randrange(9999)
        name=self.names[index%len(self.names)]
        log={
            'name':name, 'u':u, 'lane':self.lanes[index%len(self.lanes)],
            'speed':self.speeds[index%len(self.speeds)],
            'phase':index*1.37, 'nudge':0.0, 'nudge_dir':1.0,
        }
        self.logs.append(log)
        return log

    def update(self,dt):
        self.time+=dt
        for log in self.logs:
            log['u']+=log['speed']*dt
            if log['nudge']>0:
                log['nudge']=max(0.0,log['nudge']-8.0*dt)
        self.logs=[l for l in self.logs if l['u']<self.end_u+40.0]
        self.spawn_left-=dt
        if self.spawn_left<=0.0 and len(self.logs)<self.MAX_LOGS:
            self.spawn(self.spawn_u)
            self.spawn_left=self.rng.uniform(self.gap_min,self.gap_max)

    def position(self,log):
        shift=(log['lane']+
               self.bob*math.sin(math.tau*self.time/max(.1,self.bob_period)+log['phase'])+
               log['nudge_dir']*log['nudge'])
        return (self.origin[0]+self.flow[0]*log['u']+self.across[0]*shift,
                self.origin[1]+self.flow[1]*log['u']+self.across[1]*shift)

    @staticmethod
    def inside_polygon(point,polygon):
        x,y=point
        inside=False
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            if (a[1]>y)!=(b[1]>y):
                test_x=a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
                if x<test_x:
                    inside=not inside
        return inside

    def hit_test(self,previous,position):
        # Capsule collision, sampling the kart's swept movement so high-speed
        # updates cannot skip a moving log between adjacent frames.
        for fraction in (0.0,.25,.5,.75,1.0):
            kart=lerp(previous,position,fraction)
            if not self.inside_polygon(kart,self.ford_polygon):
                continue
            for log in self.logs:
                x,y=self.position(log)
                spec=self.art[log['name']]['hitbox']
                half=float(spec['length_px'])*0.5
                a=(x-self.flow[0]*half,y-self.flow[1]*half)
                b=(x+self.flow[0]*half,y+self.flow[1]*half)
                distance,_,_=point_segment_projection(a,b,kart)
                if distance<=float(spec['radius_px'])+self.KART_RADIUS:
                    return log
        return None

    def nudge_on_hit(self,log,kart_pos):
        # Logs keep floating; a small 4px sideways wobble shows the impact.
        x,y=self.position(log)
        side=(kart_pos[0]-x)*self.across[0]+(kart_pos[1]-y)*self.across[1]
        log['nudge_dir']=1.0 if side>=0 else -1.0
        log['nudge']=4.0

    def draw(self,canvas,to_screen):
        original_clip=canvas.get_clip()
        canvas.set_clip(TRACK_RECT)
        positioned=[]
        for log in self.logs:
            x,y=self.position(log)
            if not (-75<=x<=MAP_W+75 and -75<=y<=MAP_H+75):
                continue
            xy=to_screen((x,y))
            positioned.append((log,(round(xy[0]),round(xy[1]))))
        # Shadows, alternating foam, then solid logs. Overlay bridges are
        # drawn by WasteKart AFTER this entire hazard layer.
        for key in ('shadow','foam','body'):
            for log,point in positioned:
                sprites=self.art[log['name']]
                if key=='foam':
                    frame=int(self.time/.16+log['phase'])%len(sprites['foam'])
                    sprite=sprites['foam'][frame]
                else:
                    sprite=sprites[key]
                canvas.blit(sprite,sprite.get_rect(center=point))
        canvas.set_clip(original_clip)


class CometCanyon:
    """Comet Canyon masks, deterministic falling meteors and rescue sprites.

    960x600 world pixels throughout. Art is scaled once to the 740x462 viewport.
    Meteor timing is a repeating authored 28-second cycle, rather than random
    strikes over the bridge, jump pad, or the safe western alternative.
    """
    FALL_SECONDS=.9
    DUST_SECONDS=.40
    WAIT_SECONDS=.60
    RESCUE_SECONDS=.80
    PENALTY_SECONDS=1.20
    IMMUNITY_SECONDS=1.50

    def __init__(self,track):
        self.track=track
        self.manifest=track.canyon_data
        self.base=os.path.dirname(track.canyon_manifest_path)
        self.sx=TRACK_RECT.width/MAP_W
        self.sy=TRACK_RECT.height/MAP_H
        self.types={}
        for kind,spec in self.manifest['comet_hazard']['types'].items():
            self.types[kind]={'spec':spec,
                'comet':self.load(spec['sprite_fall_rotated']),
                'shadow':self.load(spec['shadow']),
                'impacts':[self.load(name) for name in spec['impact_frames']],
                'fresh':self.load(spec['crater_fresh']),
                'scorched':self.load(spec['crater_scorched'])}
        self.smokes=[self.load('comets/smoke/smoke_%s.png'%i) for i in range(4)]
        self.dust=[self.load('fall/dust_puff_%s.png'%i) for i in range(5)]
        self.cloud=[self.load('fall/rescue_cloud_a.png'),self.load('fall/rescue_cloud_b.png')]
        self.sparkle=[self.load('fall/respawn_sparkle_%s.png'%i) for i in range(4)]
        self.fall_shadow=self.load('fall/kart_shadow.png')
        self.events=[]
        for original in self.manifest['comet_hazard']['sample_schedule']['events']:
            event=dict(original)
            point=(event['x'],event['y'])
            if not track.canyon_mask('comet_strike_zone',point):
                # The authored fifth event is 1px outside the white mask due
                # to fractional-coordinate rounding. Keep it in its intended
                # south approach, but move that impact onto the safe white pixel.
                for radius in range(1,10):
                    candidates=((0,-radius),(-radius,0),(radius,0),(0,radius))
                    allowed=[(point[0]+dx,point[1]+dy) for dx,dy in candidates
                             if track.canyon_mask('comet_strike_zone',
                                                  (point[0]+dx,point[1]+dy))]
                    if allowed:
                        event['x'],event['y']=allowed[0]
                        break
            self.events.append(event)
        self.cycle=float(self.manifest['comet_hazard']['sample_schedule']['cycle_length_s'])
        self.warning=float(self.manifest['comet_hazard']['timeline_s']['warning_shadow_grow'])
        self.crater_cap=int(self.manifest['comet_hazard']['timeline_s']['max_active_craters'])
        self.jump_time=float(self.manifest['jump']['flight_time_s'])
        self.jump_lip=float(self.manifest['jump']['launch_lip_y'])
        self.reset()

    def load(self,rel):
        img=pygame.image.load(os.path.join(self.base,*rel.split('/'))).convert_alpha()
        return pygame.transform.smoothscale(img,(max(1,round(img.get_width()*self.sx)),
                                                 max(1,round(img.get_height()*self.sy))))

    def reset(self):
        self.time=0.0
        self.previous_time=0.0

    def update(self,dt):
        self.previous_time=self.time
        self.time+=dt

    def active_events(self):
        # A fixed-size list (<= 9*2), not an ever-growing array of meteor objects.
        cycle=int(self.time//self.cycle)
        for index in (cycle-1,cycle,cycle+1):
            if index<0:continue
            for slot,event in enumerate(self.events):
                hit=index*self.cycle+float(event['t_impact_s'])
                age=self.time-hit
                if -self.warning<=age<=7.4:
                    yield index,slot,event,age,hit

    def crater_events(self):
        # Include the preceding cycle, but retain only the last six active
        # impact points. They expire in arrival order, not all at cycle reset.
        all_events=[]
        cycle=int(self.time//self.cycle)
        for index in range(max(0,cycle-2),cycle+1):
            for slot,event in enumerate(self.events):
                hit=index*self.cycle+float(event['t_impact_s'])
                if hit<=self.time:
                    all_events.append((hit,event))
        return all_events[-self.crater_cap:]

    def speed_factor(self,pos):
        for hit,event in self.crater_events():
            radius=self.types[event['type']]['spec']['impact_radius_px']
            if length(pos,(event['x'],event['y']))<=radius:
                return .55
        for _,_,event,age,_ in self.active_events():
            if -self.warning<=age<0:
                radius=self.types[event['type']]['spec']['impact_radius_px']
                if length(pos,(event['x'],event['y']))<=radius:
                    return .70
        return 1.0

    def meteor_head(self,event,age):
        # Approaches along the original NW-to-SE falling vector.
        remaining=clamp(-age/.38,0.0,1.0)
        dx,dy=self.manifest['comet_hazard']['timeline_s']['fall_from_offset_px']
        return (event['x']+dx*remaining,event['y']+dy*remaining)

    def hit_test(self,previous,position):
        for _,_,event,age,_ in self.active_events():
            if age<-.15 or age>.10:continue
            spec=self.types[event['type']]['spec']
            radius=float(spec['impact_radius_px'])+10.0
            target=(event['x'],event['y']) if age>=0 else self.meteor_head(event,age)
            if segment_near_point(previous,position,target)<=radius:
                return event
        return None

    def checkpoint_route(self,route):
        """Match both manifest branches to the actual player's drawn spline.

        Checkpoints are repeated per lap only where the authored line passes
        near the checkpoint and faces approximately the same direction.
        Each match stores both the route distance and original map heading.
        """
        records=[]
        sets=self.manifest['fall']['respawn_points']
        lap_starts=[0.0]+list(route.lap_boundaries[:-1])
        for lap_start,lap_end in zip(lap_starts,route.lap_boundaries):
            lo=max(0,bisect.bisect_left(route.accumulated,lap_start)-1)
            hi=min(len(route.points)-1,bisect.bisect_right(route.accumulated,lap_end))
            for branch in ('short_route','long_route'):
                for cp in sets[branch]:
                    point=(float(cp['x']),float(cp['y']))
                    cp_angle=math.radians(float(cp['heading_deg_clockwise_from_east']))
                    best=None
                    for j in range(lo,hi):
                        a,b=route.points[j:j+2]
                        segment_angle=math.atan2(b[1]-a[1],b[0]-a[0])
                        if abs(angle_delta(segment_angle,cp_angle))>math.radians(55):
                            continue
                        separation,t,_=point_segment_projection(a,b,point)
                        distance=route.accumulated[j]+t*length(a,b)
                        if not (lap_start-1<=distance<=lap_end+1):continue
                        if best is None or separation<best[0]:
                            best=(separation,distance)
                    if best is not None and best[0]<28.0:
                        records.append((best[1],point,cp_angle,cp['id']))
        records.sort(key=lambda entry:entry[0])
        # On shared straights, S and L checkpoints are only 18 px apart.
        # Keep the more precisely aligned one to avoid duplicate triggers.
        matched=[]
        for candidate in records:
            if matched and abs(matched[-1][0]-candidate[0])<14.0:
                prev=matched[-1]
                dist_a=length(route.sample(prev[0])[0],prev[1])
                dist_b=length(route.sample(candidate[0])[0],candidate[1])
                if dist_b<dist_a:matched[-1]=candidate
            else:
                matched.append(candidate)
        return matched

    def closest_forward_distance(self,route,origin,destination,span=180):
        start=max(0,bisect.bisect_left(route.accumulated,origin)-1)
        stop=min(len(route.points)-1,bisect.bisect_right(route.accumulated,origin+span))
        best=(1e30,origin)
        for j in range(start,stop):
            a,b=route.points[j:j+2]
            gap,t,_=point_segment_projection(a,b,destination)
            projected=route.accumulated[j]+t*length(a,b)
            if projected>=origin-5 and gap<best[0]:best=(gap,projected)
        return best

    @staticmethod
    def blit_center(canvas,img,point):
        canvas.blit(img,img.get_rect(center=(round(point[0]),round(point[1]))))

    def draw(self,canvas,to_screen):
        clip=canvas.get_clip()
        canvas.set_clip(TRACK_RECT)
        for hit,event in self.crater_events():
            spec=self.types[event['type']]
            age=self.time-hit
            image=spec['fresh'] if age<6.0 else spec['scorched']
            self.blit_center(canvas,image,to_screen((event['x'],event['y'])))
        # Pre-impact shadow -> falling comet -> impact flash/smoke.
        for _,slot,event,age,_ in self.active_events():
            spec=self.types[event['type']]
            at=to_screen((event['x'],event['y']))
            if age<0:
                p=clamp((self.warning+age)/self.warning,0,1)
                scale=.25+.75*p*p
                shadow=spec['shadow']
                size=(max(1,round(shadow.get_width()*scale)),
                      max(1,round(shadow.get_height()*scale)))
                image=pygame.transform.smoothscale(shadow,size)
                image.set_alpha(round(102+153*p))
                self.blit_center(canvas,image,at)
                if age>-.38:
                    self.blit_center(canvas,spec['comet'],to_screen(self.meteor_head(event,age)))
            elif age<.36:
                index=min(5,int(age/.06))
                self.blit_center(canvas,spec['impacts'][index],at)
            if 0<=age<1.4:
                frame=min(3,int(age/1.4*4))
                self.blit_center(canvas,self.smokes[frame],(at[0]+9,at[1]-8-age*12))
        canvas.set_clip(clip)

    def rescue_positions(self,to_screen,racer):
        """Carry the rescued kart from the fall site to its safe forward landing."""
        at=to_screen(racer.fall_at)
        target=(to_screen(racer.rescue_target[1]) if racer.rescue_target else at)
        t=clamp(racer.fall_age/self.RESCUE_SECONDS,0.0,1.0)
        smooth=t*t*(3.0-2.0*t)
        cart=lerp((at[0],at[1]-4),(target[0],target[1]-4),smooth)
        cloud=(cart[0]+(1.0-smooth)*95,cart[1]-45-(1.0-smooth)*66)
        return cloud,cart

    def draw_rescue(self,canvas,to_screen,racer):
        if not racer.fall_phase or racer.fall_phase=='penalty':return
        at=to_screen(racer.fall_at)
        phase=racer.fall_phase
        if phase=='fall':
            shade=self.fall_shadow.copy()
            shade.set_alpha(round(200*(1-racer.fall_age/self.FALL_SECONDS)))
            self.blit_center(canvas,shade,at)
        elif phase=='dust':
            index=min(4,int(racer.fall_age/.08))
            self.blit_center(canvas,self.dust[index],at)
        elif phase=='rescue':
            cloud_point,cart=self.rescue_positions(to_screen,racer)
            pygame.draw.line(canvas,(255,241,196),cloud_point,cart,2)
            self.blit_center(canvas,self.cloud[int(self.time*8)%2],cloud_point)

    def draw_sparkles(self,canvas,to_screen,racer):
        if racer.train_immunity_left<=0 and racer.fall_phase!='penalty' and racer.respawn_fx_left<=0:return
        x,y=to_screen(racer.pos)
        if racer.fall_phase=='penalty' or racer.respawn_fx_left>0:
            elapsed=max(0,.60-racer.respawn_fx_left)
            index=min(3,int(elapsed/.15))
            self.blit_center(canvas,self.sparkle[index],(x,y))
        pygame.draw.circle(canvas,(145,255,241),(round(x),round(y)),19,2)

class PhantomBoardwalk:
    """Original authored Star Cup ghosts and swamp rescue sprites.

    All actor movement and collision use 960x600 world coordinates. The track
    overlay (mansion glass/rafters) is composited after karts and ghosts.
    """
    FALL_SECONDS=.90
    DUST_SECONDS=.40
    WAIT_SECONDS=.60
    RESCUE_SECONDS=.80
    PENALTY_SECONDS=1.20
    IMMUNITY_SECONDS=1.50
    KART_RADIUS=10.0

    def __init__(self,track):
        self.track=track
        self.manifest=track.phantom_data
        self.base=os.path.dirname(track.phantom_manifest_path)
        self.sx=TRACK_RECT.width/MAP_W
        self.sy=TRACK_RECT.height/MAP_H
        self.phase=self.manifest['ghost_phase']
        self.hit_only_solid=bool(self.phase.get('hit_only_when_solid',True))
        self.ghost_specs=self.manifest['ghost_sprites']
        self.art={}
        for kind,spec in self.ghost_specs.items():
            frames=spec['frames']
            self.art[kind]={
                'idle':[self.load(x) for x in frames['idle']],
                'chase':[self.load(x) for x in frames['chase']],
                'poof':[self.load(x) for x in frames['poof']],
                'glow':self.load(spec['glow']),
                'shadow':self.load(spec['shadow']),
                'radius':float(spec['hitbox_radius_px']),
                'bob':float(spec.get('bob_px',0)),
                'fps':float(spec.get('anim_hz',3))}
        self.dust=[self.load('fall/splash_%s.png'%i) for i in range(5)]
        self.cloud=[self.load('fall/rescue_cloud_a.png'),
                    self.load('fall/rescue_cloud_b.png')]
        self.sparkle=[self.load('fall/respawn_sparkle_%s.png'%i) for i in range(4)]
        self.fall_shadow=self.load('fall/kart_shadow.png')
        self.actors=[]
        for i,record in enumerate(self.manifest['ghosts']):
            actor=dict(record)
            actor['index']=i
            actor['route']=(Route([tuple(p) for p in record['loop_points']]+
                                  [tuple(record['loop_points'][0])])
                            if record['motion']=='loop_reverse' else
                            Route([tuple(p) for p in record['points']])
                            if record['motion']=='pingpong' else None)
            actor['pos']=(0.0,0.0)
            actor['previous']=(0.0,0.0)
            actor['poof_at']=-999.0
            self.actors.append(actor)
        self.reset()

    def load(self,rel):
        img=pygame.image.load(os.path.join(self.base,*rel.split('/'))).convert_alpha()
        return pygame.transform.smoothscale(img,(
            max(1,round(img.get_width()*self.sx)),
            max(1,round(img.get_height()*self.sy))))

    def reset(self):
        self.time=0.0
        for actor in self.actors:
            actor['poof_at']=-999.0
            actor['pos']=self.position(actor,0.0,())
            actor['previous']=actor['pos']

    def position(self,actor,at,players):
        motion=actor['motion']
        if motion=='sweep':
            period=max(.1,float(actor['period_s']))
            phase=(at+float(actor.get('phase_s',0)))/period
            u=.5-.5*math.cos(math.tau*phase)
            return lerp(actor['a'],actor['b'],u)
        if motion=='loop_reverse':
            route=actor['route']
            travelled=(max(0.0,at+float(actor.get('start_offset_s',0))) *
                       float(actor['speed_px_s']))%max(1.0,route.length)
            return route.sample(travelled)[0]
        if motion=='pingpong':
            route=actor['route']
            period=route.length*2
            d=(at*float(actor['speed_px_s']))%max(1.0,period)
            d=d if d<=route.length else 2*route.length-d
            pos=route.sample(d)[0]
            # A modest visible lunge when a kart approaches the mansion hall;
            # never let the banshee leave its authored patrol altogether.
            threshold=float(actor.get('lunge_when_kart_within_px',0))
            if threshold>0:
                for racer in players:
                    if racer.finished or racer.fall_phase or racer.flight_left>0:
                        continue
                    distance=length(pos,racer.pos)
                    if 1e-3<distance<threshold:
                        reach=min(9.0,(threshold-distance)*.23)
                        pos=lerp(pos,racer.pos,reach/distance)
                        break
            return pos
        return (0.0,0.0)

    def update(self,dt,players=()):
        self.time+=dt
        for actor in self.actors:
            actor['previous']=actor['pos']
            actor['pos']=self.position(actor,self.time,players)

    def phase_alpha(self,actor):
        cycle=float(self.phase.get('cycle_s',7.0))
        # Offset the actors so all eight do not simultaneously disappear.
        t=(self.time+actor['index']*.73)%max(.1,cycle)
        solid=float(self.phase.get('solid_s',4.6))
        fade_out=float(self.phase.get('fade_out_s',.5))
        intangible=float(self.phase.get('intangible_s',1.4))
        fade_in=float(self.phase.get('fade_in_s',.5))
        floor=float(self.phase.get('intangible_alpha',.28))
        if t<solid:return 1.0,True
        t-=solid
        if t<fade_out:
            return 1-(1-floor)*t/max(.001,fade_out),False
        t-=fade_out
        if t<intangible:return floor,False
        t-=intangible
        if t<fade_in:
            return floor+(1-floor)*t/max(.001,fade_in),False
        return 1.0,True

    def hit_test(self,previous,position):
        # Relative swept segments prevent fast karts or wisps from tunnelling
        # through each other between Pygbag frames.
        for actor in self.actors:
            if self.time-actor['poof_at']<1.0:
                continue
            alpha,solid=self.phase_alpha(actor)
            if self.hit_only_solid and not solid:
                continue
            relative0=(previous[0]-actor['previous'][0],
                       previous[1]-actor['previous'][1])
            relative1=(position[0]-actor['pos'][0],
                       position[1]-actor['pos'][1])
            if segment_near_point(relative0,relative1,(0,0)) <= \
                    self.art[actor['type']]['radius']+self.KART_RADIUS:
                return actor
        return None

    def ghost_hit(self,actor):
        actor['poof_at']=self.time

    def checkpoint_route(self,route):
        """Project fourteen authored checkpoints onto each drawn lap."""
        records=[]
        lap_starts=[0.0]+list(route.lap_boundaries[:-1])
        for lap_start,lap_end in zip(lap_starts,route.lap_boundaries):
            lo=max(0,bisect.bisect_left(route.accumulated,lap_start)-1)
            hi=min(len(route.points)-1,bisect.bisect_right(route.accumulated,lap_end))
            for cp in self.manifest['fall']['respawn_points']:
                point=(float(cp['x']),float(cp['y']))
                angle=math.radians(float(cp['heading_deg_clockwise_from_east']))
                best=None
                for j in range(lo,hi):
                    a,b=route.points[j:j+2]
                    actual=math.atan2(b[1]-a[1],b[0]-a[0])
                    if abs(angle_delta(actual,angle))>math.radians(55):continue
                    gap,t,_=point_segment_projection(a,b,point)
                    d=route.accumulated[j]+t*length(a,b)
                    if not (lap_start-1<=d<=lap_end+1):continue
                    if best is None or gap<best[0]:best=(gap,d)
                if best and best[0]<35.0:
                    pos,heading,_=route.sample(best[1])
                    if not self.track.canyon_fall(pos):
                        records.append((best[1],pos,heading,cp['id']))
        records.sort(key=lambda p:p[0])
        return records

    def rescue_positions(self,to_screen,racer):
        at=to_screen(racer.fall_at)
        target=(to_screen(racer.rescue_target[1]) if racer.rescue_target else at)
        t=clamp(racer.fall_age/self.RESCUE_SECONDS,0.0,1.0)
        smooth=t*t*(3.0-2.0*t)
        cart=lerp((at[0],at[1]-3),(target[0],target[1]-3),smooth)
        cloud=(cart[0]+(1-smooth)*62,cart[1]-39-(1-smooth)*58)
        return cloud,cart

    def draw_rescue(self,canvas,to_screen,racer):
        if not racer.fall_phase or racer.fall_phase=='penalty':return
        at=to_screen(racer.fall_at)
        if racer.fall_phase=='fall':
            shade=self.fall_shadow.copy()
            shade.set_alpha(round(200*(1-racer.fall_age/self.FALL_SECONDS)))
            canvas.blit(shade,shade.get_rect(center=(round(at[0]),round(at[1]))))
        elif racer.fall_phase=='dust':
            frame=min(4,int(racer.fall_age/.08))
            splash=self.dust[frame]
            canvas.blit(splash,splash.get_rect(center=(round(at[0]),round(at[1]))))
        elif racer.fall_phase=='rescue':
            cloud,cart=self.rescue_positions(to_screen,racer)
            pygame.draw.line(canvas,(189,243,231),cloud,cart,2)
            sprite=self.cloud[int(self.time*8)%2]
            canvas.blit(sprite,sprite.get_rect(center=(round(cloud[0]),round(cloud[1]))))

    def draw_sparkles(self,canvas,to_screen,racer):
        xy=to_screen(racer.pos)
        if racer.respawn_fx_left>0:
            index=min(3,int(max(0,.60-racer.respawn_fx_left)/.15))
            sprite=self.sparkle[index]
            canvas.blit(sprite,sprite.get_rect(center=(round(xy[0]),round(xy[1]))))
        pygame.draw.circle(canvas,(135,247,230),(round(xy[0]),round(xy[1])),19,2)

    def draw(self,canvas,to_screen):
        clip=canvas.get_clip()
        canvas.set_clip(TRACK_RECT)
        for actor in self.actors:
            at=to_screen(actor['pos'])
            art=self.art[actor['type']]
            poof_age=self.time-actor['poof_at']
            if 0<=poof_age<1.0:
                if poof_age<.28:
                    index=min(3,int(poof_age/.07))
                    sprite=art['poof'][index]
                    canvas.blit(sprite,sprite.get_rect(center=(round(at[0]),round(at[1]))))
                continue
            alpha,solid=self.phase_alpha(actor)
            t=self.time*art['fps']+actor['index']*.61
            frame=int(t)%2
            bob=math.sin(self.time*4+actor['index'])*art['bob']*self.sy
            point=(round(at[0]),round(at[1]+bob))
            # Shadows are present on the boardwalk even for transparent ghosts.
            shadow=art['shadow']
            canvas.blit(shadow,shadow.get_rect(center=(point[0],point[1]+7)))
            glow=art['glow']
            image=(art['chase'] if actor['type']=='banshee' or not solid
                   else art['idle'])[frame]
            if alpha<.995:
                # Copies only during the fade portion; original art stays cached.
                image=image.copy();image.set_alpha(round(alpha*255))
                glow=glow.copy();glow.set_alpha(round(alpha*190))
            canvas.blit(glow,glow.get_rect(center=point))
            canvas.blit(image,image.get_rect(center=point))
        canvas.set_clip(clip)


class GlowGardenFairies:
    """Eleven authored fairy hazards: six glimmers, three petals, two moths.

    A fairy animates on a deterministic home path, with a separately integrated
    curiosity offset. All movement and hit testing uses 960x600 world pixels.
    """
    KART_RADIUS=10.0
    SPIN_SECONDS=.90
    IMMUNITY_AFTER_SPIN=.60

    def __init__(self,track):
        self.track=track
        self.manifest=track.glow_data
        self.base=os.path.dirname(track.glow_manifest_path)
        self.sx=TRACK_RECT.width/MAP_W
        self.sy=TRACK_RECT.height/MAP_H
        self.curiosity=self.manifest['fairy_curiosity']
        self.sense=float(self.curiosity['sense_radius_px'])
        self.drift_speed=float(self.curiosity['drift_speed_px_s'])
        self.leash=float(self.curiosity['max_leash_px'])
        self.art={}
        for kind,spec in self.manifest['fairy_sprites'].items():
            self.art[kind]={
                'idle':[self.load(s) for s in spec['idle']],
                'poof':[self.load(s) for s in spec['poof']],
                'glow':self.load(spec['glow']),
                'shadow':self.load(spec['shadow']),
                'radius':float(spec['hitbox_radius_px']),
                'fps':float(spec.get('anim_hz',6)),
                'bob':float(spec.get('bob_px',1))}
        self.dust=[self.load(s) for s in self.manifest.get('dust_trail',[])]
        self.actors=[]
        for record in self.manifest['fairies']:
            a=dict(record)
            if a['motion']=='loop_forward':
                a['route']=Route([tuple(p) for p in a['loop_points']]+
                                 [tuple(a['loop_points'][0])])
            a['offset']=(0.0,0.0)
            a['pos']=(0.0,0.0)
            a['previous']=(0.0,0.0)
            a['poof_at']=-100.0
            a['dust_history']=[]
            self.actors.append(a)
        self.reset()

    def load(self,relative):
        im=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
        return pygame.transform.smoothscale(im,(
            max(1,round(im.get_width()*self.sx)),
            max(1,round(im.get_height()*self.sy))))

    def reset(self):
        self.time=0.0
        self.dust_clock=0.0
        for a in self.actors:
            a['offset']=(0.0,0.0)
            a['poof_at']=-100.0
            a['dust_history']=[]
            a['pos']=self.home(a,0.0)
            a['previous']=a['pos']

    def home(self,a,t):
        motion=a['motion']
        if motion=='lissajous':
            phase=math.tau*float(a['freq_hz'])*t+float(a['phase'])
            along=float(a['along_amp_px'])*math.sin(phase)
            lateral=float(a['lateral_amp_px'])*math.sin(2*phase+.55)
            return (a['center'][0]+a['tangent'][0]*along+a['normal'][0]*lateral,
                    a['center'][1]+a['tangent'][1]*along+a['normal'][1]*lateral)
        if motion=='orbit':
            angle=math.tau*t/max(.1,float(a['period_s']))*int(a['direction'])+float(a['phase'])
            return (a['center'][0]+float(a['radius_px'])*math.cos(angle),
                    a['center'][1]+float(a['radius_px'])*math.sin(angle))
        if motion=='loop_forward':
            route=a['route']
            d=t*float(a['speed_px_s'])%max(.1,route.length)
            return route.sample(d)[0]
        return tuple(a.get('center',(0,0)))

    def update(self,dt,players=()):
        self.time+=dt
        self.dust_clock+=dt
        emit=self.dust_clock>=.08
        if emit:self.dust_clock%=.08
        for a in self.actors:
            a['previous']=a['pos']
            home=self.home(a,self.time)
            ox,oy=a['offset']
            goal=(0.0,0.0)
            if a.get('curious',False):
                closest=None
                for r in players:
                    if r.finished or r.fall_phase or r.flight_left>0:continue
                    delta=(r.pos[0]-home[0],r.pos[1]-home[1])
                    dist=math.hypot(*delta)
                    if dist<self.sense and (closest is None or dist<closest[0]):
                        closest=(dist,delta)
                if closest is not None and closest[0]>1e-4:
                    dist,delta=closest
                    reach=min(self.leash,max(0.0,dist-8.0))
                    goal=(delta[0]*reach/dist,delta[1]*reach/dist)
            diff=(goal[0]-ox,goal[1]-oy)
            dist=math.hypot(*diff)
            # Approach curiosity offset at bounded world speed; return smoothly.
            step=min(dist,self.drift_speed*dt)
            if dist>1e-5:
                ox+=diff[0]*step/dist
                oy+=diff[1]*step/dist
            leash=math.hypot(ox,oy)
            if leash>self.leash:
                ox*=self.leash/leash;oy*=self.leash/leash
            a['offset']=(ox,oy)
            a['pos']=(home[0]+ox,home[1]+oy)
            a['dust_history']=[(p,t) for p,t in a['dust_history'] if self.time-t<.30]
            if emit and self.time-a['poof_at']>=1.2:
                a['dust_history'].append((a['pos'],self.time))

    def hit_test(self,previous,position):
        for a in self.actors:
            if self.time-a['poof_at']<1.2:continue
            rel0=(previous[0]-a['previous'][0],previous[1]-a['previous'][1])
            rel1=(position[0]-a['pos'][0],position[1]-a['pos'][1])
            if segment_near_point(rel0,rel1,(0,0))<=self.KART_RADIUS+self.art[a['type']]['radius']:
                return a
        return None

    def on_hit(self,a):
        a['poof_at']=self.time
        a['offset']=(0.0,0.0)
        a['dust_history']=[]

    def draw(self,canvas,to_screen):
        clip=canvas.get_clip();canvas.set_clip(TRACK_RECT)
        if self.dust:
            for a in self.actors:
                for pos,born in a['dust_history']:
                    age=self.time-born
                    if age>=.3:continue
                    img=self.dust[min(len(self.dust)-1,int(age/.1))]
                    xy=to_screen(pos)
                    canvas.blit(img,img.get_rect(center=(round(xy[0]),round(xy[1]))))
        for i,a in enumerate(self.actors):
            xy=to_screen(a['pos']);at=(round(xy[0]),round(xy[1]))
            art=self.art[a['type']]
            age=self.time-a['poof_at']
            if 0<=age<1.2:
                if age<.28:
                    img=art['poof'][min(3,int(age/.07))]
                    canvas.blit(img,img.get_rect(center=at))
                continue
            frame=int(self.time*art['fps']+i*.63)%len(art['idle'])
            bob=round(math.sin(self.time*5+i)*art['bob']*self.sy)
            p=(at[0],at[1]+bob)
            shadow=art['shadow']
            canvas.blit(shadow,shadow.get_rect(center=(p[0],p[1]+7)))
            for name in ('glow',):
                img=art[name]
                canvas.blit(img,img.get_rect(center=p))
            img=art['idle'][frame]
            canvas.blit(img,img.get_rect(center=p))
        canvas.set_clip(clip)


class StarlightSpiralCats:
    """Authored kitten rosettes, telegraphed dashers and ribbon-tailed giants."""
    KART_RADIUS=10.0
    SPIN_SECONDS=.90
    IMMUNITY_AFTER_SPIN=.60

    def __init__(self,track):
        self.track=track
        self.manifest=track.spiral_data
        self.base=os.path.dirname(track.spiral_manifest_path)
        self.sx=TRACK_RECT.width/MAP_W
        self.sy=TRACK_RECT.height/MAP_H
        self.art={}
        for kind,spec in self.manifest['cat_sprites'].items():
            self.art[kind]={
                'idle':[self.load(s) for s in spec['idle']],
                'poof':[self.load(s) for s in spec['poof']],
                'glow':self.load(spec['glow']),
                'shadow':self.load(spec['shadow']),
                'radius':float(spec['hitbox_radius_px']),
                'fps':float(spec.get('anim_hz',5)),
                'trail_height':float(spec['trail_height_px'])}
        self.swirl=[self.load(s) for s in self.manifest['fx']['swirl']]
        self.sparks=[self.load(s) for s in self.manifest['fx']['spark']]
        self.warning_img=self.load(self.manifest['fx']['warning_tile'])
        self.warning_rotated={}  # One cached strip orientation per authored lane.
        # The 16x18 rainbow segments are loaded and scaled per cat type once.
        self.tiles={}
        for kind,art in self.art.items():
            h=max(3,round(art['trail_height']*self.sy))
            self.tiles[kind]=[self.load(s,(max(4,round(16*self.sx)),h))
                              for s in self.manifest['trail']['tiles']]
        self.tail_end=self.load(self.manifest['trail']['end'])
        self.trail_rotation_cache={}  # (kind, wave, 12-degree heading), lazy
        self.actors=[]
        for a in self.manifest['cats']:
            actor=dict(a)
            if a['motion']=='loop_weave':
                pts=[tuple(p) for p in a['loop_points']]
                actor['route']=Route(pts+[pts[0]])
            actor['pos']=(0.0,0.0)
            actor['previous']=(0.0,0.0)
            actor['heading']=0.0
            actor['poof_at']=-100.0
            actor['trail']=[]
            self.actors.append(actor)
        self.reset()

    def load(self,relative,override_size=None):
        im=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
        size=(max(1,round(im.get_width()*self.sx)),max(1,round(im.get_height()*self.sy)))
        return pygame.transform.smoothscale(im,override_size or size)

    def reset(self):
        self.time=0.0
        for a in self.actors:
            a['poof_at']=-100.0
            a['trail']=[]
            p,heading,visible=self.position(a,0.0)
            a['pos']=p
            a['previous']=p
            a['heading']=heading
            a['visible']=visible

    def dash_phase(self,a,t):
        return ((t+float(a.get('phase_s',0)))%max(.1,float(a['cycle_s'])))

    def position(self,a,t):
        motion=a['motion']
        if motion=='spiral_orbit':
            u=((t/float(a['cycle_s']))+float(a['phase']))%1.0
            r=float(a['r_min_px'])+(float(a['r_max_px'])-float(a['r_min_px']))*(.5-.5*math.cos(math.tau*u))
            angle=math.tau*float(a['turns_per_cycle'])*u
            xy=(a['center'][0]+r*math.cos(angle),a['center'][1]+r*math.sin(angle))
            # Analytic tangent of the rosette determines readable orientation.
            du=math.tau/max(.1,float(a['cycle_s']))
            dr=.5*(float(a['r_max_px'])-float(a['r_min_px']))*math.tau*math.sin(math.tau*u)/max(.1,float(a['cycle_s']))
            da=math.tau*float(a['turns_per_cycle'])/max(.1,float(a['cycle_s']))
            dx=dr*math.cos(angle)-r*math.sin(angle)*da
            dy=dr*math.sin(angle)+r*math.cos(angle)*da
            return xy,math.atan2(dy,dx),True
        if motion=='strike':
            phase=self.dash_phase(a,t)
            start=float(a['warning_s']);duration=float(a['dash_s'])
            if start<=phase<start+duration:
                u=(phase-start)/duration
                xy=lerp(a['a'],a['b'],u)
                return xy,math.atan2(a['b'][1]-a['a'][1],a['b'][0]-a['a'][0]),True
            return tuple(a['a']),math.atan2(a['b'][1]-a['a'][1],a['b'][0]-a['a'][0]),False
        if motion=='loop_weave':
            route=a['route']
            # Supplied loop_points already encode forward vs counter-lap.
            # In particular G1's tangent is opposite the course's tangent;
            # reversing it here would accidentally turn G1 into a chaser.
            travelled=(t*float(a['speed_px_s']))%max(.1,route.length)
            p,heading,_=route.sample(travelled)
            angle=math.tau*float(a['pirouette_hz'])*t
            radius=float(a['pirouette_radius_px'])
            return (p[0]+radius*math.cos(angle),p[1]+radius*math.sin(angle)),heading,True
        return (0.0,0.0),0.0,False

    def update(self,dt,players=()):
        self.time+=dt
        for a in self.actors:
            a['previous']=a['pos']
            was=a.get('visible',False)
            a['pos'],a['heading'],a['visible']=self.position(a,self.time)
            if self.time-a['poof_at']<1.2 or not a['visible']:
                a['trail']=[]
                continue
            # Dash only exists for its 0.6-second active interval; don't stitch
            # a ribbon across a hidden/teleported phase boundary.
            if not was or not a['trail'] or length(a['trail'][-1],a['pos'])>32:
                a['trail']=[a['pos']]
            elif length(a['trail'][-1],a['pos'])>=4.0:
                a['trail'].append(a['pos'])
            cap=float(a.get('trail_length_px',105 if a['type']=='giant' else 55))
            # Bound history for Pygbag and trim by geometric distance.
            while len(a['trail'])>2 and sum(length(x,y) for x,y in zip(a['trail'],a['trail'][1:]))>cap:
                a['trail'].pop(0)
            if len(a['trail'])>45:a['trail']=a['trail'][-45:]

    def hit_test(self,previous,position):
        for a in self.actors:
            if not a['visible'] or self.time-a['poof_at']<1.2:continue
            # A dasher is dangerous ONLY during its strike, never warning/hidden.
            if a['motion']=='strike':
                phase=self.dash_phase(a,self.time)
                if not (float(a['warning_s'])<=phase<float(a['warning_s'])+float(a['dash_s'])):
                    continue
            rel0=(previous[0]-a['previous'][0],previous[1]-a['previous'][1])
            rel1=(position[0]-a['pos'][0],position[1]-a['pos'][1])
            if segment_near_point(rel0,rel1,(0,0))<=self.KART_RADIUS+self.art[a['type']]['radius']:
                return a
        return None

    def on_hit(self,a):
        a['poof_at']=self.time
        a['trail']=[]

    @staticmethod
    def blit_center(canvas,img,xy):
        canvas.blit(img,img.get_rect(center=(round(xy[0]),round(xy[1]))))

    def draw_underlay(self,canvas,to_screen):
        """Warning strips and harmless rainbow ribbons go under the karts."""
        clip=canvas.get_clip();canvas.set_clip(TRACK_RECT)
        for a in self.actors:
            if a['motion']=='strike' and self.dash_phase(a,self.time)<float(a['warning_s']):
                from_xy,to_xy=to_screen(a['a']),to_screen(a['b'])
                progress=self.dash_phase(a,self.time)/max(.01,float(a['warning_s']))
                warning_color=(248,116,228) if int(self.time*7)%2 else (103,230,244)
                pygame.draw.line(canvas,warning_color,from_xy,to_xy,max(4,round(7*self.sx)))
                if a['id'] not in self.warning_rotated:
                    heading=math.degrees(math.atan2(to_xy[1]-from_xy[1],
                                                    to_xy[0]-from_xy[0]))
                    self.warning_rotated[a['id']]=pygame.transform.rotate(
                        self.warning_img,90-heading)
                tile=self.warning_rotated[a['id']]
                segments=max(1,int(length(from_xy,to_xy)/24))
                for n in range(segments+1):
                    q=lerp(from_xy,to_xy,n/segments)
                    self.blit_center(canvas,tile,q)
            pts=a['trail']
            if len(pts)<2 or not a['visible']:continue
            for i in range(1,len(pts)):
                aa=to_screen(pts[i-1]);bb=to_screen(pts[i])
                dx,dy=bb[0]-aa[0],bb[1]-aa[1]
                dist=math.hypot(dx,dy)
                if dist<.2:continue
                normal=(-dy/dist,dx/dist)
                h=self.art[a['type']]['trail_height']*self.sy
                # Six translucent rainbow bands, along the actual recent path.
                for k,color in enumerate(((255,104,140),(255,188,106),(255,245,136),
                                           (124,245,159),(117,211,255),(198,140,255))):
                    shift=(k-2.5)*h/6.0
                    start=(aa[0]+normal[0]*shift,aa[1]+normal[1]*shift)
                    end=(bb[0]+normal[0]*shift,bb[1]+normal[1]*shift)
                    pygame.draw.line(canvas,color,start,end,max(1,round(h/6)))
                # Use supplied rainbow-tile artwork to accent trailing edges.
                if i%2==0:
                    image=self.tiles[a['type']][int(self.time*8+i)%2]
                    angle=-math.degrees(math.atan2(dy,dx))
                    quant=int(round(angle/12.0))*12
                    wave=int(self.time*8+i)%2
                    key=(a['type'],wave,quant)
                    rotated=self.trail_rotation_cache.get(key)
                    if rotated is None:
                        rotated=pygame.transform.rotate(self.tiles[a['type']][wave],quant)
                        self.trail_rotation_cache[key]=rotated
                    self.blit_center(canvas,rotated,aa)
            self.blit_center(canvas,self.tail_end,to_screen(pts[0]))
        canvas.set_clip(clip)

    def draw(self,canvas,to_screen):
        clip=canvas.get_clip();canvas.set_clip(TRACK_RECT)
        for i,a in enumerate(self.actors):
            age=self.time-a['poof_at']
            at=to_screen(a['pos'])
            art=self.art[a['type']]
            if 0<=age<1.2:
                if age<.28:
                    frame=min(3,int(age/.07))
                    self.blit_center(canvas,art['poof'][frame],at)
                continue
            if not a['visible']:continue
            frame=int(self.time*art['fps']+i*.47)%len(art['idle'])
            # Cat art faces east; retain an upright, mirrored pose when westbound.
            angle=((a['heading']+math.pi)%(math.tau))-math.pi
            flip=abs(angle)>math.pi/2
            turn=math.degrees(angle)
            if flip:turn+=180 if turn<0 else -180
            body=art['idle'][frame]
            glow=art['glow']
            if flip:
                body=pygame.transform.flip(body,True,False)
                glow=pygame.transform.flip(glow,True,False)
            body=pygame.transform.rotate(body,-turn)
            glow=pygame.transform.rotate(glow,-turn)
            shadow=art['shadow']
            self.blit_center(canvas,shadow,(at[0],at[1]+7))
            self.blit_center(canvas,glow,at)
            self.blit_center(canvas,body,at)
        canvas.set_clip(clip)

    def draw_swirl(self,canvas,to_screen,racer):
        if racer.train_spin_left<=0 or getattr(racer,'spin_fx_kind',None)!='cat':
            return
        phase=1.0-racer.train_spin_left/max(.01,racer.train_spin_duration)
        index=int(phase*racer.train_spin_duration/.06)%len(self.swirl)
        self.blit_center(canvas,self.swirl[index],to_screen(racer.pos))

class RainbowRocketHazards:
    """Authoritative 2624px width/elevation lap, Cog Chompers and star rescue.

    Every actor keeps an independent track-layer index, including at the two
    crossings. Actor movement is deterministic and does not depend on FPS.
    """
    FALL_SECONDS=.90
    DUST_SECONDS=.40
    WAIT_SECONDS=.60
    RESCUE_SECONDS=.80
    PENALTY_SECONDS=1.20
    IMMUNITY_SECONDS=1.50

    def __init__(self,track):
        self.track=track
        self.manifest=track.rocket_data
        self.base=os.path.dirname(track.rocket_manifest_path)
        self.sx=TRACK_RECT.width/MAP_W
        self.sy=TRACK_RECT.height/MAP_H
        self.types={}
        for name,spec in self.manifest['chomper_sprites'].items():
            self.types[name]={
                'spec':spec,
                'idle':[self.load(f) for f in spec['idle']],
                'charge':[self.load(f) for f in spec['charge']],
                'glow':self.load(spec['glow']),
                'shadow':self.load(spec['shadow']),
                'radius':float(spec['hitbox_radius_px'])}
        self.links={}
        for spec in self.manifest['chompers']:
            rel=spec['chain']['sprite']
            if rel not in self.links:self.links[rel]=self.load(rel)
        self.dust=[self.load('fall/stardust_%d.png'%i) for i in range(5)]
        self.cloud=[self.load('fall/rescue_cloud_a.png'),self.load('fall/rescue_cloud_b.png')]
        self.sparkle=[self.load('fall/respawn_sparkle_%d.png'%i) for i in range(4)]
        self.fall_shadow=self.load('fall/kart_shadow.png')
        self._transforms={}
        self.actors=[]
        for i,entry in enumerate(self.manifest['chompers']):
            a=dict(entry)
            a['index']=i
            a['s']=float(a['start_index'])
            a['previous_s']=a['s']
            a['pos']=(0,0)
            a['previous']=(0,0)
            a['layer']=0
            a['previous_layer']=0
            a['scale']=1.0
            a['heading']=0.0
            a['hit_at']=-100.0
            self.actors.append(a)
        self.reset()

    def load(self,relative):
        image=pygame.image.load(os.path.join(self.base,*relative.split('/'))).convert_alpha()
        return pygame.transform.smoothscale(image,(
            max(1,round(image.get_width()*self.sx)),
            max(1,round(image.get_height()*self.sy))))

    def reset(self):
        self.time=0.0
        for a in self.actors:
            a['hit_at']=-100.0
            a['s']=float(a['start_index'])
            a['previous_s']=a['s']
            a['pos'],a['heading'],a['layer'],a['scale']=self.position(a,0.0)
            a['previous']=a['pos']
            a['previous_layer']=a['layer']

    def travelled(self,a,t):
        lunge=a['lunge']
        cycle=float(lunge['cycle_s']);roam=float(lunge['roam_s'])
        windup=float(lunge['windup_s']);strike=float(lunge['lunge_s'])
        phase=t%cycle
        cycles=math.floor(t/cycle)
        slow=float(a['speed_px_s']);fast=float(lunge['lunge_speed_px_s'])
        reset=max(0.0,cycle-roam-windup-strike)
        entire=roam*slow+strike*fast+reset*slow
        if phase<roam:travel=phase*slow
        elif phase<roam+windup:travel=roam*slow
        elif phase<roam+windup+strike:
            travel=roam*slow+(phase-roam-windup)*fast
        else:
            travel=roam*slow+strike*fast+(phase-roam-windup-strike)*slow
        return cycles*entire+travel,phase

    def position_s(self,a,distance,t):
        samples=self.track.rocket_samples
        s=float(distance)%self.track.rocket_length
        i=max(0,min(len(samples)-2,bisect.bisect_right(self.track.rocket_s,s)-1))
        p,q=samples[i:i+2]
        u=clamp((s-p['s'])/max(.001,q['s']-p['s']),0.0,1.0)
        x=p['x']+(q['x']-p['x'])*u
        y=p['y']+(q['y']-p['y'])*u
        tangent=math.atan2(p['ty']+(q['ty']-p['ty'])*u,
                           p['tx']+(q['tx']-p['tx'])*u)
        scale,layer,height,halfwidth=self.track.rocket_at_s(s)
        weave=a['weave']
        lateral=float(weave['amplitude_halfwidth'])*halfwidth*math.sin(
            math.tau*s/max(1.,float(weave['period_px'])))
        x-=math.sin(tangent)*lateral
        y+=math.cos(tangent)*lateral
        if a['direction']=='against_lap':tangent+=math.pi
        return (x,y),tangent,layer,scale

    def position(self,a,t):
        walked,phase=self.travelled(a,t)
        sign=1 if a['direction']=='with_lap' else -1
        s=(float(a['start_index'])+sign*walked)%self.track.rocket_length
        pos,heading,layer,scale=self.position_s(a,s,t)
        lunge=a['lunge']
        if float(lunge['roam_s'])<=phase<float(lunge['roam_s'])+float(lunge['windup_s']):
            shake=1.5*math.sin(t*math.tau*14.0+a['index'])
            pos=(pos[0]+math.cos(heading)*shake,pos[1]+math.sin(heading)*shake)
        return pos,heading,layer,scale

    def update(self,dt,players=()):
        self.time+=dt
        for a in self.actors:
            a['previous']=a['pos']
            a['previous_layer']=a['layer']
            a['previous_s']=a['s']
            walked,phase=self.travelled(a,self.time)
            sign=1 if a['direction']=='with_lap' else -1
            a['s']=(float(a['start_index'])+sign*walked)%self.track.rocket_length
            a['pos'],a['heading'],a['layer'],a['scale']=self.position(a,self.time)

    def hit_test(self,previous,position,racer):
        layer=self.track.rocket_state(position,racer.route.sample(racer.distance)[1])[0]
        kart_radius=10.0*clamp(racer.kart_scale,.65,1.36)
        for a in self.actors:
            if a['layer']!=layer or a['previous_layer']!=layer:continue
            relative_start=(previous[0]-a['previous'][0],previous[1]-a['previous'][1])
            relative_end=(position[0]-a['pos'][0],position[1]-a['pos'][1])
            radius=self.types[a['type']]['radius']*a['scale']+kart_radius
            if segment_near_point(relative_start,relative_end,(0,0))<=radius:
                return a
        return None

    def on_hit(self,a):
        # Chompers keep rolling. Their flash is cosmetic; immunity belongs to
        # each kart individually, so a chomper may still hit a second racer.
        a['hit_at']=self.time

    def checkpoint_route(self,route):
        """Match authored layered 19-point respawn plan to EACH player's laps."""
        recorded=[]
        lap_starts=[0.0]+list(route.lap_boundaries[:-1])
        for lap_start,lap_end in zip(lap_starts,route.lap_boundaries):
            lo=max(0,bisect.bisect_left(route.accumulated,lap_start)-1)
            hi=min(len(route.points)-1,bisect.bisect_right(route.accumulated,lap_end))
            for cp in self.manifest['fall']['respawn_points']:
                point=(float(cp['x']),float(cp['y']))
                angle=math.radians(float(cp['heading_deg_clockwise_from_east']))
                best=None
                for j in range(lo,hi):
                    a,b=route.points[j:j+2]
                    segment_angle=math.atan2(b[1]-a[1],b[0]-a[0])
                    if abs(angle_delta(segment_angle,angle))>math.radians(58):continue
                    gap,t,_=point_segment_projection(a,b,point)
                    distance=route.accumulated[j]+t*length(a,b)
                    if not lap_start-1<=distance<=lap_end+1:continue
                    if best is None or gap<best[0]:best=(gap,distance)
                if best and best[0]<36.0:
                    pos,heading,_=route.sample(best[1])
                    if not self.track.rocket_fall(pos,heading):
                        recorded.append((best[1],pos,heading,cp['id']))
        recorded.sort(key=lambda x:x[0])
        # Small off-route deviations may match adjacent checkpoints; avoid
        # duplicate notifications at the same point on the drawn spline.
        unique=[]
        for item in recorded:
            if unique and item[0]-unique[-1][0]<10:continue
            unique.append(item)
        return unique

    def rescue_positions(self,to_screen,racer):
        at=to_screen(racer.fall_at)
        target=(to_screen(racer.rescue_target[1]) if racer.rescue_target else at)
        t=clamp(racer.fall_age/self.RESCUE_SECONDS,0,1)
        ease=t*t*(3-2*t)
        cart=lerp((at[0],at[1]-3),(target[0],target[1]-3),ease)
        cloud=(cart[0]+(1-ease)*68,cart[1]-43-(1-ease)*58)
        return cloud,cart

    @staticmethod
    def blit_center(canvas,img,p):
        canvas.blit(img,img.get_rect(center=(round(p[0]),round(p[1]))))

    def draw_rescue(self,canvas,to_screen,racer):
        if not racer.fall_phase or racer.fall_phase=='penalty':return
        point=to_screen(racer.fall_at)
        if racer.fall_phase=='fall':
            shade=self.fall_shadow.copy()
            shade.set_alpha(round(200*(1-racer.fall_age/self.FALL_SECONDS)))
            self.blit_center(canvas,shade,point)
        elif racer.fall_phase=='dust':
            i=min(4,int(racer.fall_age/.08))
            self.blit_center(canvas,self.dust[i],point)
        elif racer.fall_phase=='rescue':
            cloud,cart=self.rescue_positions(to_screen,racer)
            pygame.draw.line(canvas,(240,213,255),cloud,cart,2)
            self.blit_center(canvas,self.cloud[int(self.time*8)%2],cloud)

    def draw_sparkles(self,canvas,to_screen,racer):
        point=to_screen(racer.pos)
        if racer.respawn_fx_left>0:
            i=min(3,int(max(0,.60-racer.respawn_fx_left)/.15))
            self.blit_center(canvas,self.sparkle[i],point)
        pygame.draw.circle(canvas,(244,201,255),
                           (round(point[0]),round(point[1])),19,2)

    def sprite(self,image,key,scale,heading=0.0):
        quant=max(16,min(34,round(scale*25)))
        rotation=round(math.degrees(heading)/30)*30
        cache=(key,quant,rotation)
        if cache not in self._transforms:
            scaled=pygame.transform.smoothscale(image,(
                max(1,round(image.get_width()*quant/25)),
                max(1,round(image.get_height()*quant/25))))
            self._transforms[cache]=(pygame.transform.rotate(scaled,-rotation)
                                     if rotation else scaled)
        return self._transforms[cache]

    def draw(self,canvas,to_screen,layer=0):
        clip=canvas.get_clip();canvas.set_clip(TRACK_RECT)
        for a in self.actors:
            if a['layer']!=layer:continue
            body=self.types[a['type']]
            spec=a['chain']
            link=self.links[spec['sprite']]
            sign=1 if a['direction']=='with_lap' else -1
            # Draw four/five harmless chain links behind the moving cog ball.
            for k in range(int(spec['links']),0,-1):
                tail_s=a['s']-sign*k*float(spec['spacing_px'])
                tail,tail_heading,tail_layer,tail_scale=self.position_s(a,tail_s,self.time)
                if tail_layer==layer:
                    piece=self.sprite(link,('chain',spec['sprite']),tail_scale,
                                      tail_heading+math.pi/2 if k%2 else tail_heading)
                    self.blit_center(canvas,piece,to_screen(tail))
            xy=to_screen(a['pos'])
            phase=self.travelled(a,self.time)[1]
            lunge=a['lunge'];roam=float(lunge['roam_s'])
            windup=float(lunge['windup_s']);strike=float(lunge['lunge_s'])
            charging=roam<=phase<roam+windup+strike or self.time-a['hit_at']<.25
            frames=body['charge'] if charging else body['idle']
            frame=int(self.time*body['spec'].get('anim_hz',4)+a['index']*.45)%len(frames)
            # Mostly face along the road. A few angular degrees of rotation
            # imply rolling without forcing an expensive per-frame transform.
            angle=a['heading']
            image=self.sprite(frames[frame],(a['type'],'charge' if charging else 'idle',frame),
                              a['scale'],angle)
            shadow=self.sprite(body['shadow'],(a['type'],'shadow'),a['scale'])
            glow=self.sprite(body['glow'],(a['type'],'glow'),a['scale'])
            self.blit_center(canvas,shadow,(xy[0],xy[1]+6*a['scale']))
            self.blit_center(canvas,glow,xy)
            if charging:
                # Thin flame halo during wind-up; collision remains live.
                r=max(4,round(body['radius']*a['scale']*.78))
                color=(255,184,81) if int(self.time*10)%2 else (255,85,64)
                pygame.draw.circle(canvas,color,
                                   (round(xy[0]),round(xy[1])),r,2)
            self.blit_center(canvas,image,xy)
        canvas.set_clip(clip)


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
        self.modifiers=[]       # Future per-kart bonuses (separate from interactions).
        self.interaction_factor=1.0
        self.drafting=False
        self.bump_fx_left=0.0
        self.train_spin_left=0.0
        self.spin_fx_kind=None
        self.train_spin_duration=MovingTrain.STUN_SECONDS
        self.train_spin_heading=0.0
        self.train_spin_turns=1.0
        self.train_spin_motion=0.0
        self.train_immunity_left=0.0
        self.train_hits=0
        self.train_hit_events=[]
        self.ghost_train_hits=[]
        self.ghost_train_hits_index=0
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
        self.kart_scale=1.0  # only Rainbow Rocket uses the authored width profile
        # Ghost uses the recorded reaction, including an early-press penalty.
        self.ghost_reaction=None
        self.ghost_reaction_applied=False
        self.flight_left=0.0
        self.flight_elapsed=0.0
        self.flight_origin=None
        self.flight_heading=0.0
        self.flight_speed=0.0
        self.flight_distance=0.0
        self.fall_phase=None
        self.fall_age=0.0
        self.fall_at=None
        self.rescue_target=None
        self.fall_heading=0.0
        self.fall_count=0
        self.respawn_fx_left=0.0
        self.canyon_checkpoints=[]
        self.next_checkpoint=0
        self.last_checkpoint=(0.0,self.pos,self.heading,'START')

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

    def hit_by_train(self,elapsed=None,replay=False):
        """Stop, spin exactly once, and continue the same racing spline."""
        if (self.finished or self.train_immunity_left>0 or
                (self.is_ghost and not replay)):
            return False
        self.train_spin_heading=self.heading
        self.spin_fx_kind=None
        self.train_spin_duration=MovingTrain.STUN_SECONDS
        self.train_spin_turns=1.0
        self.train_spin_motion=0.0
        self.train_spin_left=self.train_spin_duration
        self.train_immunity_left=MovingTrain.HIT_IMMUNITY
        self.train_hits+=1
        if not replay and elapsed is not None:
            self.train_hit_events.append(round(elapsed,3))
        self.speed=0.0
        self.drafting=False
        self.interaction_factor=1.0
        return True

    def hit_by_log(self,elapsed=None,replay=False):
        """Two full spins in 0.9s while travelling at 40% normal speed."""
        if (self.finished or self.train_immunity_left>0 or
                (self.is_ghost and not replay)):
            return False
        self.train_spin_heading=self.heading
        self.spin_fx_kind=None
        self.train_spin_duration=GoldenGorgeLogs.SPIN_SECONDS
        self.train_spin_turns=2.0
        self.train_spin_motion=0.4
        self.train_spin_left=self.train_spin_duration
        self.train_immunity_left=(self.train_spin_duration+
                                  GoldenGorgeLogs.IMMUNITY_AFTER_SPIN)
        self.train_hits+=1
        if not replay and elapsed is not None:
            # Shared ghost history: old train records are plain timestamps;
            # Golden Gorge records are [time, 'log'] for correct replay.
            self.train_hit_events.append([round(elapsed,3),'log'])
        self.drafting=False
        self.interaction_factor=1.0
        return True

    def hit_by_comet(self,elapsed=None):
        if not self.hit_by_log(elapsed):return False
        if self.train_hit_events:
            event=self.train_hit_events[-1]
            if isinstance(event,list) and event[1]=='log':event[1]='comet'
        return True

    def hit_by_phantom(self,elapsed=None):
        if not self.hit_by_log(elapsed):return False
        if self.train_hit_events:
            event=self.train_hit_events[-1]
            if isinstance(event,list) and event[1]=='log':event[1]='phantom'
        return True

    def hit_by_fairy(self,elapsed=None):
        if not self.hit_by_log(elapsed):return False
        if self.train_hit_events:
            event=self.train_hit_events[-1]
            if isinstance(event,list) and event[1]=='log':event[1]='fairy'
        return True

    def hit_by_cat(self,elapsed=None):
        if not self.hit_by_log(elapsed):return False
        self.spin_fx_kind='cat'
        if self.train_hit_events:
            event=self.train_hit_events[-1]
            if isinstance(event,list) and event[1]=='log':event[1]='cat'
        return True

    def hit_by_rocket(self,elapsed=None):
        if not self.hit_by_log(elapsed):return False
        if self.train_hit_events:
            event=self.train_hit_events[-1]
            if isinstance(event,list) and event[1]=='log':event[1]='rocket'
        return True

    def hit_by_cactus(self,elapsed=None):
        # Same gentle 360-degree stop/spin as the Dusty Drive train.
        return self.hit_by_train(elapsed)

    def start_flight(self,origin,launch_distance,speed,heading,flight_time):
        self.flight_origin=tuple(origin)
        self.flight_distance=float(launch_distance)
        self.flight_speed=float(speed)
        self.flight_heading=float(heading)
        self.flight_elapsed=0.0
        self.flight_left=flight_time
        self.pos=tuple(origin)
        self.heading=heading
        self.distance=launch_distance
        self.drafting=False
        self.interaction_factor=1.0

    def begin_fall(self,elapsed=None,replay=False):
        if self.finished or self.fall_phase or self.train_immunity_left>0:
            return False
        self.flight_left=0.0
        self.fall_at=tuple(self.pos)
        self.rescue_target=None
        self.fall_heading=self.heading
        self.fall_phase='fall'
        self.fall_age=0.0
        self.fall_count+=1
        self.drafting=False
        self.interaction_factor=1.0
        self.speed=0.0
        self.train_spin_left=0.0
        if not replay and elapsed is not None:
            self.train_hit_events.append([round(elapsed,3),'fall'])
        return True

    def update_checkpoint(self):
        while self.next_checkpoint<len(self.canyon_checkpoints) and \
              self.canyon_checkpoints[self.next_checkpoint][0]<=self.distance+1.0:
            self.last_checkpoint=self.canyon_checkpoints[self.next_checkpoint]
            self.next_checkpoint+=1

    def find_forward_rescue(self,track):
        """Find a stable section AHEAD of the fall on the player's own spline.

        Rewinding to the previous checkpoint causes the kart to drive back into
        the same abyss. Sample the remaining authored line instead: first try
        the NEXT checkpoint, then the earliest long safe road stretch. The
        look-ahead ensures a landing just on the canyon lip is not accepted.
        """
        start=min(self.total_length,max(0.0,self.distance+9.0))
        if start>=self.total_length:
            position,angle,_=self.route.sample(self.total_length)
            return (self.total_length,position,angle)

        def safe_run(distance,span,road_only):
            stop=min(self.total_length,distance+span)
            if stop-distance<30.0 and stop<self.total_length-.1:
                return False
            steps=max(1,math.ceil((stop-distance)/5.0))
            for j in range(steps+1):
                sample,heading,_=self.route.sample(distance+(stop-distance)*j/steps)
                if track.canyon_fall(sample,heading):
                    return False
                if road_only and not track.on_road(sample):
                    return False
            return True

        # Named respawn points are beyond the canyon mouths. A slow crater is
        # still safe ground, so require a canyon-free run rather than excluding
        # a checkpoint simply because a crater temporarily slows the kart.
        # Project onto the player's drawing instead of using the manifest xy.
        for checkpoint in self.canyon_checkpoints:
            distance=checkpoint[0]
            if distance>=start and safe_run(distance,90.0,False):
                position,heading,_=self.route.sample(distance)
                return (distance,position,heading)

        # Deviating hand-drawn routes may miss all manifest checkpoints.
        # Find the next long, canyon-free segment, preferring actual road.
        # If the child drew on grass, a safe grass position is still better
        # than placing them in the canyon or starting an endless rescue loop.
        for road_only in (True,False):
            for clearance in (90.0,48.0,20.0):
                distance=start
                while distance<=self.total_length+.001:
                    if safe_run(distance,clearance,road_only):
                        # Land inside this clear stretch, not on its edge.
                        place=min(self.total_length,distance+min(20.0,clearance*.25))
                        position,heading,_=self.route.sample(place)
                        if not track.canyon_fall(position,heading):
                            return (place,position,heading)
                    distance+=6.0
        # The route ends at the start/finish flag. Finishing beats an infinite
        # fall loop for a drawing that remains over the canyon all the way out.
        position,heading,_=self.route.sample(self.total_length)
        return (self.total_length,position,heading)

    def update_fall(self,dt,track,elapsed=None):
        self.fall_age+=dt
        durations={'fall':.90,'dust':.40,'wait':.60,'rescue':.80,'penalty':1.20}
        if self.fall_age<durations[self.fall_phase]:return
        self.fall_age=0.0
        if self.fall_phase=='fall':self.fall_phase='dust'
        elif self.fall_phase=='dust':self.fall_phase='wait'
        elif self.fall_phase=='wait':
            self.rescue_target=self.find_forward_rescue(track)
            self.fall_phase='rescue'
        elif self.fall_phase=='rescue':
            # Always teleport FORWARD, beyond the hazard, on the original
            # player-drawn route. Never go back to the pre-fall checkpoint.
            if self.rescue_target is None:
                self.rescue_target=self.find_forward_rescue(track)
            old_distance=self.distance
            self.distance,self.pos,self.heading=self.rescue_target
            self.on_track=track.on_road(self.pos)
            if track.rocket_data:
                self.kart_scale=track.rocket_state(self.pos,self.heading)[1]
            self.speed=0.0
            # Crossing a start/finish line during rescue must still advance
            # the lap counter in a three-lap race. The tow counts as time,
            # not as a free instant lap or a missed boundary.
            if elapsed is not None and self.distance>old_distance:
                while self.completed_laps<self.laps and \
                      self.distance>=self.lap_boundaries[self.completed_laps]-1e-4:
                    previous_end=(self.lap_crossing_times[-1]
                                  if self.lap_crossing_times else 0.0)
                    crossing=round(max(elapsed,previous_end),3)
                    self.lap_times.append(round(crossing-previous_end,3))
                    self.lap_crossing_times.append(crossing)
                    self.completed_laps+=1
            checkpoint_distances=[p[0] for p in self.canyon_checkpoints]
            self.next_checkpoint=bisect.bisect_right(checkpoint_distances,self.distance+1.0)
            if self.next_checkpoint>0:
                self.last_checkpoint=self.canyon_checkpoints[self.next_checkpoint-1]
            self.fall_phase='penalty'
            self.respawn_fx_left=.60
        elif self.fall_phase=='penalty':
            self.fall_phase=None
            self.fall_age=0.0
            self.rescue_target=None
            self.train_immunity_left=1.50
            self.respawn_fx_left=.60

    def update(self,dt,elapsed,track):
        if self.finished:return
        self.respawn_fx_left=max(0.0,self.respawn_fx_left-dt)
        if self.fall_phase:
            self.update_fall(dt,track,elapsed)
            return
        if self.flight_left>0:
            step=min(dt,self.flight_left)
            self.flight_elapsed+=step
            self.flight_left=max(0.0,self.flight_left-step)
            flight=self.flight_speed*self.flight_elapsed
            self.pos=(self.flight_origin[0]+math.cos(self.flight_heading)*flight,
                      self.flight_origin[1]+math.sin(self.flight_heading)*flight)
            self.heading=self.flight_heading
            self.distance=min(self.total_length,self.flight_distance+flight)
            self.update_checkpoint()
            if self.flight_left<=0 and track.canyon_fall(self.pos):
                self.begin_fall(elapsed)
            elif self.flight_left<=0:
                # A jump uses locked heading, then rejoins the child's line
                # at the nearest forward segment, never rewinding midair.
                gap,projected=track.canyon_hazards.closest_forward_distance(
                    self.route,self.flight_distance,self.pos,
                    max(160.0,flight+95))
                if gap<42:self.distance=max(self.flight_distance,projected)
                self.update_checkpoint()
            return
        self.train_immunity_left=max(0.0,self.train_immunity_left-dt)
        if self.is_ghost and self.ghost_train_hits_index<len(self.ghost_train_hits):
            event=self.ghost_train_hits[self.ghost_train_hits_index]
            trigger=event[0] if isinstance(event,(tuple,list)) else event
            if elapsed>=trigger:
                if isinstance(event,(tuple,list)) and len(event)>1 and event[1] in ('log','comet','phantom','fairy','cat','rocket'):
                    self.hit_by_log(replay=True)
                    if isinstance(event,(tuple,list)) and len(event)>1 and event[1]=='cat':
                        self.spin_fx_kind='cat'
                elif isinstance(event,(tuple,list)) and len(event)>1 and event[1]=='fall':
                    self.begin_fall(replay=True)
                else:
                    self.hit_by_train(replay=True)
                self.ghost_train_hits_index+=1
        if self.train_spin_left>0.0:
            self.train_spin_left=max(0.0,self.train_spin_left-dt)
            portion=1.0-self.train_spin_left/self.train_spin_duration
            self.heading=self.train_spin_heading+math.tau*self.train_spin_turns*portion
            if self.train_spin_motion>0:
                # Ford logs are a soft obstacle: the child keeps following
                # their authored line at 40% speed during the two rotations.
                travel=self.speed*self.train_spin_motion*dt
                self.distance=min(self.total_length,self.distance+travel)
                self.pos,_,_=self.route_sample(self.distance)
                self.on_track=track.on_road(self.pos)
                if self.distance>=self.total_length-1e-3:
                    self.finished=True
                    self.finish_time=round(elapsed,3)
            else:
                self.speed=0.0
            return
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
        desired=(track.max_speed*bend*(ROAD_FACTOR if road else GRASS_FACTOR)
                  *min(1.95,temporary)*self.interaction_factor)
        if track.canyon_hazards is not None:
            desired*=track.canyon_hazards.speed_factor(pos)
        if track.phantom_data and track.phantom_mask('rail_wall_mask',pos):
            # A softer fence collision respects the child's already-drawn path.
            desired*=.42
        for modifier in self.modifiers:
            desired*=modifier
        response=3.1 if desired>self.speed else 5.2
        self.speed+=(desired-self.speed)*min(1.0,dt*response)
        advance=self.speed*dt
        previous=self.distance
        self.distance=min(self.total_length,self.distance+advance)
        self.pos,self.heading,_=self.route_sample(self.distance)
        self.on_track=track.on_road(self.pos)
        if track.rocket_data:
            intended=track.rocket_state(self.pos,self.heading)[1]
            self.kart_scale+=((intended-self.kart_scale)*min(1.0,dt/.15))
        if track.canyon_data or track.phantom_data or track.rocket_data:
            self.update_checkpoint()
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
        self.interactions_enabled=True  # Optional gentle kart drafting / bumping.
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
        self.bump_cooldowns={}  # (low player, high player) -> next allowed time.
        self.elapsed=0.0
        self.countdown=0.0
        self.paused=False
        self.results_time=0.0
        self.kart_picks=[0,1,2,3]
        self.map_surface=None
        self.bridge_overlay_surface=None
        self.moving_train=None
        self.cactus_hazards=None
        self.gorge_hazards=None
        self.canyon_hazards=None
        self.phantom_hazards=None
        self.glow_hazards=None
        self.spiral_hazards=None
        self.rocket_hazards=None
        self.fall_hazards=None
        self.draw_warning=None
        self.race_routes_layer=None  # Legacy field; used only during transition.
        self.race_trails=[]      # AheadTrail for each player (+ optional ghost).
        self.pickups=[]          # Fresh shared boxes for each race; stable during drawing.
        self.item_box_clock=0.0
        self.question_mark=None
        self.draw_routes_layer=None
        self.draw_routes_layer_overpass=None
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
        self.load_amulet_art()
        self.amulet_pressed_until=[-1.0]*4

    def load_catalog(self):
        with open(os.path.join(ASSET_ROOT,'catalog.json'),encoding='utf8') as stream:
            catalog=json.load(stream)
        # Desert Cup race 4/4. The new art is an additive asset folder, so the
        # GameHub catalog on GitHub does NOT need a separate manual edit.
        if len(catalog.get('tracks',[]))>=12:
            catalog['tracks'][11]={
                'name':'Comet Canyon',
                'image':'comet_canyon/comet_canyon_track.png',
                'road_mask':'comet_canyon/comet_canyon_road_mask.png',
                'geometry':'comet_canyon/comet_canyon_geometry.json'}
        # Star Cup, track 1/4. Drop-in asset directory, no catalog edit needed.
        if len(catalog.get('tracks',[]))>=13:
            catalog['tracks'][12]={
                'name':'Phantom Boardwalk',
                'image':'phantom_boardwalk/phantom_boardwalk_track.png',
                'road_mask':'phantom_boardwalk/phantom_boardwalk_road_mask.png',
                'geometry':'phantom_boardwalk/phantom_boardwalk_geometry.json'}
        # Star Cup 2 and 3 are delivered as additive asset folders.
        if len(catalog.get('tracks',[]))>=15:
            catalog['tracks'][13]={
                'name':'Glow Garden',
                'image':'glow_garden/glow_garden_track.png',
                'road_mask':'glow_garden/glow_garden_road_mask.png',
                'geometry':'glow_garden/glow_garden_geometry.json'}
            catalog['tracks'][14]={
                'name':'Starlight Spiral',
                'image':'starlight_spiral/starlight_spiral_track.png',
                'road_mask':'starlight_spiral/starlight_spiral_road_mask.png',
                'geometry':'starlight_spiral/starlight_spiral_geometry.json'}
        if len(catalog.get('tracks',[]))>=16:
            catalog['tracks'][15]={
                'name':'Rainbow Rocket',
                'image':'rainbow_rocket/rainbow_rocket_track.png',
                'road_mask':'rainbow_rocket/rainbow_rocket_road_mask_all.png',
                'geometry':'rainbow_rocket/rainbow_rocket_geometry.json'}
        return catalog

    def load_karts(self):
        for entry in self.catalog['karts']:
            path=os.path.join(ASSET_ROOT,*entry['image'].split('/'))
            image=pygame.image.load(path).convert_alpha()
            self.kart_images.append(image)

    def load_amulet_art(self):
        """Preload the supplied 1x (800x600 logical pixel) amulet artwork.

        2x and 4x are editing masters, not needed in the runtime. If assets
        are absent, retain the original Pygame circles as a safe fallback.
        """
        self.amulet_art=None
        root=os.path.join(ASSET_ROOT,'amulets')
        manifest_file=os.path.join(root,'amulet_manifest.json')
        if not os.path.isfile(manifest_file):
            return
        try:
            with open(manifest_file,encoding='utf8') as source:
                manifest=json.load(source)
            directory=os.path.join(root,'1x')
            def sprite(relative):
                return pygame.image.load(os.path.join(directory,*relative.split('/'))).convert_alpha()
            names=manifest['palette_index_to_name']
            self.amulet_art={
                'plain':[sprite(f'amulets/amulet_{i}_{names[str(i)]}_plain.png') for i in range(8)],
                'socket':[sprite(f'amulets/amulet_{i}_{names[str(i)]}_socket.png') for i in range(8)],
                'off_plain':sprite('amulets/amulet_off_plain.png'),
                'off_socket':sprite('amulets/amulet_off_socket.png'),
                'badges':[[sprite(f'badges/badge_{i}_{names[str(i)]}_p{p}.png')
                           for p in range(1,5)] for i in range(8)],
                'off_badges':[sprite(f'badges/badge_off_p{p}.png') for p in range(1,5)],
                'fx':{name:sprite(f'fx/{name}.png') for name in
                      ('halo_gold','halo_turbo','halo_tailwind','pressed_overlay')},
                'halo_cache':{},
            }
        except (OSError,ValueError,KeyError,pygame.error):
            # Never block GameHub startup because an optional art pack is absent.
            self.amulet_art=None

    def draw_amulet_halo(self,name,player,cx,cy):
        """Small quantized alpha palette avoids allocating images each frame."""
        art=self.amulet_art
        if not art:return
        opacity=round((.64+.32*abs(math.sin(self.item_box_clock*4.8+player)))*255/16)*16
        opacity=int(clamp(opacity,0,255))
        key=(name,opacity)
        img=art['halo_cache'].get(key)
        if img is None:
            img=art['fx'][name].copy()
            img.set_alpha(opacity)
            art['halo_cache'][key]=img
        self.canvas.blit(img,(cx-48,cy-48))

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
        self.bridge_overlay_surface=None
        self.bridge_overlay_xy=TRACK_RECT.topleft
        if self.track.overlay_path and os.path.exists(self.track.overlay_path):
            overlay=pygame.image.load(self.track.overlay_path).convert_alpha()
            if self.track.rocket_data:
                # The supplied rainbow deck overlay has ROUND end caps. Those
                # caps are already in the base map: re-blitting them between
                # kart layers incorrectly paints semicircles OVER karts on the
                # upper ramp approaches. The overlay is needed only WHERE
                # the upper deck actually crosses a lower road. Clip to two
                # lower-road corridors; upper-road racers are rendered later.
                cover=pygame.Surface(overlay.get_size(),pygame.SRCALPHA)
                for crossing in self.track.rocket_data['layers']['crossings']:
                    at=min(self.track.rocket_samples,
                           key=lambda sample:abs(sample['s']-crossing['lower_index']))
                    x,y=map(float,crossing['point'])
                    tx,ty=float(at['tx']),float(at['ty'])
                    mag=math.hypot(tx,ty) or 1.0
                    tx/=mag;ty/=mag
                    nx,ny=-ty,tx
                    half_width=float(at['half_width'])+14.0  # Kart/sprite margin.
                    half_length=90.0
                    corners=[(x+along*tx+across*nx,y+along*ty+across*ny)
                             for along,across in ((-half_length,-half_width),
                                                  (half_length,-half_width),
                                                  (half_length,half_width),
                                                  (-half_length,half_width))]
                    pygame.draw.polygon(cover,(255,255,255,255),corners)
                overlay.blit(cover,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
            if self.track.glow_data or self.track.rocket_data:
                # Tunnel / space decks occupy only ~266x131 of the 960x600 map. Crop once,
                # rather than alpha-blending a full 740x462 sprite at 60 FPS.
                bbox=overlay.get_bounding_rect(min_alpha=1)
                if bbox.width and bbox.height:
                    cropped=overlay.subsurface(bbox).copy()
                    sx=TRACK_RECT.width/MAP_W;sy=TRACK_RECT.height/MAP_H
                    size=(max(1,round(bbox.width*sx)),max(1,round(bbox.height*sy)))
                    self.bridge_overlay_surface=pygame.transform.smoothscale(cropped,size)
                    self.bridge_overlay_xy=(TRACK_RECT.left+round(bbox.left*sx),
                                            TRACK_RECT.top+round(bbox.top*sy))
            else:
                self.bridge_overlay_surface=pygame.transform.smoothscale(overlay,TRACK_RECT.size)
        # Only Dusty Drive (and future train-manifest tracks) loads a consist.
        self.moving_train=(MovingTrain(self.track) if self.track.train_manifest_path else None)
        self.cactus_hazards=(CactusLaneHazards(self.track)
                             if self.track.cactus_manifest_path else None)
        self.gorge_hazards=(GoldenGorgeLogs(self.track,self.map_surface)
                             if self.track.gorge_manifest_path else None)
        self.canyon_hazards=(CometCanyon(self.track)
                              if self.track.canyon_manifest_path else None)
        self.track.canyon_hazards=self.canyon_hazards
        self.phantom_hazards=(PhantomBoardwalk(self.track)
                              if self.track.phantom_manifest_path else None)
        self.track.phantom_hazards=self.phantom_hazards
        self.glow_hazards=(GlowGardenFairies(self.track)
                           if self.track.glow_manifest_path else None)
        self.track.glow_hazards=self.glow_hazards
        self.spiral_hazards=(StarlightSpiralCats(self.track)
                             if self.track.spiral_manifest_path else None)
        self.track.spiral_hazards=self.spiral_hazards
        self.rocket_hazards=(RainbowRocketHazards(self.track)
                             if self.track.rocket_manifest_path else None)
        self.track.rocket_hazards=self.rocket_hazards
        self.fall_hazards=self.canyon_hazards or self.phantom_hazards or self.rocket_hazards

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

    def amulet_hit(self, pos, player):
        """Touch the visible circle, not an invisible rectangular corner."""
        if not 0 <= player < self.players:
            return False
        cx,cy=PLAYER_AMULETS[player]
        return (pos[0]-cx)**2 + (pos[1]-cy)**2 <= AMULET_TOUCH_RADIUS**2

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

    def draw_star(self, center, radius, color=YELLOW, outline=None, phase=0.0):
        """Small five-point star with no font or new artwork dependency."""
        x,y=center
        vertices=[]
        for i in range(10):
            rad=radius if i%2==0 else radius*.44
            angle=-math.pi/2+i*math.pi/5+phase
            vertices.append((round(x+math.cos(angle)*rad),round(y+math.sin(angle)*rad)))
        pygame.draw.polygon(self.canvas,color,vertices)
        if outline is not None:
            pygame.draw.polygon(self.canvas,outline,vertices,2)

    def draw_sparkle(self,center,radius,color=YELLOW):
        """Tiny four-point glint with a soft cross; safe to draw each frame."""
        x,y=round(center[0]),round(center[1])
        r=max(2,round(radius))
        pygame.draw.line(self.canvas,color,(x-r,y),(x+r,y),max(1,r//3))
        pygame.draw.line(self.canvas,color,(x,y-r),(x,y+r),max(1,r//3))
        pygame.draw.circle(self.canvas,WHITE,(x,y),max(1,r//4))

    def draw_medal(self,center,rank,scale=1.0):
        """Gold/silver/bronze number badge for child-readable rankings."""
        x,y=round(center[0]),round(center[1])
        rad=max(11,round(17*scale))
        fill=((255,203,73) if rank==1 else (194,217,228) if rank==2
              else (222,156,106) if rank==3 else (120,155,188))
        dark=(72,52,44) if rank<=3 else (27,40,61)
        pygame.draw.circle(self.canvas,(20,31,50),(x,y+3),rad+2)
        pygame.draw.circle(self.canvas,fill,(x,y),rad)
        pygame.draw.circle(self.canvas,(255,248,222) if rank==1 else (225,235,245),
                           (x,y),rad,2)
        self.text(str(rank),(x,y),25,dark)
        if rank==1:
            self.draw_sparkle((x+rad+6,y-rad+2),5,(255,241,128))

    def draw_trophy(self,center,scale=1.0):
        """Tiny cartoon trophy icon, including two handles and a star."""
        x,y=center
        def pt(dx,dy):return (round(x+dx*scale),round(y+dy*scale))
        # Handles stay visible even when the results title is long.
        pygame.draw.arc(self.canvas,(251,200,75),
            pygame.Rect(*pt(-22,-18),round(18*scale),round(26*scale)),
            math.pi*.55,math.pi*1.60,max(2,round(4*scale)))
        pygame.draw.arc(self.canvas,(251,200,75),
            pygame.Rect(*pt(4,-18),round(18*scale),round(26*scale)),
            -math.pi*.60,math.pi*.48,max(2,round(4*scale)))
        pygame.draw.polygon(self.canvas,(244,171,52),
            [pt(-15,-17),pt(15,-17),pt(11,4),pt(5,11),pt(-5,11),pt(-11,4)])
        pygame.draw.polygon(self.canvas,(255,222,92),
            [pt(-12,-14),pt(8,-14),pt(6,3),pt(0,8),pt(-8,1)])
        pygame.draw.rect(self.canvas,(251,204,79),
            pygame.Rect(*pt(-4,10),round(8*scale),round(10*scale)))
        pygame.draw.rect(self.canvas,(240,159,66),
            pygame.Rect(*pt(-13,19),round(26*scale),round(5*scale)),border_radius=2)
        self.draw_star(pt(0,-5),6*scale,(255,251,198))

    def kart_preview(self,kart_id,center,scale=1.0,selected=False):
        """Cache smooth, correctly proportioned kart images; give large cards a plinth.

        Small previews (results and standings) stay compact, without floor art.
        """
        image=self.kart_images[kart_id]
        base_size=(118,90) if scale>=.75 else (101,76)
        sz=(max(8,round(base_size[0]*scale)),max(6,round(base_size[1]*scale)))
        key=('preview',kart_id,sz)
        if key not in self.kart_rotation_cache:
            self.kart_rotation_cache[key]=pygame.transform.smoothscale(image,sz)
        sprite=self.kart_rotation_cache[key]
        cx,cy=round(center[0]),round(center[1])
        if scale>=.75:
            pygame.draw.ellipse(self.canvas,(21,31,48),
                (cx-57,cy+29,114,17))
            pygame.draw.ellipse(self.canvas,(67,94,114),
                (cx-48,cy+30,96,9),2)
            if selected:
                shimmer=3*math.sin(self.item_box_clock*4)
                pygame.draw.ellipse(self.canvas,(255,225,139),
                    (cx-62,cy+28+shimmer,124,19),2)
        # Slight bounce on the actively selected kart only.
        rise=round(2.0*math.sin(self.item_box_clock*4.1)) if selected else 0
        self.canvas.blit(sprite,sprite.get_rect(center=(cx,cy-rise)))
        if selected and scale>=.75:
            self.draw_sparkle((cx+52,cy-26),5+(math.sin(self.item_box_clock*7)+1)*2)

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

        # Three independent feature switches, each with full-height 41px touch
        # targets, even on a shared iPad. Interactions only affect humans.
        self.panel((40,480,233,54))
        self.text('ITEMS',(85,506),20,YELLOW)
        self.button((137,486,61,41),'OFF',('powerups',False),
                    selected=not self.powerups_enabled,size=20)
        self.button((204,486,61,41),'ON',('powerups',True),
                    selected=self.powerups_enabled,size=20)
        self.panel((283,480,233,54))
        self.text('LINES',(329,506),20,YELLOW)
        self.button((380,486,61,41),'OFF',('lines',False),
                    selected=not self.show_racing_lines,size=20)
        self.button((447,486,61,41),'ON',('lines',True),
                    selected=self.show_racing_lines,size=20)
        self.panel((526,480,234,54))
        self.text('BUMP',(568,506),20,YELLOW)
        self.button((624,486,61,41),'OFF',('interactions',False),
                    selected=not self.interactions_enabled,size=20)
        self.button((692,486,61,41),'ON',('interactions',True),
                    selected=self.interactions_enabled,size=20)
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
            self.text(name,(x+88,359),19 if len(name)>15 else 22,WHITE)
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
        self.title('CHOOSE YOUR KART','Your kart color stays in YOUR corner all race!')
        color=PALETTE[self.kart_ids[current]]
        self.text(f'PLAYER {current+1}',(400,129),50,color)
        for k in range(8):
            col=k%4;row=k//4
            r=pygame.Rect(56+col*176,172+row*139,158,121)
            taken=k in self.kart_ids[:current]
            selected=k==self.kart_ids[current]
            self.panel(r,(64,85,115) if selected else (42,52,75),YELLOW if selected else (89,113,151))
            if selected:
                self.draw_star((r.right-14,r.top+13),11,YELLOW,(113,72,30))
            self.kart_preview(k,(r.centerx,r.top+46),1.02,selected=selected)
            self.text(self.catalog['karts'][k]['name'],(r.centerx,r.bottom-17),21,(154,160,171) if taken else WHITE)
            if taken:
                # Clearly distinguish unavailable karts without hiding their art.
                pygame.draw.rect(self.canvas,(20,27,42),r,2,border_radius=18)
                pygame.draw.line(self.canvas,(224,109,113),r.topleft,r.bottomright,4)
            else:self.action_buttons.append((r,('kart',k)))
        # Four corner amulets show the complete seating arrangement BEFORE
        # anyone starts drawing. The active player's amulet gets a gold halo.
        self.text('SAME FOUR CORNERS FOR BOOSTS AND ITEMS!',(400,449),19,YELLOW)
        action='START DRAWING  >' if current==self.players-1 else 'NEXT PLAYER  >'
        self.button((222,472,356,75),action,('kart_next',None),selected=True,size=32)
        self.button((26,540,149,47),'< TRACKS',('state','tracks'),size=24)
        self.home()
        self.draw_player_amulets('selection')

    def world_to_screen(self,pos):
        return (TRACK_RECT.left+pos[0]*TRACK_RECT.width/MAP_W,
                TRACK_RECT.top+pos[1]*TRACK_RECT.height/MAP_H)

    def screen_to_world(self,pos):
        return (clamp((pos[0]-TRACK_RECT.left)*MAP_W/TRACK_RECT.width,0,MAP_W),
                clamp((pos[1]-TRACK_RECT.top)*MAP_H/TRACK_RECT.height,0,MAP_H))

    def map_base(self):
        self.canvas.fill((18,30,49))
        if self.map_surface is not None:
            base=(self.gorge_hazards.water_frames[
                  int(self.item_box_clock/self.gorge_hazards.water_frame_seconds)%
                  len(self.gorge_hazards.water_frames)]
                  if self.gorge_hazards is not None else self.map_surface)
            self.canvas.blit(base,TRACK_RECT.topleft)
        pygame.draw.rect(self.canvas,(130,151,172),TRACK_RECT,2,border_radius=3)

    def draw_route(self,pts,color,width=4,dashed=False,end_caps=True):
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
        if end_caps and not dashed:
            for p in (points[0],points[-1]):
                pygame.draw.circle(self.canvas,color,(round(p[0]),round(p[1])),5)

    def route_runs_for_layer(self, pts, layer):
        if len(pts)<2:
            return []
        if not self.track or not self.track.has_overpasses():
            return [pts] if layer==0 else []
        runs=[]
        current=[pts[0],pts[1]]
        current_layer=self.track.segment_layer(pts[0],pts[1])
        for i in range(1,len(pts)-1):
            a,b=pts[i],pts[i+1]
            seg_layer=self.track.segment_layer(a,b)
            if seg_layer==current_layer:
                current.append(b)
            else:
                if current_layer==layer and len(current)>=2:
                    runs.append(current)
                current=[a,b]
                current_layer=seg_layer
        if current_layer==layer and len(current)>=2:
            runs.append(current)
        return runs

    def draw_route_layered(self, pts, color, width=4, dashed=False, layer=0):
        runs=self.route_runs_for_layer(pts,layer)
        for run in runs:
            self.draw_route(run,color,width,dashed,end_caps=False)

    def draw_bridge_overlay(self):
        if self.bridge_overlay_surface is not None:
            self.canvas.blit(self.bridge_overlay_surface, self.bridge_overlay_xy)

    def draw_powerup_boxes(self, race=False):
        """Small rotating, bobbing cubes with orbital sparkles and respawn effects.

        The animation uses deterministic per-box phases, no per-frame image
        transforms, and no particle surfaces: inexpensive on Pygbag/iPad.
        """
        if not self.powerups_enabled or not self.pickups:return
        if self.question_mark is None:
            self.question_mark=self.font(30).render('?',True,(255,251,220))
        t=self.item_box_clock
        for box in self.pickups:
            x,y=self.world_to_screen(box.pos)
            if race and not box.available(self.elapsed):
                age=self.elapsed-box.picked_at
                if 0<=age<.52:
                    radius=round(8+age*49)
                    pygame.draw.circle(self.canvas,(255,226,130),(round(x),round(y)),radius,3)
                    pygame.draw.circle(self.canvas,(147,237,248),(round(x),round(y)),max(3,radius-6),2)
                    for j in range(4):
                        theta=j*math.pi/2+age*4
                        self.draw_sparkle((x+math.cos(theta)*radius,y+math.sin(theta)*radius),
                                          3+(1-age)*3,(255,242,166))
                continue
            phase=t*3.0+box.slot*.91
            bob=math.sin(phase)*4.0
            cx,cy=round(x),round(y+bob)
            # Orbiting motes make the pickup visually lively even when the cube
            # is almost edge-on in its fake 3D rotation.
            for j in range(3):
                theta=t*(1.45+j*.15)+box.slot*1.37+j*2*math.pi/3
                orbit=25+2*math.sin(t*2+j+box.slot)
                sx=cx+math.cos(theta)*orbit
                sy=cy+math.sin(theta)*orbit*.62
                mote_color=((255,234,147),(133,244,255),(227,177,255))[j]
                self.draw_sparkle((sx,sy),3.2+1.6*abs(math.sin(phase+j)),mote_color)
            spin=math.sin(phase)
            wide=10+round(7*abs(math.cos(phase)))
            depth=7 if spin>=0 else -7
            pts=[(cx-wide,cy-13),(cx+wide,cy-13),(cx+wide,cy+13),(cx-wide,cy+13)]
            side=[pts[1],(pts[1][0]+depth,pts[1][1]-5),
                  (pts[2][0]+depth,pts[2][1]-5),pts[2]] if spin>=0 else [
                  pts[0],(pts[0][0]+depth,pts[0][1]-5),
                  (pts[3][0]+depth,pts[3][1]-5),pts[3]]
            pygame.draw.ellipse(self.canvas,(37,35,71),(cx-18,cy+14,36,8))
            pygame.draw.polygon(self.canvas,(67,187,228),side)
            pygame.draw.polygon(self.canvas,(144,86,211),pts)
            pygame.draw.polygon(self.canvas,(218,176,255),pts,3)
            pygame.draw.line(self.canvas,(255,238,173),(cx-wide+4,cy-9),(cx+wide-3,cy-9),2)
            self.canvas.blit(self.question_mark,self.question_mark.get_rect(center=(cx,cy+1)))
            self.draw_sparkle((cx+wide+depth+3,cy-15),
                              4+2*abs(math.sin(t*4+box.slot)),(255,251,177))


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
        self.title('YOUR TURN!',('RAINBOW ROCKET - STAR CUP 4/4' if self.track.rocket_data else
                           'GLOW GARDEN - STAR CUP 2/4' if self.track.glow_data else
                          'STARLIGHT SPIRAL - STAR CUP 3/4' if self.track.spiral_data else
                          'PHANTOM BOARDWALK - STAR CUP 1/4'
                          if self.track.phantom_data else
                          f'{self.catalog["cups"][self.cup]} - TRACK {self.track_index+1}/4'
                          if self.race_mode=='cup' else f'{self.track.name} - Pass the screen'))
        p=self.draw_player
        self.text(f'PLAYER {p+1}',(400,165),72,PALETTE[self.kart_ids[p]])
        self.kart_preview(self.kart_ids[p],(400,296),2.3)
        self.text(f'Draw {self.laps} lap'+('s' if self.laps>1 else '')+' - each one is different!',(400,385),32,WHITE)
        self.text('Start at the green dot. Your finger is the pencil.',(400,424),25,MUTED)
        self.button((220,473,360,79),'READY TO DRAW!',('start_draw',None),selected=True,size=37)
        self.home()
        self.draw_player_amulets('preview')

    def ensure_draw_routes_layer(self):
        """Cache prior drawings once per turn, splitting overpass layers.

        In particular, do NOT rasterize four 3-lap previous players' drawings
        twice per frame just because the current course has one bridge.
        """
        cache_key=(self.cup,self.track_index,self.draw_player,
                   len(self.routes),len(self.drawn_laps))
        if self.draw_routes_layer_key==cache_key and self.draw_routes_layer is not None:
            return
        previous=self.canvas
        self.draw_routes_layer=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
        has_bridge=bool(self.track and self.track.has_overpasses())
        self.draw_routes_layer_overpass=(pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
                                          if has_bridge else None)
        try:
            color=PALETTE[self.kart_ids[self.draw_player]]
            for layer in ((0,1) if has_bridge else (0,)):
                self.canvas=(self.draw_routes_layer if layer==0 else self.draw_routes_layer_overpass)
                for idx,route in enumerate(self.routes):
                    if route is not None:
                        if has_bridge:self.draw_route_layered(route.points,PALETTE[self.kart_ids[idx]],3,True,layer)
                        else:self.draw_route(route.points,PALETTE[self.kart_ids[idx]],3,dashed=True)
                for prior in self.drawn_laps:
                    if len(prior)>1:
                        if has_bridge:self.draw_route_layered(prior,color,3,True,layer)
                        else:self.draw_route(prior,color,3,dashed=True)
        finally:
            self.canvas=previous
        self.draw_routes_layer_key=cache_key

    def draw_page(self):
        self.map_base()
        color=PALETTE[self.kart_ids[self.draw_player]]
        if self.track and self.track.has_overpasses():
            self.ensure_draw_routes_layer()
            self.canvas.blit(self.draw_routes_layer,(0,0))
            self.draw_powerup_boxes()
            if self.gorge_hazards is not None:
                self.gorge_hazards.draw(self.canvas,self.world_to_screen)
            if self.canyon_hazards is not None:
                self.canyon_hazards.draw(self.canvas,self.world_to_screen)
            if self.rocket_hazards is not None:
                self.rocket_hazards.draw(self.canvas,self.world_to_screen,layer=0)
            if len(self.draft)>1:
                self.draw_route_layered(self.draft,color,6,dashed=False,layer=0)
            self.draw_start()
            self.draw_bridge_overlay()
            if self.rocket_hazards is not None:
                self.rocket_hazards.draw(self.canvas,self.world_to_screen,layer=1)
            if self.draw_routes_layer_overpass is not None:
                self.canvas.blit(self.draw_routes_layer_overpass,(0,0))
            if len(self.draft)>1:
                self.draw_route_layered(self.draft,color,6,dashed=False,layer=1)
        else:
            self.ensure_draw_routes_layer()
            self.canvas.blit(self.draw_routes_layer,(0,0))
            self.draw_powerup_boxes()
            if self.gorge_hazards is not None:
                self.gorge_hazards.draw(self.canvas,self.world_to_screen)
            if self.canyon_hazards is not None:
                self.canyon_hazards.draw(self.canvas,self.world_to_screen)
            if len(self.draft)>1:self.draw_route(self.draft,color,6)
            self.draw_start()
            if self.phantom_hazards is not None:
                self.phantom_hazards.draw(self.canvas,self.world_to_screen)
                self.draw_bridge_overlay()
            if self.glow_hazards is not None:
                self.glow_hazards.draw(self.canvas,self.world_to_screen)
                self.draw_bridge_overlay()
            if self.spiral_hazards is not None:
                self.spiral_hazards.draw_underlay(self.canvas,self.world_to_screen)
                self.spiral_hazards.draw(self.canvas,self.world_to_screen)
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,72))
        self.text(f'P{self.draw_player+1} - DRAW LAP {len(self.drawn_laps)+1}/{self.laps}',(306,31),34,color)
        self.text(('\u221e' if self.time_left is None else f'{max(0,math.ceil(self.time_left))}s'),(713,30),44,YELLOW)
        warning=self.draw_warning if (self.track.canyon_data or self.track.phantom_data or self.track.rocket_data) else None
        if warning:
            ink=(255,169,91) if warning.startswith('RAMP') else (255,117,108)
            self.text(warning,(380,59),22,ink)
        else:
            self.text('Draw to the green dot. Every lap gets its OWN line!',(380,59),22,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,545,LOGICAL_W,55))
        self.button((25,550,160,43),'CLEAR',('clear',None),size=25)
        self.text(f'LAPS DONE: {len(self.drawn_laps)}/{self.laps}   -   Lift to pause. CLEAR to retry.',(397,571),21,MUTED)
        self.button((624,550,150,43),'FINISH LAP',('draw_done',None),selected=True,size=23)
        self.home()
        self.draw_player_amulets('preview')

    def racer_image(self,kart_id,angle):
        # The supplied kart artwork points to the LEFT in its base image.
        quant=(int(round(math.degrees(angle)/6))*6+180)%360
        key=('race',kart_id,quant)
        if key not in self.kart_rotation_cache:
            img=self.kart_images[kart_id]
            # Selection previews stay large; only the racing karts are smaller.
            scaled=pygame.transform.smoothscale(img,RACE_KART_SIZE)
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
        base=(center[0]-ux*15,center[1]-uy*15)
        power=clamp((r.start_modifier-1.0)/0.45,0.0,1.0)
        life=clamp(r.start_effect_left/REACTION_EFFECT_SECONDS,0.0,1.0)
        flicker=math.sin(self.elapsed*29.0+r.index*2.4)*3.0
        extent=(12.0+14.0*power+flicker)*(0.55+0.45*life)
        breadth=5.0+1.7*power
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
                root=(center[0]-ux*14+nx*side*.74,center[1]-uy*14+ny*side*.74)
                flick=math.sin(t*29+side+r.index)*5
                def at(back,width):
                    return (round(root[0]-ux*back+nx*width),
                            round(root[1]-uy*back+ny*width))
                pygame.draw.polygon(self.canvas,(247,70,43),
                    [at(0,-4),at(25+flick,0),at(0,4)])
                pygame.draw.polygon(self.canvas,(255,209,61),
                    [at(0,-2.5),at(18+flick*.5,0),at(0,2.5)])
                pygame.draw.circle(self.canvas,(255,244,133),at(32+flick,0),3)
        else:
            # Tailwind is a cool turquoise airflow, NOT another orange flame.
            for side in (-1,1):
                for k in range(3):
                    shift=(t*47+k*20+r.index*9)%59
                    side_dist=side*(12+math.sin(t*8+k)*2)
                    a=(round(center[0]-ux*(10+shift)+nx*side_dist),
                       round(center[1]-uy*(10+shift)+ny*side_dist))
                    b=(round(a[0]-ux*(11+k*2)),round(a[1]-uy*(11+k*2)))
                    pygame.draw.line(self.canvas,(74,235,234),a,b,3 if k==0 else 2)
            pygame.draw.circle(self.canvas,(161,255,243),center,21,2)

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

    def draw_tap_icon(self, center, size=22, color=WHITE):
        """Simple child-friendly tap symbol for reflex buttons."""
        x,y=center
        pygame.draw.circle(self.canvas,color,(round(x),round(y-size*0.62)),max(3,int(size*0.16)))
        pygame.draw.rect(self.canvas,color,(round(x-size*0.10),round(y-size*0.52),
                                             max(4,int(size*0.20)),max(16,int(size*0.58))),border_radius=4)
        pygame.draw.rect(self.canvas,color,(round(x-size*0.34),round(y-size*0.05),
                                             max(7,int(size*0.68)),max(6,int(size*0.20))),border_radius=4)
        pygame.draw.arc(self.canvas,color,(round(x-size*0.78),round(y-size*0.86),
                                           max(12,int(size*0.72)),max(12,int(size*0.72))),
                        -0.55,0.55,2)
        pygame.draw.arc(self.canvas,color,(round(x-size*1.00),round(y-size*1.08),
                                           max(12,int(size*1.12)),max(12,int(size*1.12))),
                        -0.55,0.55,2)

    def draw_player_amulets(self, mode='game'):
        """Four permanent corner amulets, with one identity and one tap zone.

        'selection' shows the cart whose color belongs to that corner; 'preview'
        keeps the same layout during route drawing. During the race, the INSIDE
        of each amulet becomes its reflex button, then its item slot. The outer
        ring never changes away from the selected kart color.
        """
        for player,(cx,cy) in enumerate(PLAYER_AMULETS):
            enabled = player < self.players
            color = PALETTE[self.kart_ids[player]] if enabled else (84,96,112)
            racer = (self.racers[player] if mode=='game' and enabled and
                     player < len(self.racers) else None)
            reflex = bool(racer is not None and self.reflex_start and
                          (self.state=='countdown' or
                           (self.state=='race' and self.elapsed<REACTION_WINDOW)))
            active_selection = (enabled and mode in ('selection','preview') and
                                (player==self.kart_player if mode=='selection'
                                 else player==self.draw_player))
            held = racer.held_powerup if racer is not None else None
            running = (racer.powerup_kind if racer is not None and
                       racer.powerup_left>0 else None)
            item_ready = (bool(held) and self.state=='race' and not self.paused
                          and not reflex and running is None)
            clock = self.item_box_clock
            centre=(cx,cy)
            radius=AMULET_RADIUS
            art=self.amulet_art
            socket=bool(enabled and mode=='game' and not reflex and
                        self.powerups_enabled and racer is not None and
                        self.state=='race')
            if art:
                # 96x96 art is centered at (48,48); touch circle still radius 41.
                bg=(art['socket' if socket else 'plain'][self.kart_ids[player]]
                    if enabled else art['off_plain'])
                self.canvas.blit(bg,(cx-48,cy-48))
                halo=('halo_turbo' if running=='turbo' else
                      'halo_tailwind' if running=='tailwind' else
                      'halo_gold' if (active_selection or item_ready or
                                      (reflex and self.state=='race' and
                                       player<len(self.reaction_status) and
                                       self.reaction_status[player]=='waiting')) else None)
                if halo:
                    self.draw_amulet_halo(halo,player,cx,cy)
                if (racer is not None and
                        self.item_box_clock<self.amulet_pressed_until[player]):
                    self.canvas.blit(art['fx']['pressed_overlay'],(cx-48,cy-48))
            else:
                # Preserve the old native Pygame rendering without the art pack.
                pygame.draw.circle(self.canvas,(10,17,29),(cx,cy+3),radius+3)
                tint=(round(color[0]*.20+20),round(color[1]*.20+26),
                      round(color[2]*.20+38))
                pygame.draw.circle(self.canvas,tint,centre,radius-2)
                pygame.draw.circle(self.canvas,color,centre,radius,6)
                pygame.draw.circle(self.canvas,(171,192,208) if enabled else (81,93,107),
                                   centre,radius-7,1)
                if active_selection or item_ready:
                    pulse=2+round(2*abs(math.sin(clock*4.8+player)))
                    pygame.draw.circle(self.canvas,YELLOW,centre,radius+pulse,2)
            badge=(cx-27,cy-27)

            if not enabled:
                self.text('—', (cx,cy+2),30,(122,134,147))
                if art:
                    self.canvas.blit(art['off_badges'][player],(cx-43,cy-43))
                else:
                    pygame.draw.circle(self.canvas,(13,22,37),badge,15)
                    pygame.draw.circle(self.canvas,color,badge,13)
                    self.text(str(player+1),badge,20,WHITE)
                continue

            if mode in ('selection','preview') or (mode=='game' and
                                                 self.state=='countdown' and
                                                 not self.reflex_start):
                kart_id=self.kart_ids[player]
                key=('amulet',kart_id)
                if key not in self.kart_rotation_cache:
                    self.kart_rotation_cache[key]=pygame.transform.smoothscale(
                        self.kart_images[kart_id],(39,29))
                img=self.kart_rotation_cache[key]
                self.canvas.blit(img,img.get_rect(center=(cx,cy-3)))
                label=('PICK' if active_selection else 'KART')
                self.text(label,(cx,cy+24),16,YELLOW if active_selection else WHITE)
            elif reflex:
                status=self.reaction_status[player] if player<len(self.reaction_status) else 'waiting'
                if status=='early':
                    self.text('EARLY',(cx,cy-1),19,(255,163,164))
                    self.text('WAIT',(cx,cy+24),16,WHITE)
                elif status=='boost':
                    self.text('BOOST',(cx,cy-1),20,YELLOW)
                    self.text('GO!',(cx,cy+24),16,WHITE)
                elif status=='late':
                    self.text('OK!',(cx,cy),25,WHITE)
                else:
                    green=self.state=='race'
                    self.draw_tap_icon((cx,cy-5),23,WHITE if green else MUTED)
                    self.text('TAP!' if green else 'WAIT',
                              (cx,cy+25),17,YELLOW if green else MUTED)
                    if green and not art:
                        pygame.draw.circle(self.canvas,YELLOW,centre,radius+2,2)
            elif self.powerups_enabled and racer is not None:
                # Reuse the two established, recognizable TURBO and TAILWIND
                # logos, including the original '?' empty item indicator.
                kind=running if running else held
                self.draw_powerup_icon(kind,(cx,cy-4),34)
                if held and running is None:
                    self.text('PAUSE' if self.paused else 'TAP!',
                              (cx,cy+26),16 if self.paused else 17,
                              MUTED if self.paused else YELLOW)
                elif running:
                    duration=POWERUP_DURATION[running]
                    remaining=clamp(racer.powerup_left/duration,0,1)
                    arc=pygame.Rect(cx-32,cy-32,64,64)
                    if remaining>0:
                        pygame.draw.arc(self.canvas,POWERUP_COLORS[running],arc,
                                        -math.pi/2,-math.pi/2+math.tau*remaining,3)
                    self.text('GO!',(cx,cy+26),16,WHITE)
                else:
                    self.text('EMPTY',(cx,cy+26),14,MUTED)
            else:
                # Items off: leave the amulet and the selected kart visible.
                kart_id=self.kart_ids[player]
                key=('amulet',kart_id)
                if key not in self.kart_rotation_cache:
                    self.kart_rotation_cache[key]=pygame.transform.smoothscale(
                        self.kart_images[kart_id],(39,29))
                sprite=self.kart_rotation_cache[key]
                self.canvas.blit(sprite,sprite.get_rect(center=(cx,cy-3)))
                self.text('KART',(cx,cy+24),16,WHITE)

            # Identity badge on TOP of pocket/logos, as authored in the manifest.
            if art:
                self.canvas.blit(art['badges'][self.kart_ids[player]][player],
                                 (cx-43,cy-43))
            else:
                pygame.draw.circle(self.canvas,(13,22,37),badge,15)
                pygame.draw.circle(self.canvas,color,badge,13)
                self.text(str(player+1),badge,20,INK)

            # Only real racers in the playable state are touch-active. The same
            # button handles both start reaction and later item activation.
            if racer is not None and not self.paused and (reflex or
                  (self.powerups_enabled and self.state=='race' and
                   (not self.reflex_start or self.elapsed>=REACTION_WINDOW))):
                touch=pygame.Rect(cx-AMULET_TOUCH_RADIUS,cy-AMULET_TOUCH_RADIUS,
                                  AMULET_TOUCH_RADIUS*2,AMULET_TOUCH_RADIUS*2)
                self.action_buttons.append((touch,('amulet',player)))

    def display_racers(self, layer=None):
        ordered=([self.active_ghost] if self.active_ghost is not None else [])+self.racers
        for r in ordered:
            if layer is not None and self.track and self.track.has_overpasses():
                # Sprite heading spins during collisions, but the kart must
                # remain on its actual ROAD layer at a figure-eight crossing.
                road_heading=(r.route.sample(r.distance)[1] if self.track.rocket_data
                              else r.heading)
                racer_layer = 1 if self.track.point_on_overpass(r.pos, road_heading) else 0
                if racer_layer != layer:
                    continue
            if self.fall_hazards is not None and r.fall_phase in ('dust','wait','rescue'):
                self.fall_hazards.draw_rescue(self.canvas,self.world_to_screen,r)
                if r.fall_phase=='rescue':
                    # A small kart visibly rises on the cloud's tow rope.
                    _,cart=self.fall_hazards.rescue_positions(
                        self.world_to_screen,r)
                    rescued=self.racer_image(r.kart_id,r.fall_heading)
                    rescued=pygame.transform.smoothscale(rescued,(
                        max(1,int(rescued.get_width()*.54)),
                        max(1,int(rescued.get_height()*.54))))
                    self.canvas.blit(rescued,rescued.get_rect(center=(int(cart[0]),int(cart[1]))))
                continue
            xy=self.world_to_screen(r.pos)
            # Shadows, outlined friendly cartoon karts and a player number.
            if not r.is_ghost:
                pygame.draw.ellipse(self.canvas,(21,28,38),(xy[0]-17,xy[1]+6,34,11))
            img=self.racer_image(r.kart_id,r.heading)
            if self.rocket_hazards is not None:
                factor=clamp(r.kart_scale,.65,1.36)
                # Pre-cache width states every 0.04 to avoid per-frame resizes.
                quant=max(16,min(34,round(factor*25)))
                key=('rocket_kart',r.kart_id,
                     (int(round(math.degrees(r.heading)/6))*6+180)%360,quant)
                if key not in self.kart_rotation_cache:
                    self.kart_rotation_cache[key]=pygame.transform.smoothscale(img,(
                        max(1,round(img.get_width()*quant/25)),
                        max(1,round(img.get_height()*quant/25))))
                img=self.kart_rotation_cache[key]
            if self.fall_hazards is not None:
                if r.flight_left>0:
                    # Shadow stays at road/canyon floor while the kart lifts.
                    shadow=self.canyon_hazards.fall_shadow
                    self.canvas.blit(shadow,shadow.get_rect(center=(int(xy[0]),int(xy[1]+6))))
                    fraction=r.flight_elapsed/max(.01,self.canyon_hazards.jump_time)
                    rise=1.0+.35*math.sin(math.pi*fraction)
                    img=pygame.transform.smoothscale(img,(
                        max(1,round(img.get_width()*rise)),
                        max(1,round(img.get_height()*rise))))
                elif r.fall_phase=='fall':
                    fraction=clamp(r.fall_age/.9,0,1)
                    size=1.0-.85*fraction
                    img=pygame.transform.smoothscale(img,(
                        max(1,round(img.get_width()*size)),
                        max(1,round(img.get_height()*size))))
                    img=pygame.transform.rotate(img,-540*fraction)
                    img.set_alpha(round(255*(1.0-.5*fraction)))
                    self.fall_hazards.draw_rescue(self.canvas,self.world_to_screen,r)
            if r.is_ghost:
                key=('ghost',r.kart_id,int(round(math.degrees(r.heading)/6))*6%360,
                     round(r.kart_scale*25) if self.rocket_hazards is not None else 25)
                if key not in self.kart_rotation_cache:
                    faded=img.copy();faded.set_alpha(95)
                    self.kart_rotation_cache[key]=faded
                img=self.kart_rotation_cache[key]
            center=(int(xy[0]),int(xy[1]))
            if (self.spiral_hazards is not None and r.train_spin_left>0 and
                    r.spin_fx_kind=='cat'):
                # The kart moves in a 10px visual circle, not its world route.
                phase=1-r.train_spin_left/max(.01,r.train_spin_duration)
                offset=(10*math.cos(math.tau*phase),10*math.sin(math.tau*phase))
                center=(round(xy[0]+offset[0]),round(xy[1]+offset[1]))
                self.spiral_hazards.draw_swirl(self.canvas,self.world_to_screen,r)
            self.boost_flame(r,center)
            self.powerup_visuals(r,center)
            self.draw_interaction_effect(r,center)
            if r.train_spin_left>0 and not r.is_ghost:
                phase=1-r.train_spin_left/r.train_spin_duration
                for j in range(4):
                    a=phase*math.tau*2+j*math.tau/4
                    star=(round(center[0]+math.cos(a)*24),
                          round(center[1]+math.sin(a)*19))
                    pygame.draw.circle(self.canvas,(255,224,86),star,4)
                    pygame.draw.circle(self.canvas,(255,255,235),star,2)
            # The kart blinks during the 1.5 seconds of tow immunity.
            visible=not (self.fall_hazards is not None and r.train_immunity_left>0
                         and r.fall_phase is None and int(self.elapsed*16)%2==0)
            if visible:
                self.canvas.blit(img,img.get_rect(center=center))
            if self.fall_hazards is not None and (r.respawn_fx_left>0 or
                    (r.train_immunity_left>0 and r.fall_count>0)):
                self.fall_hazards.draw_sparkles(self.canvas,self.world_to_screen,r)
            if r.is_ghost:continue
            dot=(center[0],center[1]-18)
            pygame.draw.circle(self.canvas,(20,31,52),dot,9)
            pygame.draw.circle(self.canvas,PALETTE[r.kart_id],dot,7)
            self.text(str(r.index+1),dot,16,(23,28,41))

    def race_page(self):
        self.map_base()
        # Draw each kart's untraveled route separately. Previously driven
        # sections disappear immediately, including during lap 2 and lap 3.
        if self.show_racing_lines:
            for racer,trail in self.race_trails:
                trail.draw(self.canvas,racer.distance)
        self.draw_powerup_boxes(race=self.state=='race')
        self.draw_start()
        # Underneath karts and both bridge overlays. Only the ford can hit.
        if self.gorge_hazards is not None:
            self.gorge_hazards.draw(self.canvas,self.world_to_screen)
        if self.canyon_hazards is not None:
            self.canyon_hazards.draw(self.canvas,self.world_to_screen)
        if self.spiral_hazards is not None:
            self.spiral_hazards.draw_underlay(self.canvas,self.world_to_screen)
        if self.track and self.track.has_overpasses():
            if self.rocket_hazards is not None:
                self.rocket_hazards.draw(self.canvas,self.world_to_screen,layer=0)
            self.display_racers(layer=0)
            self.draw_bridge_overlay()
            if self.rocket_hazards is not None:
                self.rocket_hazards.draw(self.canvas,self.world_to_screen,layer=1)
            self.display_racers(layer=1)
        else:
            self.display_racers()
            if self.phantom_hazards is not None:
                self.phantom_hazards.draw(self.canvas,self.world_to_screen)
                # Mansion glass roof is ABOVE both karts and ghost actors.
                self.draw_bridge_overlay()
            if self.glow_hazards is not None:
                self.glow_hazards.draw(self.canvas,self.world_to_screen)
                # The 17 tunnel ribs are a glass overlay ABOVE the karts/fairies.
                self.draw_bridge_overlay()
            if self.spiral_hazards is not None:
                self.spiral_hazards.draw(self.canvas,self.world_to_screen)
        if self.moving_train is not None:
            self.moving_train.draw(self.canvas,self.world_to_screen)
        if self.cactus_hazards is not None:
            self.cactus_hazards.draw(self.canvas,self.world_to_screen)
        pygame.draw.rect(self.canvas,INK,(0,0,LOGICAL_W,73))
        self.text('WASTE KART', (234,27),38,YELLOW)
        if self.state=='countdown':
            self.text('TAP YOUR COLOR ON GREEN!' if self.reflex_start else 'START YOUR ENGINES!',(425,60),24,WHITE)
        else:
            self.text(f'{self.elapsed:05.1f}s',(704,28),38,WHITE)
            self.text(f'{self.laps} LAP'+('S' if self.laps>1 else '')+(' - GHOST' if self.active_ghost else ''),(396,58),24,MUTED)
        pygame.draw.rect(self.canvas,INK,(0,544,LOGICAL_W,56))
        w=(LOGICAL_W-24)/max(1,len(self.racers))
        for index,r in enumerate(self.racers):
            left=10+index*w
            label=f'P{index+1}  '+('FINISH!' if r.finished else f'LAP {min(self.laps,r.completed_laps+1)}/{self.laps}')
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
        if self.paused:
            panel=pygame.Surface((LOGICAL_W,LOGICAL_H),pygame.SRCALPHA)
            panel.fill((11,19,37,185));self.canvas.blit(panel,(0,0))
            self.text('PAUSED',(400,230),72,YELLOW)
            self.button((250,322,300,80),'RESUME',('pause',None),selected=True,size=38)
        elif self.state=='race':
            self.button((668,11,120,48),'PAUSE',('pause',None),size=22)
        self.draw_player_amulets('game')

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
        # Animated celebratory glints occupy the margins, never the result rows.
        shimmer=self.item_box_clock
        for i,(x,y) in enumerate(((52,112),(748,112),(89,454),(712,454))):
            radius=5+2.5*abs(math.sin(shimmer*3.5+i))
            self.draw_sparkle((x,y),radius,(255,226,137))
        ordered=sorted(self.racers,key=lambda r:(r.finish_time if r.finish_time is not None else 1e9,r.index))
        if self.race_mode=='cup':
            final=self.cup_stage==3
            champions=self.cup_winners() if final else []
            self.text(('CUP CHAMPIONS!' if len(champions)>1 else 'CUP CHAMPION!')
                      if final else 'RACE FINISHED!',(400,43),56,YELLOW)
            subtitle=f'{self.catalog["cups"][self.cup]}  -  RACE {self.cup_stage+1} / 4'
            self.text(subtitle,(400,90),28,WHITE)
            # Four small lit milestones show cup progress without needing text.
            for stage in range(4):
                x=369+stage*21
                pygame.draw.circle(self.canvas,(28,42,69),(x,152),9)
                pygame.draw.circle(self.canvas,YELLOW if stage<=self.cup_stage
                                   else (96,115,145),(x,152),6)
                if stage==self.cup_stage:
                    self.draw_star((x,152),4,(255,249,205))
            if final:
                self.draw_trophy((86,108),.85)
                self.draw_trophy((712,108),.85)
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
                pygame.draw.rect(self.canvas,(59,77,102) if place%2==0 else (50,66,91),
                                 pygame.Rect(43,y-22,326,44),border_radius=11)
                self.draw_medal((65,y),place+1,.80)
                self.kart_preview(r.kart_id,(126,y),.42)
                self.text(f'P{r.index+1}',(173,y),28,PALETTE[r.kart_id],align='left')
                self.text(f'{r.finish_time:.1f}s',(353,y),24,WHITE,align='right')
            for rank,who in enumerate(self.cup_standings()):
                y=235+rank*55
                place=self.cup_rank(who)
                pygame.draw.rect(self.canvas,(59,77,102) if rank%2==0 else (50,66,91),
                                 pygame.Rect(427,y-22,332,44),border_radius=11)
                self.draw_medal((450,y),place,.80)
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
            self.draw_trophy((102,83),1.00)
            self.draw_trophy((697,83),1.00)
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
                pygame.draw.rect(self.canvas,(64,79,104) if place%2==0 else (52,69,92),
                                 pygame.Rect(146,y-21,512,43),border_radius=11)
                self.draw_medal((176,y),place+1,.92)
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
        self.draw_warning=None
        self.draw_pointer=None

    def append_draft(self,xy):
        """Record input and notice each REAL return to the finish marker."""
        if self.state!='draw' or not self.draft:
            return
        if len(self.draft)>=1250 or length(self.draft[-1],xy)<8:
            return
        previous=self.draft[-1]
        self.draft.append(xy)
        if self.track.canyon_data:
            # Sample the full pencil stroke, including fast iPad finger swipes.
            # The intended northbound ramp gap is explicitly allowed.
            for i in range(1,max(2,math.ceil(length(previous,xy)/6)+1)):
                p=lerp(previous,xy,i/max(1,math.ceil(length(previous,xy)/6)))
                if self.track.canyon_fall(p):
                    jumping=(245<p[0]<298 and 245<p[1]<350 and
                             xy[1]<previous[1] and
                             any(self.track.canyon_mask('ramp',q)
                                 for q in self.draft[-35:]))
                    if not jumping:
                        self.draw_warning='CANYON AHEAD! Use a bridge or the jump ramp.'
                    elif self.draw_warning is None:
                        self.draw_warning='RAMP JUMP: stay above 160 speed!'
                elif not self.track.on_road(p) and self.draw_warning is None:
                    self.draw_warning='OFF ROAD: your kart will slow down!'
        if self.track.rocket_data:
            steps=max(1,math.ceil(length(previous,xy)/5))
            heading=math.atan2(xy[1]-previous[1],xy[0]-previous[0])
            for j in range(1,steps+1):
                at=lerp(previous,xy,j/steps)
                if self.track.rocket_fall(at,heading):
                    self.draw_warning='OPEN SPACE! Stay on the rainbow road.'
                    break
        if self.track.phantom_data:
            steps=max(1,math.ceil(length(previous,xy)/6))
            for i in range(1,steps+1):
                p=lerp(previous,xy,i/steps)
                if self.track.canyon_fall(p):
                    self.draw_warning='SWAMP GAP! Stay on the boards or an island.'
                    break
                if self.track.phantom_mask('rail_wall_mask',p):
                    if self.draw_warning is None:
                        self.draw_warning='RAIL: this line will slow the kart.'
                elif not self.track.on_road(p) and self.draw_warning is None:
                    self.draw_warning='OFF ROAD: grass islands slow your kart.'
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
        self.draw_warning=None
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
        if self.moving_train is not None:
            self.moving_train.reset()
        if self.cactus_hazards is not None:
            self.cactus_hazards.reset()
        if self.gorge_hazards is not None:
            self.gorge_hazards.reset()
        if self.canyon_hazards is not None:
            self.canyon_hazards.reset()
        if self.phantom_hazards is not None:
            self.phantom_hazards.reset()
        if self.glow_hazards is not None:
            self.glow_hazards.reset()
        if self.spiral_hazards is not None:
            self.spiral_hazards.reset()
        if self.rocket_hazards is not None:
            self.rocket_hazards.reset()
        self.countdown=0.0
        self.elapsed=0.0
        self.paused=False
        self.new_best=False
        self.ghost_target_time=None
        self.racers=[Racer(i,self.kart_ids[i],self.routes[i],laps=self.laps)
                     for i in range(self.players)]
        self.bump_cooldowns={}
        if self.fall_hazards is not None:
            for racer in self.racers:
                racer.canyon_checkpoints=self.fall_hazards.checkpoint_route(racer.route)
                if self.rocket_hazards is not None:
                    racer.kart_scale=self.track.rocket_state(racer.pos,racer.heading)[1]
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
                self.active_ghost.ghost_train_hits=list(record.get('hazard_hits',[]))
                if self.fall_hazards is not None:
                    self.active_ghost.canyon_checkpoints=self.fall_hazards.checkpoint_route(
                        self.active_ghost.route)
                    if self.rocket_hazards is not None:
                        self.active_ghost.kart_scale=self.track.rocket_state(
                            self.active_ghost.pos,self.active_ghost.heading)[1]
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

    def update_interactions(self, dt):
        """Pairwise, deterministic slipstreaming and gentle kart bumps.

        No route coordinates are altered. A child always gets the line they
        drew; other karts only influence speed, with brief visual effects.
        Ghost karts are excluded, and the whole mechanic can be switched off.
        Pairwise checks are O(n²) for at most four players (six comparisons).
        """
        for racer in self.racers:
            racer.drafting=False
            racer.interaction_factor=1.0
            racer.bump_fx_left=max(0.0,racer.bump_fx_left-dt)
        if not self.interactions_enabled or self.players<2:
            return
        for i,a in enumerate(self.racers):
            if a.finished or a.train_spin_left>0 or a.flight_left>0 or a.fall_phase:
                continue
            for b in self.racers[i+1:]:
                if b.finished or b.train_spin_left>0 or b.flight_left>0 or b.fall_phase:
                    continue
                dx=b.pos[0]-a.pos[0]
                dy=b.pos[1]-a.pos[1]
                separation=math.hypot(dx,dy)
                if separation>DRAFT_MAX+3.0:
                    continue
                # Bridge/underpass racers occupy different layers. 2D closeness
                # alone must never create a bump or a slipstream across decks.
                if self.track and self.track.has_overpasses():
                    angle_a=(a.route.sample(a.distance)[1] if self.track.rocket_data
                             else a.heading)
                    angle_b=(b.route.sample(b.distance)[1] if self.track.rocket_data
                             else b.heading)
                    if (self.track.point_on_overpass(a.pos,angle_a) !=
                            self.track.point_on_overpass(b.pos,angle_b)):
                        continue
                # Drafting only works behind a moving kart, facing the same
                # direction. Side-by-side, opposite, or crossing karts do not
                # create unrealistic turbo wind. Neither benefit can stack.
                alignment=(math.cos(a.heading)*math.cos(b.heading)+
                           math.sin(a.heading)*math.sin(b.heading))
                if (alignment>0.86 and separation>=DRAFT_MIN and
                        self.elapsed>BUMP_MIN_TIME):
                    for follower,leader in ((a,b),(b,a)):
                        ux,uy=math.cos(leader.heading),math.sin(leader.heading)
                        ahead=((leader.pos[0]-follower.pos[0])*ux+
                               (leader.pos[1]-follower.pos[1])*uy)
                        sideways=abs((leader.pos[0]-follower.pos[0])*(-uy)+
                                    (leader.pos[1]-follower.pos[1])*ux)
                        if (DRAFT_MIN<=ahead<=DRAFT_MAX and
                                sideways<=DRAFT_HALF_WIDTH and leader.speed>65.0):
                            follower.drafting=True
                            follower.interaction_factor=max(
                                follower.interaction_factor,DRAFT_SPEED_FACTOR)
                # A gentle 'bonk': don't bounce a child off the authored line.
                # Use a cooldown so two karts travelling together aren't
                # permanently slowed or showered with endless sparks.
                bump_radius=BUMP_DISTANCE*(a.kart_scale+b.kart_scale)*.5
                if separation<bump_radius and self.elapsed>BUMP_MIN_TIME:
                    pair=(a.index,b.index)
                    if self.elapsed>=self.bump_cooldowns.get(pair,0.0):
                        self.bump_cooldowns[pair]=self.elapsed+BUMP_COOLDOWN
                        for racer in (a,b):
                            racer.bump_fx_left=BUMP_EFFECT_SECONDS
                        # The kart that approaches from behind slows more;
                        # the leader gets a tiny nudge. For a side impact,
                        # both slow equally. Interaction is intentionally soft.
                        projection=(dx*math.cos(a.heading)+dy*math.sin(a.heading))
                        if alignment>0.65 and abs(projection)>BUMP_DISTANCE*.28:
                            leader=b if projection>0 else a
                            follower=a if projection>0 else b
                            follower.speed*=0.66
                            leader.speed=min(leader.speed*1.04,self.track.max_speed*1.5)
                        else:
                            a.speed*=0.78
                            b.speed*=0.78

    def draw_interaction_effect(self,r,center):
        """Small, allocation-free wake and impact stars under the kart."""
        if (r.is_ghost or self.state!='race' or not self.interactions_enabled):
            return
        ux,uy=math.cos(r.heading),math.sin(r.heading)
        nx,ny=-uy,ux
        if r.drafting:
            wobble=math.sin(self.elapsed*14+r.index)*2
            for side in (-1,1):
                lateral=side*(11+wobble)
                a=(round(center[0]-ux*16+nx*lateral),
                   round(center[1]-uy*16+ny*lateral))
                b=(round(center[0]-ux*29+nx*lateral*1.15),
                   round(center[1]-uy*29+ny*lateral*1.15))
                pygame.draw.line(self.canvas,(117,243,243),a,b,2)
        if r.bump_fx_left>0:
            strength=r.bump_fx_left/BUMP_EFFECT_SECONDS
            radius=7+round(8*strength)
            x,y=center
            for step in range(5):
                angle=step*math.tau/5+self.elapsed*3
                dx,dy=math.cos(angle),math.sin(angle)
                q=(round(x+dx*radius),round(y+dy*radius))
                q2=(round(x+dx*(radius+4)),round(y+dy*(radius+4)))
                pygame.draw.line(self.canvas,(255,231,122),q,q2,2)

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
                                         'powerup_uses':list(r.used_powerups),
                                         'hazard_hits':list(r.train_hit_events)}
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
        elif name=='interactions':self.interactions_enabled=bool(value)
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
        elif name=='amulet':
            if 0<=value<self.players and not self.paused:
                self.amulet_pressed_until[value]=self.item_box_clock+.12
            # No moving or disappearing control: one action at the same corner
            # for the whole race. Reflex has priority during the green window.
            if self.reflex_start and (self.state=='countdown' or
                                      (self.state=='race' and self.elapsed<REACTION_WINDOW)):
                if not self.paused:self.press_reflex(value)
            else:
                self.activate_held_powerup(value)
        elif name=='reflex_press':self.press_reflex(value) # keyboard/legacy support
        elif name=='powerup_press':self.activate_held_powerup(value)
        elif name=='start_draw':self.begin_draw()
        elif name=='clear':
            self.draft=[self.track.centerline[0]]
            self.draw_warning=None
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
                if action[0]=='amulet' and not self.amulet_hit(pos,action[1]):
                    continue
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
                if self.moving_train is not None:
                    self.moving_train.update(dt)
                if self.gorge_hazards is not None:
                    self.gorge_hazards.update(dt)
                self.countdown+=dt
                if self.countdown>=GREEN_AT:
                    self.state='race'
                    self.elapsed=0.0
        elif self.state=='race':
            if not self.paused:
                self.elapsed+=dt
                if self.moving_train is not None:
                    self.moving_train.update(dt)
                if self.cactus_hazards is not None:
                    self.cactus_hazards.update(dt)
                if self.gorge_hazards is not None:
                    self.gorge_hazards.update(dt)
                if self.canyon_hazards is not None:
                    self.canyon_hazards.update(dt)
                if self.phantom_hazards is not None:
                    self.phantom_hazards.update(dt,self.racers)
                if self.glow_hazards is not None:
                    self.glow_hazards.update(dt,self.racers)
                if self.spiral_hazards is not None:
                    self.spiral_hazards.update(dt,self.racers)
                if self.rocket_hazards is not None:
                    self.rocket_hazards.update(dt,self.racers)
                self.update_interactions(dt)
                for racer in self.racers:
                    before=racer.pos
                    before_distance=racer.distance
                    was_flying=racer.flight_left>0
                    racer.update(dt,self.elapsed,self.track)
                    if self.canyon_hazards is not None and not racer.finished and \
                       not racer.fall_phase and not was_flying:
                        # Ramp launch is strictly northbound and requires a
                        # previous contact with the painted ramp's actual mask.
                        if (self.track.canyon_mask('ramp',before) and
                            not self.track.canyon_mask('ramp',racer.pos) and
                            racer.pos[1]<before[1] and
                            abs(angle_delta(racer.heading,-math.pi/2))<.54):
                            dy=racer.pos[1]-before[1]
                            t=clamp((self.canyon_hazards.jump_lip-before[1])/dy,
                                    0,1) if abs(dy)>1e-5 else 1.0
                            lip=lerp(before,racer.pos,t)
                            launch_dist=before_distance+(racer.distance-before_distance)*t
                            racer.start_flight(lip,launch_dist,racer.speed,racer.heading,
                                               self.canyon_hazards.jump_time)
                        elif self.track.canyon_fall(racer.pos):
                            # Swept collision catches narrow side-canyons even
                            # when the kart crosses the mask in a fast frame.
                            racer.begin_fall(self.elapsed)
                        else:
                            for j in range(1,5):
                                at=lerp(before,racer.pos,j/5)
                                if self.track.canyon_fall(at):
                                    racer.pos=at
                                    racer.begin_fall(self.elapsed)
                                    break
                    if (self.phantom_hazards is not None and not racer.finished and
                            not racer.fall_phase and not was_flying and
                            racer.train_immunity_left<=0.0):
                        for j in range(1,7):
                            at=lerp(before,racer.pos,j/6)
                            if self.track.canyon_fall(at):
                                racer.pos=at
                                racer.begin_fall(self.elapsed)
                                break
                    if (self.rocket_hazards is not None and not racer.finished and
                            not racer.fall_phase and not was_flying and
                            racer.train_immunity_left<=0):
                        steps=max(1,math.ceil(length(before,racer.pos)/4))
                        for j in range(1,steps+1):
                            at=lerp(before,racer.pos,j/steps)
                            if self.track.rocket_fall(at,racer.route.sample(
                                    before_distance+(racer.distance-before_distance)*j/steps)[1]):
                                racer.pos=at
                                racer.begin_fall(self.elapsed)
                                break
                    if (self.moving_train is not None and not racer.finished and
                            self.moving_train.hit_test(racer.pos)):
                        racer.hit_by_train(self.elapsed)
                    if (self.cactus_hazards is not None and not racer.finished and
                            self.cactus_hazards.hit_test(racer.pos)):
                        racer.hit_by_cactus(self.elapsed)
                    if self.gorge_hazards is not None and not racer.finished and \
                            racer.train_immunity_left<=0.0:
                        log=self.gorge_hazards.hit_test(before,racer.pos)
                        if log is not None and racer.hit_by_log(self.elapsed):
                            self.gorge_hazards.nudge_on_hit(log,racer.pos)
                    if (self.canyon_hazards is not None and not racer.finished and
                            not racer.fall_phase and not racer.flight_left and
                            racer.train_immunity_left<=0):
                        if self.canyon_hazards.hit_test(before,racer.pos):
                            racer.hit_by_comet(self.elapsed)
                    if (self.phantom_hazards is not None and not racer.finished
                            and not racer.fall_phase and not racer.flight_left
                            and racer.train_immunity_left<=0.0 and
                            not racer.train_spin_left):
                        actor=self.phantom_hazards.hit_test(before,racer.pos)
                        if actor is not None and racer.hit_by_phantom(self.elapsed):
                            self.phantom_hazards.ghost_hit(actor)
                    if (self.glow_hazards is not None and not racer.finished and
                            not racer.fall_phase and not racer.flight_left and
                            racer.train_immunity_left<=0 and not racer.train_spin_left):
                        fairy=self.glow_hazards.hit_test(before,racer.pos)
                        if fairy is not None and racer.hit_by_fairy(self.elapsed):
                            self.glow_hazards.on_hit(fairy)
                    if (self.spiral_hazards is not None and not racer.finished and
                            not racer.fall_phase and not racer.flight_left and
                            racer.train_immunity_left<=0 and not racer.train_spin_left):
                        cat=self.spiral_hazards.hit_test(before,racer.pos)
                        if cat is not None and racer.hit_by_cat(self.elapsed):
                            self.spiral_hazards.on_hit(cat)
                    if (self.rocket_hazards is not None and not racer.finished and
                            not racer.fall_phase and not racer.flight_left and
                            racer.train_immunity_left<=0 and not racer.train_spin_left):
                        chomper=self.rocket_hazards.hit_test(before,racer.pos,racer)
                        if chomper is not None and racer.hit_by_rocket(self.elapsed):
                            self.rocket_hazards.on_hit(chomper)
                    if not racer.fall_phase and not racer.flight_left:
                        self.try_collect_powerups(racer,before)
                if self.active_ghost is not None:
                    ghost=self.active_ghost
                    previous=ghost.pos
                    old_distance=ghost.distance
                    flying=ghost.flight_left>0
                    ghost.update(dt,self.elapsed,self.track)
                    if self.canyon_hazards is not None and not ghost.finished and \
                       not ghost.fall_phase and not flying and \
                       self.track.canyon_mask('ramp',previous) and \
                       not self.track.canyon_mask('ramp',ghost.pos) and \
                       ghost.pos[1]<previous[1] and \
                       abs(angle_delta(ghost.heading,-math.pi/2))<.54:
                        dy=ghost.pos[1]-previous[1]
                        t=clamp((self.canyon_hazards.jump_lip-previous[1])/dy,
                                0,1) if abs(dy)>1e-5 else 1.0
                        ghost.start_flight(lerp(previous,ghost.pos,t),
                            old_distance+(ghost.distance-old_distance)*t,
                            ghost.speed,ghost.heading,self.canyon_hazards.jump_time)
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
