#!/usr/bin/env python3
"""Sanity-check the Pygbag site before uploading to GitHub Pages."""
from pathlib import Path
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'WasteGame' / 'build' / 'web'
ZIP = ROOT / 'dist' / 'WasteGame_itch_io.zip'


def check() -> None:
    required = ('index.html', 'app_icon.png', 'apple-touch-icon.png',
                'favicon.png', 'manifest.webmanifest', 'install_hint.js', '.nojekyll')
    for name in required:
        if not (WEB / name).is_file():
            raise ValueError(f'Missing web file: {name}')
    html = (WEB / 'index.html').read_text(encoding='utf-8')
    if 'while not platform.window.MM.UME:' in html:
        raise ValueError('The unwanted iPad UME wait is still in index.html')
    if not all(x in html for x in ('apple-touch-icon.png', 'manifest.webmanifest', 'install_hint.js')):
        raise ValueError('Generated index.html does not reference iPad icon, manifest and hint')
    archive_match = re.search(r'(?m)^\s*apk\s*=\s*"([^"]+\.apk)"', html)
    if archive_match is None:
        raise ValueError('Cannot identify the Pygbag browser bundle in generated index.html')
    browser_bundle = archive_match.group(1)
    bundle_path = WEB / browser_bundle
    if not bundle_path.is_file() or bundle_path.stat().st_size == 0:
        raise ValueError(f'Pygbag browser bundle not found or empty: {browser_bundle}')
    manifest = json.loads((WEB / 'manifest.webmanifest').read_text(encoding='utf-8'))
    if manifest.get('display') != 'standalone':
        raise ValueError('Manifest is not configured for standalone app display')
    if not ZIP.is_file():
        raise ValueError(f'Missing local itch.io ZIP: {ZIP}')
    with zipfile.ZipFile(ZIP) as archive:
        names = set(archive.namelist())
        if not (set(required) | {browser_bundle}).issubset(names):
            raise ValueError('The itch.io ZIP is missing required web files')
    print(f'Build verified: {browser_bundle} ({bundle_path.stat().st_size / 1e6:.1f} MB), icons, hint, manifest, and itch.io ZIP')


if __name__ == '__main__':
    try:
        check()
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        sys.exit(1)
