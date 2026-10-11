# WasteKart 1.3.2 — Boost Flames and Disappearing Race Lines

## Installation

Extract this ZIP into the **root of your GameHub repository** and replace `WasteGame/wasteKart.py`. Commit the changed file to your branch or `main` as appropriate. Your existing `WasteGame/assets/WasteKart/` folder from 1.3 is unchanged and required; **no new PNG assets are needed**.

## Changes

### A. Reflex boost flames

Successful green-light reflex-start taps now produce a flickering cartoon exhaust flame *behind the kart*, oriented with its current heading. Orange, yellow and pale-yellow polygons and two sparks are painted with built-in `pygame.draw` primitives, requiring no new image assets. The flame stays while the three-second acceleration modifier is active and shrinks as it expires. False starts, non-boosted karts, and finished karts do not show flames. With **Reflex Start OFF**, there are no flames.

### B. Only untraveled racing lines remain visible

During countdown, all planned spline paths are displayed. As soon as the race starts, the portion of each driver's spline already behind their kart disappears. This also applies to the session ghost. The path remains visible ahead, even through corners, and disappears entirely when its kart reaches the finish. Every player/ghost has an independent path-progress state; single and three-lap racing and all four players are supported.

**Efficiency:** instead of redrawing the complete multi-lap spline 60 times a second, each path is pre-rendered once into small, tightly cropped 240-world-pixel sections. Only the section currently being driven is rendered partially at frame time; completed sections are skipped and the remainder are fast blits. The renderer uses arc length rather than pixel clearing, so an upcoming loop crossing an earlier loop is not damaged when the earlier segment disappears.

## Preserved features

- Single Race and four-track Cup Racing; tied scores produce shared champions.
- 1 or 3 *independently drawn* laps, with per-lap drawing timers.
- Optional reflex start, start lights, 1–4 players, 8 kart choices, 16 original courses.
- Session-only fastest-line ghosts, radius-dependent and road-mask speed rules.
- Browser-compatible `async main(screen, clock)` entry point.

## Testing and limitations

- `py_compile` passed.
- Stub-rendered full four-player, three-lap cup race completed; boost and false-start flame conditions, route visibility and ghost layers passed logic checks.
- Per-route cached surface allocation on all 16 original tracks was checked for roughly 0.8–1.4 MiB in typical three-lap routes, before other game assets.
- Real Pygame/Pygbag rendering and iPad performance were **not** available in this environment. Verify in-browser animation and touch behavior on the device.
