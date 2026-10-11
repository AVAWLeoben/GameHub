# -*- coding: utf-8 -*-
"""WastePuzzle — touch-friendly, child-oriented jigsaw-style tile puzzle.

Entry point for GameHub: await wastePuzzle.main(screen, clock)
Uses the existing assets/wastePuzzle/{image1..4,background,balloon_*} files.
There are no extra dependencies beyond pygame-ce / pygame and Python stdlib.
"""

import asyncio
import math
import os
import random

import pygame

FPS = 60
ROWS = COLS = 4
IMAGE_NAMES = ("image1.png", "image2.png", "image3.png", "image4.png")
BALLOON_NAMES = (
    "balloon_black.png", "balloon_blue.png", "balloon_green.png", "balloon_red.png"
)
PALE = (253, 247, 228)
DARK = (44, 64, 77)
BLUE = (64, 150, 214)
GREEN = (62, 177, 116)
YELLOW = (255, 209, 70)
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def candidate_paths(relative):
    """Support normal GameHub launches and Pygbag's virtual working directory."""
    yield os.path.join(MODULE_DIR, "assets", "wastePuzzle", relative)
    yield os.path.join("assets", "wastePuzzle", relative)
    yield os.path.join("WasteGame", "assets", "wastePuzzle", relative)


def load_asset(name, alpha=True):
    for path in candidate_paths(name):
        try:
            image = pygame.image.load(path)
            return image.convert_alpha() if alpha else image.convert()
        except (OSError, pygame.error):
            continue
    return None


def clamp(value, low, high):
    return max(low, min(high, value))


