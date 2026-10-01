#!/usr/bin/env python3
"""Thunderbird's http/https handler, registered in the profile's handlers.json.

Links that Thunderbird opens externally without going through the add-on's
content script (e.g. clicks inside Thunderbird Conversations) end up here. The
URL opens in the profile the add-on resolved for the selected message.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import profile_router_host as host  # noqa: E402


def main():
    for url in sys.argv[1:]:
        try:
            host.open_with_target(host.read_context(), url)
        except ValueError as e:
            print(f"browser-profile-router: {e}; using system browser", file=sys.stderr)
            try:
                host.open_url("system", None, url)
            except ValueError:
                pass  # not a web URL


if __name__ == "__main__":
    main()
