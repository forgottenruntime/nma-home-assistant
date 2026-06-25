#!/usr/bin/env bash
# Install (or refresh) the NMA Mobile Credentials integration on a REMOTE Home
# Assistant box over SSH. Assumes you can `ssh <host>` and that /config is the
# HA configuration directory on that box.
#
# Usage:
#   scripts/install-remote.sh <ssh-host> [remote-config-path]
#
# Examples:
#   # HA OS / Supervised with the official SSH & Web Terminal add-on
#   #   (default user is root@homeassistant.local, port 22222)
#   scripts/install-remote.sh root@homeassistant.local:22222
#
#   # HA Core / Container on a regular Linux box with HA in ~/homeassistant
#   scripts/install-remote.sh user@homeserver ~/homeassistant
#
# Defaults to /config (the path used by HA OS, Supervised, and Container).
set -euo pipefail

usage() {
    cat <<EOF
Usage: $(basename "$0") <ssh-host> [remote-config-path]

  <ssh-host>            Anything you can pass to ssh, e.g. user@host or
                        user@host:port (this script converts :port to -p port).
  [remote-config-path]  Defaults to /config.
EOF
    exit 64
}

[[ $# -ge 1 && $# -le 2 ]] || usage

raw_host="$1"
remote_config="${2:-/config}"

# Split host:port into "host" + "-p port" for ssh/rsync.
host="$raw_host"
port_opt=""
if [[ "$raw_host" == *:* ]]; then
    host="${raw_host%:*}"
    port="${raw_host##*:}"
    port_opt="-p $port"
fi

src="$(cd "$(dirname "$0")/.." && pwd)/custom_components/nma"
[[ -d "$src" ]] || { echo "ERROR: source not found at $src" >&2; exit 1; }

# Sanity check the remote target before we touch anything.
echo "==> Checking remote $host:$remote_config ..."
# shellcheck disable=SC2029
ssh ${port_opt} "$host" "test -f $remote_config/configuration.yaml" \
    || { echo "ERROR: $remote_config/configuration.yaml not found on $host" >&2; exit 2; }

echo "==> Ensuring $remote_config/custom_components/nma exists ..."
# shellcheck disable=SC2029
ssh ${port_opt} "$host" "mkdir -p $remote_config/custom_components/nma"

echo "==> Rsyncing integration ..."
rsync_ssh="ssh"
[[ -n "$port_opt" ]] && rsync_ssh="ssh $port_opt"
rsync -av --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    -e "$rsync_ssh" \
    "$src/" "$host:$remote_config/custom_components/nma/"

cat <<EOF

Done. Restart Home Assistant. From the HA UI:
  Settings -> System -> Restart -> Restart Home Assistant
Or from the same SSH session, on HA OS / Supervised:
  ha core restart
EOF
