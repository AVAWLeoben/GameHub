# WasteGame — one-command builds on Windows and Linux

These scripts rebuild your Pygbag browser version for itch.io or for static website hosting.
No Conda environment, manual pip commands or global `pygame` installation is needed.

## Prerequisite on each computer

Install **Python 3.10 or newer**. It must include `venv` and `pip` (`ensurepip`).
An internet connection is needed to download dependencies **on first use**.
The scripts can install Pygbag and pygame-ce, but **cannot install Python itself**.

- **Windows:** Install Python from <https://www.python.org/downloads/> and select **Add Python to PATH** (or use the `py` launcher). Double-click `build_itch.bat`.
- **Ubuntu/Debian Linux:** `sudo apt install python3 python3-venv python3-pip` if those components are not already present. Then run `sh build_itch.sh` (or `./build_itch.sh`).
- **Other Linux distributions:** Install Python 3, venv and pip through your package manager, then run `sh build_itch.sh`.
- **macOS:** The same `sh build_itch.sh` launcher also works with Python 3.10+ installed.

## Folder layout

Put *all five* build files together, next to the existing game folder:

```text
WasteGame-project/
├── build_itch.bat           <- Windows launcher
├── build_itch.sh            <- Linux/macOS launcher
├── prepare_build_env.py     <- sets up/reuses private environment
├── requirements-build.txt   <- pinned build tool versions
├── build_itch.py            <- actual Pygbag build + iPad patches + ZIP
├── app_icon.png             <- included 512 x 512 hedgehog icon (replaceable)
├── install_hint.js          <- iPad install reminder
├── home_screen_url.txt      <- optional URL for itch.io iframe users
├── WasteGame/
│   ├── main.py
│   ├── assets/                 <- restore your real assets
│   └── ...other .py files
└── dist/                     <- created automatically
```

Keep your own game files and asset paths; these scripts do not change them.

## First run

**Windows:** Double-click `build_itch.bat`, or run from Command Prompt:

```bat
build_itch.bat
```

**Linux/macOS:** From the project folder:

```sh
sh build_itch.sh
```

On the **first run**, `prepare_build_env.py` creates `.venv-build/`, then installs the versions in `requirements-build.txt` into that environment using pip. It never modifies the global Python installation and does not require Conda, `sudo pip`, or `pip --break-system-packages`.

On **later runs**, the script checks the installed versions and skips installation when both match.

After success, upload **`dist/WasteGame_itch_io.zip`** to itch.io. The ZIP contains `index.html` at its root. You can also extract its **contents** for static site hosting.

## Preserved changes from the previous build scripts

- Uses Pygbag to generate `WasteGame/build/web/`.
- Removes the known Pygbag 0.9.2 `MM.UME` media-engagement wait from generated `index.html`, without modifying your game's original files.
- Adds iPad Home Screen/standalone web app metadata, touch-safe canvas CSS and `manifest.webmanifest`.
- Copies the supplied `app_icon.png` and fails the build if this square PNG is missing, rather than silently using the generated W favicon.
- Adds `.nojekyll` for GitHub Pages compatibility.
- Packages the *contents* of `build/web/` into `dist/WasteGame_itch_io.zip`.

**Note:** Browser media/autoplay restrictions and iPadOS edge gestures cannot be disabled by the build script.

## Optional options

Rebuild the environment from scratch if it gets corrupted:

```sh
sh build_itch.sh --recreate-env
```

Windows equivalent:

```bat
build_itch.bat --recreate-env
```

Patch and re-ZIP existing `WasteGame/build/web/` without running Pygbag:

```sh
sh build_itch.sh --skip-build
```

Choose a specific Python installation:

```sh
PYTHON=/usr/bin/python3.12 sh build_itch.sh
```

On Windows Command Prompt:

```bat
set "PYTHON=C:\Path\To\Python312\python.exe"
build_itch.bat
```

To force updated build tool versions later, edit **`requirements-build.txt`** and rebuild. Pygbag is intentionally pinned at **0.9.2** to match the known HTML startup patch. Updating it may require adjusting that patch.

## Troubleshooting

| Problem | What to do |
|---|---|
| `Python 3.10+ not found` | Install a supported Python or set the `PYTHON` environment variable to a valid interpreter. |
| `No module named venv`, `ensurepip` missing | On Debian/Ubuntu, install `python3-venv` and `python3-pip`. Re-run. |
| `pip install` fails | Check internet/proxy restrictions or wheel compatibility. See the complete pip output. |
| `.venv-build` corrupt / Python moved | Delete `.venv-build/` or rerun with `--recreate-env`. |
| `WasteGame/main.py is missing` | Put the launchers beside the `WasteGame/` folder. |
| Images/sounds missing in browser | Ensure the original game `assets/` directory exists. |
| Pygbag generates different HTML | The UME patch rejects unrecognized templates; check the installed Pygbag version and update the patch if needed. |

**Important:** The build dependencies are for the **host computer**, not an automatic guarantee that Python dependencies inside your game are available inside browser WebAssembly. The game needs to remain Pygbag compatible.

**Privacy/version-control tip:** `.venv-build/`, `WasteGame/build/` and `dist/` are generated; exclude them from Git. You can recreate them on any compatible computer.

## Quiet iPad Home Screen reminder (new)

The build includes `install_hint.js` and inserts it into the generated `index.html`.
On an iPad **in a browser tab on the direct game page**, it displays a small
nonmodal notice 6 seconds after opening: **Share → Add to Home Screen → Open as Web App**.
The message disappears after 18 seconds or when closed; closing disables it
for that browser permanently. If it times out, it does not return for 21 days.
It does **not** appear in the installed web app or on desktop. In an itch.io
iframe, it shows a link to the direct web app only if you set `home_screen_url.txt`;
it cannot install or rebrand the itch.io wrapper itself. English and German messages are chosen by browser language.

The HTML/JS can only explain the steps. Safari does not provide a JavaScript
API to open the native Add to Home Screen sheet or block iPadOS system swipes.
To adjust the timing, edit constants near the top of `install_hint.js`.

**Important:** Keep `install_hint.js` beside `build_itch.py` when you move the
project. The Windows `.bat` and Linux `.sh` launchers are otherwise unchanged.

For an explanation of the original icon/reminder failure and the new test flag, see **README_INSTALL_HINT.md**.
