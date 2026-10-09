#!/usr/bin/env python3
"""Build WasteGame into an itch.io-ready HTML5 ZIP. Run from any directory."""
from pathlib import Path
import argparse
import json
import hashlib
import struct
from urllib.parse import urlparse
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
GAME = ROOT / "WasteGame"
DIST = ROOT / "dist"


def remove_media_engagement_wait(index_path: Path) -> bool:
    """Remove only Pygbag's known UME wait from the generated HTML.

    A changed/unrecognized wait fails the build rather than shipping a ZIP that
    still stalls on iPad. This does not override browser audio autoplay rules.
    """
    html = index_path.read_text(encoding="utf-8")
    lines = html.splitlines(keepends=True)
    marker = "# test/wait if user media interaction required"
    starts = [i for i, line in enumerate(lines) if line.strip() == marker]
    if not starts:
        if "while not platform.window.MM.UME:" in html:
            raise RuntimeError(
                "Found an unrecognized UME wait in generated index.html; "
                "refusing to package a potentially blocked game."
            )
        print("UME interaction wait: already absent (nothing to patch).")
        return False
    if len(starts) != 1:
        raise RuntimeError("Multiple UME wait blocks found; cannot patch safely.")

    start = starts[0]
    indentation = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
    finish = next(
        (i for i in range(start + 1, len(lines))
         if lines[i].strip() == "# cleanup" and lines[i].startswith(indentation)),
        None,
    )
    if finish is None:
        raise RuntimeError("UME wait found, but the following '# cleanup' marker is missing.")
    block = "".join(lines[start:finish])
    expected = (
        "if not platform.window.MM.UME:",
        "while not platform.window.MM.UME:",
        "await asyncio.sleep(.1)",
    )
    if not all(item in block for item in expected):
        raise RuntimeError("UME block differs from expected Pygbag template; no changes made.")

    index_path.write_text("".join(lines[:start] + lines[finish:]), encoding="utf-8")
    print("Removed media-engagement wait from generated index.html.")
    return True


def _icon_dimensions(icon: Path) -> tuple[int, int]:
    """Inspect PNG header without requiring Pillow on builders' computers."""
    with icon.open("rb") as stream:
        header = stream.read(24)
    if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n"
            or header[12:16] != b"IHDR"):
        raise RuntimeError(f"{icon} is not a valid PNG file (bad PNG header).")
    return struct.unpack(">II", header[16:24])


