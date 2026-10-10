"""WasteTrain 2.4 — creative railway sandbox for young children.

Classic grid building and finger-drawn spline rails coexist in one railway graph.
Scenery/stations are loaded from assets/wasteTrain; grass keeps its old asset.
Drop-in GameHub entry point: await wasteTrain.main(screen, clock).

Controls: TILES / DRAW / ERASE / MOVE, two-finger pan, NEW (twice to confirm).
Station, bridge and horizontal tunnel ports are ready-made snap nodes.
Tracks are generated in Pygame as connected polylines, not tile PNGs.
Version 2.4: static world cached and resized only when zoom changes; camera
movement uses cropped blits, and trains draw separately at the target zoom.
A tunnel is one continuous left-to-right structure with a hidden traversable
rail edge; trains vanish beneath the hill and reappear on the other side.
Trains automatically follow connected rail lines, without goals.
"""

import asyncio
import heapq
import json
import math
import os
import random
from collections import defaultdict

import pygame

FPS = 60
COLS, ROWS, CELL = 27, 20, 55
WORLD_W, WORLD_H = COLS * CELL, ROWS * CELL
TOPBAR = 70
SNAP_RADIUS = 39.0
# Rail gauge and sleepers are intentionally about twice their previous size.
RAIL_HALF_GAUGE = 12.0
TIE_HALF_LENGTH = 20.0
ZOOM_MAX = 1.55
ZOOM_STEP = 0.05  # Pinch zoom is accumulated smoothly but rendered in 5% levels.
GUIDE_TIME_MS = 6500
GRASS_FALLBACK = (119, 180, 105)
BROWN = (124, 76, 39)
DARK = (34, 63, 52)
CREAM = (255, 247, 211)
BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets", "wasteTrain")


