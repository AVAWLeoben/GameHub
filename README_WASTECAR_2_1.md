# WasteCar 2.1 — Drive Anywhere

Extract this ZIP into the root of your GameHub repository, overwriting `WasteGame/wasteCar.py`.

## Change

- The player's rubbish truck can drive anywhere within the map boundaries, including grass, yards, parks, and open ground. The `is_road` mask check has been removed from both the driving and collision code.
- Instant steering toward the finger remains unchanged.
- Existing acceleration, momentum, braking, collisions, camera zoom/look-ahead, bin collection, arrow, timer, menu, and game completion remain intact.
- Civilian cars still follow their extracted road network (`assets/wasteCar/mapdata.json`).
- The unused NPC road mask is no longer loaded at startup, reducing load time/memory slightly.

## Included files

- `WasteGame/wasteCar.py` (replace)
- `WasteGame/assets/wasteCar/mapdata.json` (same route data as 2.0, supplied for convenience)

Keep your current `WasteGame/assets/` PNG artwork. There are no new image assets.

## Testing

Python syntax checks and isolated tests passed: unrestricted driving, direct-finger steering with inertia, map boundaries, and off-road traffic collision. No actual Pygame/Pygbag or iPad run was available in the build environment.
