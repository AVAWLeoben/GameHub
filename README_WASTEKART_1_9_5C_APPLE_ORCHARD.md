# WasteKart 1.9.5c — Apple Orchard Edge Fix

This fixes the jagged road edges introduced in 1.9.5b.

## What happened
The curb cleanup in 1.9.5b switched to short edge segments, which left tiny gaps on tighter corners. Those gaps exposed the grass texture and made the road edge look jagged.

## Fix
- restored a continuous curb/edge underlay around the full road
- kept the improved curb placement, but now paint red curb blocks on top of that sealed edge
- preserved the upgraded orchard decorations and the approved layout

## Files
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_03.png`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_03.mask.png`
- `WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_03.json`
