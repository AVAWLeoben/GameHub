# WasteKart 1.3 — Reflex Start + Three Individually Drawn Laps

Drop-in GameHub update for `WasteGame/wasteKart.py`, compatible with Pygame-ce and the Pygbag entry point `await wasteKart.main(screen, clock)`.

## Installation

1. Extract this ZIP at the **repository root**, merging `WasteGame/` into your existing `WasteGame/` directory.
2. Commit and push the changed files to your feature branch / `main` according to your normal workflow.
3. GitHub Actions should rebuild GameHub automatically when the changes reach `main`.

The archive includes the original 16 tracks, their road masks, eight kart images and the catalog. Existing assets are unchanged; replacing `WasteGame/wasteKart.py` alone also works if WasteKart 1.1 is already installed.

## Setup options

- **Mode:** Single Race or four-track Cup Racing.
- **Players:** 1–4.
- **Time to draw:** 15 / 30 / 60 seconds **per lap**, or unlimited.
- **Laps:** 1 lap or **3 laps**.
- **Reflex start:** OFF or ON; you can choose independently of the number of laps.
- **Power-ups:** Not implemented yet; the menu says *Coming later (OFF)* rather than exposing a button that does nothing. A separate game-state setting exists for the future feature.

## How three laps work — important

Three laps are **not copies of one spline**. Player 1 draws lap 1, then draws a different lap 2, then lap 3; only then does Player 2 begin their three laps (if present). Players can keep one finger down and continuously draw across the start line, or lift and resume. Passing near the green start/finish dot after driving most of the circuit automatically saves that lap and opens the next one.

- The drawing countdown refreshes **for each of the three laps**, so 15 seconds means 15 seconds for each circuit.
- The `FINISH LAP` button and drawing timer finish only the *current* lap; an unfinished lap is connected directly back to the start/finish marker via a straight off-road segment. This retains the existing forgiving rules.
- `CLEAR` resets only the current lap, not the earlier laps already drawn.
- Completed laps appear as a dashed trail during the player's remaining drawing turns.
- The three **independently drawn** splines are concatenated into a **single continuous route**. The vehicle traverses that route once; there is no modulo wrapping or repeated geometry.
- Lap 1, 2 and 3 can have different lengths, curves, and lap split times.
- Single-player session ghosts store the distinct three-lap path and its boundaries. One-lap and three-lap ghost records never mix.

## Reflex start

When enabled, large buttons matching the players' kart colors appear during the traffic-light countdown and shortly after green:

- Press **after green** to earn a small, short-lived boost; faster taps are rewarded more.
- Press **before green** for a short, gentle false-start slowdown.
- A child who never taps is allowed to race normally (no punishment).
- Each player's input is independent, including simultaneous finger presses.
- When disabled, no reflex input is required and the game starts as before.

Power-ups and kart-to-kart physics remain intentionally out of scope for this release.

## Other retained features

- Cup championship points are 9 / 6 / 3 / 1 per race.
- **Equal championship points produce shared champions**, not an arbitrary tie-break winner.
- 16 original tracks, their per-pixel road masks, eight cosmetic karts.
- Radius-dependent speed plus off-road slowdown, Catmull–Rom drawing, session-only ghosts, one-lap and three-lap modes.
- Cached completed drawing trails and cached race-route overlays to reduce rendering work during three-lap multiplayer sessions.

## Testing

- Python syntax compilation passed.
- Logic simulations passed for drawing three distinct laps on **all 16 tracks**, per-lap timer reset, separate lap boundaries, lap split times, one-player ghosts, four-player Cup Racing, optional reflex input and tied champions.
- UI screens were exercised with a fake `pygame` rendering stub.
- **Not yet tested** in a real graphical Pygame or Pygbag runtime, or on a physical iPad. Confirm multitouch, button size, animation and real-world frame rate before treating the update as production-verified.
