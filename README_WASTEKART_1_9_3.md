# WasteKart 1.9.3 — Clover Crossing: The Figure Eight

This update **replaces the rejected cloverleaf/interchange course** with one
clean, two-loop figure-eight circuit. It has **exactly one crossover** in the
center. The road above that crossover follows the same centreline as the track.

## Install

Merge the `WasteGame/` directory into your GameHub repository, replacing:

- `WasteGame/wasteKart.py`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_02.png`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_02.mask.png`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_02_overlay.png`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_02.json`

The **Daisy Dash 1.9.1** and all other track files are unchanged. If your
repository already has the earlier broken Clover Crossing, this completely
replaces that course. No change to `catalog.json` is required.

## What overpass support does

- The bridge visual is loaded from an optional alpha PNG, with metadata in JSON.
- During drawing, strokes on the underpass render beneath the raised bridge;
  strokes following the upper road render above it.
- During races, each kart/ghost is drawn on the correct side of the bridge
  based on its location and heading.
- Karts on opposite layers **cannot** slipstream or collide at the crossover.
- Power-up boxes are kept away from the crossing so their level is unambiguous.
- Road masks remain the union of the two roads, with full road speed on both.

## Gameplay note

This is still a children's freehand drawing game. Drawn routes are not
forced onto the road, and the two-level behavior is inferred by heading at
the crossover. A child can draw either loop and cross the bridge normally.
No new controls are required.

## Checks

The 960×600 track's centerline is one closed route, contains exactly one
non-adjacent crossing, and keeps road pixels and geometry aligned. Four
checkpoint suggestions are saved in JSON, but checkpoints are **not yet
required/enforced** by the game.
