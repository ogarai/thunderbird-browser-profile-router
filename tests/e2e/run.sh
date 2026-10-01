#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# End-to-end test against a given Thunderbird build, run in a bubblewrap
# sandbox: fresh profile with test accounts, empty $HOME, no network, and
# no access to the real home directory. A fake google-chrome-canary records
# launches instead of opening a browser.
#
#   tests/e2e/run.sh <thunderbird-install-dir>   e.g. /usr/lib/thunderbird
set -eu

TB=$(cd "${1:?usage: $0 <thunderbird-install-dir>}" && pwd)
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/bpr-e2e.XXXXXX")

mkdir -p "$WORK/repo"
(cd "$ROOT" && tar --exclude=.git --exclude='*.xpi' -cf - .) | tar -xf - -C "$WORK/repo"

bwrap \
  --ro-bind /usr /usr \
  --symlink usr/lib /lib --symlink usr/lib /lib64 \
  --symlink usr/bin /bin --symlink usr/bin /sbin \
  --ro-bind /etc /etc \
  --proc /proc --dev /dev --tmpfs /tmp \
  --ro-bind "$TB" /tb \
  --bind "$WORK" /work \
  --unshare-all --die-with-parent --new-session \
  --clearenv \
  --setenv HOME /work/home \
  --setenv PATH /work/bin:/usr/bin \
  --setenv XDG_RUNTIME_DIR /work/run \
  --setenv MOZ_HEADLESS 1 \
  /bin/sh /work/repo/tests/e2e/inside.sh

echo "Work directory: $WORK"
python3 "$ROOT/tests/e2e/check.py" "$WORK/results"