def dst(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def between(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def key(p):
    return (round(float(p[0]), 3), round(float(p[1]), 3))


def point_to_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    norm = vx * vx + vy * vy
    t = max(0., min(1., ((p[0]-a[0])*vx + (p[1]-a[1])*vy)/norm)) if norm else 0.
    q = between(a, b, t)
    return dst(p, q), q, t


def segment_cross(a, b, c, d):
    """Intersection parameters, excluding collinear overlap."""
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = d[0] - c[0], d[1] - c[1]
    determinant = vx * wy - vy * wx
    if abs(determinant) < 1e-7:
        return None
    dx, dy = c[0] - a[0], c[1] - a[1]
    t = (dx * wy - dy * wx) / determinant
    u = (dx * vy - dy * vx) / determinant
    if -1e-6 <= t <= 1+1e-6 and -1e-6 <= u <= 1+1e-6:
        return max(0., min(1., t)), max(0., min(1., u))
    return None


def smooth_stroke(raw, spacing=7.0):
    """Catmull–Rom, oversampling then approximately equidistant points."""
    if len(raw) < 2:
        return raw[:]
    filtered = [raw[0]]
    for p in raw[1:]:
        if dst(p, filtered[-1]) >= 2.0:
            filtered.append(p)
    if len(filtered) < 2:
        return filtered
    dense = [filtered[0]]
    for i in range(len(filtered)-1):
        a, b = filtered[max(0, i-1)], filtered[i]
        c, d = filtered[i+1], filtered[min(i+2, len(filtered)-1)]
        steps = max(2, int(dst(b, c)/3.5))
        for j in range(1, steps+1):
            t = j / steps
            t2, t3 = t*t, t*t*t
            dense.append((0.5*(2*b[0]+(-a[0]+c[0])*t+(2*a[0]-5*b[0]+4*c[0]-d[0])*t2+(-a[0]+3*b[0]-3*c[0]+d[0])*t3),
                          0.5*(2*b[1]+(-a[1]+c[1])*t+(2*a[1]-5*b[1]+4*c[1]-d[1])*t2+(-a[1]+3*b[1]-3*c[1]+d[1])*t3)))
    result = [filtered[0]]
    distance_since = 0.0
    for a, b in zip(dense, dense[1:]):
        length = dst(a, b)
        if length < .001:
            continue
        travelled = spacing-distance_since
        while travelled <= length:
            result.append(between(a, b, travelled/length))
            travelled += spacing
        distance_since = (distance_since+length) % spacing
    if dst(result[-1], filtered[-1]) > 0.2:
        result.append(filtered[-1])
    else:
        result[-1] = filtered[-1]
    return result


class RailNetwork:
    """A split-edge graph. Freehand crossings and endpoints form real junctions."""

    def __init__(self):
        self.graph = {}
        self.points = {}
        self.visible_segments = []
        self.edges = []

    def rebuild(self, grid, curves, station_ports, tunnels, bridge):
        raw = []  # [(a,b,kind,stroke_id,segment_index)]
        add = lambda a, b, kind, group, index: raw.append((key(a), key(b), kind, group, index))
        grid_pts = {g: ((g[0]+.5)*CELL, (g[1]+.5)*CELL) for g in grid}
        for x, y in grid:
            for nb in ((x+1, y), (x, y+1)):
                if nb in grid:
                    add(grid_pts[(x,y)], grid_pts[nb], 'normal', ('grid',x,y), 0)
        # Draw isolated tiles as short track stubs, not as empty nodes.
        for x, y in grid:
            if not any((x+dx,y+dy) in grid for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                p = grid_pts[(x,y)]
                add((p[0]-CELL*.2, p[1]), (p[0]+CELL*.2,p[1]),
                    'normal', ('stub',x,y), 0)
        for index, curve in enumerate(curves):
            for j,(a,b) in enumerate(zip(curve,curve[1:])):
                if dst(a,b) > .1:
                    add(a,b,'normal',('curve',index),j)
        for index, (a,b) in enumerate(tunnels):
            add(a,b,'tunnel',('tunnel',index),0)
        if bridge is not None:
            a,b=bridge
            add(a,b,'bridge',('bridge',0),0)

        splits = [[(0.0, a), (1.0, b)] for a,b,*_ in raw]
        # Candidate lookup in 48px spatial buckets: keeps crossing detection fast.
        buckets = defaultdict(list)
        cell = 48
        for i,(a,b,kind,group,j) in enumerate(raw):
            if kind == 'tunnel' or kind == 'bridge':
                continue  # An invisible tunnel / raised bridge has no mid-span switches.
            xmin,xmax=sorted((a[0],b[0])); ymin,ymax=sorted((a[1],b[1]))
            candidates = set()
            for bx in range(int(xmin//cell),int(xmax//cell)+1):
                for by in range(int(ymin//cell),int(ymax//cell)+1):
                    candidates.update(buckets[(bx,by)])
            for old in candidates:
                c,d,other_kind,other_group,k=raw[old]
                if group == other_group and abs(j-k)<=1:
                    continue
                found=segment_cross(a,b,c,d)
                if found is None:
                    continue
                t,u=found
                q=key(between(a,b,t))
                splits[i].append((t,q))
                splits[old].append((u,q))
            for bx in range(int(xmin//cell),int(xmax//cell)+1):
                for by in range(int(ymin//cell),int(ymax//cell)+1):
                    buckets[(bx,by)].append(i)

        # Explicitly attach stroke endpoints to existing edges, even if they
        # touch a segment without geometrically crossing through it.
        endpoints=[]
        for curve in curves:
            if len(curve)>=2:
                endpoints.extend((key(curve[0]),key(curve[-1])))
        graph = defaultdict(dict)
        for endpoint in endpoints:
            near = (0.85, None, None, None)
            for i,(a,b,kind,group,j) in enumerate(raw):
                if kind=='tunnel' or kind=='bridge':
                    continue
                dd,q,t=point_to_segment(endpoint,a,b)
                if dd < near[0]:
                    near=(dd,i,key(q),t)
            _,i,q,t=near
            if i is not None:
                splits[i].append((t, endpoint if dst(endpoint,q)<0.004 else q))
                if q!=endpoint:
                    graph[endpoint][q]=(max(dst(endpoint,q),.001),'normal')
                    graph[q][endpoint]=(max(dst(endpoint,q),.001),'normal')
        for i, (a,b,kind,group,j) in enumerate(raw):
            ordered=sorted(splits[i],key=lambda x:x[0])
            for (_,p),(_,q) in zip(ordered,ordered[1:]):
                if p==q:
                    continue
                dd=dst(p,q)
                graph[p][q]=(dd,kind)
                graph[q][p]=(dd,kind)
        # Ports are navigable graph nodes even before anything is connected.
        for p in station_ports:
            graph.setdefault(key(p),{})
        for a,b in tunnels:
            graph.setdefault(key(a),{})
            graph.setdefault(key(b),{})
        if bridge:
            graph.setdefault(key(bridge[0]),{})
            graph.setdefault(key(bridge[1]),{})
        self.graph = dict(graph)
        self.visible_segments = [(a,b,kind,group) for a,b,kind,group,_ in raw if kind != 'tunnel']
        self.edges = raw

    def nearest(self, p, max_distance=SNAP_RADIUS):
        """Snap to a *point on any visible rail edge*, not just curve ends."""
        best_distance = max_distance
        answer = p
        for a,b,kind,*_ in self.edges:
            if kind=='tunnel' or kind=='bridge':
                continue
            d,q,_=point_to_segment(p,a,b)
            if d < best_distance:
                best_distance=d
                answer=q
        for node in self.graph:
            if dst(p,node) < best_distance:
                best_distance=dst(p,node)
                answer=node
        return answer

    def path(self,start,end):
        start,end=key(start),key(end)
        if start not in self.graph or end not in self.graph:
            return []
        heap=[(0.0,start)]
        dist_map={start:0.0}
        prev={}
        while heap:
            d,node=heapq.heappop(heap)
            if d > dist_map[node]+1e-5:
                continue
            if node==end:
                result=[node]
                while node in prev:
                    node=prev[node]
                    result.append(node)
                return result[::-1]
            for nxt,(length,kind) in self.graph[node].items():
                alt=d+length
                if alt < dist_map.get(nxt, float('inf'))-1e-5:
                    dist_map[nxt]=alt
                    prev[nxt]=node
                    heapq.heappush(heap,(alt,nxt))
        return []

    def reachable(self, source):
        source=key(source)
        if source not in self.graph:
            return set()
        visited={source}
        stack=[source]
        while stack:
            node=stack.pop()
            for nxt in self.graph[node]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        return visited



def rail_paths(network):
    """Join degree-two rail nodes into continuous polylines.

    Grid tracks and free-drawn curves use the SAME path collection. Sleepers
    keep their spacing around bends, rather than starting over at each tile.
    Tunnel/bridge interiors are handled by their dedicated artwork.
    """
    neighbors = {}
    for a, links in network.graph.items():
        for b, (distance, kind) in links.items():
            if kind != 'normal' or distance < 0.01:
                continue
            neighbors.setdefault(a, set()).add(b)
    visited=set()
    paths=[]
    def edge(a,b):
        return (a,b) if a<b else (b,a)
    def walk(a,b):
        chain=[a,b]
        visited.add(edge(a,b))
        prev,cur=a,b
        for _ in range(len(neighbors)+2):
            nexts=neighbors.get(cur,set())
            if len(nexts)!=2:
                break
            nextnode=next((n for n in nexts if n!=prev), None)
            if nextnode is None or edge(cur,nextnode) in visited:
                break
            visited.add(edge(cur,nextnode))
            chain.append(nextnode)
            prev,cur=cur,nextnode
        return chain
    for a in sorted(neighbors):
        if len(neighbors[a]) != 2:
            for b in sorted(neighbors[a]):
                if edge(a,b) not in visited:
                    paths.append(walk(a,b))
    # Closed loops have no degree!=2 starting point.
    for a in sorted(neighbors):
        for b in sorted(neighbors[a]):
            if edge(a,b) not in visited:
                paths.append(walk(a,b))
    return paths


def rail_offsets(points, half_width=RAIL_HALF_GAUGE):
    """Miter-joined parallel rails, with safe handling of sharp turns."""
    if len(points)<2:
        return [],[]
    normals=[]
    for a,b in zip(points,points[1:]):
        length=max(.0001,dst(a,b))
        normals.append((-(b[1]-a[1])/length,(b[0]-a[0])/length))
    plus=[];minus=[]
    for i,p in enumerate(points):
        if i==0:
            vx,vy=normals[0];scale=half_width
        elif i==len(points)-1:
            vx,vy=normals[-1];scale=half_width
        else:
            nx,ny=normals[i-1];mx,my=normals[i]
            sx,sy=nx+mx,ny+my
            mag=math.hypot(sx,sy)
            if mag<0.001:
                vx,vy=mx,my;scale=half_width
            else:
                vx,vy=sx/mag,sy/mag
                # At 90deg the miter extends ~sqrt(2)*rail width.
                dot=max(.50,abs(vx*mx+vy*my))
                scale=min(half_width*2.,half_width/dot)
        plus.append((p[0]+vx*scale,p[1]+vy*scale))
        minus.append((p[0]-vx*scale,p[1]-vy*scale))
    return plus,minus


def paint_rail_network(surface,network):
    """Layered continuous rail geometry. No per-tile rail/sleeper resets."""
    paths=rail_paths(network)
    # Paint ALL ballast before ANY sleepers or metallic rails. This avoids
    # one segment's ballast covering its neighbor's rails at connections.
    for path in paths:
        if len(path)<2:continue
        pygame.draw.lines(surface,(123,96,70),False,path,44)
        for p in path:
            pygame.draw.circle(surface,(123,96,70),(round(p[0]),round(p[1])),22)
        pygame.draw.lines(surface,(212,185,132),False,path,36)
        for p in path:
            pygame.draw.circle(surface,(212,185,132),(round(p[0]),round(p[1])),18)
    # Lay sleepers every 15 world pixels along each uninterrupted route.
    # No extra 'first sleeper' at every classic-grid tile boundary.
    for path in paths:
        distance_to_next=5.0
        for a,b in zip(path,path[1:]):
            span=dst(a,b)
            if span<.001:continue
            vx=(b[0]-a[0])/span;vy=(b[1]-a[1])/span
            nx,ny=-vy,vx
            step=distance_to_next
            while step<=span+0.0001:
                q=between(a,b,step/span)
                p1=(q[0]+nx*TIE_HALF_LENGTH,q[1]+ny*TIE_HALF_LENGTH)
                p2=(q[0]-nx*TIE_HALF_LENGTH,q[1]-ny*TIE_HALF_LENGTH)
                pygame.draw.line(surface,(112,66,43),p1,p2,7)
                pygame.draw.line(surface,(183,117,66),p1,p2,3)
                step+=15.
            distance_to_next=step-span
    # Miter joins match adjacent track pieces exactly. Round endpoints prevent
    # 1px seams caused by integer rasterization at multiway junctions.
    for path in paths:
        left,right=rail_offsets(path,RAIL_HALF_GAUGE)
        for rail in (left,right):
            if len(rail)<2:continue
            pygame.draw.lines(surface,(51,64,72),False,rail,7)
            pygame.draw.lines(surface,(230,237,235),False,rail,3)
            for p in (rail[0],rail[-1]):
                pygame.draw.circle(surface,(80,91,93),(round(p[0]),round(p[1])),4)
                pygame.draw.circle(surface,(230,237,235),(round(p[0]),round(p[1])),2)


class ToyTrain:
    """A single continuous, unteleporting train on the connected rail graph.

    Active rides persist when rails are edited. At a terminus, the new ride
    starts at the SAME graph node or the train pauses; it never respawns on
    a remote track, nor moves to another connected component unexpectedly.
    """

    def __init__(self, net, stations, rng, focus=None):
        self.net, self.stations, self.rng = net, stations, rng
        self.focus = key(focus) if focus is not None else None
        self.pending_net = None
        self.nodes = []
        self.distances = []
        self.length = 0.0
        self.travel = 0.0
        self.speed = 66.0  # Child-friendly: slow enough to follow by eye.
        self.destination = None
        self.active = True
        self.wait_at_end = 0.0
        self.stopped = False
        self.wagons = ['wagon_passenger_red', 'wagon_passenger_blue',
                       'wagon_freight_green']
        self.odometer = 0.0
        self.history = []
        self.choose_new_ride()
        first = self.sample(0)
        if first is not None:
            self.history = [(0.0, first)]

    def queue_network(self, new_net):
        """Use changed geometry after the current journey finishes."""
        self.pending_net = new_net

    def set_route(self, path):
        self.nodes = path
        self.distances = [0.0]
        for a, b in zip(path, path[1:]):
            self.distances.append(self.distances[-1] + dst(a, b))
        self.length = self.distances[-1]
        self.travel = 0.0
        self.destination = path[-1]
        self.stopped = False

    def choose_new_ride(self, source=None):
        net = self.net
        ports = [key(p) for p in self.stations]
        # A source means the current train already exists. Never select a new
        # disconnected component in that case.
        if source is not None:
            source = key(source)
            if source not in net.graph or not net.graph[source]:
                self.stopped = True
                return False
            components = [net.reachable(source)]
        else:
            components = []
            examined = set()
            for node in net.graph:
                if node in examined:
                    continue
                component = net.reachable(node)
                examined.update(component)
                if len(component) > 1:
                    components.append(component)
            if self.focus is not None and components:
                closest = min(net.graph, key=lambda p: dst(p, self.focus))
                focused = [c for c in components if closest in c]
                if focused and dst(closest, self.focus) <= CELL:
                    components = focused
        if not components:
            self.stopped = True
            return False
        candidates = []
        for component in components:
            stops = [p for p in ports if p in component and net.graph[p]]
            start = source if source is not None else (
                self.rng.choice(stops) if stops else min(component))
            # Prefer rides that visit a different station; otherwise follow a
            # connected track to its farthest point, including short ones.
            targets = [p for p in stops if p != start]
            if not targets:
                farthest = max(component, key=lambda p: dst(start,p))
                if farthest != start:
                    targets = [farthest]
                else:
                    targets = [p for p in net.graph[start] if p != start]
            for end in targets:
                path = net.path(start, end)
                if len(path) >= 2:
                    length = sum(dst(a,b) for a,b in zip(path,path[1:]))
                    if length > 1.0:
                        candidates.append((length,path))
        if not candidates:
            self.stopped = True
            return False
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = self.rng.choice(candidates[:min(3,len(candidates))])[1]
        assert source is None or chosen[0] == source, 'Route must remain continuous'
        self.set_route(chosen)
        return True

    def change_at_terminus(self):
        endpoint = self.destination
        if self.pending_net is not None:
            pending = self.pending_net
            self.pending_net = None
            # Change networks only when the current endpoint still exists.
            # Otherwise freeze in place, rather than jumping to a new segment.
            if endpoint in pending.graph and pending.graph[endpoint]:
                self.net = pending
            else:
                self.stopped = True
                return
        self.choose_new_ride(endpoint)

    def update(self, dt):
        if not self.active or self.stopped or len(self.nodes) < 2:
            return
        if self.wait_at_end > 0.0:
            self.wait_at_end -= dt
            if self.wait_at_end <= 0.0:
                self.change_at_terminus()
            return
        remaining = self.speed * dt
        while remaining > 0.0001 and not self.stopped:
            delta = min(remaining, max(0.0, self.length-self.travel))
            self.travel += delta
            self.odometer += delta
            sampled = self.sample(self.travel)
            if sampled is not None:
                self.history.append((self.odometer,sampled))
            remaining -= delta
            if self.travel >= self.length-0.001:
                self.wait_at_end = 0.5
                break
        cutoff = self.odometer - (len(self.wagons)*58 + 115)
        while len(self.history) > 2 and self.history[1][0] < cutoff:
            self.history.pop(0)

    def wagon_sample(self, offset):
        """Return previous distance along the *actual traversed route*."""
        wanted = self.odometer-offset
        if wanted < 0 or not self.history or wanted < self.history[0][0]:
            return None
        for j in range(len(self.history)-1):
            before,a = self.history[j]
            after,b = self.history[j+1]
            if wanted <= after:
                t = max(0.,min(1.,(wanted-before)/max(.0001,after-before)))
                p = between(a[0],b[0],t)
                # Angle of the *local traveled path*, not a random destination.
                angle = (-math.degrees(math.atan2(b[0][1]-a[0][1],
                            b[0][0]-a[0][0])) if dst(a[0],b[0]) > .01 else a[1])
                kind = a[2] if t < 0.5 else b[2]
                return p,angle,kind
        return self.history[-1][1]

    def sample(self, travelled):
        if len(self.nodes) < 2:
            return None
        travelled = max(0.,min(self.length,travelled))
        for i in range(len(self.nodes)-1):
            start,end = self.distances[i:i+2]
            if travelled <= end or i == len(self.nodes)-2:
                t = (travelled-start)/max(.001,end-start)
                a,b = self.nodes[i:i+2]
                pos = between(a,b,t)
                angle = -math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))
                kind = self.net.graph[a][b][1]
                return pos,angle,kind
        return None


class WasteTrainWorld:
    def __init__(self,screen):
        self.screen=screen
        self.sw,self.sh=screen.get_size()
        self.viewport=pygame.Rect(0,TOPBAR,self.sw,max(1,self.sh-TOPBAR))
        self.camera=[65.,70.]
        self.zoom=1.0
        self.zoom_goal=1.0  # Continuous accumulation; avoid dropping tiny pinch movements.
        self.follow_train=False
        self.static_world=None  # The assembled full-resolution background.
        self.static_zoom=None  # The background scaled to the current zoom.
        self.static_zoom_key=None
        self.grid_overlay=None  # Viewport-sized, subtle guide only when needed.
        self.grid_overlay_key=None
        self.draw_surface=None
        self.font=pygame.font.Font(None,22)
        self.titlefont=pygame.font.Font(None,28)
        self.rng=random.Random()
        self.mode='grid'
        self.dragging=False
        self.pointer_last=None
        self.stroke=[]
        self.last_tile=None
        self.grid=set()
        self.curves=[]
        self.buttons={}
        self.guide_until=pygame.time.get_ticks()+GUIDE_TIME_MS
        self.sprite_manifest=self.load_sprite_manifest()
        self.assets=self.load_assets()
        self.structure_cache={}
        self.rotate_cache={}
        self.fallback_trains={}
        self.make_grass()
        self.make_grid_guide()
        self.new_world()

    def load_sprite_manifest(self):
        """Read sprite anchors and rail ports from module/cwd asset paths."""
        for path in (os.path.join(ASSETS,'sprites_manifest.json'),
                     os.path.join('assets','wasteTrain','sprites_manifest.json'),
                     os.path.join('WasteGame','assets','wasteTrain','sprites_manifest.json')):
            try:
                with open(path,encoding='utf-8') as f:
                    data=json.load(f)
                return {entry['name']:entry for entry in data['sprites']}
            except (OSError,ValueError,KeyError,TypeError):
                continue
        print('WasteTrain: sprite metadata missing; using default anchors')
        return {}

    def structure_anchors(self, sprite_name):
        """Normalized rail endpoints; default coordinates match supplied PNGs."""
        defaults={
            'tunnel_horizontal':((0.015,0.70),(0.985,0.70)),
            'bridge_horizontal':((0.012,0.36),(0.988,0.36)),
        }
        entry=self.sprite_manifest.get(sprite_name,{})
        ports=entry.get('entry_points_norm',{})
        left=ports.get('left_port') or ports.get('left_rail')
        right=ports.get('right_port') or ports.get('right_rail')
        if not left or not right or right[0]-left[0]<0.2:
            return defaults[sprite_name]
        return tuple(left),tuple(right)

    def draw_structure(self, sprite_name, a, b):
        """Fit the full structure across the *actual* rail node positions.

        The endpoints are in world coordinates. The image is positioned using
        its normalized PNG rail connection points, not its rectangle center,
        so its outer rails meet tiles and freeform tracks exactly.
        """
        src=self.assets.get(sprite_name)
        if src is None:
            self.draw_track((self.to_screen(a),self.to_screen(b)),self.draw_surface)
            return
        left,right=self.structure_anchors(sprite_name)
        span=right[0]-left[0]
        width=max(1,round((b[0]-a[0])/span))
        # Scale using the native aspect ratio (same scale in both axes).
        height=max(1,round(width*src.get_height()/src.get_width()))
        cache_key=(sprite_name,width,height)
        if cache_key not in self.structure_cache:
            self.structure_cache[cache_key]=pygame.transform.smoothscale(src,(width,height))
        sprite=self.structure_cache[cache_key]
        x=round(a[0]-width*left[0]-self.camera[0])
        y=round(a[1]-height*left[1]-self.camera[1])
        rect=pygame.Rect(x,y,width,height)
        if rect.colliderect(self.draw_surface.get_rect()):
            self.draw_surface.blit(sprite,rect)

    def asset_candidates(self,relative):
        """Pygbag often uses a virtual cwd; try both module and cwd assets."""
        parts=relative.split('/')
        return [os.path.join(ASSETS,*parts),
                os.path.join('assets','wasteTrain',*parts),
                os.path.join('WasteGame','assets','wasteTrain',*parts)]

    def load_assets(self):
        # Old artwork remains available as a station; the legacy track images
        # and old train/wagon files are not needed by this renderer.
        asset_files={
            'station_old':'station.png',
            'station_blue':'stations/station_blue.png',
            'station_red':'stations/station_red.png',
            'station_green':'stations/station_green.png',
            'tree_broadleaf':'scenery/tree_broadleaf.png',
            'tree_pine':'scenery/tree_pine.png',
            'rock_cluster':'scenery/rock_cluster.png',
            'flower_bush':'scenery/flower_bush.png',
            'pond':'scenery/pond.png',
            'tunnel_horizontal':'scenery/tunnel_horizontal.png',
            'bridge_horizontal':'scenery/bridge_horizontal.png',
            'flower_patch':'scenery/flower_patch.png',
            'grass_tuft':'scenery/grass_tuft.png',
            'locomotive_red':'trains/locomotive_red.png',
            'locomotive_blue':'trains/locomotive_blue.png',
            'wagon_passenger_red':'trains/wagon_passenger_red.png',
            'wagon_passenger_blue':'trains/wagon_passenger_blue.png',
            'wagon_freight_green':'trains/wagon_freight_green.png',
            'wagon_tanker_gold':'trains/wagon_tanker_gold.png',
            'wagon_logs':'trains/wagon_logs.png',
            'wagon_coal_gray':'trains/wagon_coal_gray.png',
        }
        sizes={
            'station_old':(245,163),'station_blue':(220,160),
            'station_red':(220,160),'station_green':(220,160),
            'tree_broadleaf':(105,105),'tree_pine':(76,114),
            'rock_cluster':(110,83),'flower_bush':(62,49),
            'pond':(270,185),
            'tunnel_horizontal':(629,231),'bridge_horizontal':(553,227),
            'flower_patch':(55,40), 'grass_tuft':(42,34),
            # Locomotive and wagons have similar wheel-center heights.
            'locomotive_red':(91,57),'locomotive_blue':(91,57),
            'wagon_passenger_red':(74,49),
            'wagon_passenger_blue':(74,49),'wagon_freight_green':(70,49),
            'wagon_tanker_gold':(74,49),'wagon_logs':(74,49),
            'wagon_coal_gray':(74,49),
        }
        result={}
        self.missing_assets=[]
        for name,relative in asset_files.items():
            sprite=None
            for path in self.asset_candidates(relative):
                try:
                    sprite=pygame.image.load(path).convert_alpha()
                    break
                except (OSError,pygame.error):
                    continue
            if sprite is None:
                self.missing_assets.append(relative)
                result[name]=None
                continue
            bounds=sprite.get_bounding_rect(min_alpha=10)
            if bounds.width>0 and bounds.height>0:
                sprite=sprite.subsurface(bounds).copy()
            width,height=sizes[name]
            scale=min(width/max(1,sprite.get_width()), height/max(1,sprite.get_height()))
            dimensions=(max(1,round(sprite.get_width()*scale)),
                        max(1,round(sprite.get_height()*scale)))
            result[name]=pygame.transform.smoothscale(sprite,dimensions)
        if self.missing_assets:
            print('WasteTrain missing sprites (upload the entire assets/wasteTrain folder):',
                  ', '.join(self.missing_assets))
        return result

    def make_grass(self):
        grass_path=os.path.join(BASE,'assets','hungryHedgie','grass.png')
        try:
            original=pygame.image.load(grass_path).convert()
            self.grass=pygame.transform.smoothscale(original,(WORLD_W,WORLD_H))
        except (OSError,pygame.error):
            self.grass=pygame.Surface((WORLD_W,WORLD_H)).convert()
            self.grass.fill(GRASS_FALLBACK)
        # Tiny decorative patches laid ON TOP of the old grass, not opaque grid tiles.
        rng=random.Random(128)
        tint=pygame.Surface((WORLD_W,WORLD_H),pygame.SRCALPHA)
        for _ in range(460):
            x,y=rng.randrange(WORLD_W),rng.randrange(WORLD_H)
            pygame.draw.circle(tint,(238,250,193,20),(x,y),rng.randrange(2,8))
        self.grass.blit(tint,(0,0))

    def make_grid_guide(self):
        self.guide=pygame.Surface((WORLD_W,WORLD_H),pygame.SRCALPHA)
        for x in range(0,WORLD_W+1,CELL):
            pygame.draw.line(self.guide,(255,255,238,24),(x,0),(x,WORLD_H))
        for y in range(0,WORLD_H+1,CELL):
            pygame.draw.line(self.guide,(255,255,238,24),(0,y),(WORLD_W,y))

    def pos(self,tile):
        return ((tile[0]+.5)*CELL,(tile[1]+.5)*CELL)

    def new_world(self):
        self.static_world=None
        self.static_zoom=None
        self.static_zoom_key=None
        self.grid_overlay=None
        self.grid_overlay_key=None
        self.grid=set()
        self.curves=[]
        # Original station is deliberately retained beside the new artworks.
        tiles=[(3,4),(23,4),(4,16),(23,16)]
        self.station_ports=[self.pos(p) for p in tiles]
        names=('station_old','station_blue','station_red','station_green')
        self.stations=[(tiles[i],names[i]) for i in range(4)]

        # Horizontal tunnel artwork represents one hill with two side-facing
        # mouths. The ports are left/right, aligned with the rails in the PNG.
        # No decorative duplicate at either end (old version did that).
        self.tunnel_tiles=[((10,5),(17,5)),((8,15),(15,15))]
        self.tunnels=[(self.pos(a),self.pos(b)) for a,b in self.tunnel_tiles]
        self.bridge_tiles=((17,11),(22,11))
        self.bridge=tuple(map(self.pos,self.bridge_tiles))

        # Structures start connected internally, but outside track construction
        # is always possible. Prebuilt stubs face OUTWARD from the hill/water.
        self.pinned=set(tiles)
        self.no_build=set()
        for left,right in self.tunnel_tiles:
            self.pinned.add(left)
            self.pinned.add(right)
            for x in range(left[0]+1,right[0]):
                self.no_build.add((x,left[1]))
            for t in ((left[0]-1,left[1]),(right[0]+1,right[1])):
                self.pinned.add(t)
        a,b=self.bridge_tiles
        self.pinned.update((a,b,(a[0]-1,a[1]),(b[0]+1,b[1])))
        for x in range(a[0]+1,b[0]):
            self.no_build.add((x,a[1]))
        for x,y in tiles:
            self.pinned.add((x,y+1))
        self.grid.update(self.pinned)

        self.scenery=[]
        protected=[self.pos(t) for t in self.pinned]
        protected.extend(self.pos(t) for t in self.no_build)
        pond_center=((self.bridge[0][0]+self.bridge[1][0])/2,
                     self.bridge[0][1]+47)
        self.scenery.append(('pond',pond_center))
        for a,b in self.tunnels:
            for x in range(round(a[0]-30),round(b[0]+31),40):
                protected.append((x,a[1]-45))
        # A few obvious colorful items within the FIRST viewport make the
        # playground feel alive before a child pans around the larger world.
        starter=[('tree_broadleaf',(8*CELL,8*CELL)),
                 ('tree_pine',(6*CELL,11*CELL)),
                 ('flower_bush',(9*CELL,11*CELL)),
                 ('rock_cluster',(6*CELL,14*CELL)),
                 ('flower_bush',(9*CELL,3*CELL)),
                 ('flower_patch',(11*CELL,12*CELL))]
        self.scenery.extend(starter)
        sizes={'tree_broadleaf':69,'tree_pine':62,'rock_cluster':58,
               'flower_bush':31,'flower_patch':22,
               'grass_tuft':20}
        weights=('tree_broadleaf','tree_pine','rock_cluster','flower_bush',
                 'flower_bush','flower_patch',
                 'grass_tuft')
        for _ in range(450):
            name=self.rng.choice(weights)
            p=(self.rng.randint(35,WORLD_W-35),self.rng.randint(42,WORLD_H-35))
            if any(dst(p,q)<sizes[name]+10 for q in protected):
                continue
            if any(dst(p,q)<(sizes[name]+sizes.get(n,40))*.54 for n,q in self.scenery):
                continue
            if any(a[0]-50<p[0]<b[0]+50 and a[1]-110<p[1]<a[1]+50
                   for a,b in self.tunnels):
                continue
            if abs(p[1]-self.bridge[0][1])<90 and self.bridge[0][0]-55<p[0]<self.bridge[1][0]+55:
                continue
            self.scenery.append((name,p))
            if len(self.scenery)>=100:
                break

        self.net=RailNetwork()
        self.net.rebuild(self.grid,self.curves,self.station_ports,self.tunnels,self.bridge)
        self.train=ToyTrain(self.net,self.station_ports,self.rng)
        self.train.active=False  # A child must first draw or place some tracks.
        self.locomotive_name=self.rng.choice(('locomotive_red','locomotive_blue'))
        self.train.wagons=self.rng.sample(
            ('wagon_passenger_red','wagon_passenger_blue','wagon_freight_green',
             'wagon_logs','wagon_tanker_gold','wagon_coal_gray'),3)
        self.active_rail=None
        self.refresh_track_layer()
        self.camera[0]=65.0
        self.camera[1]=70.0
        self.clamp_cam()

    def minimum_zoom(self):
        # At minimum zoom the world fills the viewport without stretching or
        # exposing empty terrain beyond the map edges.
        return min(1., max(0.48, self.viewport.width/WORLD_W,
                           self.viewport.height/WORLD_H))


    def clamp_cam(self):
        lower=self.minimum_zoom()
        self.zoom=max(lower,min(ZOOM_MAX,self.zoom))
        self.zoom_goal=max(lower,min(ZOOM_MAX,self.zoom_goal))
        self.camera[0]=max(0.,min(float(max(0,WORLD_W-self.viewport.width/self.zoom)),self.camera[0]))
        self.camera[1]=max(0.,min(float(max(0,WORLD_H-self.viewport.height/self.zoom)),self.camera[1]))

    def from_screen(self,p):
        return (p[0]/self.zoom+self.camera[0],
                (p[1]-TOPBAR)/self.zoom+self.camera[1])

    def to_screen(self,p):
        """World coordinates on the native-resolution static-world canvas."""
        return (p[0]-self.camera[0],p[1]-self.camera[1])

    def view_point(self,p):
        """World coordinates on the final DISPLAY, including zoom and toolbar."""
        return (self.viewport.left+(p[0]-self.camera[0])*self.zoom,
                self.viewport.top+(p[1]-self.camera[1])*self.zoom)

    def zoom_at(self,factor,screen_center):
        """Anchor pinch zoom to touch position, but only rescale per 5% step.

        Accumulate fractional changes in zoom_goal so slow pinches still zoom.
        """
        if factor<=0 or not math.isfinite(factor):
            return
        old_point=self.from_screen(screen_center)
        lower=self.minimum_zoom()
        self.zoom_goal=max(lower,min(ZOOM_MAX,self.zoom_goal*factor))
        quantized=round(self.zoom_goal/ZOOM_STEP)*ZOOM_STEP
        new_zoom=max(lower,min(ZOOM_MAX,round(quantized,4)))
        if abs(new_zoom-self.zoom)<1e-5:
            return
        self.zoom=new_zoom
        self.camera[0]=old_point[0]-(screen_center[0]-self.viewport.left)/self.zoom
        self.camera[1]=old_point[1]-(screen_center[1]-self.viewport.top)/self.zoom
        self.clamp_cam()
        self.grid_overlay_key=None

    def inside(self,p):
        return 0<=p[0]<WORLD_W and 0<=p[1]<WORLD_H

    def tile_at(self,p):
        x,y=int(p[0]//CELL),int(p[1]//CELL)
        if 0<=x<COLS and 0<=y<ROWS:
            return (x,y)
        return None

    def protected_tile(self,tile):
        return tile in self.pinned

    def add_tile(self,tile):
        if tile is not None and tile not in self.grid and tile not in self.no_build:
            self.grid.add(tile)
            self.last_change_point=self.pos(tile)
            self.active_rail=True

    def erase_at(self,p):
        c=self.tile_at(p)
        if c in self.grid and not self.protected_tile(c):
            self.grid.remove(c)
            self.last_change_point=p
            self.active_rail=True
            return
        closest=None
        for i,curve in enumerate(self.curves):
            for a,b in zip(curve,curve[1:]):
                d,_,_=point_to_segment(p,a,b)
                if closest is None or d<closest[0]:
                    closest=(d,i)
        if closest is not None and closest[0]<=21:
            self.curves.pop(closest[1])
            self.last_change_point=p
            self.active_rail=True

    def add_curve(self,raw):
        if len(raw)<2 or sum(dst(a,b) for a,b in zip(raw,raw[1:]))<CELL*.55:
            return
        start=self.net.nearest(raw[0])
        end=self.net.nearest(raw[-1])
        # Stations and tunnel/bridge ports are explicitly included as snap points.
        for port in self.station_ports+[p for ab in self.tunnels for p in ab]+list(self.bridge):
            if dst(raw[0],port)<SNAP_RADIUS and dst(raw[0],port)<=dst(start,raw[0]):
                start=port
            if dst(raw[-1],port)<SNAP_RADIUS and dst(raw[-1],port)<=dst(end,raw[-1]):
                end=port
        raw[0],raw[-1]=start,end
        if dst(start,end)<6 and sum(dst(a,b) for a,b in zip(raw,raw[1:]))<CELL*2:
            return
        curve=smooth_stroke(raw,spacing=7)
        if len(curve)>=2:
            self.curves.append(curve)
            self.last_change_point=curve[-1]
            self.active_rail=True

    def commit(self):
        if self.active_rail:
            new_net=RailNetwork()
            new_net.rebuild(self.grid,self.curves,self.station_ports,self.tunnels,self.bridge)
            self.net=new_net
            if (self.train.active and not self.train.stopped
                    and len(self.train.nodes) >= 2):
                # Don't respawn the locomotive on every child tap! It finishes
                # its present ride; the revised network is used at the next stop.
                self.train.queue_network(self.net)
            else:
                self.train=ToyTrain(self.net,self.station_ports,self.rng,
                                    focus=self.last_change_point)
                self.train.active=True
                self.train.wagons=self.rng.sample(
                    ('wagon_passenger_red','wagon_passenger_blue','wagon_freight_green',
                     'wagon_logs','wagon_tanker_gold','wagon_coal_gray'),3)
            self.refresh_track_layer()
        self.active_rail=None

    def press(self,p):
        for name,rect in self.buttons.items():
            if rect.collidepoint(p):
                if name=='home':
                    return 'home'
                if name in ('grid','free','erase','move'):
                    self.mode=name
                    self.guide_until=pygame.time.get_ticks()+GUIDE_TIME_MS
                elif name=='follow':
                    self.follow_train=not self.follow_train
                elif name=='zoom_in':
                    self.zoom_at(1.25,(self.sw/2,self.viewport.centery))
                elif name=='zoom_out':
                    self.zoom_at(1/1.25,(self.sw/2,self.viewport.centery))
                elif name=='new':
                    now=pygame.time.get_ticks()
                    if getattr(self,'confirm_until',0)>now:
                        self.new_world()
                        self.confirm_until=0
                    else:
                        self.confirm_until=now+2600
                return None
        if not self.viewport.collidepoint(p):
            return None
        self.dragging=True
        self.pointer_last=p
        world=self.from_screen(p)
        if self.mode=='grid':
            self.last_tile=self.tile_at(world)
            self.add_tile(self.last_tile)
        elif self.mode=='free':
            self.stroke=[world]
        elif self.mode=='erase':
            self.erase_at(world)
        return None

    def motion(self,p):
        if not self.dragging:
            return
        if self.mode=='move':
            if self.pointer_last is not None:
                self.pan(p[0]-self.pointer_last[0],p[1]-self.pointer_last[1])
            self.pointer_last=p
            return
        if not self.viewport.collidepoint(p):
            return
        world=self.from_screen(p)
        if self.mode=='grid':
            new=self.tile_at(world)
            if new is not None and self.last_tile is not None and new!=self.last_tile:
                # Manhattan fill keeps long, fast finger drags continuous.
                x,y=self.last_tile
                x1,y1=new
                while x!=x1:
                    x+=1 if x1>x else -1
                    self.add_tile((x,y))
                while y!=y1:
                    y+=1 if y1>y else -1
                    self.add_tile((x,y))
            self.last_tile=new
        elif self.mode=='free':
            if self.stroke and dst(self.stroke[-1],world)>5:
                self.stroke.append(world)
        elif self.mode=='erase':
            self.erase_at(world)
        self.pointer_last=p
        self.guide_until=pygame.time.get_ticks()+GUIDE_TIME_MS

    def cancel_gesture(self):
        """Two-finger pan cancels a partly drawn curve instead of saving it."""
        if self.dragging:
            self.stroke=[]
            self.dragging=False
            self.last_tile=None
            self.pointer_last=None
            self.commit()

    def release(self,p=None):
        if not self.dragging:
            return
        if self.mode=='free' and self.stroke:
            if p is not None and self.viewport.collidepoint(p):
                q=self.from_screen(p)
                if dst(q,self.stroke[-1])>2:
                    self.stroke.append(q)
            self.add_curve(self.stroke)
        self.stroke=[]
        self.dragging=False
        self.last_tile=None
        self.pointer_last=None
        self.commit()

    def pan(self,dx,dy):
        self.follow_train=False
        self.camera[0]-=dx/self.zoom
        self.camera[1]-=dy/self.zoom
        self.clamp_cam()

    def resize(self,screen):
        self.screen=screen
        self.sw,self.sh=screen.get_size()
        self.viewport=pygame.Rect(0,TOPBAR,self.sw,max(1,self.sh-TOPBAR))
        self.grid_overlay=None
        self.grid_overlay_key=None
        self.clamp_cam()

    def static_image(self,name,p,base_angle=0):
        img=self.assets.get(name)
        if img is None:
            if name in ('station_old','station_blue','station_red','station_green'):
                rect=pygame.Rect(0,0,140,76)
                rect.midbottom=(int(self.to_screen(p)[0]),int(self.to_screen(p)[1]))
                pygame.draw.rect(self.draw_surface,(215,115,83),rect,border_radius=8)
            return
        if base_angle:
            cache_key=(name,base_angle)
            if cache_key not in self.rotate_cache:
                self.rotate_cache[cache_key]=pygame.transform.rotate(img,base_angle)
            img=self.rotate_cache[cache_key]
        sx,sy=self.to_screen(p)
        meta=self.sprite_manifest.get(name,{})
        anchor=meta.get('anchor',{}).get('norm',
            [.5,1.] if name.startswith('station') or name.startswith('tree') else [.5,.5])
        # station platform artwork sits a few pixels above the prebuilt stub.
        if name.startswith('station'):
            sy-=7
        r=pygame.Rect(round(sx-img.get_width()*anchor[0]),
                      round(sy-img.get_height()*anchor[1]),
                      img.get_width(),img.get_height())
        if r.colliderect(self.draw_surface.get_rect()):
            self.draw_surface.blit(img,r)

    def make_train_fallback(self,name):
        """Friendly procedural backup: never show cryptic red circles."""
        engine=name.startswith('locomotive')
        width,height=(83,49) if engine else (67,42)
        img=pygame.Surface((width,height),pygame.SRCALPHA)
        color=(223,65,64) if engine or 'red' in name else (
            (63,148,237) if 'blue' in name else
            (62,184,105) if 'green' in name else (235,187,53))
        pygame.draw.rect(img,(56,56,66),(3,height-14,width-6,7),border_radius=3)
        pygame.draw.rect(img,color,(5,12,width-10,height-26),border_radius=6)
        pygame.draw.rect(img,(251,201,64),(5,height-17,width-10,4))
        if engine:
            pygame.draw.rect(img,(69,92,126),(9,4,24,16),border_radius=3)
            pygame.draw.rect(img,(119,224,239),(16,8,11,10))
            pygame.draw.rect(img,(75,77,88),(53,2,12,19),border_radius=3)
            pygame.draw.circle(img,(245,223,94),(width-8,height//2),5)
        else:
            for x in (16,35):
                pygame.draw.rect(img,(133,221,242),(x,17,13,10),border_radius=2)
        for x in ((17,48,69) if engine else (19,49)):
            pygame.draw.circle(img,(51,57,76),(x,height-9),7)
            pygame.draw.circle(img,(246,191,53),(x,height-9),3)
        return img

    def train_sprite(self,name,p,angle):
        """Draw the moving sprite on-screen at zoom, NOT on the static map.

        Sprite rotations/scaling are cached per discrete angle and zoom level.
        Side-on artwork is never turned upside down.
        """
        image=self.assets.get(name)
        if image is None:
            if name not in self.fallback_trains:
                self.fallback_trains[name]=self.make_train_fallback(name)
            image=self.fallback_trains[name]
        rad=math.radians(angle)
        dx=math.cos(rad)
        dy=-math.sin(rad)
        face_left=dx<-0.035
        tilt=math.degrees(math.atan2(dy,max(0.2,abs(dx))))
        tilt=max(-36.,min(36.,tilt))
        spin=tilt if face_left else -tilt
        quant=int(round(spin/3.0))*3
        cache_key=(name,quant,face_left,round(self.zoom*1000))
        sprite=self.rotate_cache.get(cache_key)
        if sprite is None:
            oriented=pygame.transform.flip(image,True,False) if face_left else image
            sprite=pygame.transform.rotate(oriented,quant)
            if abs(self.zoom-1.0)>0.001:
                dimensions=(max(1,round(sprite.get_width()*self.zoom)),
                            max(1,round(sprite.get_height()*self.zoom)))
                sprite=pygame.transform.smoothscale(sprite,dimensions)
            # At most a handful of zoom levels should be retained on mobile.
            self.rotate_cache[cache_key]=sprite
        xy=self.view_point(p)
        r=sprite.get_rect(center=(round(xy[0]),round(xy[1])))
        if r.colliderect(self.viewport):
            self.screen.blit(sprite,r)

    def draw_track(self,points,surface):
        """Fallback for a structure whose image was not installed."""
        if len(points)<2:
            return
        a,b=points[0],points[-1]
        if dst(a,b)<2:
            return
        pygame.draw.line(surface,(128,87,54),a,b,44)
        pygame.draw.line(surface,(218,197,147),a,b,36)
        for sign in (-1,1):
            nx,ny=-(b[1]-a[1])/dst(a,b),(b[0]-a[0])/dst(a,b)
            shift=(nx*sign*RAIL_HALF_GAUGE,ny*sign*RAIL_HALF_GAUGE)
            pygame.draw.line(surface,(52,65,70),(a[0]+shift[0],a[1]+shift[1]),
                             (b[0]+shift[0],b[1]+shift[1]),6)

    def refresh_track_layer(self):
        # Geometry changes invalidate both static caches, never per-frame camera motion.
        self.static_world=None
        self.static_zoom=None
        self.static_zoom_key=None
        self.track_layer=pygame.Surface((WORLD_W,WORLD_H),pygame.SRCALPHA)
        paint_rail_network(self.track_layer,self.net)
        self.visible_scenery=[]
        for name,p in self.scenery:
            if name=='pond':
                continue
            if self.near_track(p,45):
                continue
            self.visible_scenery.append((name,p))

    def near_track(self,p,limit=35):
        for a,b,kind,*_ in self.net.edges:
            if kind=='tunnel':
                continue
            dd,_,_=point_to_segment(p,a,b)
            if dd<limit:
                return True
        return False

    def rebuild_static_world(self):
        """Build everything immobile once, including rail geometry and art.

        All static artwork uses its original world-space anchor. We temporarily
        set the camera to zero while composing the whole native-size surface.
        """
        self.static_world=self.grass.copy()
        previous_camera=self.camera[:]
        previous_draw_surface=self.draw_surface
        self.camera=[0.,0.]
        self.draw_surface=self.static_world
        try:
            for name,p in self.scenery:
                if name=='pond':
                    self.static_image(name,p)
            self.static_world.blit(self.track_layer,(0,0))
            self.draw_structure('bridge_horizontal',*self.bridge)
            for name,p in self.visible_scenery:
                self.static_image(name,p)
            for tile,name in self.stations:
                self.static_image(name,self.pos(tile))
            for a,b in self.tunnels:
                self.draw_structure('tunnel_horizontal',a,b)
        finally:
            self.camera=previous_camera
            self.draw_surface=previous_draw_surface
        self.static_zoom=None
        self.static_zoom_key=None

    def ensure_scaled_static(self):
        """Rescale a static image ONLY when level changes, never per frame."""
        if self.static_world is None:
            self.rebuild_static_world()
        zoom_key=round(self.zoom,4)
        if self.static_zoom_key!=zoom_key or self.static_zoom is None:
            if abs(self.zoom-1.)<0.0001:
                self.static_zoom=self.static_world
            else:
                target=(max(1,round(WORLD_W*self.zoom)),
                        max(1,round(WORLD_H*self.zoom)))
                self.static_zoom=pygame.transform.smoothscale(self.static_world,target)
            self.static_zoom_key=zoom_key
            # No persistent multizoom surfaces: memory usage stays bounded.
            # Rotated train sprites are small; remove old zoom entries as well.
            self.rotate_cache={k:v for k,v in self.rotate_cache.items()
                               if len(k)!=4 or k[-1]==round(self.zoom*1000)}

    def draw_grid_overlay(self):
        """Subtle alpha guide; cached per camera pixel/zoom, not scaled per frame."""
        if self.mode!='grid' or pygame.time.get_ticks()>=self.guide_until:
            return
        scale=self.zoom
        # Pixel alignment makes panning smooth and prevents redraw on subpixel
        # camera changes that have no visible effect.
        ox=round(-self.camera[0]*scale)
        oy=round(-self.camera[1]*scale)
        tag=(ox,oy,round(scale,4),self.viewport.size)
        if self.grid_overlay_key!=tag or self.grid_overlay is None:
            w,h=self.viewport.size
            overlay=pygame.Surface((w,h),pygame.SRCALPHA)
            shade=(255,255,238,30)
            for n in range(COLS+1):
                x=round(n*CELL*scale+ox)
                if 0<=x<w:
                    pygame.draw.line(overlay,shade,(x,0),(x,h))
            for n in range(ROWS+1):
                y=round(n*CELL*scale+oy)
                if 0<=y<h:
                    pygame.draw.line(overlay,shade,(0,y),(w,y))
            self.grid_overlay=overlay
            self.grid_overlay_key=tag
        self.screen.blit(self.grid_overlay,self.viewport.topleft)

    def draw_world(self):
        """One source-rectangle blit per frame, not software smoothscale.

        The camera can follow moving trains at 60 FPS without resampling a
        million-pixel world. Only zoom changes or track edits rebuild caches.
        """
        self.ensure_scaled_static()
        self.screen.fill(GRASS_FALLBACK,self.viewport)
        source=pygame.Rect(round(self.camera[0]*self.zoom),
                           round(self.camera[1]*self.zoom),
                           self.viewport.width,self.viewport.height)
        source=source.clip(self.static_zoom.get_rect())
        if source.width and source.height:
            self.screen.blit(self.static_zoom,self.viewport.topleft,source)
        previous_clip=self.screen.get_clip()
        self.screen.set_clip(self.viewport)
        try:
            self.draw_grid_overlay()
            if len(self.stroke)>1:
                pygame.draw.lines(self.screen,(255,231,99),False,
                    [self.view_point(q) for q in self.stroke],
                    max(2,round(7*self.zoom)))
            if self.train.active and len(self.train.nodes)>=2:
                for offset,name in reversed(list(enumerate(self.train.wagons,start=1))):
                    sampled=self.train.wagon_sample(offset*58)
                    if sampled:
                        p,angle,kind=sampled
                        if kind!='tunnel':
                            self.train_sprite(name,p,angle)
                sampled=self.train.sample(self.train.travel)
                if sampled:
                    p,angle,kind=sampled
                    if kind!='tunnel':
                        self.train_sprite(self.locomotive_name,p,angle)
        finally:
            self.screen.set_clip(previous_clip)

    def draw_button_icon(self,name,x,y,color):
        """Large pictograms make the tools readable before children can read."""
        draw=pygame.draw
        if name=='home':
            draw.polygon(self.screen,color,[(x-11,y-2),(x,y-12),(x+11,y-2)])
            draw.rect(self.screen,color,(x-8,y-2,16,12),border_radius=2)
            draw.rect(self.screen,(41,91,72),(x-3,y+3,6,7))
        elif name=='grid':
            for i in (-7,0,7):
                draw.line(self.screen,color,(x+i,y-12),(x+i,y+12),2)
            draw.line(self.screen,color,(x-13,y-6),(x+13,y-6),4)
            draw.line(self.screen,color,(x-13,y+6),(x+13,y+6),4)
        elif name=='free':
            points=[(x-12,y+6),(x-6,y-3),(x,y+3),(x+7,y-7),(x+12,y-4)]
            draw.lines(self.screen,color,False,points,4)
            draw.circle(self.screen,color,(x+12,y-4),3)
        elif name=='erase':
            draw.polygon(self.screen,color,[(x-9,y+3),(x+2,y-10),
                                            (x+12,y-2),(x+1,y+11)])
            draw.line(self.screen,(41,91,72),(x-2,y-4),(x+9,y+5),2)
        elif name=='move':
            draw.line(self.screen,color,(x-11,y),(x+11,y),3)
            draw.line(self.screen,color,(x,y-11),(x,y+11),3)
            for p in (((x-13,y),(x-6,y-5),(x-6,y+5)),
                      ((x+13,y),(x+6,y-5),(x+6,y+5)),
                      ((x,y-13),(x-5,y-6),(x+5,y-6)),
                      ((x,y+13),(x-5,y+6),(x+5,y+6))):
                draw.polygon(self.screen,color,p)
        elif name=='follow':
            draw.rect(self.screen,color,(x-12,y-6,19,12),border_radius=3)
            draw.rect(self.screen,color,(x+2,y-10,10,10),border_radius=2)
            for cx in (x-7,x+7):
                draw.circle(self.screen,color,(cx,y+8),4)
        elif name=='new':
            draw.arc(self.screen,color,(x-10,y-10,20,20),.3,5.3,4)
            draw.polygon(self.screen,color,[(x+11,y+2),(x+12,y-9),(x+2,y-3)])

    def draw_ui(self):
        s=self.screen
        pygame.draw.rect(s,(41,91,72),(0,0,self.sw,TOPBAR))
        labels=(('home','HOME'),('grid','TILES'),('free','DRAW'),
                ('erase','ERASE'),('move','MOVE'),('follow','TRAIN'),('new','NEW'))
        gap=8
        width=max(44,min(122,(self.sw-gap*(len(labels)+1))//len(labels)))
        x=max(4,(self.sw-(len(labels)*width+(len(labels)-1)*gap))//2)
        colors={'home':(230,129,60),'grid':(56,160,223),'free':(89,168,126),
                'erase':(239,159,80),'move':(137,127,208),'follow':(77,145,129),
                'new':(213,94,90)}
        self.buttons={}
        for name,text in labels:
            r=pygame.Rect(x,9,width,49)
            self.buttons[name]=r
            selected=(self.follow_train if name=='follow' else name==self.mode)
            pygame.draw.rect(s,(255,245,196) if selected else colors[name],r,border_radius=13)
            pygame.draw.rect(s,(255,255,255),r,2,border_radius=13)
            color=DARK if selected else (255,255,255)
            icon_x=r.x+21 if width>=78 else r.centerx
            self.draw_button_icon(name,icon_x,r.centery,color)
            if width>=78:
                rendered=self.font.render(text,True,color)
                s.blit(rendered,rendered.get_rect(center=(r.centerx+14,r.centery)))
            x+=width+gap
        # Optional minimap: clear indication that this world is much larger.
        mw,mh=121,90
        rect=pygame.Rect(self.sw-mw-8,self.sh-mh-9,mw,mh)
        pygame.draw.rect(s,(243,238,197),rect,border_radius=7)
        pygame.draw.rect(s,(54,101,72),rect,2,border_radius=7)
        for p in self.station_ports:
            x=rect.left+p[0]/WORLD_W*rect.width
            y=rect.top+p[1]/WORLD_H*rect.height
            pygame.draw.circle(s,(219,89,80),(int(x),int(y)),4)
        area=pygame.Rect(rect.left+self.camera[0]/WORLD_W*mw,
                         rect.top+self.camera[1]/WORLD_H*mh,
                         self.viewport.width/self.zoom/WORLD_W*mw,
                         self.viewport.height/self.zoom/WORLD_H*mh)
        pygame.draw.rect(s,(65,116,218),area,2,border_radius=3)
        # Accessible large +/- buttons, also usable with mouse wheel and pinch.
        for key,sign,index in (('zoom_out','-',0),('zoom_in','+',1)):
            zr=pygame.Rect(rect.left+index*64,rect.top-53,57,44)
            self.buttons[key]=zr
            pygame.draw.rect(s,(53,130,167),zr,border_radius=10)
            pygame.draw.rect(s,(255,255,255),zr,2,border_radius=10)
            txt=self.titlefont.render(sign,True,(255,255,255))
            s.blit(txt,txt.get_rect(center=zr.center))
        scale_text=self.font.render(str(round(self.zoom*100))+'%',True,DARK)
        # Mini-map shows the visible area, taking the zoom factor into account.
        s.blit(scale_text,scale_text.get_rect(midbottom=(rect.centerx,rect.top+20)))
        if self.missing_assets:
            # Children still get a playable procedural fallback, but parents
            # can identify the missing-asset deployment without opening logs.
            label=self.font.render('Missing art: upload assets/wasteTrain folders',True,(255,255,255))
            x=10; y=self.sh-30
            pygame.draw.rect(s,(154,51,45),(x-5,y-3,label.get_width()+10,26),border_radius=5)
            s.blit(label,(x,y))
        now=pygame.time.get_ticks()
        if getattr(self,'confirm_until',0)>now:
            text=self.font.render('Tap NEW again to start a new world', True, CREAM)
            bg=text.get_rect(midbottom=(self.sw//2,self.sh-16)).inflate(20,12)
            pygame.draw.rect(s,DARK,bg,border_radius=9)
            s.blit(text,text.get_rect(center=bg.center))
        pygame.display.flip()

    def update(self,dt):
        self.train.update(dt)
        if self.follow_train and self.train.active and len(self.train.nodes)>=2:
            sampled=self.train.sample(self.train.travel)
            if sampled is not None:
                position=sampled[0]
                target_x=position[0]-self.viewport.width/(2*self.zoom)
                target_y=position[1]-self.viewport.height/(2*self.zoom)
                smooth=min(1.0,5.0*dt)
                self.camera[0]+=(target_x-self.camera[0])*smooth
                self.camera[1]+=(target_y-self.camera[1])*smooth
                self.clamp_cam()

    def draw(self):
        self.draw_world()
        self.draw_ui()


def finger_position(ev,world):
    return (float(ev.x)*world.sw,float(ev.y)*world.sh)


async def main(screen,clock):
    """GameHub compatible entry point; works with pygame-ce / Pygbag."""
    world=WasteTrainWorld(screen)
    active=True
    touches={}
    drawing_finger=None
    last_centroid=None
    last_pinch_distance=None
    suppress_mouse_until=0
    mouse_drag=False
    while active:
        dt=min(clock.tick(FPS)/1000.,.05)
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                active=False
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:
                    active=False
                elif event.key in (pygame.K_PLUS,pygame.K_EQUALS,pygame.K_KP_PLUS):
                    world.zoom_at(1.2,(world.sw/2,world.viewport.centery))
                elif event.key in (pygame.K_MINUS,pygame.K_KP_MINUS):
                    world.zoom_at(1/1.2,(world.sw/2,world.viewport.centery))
                elif event.key in (pygame.K_LEFT,pygame.K_RIGHT,pygame.K_UP,pygame.K_DOWN):
                    arrows={pygame.K_LEFT:(45,0),pygame.K_RIGHT:(-45,0),
                            pygame.K_UP:(0,45),pygame.K_DOWN:(0,-45)}
                    world.pan(*arrows[event.key])
            elif event.type==pygame.FINGERDOWN:
                pos=finger_position(event,world)
                touches[event.finger_id]=pos
                suppress_mouse_until=pygame.time.get_ticks()+400
                if len(touches)==1:
                    drawing_finger=event.finger_id
                    if world.press(pos)=='home':
                        active=False
                else:
                    # A second finger turns the gesture into camera panning.
                    world.cancel_gesture()
                    drawing_finger=None
                    last_centroid=(sum(p[0] for p in touches.values())/len(touches),
                                   sum(p[1] for p in touches.values())/len(touches))
                    pair=list(touches.values())[:2]
                    last_pinch_distance=dst(pair[0],pair[1])
            elif event.type==pygame.FINGERMOTION and event.finger_id in touches:
                p=finger_position(event,world)
                touches[event.finger_id]=p
                suppress_mouse_until=pygame.time.get_ticks()+400
                if len(touches)>=2:
                    center=(sum(q[0] for q in touches.values())/len(touches),
                            sum(q[1] for q in touches.values())/len(touches))
                    pair=list(touches.values())[:2]
                    pinch_distance=dst(pair[0],pair[1])
                    if last_pinch_distance and pinch_distance>25:
                        world.zoom_at(pinch_distance/last_pinch_distance,center)
                    last_pinch_distance=pinch_distance
                    if last_centroid is not None:
                        world.pan(center[0]-last_centroid[0],center[1]-last_centroid[1])
                    last_centroid=center
                elif event.finger_id==drawing_finger:
                    world.motion(p)
            elif event.type==pygame.FINGERUP:
                p=finger_position(event,world)
                if drawing_finger==event.finger_id:
                    world.release(p)
                    drawing_finger=None
                touches.pop(event.finger_id,None)
                suppress_mouse_until=pygame.time.get_ticks()+400
                last_centroid=None
                last_pinch_distance=None
            elif event.type==pygame.MOUSEWHEEL:
                # Wheel-up zooms in, wheel-down out; anchor at cursor.
                try:
                    pointer=pygame.mouse.get_pos()
                except pygame.error:
                    pointer=(world.sw/2,world.viewport.centery)
                world.zoom_at(1.12**event.y,pointer)
            elif event.type==pygame.MOUSEBUTTONDOWN:
                if getattr(event,'touch',False) or touches or pygame.time.get_ticks()<suppress_mouse_until:
                    continue
                if event.button==1:
                    mouse_drag=True
                    if world.press(event.pos)=='home':
                        active=False
                elif event.button in (2,3):
                    mouse_drag=True
                    world.mode_before_pan=world.mode
                    world.mode='move'
                    world.press(event.pos)
            elif event.type==pygame.MOUSEMOTION and mouse_drag and not touches:
                if not getattr(event,'touch',False) and pygame.time.get_ticks()>=suppress_mouse_until:
                    world.motion(event.pos)
            elif event.type==pygame.MOUSEBUTTONUP and mouse_drag:
                if not getattr(event,'touch',False):
                    world.release(event.pos)
                    mouse_drag=False
                    if hasattr(world,'mode_before_pan'):
                        world.mode=world.mode_before_pan
                        delattr(world,'mode_before_pan')
            elif event.type==pygame.VIDEORESIZE:
                world.resize(pygame.display.get_surface() or screen)
        world.update(dt)
        world.draw()
        await asyncio.sleep(0)
