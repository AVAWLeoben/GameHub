# WasteKart 2.1.2 — Cactus Corner moving desert hazards

## Install
Merge `WasteGame/` from this ZIP into the GameHub repository. **Replace
`WasteGame/wasteKart.py`**; keep the existing GameHub catalog, other tracks and
kart images. The patch includes only the affected course and hazard assets.

## Course slot
The supplied `cactus_corner_track_with_hazards_preview.png` says **Desert Cup
2/4**. WasteKart's existing course sequence also puts Cactus Corner second,
so this patch replaces **Cup3/track_02**. It does *not* overwrite the Desert Cup
3/4 course (Golden Gorge). The user's "Desert Cup 3/4" wording appears to refer
to Cup 3 of 4; if the *third course* is intended, its catalog entry can be
changed separately.

## Supplied art
- `track_02.png` and `track_02.mask.png`: unmodified, byte-for-byte copies of
  `cactus_corner_track.png` and `cactus_corner_road_mask.png`.
- `cactus_manifest.json` and **all supplied hazard sprites**, including shadows
  and high-resolution variants, preserved without modification.
- `track_02.json`: generated from the road mask's complete ordered skeleton;
  first point is near the provided west-facing starting grid (273, 431).

## Behavior
- Three narrow-western-leg lanes at y=236, 272 and 308 world pixels.
- Animated walking saguaro cacti in the upper/lower lanes, rolling barrel in
  the center, following the manifest's speed, anchor and hitbox values.
- Obstacles move from one safe desert end to the other and back, taking turns
  on the road. **Only one crossing is active at once**, leaving a gap.
- Collision **stops a kart and visibly rotates it 360 degrees for 1.45 s**,
  then the kart resumes its own previously drawn line. The cactus or barrel
  continues independently, and a cooldown avoids repeated spins.
- No effect on ordinary tracks or on the Dusty Drive train. Does not depend
  on enabling kart-to-kart bumping or power-ups.
- Four-player independent collisions, pausing, single/three lap racing and
  per-session ghost collision replay retain their normal flow.

## Testing note
Static Python syntax, extracted-mask geometry, simulation of three lanes,
collision/cooldown, and a fake-Pygame rendering harness are checked offline.
A real Pygbag/iPad race is still required before considering deployment proven.
