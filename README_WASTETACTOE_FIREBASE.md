# WasteTacToe 3.0 — Firebase multiplayer for GameHub

This replaces PeerJS + WebRTC with Firebase Realtime Database. Different networks (Wi-Fi / mobile) are supported without a TURN server.

## Upload ONE Python file

Copy `WasteGame/wasteTacToe.py` into the same path in your GameHub GitHub repository. Other games, `main.py`, and build scripts stay unchanged.

## Mandatory ONE-TIME Firebase setup

1. In Firebase Console, project `gamehub-1c72c`, check **Authentication > Sign-in method > Anonymous** is **enabled and SAVED**.
2. Go to **Build > Realtime Database > Rules** for the database `gamehub-1c72c-default-rtdb`.
3. Replace the existing rules with the ENTIRE CONTENTS of `firebase_realtime_database_rules.json`, and click **Publish**.
4. **Do not select unrestricted test mode** or use `".read": true, ".write": true`.
5. Upload the Python file to GitHub; wait for GitHub Pages deployment; refresh both devices (private window if cached).
6. Device A: 2 Players > Online Play > Create Secret Room > 3 animals.
7. Device B: 2 Players > Online Play > Join Secret Room > same 3 animals in same order.

No PeerJS setup, TURN account, or web build change is required. The prior PeerJS preload can remain; this game simply does not use it.

## Notes

- No personal account, email, or names required. Firebase signs devices in anonymously in the background. Internet is still required.
- The **three-animal code has only 125 combinations**, so it is a convenient room selector, **not a secure/private password**. Rooms store only board state and anonymous Firebase IDs, no child-identifying information. Other signed-in clients can potentially discover active room codes. Don't use these codes to protect sensitive data.
- Rooms are deleted when the host leaves/disconnects where supported, and become reclaimable after 45 minutes if cleanup fails. When a guest leaves, its seat becomes available again.
- Only one active game may use a particular three-animal code. Choose a different code if occupied.
- Database rules restrict writes to valid room creation, joining, leaving, a player's own turn, and rematches. They are not an anti-abuse/rate-limiting service. Monitor database usage and consider App Check / backend throttling if distributed widely.
- `firebaseConfig.apiKey` in Python is a normal public Firebase web-app identifier, not an administrator key. **Never commit service-account keys.**
- The browser loads official Firebase modules from `www.gstatic.com`. If a browser blocks that domain, online play will display a loading error.
- Automatic guest account cleanup is controlled in Firebase Authentication and is okay to leave enabled.

## Troubleshooting

- `Permission denied`: publish the supplied Realtime Database rules; do not leave locked default rules.
- `auth/operation-not-allowed`: enable Anonymous under Authentication and click Save.
- `Room already used`: another match currently uses those three animals; choose another code.
- `Room not available`: create the room first on Device A.
- `Failed to fetch dynamically imported module`: confirm the browser can access `https://www.gstatic.com/firebasejs/13.0.0/firebase-app.js`, `firebase-auth.js`, and `firebase-database.js`.

## Testing status

Syntax and local protocol/bridge tests can be run without contacting Firebase. Live two-device verification requires publishing rules and opening the deployed GitHub Pages game on two browsers.
