# WasteKart 2.1.1 — Desert Cup 1/4: Dusty Drive Moving Train

This GitHub patch adds **one new track and its train hazard**. Other 15 courses
(including Clover Crossing bridge support) are unchanged.

## Installation

Merge the `WasteGame/` directory into the GameHub repo. In particular,
replace `WasteGame/wasteKart.py` and merge all supplied track files into
`WasteGame/assets/WasteKart/Tracks/Cups/Cup3/`.

## Provided artwork

* `track_01.png` is an **unmodified byte-for-byte copy** of `dusty_drive_track.png`.
* `track_01.mask.png` is an **unmodified byte-for-byte copy** of
  `dusty_drive_road_mask.png`.
* `dusty_drive_tunnel_overlay.png`, `train_manifest.json`, and all supplied
  train sprites are copied unmodified.
* `track_01.json` is generated from the supplied road mask's actual medial
  centerline and contains the train asset paths and 4 checkpoints.

## Gameplay

* During countdown and racing, a five-car train travels west (right-to-left)
  along the y=330 railway.
* Center spacing, tunnel x-range, sprites and portal/crossing information
  come from `train_manifest.json`.
* The locomotive and wagons disappear beneath the supplied tunnel overlay.
* On collision, a kart **stops and rotates 360 degrees over 1.45 seconds**,
  with yellow stars; then it accelerates along its original drawn route.
* The train is unaffected, and another hit cannot restart the spin until the
  safety cooldown expires.
* Train collisions affect actual racers independently of the optional
  kart-to-kart interactions toggle. Session ghosts replay recorded train hits
  at their original times rather than colliding with the current train.
* Crossing lights blink red as the train approaches each road crossing.
* Tunnel art is cropped to its opaque region before scaling, to reduce blit
  cost during Pygbag races.
* The train freezes when paused. It resets once per race, not per drawing turn.
* The route/checkpoint engine and scoring are otherwise unchanged.

## Known limit

The track checkpoint coordinates are metadata only: the current game does not
verify that a child passes checkpoints in order. The train does not change that.
Actual browser/iPad performance should still be verified on device.
