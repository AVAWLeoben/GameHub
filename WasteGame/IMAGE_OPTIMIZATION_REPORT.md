# WasteGame image optimization

Based on WasteGame_deduplicated.zip.

Four fully opaque background/map PNGs were converted to visually similar JPEGs at quality 90 with 4:4:4 color sampling. Original dimensions are unchanged. Game source references were updated. Collision masks, roads and transparent sprites were not altered.

| Original | Replacement | Before | After | Saved |
|---|---|---:|---:|---:|
| `WasteGame/assets/wastePilot/map_lrg.png` | `WasteGame/assets/wastePilot/map_lrg.jpg` | 25.24 MiB | 7.84 MiB | 17.40 MiB |
| `WasteGame/assets/wastePizza/kitchen.png` | `WasteGame/assets/wastePizza/kitchen.jpg` | 2.04 MiB | 0.35 MiB | 1.69 MiB |
| `WasteGame/assets/wasteCollect/background/background.png` | `WasteGame/assets/wasteCollect/background/background.jpg` | 1.77 MiB | 0.29 MiB | 1.47 MiB |
| `WasteGame/assets/BuildTower/background.png` | `WasteGame/assets/BuildTower/background.jpg` | 2.10 MiB | 0.38 MiB | 1.73 MiB |

Total raw asset savings: 22.29 MiB.

These JPEG conversions are lossy: minor pixel/color differences are expected. Pygame JPEG image loading is supported. The game has not been play-tested in Pygbag or on iPad.

Other large assets remain as originally provided.