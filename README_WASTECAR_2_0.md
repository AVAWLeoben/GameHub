# WasteCar 2.0 — GameHub / Pygbag update

This update preserves the GTA2-style child-friendly map and uses the original truck, road, bin, and car artwork.

## Install

1. Extract this archive into your `GameHub` repository root, merging the `WasteGame/` folder.
2. Replace `WasteGame/wasteCar.py` with the included code.
3. Add **`WasteGame/assets/wasteCar/mapdata.json`**. This file is REQUIRED: it contains the exact precomputed NPC road centerlines and ten original bin markers.
4. Keep the existing assets at `WasteGame/assets/`: `road.png`, `road_driveable - NPC.png`, `road_bins.png`, `truck.png`, `car1.png`, `car2.png`, `car3.png`, `wasteBin_full.png`, `wasteBin_empty.png`.
5. Commit both files to `main` to trigger automatic GitHub Pages deployment.

## Controls

- iPad: **touch and hold** anywhere in the game world to drive directly toward that finger. No steering delay. Release to brake.
- Desktop: mouse button held, or WASD / arrow keys. Space brakes.
- Menu: START DRIVING / HOME; pause and resume available in-game.
- Collect the waste bins: follow the purple chevron. Stop close to a bin to collect automatically.
- Timer measures elapsed play time; pausing stops the timer.
- After all 10 bins, a persistent result screen shows the time, confetti, Play Again and Home.

## Mechanical changes

- Truck facing direction snaps immediately to touch/mouse position; *velocity* accelerates, coasts, and reacts to collisions for a heavier feel.
- Camera pulls farther back as speed increases and looks ahead in the driving direction.
- Other cars follow a road network derived from the actual magenta traffic line in the existing `road_driveable - NPC.png`. Vehicles follow curves and choose turns at junctions. This road network was precomputed offline: the game does not need cv2, numpy, scipy or skimage.
- Physical bumps slow cars, recoil the truck, shake the screen briefly and emit sparks.
- Fixed original bin-collection bug (`self.full == False` never changed state).
- Does not quit the global Pygame instance when returning to GameHub.
- Efficient camera: crops the visible portion of the *original* map then scales just the viewport, never smoothscales the entire large world each frame.

## Testing

- Syntax compilation passed.
- Pure-Python simulation checked 10 traffic cars for 2,400 physics steps each, including junctions and dead ends; no traffic position jumps.
- Verified immediate truck heading changes with velocity inertia.
- Verified successful collection creates a persistent completed game state and a recorded elapsed time.
- Pygame is not installed in this sandbox, so full interactive graphics and iPad browser behavior are **not yet verified**. Test in Pygbag before declaring a stable release.
