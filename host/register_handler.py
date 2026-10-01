#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Make thunderbird_url_handler.py Thunderbird's handler for http/https links.

This edits handlers.json in each Thunderbird profile (or the ones passed with
--profile). Thunderbird must be closed, since it rewrites the file itself.
It only affects links Thunderbird opens; the system default browser is unchanged.

  register_handler.py              register in all profiles
  register_handler.py --uninstall  restore Thunderbird's default handling
"""

import argparse
import configparser
import json
import os
import shutil
import sys
from pathlib import Path

HANDLER = Path(__file__).resolve().parent / "thunderbird_url_handler.py"
HANDLER_NAME = "Browser Profile Router"
SCHEMES = ("http", "https")
USE_HELPER_APP = 2  # nsIHandlerInfo.useHelperApp


def thunderbird_root():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Thunderbird"
    return Path.home() / ".thunderbird"


def find_profiles():
    root = thunderbird_root()
    parser = configparser.RawConfigParser()
    parser.read(root / "profiles.ini", encoding="utf-8")
    for section in parser.sections():
        if section.startswith("Profile") and "Path" in parser[section]:
            path = parser[section]["Path"]
            relative = parser[section].get("IsRelative", "1") == "1"
            yield root / path if relative else Path(path)


def is_running(profile):
    # On Linux the profile has a "lock" symlink pointing at "<ip>:+<pid>". It is
    # left behind on exit, so check whether that process is still alive.
    lock = profile / "lock"
    if not lock.is_symlink():
        return False
    try:
        pid = int(os.readlink(lock).rpartition("+")[2])
        os.kill(pid, 0)
    except ValueError:
        return True  # unrecognised format; be safe
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def update(profile, uninstall):
    path = profile / "handlers.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # Thunderbird discards the whole file unless defaultHandlersVersion is set.
    data.setdefault("defaultHandlersVersion", {})
    data.setdefault("mimeTypes", {})
    schemes = data.setdefault("schemes", {})
    for scheme in SCHEMES:
        if uninstall:
            entry = schemes.get(scheme, {})
            if any(h.get("name") == HANDLER_NAME for h in entry.get("handlers", [])):
                del schemes[scheme]
        else:
            schemes[scheme] = {
                "action": USE_HELPER_APP,
                "ask": False,
                "handlers": [{"name": HANDLER_NAME, "path": str(HANDLER)}],
            }
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(data), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", action="append", type=Path, help="Thunderbird profile directory")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    profiles = args.profile or [p for p in find_profiles() if p.is_dir()]
    if not profiles:
        sys.exit("No Thunderbird profiles found; pass --profile.")
    running = [p for p in profiles if is_running(p)]
    if running:
        sys.exit("Close Thunderbird first (in use: " + ", ".join(str(p) for p in running) + ").")

    HANDLER.chmod(0o755)
    for profile in profiles:
        update(profile, args.uninstall)
        print(("Removed handler from " if args.uninstall else "Registered handler in ") + str(profile / "handlers.json"))


if __name__ == "__main__":
    main()
