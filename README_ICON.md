# WasteGame custom icon

This kit already includes a **512×512 `app_icon.png`** (your hedgehog game icon). You do **not** have to rename it or supply one separately.

To change it, replace `app_icon.png` in the same directory as `build_itch.py` with your own square PNG, at least 180×180 pixels, ideally 512×512.

Rebuild using `build_itch.bat` or `sh build_itch.sh`. Your output ZIP includes:

- `app_icon.png` and `apple-touch-icon.png` — used by iPadOS
- `favicon.png` — the game's browser tab icon, also your custom image
- `manifest.webmanifest` — declares the Home Screen icon and standalone display
- `index.html` — links to the above with cache-busting icon URLs

The build now fails if `app_icon.png` is missing instead of quietly using Pygbag's W.

**Note:** The icon applies to the direct hosted game URL, such as a GitHub Pages deployment. If you add the *itch.io project page* to the iPad Home Screen, its icon is controlled by itch.io, not your game's iframe. Remove and re-add an existing Home Screen shortcut after deploying a new icon.
