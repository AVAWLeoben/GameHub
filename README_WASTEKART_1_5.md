# WasteKart 1.5 — Smaller Racing Karts and First Kart Interactions

This is a **code-only** replacement for the working WasteKart 1.4.5 build. The original 16 tracks, masks, kart selection art, power-up graphics and GameHub integration remain unchanged.

## Changes

### Kart size

The new top-down kart sprites now render at **38 × 28 logical pixels**, instead of **56 × 42** in 1.4.5. This means the previous sprites were about 50% larger than the new ones. Selection-screen previews remain at their previous size so children can still compare the artwork. Player number badges, shadows, flame origins and airflow effects were adjusted to the reduced in-race footprint.

### Kart interactions (optional)

The setup screen now has three independent settings in its bottom row:
- **ITEMS — ON/OFF**
- **LINES — ON/OFF**
- **BUMP — ON/OFF** (new; defaults to ON)

With **BUMP** enabled and at least two human players:

- **Slipstream:** A kart running closely behind another kart in the same direction receives a mild (13%) speed advantage while in that position. Short turquoise airflow streaks appear behind the drafting kart. Multiple nearby karts do not stack slipstream boosts.
- **Gentle bumps:** Karts passing very close to one another have a short, friendly speed interaction with little yellow impact sparkles. Rear contact slows the approaching kart and slightly nudges the leading kart; crossing contact slows both. A 0.65-second per-pair cooldown prevents repeated collision spam.
- **Author-drawn lines are preserved:** Bumps change speed, never kart position or the spline path, so a child’s kart cannot be knocked permanently off its drawn line.
- **No impact on the starting grid:** Contacts are inactive for the first second after GO.
- **Ghosts do not interact:** Session ghost time trials remain comparable and the ghost neither drafts nor bumps other karts. One-player racing is unchanged.

Turning **BUMP** OFF switches both effects off. The first pass is intentionally light: interactions do not cause crashes, remove items, or add penalties.

## Install

Unzip into your GameHub repository root and replace:

`WasteGame/wasteKart.py`

Keep all of your existing images, sprites, road masks, `catalog.json`, and launcher registration. Commit and push to `main` to deploy with your normal GitHub Actions workflow.

## Verification

- Python compilation passed.
- Headless logic tests passed: UI ON/OFF controls, 38 × 28 sprite cache, slipstream eligibility, no stacking, single-player/disabled mode, bump cooldown, no position changes, and visual effect drawing.
- Automated simulations completed **all 16 tracks** with **1, 2 and 4 karts**.
- Separate **three-lap** race simulations passed with **four players**, reflex boosts, power-up boosts, and interactions active.
- The 1.4.5 **corner button** regression suite also passed for 1–4 players.
- **Real Pygame/Pygbag visual rendering and iPad multiplayer touch testing have not been performed here.**

## Suggested playtest

Use two players on Meadow Cup Track 1-1 with **BUMP ON**, **ITEMS OFF**, and **1 LAP**. Draw one kart directly behind the other on a long straight to see the turquoise slipstream; draw crossing routes to see a brief spark. Repeat with **BUMP OFF** to compare. Then try a four-player race to evaluate kart readability at the new size.
