# GameHub PeerJS build fix — same-origin preload

## Why this patch

WasteGame uses Pygbag, which generates `WasteGame/build/web/index.html` fresh at
build time. Editing an `index.html` in the repository root would not change the
page deployed by the current GitHub Actions workflow. The workflow already runs:

1. `python prepare_build_env.py`, which calls `build_itch.py`.
2. `python verify_web_build.py`.
3. GitHub Pages upload from `WasteGame/build/web`.

This patch changes only the two existing **repository-root** build scripts.
**No `.github/workflows/deploy.yml` change is needed.**

## Install

Copy the following files from this ZIP into the root of your GameHub repo,
overwriting the existing files:

- `build_itch.py`
- `verify_web_build.py`

Keep your latest `WasteGame/wasteTacToe.py` (v2.1.2) in place; this patch does not
change the gameplay, UI, room codes, or networking protocol.

Commit these files to `main`. The GitHub Actions deploy will rebuild the site.

## How it works

- During the GitHub Actions build, `build_itch.py` downloads the **pinned**
  PeerJS v1.5.4 browser script, trying cdnjs, jsDelivr, then unpkg.
- If all downloads fail, the build **fails with an explicit message** rather
  than publishing a broken online multiplayer experience.
- The script is written to `WasteGame/build/web/vendor/peerjs-1.5.4.min.js`.
- It injects a normal synchronous `<script>` reference in the generated
  `index.html` `<head>` **before** Pygbag initializes.
- It includes the PeerJS MIT license alongside the script.
- `verify_web_build.py` ensures the deployed site and itch.io ZIP both include
  PeerJS and the generated HTML actually references it.
- In the user's browser, PeerJS loads from your own GitHub Pages origin, not
  from an external CDN. Your existing Python lazy loader will detect it.

## Verify after deploying

1. Wait for **Build and deploy GameHub** to finish successfully.
2. Visit `https://avawleoben.github.io/GameHub/vendor/peerjs-1.5.4.min.js`.
   It should display/download JavaScript, **not** a 404 page.
3. Open `https://avawleoben.github.io/GameHub/` on **both devices**, and hard
   refresh / close and reopen the installed PWA if necessary.
4. In Tic Tac Toe choose online play. The previous `PeerJS did not load` error
   should no longer occur. Try hosting and joining with the same three icons.

## Remaining dependencies

The game still requires live signaling via the public PeerJS Cloud server and
WebRTC-capable connectivity between browsers. A preloaded script fixes library
availability, **not** all possible network/NAT/connectivity failures. Two real
browser devices have not yet been tested here.

PeerJS is MIT licensed: https://github.com/peers/peerjs/blob/master/LICENSE
