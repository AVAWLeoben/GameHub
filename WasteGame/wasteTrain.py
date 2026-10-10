"""WasteTrain: classic grid + freehand spline railway sandbox.

Replace WasteGame/wasteTrain.py with this file. Uses the original station,
train and wagon artwork. Entry point: await main(screen, clock).
"""
import asyncio
import heapq
import math
import random
import pygame

FPS = 60
GRID_COLS, GRID_ROWS = 24, 18
BG = (112, 168, 106)
RAIL = (91, 92, 92)
WOOD = (114, 80, 53)
TEXT = (245, 246, 230)


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def interpolate(points, spacing=7):
    """Centripetal-ish Catmull-Rom interpolation, then uniform arc samples."""
    if len(points) < 2:
        return points[:]
    out = [points[0]]
    for i in range(len(points)-1):
        p0 = points[max(0, i-1)]
        p1 = points[i]
        p2 = points[i+1]
        p3 = points[min(len(points)-1, i+2)]
        steps = max(2, int(distance(p1, p2)/4))
        for j in range(1, steps+1):
            t = j/steps
            t2, t3 = t*t, t*t*t
            x = .5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = .5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            out.append((x, y))
    # Resample the smoothed polyline at approximately constant distance.
    samples = [out[0]]
    remaining = spacing
    previous = out[0]
    for end in out[1:]:
        segment = distance(previous, end)
        while segment >= remaining and segment > 1e-6:
            t = remaining / segment
            node = (previous[0]+(end[0]-previous[0])*t,
                    previous[1]+(end[1]-previous[1])*t)
            samples.append(node)
            previous = node
            segment = distance(previous, end)
            remaining = spacing
        remaining -= segment
        previous = end
    if distance(samples[-1], out[-1]) > 0.5:
        samples.append(out[-1])
    return samples


def shortest_path(graph, start, goal):
    queue = [(0, start)]
    dist = {start: 0}
    previous = {}
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > dist[node]:
            continue
        if node == goal:
            path = [node]
            while node in previous:
                node = previous[node]
                path.append(node)
            return path[::-1]
        for neighbor, weight in graph.get(node, {}).items():
            new = cost+weight
            if new < dist.get(neighbor, float('inf')):
                dist[neighbor] = new
                previous[neighbor] = node
                heapq.heappush(queue, (new, neighbor))
    return []


