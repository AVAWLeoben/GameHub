import asyncio
import random
import pygame

# --- PYGBAG / PYODIDE WEBASSEMBLY CHECK ---
try:
    from js import Peer, create_proxy
    IS_WEB = True
except ImportError:
    IS_WEB = False
    Peer = None
    create_proxy = lambda f: f  # Local desktop fallback

# --- COLOR PALETTE ---
COLOR_BG = (33, 37, 41)         # Deep slate background
COLOR_PANEL = (49, 54, 63)      # Container frame background
COLOR_TEXT = (248, 249, 250)     # Text color
COLOR_GOLD = (255, 193, 7)      # Header gold
COLOR_RED = (255, 71, 87)       # X Player / Clear button
COLOR_GREEN = (46, 213, 115)    # O Player / Play Again
COLOR_BLUE = (30, 144, 255)     # Single Player / Same Screen
COLOR_PURPLE = (155, 89, 182)   # Online Play option
COLOR_ORANGE = (255, 127, 80)   # Create Room option

# --- VECTOR ANIMAL DRAWING (Zero External Files Required) ---
def draw_animal_icon(surface, center_x, center_y, icon_idx, size=32):
    """Draws procedural animal faces using Pygame vector shapes."""
    x, y = center_x, center_y

    if icon_idx == 0:  # DOG
        pygame.draw.ellipse(surface, (120, 70, 32), (x - size * 0.9, y - size * 0.4, size * 0.6, size * 0.9))
        pygame.draw.ellipse(surface, (120, 70, 32), (x + size * 0.3, y - size * 0.4, size * 0.6, size * 0.9))
        pygame.draw.circle(surface, (200, 135, 80), (x, y), size * 0.7)
        pygame.draw.ellipse(surface, (245, 230, 210), (x - size * 0.35, y - size * 0.1, size * 0.7, size * 0.5))
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.25, y - size * 0.2), size * 0.1)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.25, y - size * 0.2), size * 0.1)
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.15, y - size * 0.05, size * 0.3, size * 0.2))

    elif icon_idx == 1:  # CAT
        pygame.draw.polygon(surface, (240, 140, 40), [(x - size * 0.7, y - size * 0.2), (x - size * 0.4, y - size * 0.8), (x - size * 0.1, y - size * 0.4)])
        pygame.draw.polygon(surface, (240, 140, 40), [(x + size * 0.1, y - size * 0.4), (x + size * 0.4, y - size * 0.8), (x + size * 0.7, y - size * 0.2)])
        pygame.draw.circle(surface, (255, 165, 50), (x, y), size * 0.65)
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.25, y - size * 0.15), size * 0.09)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.25, y - size * 0.15), size * 0.09)
        pygame.draw.polygon(surface, (255, 105, 180), [(x - size * 0.1, y), (x + size * 0.1, y), (x, y + size * 0.12)])

    elif icon_idx == 2:  # RABBIT
        pygame.draw.ellipse(surface, (240, 240, 240), (x - size * 0.45, y - size * 1.1, size * 0.35, size * 0.9))
        pygame.draw.ellipse(surface, (240, 240, 240), (x + size * 0.1, y - size * 1.1, size * 0.35, size * 0.9))
        pygame.draw.ellipse(surface, (255, 182, 193), (x - size * 0.35, y - size * 0.95, size * 0.18, size * 0.65))
        pygame.draw.ellipse(surface, (255, 182, 193), (x + size * 0.18, y - size * 0.95, size * 0.18, size * 0.65))
        pygame.draw.circle(surface, (245, 245, 245), (x, y), size * 0.65)
        pygame.draw.circle(surface, (30, 30, 30), (x - size * 0.25, y - size * 0.1), size * 0.09)
        pygame.draw.circle(surface, (30, 30, 30), (x + size * 0.25, y - size * 0.1), size * 0.09)
        pygame.draw.circle(surface, (255, 182, 193), (x - size * 0.4, y + size * 0.1), size * 0.12)
        pygame.draw.circle(surface, (255, 182, 193), (x + size * 0.4, y + size * 0.1), size * 0.12)

    elif icon_idx == 3:  # FOX
        pygame.draw.polygon(surface, (210, 75, 25), [(x - size * 0.75, y - size * 0.2), (x - size * 0.45, y - size * 0.85), (x - size * 0.1, y - size * 0.3)])
        pygame.draw.polygon(surface, (210, 75, 25), [(x + size * 0.1, y - size * 0.3), (x + size * 0.45, y - size * 0.85), (x + size * 0.75, y - size * 0.2)])
        pygame.draw.circle(surface, (230, 90, 35), (x, y), size * 0.65)
        pygame.draw.polygon(surface, (250, 250, 250), [(x - size * 0.65, y), (x, y + size * 0.65), (x, y - size * 0.1)])
        pygame.draw.polygon(surface, (250, 250, 250), [(x + size * 0.65, y), (x, y + size * 0.65), (x, y - size * 0.1)])
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.28, y - size * 0.1), size * 0.08)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.28, y - size * 0.1), size * 0.08)
        pygame.draw.circle(surface, (10, 10, 10), (x, y + size * 0.35), size * 0.12)

    elif icon_idx == 4:  # PANDA
        pygame.draw.circle(surface, (30, 30, 30), (x - size * 0.5, y - size * 0.5), size * 0.25)
        pygame.draw.circle(surface, (30, 30, 30), (x + size * 0.5, y - size * 0.5), size * 0.25)
        pygame.draw.circle(surface, (245, 245, 245), (x, y), size * 0.65)
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.42, y - size * 0.22, size * 0.3, size * 0.38))
        pygame.draw.ellipse(surface, (30, 30, 30), (x + size * 0.12, y - size * 0.22, size * 0.3, size * 0.38))
        pygame.draw.circle(surface, (255, 255, 255), (x - size * 0.26, y - size * 0.08), size * 0.06)
        pygame.draw.circle(surface, (255, 255, 255), (x + size * 0.26, y - size * 0.08), size * 0.06)
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.15, y + size * 0.1, size * 0.3, size * 0.2))

