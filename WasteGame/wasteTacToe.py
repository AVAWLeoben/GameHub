# -*- coding: utf-8 -*-
"""WasteTacToe / GameHub — Firebase online multiplayer, 3-animal room codes.

Version 3.0.1: persistent rooms, verified creation and resilient joining.
The existing children's interface, one-player AI and shared-device play stay intact.
Requires Firebase anonymous sign-in and the shipped RTDB security rules to be enabled.
GameHub calls ``await main(screen, clock)``; importing is side-effect free.
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
ICON_NAMES = ('Dog', 'Cat', 'Rabbit', 'Fox', 'Panda')
PROTOCOL_VERSION = 3

# Firebase Web config is public by design; server-side RTDB rules restrict writes.
FIREBASE_CONFIG = {'apiKey': 'AIzaSyAwnGfsl7YoVcARQ67QD8JSm-e0zIjN8uU', 'authDomain': 'gamehub-1c72c.firebaseapp.com', 'projectId': 'gamehub-1c72c', 'storageBucket': 'gamehub-1c72c.firebasestorage.app', 'messagingSenderId': '857441682920', 'appId': '1:857441682920:web:d91a0bcb0e8da5cb4d905d', 'databaseURL': 'https://gamehub-1c72c-default-rtdb.europe-west1.firebasedatabase.app'}

# Firebase SDK code executes inside the browser. Pygame only exchanges small
# JSON messages with it, avoiding Pyodide JsProxy callback compatibility issues.
FIREBASE_BRIDGE_SCRIPT = r'''(function () {
  'use strict';
  // This is executed via js.eval by the GameHub Pygbag Python module.
  // Every Firebase callback stays on the JavaScript side.
  const prior = window.__ghTttFirebase;
  if (prior && typeof prior.close === 'function') prior.close();

  const config = __FIREBASE_CONFIG__;
  const roomCode = __ROOM_CODE__;
  const role = __ROLE__;
  const s = {
    disposed: false, uid: null, role, roomCode, queue: [], room: null,
    busy: false, ready: false, ref: null, cancelListen: null,
    firebase: null, close: null, move: null,
    restart: null, pending: false
  };
  window.__ghTttFirebase = s;
  window.__ghTttFirebaseEventsJSON = '[]';
  function emit(kind, data) {
    if (s.disposed) return;
    if (s.queue.length >= 96) s.queue.shift();
    s.queue.push({kind, data: data === undefined ? null : data});
  }
  function fail(where, error) {
    const code = String(error && error.code || '').slice(0, 72);
    const message = String(error && error.message || error || 'Unknown error').slice(0, 210);
    emit('error', {where, code, message});
  }
  const due = () => Date.now() + 45 * 60 * 1000;
  const fresh = room => room && typeof room === 'object' &&
      Number(room.expiresAt) > Date.now() && typeof room.hostUid === 'string';
  const initialRoom = uid => ({
    hostUid: uid, board: '---------', turn: 'X', winner: '',
    round: 0, revision: 0, createdAt: Date.now(), expiresAt: due()
  });
  function gameWinner(board) {
    for (const [a,b,c] of [
      [0,1,2], [3,4,5], [6,7,8], [0,3,6], [1,4,7], [2,5,8], [0,4,8], [2,4,6]
    ]) {
      if (board[a] !== '-' && board[a] === board[b] && board[b] === board[c]) return board[a];
    }
    return board.indexOf('-') < 0 ? 'TIE' : '';
  }
  function member(room) {
    return s.role === 'CREATE' ? room.hostUid === s.uid : room.guestUid === s.uid;
  }
  function publish(room) {
    if (!fresh(room)) {
      s.ready = false;
      emit('lost', 'Room closed or expired. Go back to create/join.');
      return;
    }
    if (!member(room)) {
      s.ready = false;
      emit('lost', 'Your seat is no longer active. Go back to rejoin.');
      return;
    }
    s.room = room;
    const ready = Boolean(room.hostUid && room.guestUid);
    s.ready = ready;
    emit('state', {
      board: room.board, turn: room.turn, winner: room.winner,
      round: room.round, revision: room.revision, ready,
      role: s.role
    });
  }
  s.close = function () {
    if (s.disposed) return;
    s.disposed = true;
    try { if (s.cancelListen) s.cancelListen(); } catch (_) {}
    s.cancelListen = null;
    // End the old room only if the current user still owns that seat.
    // The transaction check prevents deleting a room reused by someone else.
    if (s.ref && s.uid && s.firebase) {
      const {runTransaction} = s.firebase;
      runTransaction(s.ref, old => {
        if (!old || !member(old)) return;
        if (s.role === 'CREATE') return null;
        return {...old, guestUid: null};
      }, {applyLocally: false}).catch(() => {});
    }
    s.queue.length = 0;
  };
  async function transaction(update) {
    if (s.disposed || !s.ref || !s.firebase || s.busy) return;
    s.busy = true;
    try {
      const result = await s.firebase.runTransaction(s.ref, old => {
        if (!fresh(old) || !member(old) || !old.guestUid) return;
        return update(old);
      }, {applyLocally: false});
      if (!result.committed && !s.disposed) emit('notice', 'Move not accepted. Waiting for board update.');
    } catch (error) { fail('saving move', error); }
    finally { s.busy = false; }
  }
  s.move = function (index) {
    if (!Number.isInteger(index) || index < 0 || index > 8 || !s.ready) return;
    transaction(old => {
      const symbol = s.role === 'CREATE' ? 'X' : 'O';
      if (old.turn !== symbol || old.winner ||
          typeof old.board !== 'string' || old.board.length !== 9 ||
          old.board[index] !== '-') return;
      const board = old.board.slice(0, index) + symbol + old.board.slice(index + 1);
      const winner = gameWinner(board);
      return {...old, board, turn: winner ? old.turn : (symbol === 'X' ? 'O' : 'X'),
          winner, revision: old.revision + 1, expiresAt: due()};
    });
  };
  s.restart = function () {
    if (!s.ready) return;
    transaction(old => {
      if (!old.winner) return;
      return {...old, board: '---------', turn: 'X', winner: '',
          revision: 0, round: old.round + 1, expiresAt: due()};
    });
  };

  (async function start() {
    try {
      emit('status', 'Loading Firebase...');
      const version = '13.0.0';
      const base = `https://www.gstatic.com/firebasejs/${version}/`;
      const [appSdk, authSdk, dbSdk] = await Promise.all([
        import(base + 'firebase-app.js'),
        import(base + 'firebase-auth.js'),
        import(base + 'firebase-database.js')
      ]);
      if (s.disposed) return;
      emit('status', 'Signing in as a guest...');
      const app = appSdk.getApps().find(a => a.name === 'gamehub-ttt-firebase') ||
          appSdk.initializeApp(config, 'gamehub-ttt-firebase');
      const auth = authSdk.getAuth(app);
      // Let Firebase restore an earlier anonymous sign-in if available.
      await auth.authStateReady();
      let user = auth.currentUser;
      if (!user) user = (await authSdk.signInAnonymously(auth)).user;
      if (s.disposed) return;
      s.uid = user.uid;
      s.firebase = dbSdk;
      const database = dbSdk.getDatabase(app, config.databaseURL);
      s.ref = dbSdk.ref(database, 'tttRooms/' + roomCode);
      emit('status', role === 'CREATE' ? 'Creating room...' : 'Looking for room...');
      if (role === 'CREATE') {
        const outcome = await dbSdk.runTransaction(s.ref, old => {
          if (fresh(old)) return;  // never steal a live room
          return initialRoom(s.uid);
        }, {applyLocally: false});
        if (!outcome.committed) {
          throw new Error('Code already in use. Choose another three animals.');
        }
        // Don't claim the room exists until a separate server read confirms it.
        const verify = (await dbSdk.get(s.ref)).val();
        if (!fresh(verify) || verify.hostUid !== s.uid) {
          throw new Error('Room was not saved on the server. Check Database Rules and retry.');
        }
        emit('status', 'Room created on server. Waiting for friend...');
      } else {
        // The host may still be completing anonymous sign-in / room creation.
        // Waiting briefly avoids treating that normal startup race as a failure.
        const end = Date.now() + 20000;
        let joined = false;
        while (!s.disposed && Date.now() < end) {
          let existing;
          try {
            existing = (await dbSdk.get(s.ref)).val();
          } catch (error) {
            // A permissions failure is not a missing room; show the real error.
            fail('reading room', error);
            return;
          }
          if (!fresh(existing)) {
            emit('status', 'Waiting for creator to finish setting up room...');
            await new Promise(resolve => setTimeout(resolve, 1300));
            continue;
          }
          if (existing.hostUid === s.uid) {
            throw new Error('Both devices use the same guest account. Try separate browsers.');
          }
          if (existing.guestUid && existing.guestUid !== s.uid) {
            throw new Error('Room already has two players. Choose a different code.');
          }
          const outcome = await dbSdk.runTransaction(s.ref, old => {
            if (!fresh(old) || old.hostUid === s.uid ||
                (old.guestUid && old.guestUid !== s.uid)) return;
            return {...old, guestUid: s.uid, expiresAt: due()};
          }, {applyLocally: false});
          if (outcome.committed) {
            const confirmed = (await dbSdk.get(s.ref)).val();
            if (fresh(confirmed) && confirmed.guestUid === s.uid) {
              joined = true;
              break;
            }
          }
          emit('status', 'Room changed while joining. Retrying...');
          await new Promise(resolve => setTimeout(resolve, 1300));
        }
        if (s.disposed) return;
        if (!joined) {
          throw new Error('No active room found. On device 1, wait for "Room created on server" before joining.');
        }
        emit('status', 'Joined room on server. Syncing board...');
      }
      if (s.disposed) return;
      // DO NOT use onDisconnect.remove() on the room: mobile/iPad tabs can
      // disconnect briefly while backgrounded, deleting a room before joining.
      // Explicit Back/HOME cleans up seats; abandoned rooms expire automatically.
      s.cancelListen = dbSdk.onValue(s.ref, snap => {
        if (!s.disposed) publish(snap.val());
      }, error => fail('watching room', error));
    } catch (error) { fail('starting online game', error); }
  })();
})();
'''

font_title = font_btn_title = font_btn_sub = font_status = None

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




class FirebaseSession:
    """Browser-owned Firebase session, polled through a JSON event queue."""

    def __init__(self, game):
        self.game = game
        self.role = None
        self.ready = False
        self.closed = False
        self.status = 'Starting Firebase...'
        self.last_error = False

    @staticmethod
    def _browser_eval(script):
        from js import eval as js_eval
        if js_eval is None or not callable(js_eval):
            raise RuntimeError('Pygbag browser JavaScript bridge is unavailable')
        return js_eval(script)

    @staticmethod
    def _js_text(value, default=''):
        if value is None:
            return default
        if isinstance(value, str):
            return value
        try:
            convert = getattr(value, 'to_py', None)
            if convert is not None and callable(convert):
                result = convert()
                if result is not None and result is not value:
                    return str(result)
        except Exception:
            pass
        return str(value)

    def launch(self, role, animals):
        self.role = role
        code = ''.join(str(i) for i in animals)
        if len(code) != 3 or any(c not in '01234' for c in code):
            self.status = 'Invalid animal code'
            return
        try:
            script = (FIREBASE_BRIDGE_SCRIPT
                .replace('__FIREBASE_CONFIG__', json.dumps(FIREBASE_CONFIG))
                .replace('__ROOM_CODE__', json.dumps(code))
                .replace('__ROLE__', json.dumps(role)))
            self._browser_eval(script)
            self.status = 'Signing in to Firebase...'
        except Exception as exc:
            self.status = ('Starting Firebase: ' + type(exc).__name__ + ': ' + str(exc))[:175]

    def stop(self):
        self.closed = True
        self.ready = False
        try:
            self._browser_eval('(function(){const s=window.__ghTttFirebase; '
                'if(s && s.close) s.close(); window.__ghTttFirebase=null;})()')
        except Exception:
            pass

    def poll(self):
        if self.closed:
            return
        try:
            self._browser_eval('''(function(){
                const s=window.__ghTttFirebase;
                window.__ghTttFirebaseEventsJSON=JSON.stringify(
                  s && !s.disposed ? s.queue.splice(0,96) : []);
            })()''')
            from js import window
            raw=self._js_text(getattr(window, '__ghTttFirebaseEventsJSON', '[]'), '[]')
            events=json.loads(raw)
            if not isinstance(events, list):
                return
            for e in events:
                if self.closed or not isinstance(e, dict):
                    break
                kind=e.get('kind'); data=e.get('data')
                if kind == 'status' and not self.last_error:
                    self.status = str(data)[:175]
                elif kind == 'notice' and not self.last_error:
                    self.status = str(data)[:175]
                    self.game.waiting_move=False
                elif kind == 'error':
                    self.ready=False
                    self.last_error=True
                    self.game.waiting_move=False
                    where=str((data or {}).get('where', 'Firebase'))
                    code=str((data or {}).get('code', ''))
                    detail=str((data or {}).get('message',''))
                    if 'permission-denied' in code or 'PERMISSION_DENIED' in detail:
                        self.status = 'Permission denied: publish Firebase Database rules.'
                    elif 'auth/operation-not-allowed' in code:
                        self.status = 'Enable Anonymous sign-in in Firebase Authentication.'
                    else:
                        self.status = (where + ': ' + code + ' ' + detail)[:220]
                elif kind == 'lost':
                    self.ready=False
                    self.game.waiting_move=False
                    self.status=str(data)[:200]
                elif kind == 'state' and isinstance(data, dict):
                    self._handle_state(data)
        except Exception as exc:
            self.status=('Reading Firebase events: '+type(exc).__name__+': '+str(exc))[:190]

    def _handle_state(self, data):
        board=data.get('board')
        turn=data.get('turn')
        winner=data.get('winner')
        round_no=data.get('round')
        revision=data.get('revision')
        if not (isinstance(board,str) and len(board)==9 and
                all(c in '-XO' for c in board) and turn in ('X','O') and
                winner in ('','X','O','TIE') and type(round_no) is int and
                round_no>=0 and type(revision) is int and revision>=0):
            self.status='Invalid online board state'
            return
        game=self.game
        new_board=['' if c=='-' else c for c in board]
        # Ignore duplicate / stale snapshots that could arrive due to reconnect.
        if (round_no < game.round_number or
                (round_no==game.round_number and revision < game.revision)):
            return
        game.board=new_board
        game.current_turn=turn
        game.winner=winner if winner else None
        game.round_number=round_no
        game.revision=revision
        game.waiting_move=False
        self.ready=bool(data.get('ready'))
        self.last_error=False
        self.status=('Friend connected! Play together.' if self.ready else
                    ('Waiting for friend...' if self.role=='CREATE' else
                     'Waiting for host...'))

    def _send_action(self, action, index=None):
        if self.closed or not self.ready:
            return False
        try:
            if action=='move':
                script='(function(){const s=window.__ghTttFirebase; if(s && s.move) s.move('+str(int(index))+');})()'
            else:
                script='(function(){const s=window.__ghTttFirebase; if(s && s.restart) s.restart();})()'
            self._browser_eval(script)
            return True
        except Exception as exc:
            self.status=('Saving game: '+str(exc))[:170]
            return False

    def send_move(self, index):
        return self._send_action('move', index)

    def request_restart(self):
        return self._send_action('restart')



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
            my_symbol = 'X' if self.room_role == 'CREATE' else 'O'
            if self.current_turn == my_symbol and not self.waiting_move:
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
            if self.net.request_restart():
                self.net.status = 'Starting new round...'
        else:
            self.new_round()

    def _start_network(self):
        self._close_online()
        self.net = FirebaseSession(self)
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
                    status=('You are X - your move' if self.room_role=='CREATE' else 'You are O - your move')
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
