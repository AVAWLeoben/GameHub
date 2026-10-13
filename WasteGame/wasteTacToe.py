# -*- coding: utf-8 -*-
"""WasteTacToe / GameHub — Firebase online multiplayer, 3-animal room codes.

Version 3.1.1: native-resolution UI; proven Firebase 3.0.2 backend unchanged.
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
  // Wait for old room cleanup before creating another room with the same code.
  // Otherwise a late delete from the prior session can remove the new room.
  const previousClose = prior && typeof prior.close === 'function'
      ? Promise.resolve(prior.close()) : Promise.resolve();

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
  const due = () => Date.now() + 20 * 60 * 1000;
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
    if (s.closePromise) return s.closePromise;
    s.disposed = true;
    try { if (s.cancelListen) s.cancelListen(); } catch (_) {}
    s.cancelListen = null;
    s.queue.length = 0;
    // Don't use a transaction here: an uncached transaction can receive null
    // and abort without ever asking the server to remove the room or seat.
    // The published rules permit host deletion and guest seat removal only.
    if (s.ref && s.uid && s.firebase) {
      s.closePromise = (s.role === 'CREATE'
          ? s.firebase.remove(s.ref)
          : s.firebase.update(s.ref, {guestUid: null})).catch(() => {});
    } else {
      s.closePromise = Promise.resolve();
    }
    return s.closePromise;
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
      await previousClose;
      if (s.disposed) return;
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
        // Never use a transaction that returns undefined on a first null
        // snapshot: Firebase documents that null may only mean uncached data.
        // The rules protect existing rooms against another creator's set().
        const previous = (await dbSdk.get(s.ref)).val();
        if (fresh(previous)) {
          if (previous.hostUid !== s.uid) {
            throw new Error('This animal code already has a room. Try another code.');
          }
          // Recreating your *own* code replaces a leftover test session.
          // An explicit remove is permitted only to the original host UID.
          emit('status', 'Resetting your previous room...');
          await dbSdk.remove(s.ref);
        }
        try {
          await dbSdk.set(s.ref, initialRoom(s.uid));
        } catch (error) {
          if (String(error && error.code || '').includes('permission-denied')) {
            const room = (await dbSdk.get(s.ref)).val();
            if (fresh(room)) {
              throw new Error('This animal code already has a room. Try another code.');
            }
          }
          throw error;
        }
        // Only show success after the Firebase server confirms the new room.
        const verify = (await dbSdk.get(s.ref)).val();
        if (!fresh(verify) || verify.hostUid !== s.uid) {
          throw new Error('Room was not saved on the server. Check Database Rules and retry.');
        }
        emit('status', 'Room created on server (v3.0.2). Waiting for friend...');
      } else {
        const end = Date.now() + 20000;
        let joined = false;
        while (!s.disposed && Date.now() < end) {
          let existing;
          try {
            existing = (await dbSdk.get(s.ref)).val();
          } catch (error) {
            fail('reading room', error);
            return;
          }
          if (!fresh(existing)) {
            emit('status', 'Waiting for creator to finish setting up room...');
            await new Promise(resolve => setTimeout(resolve, 1300));
            continue;
          }
          if (existing.hostUid === s.uid) {
            throw new Error('Both devices share the same guest account. Use separate browsers.');
          }
          if (existing.guestUid && existing.guestUid !== s.uid) {
            throw new Error('Room already has two players. Choose another animal code.');
          }
          if (existing.guestUid !== s.uid) {
            try {
              // Atomic, server-validated seat claim. No transaction updater
              // to abort on an initially uncached null value. Concurrent
              // guests cannot steal seats: the database rules forbid it.
              await dbSdk.update(s.ref, {guestUid: s.uid, expiresAt: due()});
            } catch (error) {
              const code = String(error && error.code || '');
              if (!code.includes('permission-denied')) {
                fail('joining room', error);
                return;
              }
              // Race: another guest joined, the room expired, or the host
              // closed it. Inspect the actual server state once more.
              const current = (await dbSdk.get(s.ref)).val();
              if (fresh(current) && current.guestUid && current.guestUid !== s.uid) {
                throw new Error('Room already has two players. Choose another animal code.');
              }
              if (fresh(current) && !current.guestUid &&
                  current.hostUid === existing.hostUid) {
                fail('joining room', error);  // Rules need checking.
                return;
              }
              emit('status', 'Room changed during setup. Retrying...');
              await new Promise(resolve => setTimeout(resolve, 1300));
              continue;
            }
          }
          const confirmed = (await dbSdk.get(s.ref)).val();
          if (fresh(confirmed) && confirmed.hostUid === existing.hostUid &&
              confirmed.guestUid === s.uid) {
            joined = true;
            break;
          }
          emit('status', 'Room changed during setup. Retrying...');
          await new Promise(resolve => setTimeout(resolve, 1300));
        }
        if (s.disposed) return;
        if (!joined) {
          throw new Error('Room could not be joined. Make sure the creator is waiting and retry.');
        }
        emit('status', 'Joined room on server (v3.0.2). Syncing board...');
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


# --- Pure Pygame presentation; no changes to Firebase room protocol ---
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
                'if(s && s.close) s.close();})()')
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
                    ('Waiting for friend... (v3.0.2)' if self.role=='CREATE' else
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



from pathlib import Path

# Native GameHub surface size. Do not draw a small frame and stretch it to 800x600.
WIDTH, HEIGHT = 800, 600
HOME_RECT = pygame.Rect(10, 10, 100, 100)
BACK_RECT = pygame.Rect(642, 24, 145, 56)
MENU_BTN_1 = pygame.Rect(170, 185, 460, 122)
MENU_BTN_2 = pygame.Rect(170, 338, 460, 122)
CLEAR_RECT = pygame.Rect(620, 207, 164, 64)
ANIMAL_RECTS = [pygame.Rect(72 + n * 132, 336, 120, 148) for n in range(5)]
AGAIN_RECT = pygame.Rect(617, 529, 168, 60)
BOARD_RECTS = [pygame.Rect(240 + c * 110, 169 + r * 110, 100, 100)
               for r in range(3) for c in range(3)]

# Dark background and saturated, distinguishable action buttons.
BG = (20, 34, 54)
DARK = (16, 27, 45)
PANEL = (43, 62, 87)
PANEL_LIGHT = (58, 81, 106)
CREAM = (255, 250, 240)
MUTED = (205, 226, 238)
YELLOW = (255, 216, 97)
SKY = (43, 147, 230)
GREEN = (34, 169, 118)
PURPLE = (126, 88, 216)
ORANGE = (238, 136, 64)
RED = (243, 89, 106)
TURQUOISE = (36, 193, 201)

FONT = {}


def init_fonts():
    """Default pygame font is bundled with Pygbag and stays sharp at 800x600."""
    global FONT
    FONT = {
        'title': pygame.font.Font(None, 62),
        'button': pygame.font.Font(None, 46),
        'banner_small': pygame.font.Font(None, 36),
        'small': pygame.font.Font(None, 26),
        'code': pygame.font.Font(None, 23),
        'status': pygame.font.Font(None, 23),
        'tiny': pygame.font.Font(None, 20),
        'animal_label': pygame.font.Font(None, 17),
        'back': pygame.font.Font(None, 31),
        'mark': pygame.font.Font(None, 108),
        'winner': pygame.font.Font(None, 49),
    }


def t(surface, text, font, color, center=None, topleft=None):
    """Draw sharply at final output size, without text shadow or scaling."""
    im = FONT[font].render(text, True, color)
    rect = im.get_rect()
    if center is not None:
        rect.center = (round(center[0]), round(center[1]))
    else:
        rect.topleft = (round(topleft[0]), round(topleft[1]))
    surface.blit(im, rect)
    return rect


def panel(surface, rect, fill=PANEL, border=PANEL_LIGHT, radius=20, shadow=True):
    if shadow:
        pygame.draw.rect(surface, (10, 20, 32), rect.move(0, 6), border_radius=radius)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 3, border_radius=radius)


def animal_face(surface, x, y, index, scale=1.0):
    """Original, high-contrast animal illustrations at the final screen size."""
    def P(dx, dy): return (int(x + dx * scale), int(y + dy * scale))
    def R(dx, dy, w, h):
        return pygame.Rect(int(x + dx * scale), int(y + dy * scale),
                           max(1, int(w * scale)), max(1, int(h * scale)))
    def oval(c, b): pygame.draw.ellipse(surface, c, R(*b))
    def circle(c, dx, dy, r): pygame.draw.circle(surface, c, P(dx, dy), max(1, int(r * scale)))
    def poly(c, points): pygame.draw.polygon(surface, c, [P(*pt) for pt in points])
    edge = (57, 53, 55)
    pupil = (30, 38, 46)
    cream = (255, 250, 237)
    if index == 0:  # DOG - floppy ears
        oval(edge, (-40, -23, 28, 48)); oval(edge, (12, -23, 28, 48))
        oval((139, 87, 54), (-38, -21, 25, 45)); oval((139, 87, 54), (13, -21, 25, 45))
        circle(edge, 0, 0, 33); circle((219, 168, 103), 0, 0, 30)
        oval((244, 217, 167), (-19, 6, 38, 26))
        circle(pupil, -12, -7, 4); circle(pupil, 12, -7, 4)
        oval(edge, (-5, 7, 10, 8)); pygame.draw.arc(surface, edge, R(-12, 9, 24, 16), 0.15, 3.0, max(2,int(2*scale)))
    elif index == 1:  # CAT - orange triangular ears
        poly(edge, [(-31,-15),(-29,-44),(-5,-27)]); poly(edge,[(31,-15),(29,-44),(5,-27)])
        poly((253,155,57),[(-28,-16),(-25,-37),(-5,-23)])
        poly((253,155,57),[(28,-16),(25,-37),(5,-23)])
        circle(edge,0,0,32); circle((255,174,71),0,0,29)
        circle(pupil,-12,-6,4); circle(pupil,12,-6,4)
        poly((238,93,116),[(-6,9),(6,9),(0,15)])
        for sign in (-1, 1):
            pygame.draw.line(surface, cream, P(sign*13,14), P(sign*33,10), max(1,int(2*scale)))
            pygame.draw.line(surface, cream, P(sign*13,18), P(sign*31,23), max(1,int(2*scale)))
    elif index == 2:  # RABBIT - tall white/pink ears
        oval(edge,(-28,-55,20,49)); oval(edge,(8,-55,20,49))
        oval(cream,(-26,-53,16,46)); oval(cream,(10,-53,16,46))
        oval((255,173,188),(-20,-48,6,33)); oval((255,173,188),(14,-48,6,33))
        circle(edge,0,0,31); circle((247,245,240),0,0,28)
        circle(pupil,-11,-6,4); circle(pupil,11,-6,4)
        circle((255,172,190),-20,9,7); circle((255,172,190),20,9,7)
        poly((251,138,158),[(-4,5),(4,5),(0,11)])
    elif index == 3:  # FOX
        poly(edge,[(-32,-10),(-29,-42),(-3,-23)]); poly(edge,[(32,-10),(29,-42),(3,-23)])
        poly((234,93,45),[(-29,-10),(-26,-36),(-3,-19)])
        poly((234,93,45),[(29,-10),(26,-36),(3,-19)])
        circle(edge,0,0,32); circle((241,110,47),0,0,29)
        poly(cream,[(-29,4),(-5,6),(0,29),(-24,18)])
        poly(cream,[(29,4),(5,6),(0,29),(24,18)])
        circle(pupil,-11,-7,4); circle(pupil,11,-7,4)
        circle(pupil,0,12,5)
    else:  # PANDA
        circle(edge,-22,-25,14); circle(edge,22,-25,14)
        circle(edge,0,0,33); circle(cream,0,0,30)
        oval(edge,(-23,-14,19,23)); oval(edge,(4,-14,19,23))
        circle(cream,-13,-5,3); circle(cream,13,-5,3)
        oval(edge,(-6,9,12,8))
        pygame.draw.arc(surface,edge,R(-10,12,20,14),0.1,3.0,max(1,int(2*scale)))


def pictogram(surface, kind, box, color=CREAM):
    """Large solid high-contrast symbols, no pale circles or squeezed icons."""
    cx, cy = box.center
    thick = 5
    if kind == 'solo':
        pygame.draw.rect(surface, color, (cx-29,cy-21,58,49), border_radius=13)
        pygame.draw.circle(surface, DARK, (cx-13,cy-1), 7)
        pygame.draw.circle(surface, DARK, (cx+13,cy-1), 7)
        pygame.draw.rect(surface, DARK, (cx-12,cy+12,24,4), border_radius=2)
        pygame.draw.line(surface,color,(cx,cy-21),(cx,cy-32),4)
        pygame.draw.circle(surface,YELLOW,(cx,cy-33),6)
    elif kind == 'friends':
        for dx in (-20,20):
            pygame.draw.circle(surface,color,(cx+dx,cy-10),17)
            pygame.draw.arc(surface,color,(cx+dx-22,cy+3,44,33),3.2,6.1,5)
            pygame.draw.circle(surface,DARK,(cx+dx-6,cy-13),3)
            pygame.draw.circle(surface,DARK,(cx+dx+6,cy-13),3)
    elif kind == 'tablet':
        pygame.draw.rect(surface,color,(cx-34,cy-31,68,62),6,border_radius=9)
        pygame.draw.circle(surface,color,(cx,cy+24),3)
        pygame.draw.line(surface,color,(cx-18,cy-6),(cx+18,cy-6),4)
    elif kind == 'online':
        pygame.draw.circle(surface,color,(cx,cy),31,5)
        pygame.draw.ellipse(surface,color,(cx-15,cy-31,30,62),4)
        pygame.draw.line(surface,color,(cx-30,cy),(cx+30,cy),4)
        pygame.draw.line(surface,color,(cx-25,cy-16),(cx+25,cy-16),3)
        pygame.draw.line(surface,color,(cx-25,cy+16),(cx+25,cy+16),3)
    elif kind == 'create':
        pygame.draw.line(surface,color,(cx,cy-26),(cx,cy+26),9)
        pygame.draw.line(surface,color,(cx-26,cy),(cx+26,cy),9)
    elif kind == 'join':
        pygame.draw.rect(surface,color,(cx-32,cy-29,39,58),5,border_radius=6)
        pygame.draw.line(surface,color,(cx-2,cy),(cx+32,cy),7)
        pygame.draw.polygon(surface,color,[(cx+32,cy),(cx+13,cy-16),(cx+13,cy+16)])
    elif kind == 'back':
        pygame.draw.line(surface,color,(cx+12,cy),(cx-12,cy),5)
        pygame.draw.polygon(surface,color,[(cx-16,cy),(cx-2,cy-11),(cx-2,cy+11)])
    elif kind == 'clear':
        pygame.draw.line(surface,color,(cx-13,cy-13),(cx+13,cy+13),5)
        pygame.draw.line(surface,color,(cx+13,cy-13),(cx-13,cy+13),5)
    elif kind == 'again':
        # Simple, bold replay/play triangle with generous padding.
        pygame.draw.polygon(surface,color,[(cx-10,cy-16),(cx+16,cy),(cx-10,cy+16)])


def menu_button(surface, rect, title, kind, fill):
    panel(surface, rect, fill, (249, 250, 250), 22)
    # Icon zone is a saturated, dark rectangle, deliberately NOT a white ellipse.
    ib = pygame.Rect(rect.x+18, rect.y+18, 90, rect.height-36)
    pygame.draw.rect(surface, (21, 47, 68), ib, border_radius=18)
    pictogram(surface, kind, ib, CREAM)
    t(surface,title,'button',CREAM,center=(rect.x+286,rect.centery))


def small_action(surface, rect, name, kind, fill):
    panel(surface,rect,fill,(249,249,242),14)
    ib=pygame.Rect(rect.x+10,rect.y+12,32,rect.height-24)
    pictogram(surface,kind,ib,CREAM)
    t(surface,name,'back',CREAM,center=(rect.x + (rect.width+38)//2,rect.centery))


def load_standard_home_image():
    """Use the same wooden HOME image as other GameHub mini-games."""
    locations=[]
    try:
        locations.append(Path(__file__).resolve().parent/'assets'/'retBut.png')
    except Exception:
        pass
    locations.append(Path(__file__).resolve().parent/'assets'/'wasteTacToe'/'retBut.png')
    locations.append(Path('assets')/'retBut.png')
    for path in locations:
        try:
            image=pygame.image.load(str(path)).convert_alpha()
            return pygame.transform.smoothscale(image,HOME_RECT.size)
        except (OSError,pygame.error):
            pass
    return None


def fallback_home(surface):
    # Only used if the standard asset is absent. Same shape and hit area.
    rect=HOME_RECT.inflate(-4,-4)
    pygame.draw.circle(surface,(133,70,30),rect.center,rect.width//2)
    pygame.draw.circle(surface,(212,139,64),rect.center,rect.width//2-5)
    cx,cy=rect.center
    pygame.draw.polygon(surface,(100,55,30),[(cx-26,cy-3),(cx,cy-27),(cx+26,cy-3)])
    pygame.draw.rect(surface,(100,55,30),(cx-18,cy-3,36,25))
    pygame.draw.rect(surface,(227,177,101),(cx-6,cy+8,12,14))


def wrap_lines(message, font='tiny', max_width=478, max_lines=2):
    message=str(message)
    lines=[]
    for paragraph in message.split('\n'):
        words=paragraph.split()
        line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if line and FONT[font].size(candidate)[0] > max_width:
                lines.append(line)
                line=word
            else:
                line=candidate
        if line: lines.append(line)
    return lines[:max_lines]


class TicTacToeGame:
    GRID_RECTS = BOARD_RECTS

    def __init__(self, screen, clock):
        self.screen=screen
        self.clock=clock
        self.state='MENU_MODE'
        self.players_count=1
        self.net_type='LOCAL'
        self.room_role='CREATE'
        self.selected_pass=[]
        self.board=['']*9
        self.current_turn='X'
        self.winner=None
        self.round_number=0
        self.revision=0
        self.waiting_move=False
        self.net=None
        self.running=True
        self._last_press=(-500,(-1000,-1000),None)
        self.home_image=load_standard_home_image()
        # Direct native-size rendering for standard GameHub 800x600.
        self.native = self.screen.get_size() == (WIDTH,HEIGHT)
        self.view = self.screen if self.native else pygame.Surface((WIDTH,HEIGHT))
        self.viewport=pygame.Rect(0,0,*self.screen.get_size())
        self.background=self._make_background()

    def _make_background(self):
        bg=pygame.Surface((WIDTH,HEIGHT))
        bg.fill(BG)
        for y in range(0,HEIGHT,5):
            q=y//5
            pygame.draw.line(bg,(20+q//22,34+q//13,54+q//16),(0,y),(WIDTH,y),5)
        # Background decorations are muted, not competing with interactive controls.
        for x,y,r in ((30,290,120),(730,110,100),(72,545,90),(715,515,105),(400,570,200)):
            pygame.draw.circle(bg,(28,49,73),(x,y),r)
            pygame.draw.circle(bg,(37,62,83),(x,y),max(5,r-22),3)
        for x,y in ((135,135),(684,183),(112,424),(697,432),(330,110),(480,520),(752,350)):
            pygame.draw.circle(bg,(61,100,121),(x,y),5)
        return bg

    def _close_online(self):
        if self.net is not None:
            self.net.stop()
            self.net=None
        self.waiting_move=False

    def new_round(self):
        self.board=['']*9
        self.current_turn='X'
        self.winner=None
        self.round_number+=1
        self.revision=0
        self.waiting_move=False

    def reset_to_menu(self):
        self._close_online()
        self.state='MENU_MODE'
        self.selected_pass=[]
        self.new_round()

    def back(self):
        if self.state=='MENU_NET_TYPE':
            self.state='MENU_MODE'
        elif self.state=='MENU_ROOM_ROLE':
            self.state='MENU_NET_TYPE'
        elif self.state=='MENU_PASSWORD':
            self.state='MENU_ROOM_ROLE'
            self.selected_pass.clear()
        elif self.state=='PLAYING':
            self.reset_to_menu()
        else:
            self.running=False
        if self.state!='PLAYING':
            self._close_online()

    def game_winner(self):
        for a,b,c in ((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)):
            if self.board[a] and self.board[a]==self.board[b]==self.board[c]:
                return self.board[a]
        return 'TIE' if '' not in self.board else None

    def apply_move(self,index,symbol):
        if (not 0<=index<9 or self.board[index] or
                self.winner is not None or symbol!=self.current_turn):
            return False
        self.board[index]=symbol
        self.winner=self.game_winner()
        if self.winner is None:
            self.current_turn='O' if symbol=='X' else 'X'
        self.revision+=1
        return True

    def click_cell(self,index):
        if self.winner is not None or self.board[index]:
            return
        if self.net_type=='REMOTE':
            if self.net is None or not self.net.ready:
                return
            mine='X' if self.room_role=='CREATE' else 'O'
            if self.current_turn==mine and not self.waiting_move:
                self.waiting_move=True
                if not self.net.send_move(index):
                    self.waiting_move=False
        else:
            sym=self.current_turn
            if self.apply_move(index,sym):
                if self.players_count==1 and self.winner is None and self.current_turn=='O':
                    choices=[i for i,v in enumerate(self.board) if not v]
                    if choices: self.apply_move(random.choice(choices),'O')

    def restart(self):
        if self.net_type=='REMOTE':
            if self.net is None or not self.net.ready or self.winner is None: return
            if self.net.request_restart():
                self.net.status='Starting new round...'
        else:
            self.new_round()

    def _start_network(self):
        self._close_online()
        self.net=FirebaseSession(self)
        self.net.launch(self.room_role,self.selected_pass)
        self.state='PLAYING'
        self.board=['']*9
        self.current_turn='X'
        self.winner=None
        self.round_number=0
        self.revision=0
        self.waiting_move=False

    def _viewport(self):
        sw,sh=self.screen.get_size()
        scale=min(sw/WIDTH,sh/HEIGHT)
        dw=max(1,round(WIDTH*scale)); dh=max(1,round(HEIGHT*scale))
        return pygame.Rect((sw-dw)//2,(sh-dh)//2,dw,dh)

    def scaled_pos(self,event):
        if event.type==pygame.FINGERDOWN:
            sw,sh=self.screen.get_size()
            x,y=event.x*sw,event.y*sh
        else:
            x,y=event.pos
        vp=self._viewport()
        return (int((x-vp.x)*WIDTH/max(vp.width,1)),
                int((y-vp.y)*HEIGHT/max(vp.height,1)))

    def on_press(self,pos,source=None):
        ticks=pygame.time.get_ticks()
        prev_ticks,prev_pos,prev_source=self._last_press
        if (source is not None and prev_source is not None and source!=prev_source
                and ticks-prev_ticks<145 and abs(pos[0]-prev_pos[0])<9
                and abs(pos[1]-prev_pos[1])<9):
            return
        self._last_press=(ticks,pos,source)
        if HOME_RECT.collidepoint(pos):
            self.running=False
            return
        if self.state!='MENU_MODE' and BACK_RECT.collidepoint(pos):
            self.back()
            return
        if self.state=='MENU_MODE':
            if MENU_BTN_1.collidepoint(pos):
                self.reset_to_menu()
                self.players_count=1
                self.net_type='LOCAL'
                self.state='PLAYING'
            elif MENU_BTN_2.collidepoint(pos):
                self.players_count=2
                self.state='MENU_NET_TYPE'
        elif self.state=='MENU_NET_TYPE':
            if MENU_BTN_1.collidepoint(pos):
                self.net_type='LOCAL'
                self.new_round()
                self.state='PLAYING'
            elif MENU_BTN_2.collidepoint(pos):
                self.net_type='REMOTE'
                self.state='MENU_ROOM_ROLE'
        elif self.state=='MENU_ROOM_ROLE':
            if MENU_BTN_1.collidepoint(pos):
                self.room_role='CREATE'
                self.selected_pass=[]
                self.state='MENU_PASSWORD'
            elif MENU_BTN_2.collidepoint(pos):
                self.room_role='JOIN'
                self.selected_pass=[]
                self.state='MENU_PASSWORD'
        elif self.state=='MENU_PASSWORD':
            if CLEAR_RECT.collidepoint(pos):
                self.selected_pass=[]
                return
            for i,rect in enumerate(ANIMAL_RECTS):
                if rect.collidepoint(pos) and len(self.selected_pass)<3:
                    self.selected_pass.append(i)
                    if len(self.selected_pass)==3:
                        self._start_network()
                    break
        elif self.state=='PLAYING':
            if self.winner is not None:
                replay_rect = AGAIN_RECT if self.net_type=='REMOTE' else pygame.Rect(300,529,200,60)
                if replay_rect.collidepoint(pos): self.restart()
            else:
                for i,rect in enumerate(self.GRID_RECTS):
                    if rect.collidepoint(pos):
                        self.click_cell(i)
                        break

    def draw_chrome(self,dst):
        if self.home_image is not None:
            dst.blit(self.home_image,HOME_RECT.topleft)
        else:
            fallback_home(dst)
        if self.state!='MENU_MODE':
            small_action(dst,BACK_RECT,'BACK','back',(71,95,129))

    def draw_title(self,dst,label,subtitle=''):
        t(dst,label,'title',YELLOW,center=(WIDTH//2,86))
        if subtitle:
            t(dst,subtitle,'small',MUTED,center=(WIDTH//2,131))

    def draw_menus(self,dst):
        if self.state=='MENU_MODE':
            self.draw_title(dst,'TIC-TAC-TOE')
            menu_button(dst,MENU_BTN_1,'SOLO','solo',SKY)
            menu_button(dst,MENU_BTN_2,'FRIENDS','friends',GREEN)
        elif self.state=='MENU_NET_TYPE':
            self.draw_title(dst,'TWO PLAYERS')
            menu_button(dst,MENU_BTN_1,'TOGETHER','tablet',SKY)
            menu_button(dst,MENU_BTN_2,'ONLINE','online',PURPLE)
        elif self.state=='MENU_ROOM_ROLE':
            self.draw_title(dst,'ONLINE PLAY')
            menu_button(dst,MENU_BTN_1,'MAKE ROOM','create',ORANGE)
            menu_button(dst,MENU_BTN_2,'JOIN ROOM','join',GREEN)

    def draw_code_selection(self,dst):
        self.draw_title(dst,'PICK 3 ANIMALS')
        # Selected sequence: large faces, good contrast, same visual across devices.
        for i in range(3):
            rect=pygame.Rect(249+i*101,194,90,90)
            panel(dst,rect,(62,83,102),(235,241,238),17,False)
            if i<len(self.selected_pass):
                animal_face(dst,rect.centerx,rect.centery,self.selected_pass[i],1.06)
            else:
                t(dst,str(i+1),'button',(161,186,196),center=rect.center)
        small_action(dst,CLEAR_RECT,'CLEAR','clear',RED)
        # Spacious animal choice cards. Names are secondary to colorful faces.
        for i,rect in enumerate(ANIMAL_RECTS):
            panel(dst,rect,(75,105,132),(219,237,243),18)
            animal_face(dst,rect.centerx,rect.y+60,i,1.08)
            t(dst,ICON_NAMES[i].upper(),'code',CREAM,center=(rect.centerx,rect.bottom-29))
        t(dst,'Same 3 animals, same order','small',MUTED,center=(400,532))

    def draw_online_code(self,dst):
        # Always display code after launching an online game, including waiting.
        if self.net_type!='REMOTE' or len(self.selected_pass)!=3:
            return
        rect=pygame.Rect(598,159,190,158)
        panel(dst,rect,(49,73,92),(250,214,111),17)
        t(dst,'ROOM CODE','code',YELLOW,center=(rect.centerx,rect.y+23))
        for i,idx in enumerate(self.selected_pass):
            x=rect.x+35+i*60
            animal_face(dst,x,rect.y+83,idx,0.75)
            # Small names remain directly under the face.
            t(dst,ICON_NAMES[idx].upper(),'animal_label',CREAM,center=(x,rect.y+134))

    def draw_online_status(self,dst):
        if self.net_type!='REMOTE': return
        rect=pygame.Rect(124,522,478,68)
        panel(dst,rect,(50,73,95),(93,135,157),12,False)
        if self.net is None:
            status='Connecting...'
        elif self.waiting_move:
            status='Sending move...'
        elif self.net.last_error or not self.net.ready:
            status=self.net.status
        elif self.winner is not None:
            status='Game finished'
        else:
            my_symbol='X' if self.room_role=='CREATE' else 'O'
            status='Your turn!' if self.current_turn==my_symbol else 'Friend is playing...'
        lines=wrap_lines(status,'tiny',rect.width-28,3)
        if len(lines)==1:
            t(dst,lines[0],'tiny',YELLOW if self.net is not None and not self.net.ready else CREAM,center=rect.center)
        else:
            for j,line in enumerate(lines):
                t(dst,line,'tiny',YELLOW if self.net is not None and not self.net.ready else CREAM,
                  center=(rect.centerx,rect.y+16+j*20))

    def draw_play(self,dst):
        if self.winner:
            title='TIE GAME!' if self.winner=='TIE' else 'PLAYER '+self.winner+' WINS!'
            title_color=YELLOW if self.winner=='TIE' else (RED if self.winner=='X' else GREEN)
        elif self.net_type=='REMOTE' and (self.net is None or not self.net.ready):
            title='WAITING FOR FRIEND'
            title_color=PURPLE
        elif self.net_type=='REMOTE':
            mine='X' if self.room_role=='CREATE' else 'O'
            title='YOUR TURN!' if mine==self.current_turn else 'FRIEND TURN'
            title_color=SKY if mine==self.current_turn else PURPLE
        else:
            title='PLAYER '+self.current_turn+' TURN'
            title_color=RED if self.current_turn=='X' else GREEN
        banner=pygame.Rect(209,36,382,76)
        panel(dst,banner,title_color,CREAM,17)
        # Fit long status labels inside the banner, even on narrow Pygbag fonts.
        f='winner' if self.winner else 'button'
        if FONT[f].size(title)[0] > banner.width-28:
            f='banner_small'
        if FONT[f].size(title)[0] > banner.width-28:
            f='status'
        t(dst,title,f,CREAM,center=banner.center)

        board=pygame.Rect(219,150,362,362)
        panel(dst,board,(53,69,94),(146,176,185),22)
        for i,rect in enumerate(self.GRID_RECTS):
            pygame.draw.rect(dst,(29,46,67),rect,border_radius=16)
            pygame.draw.rect(dst,(123,155,173),rect,2,border_radius=16)
            if self.board[i]=='X':
                t(dst,'X','mark',RED,center=rect.center)
            elif self.board[i]=='O':
                t(dst,'O','mark',(73,216,152),center=rect.center)
        self.draw_online_code(dst)
        self.draw_online_status(dst)
        if self.winner is not None:
            if self.net_type=='REMOTE':
                rect=AGAIN_RECT
            else:
                rect=pygame.Rect(300,529,200,60)
            small_action(dst,rect,'AGAIN','again',GREEN)

    def draw(self):
        dst=self.view
        dst.blit(self.background,(0,0))
        if self.state in ('MENU_MODE','MENU_NET_TYPE','MENU_ROOM_ROLE'):
            self.draw_menus(dst)
        elif self.state=='MENU_PASSWORD':
            self.draw_code_selection(dst)
        elif self.state=='PLAYING':
            self.draw_play(dst)
        self.draw_chrome(dst)
        if not self.native:
            self.screen.fill(DARK)
            vp=self._viewport()
            if vp.size==(WIDTH,HEIGHT):
                self.screen.blit(dst,vp.topleft)
            else:
                # Only fallback for unexpected non-800x600 screens.
                scaled=pygame.transform.scale(dst,vp.size)
                self.screen.blit(scaled,vp.topleft)

    async def run(self):
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type==pygame.QUIT:
                        self.running=False
                    elif event.type==pygame.MOUSEBUTTONDOWN and getattr(event,'button',1)==1:
                        self.on_press(self.scaled_pos(event),event.type)
                    elif event.type==pygame.FINGERDOWN:
                        self.on_press(self.scaled_pos(event),event.type)
                if self.net is not None:
                    self.net.poll()
                self.draw()
                pygame.display.flip()
                self.clock.tick(60)
                await asyncio.sleep(0)
        finally:
            self._close_online()


async def main(screen=None,clock=None):
    """GameHub: ``await main(shared_screen, shared_clock)``."""
    if not pygame.get_init(): pygame.init()
    if not pygame.font.get_init(): pygame.font.init()
    if screen is None:
        screen=pygame.display.set_mode((WIDTH,HEIGHT))
    if clock is None:
        clock=pygame.time.Clock()
    init_fonts()
    game=TicTacToeGame(screen,clock)
    await game.run()


if __name__=='__main__':
    asyncio.run(main())
