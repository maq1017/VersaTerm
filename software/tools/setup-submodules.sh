#!/usr/bin/env bash
# Initializes/updates the git submodules used by the VersaTerm build and
# re-applies the local overrides that a plain `git submodule update` would
# otherwise wipe out:
#
#   1. lib/pico-sdk/lib/tinyusb is bumped to TinyUSB 0.18.0. The pico-sdk
#      version pinned by this repo (1.3.1) ships TinyUSB 0.12.0, which has
#      keyboard-enumeration issues through (some) USB hubs. This override
#      can't be recorded as a normal submodule pin because it's a submodule
#      nested two levels deep (VersaTerm -> pico-sdk -> tinyusb), so it has
#      to be reapplied by hand after every submodule sync.
#
#   2. lib/pico-sdk/tools/FindPioasm.cmake gets a
#      "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" argument added to its pioasm
#      ExternalProject_Add() calls. CMake 4.x refuses to configure the
#      vendored pioasm sources (both pico-sdk's own copy and PicoDVI's)
#      because their CMakeLists.txt declare `cmake_minimum_required` below
#      3.5, which CMake 4 removed support for entirely. Harmless with older
#      CMake; required with CMake >= 4.
#
# Run this from anywhere inside the repo, e.g.:
#   software/tools/setup-submodules.sh

set -euo pipefail

REPO_ROOT=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
cd "$REPO_ROOT"

TINYUSB_COMMIT=86ad6e56c1700e85f1c5678607a762cfe3aa2f47  # TinyUSB 0.18.0

echo "==> Syncing submodules (recursive)"
git submodule update --init --recursive

echo "==> Bumping lib/pico-sdk/lib/tinyusb to ${TINYUSB_COMMIT} (TinyUSB 0.18.0)"
(
    cd software/lib/pico-sdk/lib/tinyusb
    git fetch --quiet origin "$TINYUSB_COMMIT" 2>/dev/null || true
    git checkout --quiet "$TINYUSB_COMMIT"
    git submodule update --init --recursive
)

FIND_PIOASM=software/lib/pico-sdk/tools/FindPioasm.cmake
if ! grep -q "CMAKE_POLICY_VERSION_MINIMUM" "$FIND_PIOASM"; then
    echo "==> Patching $FIND_PIOASM for CMake 4.x compatibility"
    python3 - "$FIND_PIOASM" <<'PYEOF'
import sys
path = sys.argv[1]
marker = 'CMAKE_CACHE_ARGS "-DPIOASM_EXTRA_SOURCE_FILES:STRING=${PIOASM_EXTRA_SOURCE_FILES}"'
patch = marker + '\n                CMAKE_ARGS "-DCMAKE_POLICY_VERSION_MINIMUM=3.5"'
with open(path) as f:
    text = f.read()
if marker not in text:
    sys.exit(f"error: could not find insertion point in {path}")
text = text.replace(marker, patch, 1)
with open(path, "w") as f:
    f.write(text)
PYEOF
else
    echo "==> $FIND_PIOASM already patched"
fi

echo "==> Done. software/lib/pico-sdk will show as 'modified content' in git status -- that's expected."
