# WasteSort — GameHub update

A drop-in replacement for `WasteGame/wasteSort.py`.

## Fixes

1. **Can't lose items off-screen:** dragging clamps the full object rectangle to the 800×600 logical play area. The displayed image also pulses only slightly and remains inside the visible screen.
2. **Randomized positions every room:** the five existing waste objects are placed with non-overlapping random coordinates on **each of the six room backgrounds**; no fixed repeated layout from level 2 onward.
3. **Final win screen:** after completing all six rooms, a persistent celebration displays `Amazing! The whole house is clean!` with `PLAY AGAIN` and `HOME`. It does not immediately return to the launcher.
4. **Compatibility extras:** original bin categories and image filenames, mouse and finger dragging, scale-to-fit on non-800×600 game screens, and a short inter-room star celebration.

## Install

Extract the zip into your GameHub repository and replace `WasteGame/wasteSort.py`. Keep your existing `WasteGame/assets/` folder, in particular `Level1.png` ... `Level6.png`, `paperbox.png`, `banana.png`, `can3.png`, `can4.png`, `glass.png`, the eight `trashBin_*.png` bin states, `retBut.png`, and `star.png`.

Commit and push to `main` to trigger GitHub Actions deployment.

## Tests to run on iPad

- Drag each item toward all four screen edges; it must remain visible and recoverable.
- Complete room 1 and check that room 2 starts with a new layout. Check again on rooms 3–6.
- Sort the last object in room 6 and verify the celebration remains until a button is pressed.
- Try **Play Again** and **Home**.

Only the code is included; no artwork files were provided or changed.
