# WasteKart 2.1.3 — Golden Gorge / Desert Cup 3/4

Replace the included files in your GameHub repository, keeping the paths.

- `WasteGame/wasteKart.py` — adds river traffic, collision, bridge layering and ghost replay.
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup3/track_03.png` — exact supplied track art.
- `.../track_03.mask.png` — exact supplied road mask.
- `.../track_03.json` — generated closed centerline, checkpoints, bridge geometry, manifest pointer.
- `.../golden_gorge_bridge_overlay.png` and `.../golden_gorge_manifest.json` — exact originals.
- `.../logs/`, `.../water_ripples/` — supplied log/shadow/foam and ripple artwork.

No `catalog.json` edit is required if your catalog points Desert Cup 3/4 to `Tracks/Cups/Cup3/track_03.png`, `.json`, and `.mask.png`, as in the current WasteKart setup.

## Gameplay
- Floating logs drift diagonally NE to SW in three staggered river lanes.
- Logs are dangerous ONLY inside the polygonal shallow ford in the manifest. The main road bridge and decorative rope bridge are safe.
- Contact makes the kart spin **twice over 0.9 seconds**, following its drawn route at **40% speed** during the spins.
- After spinning there is **0.6 seconds** of immunity. The log gets a 4px sideways nudge but continues downstream.
- Train, cactus, kart interactions, existing powerups, one-to-four player play, drawing and race scoring remain supported.
- Water ripples are precomposed into four pre-scaled frames at load time for iPad draw performance.

## Layer order
Track/water frames -> log shadows -> log foam -> log bodies -> lower racers -> full bridge overlay (including rope bridge) -> bridge racers.

## Testing
Source syntax and bundled asset paths/metadata validated. Real Pygbag/iPad execution still requires a browser test. If your repository uses a different catalog path for this slot, adjust the catalog references accordingly.
