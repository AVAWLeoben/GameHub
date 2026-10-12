# GameHub WasteTacToe 2.1.2 — Browser Peer Constructor Fix

## Install

Replace **only** `WasteGame/wasteTacToe.py` in your GameHub repository with the file in this patch. Do not replace your GameHub `main.py` or other games. Commit and allow GitHub Pages to deploy. Refresh **both devices** (ideally reopen the tab to avoid cached Pygbag builds), and ensure they are on the same deployed version.

## Fixed

- The previous PeerJS startup called `peer_class.new(...)` on a Pyodide JavaScript proxy, which is a plausible source of `TypeError: 'NoneType' object is not callable` if that attribute resolves to `None`. This build constructs the PeerJS class **inside JavaScript** via `new ctor(...)` instead.
- Finds the PeerJS browser constructor via `window.peerjs.Peer` or `window.Peer`.
- Avoids truthiness checks on JavaScript proxies that caused earlier `object has no len()` failures.
- Checks event listener and callback functions are callable, with clear failure reasons.
- Displays the precise failing connection stage (loading PeerJS / creating peer / attaching PeerJS events) and wraps long error messages onto two lines.
- Completes the missing right-column win check (`2,5,8`).

## Test procedure

1. On device A select 2 Players -> Online Play -> Create Secret Room -> choose three animals.
2. Wait for **Room ready! Waiting for friend...**, not simply "Opening room".
3. On device B select Join Secret Room and enter the animals in the same order.
4. Expect the host's room board to appear on both devices, take turns, then rematch.
5. If the error persists, record the **exact two-line status** including the named stage on both devices.

## Verification

- Python syntax/AST validation passed.
- Simulated host and guest PeerJS handshakes, moves, board sync and connection cleanup passed.
- Simulated missing-browser-bridge error reports a specific stage.
- A JavaScript-constructor test passed in Node.js.

**Not verified:** A real browser-to-browser WebRTC session through GitHub Pages/iPad. Internet/CDN availability, PeerJS cloud signaling, browser permissions and network policies can prevent pairing independently of this Python fix. This patch does not add a private signaling server.
