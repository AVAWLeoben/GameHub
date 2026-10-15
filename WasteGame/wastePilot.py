import pygame
import math
import asyncio
import pygame.surfarray
import numpy as np
from GUI import Button


def tint_image(image, tint_color):
    """Returns a new image tinted with the given RGB color."""
    tinted_image = image.copy()
    tinted_image.fill((0, 0, 0, 255), None, pygame.BLEND_RGBA_MULT)  # remove original color
    tinted_image.fill(tint_color[0:3] + (0,), None, pygame.BLEND_RGBA_ADD)  # apply tint
    return tinted_image


# Ring-course gameplay. Coordinates use the same continuous X/Y flight space and
# altitude units as the existing Mode 7 renderer.
ALT_MIN = 55000
ALT_MAX = 390000
RING_RADIUS_XY = 255.0
RING_RADIUS_Z = 36000.0
# Map altitude units are much larger than ground X/Y units. This scale makes
# visible ring height agree with its 3-D collision opening.
RING_VERTICAL_SCALE = 3.0
# Once the helicopter is within 400 map units, the gate switches to final
# approach. A centered, correctly levelled *forward* approach is confirmed
# before its giant perspective sprite can run offscreen.
RING_CAPTURE_DISTANCE = 400.0
PASS_BANNER_DURATION = 78  # frames at the game's original 120 FPS

# Two small coins between each pair of rings act as navigational breadcrumbs.
# Depth alone does NOT visually separate objects along the same camera ray:
# two perfectly collinear coins both project onto the same pixel. Place them
# near opposite edges of the flight line and farther apart down the route, so
# they read as separate 3-D markers rather than a stacked coin pile. Their
# generous pickup radius means flying the center of the trail still collects
# them; no slalom or deviation from the flight course is required.
GUIDE_COIN_FRACTIONS = (0.26, 0.74)
GUIDE_COIN_LATERAL_OFFSET = 185.0
GUIDE_COIN_REWARD = 15
GUIDE_COIN_PICKUP_XY = 310.0
GUIDE_COIN_PICKUP_Z = 29000.0
GUIDE_COIN_MAX_DIAMETER = 23

# These courses join together across the existing scrolling map. The map texture
# wraps as before; the helicopter is never teleported between courses.
COURSE_SPECS = (
    {"name": "HORIZON RUN", "subtitle": "Gentle turns and introductory climbs",
     "count": 18, "spacing": 9200, "color": (90, 237, 201)},
    {"name": "SWITCHBACK", "subtitle": "Sharper turns and changing elevations",
     "count": 20, "spacing": 8600, "color": (255, 192, 96)},
    {"name": "SKY CIRCUIT", "subtitle": "Long climbing turns and precision flying",
     "count": 22, "spacing": 9000, "color": (128, 181, 255)},
)


def project_flight_object(x, y, z):
    """Use the original Mode 7 bearing/horizon with readable altitude scale."""
    dx, dy = x - player_x, y - player_y
    rad = math.radians(player_angle)
    forward = dx * math.cos(rad) + dy * math.sin(rad)
    if forward <= 35:
        return None
    side = -dx * math.sin(rad) + dy * math.cos(rad)
    if abs(math.atan2(side, forward)) > math.pi / 4:
        return None
    screen_x = SCREEN.get_width() / 2 - SCREEN.get_width() / 2 * (side / forward)
    screen_y = 200 + int(player_v) + (player_height - z) * RING_VERTICAL_SCALE / forward
    return screen_x, screen_y, forward