# --- BUTTON & SYMBOL RENDERERS ---
def draw_card_button(surface, rect, title, subtitle, main_color, font_title, font_sub, icon_type=None):
    """Draws 3D tactile buttons with drop shadows."""
    # Shadow
    shadow_rect = pygame.Rect(rect.x, rect.y + 6, rect.width, rect.height)
    pygame.draw.rect(surface, (20, 22, 26), shadow_rect, border_radius=16)

    # Body
    pygame.draw.rect(surface, main_color, rect, border_radius=16)

    # Highlight
    highlight_rect = pygame.Rect(rect.x + 4, rect.y + 4, rect.width - 8, rect.height // 2 - 2)
    overlay = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (255, 255, 255, 45), overlay.get_rect(), border_top_left_radius=12, border_top_right_radius=12)
    surface.blit(overlay, highlight_rect.topleft)

    # Frame
    pygame.draw.rect(surface, (255, 255, 255), rect, width=3, border_radius=16)

    # Content
    if icon_type is not None:
        draw_animal_icon(surface, rect.centerx, rect.centery, icon_type, size=28)
    else:
        if title:
            t_surf = font_title.render(title, True, COLOR_TEXT)
            t_rect = t_surf.get_rect(center=(rect.centerx, rect.y + (24 if subtitle else rect.height // 2)))
            surface.blit(t_surf, t_rect)
        if subtitle:
            s_surf = font_sub.render(subtitle, True, (220, 220, 220))
            s_rect = s_surf.get_rect(center=(rect.centerx, rect.y + 50))
            surface.blit(s_surf, s_rect)

def draw_symbol_x(surface, rect):
    margin = 25
    pygame.draw.line(surface, (150, 20, 30), (rect.left + margin + 3, rect.top + margin + 3), (rect.right - margin + 3, rect.bottom - margin + 3), 18)
    pygame.draw.line(surface, (150, 20, 30), (rect.right - margin + 3, rect.top + margin + 3), (rect.left + margin + 3, rect.bottom - margin + 3), 18)
    pygame.draw.line(surface, COLOR_RED, (rect.left + margin, rect.top + margin), (rect.right - margin, rect.bottom - margin), 14)
    pygame.draw.line(surface, COLOR_RED, (rect.right - margin, rect.top + margin), (rect.left + margin, rect.bottom - margin), 14)

def draw_symbol_o(surface, rect):
    center = rect.center
    radius = (rect.width // 2) - 22
    pygame.draw.circle(surface, (20, 120, 60), (center[0] + 3, center[1] + 3), radius, width=16)
    pygame.draw.circle(surface, COLOR_GREEN, center, radius, width=14)


# --- MAIN MODULE ENTRY POINT ---
async def main(screen, clock):
    """Main game function invoked by Game Hub main.py."""
    WIDTH, HEIGHT = screen.get_size()

    # Dynamic Fonts
    font_title = pygame.font.Font(None, 48)
    font_btn_title = pygame.font.Font(None, 36)
    font_btn_sub = pygame.font.Font(None, 22)
    font_status = pygame.font.Font(None, 28)

    # Game State Variables
    state = "MENU_MODE"  # MENU_MODE, MENU_NET_TYPE, MENU_ROOM_ROLE, MENU_PASSWORD, PLAYING
    players_count = 1
    net_type = "LOCAL"
    room_role = "CREATE"

    ICON_NAMES = ["Dog", "Cat", "Rabbit", "Fox", "Panda"]
    selected_pass = []

    peer = None
    connection = None
    net_status = "Ready"
    my_symbol = "X"

    board = [""] * 9
    current_turn = "X"
    winner = None

    # UI Geometry for 800x600 Resolution
    btn_back = pygame.Rect(20, 20, 110, 45)
    btn_opt1 = pygame.Rect(WIDTH // 2 - 200, 190, 400, 80)
    btn_opt2 = pygame.Rect(WIDTH // 2 - 200, 300, 400, 80)
    btn_clear = pygame.Rect(WIDTH // 2 + 160, 210, 90, 65)

    # 3x3 Grid
    grid_rects = []
    board_top_left_x = (WIDTH - 340) // 2
    board_top_left_y = 170
    for row in range(3):
        for col in range(3):
            grid_rects.append(pygame.Rect(
                board_top_left_x + col * 115,
                board_top_left_y + row * 115,
                100, 100
            ))

    # Networking Helpers
    def set_net_status(msg):
        nonlocal net_status
        net_status = msg

    def on_data(data):
        nonlocal board, current_turn, winner
        if data.startswith("MOVE:"):
            idx = int(data.split(":")[1])
            if board[idx] == "" and not winner:
                board[idx] = "O" if my_symbol == "X" else "X"
                check_winner()
                if not winner:
                    current_turn = my_symbol

    def on_connection(conn):
        nonlocal connection, net_status, state
        connection = conn
        net_status = "Friend Joined!"
        conn.on("data", create_proxy(on_data))
        state = "PLAYING"

    def setup_peer_host(room_key):
        nonlocal peer, net_status, my_symbol
        my_symbol = "X"
        host_id = f"ttt-kidroom-{room_key}"
        net_status = "Waiting for friend..."
        if IS_WEB:
            peer = Peer.new(host_id)
            peer.on("connection", create_proxy(on_connection))
            peer.on("error", create_proxy(lambda err: set_net_status("Code taken! Try again.")))
        else:
            state = "PLAYING"

    def setup_peer_guest(room_key):
        nonlocal peer, net_status, my_symbol
        my_symbol = "O"
        target_host_id = f"ttt-kidroom-{room_key}"
        net_status = "Connecting..."
        if IS_WEB:
            peer = Peer.new()
            def on_open(id_val):
                nonlocal connection
                connection = peer.connect(target_host_id)
                connection.on("open", create_proxy(lambda: transition_to_playing()))
                connection.on("data", create_proxy(on_data))
            peer.on("open", create_proxy(on_open))
            peer.on("error", create_proxy(lambda err: set_net_status("Room not found!")))
        else:
            state = "PLAYING"

    def transition_to_playing():
        nonlocal state, net_status
        net_status = "Connected!"
        state = "PLAYING"

    # Game Logic Helpers
    def check_winner():
        nonlocal winner
        lines = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for a, b, c in lines:
            if board[a] and board[a] == board[b] == board[c]:
                winner = board[a]
                return
        if "" not in board:
            winner = "TIE"

    def make_move(idx):
        nonlocal current_turn
        if board[idx] == "" and not winner:
            board[idx] = current_turn
            check_winner()
            if net_type == "REMOTE":
                if connection:
                    connection.send(f"MOVE:{idx}")
                if not winner:
                    current_turn = "O" if my_symbol == "X" else "X"
            else:
                if not winner:
                    current_turn = "O" if current_turn == "X" else "X"
                    if players_count == 1 and current_turn == "O":
                        ai_move()

    def ai_move():
        nonlocal current_turn
        empty_indices = [i for i, val in enumerate(board) if val == ""]
        if empty_indices:
            idx = random.choice(empty_indices)
            board[idx] = "O"
            check_winner()
            if not winner:
                current_turn = "X"

    def cleanup_connections():
        nonlocal connection, peer
        if connection:
            connection.close()
            connection = None

    def reset_game():
        nonlocal board, current_turn, winner, selected_pass, state
        board = [""] * 9
        current_turn = "X"
        winner = None
        selected_pass = []
        state = "MENU_MODE"
        cleanup_connections()

    # Module Loop
    running = True
    while running:
        screen.fill(COLOR_BG)

        # Background Bubbles
        for i in range(8):
            bx = (i * 110 + 30) % WIDTH
            by = (i * 80 + 20) % HEIGHT
            pygame.draw.circle(screen, (40, 46, 56), (bx, by), 20 + (i * 4))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                cleanup_connections()
                return  # Return control to main.py game hub loop

            if event.type == pygame.MOUSEBUTTONDOWN:
                # Top Left Back Button Logic
                if btn_back.collidepoint(event.pos):
                    if state == "MENU_MODE":
                        cleanup_connections()
                        return  # Exit game module back to Hub!
                    else:
                        reset_game()

                # MENU 1: 1 vs 2 PLAYERS
                elif state == "MENU_MODE":
                    if btn_opt1.collidepoint(event.pos):
                        players_count = 1
                        net_type = "LOCAL"
                        state = "PLAYING"
                    elif btn_opt2.collidepoint(event.pos):
                        players_count = 2
                        state = "MENU_NET_TYPE"

                # MENU 2: LOCAL vs REMOTE
                elif state == "MENU_NET_TYPE":
                    if btn_opt1.collidepoint(event.pos):
                        net_type = "LOCAL"
                        state = "PLAYING"
                    elif btn_opt2.collidepoint(event.pos):
                        net_type = "REMOTE"
                        state = "MENU_ROOM_ROLE"

                # MENU 3: CREATE vs JOIN
                elif state == "MENU_ROOM_ROLE":
                    if btn_opt1.collidepoint(event.pos):
                        room_role = "CREATE"
                        selected_pass = []
                        state = "MENU_PASSWORD"
                    elif btn_opt2.collidepoint(event.pos):
                        room_role = "JOIN"
                        selected_pass = []
                        state = "MENU_PASSWORD"

                # MENU 4: VISUAL PASSWORD PICKER
                elif state == "MENU_PASSWORD":
                    for i in range(5):
                        btn_icon = pygame.Rect((WIDTH - 535) // 2 + i * 110, 350, 95, 95)
                        if btn_icon.collidepoint(event.pos) and len(selected_pass) < 3:
                            selected_pass.append(i)
                            if len(selected_pass) == 3:
                                pass_key = "-".join([ICON_NAMES[idx] for idx in selected_pass])
                                if room_role == "CREATE":
                                    setup_peer_host(pass_key)
                                else:
                                    setup_peer_guest(pass_key)
                    if btn_clear.collidepoint(event.pos):
                        selected_pass = []

                # PLAYING STATE
                elif state == "PLAYING":
                    can_move = True
                    if net_type == "REMOTE" and current_turn != my_symbol:
                        can_move = False

                    if can_move and not winner:
                        for idx, rect in enumerate(grid_rects):
                            if rect.collidepoint(event.pos):
                                make_move(idx)

                    if winner:
                        btn_restart = pygame.Rect(WIDTH // 2 - 100, 520, 200, 50)
                        if btn_restart.collidepoint(event.pos):
                            reset_game()

        # --- RENDERING ---
        # Draw Back / Hub Button
        back_label = "< Hub" if state == "MENU_MODE" else "< Menu"
        draw_card_button(screen, btn_back, back_label, "", (70, 80, 95), font_btn_title, font_btn_sub)

        if state == "MENU_MODE":
            t_surf = font_title.render("Kiddie Tic-Tac-Toe", True, COLOR_GOLD)
            screen.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 90)))
            draw_card_button(screen, btn_opt1, "1 Player", "Play vs Computer", COLOR_BLUE, font_btn_title, font_btn_sub)
            draw_card_button(screen, btn_opt2, "2 Players", "Play with a Friend", COLOR_GREEN, font_btn_title, font_btn_sub)

        elif state == "MENU_NET_TYPE":
            t_surf = font_title.render("2 Player Mode", True, COLOR_GOLD)
            screen.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 90)))
            draw_card_button(screen, btn_opt1, "Same Screen", "Share 1 Device", COLOR_BLUE, font_btn_title, font_btn_sub)
            draw_card_button(screen, btn_opt2, "Online Play", "Play across 2 Devices", COLOR_PURPLE, font_btn_title, font_btn_sub)

        elif state == "MENU_ROOM_ROLE":
            t_surf = font_title.render("Online Setup", True, COLOR_GOLD)
            screen.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 90)))
            draw_card_button(screen, btn_opt1, "Create Secret Room", "Make a new code", COLOR_ORANGE, font_btn_title, font_btn_sub)
            draw_card_button(screen, btn_opt2, "Join Secret Room", "Enter friend's code", COLOR_GREEN, font_btn_title, font_btn_sub)

        elif state == "MENU_PASSWORD":
            title_text = "Create 3-Animal Secret Code" if room_role == "CREATE" else "Enter Friend's Code"
            t_surf = font_title.render(title_text, True, COLOR_GOLD)
            screen.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 80)))

            # 3 Code Slots
            slot_start_x = (WIDTH - 295) // 2
            for slot in range(3):
                slot_rect = pygame.Rect(slot_start_x + slot * 105, 200, 85, 85)
                pygame.draw.rect(screen, COLOR_PANEL, slot_rect, border_radius=14)
                pygame.draw.rect(screen, (255, 255, 255), slot_rect, width=3, border_radius=14)
                if slot < len(selected_pass):
                    draw_animal_icon(screen, slot_rect.centerx, slot_rect.centery, selected_pass[slot], size=30)

            draw_card_button(screen, btn_clear, "Clear", "", COLOR_RED, font_btn_title, font_btn_sub)

            # Animal Selection Buttons
            sub_surf = font_status.render("Tap 3 Animals in Order:", True, COLOR_TEXT)
            screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, 315)))

            btn_start_x = (WIDTH - 535) // 2
            for i in range(5):
                btn_icon = pygame.Rect(btn_start_x + i * 110, 350, 95, 95)
                draw_card_button(screen, btn_icon, "", "", COLOR_PANEL, font_btn_title, font_btn_sub, icon_type=i)

            if len(selected_pass) == 3:
                status_surf = font_status.render(net_status, True, COLOR_GREEN)
                screen.blit(status_surf, status_surf.get_rect(center=(WIDTH // 2, 480)))

        elif state == "PLAYING":
            # Header Turn Banner
            if winner:
                msg = "Cat's Game! TIE!" if winner == "TIE" else f"Player {winner} Wins! 🎉"
                banner_color = COLOR_GOLD if winner == "TIE" else (COLOR_RED if winner == "X" else COLOR_GREEN)
            else:
                if net_type == "REMOTE":
                    msg = "Your Turn!" if current_turn == my_symbol else "Waiting for Friend..."
                    banner_color = COLOR_BLUE if current_turn == my_symbol else COLOR_PURPLE
                else:
                    msg = f"Player {current_turn}'s Turn"
                    banner_color = COLOR_RED if current_turn == "X" else COLOR_GREEN

            header_rect = pygame.Rect(WIDTH // 2 - 200, 30, 400, 60)
            draw_card_button(screen, header_rect, msg, "", banner_color, font_btn_title, font_btn_sub)

            # Draw Board Panel Frame
            board_frame = pygame.Rect(board_top_left_x - 15, board_top_left_y - 15, 360, 360)
            pygame.draw.rect(screen, COLOR_PANEL, board_frame, border_radius=20)
            pygame.draw.rect(screen, (70, 78, 90), board_frame, width=4, border_radius=20)

            # Draw Board Cells
            for idx, rect in enumerate(grid_rects):
                pygame.draw.rect(screen, (38, 42, 50), rect, border_radius=12)
                pygame.draw.rect(screen, (80, 90, 105), rect, width=2, border_radius=12)

                if board[idx] == "X":
                    draw_symbol_x(screen, rect)
                elif board[idx] == "O":
                    draw_symbol_o(screen, rect)

            # Play Again Button
            if winner:
                btn_restart = pygame.Rect(WIDTH // 2 - 100, 530, 200, 50)
                draw_card_button(screen, btn_restart, "Play Again", "", COLOR_GREEN, font_btn_title, font_btn_sub)

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)  # Essential for Pygbag async loop!