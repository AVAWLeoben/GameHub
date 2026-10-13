# WasteTacToe 2.1.5 — Firefox browser loader-state fix

## Install

Copy `WasteGame/wasteTacToe.py` into the matching location in the GameHub GitHub repository, replacing the existing file. Wait for GitHub Pages deployment, then open a fresh private tab on both devices.

This is a one-file Python patch. The **previous 2.1.4 build-script preload update** may remain in place; no additional changes to `build_itch.py`, `verify_web_build.py`, or the GitHub Actions workflow are required.

## Corrected

- The PeerJS loader no longer checks that the return value from JavaScript `JSON.stringify(...)` is a native Python `str`. That caused `Cannot read browser SDK loader state` when the browser bridge returned a JavaScript proxy instead.
- Reads loader `status` and `detail` directly from the browser's `window.__gamehubTttPeerLoader` object, converting proxy values safely.
- Detects the `window.Peer` and `window.peerjs.Peer` constructor without relying on proxy truthiness or comparisons of proxy strings.
- If the browser cannot initialize loader state, shows a more precise diagnostic after 1 second.
- Preserves the host-authoritative online game protocol and all local play features.

## Verification

- Python syntax compiled successfully.
- Mock tests passed with Firefox-like JS proxy strings, normal Python strings, both PeerJS exports, and failed/missing loader states.
- A two-peer protocol mock confirmed board synchronization after both players move.

**Not verified:** actual Firefox + Pygbag + PeerJS signaling/WebRTC connectivity; test with two devices after deployment.

## Expected UI

After starting a room, status should progress through `Online v2.1.5: checking PeerJS...`, then either `Room ready (v2.1.5)! Waiting for friend...` or a detailed error. A stuck `Cannot read browser SDK loader state` means a cached older file is still running.
