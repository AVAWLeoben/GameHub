# WasteTacToe 3.1.1 — Native GameHub UI Correction

This patch supersedes the visually flawed 3.1 UI update. It is based on the **confirmed-working Firebase 3.0.2 multiplayer implementation**.

## What is corrected

- **Native 800×600 drawing:** the standard GameHub display gets directly drawn graphics and fonts, without 640×520-to-800×600 smooth scaling.
- **Standard GameHub Home button:** use `assets/retBut.png` (wooden house) at `(10,10)` in a `100×100` hit area. This patch also includes an exact fallback copy at `assets/wasteTacToe/retBut.png`.
- **Back button:** remains separate at top right; its arrow and text fit within its button and both are clickable.
- **Three-animal room code:** displayed in a dedicated panel beside the board throughout online play, including the waiting stage.
- **Child-friendly setup:** large, highly contrasted icons (not light-grey symbols in squashed circles); fewer words; clear animal faces with names as secondary hints.
- **Replay button:** local and online modes now each use the matching on-screen hit target.
- **Aspect ratio:** nonstandard screen sizes are letterboxed rather than stretched to a distorted aspect ratio.

## Installation

Copy files from this patch into the corresponding locations in your GitHub repository:

- `WasteGame/wasteTacToe.py`
- `WasteGame/assets/wasteTacToe/retBut.png` (fallback copy of standard Home image)

There are **no changes to Firebase configuration, Firebase Realtime Database Rules, `main.py`, or GitHub deployment scripts**.

## Validation and limits

- Python syntax/compilation checks passed.
- The Firebase JavaScript bridge and `FirebaseSession` class are byte-for-byte unchanged from 3.0.2 (other than source positioning/whitespace outside these blocks).
- Input and state checks passed for Back/Home, menu navigation, repeated animal choices, local wins, and local replay.
- Screen layouts were drawn through a Pillow-based Pygame compatibility renderer to check clipping and geometry. These are **layout approximations, not screenshots from real Pygame or Pygbag**.
- Real browser/iPad testing is still required.

Rollback: replace only `WasteGame/wasteTacToe.py` with your known-working 3.0.2 file. The added fallback Home image is harmless if unused.
