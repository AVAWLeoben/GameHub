# WasteJump 2.0.1 — GameHub Startup Recovery

This is a **startup reliability hotfix** for the WasteJump 2.0 Dusk City update. The gameplay, graphics, and normal Home button remain the same.

## Symptoms addressed
After pressing the Jump Game button in the GameHub menu, the previous 2.0 game could fail before drawing its first screen, leaving the last GameHub menu frame visible. A missing/unreadable newly introduced image is one likely cause, but **the exact browser-side cause has not been confirmed**.

## Changes
- All 3 Dusk City scenery files are included in the ZIP again (useful when a previous upload omitted them).
- Asset loader tries GameHub-root and module-relative locations without depending on `os.path.isfile()` checks.
- Loading/format conversion and scaling are defensive for pygame-ce/Pygbag.
- If any image is absent or unreadable, the game uses procedurally drawn fallback scenery, truck, obstacles, or Home icon rather than crashing before frame 1.
- If a different startup/runtime error occurs, a readable error panel appears. Tap it to return to GameHub instead of leaving a frozen main-menu frame.
- Replaced smoothscale with ordinary scale for the optional non-800×600 display case.
- Preserves gameplay and the 800×600 layout.

## Upload to GitHub
Replace `WasteGame/wasteJump.py` and ensure these three images are committed under the exact paths:

- `WasteGame/assets/wasteJump/city_dusk_sky.png`
- `WasteGame/assets/wasteJump/city_dusk_far.png`
- `WasteGame/assets/wasteJump/city_dusk_near.png`

The original `assets/wasteJump/player.png`, six obstacle PNGs and `assets/retBut*.png` are unchanged and reused when present.

No changes to `WasteGame/main.py` or the build workflow.

## Tests completed
- Python compilation.
- Offline image loading and drawing simulation using a pygame/Pillow compatibility layer, including all original assets and the three new backgrounds.
- Start with every art asset missing: procedural fallbacks render for menu, playing, pause, game over.
- Simulated async GameHub entry -> Play -> Home -> return.
- Simulated forced constructor failure -> visible error screen -> return.
- Jump, land, collisions/cooldown, loss, replay, pause, and 420 update ticks.
- ZIP extraction/CRC checks.

**Not verified:** a full Pygbag/browser/iPad run. If the screen still freezes, report any visible error text and inspect the browser console, or upload a current `WasteGame/main.py` and browser console log for more precise debugging.
