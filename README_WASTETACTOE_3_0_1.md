# WasteTacToe 3.0.1 — Firebase room reliability

## Why 3.0 could fail to join

3.0 registered Firebase `onDisconnect(...).remove()` on the **entire host room**. A temporary mobile/browser disconnect could erase the room before a friend joined. Also, the guest returned a generic `Room not available` without reporting whether the host room existed.

## Fixes

- No automatic deletion on a transient network disconnect.
- The host does not display **Room created on server** until a separate server read confirms creation.
- The guest waits up to 20 seconds for the room to become available, then shows a precise error.
- Distinct error messages for unavailable rooms, occupied rooms, shared anonymous identities, and Firebase permissions problems.
- HOME/Back still explicitly ends a room; unattended rooms become reclaimable after 45 minutes.
- Firebase rules unchanged; no PeerJS, TURN, or GitHub Actions updates.

## Install

1. Replace `WasteGame/wasteTacToe.py` in GameHub with the file in this ZIP.
2. Confirm the Firebase rules from version 3.0 are already published. The JSON is repeated in this ZIP for reference only, **do not relax permissions**.
3. Wait for GitHub Pages deployment, close old tabs and launch fresh tabs on both devices.
4. On device 1, choose Create + three animals. **Wait for `Room created on server. Waiting for friend...` before using device 2.**
5. On device 2, Join with identical animals.
6. If it still fails, send the full bottom status from **both** devices.

## Testing

Static syntax checks and simulated Firebase host/client transactions are included. They cannot verify your actual project's published Firebase rules or two real browser sessions.
