# WastePuzzle — layout, selection, difficulty, and celebration update

## Install

Extract the ZIP into the root of `AVAWLeoben/GameHub`, preserving the included path:

`WasteGame/wastePuzzle.py`

Commit the change to your `main` branch. The existing GitHub Actions workflow should rebuild and publish GameHub automatically if it is configured to deploy on pushes to `main`.

**This update intentionally does not include or replace your picture/background/balloon assets.** It reuses the files already in `WasteGame/assets/wastePuzzle/`:

- `image1.png`, `image2.png`, `image3.png`, `image4.png`
- `background.jpg`
- `balloon_black.png`, `balloon_blue.png`, `balloon_green.png`, `balloon_red.png`, `balloon_popped.png`

No additional Python dependencies are required beyond Pygame/Pygbag already used by GameHub.

## Gameplay

- Starting the game displays **four picture thumbnails**. Children tap to choose the puzzle.
- Choose difficulty using one, two, or three **stars**:
  - **1 star / HELP ME** — faint grayscale image plus marker and dotted direction hint to the selected piece's correct cell.
  - **2 stars / PICTURE** — faint grayscale image, no marker or dotted line.
  - **3 stars / NO HINTS** — blank grid only.
- Tap **PLAY!** to start. The chosen image and difficulty remain selected when returning to the menu.
- All **16 pieces are physically shuffled** into 2 columns x 4 rows on either side of the centered board.
- Pieces are **smaller while in the trays** so none overlap the board, Home, Picture or Restart buttons. They appear at full tile size during dragging and once placed.
- Drag a piece to its matching puzzle cell, or tap the piece and then tap its destination. Incorrect placements return the piece to its tray.
- Completion launches **12–21 rising balloons** (previously 8–14), a WELL DONE! message, and **AGAIN! / PICTURES** controls.
- A balloon can be popped by tapping it.
- The **HOME** button returns to the GameHub launcher.

## Technical considerations

- Uses the existing `await wastePuzzle.main(screen, clock)` entry point.
- Supports SDL2/Pygame `FINGER*` events on iPad and mouse events on desktops; synthetic mouse events following a touch are ignored.
- Only one puzzle piece can be dragged at a time, avoiding simultaneous-touch conflicts.
- Layout scales from `screen.get_size()`; reference screen: 800x600.
- No sprite assets are generated or modified here.

## Verification

- Python syntax and AST validation completed.
- Calculated screen-layout checks completed for 800x600, 1024x768, 640x480, and 960x540; all puzzle trays stayed inside the window and below the toolbar.
- Pygame wasn't available in the build sandbox, so **a real Pygame/Pygbag visual and touch test has not been performed**.

### Suggested test

Open the game on an iPad, verify picture and star selection, try dragging pieces across the board, test the one-tap-then-tap placement option, and complete one puzzle to verify the balloon celebration.
