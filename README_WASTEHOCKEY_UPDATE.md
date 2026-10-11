# WasteHockey polish update — GameHub

## Install

Extract the ZIP in the root of your `GameHub` repository, merging `WasteGame/`.

Updated files:

```text
WasteGame/
  wasteHockey.py
  assets/
    wastehockey/
      field.png
      pusher1.png
      pusher2.png
      puck.png
```

Commit/push to `main`; the existing GitHub Actions workflow will deploy normally.

## Changes

- Start menu: 1 player (computer opponent) or 2 players; 1 minute, 2 minutes, or endless.
- Finger follow speed increased; dedicated pointer ownership preserves two simultaneous fingers on iPad.
- Puck and paddles have actual alpha transparency instead of opaque white backgrounds.
- The 1280×673 field is drawn at its original ratio (800×421) inside the 800×600 game frame. Physical rink bounds align to its artwork.
- Removed debug goal markers. Rink picture still contains its built-in goals.
- Goal pause: 1.6-second confetti and goal banner.
- Timed match: final winner/draw banner, persistent final score, Play Again and Change Mode buttons.
- Single player controls left/yellow; computer controls right/blue.
- Handles screens that are not exactly 800×600 with aspect-preserving letterboxing and correct touch coordinate conversion.

## Controls

Touch: each human player drags one finger on their side of the field.
Desktop: drag mouse; alternatively WASD for left and arrow keys for right.
In one-player mode the right paddle is AI controlled.

## Testing

Python syntax check and headless logic tests were run for menu state, aspect geometry, finger ownership, AI targeting, scoring, goal pause, timed ending. PNG transparency was visually inspected. Pygame/Pygbag device rendering was not available in the build environment; test locally/iPad before calling it a release.
