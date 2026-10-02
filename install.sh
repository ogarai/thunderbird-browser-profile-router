#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Installs the native messaging host for the current user (Linux and macOS)
# and builds the add-on package (browser-profile-router.xpi).
#
#   ./install.sh                 helper only
#   ./install.sh --link-handler  also route links opened by other add-ons
#                                (e.g. Thunderbird Conversations); opt-in
#                                because it changes Thunderbird's settings
set -eu

LINK_HANDLER=
case "${1:-}" in
  "") ;;
  --link-handler) LINK_HANDLER=1 ;;
  *) echo "usage: $0 [--link-handler]" >&2; exit 2 ;;
esac

NAME=browser_profile_router
EXTENSION_ID=browser-profile-router@garai.ca
ROOT=$(cd "$(dirname "$0")" && pwd)
HOST="$ROOT/host/profile_router_host.py"

case "$(uname -s)" in
  Darwin)
    DIRS="$HOME/Library/Mozilla/NativeMessagingHosts
$HOME/Library/Application Support/Mozilla/NativeMessagingHosts" ;;
  *)
    DIRS="$HOME/.mozilla/native-messaging-hosts
$HOME/.thunderbird/native-messaging-hosts" ;;
esac

chmod +x "$ROOT"/host/*.py

echo "$DIRS" | while IFS= read -r dir; do
  mkdir -p "$dir"
  cat > "$dir/$NAME.json" <<EOF
{
  "name": "$NAME",
  "description": "Opens links in a specific browser profile",
  "path": "$HOST",
  "type": "stdio",
  "allowed_extensions": ["$EXTENSION_ID"]
}
EOF
  echo "Installed host manifest: $dir/$NAME.json"
done

rm -f "$ROOT/browser-profile-router.xpi"
(cd "$ROOT/extension" && zip -qr "$ROOT/browser-profile-router.xpi" .)
echo "Built add-on: $ROOT/browser-profile-router.xpi"

echo
if [ -z "$LINK_HANDLER" ]; then
  echo "Optional: to route links opened by other add-ons (e.g. Thunderbird"
  echo "Conversations), quit Thunderbird and run: $0 --link-handler"
elif ! python3 "$ROOT/host/register_handler.py"; then
  echo "Thunderbird's link handler was NOT registered (see above). Fix that and run:"
  echo "  $ROOT/host/register_handler.py"
fi
