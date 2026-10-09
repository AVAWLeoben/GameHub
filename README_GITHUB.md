# GameHub: GitHub Pages deployment

This is an **overlay for your existing WasteGame source**, not a complete playable game. It includes the latest Windows/Linux build scripts, Hedgehog icon, iPad startup patch, standalone web app manifest, and optional Add-to-Home-Screen reminder. Your original assets are **not** included.

## 1. Put the files into your empty GameHub repository

Clone your `GameHub` repository (GitHub Desktop or `git clone`), then copy **the contents** of this kit into the repository root. Also copy your **current working** `WasteGame/` directory, **including its complete `assets/` directory**. Keep your current game files rather than replacing them with an older copy from this conversation.

Expected layout:

```text
GameHub/
├── .github/workflows/deploy.yml
├── .gitignore
├── build_itch.py
├── build_itch.sh
├── build_itch.bat
├── prepare_build_env.py
├── requirements-build.txt
├── verify_web_build.py
├── app_icon.png
├── install_hint.js
├── home_screen_url.txt
└── WasteGame/
    ├── main.py
    ├── GUI.py
    ├── wasteHockey.py
    ├── wastePaint.py
    ├── assets/
    │   └── ... your images, sound, sprites ...
    └── ... other Python files ...
```

Do **not** upload `WasteGame/build/`, `.venv-build/`, `dist/`, `wastegame.apk` or `WasteGame.apk`. `.gitignore` ignores those. Don't upload a ZIP of the source into the repository and expect GitHub to extract it: the files need to be present as ordinary repository files.

## 2. Enable GitHub Pages

In your repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**. (If Pages is already configured, check that GitHub Actions is selected.) A public repository works with GitHub Free.

## 3. Push your game source and this kit to the `main` branch

Using Git:

```bash
git add .
git commit -m "Publish WasteGame via GitHub Pages"
git push origin main
```

If using GitHub Desktop, commit and push the changes instead. Each push to `main` will run the Pages workflow. You can also trigger it manually in **Actions → Build and deploy GameHub → Run workflow**.

The workflow: installs Python 3.12; creates/reuses a virtual environment; installs the pinned Pygbag and pygame-ce; builds `WasteGame`; removes the browser media-engagement wait; adds the custom icon, manifest and iPad hint; verifies the website; publishes `WasteGame/build/web` via the GitHub Pages artifact API. The generated APK-like asset bundle (even at ~107 MB) is **never added to Git history**.

## 4. Open the website

Your URL will be:

`https://YOUR-GITHUB-USERNAME.github.io/GameHub/`

The actual username is the **GitHub account or organization owning the repository**, which may differ from your itch.io username. After the Actions run turns green, the precise live URL is visible in the deployment summary and **Settings → Pages**.

Open that **direct URL in Safari** on an iPad to use the Home Screen icon and installation hint. Add to Home Screen. If you already installed an older shortcut, remove and reinstall it to clear cached artwork.

For reminder troubleshooting, open the direct URL with `?show_install_hint=1`. The normal tip is intentionally short and infrequent. It does not appear when already installed. Browsers may still enforce audio interaction requirements, and iPadOS system gestures cannot be disabled.

## 5. Link from itch.io (optional)

After Pages is live, replace the comments in `home_screen_url.txt` with **one line** containing the real full Pages URL and rebuild your itch.io ZIP on your computer with `sh build_itch.sh` (Linux) or `build_itch.bat` (Windows). Upload that ZIP to itch.io. Then the embedded itch.io game can show a subtle link to the standalone installation page. You cannot set the outer itch.io page's Home Screen icon from inside the game iframe.

## Notes and limits

- GitHub Pages published sites are currently limited to **1 GB** and have a soft **100 GB/month** bandwidth limit. GitHub Pages upload/deploy via Actions is the correct route for a generated ~107 MB file; normal Git commits reject individual files larger than 100 MiB.
- Source assets must be committed, unless your workflow explicitly downloads them. Any single asset over the regular Git file limit needs a different handling strategy.
- The Games/asset dependencies still need a real-browser test. The kit has been syntax and artifact-processing checked, but cannot verify a live deployment without your actual asset folder and GitHub credentials.
- Both `.github/workflows/deploy.yml` and `.nojekyll` are dotfiles: they should not get lost when copying from the ZIP.
- You can keep using the existing local itch.io builder. The Pages workflow deploys web files directly; it does not publish the local itch.io ZIP as a website.
