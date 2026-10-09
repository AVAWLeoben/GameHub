# WasteGame — duplicate asset cleanup

The `WasteGame/` folder is a drop-in replacement for the previous game source and assets.

- Exactly **17 duplicated image files removed**, across **14 identical-content groups**.
- Every removed file was verified to be **SHA-256 identical** to the retained copy.
- **No image colors, resolution, alpha, or other image data were changed.**
- Python image loading paths have been redirected to the retained copies, including the dynamic paths in `wasteCollect.py`.
- All Python scripts compile; remaining static image path strings were checked for existence.
- This is **not a Pygbag browser gameplay test**. Rebuild and test each changed minigame, especially on iPad.

## Files changed

- `WasteGame/jetStream.py`
- `WasteGame/wasteCollect.py`
- `WasteGame/wasteHog.py`
- `WasteGame/wasteJump.py`
- `WasteGame/wasteRace.py`
- `WasteGame/wasteTeroids.py`
- `WasteGame/wasteTrain.py`

## Removed assets and their replacements

- `assets/jetStream/grass.png` → `assets/hungryHedgie/grass.png`
- `assets/player.png` → `assets/card_1.png`
- `assets/treasure.png` → `assets/card_1.png`
- `assets/wasteBird/idle_christmas.png` → `assets/hungryHedgie/hedgie.png`
- `assets/wasteCollect/banana.png` → `assets/banana.png`
- `assets/wasteCollect/can.png` → `assets/can.png`
- `assets/wasteCollect/paperbox.png` → `assets/paperbox.png`
- `assets/wasteHedge/idle.png` → `assets/wasteHog/idle.png`
- `assets/wasteHog/idle_christmas.png` → `assets/hungryHedgie/hedgie.png`
- `assets/wasteHog/sack.png` → `assets/hungryHedgie/sack.png`
- `assets/wasteJump/start.png` → `assets/star.png`
- `assets/wasteRace/empty.png` → `assets/wasteBin_empty.png`
- `assets/wasteRace/full.png` → `assets/wasteBin_full.png`
- `assets/wasteRace/road.png` → `assets/road.png`
- `assets/wasteRace/truck.png` → `assets/truck.png`
- `assets/wasteTeroids/Asteroid.png` → `assets/Asteroid.png`
- `assets/wasteTrain/grass.png` → `assets/hungryHedgie/grass.png`

## Sizes (uncompressed files)

- Before: 108,941,323 bytes
- After: 101,435,328 bytes
- Net saved: 7,505,995 bytes (7.16 MiB)

A larger, separate source of download size is `assets/wastePilot/map_lrg.png` (~25 MiB). It has **not** been resized or modified.

### Installation

Replace your repository's `WasteGame/` directory with the one from this ZIP. Keep the existing build scripts, iPad icon, and GitHub Actions workflow at the repository root. Then run your existing build script.
