#!/usr/bin/env bash
# Install (or refresh) the NMA Mobile Credentials integration into an existing
# Home Assistant config directory.
#
# Usage:
#   scripts/install.sh /path/to/homeassistant/config
#
# Examples:
#   scripts/install.sh ~/homeassistant                       # HA Core in a venv
#   scripts/install.sh /Volumes/config                       # HA OS via Samba
#   scripts/install.sh /var/lib/homeassistant                # HA Container on Linux
#
# The script:
#   * verifies the target looks like an HA config dir (must contain configuration.yaml)
#   * creates <target>/custom_components/nma/ if needed
#   * rsyncs the integration sources, deleting stale files
#   * reminds you to restart Home Assistant
set -euo pipefail

usage() {
    cat <<EOF
Usage: $(basename "$0") <homeassistant-config-dir>

The config directory is the one that contains configuration.yaml.
EOF
    exit 64
}

[[ $# -eq 1 ]] || usage

target="${1%/}"
src="$(cd "$(dirname "$0")/.." && pwd)/custom_components/nma"

if [[ ! -d "$src" ]]; then
    echo "ERROR: source not found at $src" >&2
    exit 1
fi

if [[ ! -d "$target" ]]; then
    echo "ERROR: target $target does not exist" >&2
    exit 2
fi

if [[ ! -f "$target/configuration.yaml" ]]; then
    echo "ERROR: $target does not look like a Home Assistant config directory" >&2
    echo "       (configuration.yaml not found)" >&2
    exit 3
fi

dest="$target/custom_components/nma"
mkdir -p "$dest"

echo "==> Copying $src -> $dest"
rsync -a --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "$src/" "$dest/"

echo
echo "Done. Restart Home Assistant, then:"
echo "  Settings -> Devices & Services -> Add Integration -> NMA Mobile Credentials"
