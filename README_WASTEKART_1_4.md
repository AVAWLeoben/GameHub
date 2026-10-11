# WasteKart 1.4 — Optional power-ups

## Install

From the GameHub repository root, extract this ZIP and overwrite:

`WasteGame/wasteKart.py`

The existing 16 tracks, mask PNGs, kart artwork and `assets/WasteKart/catalog.json` from WasteKart 1.1–1.3.2 **remain required**. No new artwork needs to be installed. Push to `main` to deploy through the current GitHub Actions workflow.

## What's new

- **POWER-UPS ON / OFF**, selectable independently of **REFLEX START ON / OFF**.
- Seven gently bobbing, spinning, glowing **[?] boxes** per track, positioned near the **edge of the road**. An ideal centerline route misses them; players must draw a line closer to a box to pick it up.
- Collection is determined by the kart's actual drawn trajectory, not by a tap during drawing.
- **Shared pickup boxes:** any kart that touches an available box makes it disappear for **7 seconds**, even if that kart is already holding an item. If already holding an item, the original remains unchanged.
- **One held item per player.** Activate the item with that player's own colored button during the race. Those are the same input slots used for Reflex Start, which runs first when enabled.
- Two beneficial items (no attacks yet): **TURBO** = a strong 3.2-second boost, with golden fire exhaust; **TAILWIND** = a gentler 6-second boost, with turquoise airflow streaks around the kart.
- A held item is indicated on the player's tappable button. While active, the same button displays its remaining effect time. A player can collect another item while boosted, but cannot activate it until the previous effect expires.
- In single player, the session ghost records/replays boost usage for a comparable time. Ghost records are kept separately by selected lap count, Reflex Start and Power-ups settings. Nothing is saved to disk.
- Original 1/3 individually drawn laps, Single Race/Cup Racing, tied Cup champions, disappearing driven splines and reflex flame remain supported.

## Controls

- **iPad:** Draw the race line toward a nearby **[?]** box. The kart collects it automatically if it drives close enough. During the race, tap the colored button for your player to use the item. When Reflex Start is enabled, its timing buttons appear through the start reaction window, then the buttons switch to items.
- **Desktop:** Mouse works as before; number keys **1–4** trigger the equivalent player's start or item button for convenience.

## Testing / limitations

- Syntax and headless logic/UI tests passed, including menu toggles, road-placement checks on all 16 tracks, shared respawn, already-full collection, both boost types, four-player Cup flow, 3-lap ghost recording and effects, and game-finish transitions.
- A full graphical Pygame/Pygbag run and iPad touch testing were not available in this environment. Visual effect timing, touch layout and speed balance should be verified on the target devices.
