# Hungry Hedgie — quality pass 2.0

## The result

Hungry Hedgie now has a complete, gentle adventure: collect berries, carry them
home, make a visible improvement, and finish with a picnic. The existing
`await main(screen, clock)` entry point is preserved. Replace GameHub's
`hungryHedgie.py` with the supplied file; no new artwork or audio downloads
are required. The replacement has no dependency on GameHub's `GUI` module.

## What changed, and why

| Area | Original behavior | Updated behavior |
| --- | --- | --- |
| Purpose | Food disappeared into a sack with no result | An open food tray fills; deliveries earn a bed, a garden, and a picnic |
| Counting | A pickup multiplied carried food by two | Every berry adds exactly one; visible basket slots show the count |
| Delivery | Carrying was reset, then decremented again during animation | Each delivery transfers food once; flying berries are visual effects |
| Progression | Endless collection with no completion | Three short stages and a final celebration with a replay button |
| Challenge | Chasing enemy accelerated without a limit and erased food | Later stages add a slow wandering neighbour; a bump briefly pauses movement and keeps all food |
| Readability | Near-black fog obscured the scene; trees could cover play | Bright clearing, spaced berries, trees at the edges, and a trail home |
| Movement | Required continuous pressing and depended on frame rate | Tap to walk, hold and drag to guide, or use arrows/WASD; speed uses elapsed time |
| Orientation | Little guidance about what to do next | Illustrated opening, collection feedback, home arrow, basket slots, and stage markers |
| Continuity | Returning to the menu discarded the session | Saves partial progress, position, carried berries, and the sound setting |
| Integration | Assets loaded at import time | Deferred loading; missing sprites receive drawn fallbacks |

## Progression

| Stage | Berries to deliver | Basket capacity | Visible reward |
| --- | ---: | ---: | --- |
| A cosy bed | 6 | 3 | A leaf bed and a resting little hedgehog |
| A little garden | 8 | 4 | Flowering berry plants outside the home |
| A picnic for friends | 10 | 5 | A shared picnic and a clear ending |

Each stage takes two trips with full baskets. Smaller deliveries also count.
There are exactly 24 berries in the adventure, and earned decorations remain
visible during later stages. The first stage introduces collection and home
delivery alone. The second introduces the neighbour and a lantern: collecting
the lantern enlarges pickup reach for 14 seconds, with a visible duration bar.
Darkness is not required to benefit from it.

The intended fit for ages 4–5 is a design judgment to validate with children:
small counts, illustrated actions, generous pickup distance, steady movement,
and a reachable ending. There is no countdown, game-over state, lost food, or
screen-filling red hit flash. The main instructions have visual equivalents;
an adult may still need to explain the opening once. There is no spoken tutorial.

## Controls and integration

- Tap/click a place to walk there; release and Hedgie keeps walking.
- Hold and drag to change the destination. One finger controls movement.
- Arrow keys or WASD move Hedgie; diagonal movement has the same speed.
- Pause button, P, or Space pauses. The large button resumes.
- The speaker button or M toggles the optional synthesized chimes.
- The exit icon or Escape returns to GameHub without quitting its display.
- Losing focus pauses play and clears held movement input.

The logical playfield is 800 × 600 and scales with letterboxing to other display
sizes. Pointer and touch coordinates use that same viewport. Portrait screens
are supported through scaling; landscape gives larger play targets.

Existing sprites are loaded from `assets/hungryHedgie/` using the filenames in
the original game. Missing images fall back to drawings. Sound is optional and
uses an already initialized 16-bit mixer; the game never reconfigures GameHub's
audio. `setup`, `update`, `draw`, `ret`, and `debug_main` remain available.
The game can also run directly with `python hungryHedgie.py`.

Desktop saves use the adjacent `hungryHedgie.save.json` file. Pygbag uses the
browser localStorage key `GameHub.hungryHedgie.v2`. A blocked save store permits
play without persistence. Malformed saves fall back to a valid state. Delivery
credit is committed before its animation, so closing during that animation
cannot duplicate food or lose delivery credit. Do not commit generated desktop
save files to the game repository.

## Verification performed

The enclosed 21 automated checks passed under Python 3.12 and pygame-ce 2.5.8
with SDL's headless video/audio drivers. `TEST_RESULTS.txt` contains the run.

- A complete adventure using tap events and simulated walking, including six
  full-basket deliveries, all three rewards, and the 24-berry ending.
- Conservation of food through collection, delivery, animation, and save/resume:
  field berries + carried berries + delivered berries = the stage goal.
- Capacity limits, repeated collisions, no negative carrying, and no repeated
  delivery while remaining at home.
- Movement at 15, 30, 60, and 120 FPS; diagonal speed; keyboard release.
- Tap and drag behavior, scaled touch input, ignored duplicate mouse events,
  and additional fingers leaving the active pointer alone.
- Pause/focus behavior, safe home, neighbour bumps, and lantern expiration.
- Desktop JSON saving, simulated browser storage and denied storage, malformed
  data, partial-session resume, delivery-time resume, and completed-game replay.
- Rendering the play, welcome, pause, reward, and ending screens at five sizes.
- Original asset-name loading with generated fixture images, and asset-free
  fallback rendering.
- The asynchronous GameHub entry point exits without quitting pygame and can
  be started again.

The welcome, play, and reward renderings were also visually inspected.

To rerun, install pygame or pygame-ce, open the package folder, and run:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -v
```

## Remaining playtest

The attachment contained only the Python module. This pass could not visually
verify the actual GameHub sprite set or run the deployed Pygbag build on a
phone/tablet. Browser storage was exercised through a simulated browser API.
Audio was exercised with a dummy mixer rather than assessed by listening.
Check these in the deployed game, then observe a young player: can they find
the first berry, recognize when the basket is full, and return home without
repeated prompting? Adjust collection radius, walking speed, or hints from
that observation. Automated completion does not establish age suitability.

## A repeatable quality-pass method

1. Trace a complete player journey and find where the software fails to explain
   or reward the user's action.
2. Correct behavior and data accounting before adding progression.
3. Add one concrete outcome for each repeated action and an attainable end.
4. Tune input, visibility, feedback, and consequences for the intended audience.
5. Preserve integration boundaries and define regression checks around real
   user journeys and invariants.
6. Deliver runnable code, evidence, and a short list of observations still
   needed in the real environment.

This is a proposed quality pass, not an automatic judgment that more features
always improve a game. Child playtesting should determine the next iteration.
