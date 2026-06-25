#!/usr/bin/env bash
# Build a release tarball of the NMA Mobile Credentials integration.
#
# Produces dist/nma-<version>.tar.gz that you can:
#   * upload to a GitHub release,
#   * scp into a Home Assistant box,
#   * drop into Studio Code Server / File editor,
#   * or attach to a chat message.
#
# Version comes from custom_components/nma/manifest.json.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
src="$root/custom_components/nma"
dist="$root/dist"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 required to read manifest.json" >&2
    exit 1
fi

version=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$src/manifest.json")
[[ -n "$version" ]] || { echo "ERROR: empty version in manifest.json" >&2; exit 1; }

mkdir -p "$dist"
out="$dist/nma-${version}.tar.gz"

# Build tarball relative to custom_components/ so it unpacks as `nma/`.
tar -C "$root/custom_components" \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    -czf "$out" \
    nma

ls -lh "$out"
echo
echo "Unpack on the target machine with:"
echo "  tar -xzf $(basename "$out") -C /config/custom_components/"
