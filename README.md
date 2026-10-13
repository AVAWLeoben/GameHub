# GameHub / WasteTacToe 2.1.4 — PeerJS load + deploy fix

This is a **single coordinated patch**. Previous Python + build patches must be installed together for online mode to work reliably.

## Replace these exact repository paths

- `WasteGame/wasteTacToe.py` (GameHub-compatible game; no changes to `main.py`)
- `build_itch.py` (repository root; preloads the PeerJS JavaScript file at BUILD time)
- `verify_web_build.py` (repository root; verifies the preload and included JS)

Commit all 3 files to **main** in the same commit. Do **not** copy the Python game into the repository root.

## What changed

- The preloaded `window.Peer` or `window.peerjs.Peer` constructor is now detected through an explicit JavaScript-returned string, avoiding Pyodide `is True` identity issues.
- If preloading is missing, Python tries the **same-origin** `vendor/peerjs-1.5.4.min.js` first; only then tries external CDNs.
- JavaScript `onload`, `onerror` and timeouts report which source failed. The old generic "PeerJS did not load" error has been replaced.
- The generated HTML synchronously loads `vendor/peerjs-1.5.4.min.js` before Pygbag starts.
- The build fails if it can't download a usable PeerJS file; the verification script fails if the generated web bundle is missing the preload.
- Host-authoritative multiplayer, room codes and kid-friendly UI remain unchanged.

## Essential deployment verification

1. Commit **all three** replacement files on GitHub's **main** branch.
2. In GitHub -> Actions -> **Build and deploy GameHub**, confirm **both** the build and deploy jobs succeed on that commit.
3. Open `https://avawleoben.github.io/GameHub/vendor/peerjs-1.5.4.min.js` in Safari. It should display/download JavaScript (a 404 means the deployment did not include the build patch).
4. Open the GameHub page in a NEW PRIVATE BROWSING tab on both devices to bypass stale installed-PWA caches, and run online Tic-Tac-Toe. The new status starts `Online v2.1.4` and, once created, says `Room ready (v2.1.4)!`.
5. Open room on one device, then join with the same three animals on another.

## If it still fails

Record the exact lower-screen message. This version distinguishes (a) library unavailable, (b) room-server registration failure, (c) no room found, and (d) WebRTC connection failure. The remote connection uses the public PeerJS signaling service and still requires working internet/WebRTC connectivity.

## What has / hasn't been tested

Checked: Python syntax; JS loader in simulated browser cases; Python host/guest callback and board logic; ZIP integrity; build injection and verification using synthetic generated web assets. **Not checked**: a live GitHub Pages deployment, two actual Safari/Pygbag devices, or end-to-end access to the public PeerJS server.
