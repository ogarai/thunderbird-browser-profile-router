#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Checks the results of an e2e run and exits non-zero on failure."""

import json
import sys
from pathlib import Path

results = Path(sys.argv[1])
reports = [json.loads(line) for line in (results / "report.jsonl").read_text().splitlines()] \
    if (results / "report.jsonl").exists() else []
launches = (results / "launches.txt").read_text().splitlines() if (results / "launches.txt").exists() else []

failures = []
version = next((r["version"] for r in reports if r["step"] == "start"), "unknown")
print(f"Thunderbird {version}")

for r in reports:
    if r["step"] in ("start", "done"):
        continue
    status = "ok  " if r["ok"] else "FAIL"
    detail = json.dumps(r.get("result")) if r["ok"] else r["error"].strip()
    print(f"  {status} {r['step']}: {detail[:300]}")
    if not r["ok"]:
        failures.append(r["step"])

if not any(r["step"] == "done" for r in reports):
    failures.append("test did not finish (see thunderbird.log)")

clicked = next((r for r in reports if r["step"] == "clickLink" and r["ok"]), None)
if clicked and "https://example.com/clicked-work" not in clicked["result"]["intercepted"]:
    failures.append("click was not intercepted by link-interceptor.js")

expected = [
    "--profile-directory=Default https://example.com/conversations",   # URL handler, selection context
    "--profile-directory=Profile 1 https://example.com/clicked-work",  # click in message tab
]
print("  launches:", launches)
for line in expected:
    if line not in launches:
        failures.append(f"missing launch: {line}")
if len(launches) != len(expected):
    failures.append(f"expected {len(expected)} launches, got {len(launches)}")

if failures:
    print("FAIL:\n  " + "\n  ".join(failures))
    sys.exit(1)
print("PASS")
