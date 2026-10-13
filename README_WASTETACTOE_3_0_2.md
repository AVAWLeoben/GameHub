# WasteTacToe 3.0.2 — Firebase Room Join Fix (GameHub)

This is an incremental replacement for `WasteGame/wasteTacToe.py`. It preserves the existing one-player, same-device two-player, three-animal online room UI, and `async def main(screen, clock)` integration.

## Confirmed defect fixed

Firebase Realtime Database may call `runTransaction()` initially with `null` even when remote data exists but has not yet been cached. Version 3.0.1's guest join updater immediately returned `undefined` for that initial `null`, aborting the operation with `committed=false`. The guest could therefore repeat "Room changed while joining" although the host room existed. See Firebase docs: https://firebase.google.com/docs/database/web/read-and-write#save_data_as_transactions

Changes in 3.0.2:

- **Guest joins with `update(roomRef, {guestUid, expiresAt})`**, not `runTransaction`. The existing published security rules atomically accept only an empty guest seat, so simultaneous guests cannot overwrite each other. A server read confirms the guest seat was saved.
- **Host creates with `set()` guarded by Firebase database rules** after checking for a live room. If a live room belongs to the same anonymous host user, it can be reset by its owner; other users cannot steal it.
- **Leaving a room now uses `remove()` (host) or `update({guestUid:null})` (guest)** instead of a transaction that could also abort on an uncached `null`.
- Old cleanup is awaited before a new session starts in the same tab, preventing late cleanup from deleting the newly created room.
- Inactive rooms expire after 20 minutes (extended after each successful move). Rooms made by prior 3.0.x versions may retain their original 45-minute expiry.
- Host waiting status includes `v3.0.2` so you can confirm that your browser received the new deployment.

## Install

1. In your `GameHub` repository, replace `WasteGame/wasteTacToe.py` with the file from this ZIP.
2. **Keep the existing Firebase Realtime Database security rules from WasteTacToe 3.0.** No new rules, Firebase Hosting, PeerJS or GitHub Actions changes are needed.
3. Wait for GitHub Pages deployment. Open a *new private browser tab* on **both** devices to avoid a cached build.
4. To remove test rooms previously abandoned by the buggy versions: Firebase Console → **Realtime Database → Data** → select **`tttRooms`** → **Delete** (only if no other game is in progress). This is a **one-time optional cleanup**; it removes all Tic-Tac-Toe test rooms, not the database or its rules.
5. Device A: **2 Players → Online Play → Create Secret Room** and choose three animals. The host should display **`Waiting for friend... (v3.0.2)`**.
6. Device B: **2 Players → Online Play → Join Secret Room** and choose the exact same animals in the same order.
7. Test 3 moves per player, a win, and a rematch. Then return to the menu and try the same animal code again; it should be reusable.

## Requirements

- Firebase project `gamehub-1c72c`, Realtime Database and anonymous authentication enabled as before.
- Database rules previously provided in `WasteTacToe_3_0_Firebase_GameHub` must already be published. **Do not enable public read/write access.**
- Each device needs internet access, but they can use different networks. No TURN or PeerJS required.

## Validation

- Python syntax compilation passed.
- Tested the JavaScript bridge in an isolated two-browser Node simulation against a mock Firebase database enforcing the same room owner/guest access cases: create, guest join, moves, win, rematch, guest exit, host reset, cleanup, new room codes and rejection of other people's occupied rooms.
- **Actual Firebase server rules, real Firefox/iPad browser access, and a two-device GitHub Pages test cannot be confirmed from this environment.**

If a failure remains, provide the host and guest messages. A `Permission denied` message on a newly empty code would indicate a server security rules mismatch, and the Firebase Console → `tttRooms` data can help distinguish it from a stale room.
