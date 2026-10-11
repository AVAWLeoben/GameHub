# WasteKart 1.9.4 — Seamless Bridge Polish

This is a **visual-only fix** for the single overpass at Clover Crossing.

The old overpass was a long rounded capsule laid on top of the road. The new art:
- follows the actual 1.9.3 upper-road centerline at the crossing;
- uses the **same asphalt colours** as the surrounding road;
- has **open ends with no rounded cap** and only short parallel side rails;
- adds a small underpass shadow to distinguish the two levels;
- keeps the lower road readable on either side of the bridge.

## Installation

Requires WasteKart **1.9.3** or newer with the figure-eight Clover Crossing installed.

Merge the included `WasteGame/` directory into your repository, replacing only:

`WasteGame/assets/WasteKart/Tracks/Cups/Cup1/track_02_overlay.png`

No Python changes, no new track metadata, and no road-mask changes. All racing, ghost, collisions and over/under logic remain identical to 1.9.3.
