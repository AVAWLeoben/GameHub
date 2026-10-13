# -*- coding: utf-8 -*-
"""Kiddie Tic-Tac-Toe for GameHub (Pygame-ce / Pygbag).

One-screen kids' UI, solo AI, local two-player, and browser-only PeerJS rooms.
Version 2.1.4 fixes PeerJS detection, local-first loading, and load diagnostics.

Integration: GameHub calls ``await main(screen, clock)``.
Importing this module has no side effects. Returning from main() restores GameHub.
"""

import asyncio
import json
import random
import pygame

WIDTH, HEIGHT = 640, 520
COLOR_BG = (33, 37, 41)
COLOR_PANEL = (49, 54, 63)
COLOR_TEXT = (248, 249, 250)
COLOR_GOLD = (255, 193, 7)
COLOR_RED = (255, 71, 87)
COLOR_GREEN = (46, 213, 115)
COLOR_BLUE = (30, 144, 255)
COLOR_PURPLE = (155, 89, 182)
COLOR_ORANGE = (255, 127, 80)
ICON_NAMES = ("Dog", "Cat", "Rabbit", "Fox", "Panda")

# The build preloads the same-origin library before Pygbag runs. If that
# preload is missing/cached, try the site's own copy and then two CDN backups.
# Internet/WebRTC access is still required for the PeerJS signaling service.
PEERJS_URLS = (
    "vendor/peerjs-1.5.4.min.js",
    "https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/peerjs/1.5.4/peerjs.min.js",
)
PEERJS_SCRIPT_ID = "gamehub-tictactoe-peerjs"
PROTOCOL_VERSION = 2
CONNECTION_TIMEOUT = 24.0

# Created by the game entry point, not at import time.
font_title = None
font_btn_title = None
font_btn_sub = None
font_status = None


def init_fonts():
    global font_title, font_btn_title, font_btn_sub, font_status
    font_title = pygame.font.Font(None, 44)
    font_btn_title = pygame.font.Font(None, 32)
    font_btn_sub = pygame.font.Font(None, 20)
    font_status = pygame.font.Font(None, 26)


def draw_animal_icon(surface, center_x, center_y, icon_idx, size=30):
    """Draws cute vector animal faces using Pygame primitives."""
    x, y = center_x, center_y

    if icon_idx == 0:  # DOG
        # Ears
        pygame.draw.ellipse(surface, (120, 70, 32), (x - size * 0.9, y - size * 0.4, size * 0.6, size * 0.9))
        pygame.draw.ellipse(surface, (120, 70, 32), (x + size * 0.3, y - size * 0.4, size * 0.6, size * 0.9))
        # Face
        pygame.draw.circle(surface, (200, 135, 80), (x, y), size * 0.7)
        # Muzzle
        pygame.draw.ellipse(surface, (245, 230, 210), (x - size * 0.35, y - size * 0.1, size * 0.7, size * 0.5))
        # Eyes & Nose
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.25, y - size * 0.2), size * 0.1)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.25, y - size * 0.2), size * 0.1)
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.15, y - size * 0.05, size * 0.3, size * 0.2))

    elif icon_idx == 1:  # CAT
        # Ears
        pygame.draw.polygon(surface, (240, 140, 40), [(x - size * 0.7, y - size * 0.2), (x - size * 0.4, y - size * 0.8), (x - size * 0.1, y - size * 0.4)])
        pygame.draw.polygon(surface, (240, 140, 40), [(x + size * 0.1, y - size * 0.4), (x + size * 0.4, y - size * 0.8), (x + size * 0.7, y - size * 0.2)])
        # Face
        pygame.draw.circle(surface, (255, 165, 50), (x, y), size * 0.65)
        # Eyes & Nose
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.25, y - size * 0.15), size * 0.09)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.25, y - size * 0.15), size * 0.09)
        pygame.draw.polygon(surface, (255, 105, 180), [(x - size * 0.1, y), (x + size * 0.1, y), (x, y + size * 0.12)])

    elif icon_idx == 2:  # RABBIT
        # Long Ears
        pygame.draw.ellipse(surface, (240, 240, 240), (x - size * 0.45, y - size * 1.1, size * 0.35, size * 0.9))
        pygame.draw.ellipse(surface, (240, 240, 240), (x + size * 0.1, y - size * 1.1, size * 0.35, size * 0.9))
        pygame.draw.ellipse(surface, (255, 182, 193), (x - size * 0.35, y - size * 0.95, size * 0.18, size * 0.65))
        pygame.draw.ellipse(surface, (255, 182, 193), (x + size * 0.18, y - size * 0.95, size * 0.18, size * 0.65))
        # Face
        pygame.draw.circle(surface, (245, 245, 245), (x, y), size * 0.65)
        # Eyes & Cheeks
        pygame.draw.circle(surface, (30, 30, 30), (x - size * 0.25, y - size * 0.1), size * 0.09)
        pygame.draw.circle(surface, (30, 30, 30), (x + size * 0.25, y - size * 0.1), size * 0.09)
        pygame.draw.circle(surface, (255, 182, 193), (x - size * 0.4, y + size * 0.1), size * 0.12)
        pygame.draw.circle(surface, (255, 182, 193), (x + size * 0.4, y + size * 0.1), size * 0.12)

    elif icon_idx == 3:  # FOX
        # Ears
        pygame.draw.polygon(surface, (210, 75, 25), [(x - size * 0.75, y - size * 0.2), (x - size * 0.45, y - size * 0.85), (x - size * 0.1, y - size * 0.3)])
        pygame.draw.polygon(surface, (210, 75, 25), [(x + size * 0.1, y - size * 0.3), (x + size * 0.45, y - size * 0.85), (x + size * 0.75, y - size * 0.2)])
        # Face Body
        pygame.draw.circle(surface, (230, 90, 35), (x, y), size * 0.65)
        # White Cheeks
        pygame.draw.polygon(surface, (250, 250, 250), [(x - size * 0.65, y), (x, y + size * 0.65), (x, y - size * 0.1)])
        pygame.draw.polygon(surface, (250, 250, 250), [(x + size * 0.65, y), (x, y + size * 0.65), (x, y - size * 0.1)])
        # Eyes & Nose
        pygame.draw.circle(surface, (20, 20, 20), (x - size * 0.28, y - size * 0.1), size * 0.08)
        pygame.draw.circle(surface, (20, 20, 20), (x + size * 0.28, y - size * 0.1), size * 0.08)
        pygame.draw.circle(surface, (10, 10, 10), (x, y + size * 0.35), size * 0.12)

    elif icon_idx == 4:  # PANDA
        # Ears
        pygame.draw.circle(surface, (30, 30, 30), (x - size * 0.5, y - size * 0.5), size * 0.25)
        pygame.draw.circle(surface, (30, 30, 30), (x + size * 0.5, y - size * 0.5), size * 0.25)
        # Face
        pygame.draw.circle(surface, (245, 245, 245), (x, y), size * 0.65)
        # Eye Patches
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.42, y - size * 0.22, size * 0.3, size * 0.38))
        pygame.draw.ellipse(surface, (30, 30, 30), (x + size * 0.12, y - size * 0.22, size * 0.3, size * 0.38))
        # Eyes & Nose
        pygame.draw.circle(surface, (255, 255, 255), (x - size * 0.26, y - size * 0.08), size * 0.06)
        pygame.draw.circle(surface, (255, 255, 255), (x + size * 0.26, y - size * 0.08), size * 0.06)
        pygame.draw.ellipse(surface, (30, 30, 30), (x - size * 0.15, y + size * 0.1, size * 0.3, size * 0.2))

