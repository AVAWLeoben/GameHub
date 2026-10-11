# WasteKart 1.0 — GameHub minigame

A new original Pygame/Pygbag, SNES-era top-down kart racing game. 1–4 people take turns drawing one driving line each, then race one lap along their own spline curves. All course art in this package is original and is NOT copied from the linked Super Mario Kart map.

## Installation into GameHub

1. Extract this ZIP **at the repository root**, so `WasteGame/wasteKart.py` and `WasteGame/assets/WasteKart/` are added alongside your existing games. No existing minigame files are replaced.
2. Register WasteKart in the launcher. For the standard GameHub launcher (with `GAMES = [...]` and `buttons = [...]`), run this helper from the repository root:

   ```bash
   python add_wastekart_to_gamehub.py
   ```

   The helper makes `WasteGame/main.py.before_wastekart.bak`, detects if already integrated, and refuses to alter unfamiliar launcher layouts. Review and commit the updated `WasteGame/main.py`.
3. Commit the new source, art and track metadata to `main` and allow GitHub Actions to deploy.
4. If your launcher is customized and the helper does not recognize it, manually add `import wasteKart`, `('WasteKart', wasteKart.main)` to `GAMES`, and one new menu button pointing at `assets/WasteKart/kart_icon.png`. Its click handler must select `wasteKart.main`. Do **not** replace a customized launcher with an older one.

To run as a standalone program, with `pygame-ce` installed, run `python wasteKart.py` from inside the `WasteGame` directory. The default window is 800×600.

## Setup and gameplay

- **1–4 racers.** Each racer selects one of eight colorful karts, with no duplicates.
- **Draw time per player**: 20, 40 or 60 seconds (default 60, suitable for small children).
- **4 cups × 4 tracks** = 16 unique original illustrated courses. Navigate cups and course cards before choosing karts.
- **Separate drawing turns**. A large `READY TO DRAW` screen gives everyone time to pass the tablet. Draw with a finger or desktop mouse; lift and continue. `CLEAR` restarts the current drawing; `DONE` finishes early.
- **Child-friendly path completion.** If a drawing is unfinished when the timer expires or the player taps DONE, the *remaining* part is smoothly joined to the finish along the course, retaining the drawn section and off-road detours. An empty stroke automatically becomes a full track lap so a very young child isn't stuck.
- **Smooth Catmull–Rom interpolation** of players' drawn route, then equal-distance resampling. Cars follow this line, *not* the centerline unless the child left a section incomplete.
- **Race countdown**: 3 red lights, then GO. All karts start automatically and complete one lap.
- **Speed simulation**: wide curve radius = faster, tight bends = slower; points on the road are faster than the grass/other off-road terrain. Karts accelerate from the starting line.
- **Results**: finish times, ranking, winner, falling confetti, Race Again (reuse routes), New Race (return to setup), and Home (return to GameHub).
- **No lose states or penalties.** A child can make shortcuts and oddball tracks and still finish.

### Original tracks

- **Meadow Cup**: Daisy Dash, Clover Crossing, Apple Orchard, Bumblebee Bend
- **Coast Cup**: Shell Shore, Coral Curve, Harbor Loop, Turtle Tides
- **Desert Cup**: Dusty Drive, Cactus Corner, Golden Gorge, Comet Canyon
- **Star Cup**: Moonlight Mile, Glow Garden, Starlight Spiral, Rainbow Rocket

### Input and display

- Finger drag on iPad; mouse drag on PC. Only one finger is used to draw each player's turn.
- `SPACE`: finish drawing now; during countdown/race: pause/resume.
- `ESC`: return to GameHub from menus; pause/resume during countdown/race.
- Canvas `touch-action: none` is used when Pygbag provides the browser `js` bridge, then restored on exit.
- The standard 800×600 GameHub surface renders at native resolution. Other display sizes are supported by scaling the 800×600 logical playfield and remapping pointer input.

## File layout

```text
WasteGame/
  wasteKart.py
  assets/WasteKart/
    catalog.json
    kart_icon.png
    Karts/
      kart_01.png ... kart_08.png
    Tracks/Cups/
      Cup1/
        track_01.png, track_01.json ... track_04.png, track_04.json
      Cup2/ ...
      Cup3/ ...
      Cup4/ ...
add_wastekart_to_gamehub.py  # optional launcher integration helper
```

Each track JSON describes the road centerline and width; the PNG provides its corresponding artwork. To design your own track later, modify the PNG and keep the route geometry and start/finish aligned.

## Not yet implemented — future stretch goals

1. Individual start-reaction buttons for 1–4 players.
2. Pick-up items and a power-up action sharing the player's button.
3. Physical kart interactions when routes converge or overlap.

## Tests / limitations

- Python syntax, all 16 map geometry files and kart assets, road-mask approximation, spline endpoints, one-lap finish and on-road/off-road speed simulations: **passed**.
- Four-player menu/drawing/countdown/results/rematch flow and all screens: **passed with a lightweight pygame rendering stub**, not real display hardware.
- Automatic integration helper tested against the archived standard GameHub launcher, with syntax verification of the patched launcher.
- **Real graphical Pygame-ce, Pygbag browser and iPad performance/touch behavior have not been run in this environment.** Test on the target devices before considering it production-ready.
