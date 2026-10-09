# WasteGame — iPad icon and Home Screen reminder

## Why the previous version didn't work

1. The reminder was intentionally disabled when the game ran in an iframe. **itch.io embeds HTML5 games in an iframe.** The only page Safari can add to the Home Screen via the Share menu is the outer itch.io page.
2. The build scripts were delivered **without `app_icon.png`**, so they silently used Pygbag's default favicon (usually the letter W).

## What this update does

- Includes `app_icon.png` (512×512, the previously designed hedgehog icon) alongside the scripts. Replace this image with your preferred square PNG if desired.
- Adds `apple-touch-icon.png` at the website root, `<link rel="apple-touch-icon">` in the HTML head, a custom favicon and a manifest icon. The actual filenames are copied into each generated ZIP.
- Rejects an incomplete build if the icon is absent or not a square PNG; no more silent fallbacks to W.
- In **Safari on the direct game website** (e.g. GitHub Pages), shows a small, dismissible reminder after 6 seconds. The reminder disappears after 18 seconds, returns no sooner than 21 days, and stays dismissed if closed. It is not shown in the installed web app.
- An iframe embedded on itch.io still **cannot change the icon of itch.io's parent page**. But if you enter your direct game website address in `home_screen_url.txt`, an iframe can display a link to open the dedicated app website in a new tab (subject to the embed's pop-up policy). The link does not claim that adding the itch.io page installs WasteGame.
- Includes a QA test parameter `?show_install_hint=1` for the direct game page, which forces the tip to display shortly after loading, even on desktop or if previously dismissed. Remove that query parameter for normal use.
- Preserves the Pygbag media-user-engagement (UME) patch, stand-alone metadata, multitouch canvas style and Windows/Linux environment bootstrap.

## Installing on an iPad

1. Build using `build_itch.bat` (Windows) or `sh build_itch.sh` (Linux/macOS).
2. Deploy the generated `dist/WasteGame_itch_io.zip` to itch.io as before; publish the *contents* of the same ZIP to a standalone site such as GitHub Pages.
3. Open the **direct** game URL in iPad Safari, not the itch.io wrapper page.
4. Check that `https://YOUR-SITE/apple-touch-icon.png` shows the custom hedgehog icon. For a GitHub Pages project path, use `https://USERNAME.github.io/REPO/apple-touch-icon.png`.
5. Remove the old WasteGame Home Screen shortcut if present. Safari may retain an icon cached at installation time.
6. Tap Share → Add to Home Screen → Open as Web App → Add.

## Files and optional configuration

Place the complete kit beside your `WasteGame/` source directory. The important new/retained files are:

- `app_icon.png` — **included custom icon**, may be replaced
- `build_itch.py` — copies the icon, injects Home Screen meta tags and JavaScript
- `install_hint.js` — unobtrusive reminder or standalone link
- `home_screen_url.txt` — optional single `https://` URL for opening the direct game page from itch.io's embedded game

For testing the reminder, open `https://YOUR-GAME-URL/?show_install_hint=1` on Safari; this does **not** test install behavior on the itch.io wrapper. A real install needs a direct game URL; changing nested iframe metadata cannot change the parent site's icon.

## Troubleshooting

- If opening the raw `apple-touch-icon.png` URL gives a 404, the updated build is not deployed at that site/path.
- If you still get the W, inspect the *top-level* website's HTML and icon. Installing `geri1993.itch.io/wastegames` installs itch.io's top-level page, regardless of what your embedded ZIP contains.
- After changing the icon, delete and re-add the Home Screen app to overcome iPadOS icon caching.
- Pygbag and mobile Safari still cannot programmatically bypass platform audio-gesture or system-edge-gesture restrictions.
