# WasteKart 1.4.1 — Subtle Racing Lines & Power-up Icons

Drop-in update for GameHub's WasteKart 1.4. No PNGs or other asset changes.

## Installation

From the ZIP, copy `WasteGame/wasteKart.py` over the matching file in the GameHub repository. Keep existing `WasteGame/assets/WasteKart/` files from version 1.1+ in place. Commit the change to `main` to deploy with your existing GitHub Actions workflow.

## Visual refinements

- **Race Lines: HIDE / SHOW**, chosen in the initial setup alongside the Power-ups toggle. **HIDE is the default** to keep the course legible with 1–4 karts. This is separate from Reflex Start and Power-ups.
- **SHOW:** Remaining racing paths are very faint, **1-pixel** dashed lines in each player's color, with approximately **26% opacity** (ghost: **16%**). Driven portions still disappear. Existing route caching is preserved, and current segments are drawn to a small transparent scratch surface to prevent them appearing opaque. Three differently drawn laps, crossings, and ghosts remain supported.
- **HIDE:** No race-line overlay is rendered or constructed. During the **drawing phase**, routes remain clearly visible so children can create and compare their lines.
- **Power-up buttons now use pictograms rather than names:** an orange/yellow flame for **Turbo**, a turquoise wind symbol for **Tailwind**, and a **?** for an empty slot. Each button still shows the player's number/color. A collected power-up has a small sparkling indicator; an active power-up has a duration ring. Boost effects behind the karts remain in place.
- Buttons retain their full tappable hitbox, even with four players.

## Unchanged behavior

Single Race, four-track Cups, shared cup champions, 1/3 separately drawn laps, reflex starts, ghosts, box placement/respawn, one held item per player, power-up activation, and actual racing physics.

## Testing

Python syntax checks, 16-course gameplay/menu checks, alpha-layer test inspection, item icon states, 4-player touch-action buttons, independent settings, 3-lap ghost behavior, and full 4-player Cup simulation through a headless Pygame stub passed. A real Pygame / Pygbag / iPad visual test has **not** been run in this environment.