class FlightRing:
    """A vertical checkpoint plane, approached along the incoming route."""

    def __init__(self, x, y, z, index, direction, color):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.index = index
        self.nx, self.ny = math.cos(direction), math.sin(direction)
        self.color = color

    def crossing(self, old_x, old_y, old_z, new_x, new_y, new_z):
        """Detect travel THROUGH the hoop, including fast frame-to-frame motion.

        The ring plane is crossed from the approach side. Interpolating the
        crossing avoids missed collisions at 60/120 FPS. The lateral offset
        and altitude offset must lie inside the same elliptical opening.
        """
        before = (old_x - self.x) * self.nx + (old_y - self.y) * self.ny
        after = (new_x - self.x) * self.nx + (new_y - self.y) * self.ny
        if not (before <= 0.0 < after):
            return False, False, False
        fraction = -before / (after - before)
        x = old_x + (new_x - old_x) * fraction
        y = old_y + (new_y - old_y) * fraction
        z = old_z + (new_z - old_z) * fraction
        lateral = -(x - self.x) * self.ny + (y - self.y) * self.nx
        height_diff = z - self.z
        norm = (lateral / RING_RADIUS_XY) ** 2 + (height_diff / RING_RADIUS_Z) ** 2
        # A miss notification is only shown if the helicopter was near the gate.
        near_miss = abs(lateral) < 1300 and abs(height_diff) < 115000
        return norm <= 1.0, norm <= .16, near_miss

    def near_pass(self, old_x, old_y, old_z, new_x, new_y, new_z):
        """Confirm a genuine final approach inside the 400-unit capture zone.

        Unlike a proximity-only pickup, this needs forward progress along the
        course's ring normal, entry from the proper side, and the same 3-D
        elliptical opening as an exact plane crossing. In particular, a pilot
        who flies past the ring's side or at the wrong height cannot clear it.
        """
        before = (old_x - self.x) * self.nx + (old_y - self.y) * self.ny
        after = (new_x - self.x) * self.nx + (new_y - self.y) * self.ny
        if before > 0 or after > 0 or after <= before + 0.01:
            return False, False
        if math.hypot(new_x - self.x, new_y - self.y) > RING_CAPTURE_DISTANCE:
            return False, False
        lateral = -(new_x - self.x) * self.ny + (new_y - self.y) * self.nx
        height_diff = new_z - self.z
        norm = (lateral / RING_RADIUS_XY) ** 2 + (height_diff / RING_RADIUS_Z) ** 2
        return norm <= 1.0, norm <= .16

    def draw(self, active=True):
        w, h = SCREEN.get_size()
        near = active and math.hypot(self.x - player_x, self.y - player_y) <= RING_CAPTURE_DISTANCE
        if near:
            # The old projection divides by forward distance and rapidly
            # sends a near hoop beyond the viewport. Freeze its perspective
            # denominator at 400 and clamp a SMALL locator to the flight view.
            rad = math.radians(player_angle)
            dx, dy = self.x - player_x, self.y - player_y
            forward = dx * math.cos(rad) + dy * math.sin(rad)
            side = -dx * math.sin(rad) + dy * math.cos(rad)
            if forward <= 0:
                return  # HUD displays TURN BACK instead of a false front hoop
            depth = max(RING_CAPTURE_DISTANCE, forward)
            sx = w / 2 - w / 2 * (side / depth)
            sy = 200 + int(player_v) + (player_height - self.z) * RING_VERTICAL_SCALE / depth
            sx = max(90, min(w - 90, sx))
            sy = max(135, min(h - 155, sy))
            radius = 70  # Small close-range locator, not a giant vanishing hoop
        else:
            p = project_flight_object(self.x, self.y, self.z)
            if p is None:
                return
            sx, sy, depth = p
            if sx < -180 or sx > w + 180 or sy < -175 or sy > h + 175:
                return
            radius = min(170, max(7, int(108000 / max(350, depth))))
        cx, cy = int(sx), int(sy)
        correct_height = abs(player_height - self.z) <= RING_RADIUS_Z
        color = ((96, 240, 162) if correct_height else (255, 184, 91)) if active else (82, 119, 147)
        outline = (235, 255, 222) if active else (128, 159, 174)
        pygame.draw.circle(SCREEN, (14, 41, 55), (cx, cy), radius + 5,
                           max(2, min(13, radius // 7)))
        pygame.draw.circle(SCREEN, color, (cx, cy), radius,
                           max(3, min(13, radius // 6)))
        pygame.draw.circle(SCREEN, outline, (cx, cy), max(3, radius - 5),
                           max(1, radius // 16))
        if active and radius >= 14:
            for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                mark = (cx + int(radius * math.cos(a)),
                        cy + int(radius * math.sin(a)))
                pygame.draw.circle(SCREEN, (255, 251, 212), mark,
                                   max(2, radius // 11))
        # The next gate is marked; following gates are deliberately subdued.
        if active and radius >= 15:
            number = HUD_SMALL_FONT.render(str(self.index + 1), True, (245, 252, 244))
            SCREEN.blit(number, number.get_rect(center=(cx, cy)))
            if near:
                label = HUD_SMALL_FONT.render('FINAL APPROACH', True, (255, 238, 175))
                SCREEN.blit(label, label.get_rect(center=(cx, cy - radius - 17)))


class FlightCoin:
    """Small optional waypoint marker placed on the 3D line to a ring."""

    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.collected = False

    def picked_up_on_segment(self, old_x, old_y, old_z, new_x, new_y, new_z):
        # Find the closest position along this movement step, preventing a
        # fast frame from skipping a coin between the previous/current frame.
        dx, dy = new_x - old_x, new_y - old_y
        length_sq = dx * dx + dy * dy
        t = (max(0.0, min(1.0,
             ((self.x - old_x) * dx + (self.y - old_y) * dy) / length_sq))
             if length_sq > 0.00001 else 1.0)
        px, py = old_x + dx * t, old_y + dy * t
        pz = old_z + (new_z - old_z) * t
        return ((px - self.x) ** 2 + (py - self.y) ** 2
                <= GUIDE_COIN_PICKUP_XY ** 2
                and abs(pz - self.z) <= GUIDE_COIN_PICKUP_Z)

    def draw(self):
        if self.collected:
            return
        p = project_flight_object(self.x, self.y, self.z)
        if p is None:
            return
        sx, sy, distance = p
        w, h = SCREEN.get_size()
        if sx < -28 or sx > w + 28 or sy < -28 or sy > h + 28:
            return
        # Deliberately far smaller than the original 100px collectible.
        diameter = min(GUIDE_COIN_MAX_DIAMETER,
                       max(6, int(72000 / max(1200, distance))))
        x, y = int(sx), int(sy)
        if GUIDE_COIN_FRAMES:
            image = GUIDE_COIN_FRAMES[(frame // 8) % len(GUIDE_COIN_FRAMES)]
            key = ((frame // 8) % len(GUIDE_COIN_FRAMES), diameter)
            sprite = GUIDE_COIN_SCALED.get(key)
            if sprite is None:
                sprite = pygame.transform.smoothscale(image, (diameter, diameter))
                GUIDE_COIN_SCALED[key] = sprite
            SCREEN.blit(sprite, (x - diameter // 2, y - diameter // 2))
        else:
            # Asset-free fallback so coins still work in stripped GameHub builds.
            radius = max(3, diameter // 2)
            pygame.draw.circle(SCREEN, (113, 73, 23), (x, y), radius + 1)
            pygame.draw.circle(SCREEN, (247, 191, 69), (x, y), radius)
            if diameter >= 10:
                pygame.draw.circle(SCREEN, (255, 241, 154), (x - 1, y - 1),
                                   max(2, radius // 2))


def build_guidance_coins(courses, entries):
    """Space breadcrumbs in 3-D without stacking them on the same view ray.

    On straight legs, collinear objects at the same altitude project to the
    *same screen point* regardless of their distance. Tiny alternating lateral
    offsets make the depth sequence legible, while the altitude still smoothly
    interpolates toward the target ring. The offsets remain smaller than the
    collection radius, so pilots can simply follow the centerline.
    """
    result = []
    for course_index, rings in enumerate(courses):
        previous = entries[course_index]
        course_coins = []
        for ring in rings:
            dx, dy = ring.x - previous[0], ring.y - previous[1]
            length = math.hypot(dx, dy)
            # Perpendicular to the current leg, independent of map orientation.
            side_x, side_y = ((-dy / length, dx / length)
                              if length > 0.001 else (0.0, 0.0))
            coins = []
            for index, fraction in enumerate(GUIDE_COIN_FRACTIONS):
                side = GUIDE_COIN_LATERAL_OFFSET * (1 if index % 2 == 0 else -1)
                coins.append(FlightCoin(
                    previous[0] + dx * fraction + side_x * side,
                    previous[1] + dy * fraction + side_y * side,
                    previous[2] + (ring.z - previous[2]) * fraction))
            course_coins.append(coins)
            previous = ring.x, ring.y, ring.z
        result.append(course_coins)
    return result


def collect_guidance_coins(old_x, old_y, old_z):
    """Coins are never required to clear a gate or finish a course."""
    global SCORE
    if SHOW_COURSE_RESULT or COURSE_GATE_INDEX >= len(GUIDE_COINS[COURSE_INDEX]):
        return
    for coin in GUIDE_COINS[COURSE_INDEX][COURSE_GATE_INDEX]:
        if not coin.collected and coin.picked_up_on_segment(
                old_x, old_y, old_z, player_x, player_y, player_height):
            coin.collected = True
            SCORE += GUIDE_COIN_REWARD


def draw_guidance_coins():
    """Only show the current approach; no clutter beyond the next ring."""
    if COURSE_GATE_INDEX < len(GUIDE_COINS[COURSE_INDEX]):
        for coin in GUIDE_COINS[COURSE_INDEX][COURSE_GATE_INDEX]:
            coin.draw()


def reset_guidance_coins(course_index=None):
    courses = (GUIDE_COINS if course_index is None
               else (GUIDE_COINS[course_index],))
    for course in courses:
        for leg in course:
            for coin in leg:
                coin.collected = False


def load_guidance_coin_art():
    """Original rotating coin art if available, otherwise Pygame circles."""
    images = []
    for i in range(1, 6):
        try:
            image = pygame.image.load(
                'assets/wastePilot/coin/star coin rotate %d.png' % i).convert_alpha()
            images.append(image)
        except (OSError, pygame.error, ValueError):
            return []
    return images


def build_flight_courses(start_x, start_y):
    """Three substantial, connected courses with reproducible gate locations.

    Distinct curves and increasing changes of altitude make the player steer
    and climb, rather than simply flying straight through short gate chains.
    """
    courses = []
    entries = []
    previous = (float(start_x), float(start_y), 200000.0)
    for course_id, spec in enumerate(COURSE_SPECS):
        entries.append(previous)
        gates = []
        for i in range(spec['count']):
            if course_id == 0:
                angle = -math.pi / 2 + .20 * math.sin(i * .48) + .10 * math.sin(i * .20)
                altitude = 200000 + 36000 * math.sin(i * .55)
            elif course_id == 1:
                angle = -math.pi / 2 + .48 * math.sin(i * .64) + .16 * math.sin(i * .21)
                altitude = 210000 + 69000 * math.sin(i * .66) + 13000 * math.sin(i * .27)
            else:
                angle = -math.pi / 2 + .19 * i + .11 * math.sin(i * .39)
                altitude = 242000 + 93000 * math.sin(i * .43)
            # The first gate keeps roughly the same heading as the launch.
            distance = spec['spacing'] + 650 * math.sin(i * .8)
            x = previous[0] + math.cos(angle) * distance
            y = previous[1] + math.sin(angle) * distance
            z = max(ALT_MIN + 10000, min(ALT_MAX - 10000, altitude))
            gates.append(FlightRing(x, y, z, i, angle, spec['color']))
            previous = (x, y, z)
        courses.append(gates)
    return courses, entries


def active_ring():
    if COURSE_INDEX < len(COURSES) and COURSE_GATE_INDEX < len(COURSES[COURSE_INDEX]):
        return COURSES[COURSE_INDEX][COURSE_GATE_INDEX]
    return None


def format_flight_time(milliseconds):
    seconds = max(0, int(milliseconds) // 1000)
    return '%02d:%02d' % (seconds // 60, seconds % 60)


def finish_course():
    global SHOW_COURSE_RESULT, COURSE_FINISH_TICK, COURSE_BEST
    SHOW_COURSE_RESULT = True
    COURSE_FINISH_TICK = pygame.time.get_ticks()
    score = SCORE - COURSE_SCORE_START
    previous_best = COURSE_BEST[COURSE_INDEX]
    if previous_best is None or score > previous_best:
        COURSE_BEST[COURSE_INDEX] = score


def course_rank():
    count = len(COURSES[COURSE_INDEX])
    if COURSE_MISSES == 0 and COURSE_PERFECT >= (count + 2) // 3:
        return 'S'
    if COURSE_MISSES <= 2 and COURSE_PERFECT >= count // 4:
        return 'A'
    if COURSE_MISSES <= 4:
        return 'B'
    if COURSE_MISSES <= 8:
        return 'C'
    return 'D'


def collect_ring_if_crossed(old_x, old_y, old_z):
    global COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES, SCORE
    global RING_MESSAGE, RING_MESSAGE_FRAMES, PASS_BANNER_FRAMES, PASS_BANNER_TEXT
    ring = active_ring()
    if ring is None:
        return
    # Keep the original exact plane-crossing test for fast jumps and precision,
    # but also accept a properly aligned approach within 400 units so a gate
    # cannot visually vanish before a clear is acknowledged.
    cleared, perfect, near_miss = ring.crossing(
        old_x, old_y, old_z, player_x, player_y, player_height)
    if not cleared:
        cleared, perfect = ring.near_pass(
            old_x, old_y, old_z, player_x, player_y, player_height)
    if cleared:
        COURSE_GATE_INDEX += 1
        if perfect:
            COURSE_PERFECT += 1
        reward = 450 if perfect else 250
        SCORE += reward
        RING_MESSAGE = 'PERFECT PASS  +450' if perfect else 'RING CLEARED  +250'
        RING_MESSAGE_FRAMES = 100
        PASS_BANNER_TEXT = 'PERFECT PASS  +450' if perfect else 'RING CLEARED  +250'
        PASS_BANNER_FRAMES = PASS_BANNER_DURATION
        if COURSE_GATE_INDEX == len(COURSES[COURSE_INDEX]):
            SCORE += 1500
            RING_MESSAGE = 'COURSE COMPLETE  +1500'
            finish_course()
    elif near_miss:
        COURSE_MISSES += 1
        RING_MESSAGE = 'MISSED RING - TURN BACK AND TRY AGAIN'
        RING_MESSAGE_FRAMES = 135


def course_button_rect(primary):
    cx = SCREEN.get_width() // 2
    cy = SCREEN.get_height() // 2
    return pygame.Rect(cx + (7 if primary else -221), cy + 137, 214, 53)


def begin_next_course():
    global COURSE_INDEX, COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES
    global SHOW_COURSE_RESULT, COURSE_START_TICK, COURSE_SCORE_START
    global RING_MESSAGE, RING_MESSAGE_FRAMES, PASS_BANNER_FRAMES
    if COURSE_INDEX == len(COURSES) - 1:
        restart_ring_run()
        return
    COURSE_INDEX += 1
    COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES = 0, 0, 0
    COURSE_START_TICK = pygame.time.get_ticks()
    COURSE_SCORE_START = SCORE
    SHOW_COURSE_RESULT = False
    RING_MESSAGE, RING_MESSAGE_FRAMES = '', 0
    PASS_BANNER_FRAMES = 0


def retry_current_course():
    global player_x, player_y, player_height, player_angle, player_v
    global COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES, SCORE
    global COURSE_START_TICK, SHOW_COURSE_RESULT, RING_MESSAGE_FRAMES
    global PASS_BANNER_FRAMES
    ring = COURSES[COURSE_INDEX][0]
    player_x, player_y, player_height = COURSE_ENTRIES[COURSE_INDEX]
    player_angle = math.degrees(math.atan2(ring.ny, ring.nx))
    player_v = 0
    SCORE = COURSE_SCORE_START
    COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES = 0, 0, 0
    reset_guidance_coins(COURSE_INDEX)
    COURSE_START_TICK = pygame.time.get_ticks()
    SHOW_COURSE_RESULT = False
    RING_MESSAGE_FRAMES = 0
    PASS_BANNER_FRAMES = 0


def restart_ring_run():
    global COURSE_INDEX, COURSE_GATE_INDEX, COURSE_PERFECT, COURSE_MISSES
    global COURSE_START_TICK, COURSE_SCORE_START, SHOW_COURSE_RESULT, SCORE
    global player_x, player_y, player_height, player_angle, player_v
    global RING_MESSAGE, RING_MESSAGE_FRAMES, PASS_BANNER_FRAMES
    COURSE_INDEX, COURSE_GATE_INDEX = 0, 0
    COURSE_PERFECT, COURSE_MISSES = 0, 0
    SCORE, COURSE_SCORE_START = 0, 0
    reset_guidance_coins()
    player_x, player_y, player_height = COURSE_ENTRIES[0]
    player_angle, player_v = -90, 0
    COURSE_START_TICK = pygame.time.get_ticks()
    SHOW_COURSE_RESULT = False
    RING_MESSAGE, RING_MESSAGE_FRAMES = '', 0
    PASS_BANNER_FRAMES = 0


def handle_course_result(events):
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                begin_next_course()
            elif event.key == pygame.K_r:
                retry_current_course()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if course_button_rect(True).collidepoint(event.pos):
                begin_next_course()
            elif course_button_rect(False).collidepoint(event.pos):
                retry_current_course()
        elif event.type == pygame.FINGERDOWN:
            pos = (int(event.x * SCREEN.get_width()),
                   int(event.y * SCREEN.get_height()))
            if course_button_rect(True).collidepoint(pos):
                begin_next_course()
            elif course_button_rect(False).collidepoint(pos):
                retry_current_course()


def draw_course_results():
    w, h = SCREEN.get_size()
    panel = pygame.Surface((min(550, w - 32), min(470, h - 30)), pygame.SRCALPHA)
    pw, ph = panel.get_size()
    panel.fill((9, 27, 39, 239))
    pygame.draw.rect(panel, (112, 176, 183), panel.get_rect(), 3, border_radius=12)
    center = pw // 2
    title = 'ALL COURSES COMPLETE' if COURSE_INDEX == len(COURSES) - 1 else 'COURSE COMPLETE'
    txt = HUD_BIG_FONT.render(title, True, (236, 246, 245))
    panel.blit(txt, txt.get_rect(center=(center, 40)))
    spec = COURSE_SPECS[COURSE_INDEX]
    line = HUD_FONT.render(spec['name'], True, spec['color'])
    panel.blit(line, line.get_rect(center=(center, 82)))
    rank = HUD_RANK_FONT.render(course_rank(), True, (255, 225, 117))
    panel.blit(rank, rank.get_rect(center=(center, 167)))
    elapsed = COURSE_FINISH_TICK - COURSE_START_TICK
    stats = (
        'TIME   ' + format_flight_time(elapsed),
        'GATES   %d / %d' % (COURSE_GATE_INDEX, len(COURSES[COURSE_INDEX])),
        'PERFECT   %d     MISSES   %d' % (COURSE_PERFECT, COURSE_MISSES),
        'COURSE SCORE   %d' % (SCORE - COURSE_SCORE_START),
    )
    for i, info in enumerate(stats):
        img = HUD_FONT.render(info, True, (220, 233, 234))
        panel.blit(img, img.get_rect(center=(center, 228 + i * 35)))
    SCREEN.blit(panel, (w // 2 - pw // 2, h // 2 - ph // 2))
    buttons = ((False, 'RETRY COURSE'),
               (True, 'RESTART RUN' if COURSE_INDEX == len(COURSES) - 1 else 'NEXT COURSE'))
    for primary, text in buttons:
        r = course_button_rect(primary)
        color = (112, 219, 190) if primary else (57, 94, 111)
        pygame.draw.rect(SCREEN, color, r, border_radius=8)
        pygame.draw.rect(SCREEN, (210, 245, 237), r, 2, border_radius=8)
        img = HUD_SMALL_FONT.render(text, True, (8, 35, 43) if primary else (239, 247, 247))
        SCREEN.blit(img, img.get_rect(center=r.center))


def draw_flight_hud():
    """Compact course guidance, leaving the original cockpit unobstructed."""
    global RING_MESSAGE_FRAMES
    spec = COURSE_SPECS[COURSE_INDEX]
    total = len(COURSES[COURSE_INDEX])
    line1 = '%s  |  COURSE %d/%d  |  GATE %d/%d' % (
        spec['name'], COURSE_INDEX + 1, len(COURSES), COURSE_GATE_INDEX + 1, total)
    if SHOW_COURSE_RESULT:
        line1 = '%s  |  COURSE %d/%d FINISHED' % (
            spec['name'], COURSE_INDEX + 1, len(COURSES))
    notification = RING_MESSAGE_FRAMES > 0
    title = HUD_FONT.render(RING_MESSAGE if notification else line1, True,
                            (255, 222, 139) if notification else (251, 250, 231))
    SCREEN.blit(title, title.get_rect(center=(SCREEN.get_width() // 2, 20)))
    if notification:
        RING_MESSAGE_FRAMES -= 1
    ring = active_ring()
    if ring:
        distance = int(math.hypot(ring.x - player_x, ring.y - player_y))
        height_delta = int((ring.z - player_height) / 1000)
        climb = 'LEVEL' if abs(height_delta) < 9 else (
            'CLIMB +%d' % height_delta if height_delta > 0
            else 'DESCEND %d' % (-height_delta))
        line2 = 'DIST %d  |  %s  |  SCORE %d  |  %s' % (
            distance, climb, SCORE, COPTER_CHOICES[SELECTED_COPTER]['name'])
    else:
        line2 = 'SCORE %d  |  %s' % (SCORE, COPTER_CHOICES[SELECTED_COPTER]['name'])
    secondary = HUD_SMALL_FONT.render(line2, True, (222, 241, 244))
    SCREEN.blit(secondary, secondary.get_rect(center=(SCREEN.get_width() // 2, 49)))
    pygame.draw.line(SCREEN, (52, 92, 111), (175, 72),
                     (SCREEN.get_width() - 175, 72), 3)
    usable = SCREEN.get_width() - 350
    end = 175 + int(usable * min(1.0, COURSE_GATE_INDEX / total))
    if end > 175:
        pygame.draw.line(SCREEN, spec['color'], (175, 72), (end, 72), 3)
    if ring:
        p = project_flight_object(ring.x, ring.y, ring.z)
        w, h = SCREEN.get_size()
        side_of_screen = p is None or p[0] < 24 or p[0] > w - 24
        high_or_low = p is not None and (p[1] < 90 or p[1] > h - 80)
        if side_of_screen:
            rad = math.radians(player_angle)
            dx, dy = ring.x - player_x, ring.y - player_y
            side = -dx * math.sin(rad) + dy * math.cos(rad)
            forward = dx * math.cos(rad) + dy * math.sin(rad)
            is_left = side >= 0
            x = 142 if is_left else w - 142
            y = 143
            direction = -1 if is_left else 1
            pygame.draw.polygon(SCREEN, (255, 209, 112),
                                [(x + direction * 15, y - 10),
                                 (x - direction * 15, y),
                                 (x + direction * 15, y + 10)])
            hint = 'TURN BACK' if forward < 0 else ('LEFT' if is_left else 'RIGHT')
            text = HUD_SMALL_FONT.render(hint, True, (240, 234, 201))
            SCREEN.blit(text, text.get_rect(center=(x, y + 26)))
        elif high_or_low and abs(ring.z - player_height) > RING_RADIUS_Z:
            # A ring above/below the camera is not a left/right turn.
            hint = 'CLIMB' if ring.z > player_height else 'DESCEND'
            text = HUD_SMALL_FONT.render(hint, True, (255, 209, 112))
            SCREEN.blit(text, text.get_rect(center=(w // 2, 115)))

        # When the gate is very close, spell out WHY it has not cleared yet.
        # The next-ring locator stays visible even if the 3-D hoop is clipped.
        if math.hypot(ring.x - player_x, ring.y - player_y) <= RING_CAPTURE_DISTANCE:
            before = (player_x - ring.x) * ring.nx + (player_y - ring.y) * ring.ny
            lateral = -(player_x - ring.x) * ring.ny + (player_y - ring.y) * ring.nx
            delta_z = ring.z - player_height
            if before >= 0:
                tip = 'GATE BEHIND YOU - TURN BACK'
            else:
                lateral_ratio = abs(lateral) / RING_RADIUS_XY
                height_ratio = abs(delta_z) / RING_RADIUS_Z
                if lateral_ratio ** 2 + height_ratio ** 2 <= 1.0:
                    tip = 'KEEP FLYING FORWARD TO CLEAR'
                elif height_ratio >= lateral_ratio:
                    tip = 'CLIMB FOR GATE' if delta_z > 0 else 'DESCEND FOR GATE'
                else:
                    tip = 'ALIGN WITH RING CENTER'
            hint = HUD_SMALL_FONT.render(tip, True, (255, 218, 124))
            background = hint.get_rect(center=(w // 2, 112)).inflate(22, 12)
            pygame.draw.rect(SCREEN, (17, 43, 53), background, border_radius=6)
            SCREEN.blit(hint, hint.get_rect(center=background.center))


def draw_pass_confirmation():
    """Large, short-lived confirmation so the pilot notices every successful pass."""
    global PASS_BANNER_FRAMES
    if PASS_BANNER_FRAMES <= 0 or SHOW_COURSE_RESULT:
        return
    w, h = SCREEN.get_size()
    alpha = min(215, int(215 * PASS_BANNER_FRAMES / 20))
    width = min(400, w - 64)
    banner = pygame.Surface((width, 66), pygame.SRCALPHA)
    banner.fill((15, 62, 59, alpha))
    pygame.draw.rect(banner, (125, 248, 194, alpha), banner.get_rect(), 3,
                     border_radius=10)
    text = HUD_BIG_FONT.render(PASS_BANNER_TEXT, True, (244, 255, 225))
    banner.blit(text, text.get_rect(center=(width // 2, 33)))
    SCREEN.blit(banner, (w // 2 - width // 2, min(155, h // 3)))
    PASS_BANNER_FRAMES -= 1


def ret():
    global RUNNING
    RUNNING = False


def drawSky():
    global x_offset
    horizon_y = 200 + int(player_v)
    screen_w = SCREEN.get_width()
    # Parallax offset: shift horizontally based on vertical movement
    if abs(player_v) >= 0:
        x_offset += 1
    if x_offset > 800:
        x_offset = 0
    for line in range(0, horizon_y):
        scalefactor = 1 + (line / 500)

        # Wrap around the sky texture horizontally (parallax wrap)
        line_x_start = x_offset % SKYIMAGE.get_width()
        drawline = SKYIMAGE.subsurface((line_x_start, line), (min(800, SKYIMAGE.get_width() - line_x_start), 1))

        # In case we wrapped, concatenate two pieces
        if drawline.get_width() < 800:
            remainder = 800 - drawline.get_width()
            second_piece = SKYIMAGE.subsurface((0, line), (remainder, 1))
            drawline = pygame.Surface((800, 1))
            drawline.blit(SKYIMAGE, (0, 0), (line_x_start, line, 800 - remainder, 1))
            drawline.blit(second_piece, (800 - remainder, 0))

        # Scale line width for perspective effect
        drawline_scaled = pygame.transform.scale_by(drawline, (scalefactor, 1))

        # Center horizontally on screen
        drawline_rect = drawline_scaled.get_rect(center=(screen_w // 2, line))
        SCREEN.blit(drawline_scaled, drawline_rect)


def draw_mode7_ground(surface, player_x, player_y, player_angle):
    width, height = surface.get_size()
    map_w, map_h = map_image_orig.get_size()
    horizon_y = 200 + int(player_v)
    drawSky()
    angle_rad = math.radians(player_angle)
    left_angle = angle_rad + math.pi / 4
    right_angle = angle_rad - math.pi / 4

    cos_left, sin_left = math.cos(left_angle), math.sin(left_angle)
    cos_right, sin_right = math.cos(right_angle), math.sin(right_angle)

    screen_array = pygame.surfarray.pixels3d(surface)

    # Vectorize across all scanlines
    screen_ys = np.arange(horizon_y, height, 2)
    rel_ys = screen_ys - horizon_y + 1
    distances = player_height / rel_ys

    # Interpolated left/right world positions
    lx = player_x + distances * cos_left
    ly = player_y + distances * sin_left
    rx = player_x + distances * cos_right
    ry = player_y + distances * sin_right

    # Normalized horizontal positions
    t = np.linspace(0, 1, width).reshape((1, -1))  # Shape (1, width)
    lx = lx.reshape((-1, 1))  # Shape (n, 1)
    ly = ly.reshape((-1, 1))
    rx = rx.reshape((-1, 1))
    ry = ry.reshape((-1, 1))

    # Interpolated map coords for each screen row
    xs = ((lx + t * (rx - lx)) % map_w).astype(int)
    ys = ((ly + t * (ry - ly)) % map_h).astype(int)

    # Fill screen lines in batches
    colors = map_array[xs, ys]

    for i, screen_y in enumerate(screen_ys):
        screen_array[:, screen_y] = colors[i]
        if screen_y + 1 < height:
            screen_array[:, screen_y + 1] = colors[i]

    del screen_array




# ---------------------------------------------------------------------------
# Helicopter selection (presentation only; the original flight physics and
# cockpit-control artwork are intentionally unchanged).
# Optional images are loaded from assets/wastePilot/ap.jpg, bh.jpg and uh.jpg.
# If an image is absent or unreadable, native Pygame artwork is shown instead.
# ---------------------------------------------------------------------------
COPTER_CHOICES = (
    {"name": "APACHE", "image": "ap.jpg", "role": "ATTACK HELICOPTER",
     "accent": (232, 178, 86), "hull": (116, 123, 81)},
    {"name": "BLACK HAWK", "image": "bh.jpg", "role": "UTILITY TRANSPORT",
     "accent": (108, 209, 185), "hull": (68, 112, 104)},
    {"name": "HUEY", "image": "uh.jpg", "role": "CLASSIC UTILITY",
     "accent": (145, 185, 236), "hull": (100, 124, 91)},
)
MENU_W, MENU_H = 800, 600


def copter_card_rect(index):
    return pygame.Rect(52 + 236 * index, 155, 224, 304)


def copter_launch_rect():
    return pygame.Rect(282, 484, 236, 61)


def selection_local_pos(pos):
    w, h = SCREEN.get_size()
    return (int(pos[0] * MENU_W / max(1, w)),
            int(pos[1] * MENU_H / max(1, h)))


def render_native_copter(index):
    """Three distinct side-view helicopter silhouettes, no external sprites."""
    art = pygame.Surface((204, 143))
    for y in range(143):
        t = y / 143
        art.fill((int(20 + 29*t), int(42 + 53*t), int(68 + 51*t)),
                 (0, y, 204, 1))
    pygame.draw.polygon(art, (50, 79, 93),
                        [(0, 111), (26, 90), (57, 109), (89, 93),
                         (138, 118), (170, 98), (204, 113), (204, 143), (0, 143)])
    pygame.draw.line(art, (113, 151, 158), (0, 122), (204, 122), 2)
    accent = COPTER_CHOICES[index]["accent"]
    hull = COPTER_CHOICES[index]["hull"]
    shade = tuple(max(0, c - 43) for c in hull)
    window = (40, 75, 96)
    edge = (190, 211, 195)

    # Main rotor: shared physical layout, distinct fuselage silhouettes below.
    pygame.draw.line(art, (30, 38, 39), (105, 55), (105, 43), 4)
    pygame.draw.line(art, (19, 31, 40), (36, 42), (173, 42), 4)
    pygame.draw.line(art, (156, 178, 169), (57, 41), (157, 41), 1)
    pygame.draw.ellipse(art, (190, 198, 174), (100, 39, 10, 6))

    if index == 0:  # AH-64 Apache: angular tandem canopy, stub wings, cannon
        pygame.draw.polygon(art, shade, [(28, 84), (65, 77), (76, 89), (67, 96), (28, 90)])
        pygame.draw.polygon(art, hull,
                            [(60, 75), (122, 66), (147, 75), (174, 91),
                             (170, 100), (108, 103), (79, 96), (64, 88)])
        pygame.draw.polygon(art, window, [(94, 74), (116, 69), (128, 78), (110, 84)])
        pygame.draw.polygon(art, window, [(131, 79), (146, 79), (157, 88), (143, 90)])
        pygame.draw.line(art, edge, (112, 70), (114, 84), 2)
        pygame.draw.line(art, shade, (77, 91), (136, 96), 7)
        pygame.draw.line(art, (49, 53, 50), (89, 100), (84, 113), 4)
        pygame.draw.line(art, (49, 53, 50), (136, 99), (141, 111), 4)
        for x in (82, 93, 105):
            pygame.draw.rect(art, (50, 58, 51), (x, 99, 5, 9), border_radius=1)
        pygame.draw.line(art, (41, 44, 45), (154, 101), (164, 111), 3)
        pygame.draw.circle(art, (25, 30, 32), (164, 112), 4)
        pygame.draw.line(art, edge, (25, 82), (25, 98), 3)
        pygame.draw.line(art, edge, (18, 90), (33, 90), 2)
    elif index == 1:  # UH-60 Black Hawk: long cabin, broad windshield, wheels
        pygame.draw.polygon(art, shade, [(21, 76), (63, 75), (70, 92), (20, 90)])
        pygame.draw.polygon(art, hull,
                            [(57, 67), (131, 67), (160, 82), (174, 94),
                             (166, 106), (70, 108), (58, 93)])
        pygame.draw.polygon(art, window, [(127, 73), (150, 81), (159, 91), (125, 91)])
        pygame.draw.line(art, edge, (138, 76), (140, 91), 2)
        pygame.draw.rect(art, shade, (68, 73, 53, 28), border_radius=3)
        for x in (72, 88, 104):
            pygame.draw.rect(art, window, (x, 77, 12, 13), border_radius=2)
        pygame.draw.line(art, (35, 47, 47), (94, 94), (94, 105), 2)
        pygame.draw.circle(art, (33, 42, 43), (80, 109), 7)
        pygame.draw.circle(art, (33, 42, 43), (147, 108), 7)
        pygame.draw.line(art, edge, (18, 74), (18, 95), 3)
        pygame.draw.line(art, edge, (11, 85), (25, 85), 2)
    else:  # UH-1 Huey: squared cabin, large windows, long landing skids
        pygame.draw.polygon(art, shade, [(19, 79), (64, 76), (67, 91), (19, 90)])
        pygame.draw.polygon(art, hull,
                            [(63, 70), (142, 70), (160, 83), (174, 97),
                             (167, 107), (65, 105)])
        pygame.draw.ellipse(art, hull, (95, 60, 32, 20))
        pygame.draw.rect(art, window, (74, 75, 26, 23), border_radius=2)
        pygame.draw.rect(art, window, (104, 75, 28, 23), border_radius=2)
        pygame.draw.polygon(art, window, [(138, 76), (159, 86), (163, 98), (138, 98)])
        pygame.draw.line(art, edge, (102, 73), (102, 103), 2)
        pygame.draw.line(art, edge, (136, 73), (136, 103), 2)
        pygame.draw.line(art, (35, 42, 39), (79, 106), (77, 120), 3)
        pygame.draw.line(art, (35, 42, 39), (156, 106), (157, 120), 3)
        pygame.draw.line(art, (37, 45, 42), (63, 122), (175, 122), 4)
        pygame.draw.line(art, edge, (17, 77), (17, 96), 3)
        pygame.draw.line(art, edge, (9, 87), (26, 87), 2)

    pygame.draw.rect(art, accent, (9, 10, 35, 3), border_radius=1)
    return art


def crop_copter_photo(image, target_size):
    """Scale without distortion, then crop the edges to fill the preview."""
    w, h = image.get_size()
    tw, th = target_size
    if w < 1 or h < 1:
        return None
    scale = max(tw / w, th / h)
    rw, rh = max(tw, int(math.ceil(w * scale))), max(th, int(math.ceil(h * scale)))
    enlarged = pygame.transform.smoothscale(image, (rw, rh))
    result = pygame.Surface((tw, th))
    result.blit(enlarged, ((tw - rw) // 2, (th - rh) // 2))
    return result


def build_copter_previews():
    previews = []
    for i, copter in enumerate(COPTER_CHOICES):
        img = None
        try:
            photo = pygame.image.load('assets/wastePilot/' + copter['image']).convert()
            img = crop_copter_photo(photo, (204, 143))
        except (OSError, pygame.error, ValueError):
            pass
        previews.append(img if img is not None else render_native_copter(i))
    return previews


def make_copter_menu_background():
    bg = pygame.Surface((MENU_W, MENU_H))
    for y in range(MENU_H):
        t = y / MENU_H
        color = (int(12 + 8*t), int(27 + 17*t), int(43 + 19*t))
        pygame.draw.line(bg, color, (0, y), (MENU_W, y))
    # Muted radar/grid motif. Selection stays visually separate from flight.
    for x in range(0, MENU_W, 40):
        pygame.draw.line(bg, (24, 49, 65), (x, 125), (x, MENU_H), 1)
    for y in range(140, MENU_H, 40):
        pygame.draw.line(bg, (24, 49, 65), (0, y), (MENU_W, y), 1)
    pygame.draw.line(bg, (79, 117, 132), (142, 118), (658, 118), 1)
    return bg


def draw_copter_selection():
    """Draw 800x600 menu, scaled if GameHub supplied a different screen size."""
    canvas = COPTER_MENU_CANVAS
    canvas.blit(COPTER_MENU_BG, (0, 0))
    title_font, name_font, info_font, small_font = COPTER_MENU_FONTS
    heading = title_font.render('SELECT YOUR HELICOPTER', True, (244, 249, 247))
    canvas.blit(heading, heading.get_rect(center=(MENU_W // 2, 48)))
    note = info_font.render('Choose a helicopter to begin your flight', True, (160, 191, 200))
    canvas.blit(note, note.get_rect(center=(MENU_W // 2, 91)))

    for i, copter in enumerate(COPTER_CHOICES):
        r = copter_card_rect(i)
        picked = (i == SELECTED_COPTER)
        accent = copter['accent']
        pygame.draw.rect(canvas, (30, 59, 70) if picked else (23, 41, 56), r,
                         border_radius=13)
        pygame.draw.rect(canvas, accent if picked else (69, 92, 104), r,
                         3 if picked else 1, border_radius=13)
        preview_rect = pygame.Rect(r.left + 10, r.top + 11, 204, 143)
        canvas.blit(COPTER_PREVIEWS[i], preview_rect)
        pygame.draw.rect(canvas, accent if picked else (72, 100, 113),
                         preview_rect, 1)
        canvas.blit(name_font.render(copter['name'], True, (250, 250, 246)),
                    (r.left + 14, r.top + 170))
        canvas.blit(info_font.render(copter['role'], True, (156, 185, 197)),
                    (r.left + 14, r.top + 207))
        pygame.draw.line(canvas, (64, 87, 99),
                         (r.left + 14, r.top + 240),
                         (r.right - 14, r.top + 240), 1)
        state_label = 'SELECTED' if picked else 'TAP TO SELECT'
        state_color = accent if picked else (137, 161, 173)
        state_text = small_font.render(state_label, True, state_color)
        canvas.blit(state_text, state_text.get_rect(center=(r.centerx, r.top + 274)))
        if picked:
            pygame.draw.circle(canvas, accent, (r.right - 21, r.top + 25), 8)
            pygame.draw.line(canvas, (22, 36, 43), (r.right - 25, r.top + 24),
                             (r.right - 22, r.top + 28), 2)
            pygame.draw.line(canvas, (22, 36, 43), (r.right - 22, r.top + 28),
                             (r.right - 17, r.top + 20), 2)

    start = copter_launch_rect()
    active_color = COPTER_CHOICES[SELECTED_COPTER]['accent']
    pygame.draw.rect(canvas, active_color, start, border_radius=10)
    pygame.draw.rect(canvas, (242, 240, 216), start, 2, border_radius=10)
    launch = name_font.render('START FLIGHT  >', True, (12, 33, 43))
    canvas.blit(launch, launch.get_rect(center=start.center))
    footer = info_font.render('Visual selection only  -  flight controls unchanged',
                              True, (145, 174, 186))
    canvas.blit(footer, footer.get_rect(center=(400, 577)))

    if SCREEN.get_size() == (MENU_W, MENU_H):
        SCREEN.blit(canvas, (0, 0))
    else:
        SCREEN.blit(pygame.transform.smoothscale(canvas, SCREEN.get_size()), (0, 0))


def handle_copter_selection(events):
    global SELECTED_COPTER, SHOW_COPTER_SELECT
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                SELECTED_COPTER = (SELECTED_COPTER - 1) % len(COPTER_CHOICES)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                SELECTED_COPTER = (SELECTED_COPTER + 1) % len(COPTER_CHOICES)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                SHOW_COPTER_SELECT = False
            elif event.key == pygame.K_ESCAPE:
                ret()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                SELECTED_COPTER = event.key - pygame.K_1
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = selection_local_pos(event.pos)
            for i in range(len(COPTER_CHOICES)):
                if copter_card_rect(i).collidepoint(pos):
                    SELECTED_COPTER = i
                    break
            if copter_launch_rect().collidepoint(pos):
                SHOW_COPTER_SELECT = False
        elif event.type == pygame.FINGERDOWN:
            # Pygame touch coordinates are normalized to the screen size.
            pos = (int(event.x * MENU_W), int(event.y * MENU_H))
            for i in range(len(COPTER_CHOICES)):
                if copter_card_rect(i).collidepoint(pos):
                    SELECTED_COPTER = i
                    break
            if copter_launch_rect().collidepoint(pos):
                SHOW_COPTER_SELECT = False


def setup():
    global HOME_BUTTON, player_x, player_y, player_angle, player_v, player_a, map_image_orig, map_width, cockpit
    global stick_L, stick_R, stick_M, player_height, frame, map_height
    HOME_BUTTON = Button(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)

    global SKYIMAGE
    SKYIMAGE = pygame.image.load("assets/wastePilot/sky.png")
    global x_offset
    x_offset = 0
    # Player starting position and angle
    player_x = 800
    player_y = 600
    player_angle = -90
    player_v = 0
    player_a = 5

    # Load map
    map_image_orig = pygame.image.load("assets/wastePilot/map_lrg.jpg").convert()
    map_image_orig = pygame.transform.scale_by(map_image_orig, (1, 1))
    map_width, map_height = map_image_orig.get_size()

    # Create minimap
    global minimap
    minimap = pygame.transform.scale(map_image_orig, (map_width // 10, map_height // 10))

    global map_array
    map_array = pygame.surfarray.array3d(map_image_orig)

    # Load Cockpit
    cockpit = pygame.image.load("assets/wastePilot/cockpit_2.png").convert_alpha()
    stick_L = pygame.image.load("assets/wastePilot/stick.png").convert_alpha()
    stick_R = pygame.transform.flip(stick_L, 1, 0)
    stick_M = pygame.image.load("assets/wastePilot/stick_M.png").convert_alpha()

    player_height = 200000
    frame = 0

    global SCORE, COURSES, COURSE_ENTRIES, COURSE_INDEX, COURSE_GATE_INDEX
    global COURSE_PERFECT, COURSE_MISSES, COURSE_START_TICK, COURSE_FINISH_TICK
    global COURSE_SCORE_START, SHOW_COURSE_RESULT, COURSE_BEST
    global RING_MESSAGE, RING_MESSAGE_FRAMES
    global PASS_BANNER_FRAMES, PASS_BANNER_TEXT
    global HUD_FONT, HUD_SMALL_FONT, HUD_BIG_FONT, HUD_RANK_FONT
    SCORE = 0
    COURSES, COURSE_ENTRIES = build_flight_courses(player_x, player_y)
    global GUIDE_COINS, GUIDE_COIN_FRAMES, GUIDE_COIN_SCALED
    GUIDE_COINS = build_guidance_coins(COURSES, COURSE_ENTRIES)
    GUIDE_COIN_FRAMES = load_guidance_coin_art()
    GUIDE_COIN_SCALED = {}
    COURSE_INDEX, COURSE_GATE_INDEX = 0, 0
    COURSE_PERFECT, COURSE_MISSES = 0, 0
    COURSE_START_TICK = pygame.time.get_ticks()
    COURSE_FINISH_TICK = COURSE_START_TICK
    COURSE_SCORE_START = 0
    SHOW_COURSE_RESULT = False
    COURSE_BEST = [None] * len(COURSES)
    RING_MESSAGE, RING_MESSAGE_FRAMES = '', 0
    PASS_BANNER_FRAMES, PASS_BANNER_TEXT = 0, ''
    HUD_FONT = pygame.font.SysFont(None, 26)
    HUD_SMALL_FONT = pygame.font.SysFont(None, 22)
    HUD_BIG_FONT = pygame.font.SysFont(None, 34, bold=True)
    HUD_RANK_FONT = pygame.font.SysFont(None, 112, bold=True)

    # Menu previews are built once. Missing JPEG artwork never blocks flight.
    global SELECTED_COPTER, SHOW_COPTER_SELECT, COPTER_PREVIEWS, COPTER_MENU_BG
    global COPTER_MENU_CANVAS, COPTER_MENU_FONTS
    SELECTED_COPTER = 0
    SHOW_COPTER_SELECT = True
    COPTER_PREVIEWS = build_copter_previews()
    COPTER_MENU_BG = make_copter_menu_background()
    COPTER_MENU_CANVAS = pygame.Surface((MENU_W, MENU_H))
    COPTER_MENU_FONTS = (pygame.font.SysFont(None, 42, bold=True),
                         pygame.font.SysFont(None, 30, bold=True),
                         pygame.font.SysFont(None, 20),
                         pygame.font.SysFont(None, 18, bold=True))


def draw_minimap():
    if 1 == 2:
        # Create minimap
        minimap_scale = 20
        global minimap
        minimap = pygame.transform.scale(map_image_orig, (map_width // minimap_scale, map_height // minimap_scale))
        # # Draw player dot
        px = int(player_x // minimap_scale)
        py = int(player_y // minimap_scale)
        pygame.draw.circle(minimap, pygame.Color("red"), (px, py), 5)
        # Draw viewing direction lines
        dir_length = 15  # Length of the direction line
        angle_rad = math.radians(player_angle)

        # Forward line
        fx = int(px + math.cos(angle_rad) * dir_length)
        fy = int(py + math.sin(angle_rad) * dir_length)
        pygame.draw.line(minimap, pygame.Color("yellow"), (px, py), (fx, fy), 2)

        # Left "shoulder" line (FOV indicator)
        left_angle = angle_rad + math.radians(30)
        lx = int(px + math.cos(left_angle) * dir_length)
        ly = int(py + math.sin(left_angle) * dir_length)
        pygame.draw.line(minimap, pygame.Color("gray"), (px, py), (lx, ly), 1)

        # Right "shoulder" line (FOV indicator)
        right_angle = angle_rad - math.radians(30)
        rx = int(px + math.cos(right_angle) * dir_length)
        ry = int(py + math.sin(right_angle) * dir_length)
        pygame.draw.line(minimap, pygame.Color("gray"), (px, py), (rx, ry), 1)
        SCREEN.blit(minimap, (800 - minimap.get_width(), 0))


def draw_cockpit():
    global player_angle, player_v, player_height
    SCREEN.blit(cockpit, (0, 0))

    # Positions for each control
    pos_L = (0, 600 - stick_L.get_height())
    pos_LM = (200, 600 - stick_L.get_height())
    pos_R = (800 - stick_R.get_width(), 600 - stick_R.get_height())
    pos_RM = (600, 600 - stick_R.get_height())
    pos_M = (SCREEN.get_rect().centerx - stick_M.get_width() // 2, 600 - stick_M.get_height())

    # Get actual button rects
    rect_L = stick_L.get_rect(topleft=pos_L)
    rect_R = stick_R.get_rect(topleft=pos_R)
    rect_M = stick_M.get_rect(topleft=pos_M)
    rect_RM = stick_R.get_rect(topleft=pos_RM)
    rect_LM = stick_L.get_rect(topleft=pos_LM)

    # Input handling
    mouse_pos = pygame.mouse.get_pos()
    finger_down = pygame.mouse.get_pressed()[0]

    # Flags to indicate pressed state
    pressed_L = pressed_R = pressed_M = pressed_LM = pressed_RM = False

    if finger_down:
        if rect_L.collidepoint(mouse_pos):
            player_angle += 2
            pressed_L = True
        elif rect_R.collidepoint(mouse_pos):
            player_angle -= 2
            pressed_R = True
        elif rect_M.collidepoint(mouse_pos):
            player_v = player_v - +player_a
            pressed_M = True
        elif rect_LM.collidepoint(mouse_pos):
            player_height -= 10000
            pressed_LM = True
        elif rect_RM.collidepoint(mouse_pos):
            player_height += 10000
            pressed_RM = True

    # Scaling factor when pressed
    scale_pressed = 0.9

    # Clamp Player Height
    player_height = max(10000, player_height)

    # Function to blit with optional scaling
    def blit_button(image, pos, pressed):
        if pressed:
            scaled = pygame.transform.rotozoom(image, 0, scale_pressed)
            new_rect = scaled.get_rect(center=(pos[0] + image.get_width() // 2, pos[1] + image.get_height() // 2))
            SCREEN.blit(scaled, new_rect.topleft)
        else:
            SCREEN.blit(image, pos)

    # Draw buttons (shrink if pressed)
    blit_button(stick_L, pos_L, pressed_L)
    blit_button(stick_R, pos_R, pressed_R)
    blit_button(stick_M, pos_M, pressed_M)
    blit_button(stick_L, pos_LM, pressed_LM)
    blit_button(stick_R, pos_RM, pressed_RM)


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, EVENTS
    global HOME_BUTTON, player_x, player_y, player_angle, player_v, player_a, map_image_orig, map_width, cockpit
    global stick_L, stick_R, stick_M, player_height, frame

    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    setup()

    while RUNNING:
        CLOCK.tick(60 if (SHOW_COPTER_SELECT or SHOW_COURSE_RESULT) else 120)
        EVENTS = pygame.event.get()

        for event in EVENTS:
            if event.type == pygame.QUIT:
                RUNNING = False

        if SHOW_COPTER_SELECT:
            handle_copter_selection(EVENTS)
            if RUNNING and SHOW_COPTER_SELECT:
                draw_copter_selection()
                HOME_BUTTON.update(EVENTS)
                HOME_BUTTON.draw(screen)
                pygame.display.flip()
            # Never process selection taps as cockpit-control inputs.
            await asyncio.sleep(0)
            continue

        if SHOW_COURSE_RESULT:
            handle_course_result(EVENTS)
            # The previous world view stays behind the result panel; no physics
            # or cockpit input is processed until the next course is selected.
            if RUNNING and SHOW_COURSE_RESULT:
                draw_course_results()
                HOME_BUTTON.update(EVENTS)
                HOME_BUTTON.draw(screen)
                pygame.display.flip()
            await asyncio.sleep(0)
            continue

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            player_v -= player_a
        if keys[pygame.K_s]:
            player_v += player_a
        if keys[pygame.K_d]:
            player_angle -= 2
        if keys[pygame.K_a]:
            player_angle += 2
        if keys[pygame.K_f]:
            player_height += 10000
        if keys[pygame.K_r]:
            player_height -= 10000

        # Add Drag
        player_v = player_v * 0.95
        if abs(player_v) < 0.5:
            player_v = 0

        old_x, old_y, old_z = player_x, player_y, player_height
        rad = math.radians(player_angle)
        player_x -= player_v * math.cos(rad)
        player_y -= player_v * math.sin(rad)

        # Maintain continuous world coordinates across all three courses.
        # The original Mode 7 ground already wraps via its texture lookup.
        player_height = max(ALT_MIN, min(ALT_MAX, player_height))
        collect_guidance_coins(old_x, old_y, old_z)
        collect_ring_if_crossed(old_x, old_y, old_z)

        # Clear screen sky
        screen.fill((100, 120, 255))

        # Draw mode7 ground
        draw_mode7_ground(screen, player_x, player_y, player_angle)

        # Draw Rotor
        if frame % 3 == 0:
            pygame.draw.circle(SCREEN, pygame.Color("lightgray"), (400, -850), 900)
        if frame % 6 == 0:
            pygame.draw.circle(SCREEN, pygame.Color("lightblue"), (400, -850), 900)

        draw_minimap()

        # Small coin breadcrumbs appear only on the approach to the next gate.
        # Render behind the original cockpit, without a separate coin counter.
        draw_guidance_coins()

        # Only the active ring and two muted upcoming rings are visible.
        # They render behind the original cockpit and its five flight controls.
        course = COURSES[COURSE_INDEX]
        for ring in course[COURSE_GATE_INDEX + 1:COURSE_GATE_INDEX + 3]:
            ring.draw(active=False)
        if COURSE_GATE_INDEX < len(course):
            course[COURSE_GATE_INDEX].draw(active=True)

        draw_cockpit()
        draw_flight_hud()
        draw_pass_confirmation()

        HOME_BUTTON.update(EVENTS)
        HOME_BUTTON.draw(screen)
        pygame.display.flip()
        frame += 1

        # print(clock.get_fps())
        # print(f"{player_x} _ {player_y}")
        await asyncio.sleep(0)
    return
