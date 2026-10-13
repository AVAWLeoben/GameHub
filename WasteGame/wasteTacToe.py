# -*- coding: utf-8 -*-
"""WasteTacToe / GameHub — Firebase online multiplayer, kid-friendly UI polish.

Version 3.1.0
- keeps the working Firebase room logic from 3.0.2
- always shows the 3-animal room code during online play
- replaces text-heavy setup buttons with icon-led buttons
- improves visual clarity with sharper fonts, crisper scaling and cleaner panels

GameHub calls ``await main(screen, clock)``; importing is side-effect free.
"""

import asyncio
import json
import random
import pygame

WIDTH, HEIGHT = 640, 520
COLOR_BG = (33, 37, 41)
COLOR_PANEL = (49, 54, 63)
COLOR_PANEL_DARK = (34, 38, 46)
COLOR_PANEL_LIGHT = (68, 74, 86)
COLOR_TEXT = (248, 249, 250)
COLOR_TEXT_SOFT = (220, 225, 232)
COLOR_GOLD = (255, 193, 7)
COLOR_RED = (255, 71, 87)
COLOR_GREEN = (46, 213, 115)
COLOR_BLUE = (30, 144, 255)
COLOR_PURPLE = (155, 89, 182)
COLOR_ORANGE = (255, 127, 80)
COLOR_TEAL = (66, 194, 194)
COLOR_CREAM = (244, 232, 196)
ICON_NAMES = ('Dog', 'Cat', 'Rabbit', 'Fox', 'Panda')
PROTOCOL_VERSION = 3

FIREBASE_CONFIG = {
    'apiKey': 'AIzaSyAwnGfsl7YoVcARQ67QD8JSm-e0zIjN8uU',
    'authDomain': 'gamehub-1c72c.firebaseapp.com',
    'projectId': 'gamehub-1c72c',
    'storageBucket': 'gamehub-1c72c.firebasestorage.app',
    'messagingSenderId': '857441682920',
    'appId': '1:857441682920:web:d91a0bcb0e8da5cb4d905d',
    'databaseURL': 'https://gamehub-1c72c-default-rtdb.europe-west1.firebasedatabase.app'
}

FIREBASE_BRIDGE_SCRIPT = r'''(function () {
  'use strict';
  const prior = window.__ghTttFirebase;
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
        const previous = (await dbSdk.get(s.ref)).val();
        if (fresh(previous)) {
          if (previous.hostUid !== s.uid) {
            throw new Error('This animal code already has a room. Try another code.');
          }
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
        const verify = (await dbSdk.get(s.ref)).val();
        if (!fresh(verify) || verify.hostUid !== s.uid) {
          throw new Error('Room was not saved on the server. Check Database Rules and retry.');
        }
        emit('status', 'Room created on server (v3.1.0). Waiting for friend...');
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
              await dbSdk.update(s.ref, {guestUid: s.uid, expiresAt: due()});
            } catch (error) {
              const code = String(error && error.code || '');
              if (!code.includes('permission-denied')) {
                fail('joining room', error);
                return;
              }
              const current = (await dbSdk.get(s.ref)).val();
              if (fresh(current) && current.guestUid && current.guestUid !== s.uid) {
                throw new Error('Room already has two players. Choose another animal code.');
              }
              if (fresh(current) && !current.guestUid && current.hostUid === existing.hostUid) {
                fail('joining room', error);
                return;
              }
              emit('status', 'Room changed during setup. Retrying...');
              await new Promise(resolve => setTimeout(resolve, 1300));
              continue;
            }
          }
          const confirmed = (await dbSdk.get(s.ref)).val();
          if (fresh(confirmed) && confirmed.hostUid === existing.hostUid && confirmed.guestUid === s.uid) {
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
        emit('status', 'Joined room on server (v3.1.0). Syncing board...');
      }
      if (s.disposed) return;
      s.cancelListen = dbSdk.onValue(s.ref, snap => {
        if (!s.disposed) publish(snap.val());
      }, error => fail('watching room', error));
    } catch (error) { fail('starting online game', error); }
  })();
})();
'''

font_title = None
font_button = None
font_small = None
font_status = None
font_badge = None
font_tiny = None


