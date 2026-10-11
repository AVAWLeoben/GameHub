# WasteKart 1.1 — Single Race + Cup Racing

Playable GameHub update for Pygame-ce / Pygbag. Continues from WasteKart 1.0 and the revised design document dated October 11, 2026.

## Install

Extract the archive **at the repository root** and merge the `WasteGame/` directory. This replaces `WasteGame/wasteKart.py` and supplies updated `catalog.json` plus 16 road-mask PNGs. Original track pictures, 8 kart images and 16 geometry files are included for a complete, self-contained folder; existing GameHub launcher integration remains in place. Commit to `main` to trigger the already configured GitHub Actions deployment.

Do not replace `WasteGame/main.py` or rerun the 1.0 launcher helper if WasteKart already appears in GameHub.

## What's new

* **Two play modes on the first screen**: Single Race (a selected track) or 4-Track Cup (every track in the selected cup, in order).
* **1–4 players and four drawing timers**: 15, 30 or 60 seconds, or no limit.
* **Cup scoring**: 9, 6, 3 and 1 points for the first through fourth finishers. An interim results screen shows finishing times and cumulative points, with `NEXT TRACK`. After the fourth race a final cup champion screen offers `REPLAY CUP` or `HOME`.
* **Single Race practice**: `RACE AGAIN` returns to drawing on the same course, not straight into an old race. `CHOOSE TRACK` goes back to track selection. Single-race results award no cup points.
* **Solo ghost**: On a subsequent single-player run of a track, a translucent kart replays the best previous drawing from this **running game session**. It uses the same spline and speed model. Beat its best finishing time to update the in-memory record. No browser storage, cookies or save files.
* **Previously drawn routes appear as dashed colored lines** during the next child's turn.
* **Unfinished drawings connect in a straight line back to the finish**, and this final straight is kept straight after interpolating the child's drawn spline. Crossing grass generally slows the kart. A completely empty stroke gets a short fallback route so the game cannot hang at a zero-length path.
* **Radius-aware speed**: precomputes circumradius from spline neighbors with a smoothing window. `v_min=0.40*v_max` at tight bends, up to `v_max` on wide turns; on-road multiplier 1.0 and grass multiplier 0.55. For now karts have cosmetic differences only.
* **Separate road masks**: added 16 matching `.mask.png` files. Each kart does a single pixel lookup to decide whether it is on the road.
* **iPad input**: one finger/mouse draws, `CLEAR` restarts a route and `DONE` finishes the current turn; touch-action disabled temporarily while the game runs in a browser.

## File changes

```
WasteGame/
  wasteKart.py                              # replace 1.0 source
  assets/WasteKart/
    catalog.json                           # adds road_mask entries
    Karts/...                              # original unchanged assets
    Tracks/Cups/Cup1..Cup4/
      track_01..04.png                      # original unchanged assets
      track_01..04.json                     # original unchanged geometries
      track_01..04.mask.png                # NEW dedicated road masks
```

## Test status

Checks in the build environment passed:

* Python source syntax.
* All 16 road masks include every course's centerline samples.
* All 16 sampled one-lap routes finish in a bounded driving simulation.
* Single Race, redraw-based rematch, ghost recording and repeat ghost simulation.
* Four races in Cup mode with 1–4 player flows, 9/6/3/1 scoring and championship reset.
* 15-second drawing timeout and unlimited mode.
* Simulated rendering calls for menu, selection, drawings, countdown, race, results and all four Cup stages.

**Not yet tested on a real Pygame window or Safari/Pygbag/iPad.** The environment has no pygame-ce installation. In particular, touch behavior, button legibility and actual FPS should be verified on the user's iPad.

## Still intentionally out of scope

Reflex-start buttons, power-ups, physical kart interactions and per-kart performance attributes are future stretch features.
