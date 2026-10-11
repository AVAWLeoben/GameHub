# WasteKart 1.4.4 — Visual Polish

A presentation-only follow-up to WasteKart 1.4.3 (which itself includes the new kart artwork from 1.4.2).

## Changes

- **Kart selection:** larger, smoothly scaled kart previews with a ground shadow / display plinth, gentle selected-kart bounce, gold selection star, and a small shimmer. The existing eight kart PNGs and their selectable positions are unchanged.
- **Animated power-up boxes:** stronger bobbing, three tiny orbiting glints, twinkling edge highlight, and a small burst when a box is collected. The location, collection radius, respawn timer, inventory rules and boost effects are unchanged.
- **Cup and single-race results:** gold/silver/bronze place badges, alternating result rows, animated corner sparkles, original Pygame-drawn trophies, and a four-dot cup progress indicator. Shared cup winners on tied championship points are preserved.

All additions use Pygame drawing primitives; no extra PNG assets are required.

## Installation

Extract into your existing GameHub repository, replacing only:

`WasteGame/wasteKart.py`

Retain existing `WasteGame/assets/WasteKart/` including the 1.4.2 kart PNGs, tracks, masks and catalog. Then commit and push to `main` to trigger deployment.

## Validation

- Python compilation and AST comparison against 1.4.3 passed. Only four presentation methods changed; four visual helper methods were added.
- Rendering-path smoke tests via a lightweight pygame stub passed for the kart selection, active/collected item boxes, 1–4-player results, cup standings and tied cup champions.
- Not yet visually tested in a real Pygame/Pygbag window or on iPad.