def init_fonts():
    global font_title, font_button, font_small, font_status, font_badge, font_tiny
    font_title = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 38, bold=True)
    font_button = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 26, bold=True)
    font_small = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 18, bold=False)
    font_status = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 22, bold=True)
    font_badge = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 16, bold=True)
    font_tiny = pygame.font.SysFont('arialroundedmtbold,arial,dejavusans', 14, bold=False)


def shadow_text(surface, font, text, color, pos, center=False, shadow=(0, 0, 0), soff=(2, 2)):
    sh = font.render(text, True, shadow)
    tx = font.render(text, True, color)
    rect = tx.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    srect = rect.move(*soff)
    surface.blit(sh, srect)
    surface.blit(tx, rect)
    return rect


def draw_background(surface):
    surface.fill(COLOR_BG)
    for i in range(7):
        bx = (i * 101 + 37) % WIDTH
        by = (i * 73 + 33) % HEIGHT
        pygame.draw.circle(surface, (40, 46, 56), (bx, by), 20 + i * 4)
        pygame.draw.circle(surface, (37, 43, 51), ((bx + 160) % WIDTH, (by + 200) % HEIGHT), 12 + i * 3)


def draw_panel(surface, rect, fill=COLOR_PANEL, border=(255, 255, 255), radius=18, shadow=True):
    if shadow:
        shadow_rect = rect.move(0, 5)
        pygame.draw.rect(surface, (17, 19, 24), shadow_rect, border_radius=radius)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    gloss = pygame.Surface((rect.width, max(10, rect.height // 2)), pygame.SRCALPHA)
    pygame.draw.rect(gloss, (255, 255, 255, 32), gloss.get_rect(), border_top_left_radius=radius, border_top_right_radius=radius)
    surface.blit(gloss, (rect.x, rect.y))
    pygame.draw.rect(surface, border, rect, width=3, border_radius=radius)


def draw_animal_icon(surface, center_x, center_y, icon_idx, size=30):
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


def draw_ui_icon(surface, kind, rect, color=COLOR_TEXT):
    cx, cy = rect.center
    w, h = rect.width, rect.height
    if kind == 'solo':
        pygame.draw.circle(surface, color, (cx, cy - 4), 12, 3)
        pygame.draw.arc(surface, color, (cx - 18, cy + 2, 36, 24), 3.3, 6.1, 3)
        pygame.draw.circle(surface, COLOR_GOLD, (cx + 18, cy - 12), 5)
    elif kind == 'friends':
        pygame.draw.circle(surface, color, (cx - 10, cy - 4), 10, 3)
        pygame.draw.circle(surface, color, (cx + 10, cy - 4), 10, 3)
        pygame.draw.arc(surface, color, (cx - 26, cy + 2, 32, 22), 3.3, 6.1, 3)
        pygame.draw.arc(surface, color, (cx - 6, cy + 2, 32, 22), 3.3, 6.1, 3)
    elif kind == 'tablet':
        pygame.draw.rect(surface, color, (cx - 18, cy - 14, 36, 28), 3, border_radius=6)
        pygame.draw.circle(surface, color, (cx, cy + 9), 2)
        pygame.draw.line(surface, color, (cx - 8, cy - 4), (cx + 8, cy - 4), 3)
    elif kind == 'online':
        for rad in (8, 15, 22):
            pygame.draw.arc(surface, color, (cx - rad, cy - rad + 4, rad * 2, rad * 2), 3.7, 5.7, 3)
        pygame.draw.circle(surface, color, (cx, cy + 11), 4)
    elif kind == 'create':
        pygame.draw.circle(surface, color, (cx, cy), 16, 3)
        pygame.draw.line(surface, color, (cx, cy - 10), (cx, cy + 10), 4)
        pygame.draw.line(surface, color, (cx - 10, cy), (cx + 10, cy), 4)
    elif kind == 'join':
        pygame.draw.rect(surface, color, (cx - 19, cy - 13, 20, 26), 3, border_radius=6)
        pygame.draw.polygon(surface, color, [(cx - 2, cy), (cx + 16, cy - 11), (cx + 16, cy - 4), (cx + 24, cy - 4), (cx + 24, cy + 4), (cx + 16, cy + 4), (cx + 16, cy + 11)])
    elif kind == 'clear':
        pygame.draw.rect(surface, color, (cx - 14, cy - 10, 28, 18), 0, border_radius=5)
        pygame.draw.rect(surface, COLOR_RED, (cx - 8, cy - 7, 16, 12), 0, border_radius=3)
    elif kind == 'back':
        pygame.draw.polygon(surface, color, [(cx - 16, cy), (cx + 4, cy - 14), (cx + 4, cy - 6), (cx + 18, cy - 6), (cx + 18, cy + 6), (cx + 4, cy + 6), (cx + 4, cy + 14)])
    elif kind == 'home':
        pygame.draw.polygon(surface, color, [(cx - 14, cy + 2), (cx, cy - 14), (cx + 14, cy + 2)])
        pygame.draw.rect(surface, color, (cx - 10, cy + 2, 20, 14), border_radius=3)
    elif kind == 'play':
        pygame.draw.polygon(surface, color, [(cx - 8, cy - 12), (cx + 12, cy), (cx - 8, cy + 12)])
    elif kind == 'crown':
        pygame.draw.polygon(surface, color, [(cx - 18, cy + 10), (cx - 15, cy - 10), (cx - 4, cy + 1), (cx, cy - 13), (cx + 4, cy + 1), (cx + 15, cy - 10), (cx + 18, cy + 10)])
        pygame.draw.rect(surface, color, (cx - 18, cy + 8, 36, 6))
    elif kind == 'room':
        pygame.draw.rect(surface, color, (cx - 18, cy - 13, 36, 26), 3, border_radius=7)
        pygame.draw.circle(surface, color, (cx - 8, cy), 3)
        pygame.draw.circle(surface, color, (cx + 8, cy), 3)
    elif kind == 'turn_x':
        pygame.draw.line(surface, color, (cx - 12, cy - 12), (cx + 12, cy + 12), 5)
        pygame.draw.line(surface, color, (cx + 12, cy - 12), (cx - 12, cy + 12), 5)
    elif kind == 'turn_o':
        pygame.draw.circle(surface, color, (cx, cy), 14, 5)


def draw_card_button(surface, rect, title, subtitle, main_color, icon=None, animal_icon=None, title_font=None, subtitle_color=COLOR_TEXT_SOFT):
    title_font = title_font or font_button
    draw_panel(surface, rect, fill=main_color, radius=16)
    icon_space = 0
    if icon is not None or animal_icon is not None:
        icon_rect = pygame.Rect(rect.x + 10, rect.y + 10, 52, rect.height - 20)
        bubble = pygame.Rect(icon_rect.x + 3, icon_rect.y + 3, icon_rect.width - 6, icon_rect.height - 6)
        pygame.draw.ellipse(surface, (255, 255, 255, 25), bubble)
        if animal_icon is not None:
            draw_animal_icon(surface, icon_rect.centerx, icon_rect.centery, animal_icon, size=18)
        else:
            draw_ui_icon(surface, icon, icon_rect)
        icon_space = 58
    title_s = title_font.render(title, True, COLOR_TEXT)
    if subtitle:
        subtitle_s = font_small.render(subtitle, True, subtitle_color)
        surface.blit(title_s, (rect.x + 16 + icon_space, rect.y + 14))
        surface.blit(subtitle_s, (rect.x + 16 + icon_space, rect.y + 42))
    else:
        title_rect = title_s.get_rect(midleft=(rect.x + 18 + icon_space, rect.centery))
        if icon_space == 0:
            title_rect = title_s.get_rect(center=rect.center)
        surface.blit(title_s, title_rect)


def draw_symbol_x(surface, rect):
    margin = 22
    pygame.draw.line(surface, (140, 18, 26), (rect.left + margin + 3, rect.top + margin + 3), (rect.right - margin + 3, rect.bottom - margin + 3), 16)
    pygame.draw.line(surface, (140, 18, 26), (rect.right - margin + 3, rect.top + margin + 3), (rect.left + margin + 3, rect.bottom - margin + 3), 16)
    pygame.draw.line(surface, COLOR_RED, (rect.left + margin, rect.top + margin), (rect.right - margin, rect.bottom - margin), 14)
    pygame.draw.line(surface, COLOR_RED, (rect.right - margin, rect.top + margin), (rect.left + margin, rect.bottom - margin), 14)


def draw_symbol_o(surface, rect):
    center = rect.center
    radius = (rect.width // 2) - 20
    pygame.draw.circle(surface, (20, 120, 60), (center[0] + 3, center[1] + 3), radius, width=14)
    pygame.draw.circle(surface, COLOR_GREEN, center, radius, width=12)


class FirebaseSession:
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
            self._browser_eval('(function(){const s=window.__ghTttFirebase; if(s && s.close) s.close();})()')
        except Exception:
            pass

    def poll(self):
        if self.closed:
            return
        try:
            self._browser_eval('''(function(){
                const s=window.__ghTttFirebase;
                window.__ghTttFirebaseEventsJSON=JSON.stringify(s && !s.disposed ? s.queue.splice(0,96) : []);
            })()''')
            from js import window
            raw = self._js_text(getattr(window, '__ghTttFirebaseEventsJSON', '[]'), '[]')
            events = json.loads(raw)
            if not isinstance(events, list):
                return
            for e in events:
                if self.closed or not isinstance(e, dict):
                    break
                kind = e.get('kind')
                data = e.get('data')
                if kind == 'status' and not self.last_error:
                    self.status = str(data)[:175]
                elif kind == 'notice' and not self.last_error:
                    self.status = str(data)[:175]
                    self.game.waiting_move = False
                elif kind == 'error':
                    self.ready = False
                    self.last_error = True
                    self.game.waiting_move = False
                    where = str((data or {}).get('where', 'Firebase'))
                    code = str((data or {}).get('code', ''))
                    detail = str((data or {}).get('message', ''))
                    if 'permission-denied' in code or 'PERMISSION_DENIED' in detail:
                        self.status = 'Permission denied: publish Firebase Database rules.'
                    elif 'auth/operation-not-allowed' in code:
                        self.status = 'Enable Anonymous sign-in in Firebase Authentication.'
                    else:
                        self.status = (where + ': ' + code + ' ' + detail)[:220]
                elif kind == 'lost':
                    self.ready = False
                    self.game.waiting_move = False
                    self.status = str(data)[:200]
                elif kind == 'state' and isinstance(data, dict):
                    self._handle_state(data)
        except Exception as exc:
            self.status = ('Reading Firebase events: ' + type(exc).__name__ + ': ' + str(exc))[:190]

    def _handle_state(self, data):
        board = data.get('board')
        turn = data.get('turn')
        winner = data.get('winner')
        round_no = data.get('round')
        revision = data.get('revision')
        if not (isinstance(board, str) and len(board) == 9 and
                all(c in '-XO' for c in board) and turn in ('X', 'O') and
                winner in ('', 'X', 'O', 'TIE') and type(round_no) is int and
                round_no >= 0 and type(revision) is int and revision >= 0):
            self.status = 'Invalid online board state'
            return
        game = self.game
        new_board = ['' if c == '-' else c for c in board]
        if (round_no < game.round_number or
                (round_no == game.round_number and revision < game.revision)):
            return
        game.board = new_board
        game.current_turn = turn
        game.winner = winner if winner else None
        game.round_number = round_no
        game.revision = revision
        game.waiting_move = False
        self.ready = bool(data.get('ready'))
        self.last_error = False
        self.status = ('Friend connected! Play together.' if self.ready else
                       ('Waiting for friend... (v3.1.0)' if self.role == 'CREATE' else 'Waiting for host...'))

    def _send_action(self, action, index=None):
        if self.closed or not self.ready:
            return False
        try:
            if action == 'move':
                script = '(function(){const s=window.__ghTttFirebase; if(s && s.move) s.move(' + str(int(index)) + ');})()'
            else:
                script = '(function(){const s=window.__ghTttFirebase; if(s && s.restart) s.restart();})()'
            self._browser_eval(script)
            return True
        except Exception as exc:
            self.status = ('Saving game: ' + str(exc))[:170]
            return False

    def send_move(self, index):
        return self._send_action('move', index)

    def request_restart(self):
        return self._send_action('restart')


class TicTacToeGame:
    GRID_RECTS = [pygame.Rect(170 + col * 105, 140 + row * 105, 95, 95)
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
        self.board = [''] * 9
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
        for a, b, c in ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
                        (1, 4, 7), (2, 5, 8), (2, 4, 6), (0, 4, 8)):
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
                if self.players_count == 1 and self.winner is None and self.current_turn == 'O':
                    choices = [i for i, x in enumerate(self.board) if not x]
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
        self.board = [''] * 9
        self.current_turn = 'X'
        self.winner = None
        self.round_number = 0
        self.revision = 0
        self.waiting_move = False

    def scaled_pos(self, event):
        if event.type == pygame.FINGERDOWN:
            return (int(event.x * WIDTH), int(event.y * HEIGHT))
        x, y = event.pos
        width, height = self.screen.get_size()
        return (int(x * WIDTH / max(width, 1)), int(y * HEIGHT / max(height, 1)))

    def online_code_label(self):
        if len(self.selected_pass) != 3:
            return ''
        return ' - '.join(ICON_NAMES[i].upper() for i in self.selected_pass)

    def status_lines(self, text, max_width=250, max_lines=3):
        words = str(text).split()
        lines, line = [], ''
        for word in words:
            trial = (line + ' ' + word).strip()
            if line and font_tiny.size(trial)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines[:max_lines]

    def on_press(self, pos, source=None):
        ticks = pygame.time.get_ticks()
        prev_ticks, prev_pos, prev_source = self._last_press
        if (source is not None and prev_source is not None and source != prev_source and
                ticks - prev_ticks < 145 and abs(pos[0] - prev_pos[0]) < 9 and abs(pos[1] - prev_pos[1]) < 9):
            return
        self._last_press = (ticks, pos, source)

        if pygame.Rect(538, 14, 86, 48).collidepoint(pos):
            self.running = False
            return
        if self.state != 'MENU_MODE' and pygame.Rect(16, 14, 100, 48).collidepoint(pos):
            self.back()
            return

        opt1 = pygame.Rect(120, 168, 400, 82)
        opt2 = pygame.Rect(120, 272, 400, 82)
        if self.state == 'MENU_MODE':
            if opt1.collidepoint(pos):
                self.reset_to_menu()
                self.players_count = 1
                self.net_type = 'LOCAL'
                self.state = 'PLAYING'
            elif opt2.collidepoint(pos):
                self.players_count = 2
                self.state = 'MENU_NET_TYPE'
        elif self.state == 'MENU_NET_TYPE':
            if opt1.collidepoint(pos):
                self.net_type = 'LOCAL'
                self.new_round()
                self.state = 'PLAYING'
            elif opt2.collidepoint(pos):
                self.net_type = 'REMOTE'
                self.state = 'MENU_ROOM_ROLE'
        elif self.state == 'MENU_ROOM_ROLE':
            if opt1.collidepoint(pos):
                self.room_role = 'CREATE'
                self.selected_pass = []
                self.state = 'MENU_PASSWORD'
            elif opt2.collidepoint(pos):
                self.room_role = 'JOIN'
                self.selected_pass = []
                self.state = 'MENU_PASSWORD'
        elif self.state == 'MENU_PASSWORD':
            if pygame.Rect(487, 182, 95, 64).collidepoint(pos):
                self.selected_pass = []
                return
            for i in range(len(ICON_NAMES)):
                rect = pygame.Rect(40 + i * 114, 292, 100, 108)
                if rect.collidepoint(pos) and len(self.selected_pass) < 3:
                    self.selected_pass.append(i)
                    if len(self.selected_pass) == 3:
                        self._start_network()
                    break
        elif self.state == 'PLAYING':
            if self.winner is not None and pygame.Rect(205, 458, 230, 50).collidepoint(pos):
                self.restart()
            elif self.winner is None:
                for index, rect in enumerate(self.GRID_RECTS):
                    if rect.collidepoint(pos):
                        self.click_cell(index)
                        break

    def draw_top_bar(self, surf):
        draw_card_button(surf, pygame.Rect(538, 14, 86, 48), 'HOME', '', COLOR_GOLD, icon='home')
        if self.state != 'MENU_MODE':
            draw_card_button(surf, pygame.Rect(16, 14, 100, 48), 'BACK', '', (78, 88, 104), icon='back')

    def draw_room_code_panel(self, surf):
        if self.net_type != 'REMOTE' or len(self.selected_pass) != 3:
            return
        panel = pygame.Rect(455, 86, 160, 90)
        draw_panel(surf, panel, fill=(63, 71, 84), radius=16)
        shadow_text(surf, font_badge, 'ROOM CODE', COLOR_GOLD, (panel.centerx, panel.y + 15), center=True)
        for i, animal in enumerate(self.selected_pass):
            bubble = pygame.Rect(panel.x + 12 + i * 48, panel.y + 28, 40, 40)
            pygame.draw.ellipse(surf, COLOR_PANEL_DARK, bubble)
            pygame.draw.ellipse(surf, (255, 255, 255), bubble, 2)
            draw_animal_icon(surf, bubble.centerx, bubble.centery, animal, size=14)
        shadow_text(surf, font_tiny, self.online_code_label(), COLOR_TEXT_SOFT, (panel.centerx, panel.bottom - 14), center=True)

    def draw_status_panel(self, surf):
        if self.net_type != 'REMOTE':
            return
        rect = pygame.Rect(28, 448 if self.winner is None else 414, 260, 58 if self.winner is None else 86)
        draw_panel(surf, rect, fill=(54, 60, 72), radius=14)
        draw_ui_icon(surf, 'online', pygame.Rect(rect.x + 6, rect.y + 12, 34, 34), COLOR_GOLD if (self.net is not None and not self.net.ready) else COLOR_TEXT)
        status = self.net.status if self.net is not None else 'Starting...'
        if self.waiting_move:
            status = 'Sending move...'
        elif self.net is not None and self.net.ready and not self.waiting_move:
            my_symbol = 'X' if self.room_role == 'CREATE' else 'O'
            if self.winner is None:
                status = 'Your turn!' if self.current_turn == my_symbol else 'Friend is thinking...'
        lines = self.status_lines(status, max_width=205, max_lines=3)
        for i, line in enumerate(lines):
            color = COLOR_GOLD if (self.net is not None and not self.net.ready) else COLOR_TEXT
            surf.blit(font_tiny.render(line, True, color), (rect.x + 42, rect.y + 10 + i * 16))

    def draw_setup_title(self, surf, title, subtitle=''):
        shadow_text(surf, font_title, title, COLOR_GOLD, (WIDTH // 2, 78), center=True)
        if subtitle:
            shadow_text(surf, font_small, subtitle, COLOR_TEXT_SOFT, (WIDTH // 2, 108), center=True, shadow=(25, 25, 25), soff=(1, 1))

    def draw(self):
        surf = self.view
        draw_background(surf)
        self.draw_top_bar(surf)

        opt1 = pygame.Rect(120, 168, 400, 82)
        opt2 = pygame.Rect(120, 272, 400, 82)

        if self.state == 'MENU_MODE':
            self.draw_setup_title(surf, 'TIC-TAC-TOE', 'pick a play mode')
            draw_card_button(surf, opt1, 'SOLO', 'play with the robot', COLOR_BLUE, icon='solo')
            draw_card_button(surf, opt2, 'FRIENDS', 'play together', COLOR_GREEN, icon='friends')
        elif self.state == 'MENU_NET_TYPE':
            self.draw_setup_title(surf, 'TWO PLAYERS', 'together or online')
            draw_card_button(surf, opt1, 'ONE TABLET', 'same screen', COLOR_BLUE, icon='tablet')
            draw_card_button(surf, opt2, 'ONLINE', 'two devices', COLOR_PURPLE, icon='online')
        elif self.state == 'MENU_ROOM_ROLE':
            self.draw_setup_title(surf, 'ONLINE PLAY', 'make or use a room code')
            draw_card_button(surf, opt1, 'MAKE CODE', 'start a room', COLOR_ORANGE, icon='create')
            draw_card_button(surf, opt2, 'USE CODE', 'join a room', COLOR_GREEN, icon='join')
        elif self.state == 'MENU_PASSWORD':
            subtitle = 'tap 3 animals' if self.room_role == 'CREATE' else 'tap the same 3 animals'
            self.draw_setup_title(surf, 'ANIMAL CODE', subtitle)
            for slot in range(3):
                rect = pygame.Rect(185 + slot * 95, 175, 80, 80)
                draw_panel(surf, rect, fill=COLOR_PANEL, radius=14, shadow=False)
                if slot < len(self.selected_pass):
                    draw_animal_icon(surf, rect.centerx, rect.centery, self.selected_pass[slot], size=28)
            draw_card_button(surf, pygame.Rect(487, 182, 95, 64), 'CLEAR', '', COLOR_RED, icon='clear', title_font=font_small)
            for i, name in enumerate(ICON_NAMES):
                draw_card_button(surf, pygame.Rect(40 + i * 114, 292, 100, 108), name.upper(), '', COLOR_PANEL_LIGHT, animal_icon=i, title_font=font_small)
            hint = 'same order on both devices' if self.room_role == 'JOIN' else 'tell your friend these 3 animals'
            shadow_text(surf, font_small, hint, COLOR_TEXT_SOFT, (WIDTH // 2, 425), center=True, shadow=(20, 20, 20), soff=(1, 1))
        elif self.state == 'PLAYING':
            if self.winner is not None:
                msg = 'TIE GAME!' if self.winner == 'TIE' else f'PLAYER {self.winner} WINS!'
                banner = COLOR_GOLD if self.winner == 'TIE' else (COLOR_RED if self.winner == 'X' else COLOR_GREEN)
                icon = 'crown' if self.winner != 'TIE' else 'play'
            elif self.net_type == 'REMOTE' and (self.net is None or not self.net.ready):
                msg = 'ONLINE ROOM'
                banner = COLOR_PURPLE
                icon = 'online'
            elif self.net_type == 'REMOTE':
                my_sym = 'X' if self.room_role == 'CREATE' else 'O'
                if self.current_turn == my_sym:
                    msg, banner, icon = 'YOUR TURN', COLOR_BLUE, 'play'
                else:
                    msg, banner, icon = 'FRIEND TURN', COLOR_PURPLE, 'online'
            else:
                msg = f'PLAYER {self.current_turn}'
                banner = COLOR_RED if self.current_turn == 'X' else COLOR_GREEN
                icon = 'turn_x' if self.current_turn == 'X' else 'turn_o'
            draw_card_button(surf, pygame.Rect(140, 30, 360, 55), msg, '', banner, icon=icon)
            self.draw_room_code_panel(surf)

            board_frame = pygame.Rect(155, 125, 330, 330)
            draw_panel(surf, board_frame, fill=COLOR_PANEL, radius=20)
            for i, rect in enumerate(self.GRID_RECTS):
                cell = rect.inflate(0, 0)
                pygame.draw.rect(surf, (38, 42, 50), cell, border_radius=12)
                pygame.draw.rect(surf, (87, 96, 111), cell, width=2, border_radius=12)
                if self.board[i] == 'X':
                    draw_symbol_x(surf, cell)
                elif self.board[i] == 'O':
                    draw_symbol_o(surf, cell)

            if self.winner is not None:
                draw_card_button(surf, pygame.Rect(205, 458, 230, 50), 'PLAY AGAIN', '', COLOR_GREEN, icon='play')
            self.draw_status_panel(surf)

        width, height = self.screen.get_size()
        if (width, height) == (WIDTH, HEIGHT):
            self.screen.blit(surf, (0, 0))
        else:
            self.screen.blit(pygame.transform.scale(surf, (width, height)), (0, 0))

    async def run(self):
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', 1) == 1:
                        self.on_press(self.scaled_pos(event), event.type)
                    elif event.type == pygame.FINGERDOWN:
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
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    if screen is None:
        screen = pygame.display.set_mode((800, 600))
    if clock is None:
        clock = pygame.time.Clock()
    init_fonts()
    game = TicTacToeGame(screen, clock)
    await game.run()


if __name__ == '__main__':
    asyncio.run(main())