class World:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.toolbar = 126
        self.cell = max(16, min((self.w-self.toolbar-20)//GRID_COLS, (self.h-60)//GRID_ROWS))
        self.map_w = GRID_COLS*self.cell
        self.map_h = GRID_ROWS*self.cell
        self.ox = 8
        self.oy = max(38, (self.h-self.map_h)//2)
        self.font = pygame.font.Font(None, 22)
        self.title_font = pygame.font.Font(None, 29)
        self.mode = 'grid'
        self.dragging = False
        self.last_cell = None
        self.drawing = []
        self.tracks = set()
        self.curves = []
        self.stations = [(3, 3), (GRID_COLS-4, 3), (4, GRID_ROWS-4), (GRID_COLS-5, GRID_ROWS-5)]
        self.station_points = [self.center(cell) for cell in self.stations]
        self.tracks.update(self.stations)
        self.graph = {}
        self.positions = {}
        self.train_path = []
        self.train_progress = 0.0
        self.train_speed = max(32, self.cell*2.0)
        self.train_angle = 0
        self.train_pos = None
        self.buttons = {}
        self.assets = self.load_assets()
        self.build_graph()
        self.set_route()

    def load_assets(self):
        def load(path, size):
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.smoothscale(img, size)
            except (pygame.error, FileNotFoundError):
                return None
        return {
            'station': load('assets/wasteTrain/station.png', (self.cell*3, self.cell*2)),
            'train': load('assets/wasteTrain/train.png', (self.cell, self.cell)),
            'wagon': load('assets/wasteTrain/wagon.png', (self.cell, self.cell)),
            'grass': load('assets/hungryHedgie/grass.png', (self.w, self.h)),
        }

    def center(self, cell):
        return (self.ox+(cell[0]+.5)*self.cell, self.oy+(cell[1]+.5)*self.cell)

    def cell_at(self, pos):
        x = int((pos[0]-self.ox)//self.cell)
        y = int((pos[1]-self.oy)//self.cell)
        return (x, y) if 0 <= x < GRID_COLS and 0 <= y < GRID_ROWS else None

    def inside(self, p):
        return self.ox <= p[0] < self.ox+self.map_w and self.oy <= p[1] < self.oy+self.map_h

    def snap(self, p):
        # Snaps to station centers, grid track centers and freeform endpoints.
        targets = self.station_points + [self.center(c) for c in self.tracks]
        for curve in self.curves:
            targets.extend((curve[0], curve[-1]))
        if not targets:
            return p
        near = min(targets, key=lambda q: distance(q, p))
        return near if distance(near, p) <= max(16, self.cell*.7) else p

    def add_grid(self, cell):
        if cell and cell not in self.tracks:
            self.tracks.add(cell)
            self.build_graph()
            self.set_route()

    def remove_at(self, pos):
        cell = self.cell_at(pos)
        if cell in self.tracks and cell not in self.stations:
            self.tracks.remove(cell)
        else:
            best = None
            for i, curve in enumerate(self.curves):
                d = min(distance(pos, p) for p in curve)
                if best is None or d < best[0]:
                    best = (d, i)
            if best and best[0] < self.cell*.45:
                self.curves.pop(best[1])
        self.build_graph()
        self.set_route()

    def finish_curve(self):
        raw = self.drawing
        self.drawing = []
        if len(raw) < 2 or sum(distance(a,b) for a,b in zip(raw,raw[1:])) < self.cell*.6:
            return
        raw[0] = self.snap(raw[0])
        raw[-1] = self.snap(raw[-1])
        points = interpolate(raw, max(4, self.cell/5))
        if len(points) >= 2:
            self.curves.append(points)
            self.build_graph()
            self.set_route()

    def build_graph(self):
        """Combine grid and freeform tracks into one weighted railway graph.

        Nodes are sampled curve points and grid centers. Curve endpoints snap to
        nearby nodes; mid-curve crossings are not automatically junctions.
        """
        graph, positions = {}, {}
        def add(node, pos):
            graph.setdefault(node, {})
            positions[node] = pos
        def link(a, b):
            length = distance(positions[a], positions[b])
            if a != b:
                graph[a][b] = max(.001, length)
                graph[b][a] = max(.001, length)
        for c in self.tracks:
            add(('g', c), self.center(c))
        for x, y in self.tracks:
            for nb in ((x+1,y), (x,y+1)):
                if nb in self.tracks:
                    link(('g',(x,y)), ('g',nb))
        for i, curve in enumerate(self.curves):
            for j, p in enumerate(curve):
                add(('c',i,j), p)
                if j:
                    link(('c',i,j-1), ('c',i,j))
        # Snap connections between freeform endpoints and existing nodes.
        # Explicit endpoint-only connections avoid accidental crossing switches.
        endpoints = [('c',i,j) for i, curve in enumerate(self.curves)
                     for j in (0,len(curve)-1)]
        for node in endpoints:
            pos = positions[node]
            candidates = [(distance(pos, p), other) for other,p in positions.items()
                          if other != node and (other[0] == 'g' or
                          (other[0] == 'c' and other[2] in (0,len(self.curves[other[1]])-1)
                           and other[1] != node[1]))]
            if candidates:
                d, other = min(candidates)
                if d <= max(16, self.cell*.7):
                    link(node, other)
        self.graph, self.positions = graph, positions

    def set_route(self):
        # Pick a connected station pair if available. Never impose a mission.
        possible = []
        for a in range(len(self.stations)):
            for b in range(a+1, len(self.stations)):
                nodes = shortest_path(self.graph, ('g',self.stations[a]), ('g',self.stations[b]))
                if len(nodes) > 1:
                    possible.append(nodes)
        if possible:
            chosen = max(possible, key=len)
            self.train_path = [self.positions[n] for n in chosen]
        else:
            # Trains can also explore freeform rails that aren't station-connected.
            self.train_path = max(self.curves, key=len)[:] if self.curves else []
        self.train_progress = 0.0
        self.train_pos = self.train_path[0] if self.train_path else None

    def update(self, dt):
        if len(self.train_path) < 2:
            return
        # Train travels at fixed world speed, reversing at ends.
        total = sum(distance(a,b) for a,b in zip(self.train_path,self.train_path[1:]))
        if total < 1:
            return
        self.train_progress = (self.train_progress+self.train_speed*dt)%(total*2)
        travelled = min(self.train_progress, 2*total-self.train_progress)
        backwards = self.train_progress > total
        for a,b in zip(self.train_path,self.train_path[1:]):
            seg = distance(a,b)
            if travelled <= seg:
                t = travelled/seg if seg else 0
                self.train_pos = (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
                self.train_angle = math.degrees(math.atan2(b[1]-a[1], b[0]-a[0]))+(180 if backwards else 0)
                break
            travelled -= seg

    def draw_rail(self, points):
        if len(points) < 2:
            return
        s = self.screen
        width = max(3, self.cell//7)
        pygame.draw.lines(s, (169, 150, 112), False, points, width+8)
        # Cross ties perpendicular to the path at regular intervals.
        travelled = 0.0
        for a,b in zip(points,points[1:]):
            seg = distance(a,b)
            if seg < .001:
                continue
            dx,dy = (b[0]-a[0])/seg,(b[1]-a[1])/seg
            start = (self.cell*.30-travelled%(self.cell*.30))%(self.cell*.30)
            k = start
            while k < seg:
                cx,cy = a[0]+dx*k,a[1]+dy*k
                half = width*1.35
                pygame.draw.line(s,WOOD,(cx-dy*half,cy+dx*half),(cx+dy*half,cy-dx*half),max(2,self.cell//10))
                k += self.cell*.30
            travelled += seg
        # Rails on either side of the centerline.
        for sign in (-1,1):
            offset = []
            for i,p in enumerate(points):
                a = points[max(0,i-1)]
                b = points[min(len(points)-1,i+1)]
                seg = max(.001,distance(a,b))
                nx,ny = -(b[1]-a[1])/seg,(b[0]-a[0])/seg
                offset.append((p[0]+nx*sign*width*.68,p[1]+ny*sign*width*.68))
            pygame.draw.lines(s,RAIL,False,offset,max(2,width//2))

    def draw_sprite(self, name, pos, angle):
        sprite = self.assets[name]
        if sprite is None:
            pygame.draw.circle(self.screen,(211,69,60),tuple(map(int,pos)),self.cell//3)
            return
        # Source sprites traditionally face right; angle 0 = right.
        rotated = pygame.transform.rotate(sprite,-angle)
        self.screen.blit(rotated,rotated.get_rect(center=(int(pos[0]),int(pos[1]))))

    def draw(self):
        s = self.screen
        s.fill(BG)
        if self.assets['grass']:
            s.blit(self.assets['grass'],(0,0))
        pygame.draw.rect(s,(118,177,112),(self.ox,self.oy,self.map_w,self.map_h))
        for x in range(GRID_COLS+1):
            xx = self.ox+x*self.cell
            pygame.draw.line(s,(99,151,98),(xx,self.oy),(xx,self.oy+self.map_h),1)
        for y in range(GRID_ROWS+1):
            yy = self.oy+y*self.cell
            pygame.draw.line(s,(99,151,98),(self.ox,yy),(self.ox+self.map_w,yy),1)
        for c in self.tracks:
            x,y = c
            points = [self.center(c)]
            for n in ((x+1,y),(x,y+1)):
                if n in self.tracks:
                    self.draw_rail((self.center(c),self.center(n)))
            pygame.draw.circle(s,WOOD,tuple(map(int,points[0])),max(2,self.cell//8))
        for curve in self.curves:
            self.draw_rail(curve)
        if len(self.drawing)>1:
            pygame.draw.lines(s,(242,221,91),False,self.drawing,max(3,self.cell//7))
        for i,point in enumerate(self.station_points):
            sprite = self.assets['station']
            if sprite:
                s.blit(sprite,sprite.get_rect(midbottom=(int(point[0]),int(point[1]+self.cell*.6))))
            else:
                pygame.draw.rect(s,(216,191,127),pygame.Rect(point[0]-self.cell,point[1]-self.cell,self.cell*2,self.cell))
            pygame.draw.circle(s,(255,229,96),tuple(map(int,point)),max(3,self.cell//7))
        if self.train_pos:
            self.draw_sprite('train',self.train_pos,self.train_angle)
        pygame.draw.rect(s,(43,71,67),(0,0,self.w,34))
        s.blit(self.title_font.render('WasteTrain  •  Build anything!',True,TEXT),(9,6))
        px = self.ox+self.map_w+7
        self.buttons = {}
        labels = [('grid','GRID'),('free','DRAW'),('erase','ERASE'),('clear','CLEAR'),('home','HOME')]
        for i,(key,label) in enumerate(labels):
            r = pygame.Rect(px, self.oy+i*53, max(65,self.w-px-7),45)
            self.buttons[key] = r
            color = (69,136,102) if key == self.mode else (55,87,77)
            pygame.draw.rect(s,color,r,border_radius=8)
            text = self.font.render(label,True,TEXT)
            s.blit(text,text.get_rect(center=r.center))
        tip = 'Tap / drag' if self.mode=='grid' else 'Draw curves' if self.mode=='free' else 'Tap to erase'
        for i,line in enumerate((tip,'No goals!','Just play.')):
            text = self.font.render(line,True,(25,57,40))
            s.blit(text,(px,self.oy+285+i*24))
        pygame.display.flip()

    def press(self, pos):
        for key,rect in self.buttons.items():
            if rect.collidepoint(pos):
                if key in ('grid','free','erase'):
                    self.mode = key
                elif key == 'clear':
                    self.tracks = set(self.stations)
                    self.curves = []
                    self.build_graph()
                    self.set_route()
                elif key == 'home':
                    return 'home'
                return None
        if not self.inside(pos):
            return None
        self.dragging = True
        self.last_cell = self.cell_at(pos)
        if self.mode == 'grid':
            self.add_grid(self.last_cell)
        elif self.mode == 'erase':
            self.remove_at(pos)
        else:
            self.drawing = [self.snap(pos)]
        return None

    def motion(self, pos):
        if not self.dragging or not self.inside(pos):
            return
        if self.mode == 'grid':
            cell = self.cell_at(pos)
            if cell != self.last_cell:
                if self.last_cell is not None and cell is not None:
                    x0,y0 = self.last_cell
                    x1,y1 = cell
                    # Orthogonal route for quick diagonal finger motion.
                    while x0 != x1:
                        x0 += 1 if x1>x0 else -1
                        self.add_grid((x0,y0))
                    while y0 != y1:
                        y0 += 1 if y1>y0 else -1
                        self.add_grid((x0,y0))
                self.last_cell = cell
        elif self.mode == 'free':
            if distance(pos,self.drawing[-1]) > max(3,self.cell*.18):
                self.drawing.append(pos)
        elif self.mode == 'erase':
            self.remove_at(pos)

    def release(self, pos):
        if self.dragging and self.mode == 'free':
            if self.inside(pos) and self.drawing and distance(pos,self.drawing[-1]) > 2:
                self.drawing.append(pos)
            self.finish_curve()
        self.dragging = False
        self.last_cell = None


async def main(screen, clock):
    world = World(screen)
    running = True
    finger = None
    touch_active = False
    while running:
        dt = min(clock.tick(FPS)/1000.0, .05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.FINGERDOWN and finger is None:
                finger = event.finger_id
                touch_active = True
                if world.press((event.x*world.w,event.y*world.h)) == 'home':
                    running = False
            elif event.type == pygame.FINGERMOTION and event.finger_id == finger:
                world.motion((event.x*world.w,event.y*world.h))
            elif event.type == pygame.FINGERUP and event.finger_id == finger:
                world.release((event.x*world.w,event.y*world.h))
                finger = None
                touch_active = False
            # SDL may synthesize mouse events from touch: ignore them during touch.
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not touch_active:
                if world.press(event.pos) == 'home':
                    running = False
            elif event.type == pygame.MOUSEMOTION and world.dragging and not touch_active:
                world.motion(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and not touch_active:
                world.release(event.pos)
        world.update(dt)
        world.draw()
        await asyncio.sleep(0)
