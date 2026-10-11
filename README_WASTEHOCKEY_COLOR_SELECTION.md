# WasteHockey — Paddle Color Selection

## Installation

Merge the `WasteGame/` directory from this archive into your GameHub repository,
replacing `WasteGame/wasteHockey.py` and (optionally) its existing hockey PNGs.
Commit the changes to your `main` branch; GitHub Actions will deploy the update
if your workflow is set to run on pushes to `main`.

## What changed

- Both player slots can choose from **eight distinct colors** in the start menu:
  Red, Orange, Yellow, Green, Turquoise, Blue, Purple and Pink.
- Once a color is assigned to one paddle, the same color is **disabled** for the
  other paddle (shown dimmed with a slash). This also applies to the CPU paddle
  in one-player games.
- Default player colors remain Yellow and Blue.
- Colored paddle previews, score indicators, goal announcements, and the actual
  paddle sprites use the selected colors.
- Pygame performs the recoloring **at runtime**, using
  `pygame.transform.grayscale()` and `pygame.Surface.fill(...,
  special_flags=pygame.BLEND_RGB_MULT)`. The recolored images are cached, so
  they're not recalculated on every game frame.
- The original transparent PNGs and all previous AI/gameplay logic are retained.

## Files

```
WasteGame/
  wasteHockey.py
  assets/wastehockey/
    field.png
    pusher1.png
    pusher2.png
    puck.png
```

## Testing

Python source syntax and automated selection rules were checked, including
all eight palette options, conflicts, and invalid choices. Asset transparency
was also checked. Rendering and touch interaction still need a real Pygame /
Pygbag session on your devices.

## Customizing colors

Edit `PADDLE_PALETTE` near the top of `WasteGame/wasteHockey.py`.
Each entry is `(name, (R, G, B))`; retain eight distinct names and colors.
