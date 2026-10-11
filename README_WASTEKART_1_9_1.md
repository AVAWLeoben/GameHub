# WasteKart 1.9.1 — ONE Signature Track Prototype

Only **Meadow Cup / Track 1 (Daisy Dash)** has changed. No other tracks or Python game code are replaced.

## Why this is a genuinely different course

The old Daisy Dash was a simple oval. This hand-authored, non-self-intersecting loop is **2,669 world pixels** long, compared with roughly 1,600–1,900 for the previous Meadow prototypes. Its layout contains:

- A **310+ pixel main straight** with start/finish, four marked starting positions and a forward arrow.
- A **tight eastern hairpin** that doubles back.
- A **central alternating S-chicane** with both left and right turns.
- A **separate northern U-turn**, rather than yet another simple round bend.
- A **broad outer sweep** returning to the starting straight.
- Infield grass cuts that look tempting but trigger the existing **0.55 off-road speed factor**.

The circuit was verified as a closed, non-crossing loop, with a minimum measured centerline clearance of **101 pixels** between distant sections (the playable road is 70px wide). All road art and the game road mask derive from the same geometry.

## Original tile-art environment

The scene uses a tight flat pixel-art palette, 8px terrain tiles, repeating red/white curbs, orchard trees, a barn, fields, fences, daisies, a pond, livestock, chevrons, hay bales and a small start grandstand. Props are placed away from the road.

## Files

```
WasteGame/assets/WasteKart/Tracks/Cups/Cup1/
  track_01.png
  track_01.mask.png
  track_01.json
```

## Installation

Merge this ZIP into the repository, replacing **only** the three files above. No code update is required. Compatible with existing 960x600 WasteKart maps. Existing Cup 1 tracks 2–4 and all other cups remain untouched.

## Checkpoint limitation

The new track JSON includes **four ordered checkpoint positions**. The current WasteKart runtime does not enforce JSON checkpoints, so a determined player may still draw a shortcut that skips part of the course. Requiring checkpoint traversal is a separate gameplay change and is not claimed here.

## Verification

Geometry and masks were validated programmatically. Real Pygbag/iPad visual playtesting remains outstanding.
