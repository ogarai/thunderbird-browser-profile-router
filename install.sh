#!/bin/sh
# Installs the native messaging host for the current user (Linux and macOS)
# and builds the add-on package (browser-profile-router.xpi).
set -eu

NAME=browser_profile_router
EXTENSION_ID=browser-profile-router@local
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

# Route links opened by other add-ons (e.g. Thunderbird Conversations).
if ! python3 "$ROOT/host/register_handler.py"; then
  echo "Thunderbird's link handler was NOT registered (see above). Fix that and run:"
  echo "  $ROOT/host/register_handler.py"
fi
