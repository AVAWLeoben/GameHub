# WasteHockey — CPU opponent and stuck-puck fix

This patch is a drop-in follow-up to the polished WasteHockey build.

## What's fixed

- CPU paddle no longer shadows the puck without hitting it: the previous attack target was **72 pixels** to the right of the puck, while puck + paddle collision radii total **56 pixels**.
- CPU approaches to within 29 pixels on its own side to initiate an actual hit.
- When the puck is arriving from the other half, CPU predicts its vertical interception point, accounting for top/bottom rebounds.
- When the puck is against the CPU's far wall and the CPU cannot get behind it, the paddle retreats rather than wedging it against the boundary or shooting into its own net.
- CPU paddle and shot speeds are capped to stay beatable for young children.
- If the puck barely moves horizontally for several seconds, it gets a gentle horizontal boost **without changing position, resetting scores, or restarting the round**. Near the CPU's wall, recovery is faster.

## Compatibility

No artwork, field dimensions, menus, scores, touch controls, celebrations or multiplayer rules have changed.

## Installation

Extract the ZIP into your GameHub repository, merging `WasteGame/` into the existing folder. Commit changes on `main` to trigger your deployment workflow. If the asset PNGs are already present from the previous update, replacing only `WasteGame/wasteHockey.py` is sufficient.

## Validation

- Python syntax compilation
- Previous menu, touch, AI, goal, celebration, and clock logic tests
- Simulated idle and moving pucks on CPU side, including shots near the back wall
- 60 randomized CPU-side starting positions: all moved >100 px or reached a goal within 10 seconds

This is a simulation-based verification, not a full graphical Pygbag or iPad test. Please test one-player Endless on your device.
