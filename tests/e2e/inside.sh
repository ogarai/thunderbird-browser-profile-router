#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Runs inside the sandbox set up by run.sh.
set -eu

R=/work/repo
E=$R/tests/e2e
P=/work/profile
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" /work/bin /work/results "$P/extensions"
chmod 700 "$XDG_RUNTIME_DIR"

# Fake Chrome Canary with two signed-in profiles.
cat > /work/bin/google-chrome-canary <<'EOF'
#!/bin/sh
echo "$*" >> /work/results/launches.txt
EOF
chmod +x /work/bin/google-chrome-canary
mkdir -p "$HOME/.config/google-chrome-canary"
cat > "$HOME/.config/google-chrome-canary/Local State" <<'EOF'
{"profile": {"info_cache": {
  "Default": {"name": "Personal", "user_name": "personal@example.com"},
  "Profile 1": {"name": "Work", "user_name": "work@example.com"}}}}
EOF

# Native host + URL handler, exactly as a user would install them.
cd "$R"
./install.sh > /work/results/install.log 2>&1
python3 host/register_handler.py --profile "$P" >> /work/results/install.log 2>&1

# Test reporter native host.
chmod +x "$E/reporter.py"
cat > "$HOME/.mozilla/native-messaging-hosts/bpr_test_reporter.json" <<EOF
{"name": "bpr_test_reporter", "description": "e2e test reporter", "path": "$E/reporter.py",
 "type": "stdio", "allowed_extensions": ["browser-profile-router@garai.ca"]}
EOF

# Test build of the add-on: the real extension plus test-background.js.
cp -r "$R/extension" /work/build
cp "$E/test-background.js" /work/build/
python3 - <<'EOF'
import json
path = "/work/build/manifest.json"
manifest = json.load(open(path))
manifest["background"]["scripts"].append("test-background.js")
# Only the test needs these: import fixture messages and click the link.
manifest["permissions"] += ["messagesImport", "accountsFolders", "messagesModify"]
json.dump(manifest, open(path, "w"), indent=2)
EOF
(cd /work/build && zip -qr "$P/extensions/browser-profile-router@garai.ca.xpi" .)

cp "$E/user.js" "$P/user.js"

/tb/thunderbird --headless --no-remote --profile "$P" > /work/results/thunderbird.log 2>&1 &
TB_PID=$!
# Stop Thunderbird once the test reports "done", or after 120s.
i=0
while [ $i -lt 120 ] && ! grep -qs '"step":"done"' /work/results/report.jsonl; do
  sleep 1
  i=$((i + 1))
done
kill $TB_PID 2>/dev/null || true
wait $TB_PID 2>/dev/null || true
cp "$XDG_RUNTIME_DIR/browser-profile-router/context.json" /work/results/ 2>/dev/null || true
