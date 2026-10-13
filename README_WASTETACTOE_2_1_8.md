# WasteTacToe 2.1.8 — Connection diagnostics

## Install
Replace only `WasteGame/wasteTacToe.py` in your GameHub repository.
Keep the previous PeerJS preload build scripts. No additional services are installed.
Both devices should be refreshed after deployment.

## Changes
- Keeps the 2.1.7 JavaScript-managed PeerJS event bridge (no `pyodide.ffi`).
- Preserves the three-animal room codes and on-wire protocol; 2.1.7 and 2.1.8 can use the same room ID.
- Shows actual DataConnection error type/message instead of the generic `Connection error`.
- Reports WebRTC ICE states (`checking`, `failed`, `connected`) and connection timeouts.
- Does not hide a specific error behind a later disconnect notification.

## How to diagnose
- **No room yet / peer-unavailable**: check the same 3-animal code and that host reached Room ready.
- **WebRTC ICE failed / timeout**: PeerJS signaling may work, while network address discovery fails. Try both devices on the same Wi-Fi, turn off VPN/content blockers, or try another network. Restrictive NATs may require a TURN relay.
- **Connection ... (ICE ...)**: share the complete message from both screens to narrow down the cause.

The patch improves diagnostics; it cannot ensure peer-to-peer connections on every network. No TURN service or credentials are included. Live Firefox-to-Firefox validation is still required.
