#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Native host that appends each test report from the add-on to report.jsonl."""

import struct
import sys

header = sys.stdin.buffer.read(4)
if len(header) == 4:
    message = sys.stdin.buffer.read(struct.unpack("=I", header)[0])
    with open("/work/results/report.jsonl", "ab") as f:
        f.write(message + b"\n")
    reply = b'{"ok": true}'
    sys.stdout.buffer.write(struct.pack("=I", len(reply)) + reply)
    sys.stdout.buffer.flush()
