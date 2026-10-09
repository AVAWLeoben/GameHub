#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Override interpreter if necessary: PYTHON=/usr/bin/python3.12 sh build_itch.sh
if [ -n "${PYTHON:-}" ]; then
    exec "$PYTHON" prepare_build_env.py "$@"
fi

# Try a few common Python executable names. Only select Python >= 3.10.
for candidate in python3 python3.13 python3.12 python3.11 python3.10 python3.14 python3.15 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        exec "$candidate" prepare_build_env.py "$@"
    fi
done

printf '%s\n' '[ERROR] Python 3.10+ was not found.' >&2
printf '%s\n' 'Install Python 3, Python venv and pip, then rerun this script.' >&2
printf '%s\n' 'On Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip' >&2
exit 1
