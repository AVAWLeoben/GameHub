# Tank Battle Asset Pack

Original side-view tank art, built as separate parts so everything can rotate.
Free to use in any project.

## What's inside

| Folder | Contents |
|---|---|
| `png/` | Game-ready PNGs, rendered at 2x (retina) |
| `svg/` | Same sprites as vectors, to edit or re-export |
| `rig/tank_rig.json` | The joint/skeleton data (the important file) |
| `preview.html` | Open in a browser: pick tank/colour/weapon, drag sliders to rotate joints, press FIRE |
| `preview_*.png` | Overview images |

**Tanks (3):** `scout` (light), `heavy`, `artillery`.
**Colours (4):** `green`, `blue`, `red`, `wreck` (grey burnt-out version for destroyed tanks). Only hull and turret change colour.
**Weapons (5, swappable on any tank):** `cannon`, `twin_cannon`, `mortar`, `rocket_pod`, `plasma_gun`.
**Projectiles:** shell, bomb, rocket, plasma_bolt.
**FX:** explosion (8 frames), muzzle flash (3), smoke puff (4), crater decal, 4 debris chunks. Frames are also stitched into `*_sheet.png`.

## Skeleton (per tank)

```
hull            hinge, tilts to follow terrain (e.g. -30..30)
├─ turret       hinge, tiny recoil kick (optional)
│  └─ weapon_slot   hinge, AIM joint  (-85..15 etc.)
│     └─ weapon     slides back along -x for recoil
└─ track
   └─ wheel_0..n    hinge, continuous spin
```

## How to read `tank_rig.json`

- **Units** are logical pixels. PNGs are 2x, so multiply sizes/positions by `pngScale` (2), or set sprite scale to 0.5 in your engine.
- **`pivot`** = point inside the sprite that is the joint (rotation centre).
- **`position`** = where that pivot sits, measured from the **parent's pivot**.
- **Angles:** degrees, clockwise-positive on screen, 0 = pointing right, **-90 = straight up**. This matches Phaser, Unity UI, CSS and Canvas. In Godot/Unity-world (y-up) flip the sign.
- **Facing left:** mirror the whole tank root (scale.x = -1). Aim angles stay the same.
- **`weapon_slot`** is where any weapon plugs in. A weapon's usable aim range is the *intersection* of the slot's `rotation` range and the weapon's own `aimRange` (the mortar is limited to high lobs).
- **`muzzle`** (and `muzzles` for multi-barrel weapons) = projectile spawn point in weapon sprite pixels. Rotate it by the weapon's world angle.
- **`groundContacts`** = front/back ground points relative to the hull pivot. Sample terrain height under both, then set the hull rotation to `atan2(dy, dx)`.
- **`drawOrder`** lists a safe flat draw order if your engine has no hierarchy.

## Phaser 3 sketch

```js
// one container per node, nested exactly like rig.tanks[id].nodes
const c = scene.add.container(x + n.position[0], y + n.position[1]);
const s = scene.add.image(0, 0, key).setScale(0.5)
        .setOrigin(n.pivot[0] * 2 / tex.width, n.pivot[1] * 2 / tex.height);
c.add(s);               // children are added to their parent's container
slotContainer.angle = Phaser.Math.Clamp(aimDeg, lo, hi);
```

## Wheel/tread note

Wheels spin by rotation only; tread teeth on the track are static. For a driving effect, spin the wheels at `speed / radius`.
