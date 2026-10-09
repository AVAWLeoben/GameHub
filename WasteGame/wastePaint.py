# -*- coding: utf-8 -*-
"""
Created on Mon May 26 20:52:10 2025

@author: Admin
"""
from GUI import Toggle_Button as Button
from GUI import Button as ClickButton
import pygame
import asyncio
import math

try:
    import js
except:
    print("Saving only possible in browser")

RUNNING = True
FPS = 60
SCREEN = None
CLOCK = None
EVENTS = None

# The game runs at 800x600. Keep the painting area away from the toolbar,
# colour palette and edges (particularly useful for iPad users).
# Edit these four numbers to adjust the usable drawing area.
CANVAS_RECT = pygame.Rect(125, 35, 540, 420)
CANVAS_BORDER = 4
MAX_SIMULTANEOUS_FINGERS = 2

# Each finger gets its own previous position, so strokes never connect.
FINGER_LAST_POS = {}
LAST_POS = None  # Mouse/trackpad drawing remains supported.


def ret():
    global RUNNING
    RUNNING = False


COLORS = [
    pygame.Color(60, 60, 60),  # Soft Black (charcoal)
    pygame.Color(255, 105, 97),  # Pastel Red (light coral)
    pygame.Color(135, 206, 235),  # Sky Blue
    pygame.Color(144, 238, 144),  # Light Green
    pygame.Color(255, 255, 153),  # Light Yellow
    pygame.Color(255, 178, 102),  # Light Orange
    pygame.Color(216, 191, 216),  # Light Purple (thistle)
    pygame.Color(255, 182, 193),  # Light Pink
    pygame.Color(205, 133, 63),  # Light Brown (peru)
    pygame.Color(173, 216, 230),  # Powder Blue
    pygame.Color(238, 130, 238),  # Orchid (muted magenta)
]
COLOR_BUTTONS = []


def saveWithoutUI():
    SCREEN.fill((255, 255, 255))
    SCREEN.blit(ARTWORK, CANVAS_RECT.topleft)
    pygame.display.flip()
    script = """
        (function() {
            const canvas = document.querySelector("canvas");
            if (!canvas) {
                alert("Canvas not found!");
                return;
            }

            canvas.toBlob(blob => {
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'my_drawing_NOUI.png';
                link.click();
            });
        })();
    """
    js.eval(script)


def save():
    global SAVING
    SAVING = True

    script = """
        (function() {
            const canvas = document.querySelector("canvas");
            if (!canvas) {
                alert("Canvas not found!");
                return;
            }

            canvas.toBlob(blob => {
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'my_drawing.png';
                link.click();
            });
        })();
    """
    js.eval(script)
    saveWithoutUI()
    SAVING = False


def savefunc():
    try:
        save()
    except:
        print("Saving not possible")
        set_pencil()
        return


home_button = ClickButton(10, 10, 100, 100, "assets/retBut.png", "assets/retBut_clicked.png", ret)
SAVE_BUTTON = ClickButton(10, 110, 100, 100, "assets/saveBut.png", "assets/saveBut.png", savefunc)

BRUSH_SIZE = 4