def draw_card_button(surface, rect, title, subtitle, main_color, icon_type=None):
    """Renders a tactile, chunky 3D-styled button with a drop shadow."""
    # 1. Drop Shadow
    shadow_rect = pygame.Rect(rect.x, rect.y + 6, rect.width, rect.height)
    pygame.draw.rect(surface, (20, 22, 26), shadow_rect, border_radius=16)

    # 2. Main Button Body
    pygame.draw.rect(surface, main_color, rect, border_radius=16)

    # 3. Top Gloss/Highlight
    highlight_rect = pygame.Rect(rect.x + 4, rect.y + 4, rect.width - 8, rect.height // 2 - 2)
    overlay = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (255, 255, 255, 45), overlay.get_rect(), border_top_left_radius=12, border_top_right_radius=12)
    surface.blit(overlay, highlight_rect.topleft)

    # 4. White Border Frame
    pygame.draw.rect(surface, (255, 255, 255), rect, width=3, border_radius=16)

    # 5. Text & Icons
    if icon_type is not None:
        draw_animal_icon(surface, rect.x + 45, rect.centery, icon_type, size=24)
        t_surf = font_btn_title.render(title, True, COLOR_TEXT)
        surface.blit(t_surf, (rect.x + 85, rect.y + (12 if subtitle else 18)))
        if subtitle:
            s_surf = font_btn_sub.render(subtitle, True, (220, 220, 220))
            surface.blit(s_surf, (rect.x + 85, rect.y + 40))
    else:
        t_surf = font_btn_title.render(title, True, COLOR_TEXT)
        t_rect = t_surf.get_rect(center=(rect.centerx, rect.y + (22 if subtitle else rect.height // 2)))
        surface.blit(t_surf, t_rect)
        if subtitle:
            s_surf = font_btn_sub.render(subtitle, True, (220, 220, 220))
            s_rect = s_surf.get_rect(center=(rect.centerx, rect.y + 45))
            surface.blit(s_surf, s_rect)

def draw_symbol_x(surface, rect):
    """Draws a stylized bold rounded 'X'."""
    margin = 22
    color_shadow = (150, 20, 30)
    # Shadow offset
    pygame.draw.line(surface, color_shadow, (rect.left + margin + 3, rect.top + margin + 3), (rect.right - margin + 3, rect.bottom - margin + 3), 16)
    pygame.draw.line(surface, color_shadow, (rect.right - margin + 3, rect.top + margin + 3), (rect.left + margin + 3, rect.bottom - margin + 3), 16)
    # Main line
    pygame.draw.line(surface, COLOR_RED, (rect.left + margin, rect.top + margin), (rect.right - margin, rect.bottom - margin), 14)
    pygame.draw.line(surface, COLOR_RED, (rect.right - margin, rect.top + margin), (rect.left + margin, rect.bottom - margin), 14)

def draw_symbol_o(surface, rect):
    """Draws a stylized bold rounded 'O'."""
    center = rect.center
    radius = (rect.width // 2) - 20
    # Shadow
    pygame.draw.circle(surface, (20, 120, 60), (center[0] + 3, center[1] + 3), radius, width=14)
    # Main ring
    pygame.draw.circle(surface, COLOR_GREEN, center, radius, width=12)


class PeerSession:
    """Host-authoritative PeerJS networking with explicit proxy lifetimes."""

    def __init__(self, game):
        self.game = game
        self.closed = False
        self.role = None
        self.room_id = None
        self.peer = None
        self.connection = None
        self.ready = False
        self.proxies = []
        self.job = None
        self.status = "Ready"
        self._connect_started = None
        self._signaling_started = None
        self._ever_connected = False
        self._timeout_reported = False

    def stop(self):
        self.closed = True
        self.ready = False
        if self.job and not self.job.done():
            self.job.cancel()
        self.job = None
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
        if self.peer is not None:
            try:
                self.peer.destroy()
            except Exception:
                pass
            self.peer = None
        for proxy in self.proxies:
            try:
                proxy.destroy()
            except Exception:
                pass
        self.proxies.clear()

    def _listen(self, emitter, name, handler):
        """Keep each Pyodide callback alive until the room closes."""
        try:
            from pyodide.ffi import create_proxy
        except (ImportError, AttributeError) as exc:
            raise RuntimeError('Pyodide callback bridge unavailable') from exc
        if not callable(create_proxy):
            raise RuntimeError('Pyodide create_proxy is not callable')
        proxy = create_proxy(handler)
        self.proxies.append(proxy)
        # Calling a missing JS event method can otherwise surface only as
        # the unhelpful 'NoneType object is not callable' in the game UI.
        callback_registration = getattr(emitter, 'on', None)
        if callback_registration is None or not callable(callback_registration):
            raise RuntimeError('PeerJS listener API missing: ' + name)
        callback_registration(name, proxy)

    @staticmethod
    def _browser_eval(source):
        """Execute simple JavaScript via Pyodide's built-in browser bridge.

        PeerJS exposes a JS *constructor*. Constructing it inside JavaScript
        avoids ambiguous access to a JsProxy ``.new`` attribute in Python.
        """
        from js import eval as js_eval
        if js_eval is None or not callable(js_eval):
            raise RuntimeError('Browser JavaScript eval unavailable')
        return js_eval(source)

    @classmethod
    def _has_peerjs(cls):
        """Return a Python bool; never compare JS Boolean proxies using `is True`."""
        return cls._browser_eval("""(function () {
            return (typeof window !== 'undefined' &&
               ((window.peerjs && typeof window.peerjs.Peer === 'function') ||
                typeof window.Peer === 'function')) ? 'ready' : 'missing';
        })()""") == 'ready'

    @classmethod
    def _start_sdk_loader(cls):
        """Run the script loading and retries entirely on the JS side.

        Pyodide's JavaScript proxies can behave differently from native Python
        values. This script uses browser-native DOM operations and reports a
        plain string status to Python instead of holding JS DOM proxies.
        """
        urls_json = json.dumps(PEERJS_URLS)
        script_id = json.dumps(PEERJS_SCRIPT_ID)
        js_code = """(function() {
          const existing = window.__gamehubTttPeerLoader;
          const ctorReady = () =>
              (typeof window.Peer === 'function') ||
              (window.peerjs != null && typeof window.peerjs.Peer === 'function');
          if (ctorReady()) {
              window.__gamehubTttPeerLoader = {
                  version: 214, status: 'ready', detail: 'PeerJS already present'
              };
              return;
          }
          if (existing && existing.version === 214 && existing.status === 'loading') {
              return;
          }
          const urls = __URLS__;
          const idPrefix = __ID__;
          const state = {
              version: 214, status: 'loading', detail: 'Starting script load',
              index: 0, failures: []
          };
          window.__gamehubTttPeerLoader = state;
          function tryNext() {
              if (ctorReady()) {
                  state.status = 'ready';
                  state.detail = 'PeerJS loaded';
                  return;
              }
              if (state.index >= urls.length) {
                  state.status = 'failed';
                  state.detail = state.failures.join('; ');
                  return;
              }
              const url = urls[state.index];
              const number = state.index++;
              const label = number === 0 ? 'local vendor PeerJS' :
                    (new URL(url, document.baseURI)).hostname;
              let script = document.createElement('script');
              script.id = idPrefix + '-' + number;
              script.src = new URL(url, document.baseURI).href;
              script.async = true;
              state.detail = 'Trying ' + label;
              let finished = false;
              const timer = window.setTimeout(() => finish('timeout'), 8500);
              function finish(reason) {
                  if (finished || state.status !== 'loading') return;
                  finished = true;
                  window.clearTimeout(timer);
                  script.onload = null;
                  script.onerror = null;
                  if (ctorReady()) {
                      state.status = 'ready';
                      state.detail = 'PeerJS loaded from ' + label;
                      return;
                  }
                  state.failures.push(label + ': ' + reason);
                  script.remove();
                  tryNext();
              }
              script.onload = () => finish('loaded but PeerJS constructor missing');
              script.onerror = () => finish('network/script error');
              try {
                  document.head.appendChild(script);
              } catch (error) {
                  finish('DOM error: ' + String(error));
              }
          }
          tryNext();
        })()""".replace('__URLS__', urls_json).replace('__ID__', script_id)
        cls._browser_eval(js_code)

    @classmethod
    def _sdk_status(cls):
        """Return [status, detail] as JSON from JS, not unwrapped proxies."""
        raw = cls._browser_eval("""JSON.stringify(
          window.__gamehubTttPeerLoader ||
          {status:'missing',detail:'loader not started'})""")
        if not isinstance(raw, str):
            raise RuntimeError('Cannot read browser SDK loader state')
        state = json.loads(raw)
        return state.get('status','missing'), state.get('detail','')

    async def _load_sdk(self):
        """Detect preloaded library; try local file then CDNs with diagnostics."""
        try:
            from js import document  # noqa: F401 - confirms this is Pygbag
        except ImportError as exc:
            raise RuntimeError('Online play requires GameHub in a browser') from exc
        if self._has_peerjs():
            return
        self._start_sdk_loader()
        # JS attempts local + 2 x CDN, each with 8.5s timeout.
        for _ in range(290):
            if self.closed:
                raise asyncio.CancelledError()
            if self._has_peerjs():
                return
            status, detail = self._sdk_status()
            if status == 'ready':
                if not self._has_peerjs():
                    raise RuntimeError('Script loaded but constructor not found')
                return
            if status == 'failed':
                raise RuntimeError('PeerJS sources failed: ' + detail)
            if detail:
                self.status = 'Loading online library: ' + detail
            await asyncio.sleep(0.1)
        raise RuntimeError('PeerJS loader exceeded 29 seconds; check build + cache')

    def _construct_peer(self):
        """Construct the PeerJS class in JavaScript, not through JsProxy.new.

        Browser builds of PeerJS support window.peerjs.Peer and window.Peer.
        The result is an actual JS Peer instance with .on/.connect/.destroy.
        """
        factory = self._browser_eval("""(function(isHost, roomId) {
            const ctor = (window.peerjs && window.peerjs.Peer) || window.Peer;
            if (typeof ctor !== 'function') {
                throw new Error('PeerJS constructor unavailable after loading');
            }
            return isHost ? new ctor(roomId) : new ctor();
        })""")
        if factory is None or not callable(factory):
            raise RuntimeError('PeerJS constructor bridge is not callable')
        result = factory(self.role == 'CREATE', self.room_id)
        if result is None:
            raise RuntimeError('PeerJS constructor returned no peer')
        return result

    def poll(self, now=None):
        """Turns a stalled connection into actionable feedback on screen."""
        import time
        if self.closed or self.ready:
            return
        if now is None:
            now = time.monotonic()
        if (self.role == 'JOIN' and self._connect_started is not None
                and not self._timeout_reported
                and now - self._connect_started > CONNECTION_TIMEOUT):
            self._timeout_reported = True
            self.status = 'Timed out. Check code / Wi-Fi; go Back and retry.'
            # A late connection can still succeed; _conn_open clears timeout.
        elif (self._signaling_started is not None and self.peer is not None
              and self._connect_started is None and not self._timeout_reported
              and now - self._signaling_started > CONNECTION_TIMEOUT):
            self._timeout_reported = True
            self.status = 'Room server timeout. Check internet; retry.'

    def launch(self, role, animals):
        self.role = role
        self.room_id = 'gamehub-ttt-v2-' + '-'.join(ICON_NAMES[i].lower() for i in animals)
        self.job = asyncio.create_task(self._start())

    async def _start(self):
        stage = 'loading PeerJS'
        try:
            self.status = 'Online v2.1.4: checking PeerJS...'
            await self._load_sdk()
            if self.closed:
                return
            stage = 'creating PeerJS peer'
            import time
            self._signaling_started = time.monotonic()
            self.peer = self._construct_peer()
            self.status = ('Opening room...' if self.role == 'CREATE'
                           else 'Finding friend...')
            stage = 'attaching PeerJS events'
            self._listen(self.peer, 'open', self._peer_open)
            self._listen(self.peer, 'error', self._peer_error)
            self._listen(self.peer, 'disconnected', self._peer_disconnected)
            if self.role == 'CREATE':
                self._listen(self.peer, 'connection', self._incoming_connection)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self.closed:
                # A named stage and exception class are more diagnostic than
                # "Online unavailable: NoneType object is not callable".
                self.status = (stage + ': ' + type(exc).__name__ +
                               ': ' + str(exc))[:220]

    def _peer_open(self, _peer_id=None):
        if self.closed:
            return
        if self.role == 'CREATE':
            self._signaling_started = None
            self.status = 'Room ready (v2.1.4)! Waiting for friend...'
        else:
            self.status = 'Connecting to friend...'
            try:
                import time
                self._connect_started = time.monotonic()
                conn = self.peer.connect(self.room_id)
                self._attach_connection(conn)
            except Exception as exc:
                self.status = 'Cannot connect: ' + str(exc)[:70]

    def _incoming_connection(self, conn):
        if self.closed:
            try:
                conn.close()
            except Exception:
                pass
            return
        if self.connection is not None:
            try:
                conn.close()
            except Exception:
                pass
            return
        self._attach_connection(conn)

    def _attach_connection(self, conn):
        self.connection = conn
        self._listen(conn, 'open', self._conn_open)
        self._listen(conn, 'data', self._conn_data)
        self._listen(conn, 'close', self._conn_close)
        self._listen(conn, 'error', self._conn_error)

    def _conn_open(self, *_):
        if self.closed:
            return
        self.ready = True
        self.status = 'Friend connected!'
        self._ever_connected = True
        self._timeout_reported = False
        self._signaling_started = None
        self._connect_started = None
        self.game.waiting_move = False
        if self.role == 'CREATE':
            self.send_state()
        else:
            # Avoid a lost initial state when the guest's open event arrives
            # after the host's first state packet. Ask for an authoritative sync.
            self.send({'type': 'hello', 'round': self.game.round_number})

    def _conn_data(self, raw):
        if self.closed:
            return
        try:
            raw = str(raw)
            if len(raw) > 2048:
                return
            message = json.loads(raw)
            if not isinstance(message, dict) or message.get('v') != PROTOCOL_VERSION:
                return
            if self.role == 'CREATE':
                self._host_message(message)
            else:
                self._guest_message(message)
        except (ValueError, TypeError, KeyError):
            return

    def _host_message(self, message):
        game = self.game
        if message.get('type') == 'hello':
            self.send_state()
            return
        if message.get('round') != game.round_number:
            self.send_state()
            return
        kind = message.get('type')
        if kind == 'move':
            # Only the host mutates authoritative board state; guest is O.
            index = message.get('index')
            if (type(index) is int and 0 <= index < 9 and
                    game.current_turn == 'O' and game.winner is None and
                    game.board[index] == ''):
                game.apply_move(index, 'O')
            self.send_state()  # also acknowledges invalid/stale move
        elif kind == 'restart' and game.winner is not None:
            game.new_round()
            self.send_state()

    def _guest_message(self, message):
        if message.get('type') != 'state':
            return
        board = message.get('board')
        turn = message.get('turn')
        winner = message.get('winner')
        round_no = message.get('round')
        revision = message.get('revision')
        if (not isinstance(board, list) or len(board) != 9 or
                not all(x in ('', 'X', 'O') for x in board) or
                turn not in ('X', 'O') or
                winner not in (None, 'X', 'O', 'TIE') or
                type(round_no) is not int or round_no < 0 or
                type(revision) is not int or revision < 0):
            return
        game = self.game
        if (round_no < game.round_number or
                (round_no == game.round_number and revision < game.revision)):
            return
        game.board = list(board)
        game.current_turn = turn
        game.winner = winner
        game.round_number = round_no
        game.revision = revision
        game.waiting_move = False
        self.status = 'Connected'

    def send(self, payload):
        if not self.ready or self.connection is None:
            return False
        try:
            data = dict(payload)
            data['v'] = PROTOCOL_VERSION
            self.connection.send(json.dumps(data, separators=(',', ':')))
            return True
        except Exception:
            self.ready = False
            self.status = 'Connection lost. Go back to retry.'
            return False

    def send_state(self):
        game = self.game
        return self.send({
            'type': 'state', 'board': game.board,
            'turn': game.current_turn, 'winner': game.winner,
            'round': game.round_number, 'revision': game.revision,
        })

    def send_move(self, index):
        return self.send({'type': 'move', 'index': index,
                          'round': self.game.round_number})

    def request_restart(self):
        return self.send({'type': 'restart',
                          'round': self.game.round_number})

    def _conn_close(self, *_):
        if self.closed:
            return
        self.ready = False
        self.connection = None
        self.game.waiting_move = False
        self.status = ('Friend left. Waiting for friend...' if self.role == 'CREATE'
                       else 'Friend disconnected. Go back to retry.')

    def _conn_error(self, _error=None):
        if not self.closed:
            self.ready = False
            self.status = 'Connection error. Go back to retry.'
            self.game.waiting_move = False

    def _peer_error(self, error=None):
        if self.closed:
            return
        code = str(getattr(error, 'type', ''))
        if code == 'unavailable-id':
            self.status = 'Room already in use. Choose another animal code.'
        elif code == 'peer-unavailable':
            self.status = 'No room yet. Host must open same code first.'
        elif code in ('network', 'server-error', 'socket-error', 'socket-closed'):
            self.status = 'Cannot reach room server. Check network / retry.'
        elif code in ('webrtc', 'browser-incompatible'):
            self.status = 'WebRTC blocked. Try a different browser / network.'
        else:
            self.status = 'Online error: ' + (code or str(error))[:60]
        self.ready = False
        self._timeout_reported = True

    def _peer_disconnected(self, *_):
        if not self.closed:
            self.status = 'Room server disconnected. Go Back and retry.'
            self.ready = False


class TicTacToeGame:
    """Per-entry state; nothing persists when returning to the hub."""

    GRID_RECTS = [pygame.Rect(170 + col*105, 140 + row*105, 95, 95)
                  for row in range(3) for col in range(3)]

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.view = pygame.Surface((WIDTH, HEIGHT))
        self.state = 'MENU_MODE'
        self.players_count = 1
        self.net_type = 'LOCAL'
        self.room_role = 'CREATE'
        self.selected_pass = []
        self.board = ['']*9
        self.current_turn = 'X'
        self.winner = None
        self.round_number = 0
        self.revision = 0
        self.waiting_move = False
        self.net = None
        self.running = True
        self.status_message = ''
        self._last_press = (-500, (-1000, -1000), None)

    def _close_online(self):
        if self.net is not None:
            self.net.stop()
            self.net = None
        self.waiting_move = False

    def new_round(self):
        self.board = [''] * 9
        self.current_turn = 'X'
        self.winner = None
        self.round_number += 1
        self.revision = 0
        self.waiting_move = False

    def reset_to_menu(self):
        self._close_online()
        self.state = 'MENU_MODE'
        self.selected_pass = []
        self.new_round()

    def back(self):
        if self.state == 'MENU_NET_TYPE':
            self.state = 'MENU_MODE'
        elif self.state == 'MENU_ROOM_ROLE':
            self.state = 'MENU_NET_TYPE'
        elif self.state == 'MENU_PASSWORD':
            self.state = 'MENU_ROOM_ROLE'
            self.selected_pass.clear()
        elif self.state == 'PLAYING':
            self.reset_to_menu()
        else:
            self.running = False
        if self.state != 'PLAYING':
            self._close_online()

    def game_winner(self):
        for a,b,c in ((0,1,2),(3,4,5),(6,7,8),(0,3,6),
                      (1,4,7),(2,5,8),(2,4,6),(0,4,8)):
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return 'TIE' if '' not in self.board else None

    def apply_move(self, index, symbol):
        if (not 0 <= index < 9 or self.board[index] or
                self.winner is not None or symbol != self.current_turn):
            return False
        self.board[index] = symbol
        self.winner = self.game_winner()
        if self.winner is None:
            self.current_turn = 'O' if symbol == 'X' else 'X'
        self.revision += 1
        return True

    def click_cell(self, index):
        if self.winner is not None or self.board[index]:
            return
        if self.net_type == 'REMOTE':
            if self.net is None or not self.net.ready:
                return
            if self.room_role == 'CREATE':
                if self.current_turn == 'X' and self.apply_move(index, 'X'):
                    self.net.send_state()
            else:
                if self.current_turn == 'O' and not self.waiting_move:
                    self.waiting_move = True
                    if not self.net.send_move(index):
                        self.waiting_move = False
        else:
            symbol = self.current_turn
            if self.apply_move(index, symbol):
                if (self.players_count == 1 and self.winner is None and
                        self.current_turn == 'O'):
                    choices = [i for i,x in enumerate(self.board) if not x]
                    if choices:
                        self.apply_move(random.choice(choices), 'O')

    def restart(self):
        if self.net_type == 'REMOTE':
            if self.net is None or not self.net.ready or self.winner is None:
                return
            if self.room_role == 'CREATE':
                self.new_round()
                self.net.send_state()
            else:
                self.net.request_restart()
                self.net.status = 'Waiting for a new round...'
        else:
            self.new_round()

    def _start_network(self):
        self._close_online()
        self.net = PeerSession(self)
        self.net.launch(self.room_role, self.selected_pass)
        self.state = 'PLAYING'
        self.board = ['']*9
        self.current_turn = 'X'
        self.winner = None
        self.round_number = 0
        self.revision = 0
        self.waiting_move = False

    def scaled_pos(self, event):
        if event.type == pygame.FINGERDOWN:
            return (int(event.x*WIDTH), int(event.y*HEIGHT))
        x,y=event.pos
        width,height=self.screen.get_size()
        return (int(x*WIDTH/max(width,1)), int(y*HEIGHT/max(height,1)))

    def on_press(self, pos, source=None):
        # Ignore mouse + finger duplicates, but allow rapid repeated taps on the
        # same animal (e.g. Dog-Dog-Dog as a room code).
        ticks = pygame.time.get_ticks()
        prev_ticks, prev_pos, prev_source = self._last_press
        if (source is not None and prev_source is not None and source != prev_source and
                ticks-prev_ticks < 145 and
                abs(pos[0]-prev_pos[0]) < 9 and abs(pos[1]-prev_pos[1]) < 9):
            return
        self._last_press = (ticks,pos,source)
        if pygame.Rect(527,15,95,48).collidepoint(pos):
            self.running = False
            return
        if self.state != 'MENU_MODE' and pygame.Rect(17,15,105,48).collidepoint(pos):
            self.back()
            return
        opt1=pygame.Rect(120,170,400,75)
        opt2=pygame.Rect(120,275,400,75)
        if self.state == 'MENU_MODE':
            if opt1.collidepoint(pos):
                self.reset_to_menu()
                self.players_count=1
                self.net_type='LOCAL'
                self.state='PLAYING'
            elif opt2.collidepoint(pos):
                self.players_count=2
                self.state='MENU_NET_TYPE'
        elif self.state == 'MENU_NET_TYPE':
            if opt1.collidepoint(pos):
                self.net_type='LOCAL'
                self.new_round()
                self.state='PLAYING'
            elif opt2.collidepoint(pos):
                self.net_type='REMOTE'
                self.state='MENU_ROOM_ROLE'
        elif self.state == 'MENU_ROOM_ROLE':
            if opt1.collidepoint(pos):
                self.room_role='CREATE'
                self.selected_pass=[]
                self.state='MENU_PASSWORD'
            elif opt2.collidepoint(pos):
                self.room_role='JOIN'
                self.selected_pass=[]
                self.state='MENU_PASSWORD'
        elif self.state == 'MENU_PASSWORD':
            if pygame.Rect(490,185,90,60).collidepoint(pos):
                self.selected_pass=[]
                return
            for i in range(len(ICON_NAMES)):
                rect=pygame.Rect(55+i*108, 290, 92,95)
                if rect.collidepoint(pos) and len(self.selected_pass)<3:
                    self.selected_pass.append(i)
                    if len(self.selected_pass)==3:
                        self._start_network()
                    break
        elif self.state == 'PLAYING':
            if self.winner is not None and pygame.Rect(220,460,200,50).collidepoint(pos):
                self.restart()
            elif self.winner is None:
                for index,rect in enumerate(self.GRID_RECTS):
                    if rect.collidepoint(pos):
                        self.click_cell(index)
                        break

    def draw(self):
        surf=self.view
        surf.fill(COLOR_BG)
        for i in range(6):
            bx=(i*120+40)%WIDTH;by=(i*90+30)%HEIGHT
            pygame.draw.circle(surf,(40,46,56),(bx,by),25+i*5)

        # Always-visible return to GameHub, even on the first screen.
        pygame.draw.rect(surf, (22,25,32),pygame.Rect(530,19,92,41),border_radius=12)
        pygame.draw.rect(surf,COLOR_GOLD,pygame.Rect(530,19,92,41),width=2,border_radius=12)
        surf.blit(font_btn_sub.render('HOME',True,COLOR_TEXT),(547,31))
        if self.state != 'MENU_MODE':
            draw_card_button(surf,pygame.Rect(17,19,105,41),'< Back','',(70,80,95))

        opt1=pygame.Rect(120,170,400,75)
        opt2=pygame.Rect(120,275,400,75)
        if self.state=='MENU_MODE':
            t=font_title.render('Kiddie Tic-Tac-Toe',True,COLOR_GOLD)
            surf.blit(t,t.get_rect(center=(WIDTH//2,85)))
            draw_card_button(surf,opt1,'1 Player','Play against Computer',COLOR_BLUE)
            draw_card_button(surf,opt2,'2 Players','Play with a Friend',COLOR_GREEN)
        elif self.state=='MENU_NET_TYPE':
            t=font_title.render('2 Player Mode',True,COLOR_GOLD)
            surf.blit(t,t.get_rect(center=(WIDTH//2,85)))
            draw_card_button(surf,opt1,'Same Screen','Share 1 Device',COLOR_BLUE)
            draw_card_button(surf,opt2,'Online Play','Play across 2 Devices',COLOR_PURPLE)
        elif self.state=='MENU_ROOM_ROLE':
            t=font_title.render('Online Setup',True,COLOR_GOLD)
            surf.blit(t,t.get_rect(center=(WIDTH//2,85)))
            draw_card_button(surf,opt1,'Create Secret Room','Make a new code',COLOR_ORANGE)
            draw_card_button(surf,opt2,'Join Secret Room',"Enter friend's code",COLOR_GREEN)
        elif self.state=='MENU_PASSWORD':
            title=('Create Secret Code' if self.room_role=='CREATE' else 'Enter Friend\'s Code')
            t=font_title.render(title,True,COLOR_GOLD)
            surf.blit(t,t.get_rect(center=(WIDTH//2,87)))
            for slot in range(3):
                rect=pygame.Rect(185+slot*95,175,80,80)
                pygame.draw.rect(surf,COLOR_PANEL,rect,border_radius=14)
                pygame.draw.rect(surf,(255,255,255),rect,width=3,border_radius=14)
                if slot<len(self.selected_pass):
                    draw_animal_icon(surf,rect.centerx,rect.centery,self.selected_pass[slot],size=28)
            draw_card_button(surf,pygame.Rect(490,185,90,60),'Clear','',COLOR_RED)
            label=font_status.render('Tap 3 Animals in Order:',True,COLOR_TEXT)
            surf.blit(label,label.get_rect(center=(WIDTH//2,270)))
            for i in range(5):
                draw_card_button(surf,pygame.Rect(55+i*108,290,92,95),'','',COLOR_PANEL,icon_type=i)
            caption=font_btn_sub.render('Use the same animals on both devices.',True,(207,212,220))
            surf.blit(caption, caption.get_rect(center=(WIDTH//2,421)))
        elif self.state=='PLAYING':
            if self.winner is not None:
                msg="Cat's Game! TIE!" if self.winner=='TIE' else f'Player {self.winner} Wins!'
                banner=COLOR_GOLD if self.winner=='TIE' else (COLOR_RED if self.winner=='X' else COLOR_GREEN)
            elif self.net_type=='REMOTE' and (self.net is None or not self.net.ready):
                msg='Online Room'
                banner=COLOR_PURPLE
            elif self.net_type=='REMOTE':
                my_sym='X' if self.room_role=='CREATE' else 'O'
                msg='Your Turn!' if self.current_turn==my_sym else 'Waiting for Friend...'
                banner=COLOR_BLUE if self.current_turn==my_sym else COLOR_PURPLE
            else:
                msg=f'Player {self.current_turn}\'s Turn'
                banner=COLOR_RED if self.current_turn=='X' else COLOR_GREEN
            draw_card_button(surf,pygame.Rect(140,30,360,55),msg,'',banner)
            board_frame=pygame.Rect(155,125,330,330)
            pygame.draw.rect(surf,COLOR_PANEL,board_frame,border_radius=20)
            pygame.draw.rect(surf,(70,78,90),board_frame,width=4,border_radius=20)
            for i,rect in enumerate(self.GRID_RECTS):
                pygame.draw.rect(surf,(38,42,50),rect,border_radius=12)
                pygame.draw.rect(surf,(80,90,105),rect,width=2,border_radius=12)
                if self.board[i]=='X':
                    draw_symbol_x(surf,rect)
                elif self.board[i]=='O':
                    draw_symbol_o(surf,rect)
            if self.winner is not None:
                draw_card_button(surf,pygame.Rect(220,460,200,50),'Play Again','',COLOR_GREEN)
            if self.net_type=='REMOTE':
                # Bottom line: display the connection state, including errors.
                status=(self.net.status if self.net is not None else 'Starting...')
                if self.waiting_move:
                    status='Sending move...'
                if self.net is not None and self.net.ready and not self.waiting_move:
                    status=('You are X (host)' if self.room_role=='CREATE' else 'You are O (guest)')
                # Keep the diagnostic stage visible, including on small iPads.
                # Two lines avoid cutting off errors before the meaningful part.
                color=(COLOR_GOLD if (self.net is not None and not self.net.ready)
                       else COLOR_TEXT)
                words=status.split()
                lines=[]; line=''
                for word in words:
                    trial=(line+' '+word).strip()
                    if line and font_btn_sub.size(trial)[0] > WIDTH-25:
                        lines.append(line)
                        line=word
                    else:
                        line=trial
                if line:
                    lines.append(line)
                for j,chunk in enumerate(lines[:3]):
                    txt=font_btn_sub.render(chunk,True,color)
                    y=(453 if self.winner is None else 420) + j*21
                    surf.blit(txt,txt.get_rect(center=(WIDTH//2,y)))
        width,height=self.screen.get_size()
        if (width,height)==(WIDTH,HEIGHT):
            self.screen.blit(surf,(0,0))
        else:
            self.screen.blit(pygame.transform.smoothscale(surf,(width,height)),(0,0))

    async def run(self):
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type==pygame.QUIT:
                        self.running=False
                    elif event.type==pygame.MOUSEBUTTONDOWN and getattr(event,'button',1)==1:
                        self.on_press(self.scaled_pos(event), event.type)
                    elif event.type==pygame.FINGERDOWN:
                        self.on_press(self.scaled_pos(event), event.type)
                if self.net is not None:
                    self.net.poll()
                self.draw()
                pygame.display.flip()
                self.clock.tick(60)
                await asyncio.sleep(0)
        finally:
            self._close_online()


async def main(screen=None, clock=None):
    """GameHub-compatible entry point. Returns without quitting Pygame."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    if screen is None:
        # Standalone desktop testing only; GameHub already owns its display.
        screen=pygame.display.set_mode((800,600))
    if clock is None:
        clock=pygame.time.Clock()
    init_fonts()
    game=TicTacToeGame(screen,clock)
    await game.run()


if __name__=='__main__':
    asyncio.run(main())
