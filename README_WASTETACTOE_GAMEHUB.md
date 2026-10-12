# WasteTacToe — GameHub integration patch

This patch replaces the existing Tic Tac Toe minigame with the user-provided
redesigned Kiddie Tic-Tac-Toe UI, adapted for GameHub and browser networking.

## Installation

Merge the `WasteGame/` folder in this ZIP into the root of your GameHub repo.
The only code file to replace is:

`WasteGame/wasteTacToe.py`

No changes to `WasteGame/main.py`, other minigames, or the existing GameHub
launcher are required. In the current GameHub repository, the launcher calls
`await wasteTacToe.main(screen, clock)` on an 800 x 600 shared display.

## How to play

- **1 Player** — Local play against a simple computer opponent.
- **2 Players → Same Screen** — Two people share the same device.
- **2 Players → Online Play → Create Secret Room** — Host chooses 3 animal
  icons in order and waits. Host plays X.
- **2 Players → Online Play → Join Secret Room** — Guest on another device
  chooses **the same 3 animals in the same order**. Guest plays O.
- **HOME** returns to GameHub from every screen, including the first one.
- **< Back** returns to the previous menu or setup screen.
- **Play Again** resets the board without leaving the minigame. In online
  mode either player can request a rematch when the game has ended.

## Web multiplayer prerequisites

- Each player needs their own browser/device, internet access, and a browser
  that supports WebRTC (for example, a current Chrome/Safari/Firefox).
- When online mode is selected, the game loads the browser PeerJS 1.5.5 SDK
  from `https://unpkg.com/peerjs@1.5.5/dist/peerjs.min.js`.
- PeerJS uses its public PeerServer for connection signaling. Public
  signaling/network services can be unavailable or blocked by some networks;
  this mode is **not an offline feature**.
- The 3-animal room identifier is **not a secure password**: there are only
  5³ = 125 possible combinations, and a person who guesses the code may join.
  Do not use this for private or sensitive conversations/data.
- Some restricted/school networks block WebRTC or unpkg.com and may prevent
  online matches. Local play works independently.

## Integration changes

- Removes import-time `pygame.init()`, `display.set_mode`, and
  `asyncio.run()`, which previously hijacked the GameHub display/event loop.
- Provides `async def main(screen=None, clock=None)` and returns to the hub
  without calling `pygame.quit()`.
- Preserves the uploaded animal faces, colored cards, X/O glyphs, and
  menu/game flow. The 640 x 520 interface is scaled to the 800 x 600 shared
  GameHub display, and mouse/touch inputs are mapped back correctly.
- Imports `create_proxy` from `pyodide.ffi` (not from `js`). Each PeerJS
  event handler is retained while in use and released on exit.
- Loads the PeerJS SDK on demand when entering Online Play; no JS bootstrapping
  is required for the local/solo modes.
- Makes the host authoritative for moves; the guest sends a move request,
  and the host synchronizes the validated board state. Handles win/tie,
  disconnects, a new round, and stale messages.

## Verification status

**Automated local checks passed:** Python syntax compilation, local single-
player gameplay, local two-player gameplay, GameHub-compatible entry/exit,
coordinate scaling, UI drawing through a Pygame test double, repeated-animal
room codes, mocked two-peer join/sync, rematches, stale moves, invalid moves,
error/disconnection handling, and shutdown cleanup.

**Not verified here:** Live two-browser PeerJS signaling/WebRTC through a real
Pygbag build, or touch performance on iPad. Test on GitHub Pages after upload.