def interpolate(p1, p2, spacing=None):
    """Generate points between p1 and p2 with given spacing."""
    if spacing is None:
        spacing = max(1, BRUSH_SIZE // 2)
    x1, y1 = p1
    x2, y2 = p2
    dist = math.hypot(x2 - x1, y2 - y1)
    steps = max(int(dist / spacing), 1)
    return [(int(x1 + (x2 - x1) * i / steps), int(y1 + (y2 - y1) * i / steps)) for i in range(steps + 1)]


def inside_canvas(pos):
    """Only presses starting in the white canvas may paint."""
    return CANVAS_RECT.collidepoint(pos)


def paint_point(pos):
    """Draw in canvas-local coordinates; pixels cannot escape the canvas."""
    local = (int(pos[0]) - CANVAS_RECT.x, int(pos[1]) - CANVAS_RECT.y)
    pygame.draw.circle(ARTWORK, BRUSH_COLOR, local, BRUSH_SIZE)


def paint_segment(start, end):
    # The surface itself clips brush circles to the canvas bounds.
    for point in interpolate(start, end):
        paint_point(point)


def finger_position(event):
    """SDL/Pygame FINGER coordinates are normalized to 0..1."""
    w, h = SCREEN.get_size()
    return (int(event.x * w), int(event.y * h))


def user_draw():
    global LAST_POS
    if SAVING:
        return

    for event in EVENTS:
        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            # A touch ID plus a finger ID uniquely identifies an active stroke.
            finger = (getattr(event, "touch_id", 0), event.finger_id)
            pos = finger_position(event)

            if event.type == pygame.FINGERDOWN:
                if len(FINGER_LAST_POS) < MAX_SIMULTANEOUS_FINGERS and inside_canvas(pos):
                    FINGER_LAST_POS[finger] = pos
                    paint_point(pos)

            elif event.type == pygame.FINGERMOTION and finger in FINGER_LAST_POS:
                if inside_canvas(pos):
                    paint_segment(FINGER_LAST_POS[finger], pos)
                    FINGER_LAST_POS[finger] = pos
                else:
                    # Do not draw across the screen or start a new line when
                    # the finger comes back: a new touch must start in canvas.
                    del FINGER_LAST_POS[finger]

            elif event.type == pygame.FINGERUP:
                FINGER_LAST_POS.pop(finger, None)

        # Pygame often produces a synthetic mouse event alongside a finger
        # event. Ignore those here, but leave them for the existing UI buttons.
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if getattr(event, "touch", False):
                continue
            LAST_POS = event.pos if inside_canvas(event.pos) else None
            if LAST_POS is not None:
                paint_point(LAST_POS)

        elif event.type == pygame.MOUSEMOTION:
            if getattr(event, "touch", False):
                continue
            if LAST_POS is not None:
                # Event.buttons records the button state for THIS motion event.
                if not event.buttons[0]:
                    LAST_POS = None
                elif inside_canvas(event.pos):
                    paint_segment(LAST_POS, event.pos)
                    LAST_POS = event.pos
                else:
                    LAST_POS = None

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not getattr(event, "touch", False):
                LAST_POS = None


def set_pencil():
    global BRUSH_SIZE, BRUSH_COLOR
    brush_small_button.isPressed = False
    brush_large_button.isPressed = False
    eraser_button.isPressed = False
    BRUSH_SIZE = 4
    if LAST_COLOR:
        BRUSH_COLOR = LAST_COLOR


pencil_button = Button(690, 100 - 90, 100, 100, "assets/wastePaint/pencil.png", "assets/wastePaint/pencil_active.png", set_pencil)


def set_brush_small():
    global BRUSH_SIZE, BRUSH_COLOR
    pencil_button.isPressed = False
    brush_large_button.isPressed = False
    eraser_button.isPressed = False
    BRUSH_SIZE = 8
    if LAST_COLOR:
        BRUSH_COLOR = LAST_COLOR


brush_small_button = Button(
    690, 250 - 90, 100, 100, "assets/wastePaint/brush_small.png", "assets/wastePaint/brush_small_active.png", set_brush_small
)


def set_brush_large():
    global BRUSH_SIZE, BRUSH_COLOR
    pencil_button.isPressed = False
    brush_small_button.isPressed = False
    eraser_button.isPressed = False
    BRUSH_SIZE = 12
    if LAST_COLOR:
        BRUSH_COLOR = LAST_COLOR


brush_large_button = Button(
    690, 400 - 90, 100, 100, "assets/wastePaint/brush_large.png", "assets/wastePaint/brush_large_active.png", set_brush_large
)


def set_eraser():
    global BRUSH_SIZE, BRUSH_COLOR, LAST_COLOR
    pencil_button.isPressed = False
    brush_small_button.isPressed = False
    brush_large_button.isPressed = False
    BRUSH_SIZE = 12
    LAST_COLOR = BRUSH_COLOR
    BRUSH_COLOR = (255, 255, 255)


eraser_button = Button(690, 550 - 130, 75, 75, "assets/wastePaint/eraser.png", "assets/wastePaint/eraser_active.png", set_eraser)


BRUSH_BUTTONS = [pencil_button, brush_small_button, brush_large_button, eraser_button]


def clear_artwork():
    global ARTWORK
    ARTWORK.fill((255, 255, 255))


CLEAR_BUTTON = ClickButton(
    10, 550 - 90 - 50, 100, 100, "assets/wastePaint/clear_button.png", "assets/wastePaint/clear_button.png", clear_artwork
)


def toggleColorButtons():
    for button in COLOR_BUTTONS:
        if button.color is not BRUSH_COLOR:
            button.isPressed = False
        else:
            button.isPressed = True


def update():
    global RUNNING
    home_button.update(EVENTS)
    CLEAR_BUTTON.update(EVENTS)
    for button in BRUSH_BUTTONS:
        button.update(EVENTS)
    for button in COLOR_BUTTONS:
        button.update(EVENTS)
    toggleColorButtons()
    user_draw()
    CLEAR_BUTTON.update(EVENTS)
    SAVE_BUTTON.update(EVENTS)
    for event in EVENTS:
        if event.type == pygame.QUIT:
            RUNNING = False


def drawBrushButtons():
    for button in BRUSH_BUTTONS:
        button.draw(SCREEN)


def drawColorButtons():
    for button in COLOR_BUTTONS:
        button.draw(SCREEN)
        pygame.draw.circle(SCREEN, button.color, (button.x + button.w / 2, button.y + button.w / 2), button.w / 2)


def draw():
    try:
        SCREEN.fill((255, 255, 255))
        # Gray frame makes the permitted drawing region obvious to children.
        pygame.draw.rect(SCREEN, (95, 95, 95), CANVAS_RECT.inflate(2 * CANVAS_BORDER, 2 * CANVAS_BORDER))
        SCREEN.blit(ARTWORK, CANVAS_RECT.topleft)
        drawBrushButtons()
        drawColorButtons()
        home_button.draw(SCREEN)
        CLEAR_BUTTON.draw(SCREEN)
        SAVE_BUTTON.draw(SCREEN)
        pygame.display.flip()
    except Exception as e:
        print(e)


def setColor(Button):
    global BRUSH_COLOR
    BRUSH_COLOR = Button.color


def createColorButtons():
    global COLORS, COLOR_BUTTONS
    try:
        button_size = 66
        x = 10
        y = 500
        COLOR_BUTTONS = []
        for color in COLORS:
            color_button = Button(
                x, y, button_size, button_size, "assets/wastePaint/color_button.png", "assets/wastePaint/color_button.png", setColor
            )
            color_button.color = color
            COLOR_BUTTONS.append(color_button)
            x = x + color_button.w + 5
    except Exception as e:
        print(e)


async def main(screen, clock):
    global RUNNING, SCREEN, CLOCK, BRUSH_SIZE, BRUSH_COLOR, EVENTS, ARTWORK, SAVING, LAST_COLOR, LAST_POS
    SAVING = False
    SCREEN = screen
    CLOCK = clock
    RUNNING = True
    LAST_POS = None
    FINGER_LAST_POS.clear()
    BRUSH_SIZE = 4
    for button in BRUSH_BUTTONS:
        button.isPressed = False
    createColorButtons()
    BRUSH_COLOR = COLOR_BUTTONS[0].color
    COLOR_BUTTONS[0].isPressed = True
    BRUSH_BUTTONS[0].isPressed = True
    ARTWORK = pygame.Surface(CANVAS_RECT.size)
    # Fill it with white
    ARTWORK.fill((255, 255, 255))
    LAST_COLOR = None
    set_pencil()
    # Prevent Safari from treating touches on the game canvas as page zoom/
    # scroll gestures while this minigame is active. Restore on exit.
    browser_canvas = None
    original_touch_action = None
    try:
        browser_canvas = js.document.querySelector("canvas")
        if browser_canvas is not None:
            original_touch_action = browser_canvas.style.touchAction
            browser_canvas.style.touchAction = "none"
    except (NameError, AttributeError):
        pass  # Desktop Python has no browser DOM.

    try:
        while RUNNING:
            CLOCK.tick(FPS)
            EVENTS = pygame.event.get()
            update()
            draw()
            await asyncio.sleep(0)
    finally:
        FINGER_LAST_POS.clear()
        LAST_POS = None
        if browser_canvas is not None:
            try:
                browser_canvas.style.touchAction = original_touch_action
            except (NameError, AttributeError):
                pass
    return