def cover(image, size):
    """Fill screen with the old background, without distorting its proportions."""
    w, h = size
    scale = max(w / image.get_width(), h / image.get_height())
    scaled = pygame.transform.smoothscale(image, (max(1, round(image.get_width()*scale)),
                                                        max(1, round(image.get_height()*scale))))
    r = pygame.Rect(0, 0, w, h)
    return scaled.subsurface(pygame.Rect((scaled.get_width()-w)//2,
                                        (scaled.get_height()-h)//2, w, h)).copy()


def star_points(cx, cy, outer, inner=None):
    if inner is None:
        inner = outer * .47
    return [(round(cx + (outer if j % 2 == 0 else inner) * math.cos(j*math.pi/5-math.pi/2)),
             round(cy + (outer if j % 2 == 0 else inner) * math.sin(j*math.pi/5-math.pi/2)))
            for j in range(10)]


class Piece:
    def __init__(self, piece_id, full_image, preview_image, tray_rect):
        self.id = piece_id
        self.full_image = full_image
        self.preview_image = preview_image
        self.tray_rect = tray_rect
        self.placed = False


class Balloon:
    def __init__(self, width, height, sources, pop_source, rng):
        self.w, self.h = width, height
        target_w = rng.randrange(30, 58)
        chosen = rng.choice(sources) if sources else None
        if chosen is not None:
            aspect = chosen.get_height()/max(1, chosen.get_width())
            self.image = pygame.transform.smoothscale(chosen, (target_w, round(target_w*aspect)))
            self.pop_image = (pygame.transform.smoothscale(pop_source, self.image.get_size())
                              if pop_source else None)
        else:
            self.image = pygame.Surface((target_w, round(target_w*1.35)), pygame.SRCALPHA)
            pygame.draw.ellipse(self.image, rng.choice(((250, 87, 115), (63, 170, 236),
                                                       (94, 211, 136), (255, 197, 55))),
                                self.image.get_rect().inflate(-3, -9))
            self.pop_image = None
        self.x = rng.uniform(self.image.get_width()//2 + 4, max(self.image.get_width()//2 + 5,
                                                                 width-self.image.get_width()//2-4))
        self.y = height + rng.uniform(15, 220)
        self.speed = rng.uniform(65, 130)
        self.phase = rng.uniform(0, math.tau)
        self.amp = rng.uniform(7, 28)
        self.sway = rng.uniform(.012, .026)
        self.popped = False
        self.popped_for = 0.0
        self.alive = True

    def rect(self):
        wobble = math.sin(self.phase + self.y*self.sway)*self.amp
        return self.image.get_rect(center=(round(self.x + wobble), round(self.y)))

    def update(self, dt):
        if self.popped:
            self.popped_for += dt
            if self.popped_for >= 0.4:
                self.alive = False
        else:
            self.y -= self.speed*dt
            if self.y + self.image.get_height() < -30:
                self.alive = False

    def click(self, p):
        if not self.popped and self.rect().collidepoint(p):
            self.popped = True
            return True
        return False

    def draw(self, surface):
        image = self.pop_image if self.popped and self.pop_image else self.image
        surface.blit(image, self.rect())


class WastePuzzle:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.rng = random.Random()
        self.font = pygame.font.Font(None, max(22, round(self.h*.040)))
        self.small = pygame.font.Font(None, max(18, round(self.h*.029)))
        self.big = pygame.font.Font(None, max(34, round(self.h*.072)))
        self.images = [load_asset(n) for n in IMAGE_NAMES]
        self.balloon_images = [im for im in (load_asset(n) for n in BALLOON_NAMES) if im]
        self.pop_image = load_asset('balloon_popped.png')
        self.raw_background = load_asset('background.jpg', alpha=False)
        if self.raw_background:
            self.background = cover(self.raw_background, (self.w, self.h))
        else:
            self.background = pygame.Surface((self.w, self.h))
            self.background.fill((135, 192, 174))
        self.dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.dim.fill((23, 47, 61, 110))
        self.home_icon = None
        for path in (os.path.join(MODULE_DIR, 'assets', 'retBut.png'),
                     'assets/retBut.png', os.path.join('WasteGame', 'assets', 'retBut.png')):
            try:
                self.home_icon = pygame.image.load(path).convert_alpha()
                self.home_icon = pygame.transform.smoothscale(self.home_icon, (44, 44))
                break
            except (OSError, pygame.error):
                pass
        self.image_index = 0
        self.difficulty = 0  # 0=grayscale+marker, 1=grayscale, 2=grid only
        self.phase = 'menu'
        self.running = True
        self.buttons = {}
        self.pieces = []
        self.selected_id = None
        self.drag_id = None
        self.dragging = False
        self.drag_position = (0, 0)
        self.down_position = (0, 0)
        self.owner = None  # ('finger', id) or ('mouse', 0)
        self.balloons = []
        self.success_count = 0
        self.feedback_text = ''
        self.feedback_end = 0
        self.celebration_time = 0.0
        self.compute_layout()

    def compute_layout(self):
        self.header_height = max(70, round(self.h*.14))
        available = self.h-self.header_height-14
        board_size = int(min(available*.88, self.w*.52, 440))
        board_size = max(80, (board_size//COLS)*COLS)
        self.board = pygame.Rect((self.w-board_size)//2,
                                 self.header_height+(available-board_size)//2,
                                 board_size,board_size)
        self.cell = board_size//COLS
        side_w = max(1, self.board.left-20)
        self.tray_left = pygame.Rect(8, self.header_height+2, side_w, available-4)
        self.tray_right = pygame.Rect(self.board.right+12, self.header_height+2,
                                      self.w-self.board.right-20, available-4)
        self.tray_piece_size = max(10, int(min(self.cell*.80,
                              (min(self.tray_left.width,self.tray_right.width)-15)/2,
                              min(self.tray_left.height,self.tray_right.height)/4-13)))

    def text(self, s, x, y, font=None, color=DARK, center=False):
        img = (font or self.font).render(str(s), True, color)
        self.screen.blit(img, img.get_rect(center=(x,y)) if center else (x,y))

    def button(self, name, rect, label, fill=(251, 250, 238), active=False, icon=None):
        rect = pygame.Rect(rect)
        self.buttons[name] = rect
        pygame.draw.rect(self.screen, (36, 58, 66), rect.move(0, 3), border_radius=12)
        pygame.draw.rect(self.screen, GREEN if active else fill, rect, border_radius=12)
        pygame.draw.rect(self.screen, YELLOW if active else (248, 251, 244), rect, 3, border_radius=12)
        if icon == 'house':
            cx, cy = rect.left+23, rect.centery
            pygame.draw.polygon(self.screen, (255, 255, 255),
                                [(cx-12,cy-2),(cx,cy-15),(cx+12,cy-2)])
            pygame.draw.rect(self.screen, (255,255,255), (cx-9,cy-2,18,14))
            pygame.draw.rect(self.screen, fill, (cx-3,cy+3,6,9))
            self.text(label, rect.centerx+11, rect.centery, self.small, DARK, True)
        else:
            self.text(label, rect.centerx, rect.centery, self.font, DARK, True)

    def image_preview(self, source, square):
        if source is None:
            pygame.draw.rect(self.screen, (179, 219, 198), square, border_radius=8)
            self.text('?', square.centerx, square.centery, self.big, DARK, True)
            return
        fitted = pygame.transform.smoothscale(source, (square.width, square.height))
        self.screen.blit(fitted, square.topleft)

    def draw_menu(self):
        self.screen.blit(self.background, (0,0))
        self.screen.blit(self.dim, (0,0))
        self.buttons = {}
        self.text('CHOOSE A PUZZLE', self.w//2, max(34,self.h*.08), self.big, (255,255,240), True)
        n = len(self.images)
        gap = max(9, round(self.w*.016))
        card_width = min(162, (self.w-40-(n-1)*gap)//n)
        img_size = min(card_width-12, max(58, round(self.h*.24)))
        card_h = img_size + 35
        start = (self.w-(card_width*n+gap*(n-1)))//2
        top = round(self.h*.16)
        for idx, image in enumerate(self.images):
            rect = pygame.Rect(start+idx*(card_width+gap), top, card_width, card_h)
            self.buttons['image_'+str(idx)] = rect
            pygame.draw.rect(self.screen, YELLOW if idx==self.image_index else (248,248,241),
                             rect, border_radius=10)
            pygame.draw.rect(self.screen, (255,255,255) if idx==self.image_index else (59,94,104),
                             rect, 3 if idx==self.image_index else 2, border_radius=10)
            square = pygame.Rect(0,0,img_size,img_size)
            square.midtop = (rect.centerx, rect.top+6)
            self.image_preview(image,square)
            self.text('PICTURE '+str(idx+1),rect.centerx,rect.bottom-15,self.small,DARK,True)
        d_top = top + card_h + max(12, round(self.h*.035))
        self.text('HOW HARD?',self.w//2,d_top+11,self.font,(255,255,255),True)
        spacing = min(18, self.w//40)
        diff_w = min(182,(self.w-65-2*spacing)//3)
        diff_h = max(76, round(self.h*.15))
        total = diff_w*3+spacing*2
        dx = (self.w-total)//2
        labels = ('HELP ME', 'PICTURE', 'NO HINTS')
        for level in range(3):
            rect=pygame.Rect(dx+level*(diff_w+spacing), d_top+36,diff_w,diff_h)
            self.buttons['difficulty_'+str(level)] = rect
            pygame.draw.rect(self.screen, GREEN if self.difficulty==level else (247,244,225),rect,border_radius=12)
            pygame.draw.rect(self.screen, YELLOW if self.difficulty==level else (238,241,227),rect,3,border_radius=12)
            size = min(12,rect.height*.19)
            for j in range(level+1):
                cx=rect.centerx+(j-(level/2))*min(32,diff_w*.21)
                pygame.draw.polygon(self.screen,YELLOW,star_points(cx,rect.top+rect.height*.33,size))
            self.text(labels[level],rect.centerx,rect.bottom-20,self.small,DARK,True)
        start_rect=pygame.Rect(0,0,min(272,self.w-80),max(54,round(self.h*.095)))
        start_rect.midbottom = (self.w//2, self.h-16)
        self.button('start',start_rect,'PLAY!',GREEN,True)
        self.button('home', (8,8,min(108,self.w//6),48), 'HOME', (239,181,102), icon='house')

    def new_puzzle(self):
        self.phase = 'playing'
        self.owner = None
        self.drag_id = None
        self.selected_id = None
        self.dragging = False
        self.balloons = []
        self.success_count = 0
        self.feedback_text = ''
        source = self.images[self.image_index]
        if source is None:
            self.image = pygame.Surface((self.board.width, self.board.height))
            self.image.fill((252,205,116))
            for i in range(4):
                c = ((80+i*40)%255, (115+i*23)%255, (160+i*29)%255)
                pygame.draw.circle(self.image,c,(self.cell//2+i*self.cell,
                                                  self.cell//2+(i%2)*self.cell),self.cell//3)
        else:
            self.image = pygame.transform.smoothscale(source,self.board.size)
        self.gray = pygame.transform.grayscale(self.image)
        self.gray.set_alpha(150)
        order = list(range(ROWS*COLS))
        self.rng.shuffle(order)
        if order == list(range(ROWS*COLS)):
            order=order[1:]+order[:1]
        slots=[]
        # Compact two-column trays. Center them alongside the board, not at
        # fixed positions that would climb under the Home button.
        horizontal_gap = max(6, min(14, self.tray_left.width - 2*self.tray_piece_size - 6))
        vertical_gap = max(6, min(17, (self.tray_left.height - 4*self.tray_piece_size)//3))
        row_step = self.tray_piece_size + vertical_gap
        first_y = self.board.centery - (3*row_step)/2
        for side in (self.tray_left,self.tray_right):
            first_x = side.centerx - (self.tray_piece_size+horizontal_gap)/2
            for row in range(4):
                for col in range(2):
                    x = first_x + col*(self.tray_piece_size+horizontal_gap)
                    y = first_y + row*row_step
                    rect=pygame.Rect(0,0,self.tray_piece_size,self.tray_piece_size)
                    rect.center=(round(x),round(y))
                    slots.append(rect)
        self.pieces=[]
        for slot,pid in zip(slots,order):
            col,row=pid%COLS,pid//COLS
            tile=self.image.subsurface(pygame.Rect(col*self.cell,row*self.cell,
                                                    self.cell,self.cell)).copy()
            mini=pygame.transform.smoothscale(tile,(self.tray_piece_size,self.tray_piece_size))
            self.pieces.append(Piece(pid,tile,mini,slot))
        self.piece_by_id={p.id:p for p in self.pieces}

    def attempt_place(self, pid, screen_point):
        if pid is None or not self.board.collidepoint(screen_point):
            return False
        col = int((screen_point[0]-self.board.left)//self.cell)
        row = int((screen_point[1]-self.board.top)//self.cell)
        if row*COLS+col != pid:
            self.feedback_text='TRY AGAIN!'
            self.feedback_end=pygame.time.get_ticks()+700
            return False
        piece=self.piece_by_id[pid]
        if piece.placed:
            return False
        piece.placed=True
        self.selected_id=None
        self.success_count += 1
        if self.success_count==ROWS*COLS:
            self.phase='celebration'
            self.celebration_time=0.0
            # Original 8-14 balloons increased to 12-21 (exactly 1.5x).
            count=self.rng.randint(12,21)
            self.balloons=[Balloon(self.w,self.h,self.balloon_images,self.pop_image,self.rng)
                           for _ in range(count)]
        return True

    def pick_piece(self, point):
        # All tray pieces are non-overlapping. Reverse draw order for consistency.
        for piece in reversed(self.pieces):
            if not piece.placed and piece.tray_rect.collidepoint(point):
                return piece.id
        return None

    def pointer_down(self, point):
        for name, rect in self.buttons.items():
            if rect.collidepoint(point):
                if name == 'home':
                    self.running=False
                elif self.phase=='menu':
                    if name.startswith('image_'):
                        self.image_index=int(name.rsplit('_',1)[1])
                    elif name.startswith('difficulty_'):
                        self.difficulty=int(name.rsplit('_',1)[1])
                    elif name=='start':
                        self.new_puzzle()
                else:
                    if name=='pictures':
                        self.phase='menu'
                        self.drag_id=None
                        self.selected_id=None
                    elif name=='retry':
                        self.new_puzzle()
                return
        if self.phase=='playing':
            pid=self.pick_piece(point)
            if pid is not None:
                self.drag_id=pid
                self.down_position=point
                self.drag_position=point
                self.dragging=False
            elif self.selected_id is not None and self.board.collidepoint(point):
                self.attempt_place(self.selected_id,point)
        elif self.phase=='celebration':
            for balloon in reversed(self.balloons):
                if balloon.click(point):
                    break

    def pointer_move(self, point):
        if self.phase=='playing' and self.drag_id is not None:
            self.drag_position=point
            if math.hypot(point[0]-self.down_position[0],point[1]-self.down_position[1])>8:
                self.dragging=True

    def pointer_up(self, point):
        if self.phase=='playing' and self.drag_id is not None:
            if self.dragging or math.hypot(point[0]-self.down_position[0],
                                           point[1]-self.down_position[1])>12:
                self.attempt_place(self.drag_id,point)
                self.selected_id=None
            else:
                self.selected_id=self.drag_id
            self.drag_id=None
            self.dragging=False

    def process_event(self, event):
        if event.type==pygame.QUIT:
            self.running=False
            return
        if event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE:
            self.running=False
            return
        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            identity=('finger',event.finger_id)
            p=(int(event.x*self.w),int(event.y*self.h))
            if event.type==pygame.FINGERDOWN:
                # One active drag at a time; other fingers cannot steal pieces.
                if self.owner is None:
                    self.owner=identity
                    self.pointer_down(p)
            elif identity==self.owner:
                if event.type==pygame.FINGERMOTION:
                    self.pointer_move(p)
                else:
                    self.pointer_up(p)
                    self.owner=None
            return
        if event.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEMOTION,pygame.MOUSEBUTTONUP):
            if getattr(event,'touch',False) or getattr(event,'which',None)==getattr(pygame,'TOUCH_MOUSEID',-1):
                return
            identity=('mouse',0)
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                if self.owner is None:
                    self.owner=identity
                    self.pointer_down(event.pos)
            elif event.type==pygame.MOUSEMOTION and self.owner==identity:
                self.pointer_move(event.pos)
            elif event.type==pygame.MOUSEBUTTONUP and event.button==1 and self.owner==identity:
                self.pointer_up(event.pos)
                self.owner=None

    def draw_game(self, dt):
        self.screen.blit(self.background,(0,0))
        self.buttons={}
        # The board is centered with a dedicated two-column/four-row tray on each side.
        pygame.draw.rect(self.screen,(45,70,76),self.board.inflate(12,12),border_radius=10)
        pygame.draw.rect(self.screen,PALE,self.board)
        if self.difficulty in (0,1):
            self.screen.blit(self.gray,self.board.topleft)
        for i in range(1,COLS):
            x=self.board.left+i*self.cell
            pygame.draw.line(self.screen,(68,85,88),(x,self.board.top),(x,self.board.bottom),2)
        for i in range(1,ROWS):
            y=self.board.top+i*self.cell
            pygame.draw.line(self.screen,(68,85,88),(self.board.left,y),(self.board.right,y),2)
        # Place solved pieces exactly at their destination (full resolution).
        for p in self.pieces:
            if p.placed:
                tile = self.target_rect(p.id)
                self.screen.blit(p.full_image,tile)
                pygame.draw.rect(self.screen,(234,235,214),tile,1)
        # Side trays are visually subtle and never cover the top navigation.
        for tray in (self.tray_left,self.tray_right):
            layer=pygame.Surface(tray.size,pygame.SRCALPHA)
            layer.fill((246,243,221,55))
            self.screen.blit(layer,tray.topleft)
        for p in self.pieces:
            if p.placed or (p.id==self.drag_id and self.dragging):
                continue
            selected=p.id==self.selected_id or p.id==self.drag_id
            highlight=p.tray_rect.inflate(7,7)
            pygame.draw.rect(self.screen,YELLOW if selected else (245,245,227),
                             highlight,border_radius=5)
            self.screen.blit(p.preview_image,p.tray_rect)
            pygame.draw.rect(self.screen,DARK if not selected else (255,247,191),
                             highlight,2,border_radius=5)
        active=self.drag_id if self.drag_id is not None else self.selected_id
        # Guide marker exists ONLY on the easiest level.
        if self.difficulty==0 and active is not None and not self.piece_by_id[active].placed:
            target=self.target_rect(active)
            pygame.draw.circle(self.screen,(48,111,219),target.center,max(9,self.cell//11),3)
            pygame.draw.circle(self.screen,YELLOW,target.center,max(4,self.cell//21))
            if self.drag_id is not None and self.dragging:
                self.draw_dotted_line(self.drag_position,target.center)
        if self.drag_id is not None and self.dragging:
            dragged=self.piece_by_id[self.drag_id].full_image
            pos=dragged.get_rect(center=self.drag_position)
            pygame.draw.rect(self.screen,YELLOW,pos.inflate(6,6),border_radius=4)
            self.screen.blit(dragged,pos)
        # HUD overlays field without hiding draggable pieces.
        pygame.draw.rect(self.screen,(32,69,74),(0,0,self.w,self.header_height))
        hbtn=max(45,self.header_height-18)
        self.button('home',(9,8,max(90,self.w//9),hbtn),'HOME',(239,177,99),icon='house')
        self.button('pictures',(max(108,self.w//8),8,max(118,self.w//6),hbtn),'PICTURES',(245,235,189))
        self.button('retry',(max(240,self.w//3.2),8,max(107,self.w//7),hbtn),'RESTART',(242,191,117))
        self.text(str(self.success_count)+' / 16', self.w-40,self.header_height//2,
                  self.font,(255,255,255),True)
        if self.phase=='celebration':
            self.celebration_time+=dt
            for b in self.balloons:
                b.update(dt)
            self.balloons=[b for b in self.balloons if b.alive]
            self.draw_celebration_banner()
            for b in self.balloons:
                b.draw(self.screen)
        elif self.feedback_text and pygame.time.get_ticks()<self.feedback_end:
            self.text(self.feedback_text,self.w//2,self.header_height+19,
                      self.font,(232,80,62),True)

    def target_rect(self, pid):
        return pygame.Rect(self.board.left+(pid%COLS)*self.cell,
                           self.board.top+(pid//COLS)*self.cell,
                           self.cell,self.cell)

    def draw_dotted_line(self,a,b):
        distance=math.hypot(b[0]-a[0],b[1]-a[1])
        if distance<4:
            return
        steps=max(1,int(distance/15))
        for i in range(steps):
            t=i/steps
            pygame.draw.circle(self.screen,(245,196,66),
                               (round(a[0]+(b[0]-a[0])*t),round(a[1]+(b[1]-a[1])*t)),3)

    def draw_celebration_banner(self):
        # The solved picture remains visible underneath the balloons.
        w=min(self.w-24,530)
        banner=pygame.Rect((self.w-w)//2,self.header_height+8,w,58)
        panel=pygame.Surface(banner.size,pygame.SRCALPHA)
        panel.fill((30,88,100,224))
        self.screen.blit(panel,banner.topleft)
        self.text('WELL DONE!',banner.centerx,banner.centery,
                  self.big,(255,230,99),True)
        # Celebration actions are always accessible (also if balloons have flown off).
        y=self.h-65
        bw=min(165,(self.w-34)//3)
        x=(self.w-(bw*2+14))//2
        self.button('retry',(x,y,bw,52),'AGAIN!',(122,220,137),True)
        self.button('pictures',(x+bw+14,y,bw,52),'PICTURES',(255,226,147))

    def update(self,dt):
        if self.phase=='menu':
            self.draw_menu()
        else:
            self.draw_game(dt)
        pygame.display.flip()


async def main(screen,clock):
    """Run until Home, Escape, or window close; return to GameHub launcher."""
    game=WastePuzzle(screen)
    while game.running:
        dt=min(clock.tick(FPS)/1000.,.05)
        for event in pygame.event.get():
            game.process_event(event)
        if not game.running:
            break
        game.update(dt)
        await asyncio.sleep(0)


if __name__=='__main__':
    pygame.init()
    display=pygame.display.set_mode((800,600))
    asyncio.run(main(display,pygame.time.Clock()))
