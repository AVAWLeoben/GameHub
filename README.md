# WasteTacToe 2.1.6 — Firefox PeerJS constructor fix

## Install

Replace **only** `WasteGame/wasteTacToe.py` in your GameHub repository with the supplied file. Keep the 2.1.4 web-build PeerJS preload changes, if already installed. No modifications to `main.py` or the GitHub workflow are needed.

Wait for the GitHub Pages deployment to finish, then open GameHub in a fresh private browser window on both devices. Both players must load the latest version.

## Root cause and fix

The previous version ran `js.eval('(function(...) {...})')` and then called the returned JS function proxy from Python. On the reported Firefox/Pyodide setup the function proxy was **not Python-callable** even though JavaScript supports the function. The error was `creating PeerJS peer: RuntimeError: PeerJS constructor bridge is not callable`.

This patch invokes a *self-executing* script that constructs PeerJS **entirely in JavaScript** and stores the actual instance on `window.__gamehubTttActivePeer`; Python accesses that instance directly. There is no Python call to an evaluated JavaScript function, and session cleanup clears the reference.

## Test status

- Python compilation and offline bridge regression checks passed.
- JavaScript constructor tests passed for both `window.Peer` and `window.peerjs.Peer`, including guest and host paths.
- Live Pygbag/Firefox-to-Firefox signaling and WebRTC still require device testing; the simulator cannot prove that external connections work.

## Expected status

After selecting a three-animal code, expect `Online v2.1.6: checking PeerJS...`, then `Opening room...` or `Finding friend...`. On a registered host, `Room ready (v2.1.6)! Waiting for friend...` should appear. If another issue remains, the status includes the failing stage.