def _standalone_url() -> str | None:
    """Optional public standalone site to link to when itch.io embeds the game."""
    config = ROOT / "home_screen_url.txt"
    if not config.exists():
        return None
    lines = [line.strip() for line in config.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return None
    if len(lines) != 1:
        raise RuntimeError("home_screen_url.txt must contain exactly one URL.")
    parsed = urlparse(lines[0])
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError("home_screen_url.txt must contain a public https:// URL.")
    return lines[0]


def prepare_ipad_web_app(web: Path) -> None:
    """Add real Home Screen icons, PWA metadata and an unobtrusive install tip.

    Install info is only directly useful on the *top-level* game URL. On itch.io,
    the iframe can instead link to an optional standalone game URL.
    """
    index_path = web / "index.html"
    html = index_path.read_text(encoding="utf-8")

    # Fail instead of silently shipping the default 'W' favicon. The icon is
    # included with this build kit; users can replace app_icon.png at any time.
    supplied_icon = ROOT / "app_icon.png"
    if not supplied_icon.is_file():
        raise RuntimeError(
            "Missing app_icon.png beside build_itch.py. Copy the supplied icon "
            "into this folder or provide your own square PNG. Build not packaged."
        )
    width, height = _icon_dimensions(supplied_icon)
    if width != height or width < 180:
        raise RuntimeError("app_icon.png must be square and at least 180x180 pixels.")

    # Stable filename for iPad's root-directory icon discovery; versioned URLs
    # invalidate normal HTTP caches after a new icon is supplied.
    for name in ("app_icon.png", "apple-touch-icon.png", "favicon.png"):
        destination = web / name
        if supplied_icon.resolve() != destination.resolve():
            shutil.copy2(supplied_icon, destination)
    icon_hash = hashlib.sha256(supplied_icon.read_bytes()).hexdigest()[:12]

    # Reset our own injected section to support --skip-build / repeated builds.
    html = re.sub(
        r"[ \t]*<!-- WASTEGAME_HEAD_START -->.*?<!-- WASTEGAME_HEAD_END -->[ \t]*\n?",
        "", html, flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(
        r"[ \t]*<!-- WASTEGAME_TIP_START -->.*?<!-- WASTEGAME_TIP_END -->[ \t]*\n?",
        "", html, flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove Pygbag defaults or earlier versions' metadata. Apple will use the
    # apple-touch-icon tag in preference to a manifest icon on iPadOS.
    html = re.sub(r"[ \t]*<meta\s+name=[\"']viewport[\"'][^>]*>[ \t]*\n?", "", html,
                  flags=re.IGNORECASE)
    for name in ("apple-mobile-web-app-capable", "apple-mobile-web-app-status-bar-style",
                 "apple-mobile-web-app-title", "theme-color"):
        html = re.sub(
            rf"[ \t]*<meta\s+name=[\"']{name}[\"'][^>]*>[ \t]*\n?",
            "", html, flags=re.IGNORECASE,
        )
    for rel in ("manifest", "apple-touch-icon", "icon"):
        html = re.sub(
            rf"[ \t]*<link\s+rel=[\"']{rel}[\"'][^>]*>[ \t]*\n?",
            "", html, flags=re.IGNORECASE,
        )
    # Previous kit script was injected without our unique marker.
    html = re.sub(
        r"[ \t]*<script\s+src=[\"']install_hint\.js(?:\?[^\"']*)?[\"']\s+defer\s*></script>[ \t]*\n?",
        "", html, flags=re.IGNORECASE,
    )

    head = re.search(r"<head(?:\s[^>]*)?>", html, flags=re.IGNORECASE)
    if not head:
        raise RuntimeError("Generated index.html has no HTML <head> element")

    additions = f"""
    <!-- WASTEGAME_HEAD_START -->
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <meta name="apple-mobile-web-app-title" content="WasteGame">
    <meta name="theme-color" content="#173d35">
    <link rel="icon" type="image/png" href="favicon.png?v={icon_hash}">
    <link rel="apple-touch-icon" sizes="{width}x{height}" href="apple-touch-icon.png?v={icon_hash}">
    <link rel="manifest" href="manifest.webmanifest?v={icon_hash}">
    <!-- WASTEGAME_HEAD_END -->
"""
    html = html[:head.end()] + additions + html[head.end():]

    css = """
    /* WasteGame iPad touch behavior. iPadOS system gestures cannot be blocked. */
    html, body { width: 100%; height: 100%; overflow: hidden; overscroll-behavior: none; }
    body { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
    canvas.emscripten { touch-action: none; -webkit-user-select: none;
                        user-select: none; -webkit-touch-callout: none; }
"""
    if "/* WasteGame iPad touch behavior." not in html:
        if not re.search(r"</style\s*>", html, flags=re.IGNORECASE):
            raise RuntimeError("Generated index.html has no CSS </style> tag")
        html = re.sub(r"</style\s*>", lambda _: css + "\n    </style>", html,
                      count=1, flags=re.IGNORECASE)

    manifest = {
        "id": "./",
        "name": "WasteGame",
        "short_name": "WasteGame",
        "description": "Mini-games with a light environmental theme",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#173d35",
        "theme_color": "#173d35",
        "icons": [{"src": f"app_icon.png?v={icon_hash}", "sizes": f"{width}x{height}",
                   "type": "image/png", "purpose": "any maskable"}],
    }
    (web / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (web / ".nojekyll").touch()

    hint_source = ROOT / "install_hint.js"
    if not hint_source.is_file():
        raise RuntimeError("install_hint.js is missing beside build_itch.py")
    shutil.copy2(hint_source, web / "install_hint.js")
    hint_hash = hashlib.sha256(hint_source.read_bytes()).hexdigest()[:12]
    url_json = json.dumps(_standalone_url()).replace("<", "\\u003c")
    hint_tag = f"""
    <!-- WASTEGAME_TIP_START -->
    <script>window.WASTEGAME_STANDALONE_URL = {url_json};</script>
    <script src="install_hint.js?v={hint_hash}" defer></script>
    <!-- WASTEGAME_TIP_END -->
"""
    if not re.search(r"</body\s*>", html, flags=re.IGNORECASE):
        raise RuntimeError("Generated index.html has no </body> tag")
    html = re.sub(r"</body\s*>", lambda match: hint_tag + match.group(), html,
                  count=1, flags=re.IGNORECASE)
    index_path.write_text(html, encoding="utf-8")
    print(f"Home Screen icon: {supplied_icon.name} ({width}x{height}), fingerprint {icon_hash}.")
    print("Apple touch icon, root fallback icon, manifest and browser favicon: included.")
    print("Home Screen hint: included for a direct Safari/iPad game page.")
    if _standalone_url():
        print(f"itch.io iframe: shows link to standalone version {_standalone_url()}")
    else:
        print("itch.io iframe: tip hidden (set home_screen_url.txt to show a standalone-game link).")


def main():
    parser = argparse.ArgumentParser(description="Build WasteGame for itch.io")
    parser.add_argument("--skip-build", action="store_true", help="Repackage an existing build/web (for testing)")
    args = parser.parse_args()
    if not (GAME / "main.py").is_file():
        parser.error("WasteGame/main.py is missing")
    if not args.skip_build:
        if shutil.which("python") is None and not sys.executable:
            parser.error("Python not found")
        print("Building browser game with Pygbag...", flush=True)
        subprocess.run([sys.executable, "-m", "pygbag", "--build", str(GAME)], check=True, cwd=ROOT)
    web = GAME / "build" / "web"
    if not (web / "index.html").is_file():
        raise SystemExit(f"Missing {web / 'index.html'}; build failed or produced unexpected output")
    # Patch BEFORE packaging, so the itch.io ZIP contains the corrected index.
    remove_media_engagement_wait(web / "index.html")
    prepare_ipad_web_app(web)
    files = [p for p in web.rglob("*") if p.is_file()]
    if not files:
        raise SystemExit("No web files found")
    DIST.mkdir(exist_ok=True)
    destination = DIST / "WasteGame_itch_io.zip"
    temp = destination.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for p in sorted(files):
                archive.write(p, p.relative_to(web).as_posix())
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    print(f"Ready: {destination}")
    print(f"Packaged {len(files)} files; index.html is at ZIP root.")

if __name__ == "__main__":
    main()
