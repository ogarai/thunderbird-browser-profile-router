#!/usr/bin/env python3
"""Native messaging host for the Browser Profile Router Thunderbird add-on.

Messages (JSON, length-prefixed, as per the WebExtension native messaging spec):
  {"cmd": "listBrowsers"}
      -> {"browsers": [{"id", "name", "available", "profiles": [{"id", "name", "email"}]}]}
  {"cmd": "open", "browser": id, "profile": id, "url": url}
      -> {"ok": true}            (browser "system" opens the OS default browser)
  {"cmd": "setContext", "target": {"mode": ..., "browser"?, "profile"?}}
      -> {"ok": true}            (read by thunderbird_url_handler.py)
Errors come back as {"error": "..."}.
"""

import configparser
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

HOME = Path.home()
PLATFORM = "windows" if os.name == "nt" else "mac" if sys.platform == "darwin" else "linux"
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
MAC_SUPPORT = HOME / "Library" / "Application Support"
WIN_LOCAL = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
WIN_ROAMING = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
WIN_PROGRAMS = [Path(os.environ.get(v, "")) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]

# Target for the message currently selected in Thunderbird, written by the
# add-on and read by the URL handler for links opened by other add-ons.
STATE_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or HOME / ".cache") / "browser-profile-router"
CONTEXT_FILE = STATE_DIR / "context.json"


def mac_app(name):
    return f"/Applications/{name}.app/Contents/MacOS/{name}"


def win_paths(relative):
    return [str(base / relative) for base in WIN_PROGRAMS if str(base)]


# Each browser: executables to try (first found wins) and where profiles live,
# per platform. The order here is also the order used for auto-matching.
CHROMIUM = {
    "chrome-canary": {
        "name": "Chrome Canary",
        "linux": (["google-chrome-canary"], XDG_CONFIG / "google-chrome-canary"),
        "mac": ([mac_app("Google Chrome Canary")], MAC_SUPPORT / "Google" / "Chrome Canary"),
        "windows": (win_paths(r"Google\Chrome SxS\Application\chrome.exe"), WIN_LOCAL / "Google" / "Chrome SxS" / "User Data"),
    },
    "chrome": {
        "name": "Google Chrome",
        "linux": (["google-chrome-stable", "google-chrome"], XDG_CONFIG / "google-chrome"),
        "mac": ([mac_app("Google Chrome")], MAC_SUPPORT / "Google" / "Chrome"),
        "windows": (win_paths(r"Google\Chrome\Application\chrome.exe"), WIN_LOCAL / "Google" / "Chrome" / "User Data"),
    },
    "chrome-beta": {
        "name": "Chrome Beta",
        "linux": (["google-chrome-beta"], XDG_CONFIG / "google-chrome-beta"),
        "mac": ([mac_app("Google Chrome Beta")], MAC_SUPPORT / "Google" / "Chrome Beta"),
        "windows": (win_paths(r"Google\Chrome Beta\Application\chrome.exe"), WIN_LOCAL / "Google" / "Chrome Beta" / "User Data"),
    },
    "chrome-dev": {
        "name": "Chrome Dev",
        "linux": (["google-chrome-unstable"], XDG_CONFIG / "google-chrome-unstable"),
        "mac": ([mac_app("Google Chrome Dev")], MAC_SUPPORT / "Google" / "Chrome Dev"),
        "windows": (win_paths(r"Google\Chrome Dev\Application\chrome.exe"), WIN_LOCAL / "Google" / "Chrome Dev" / "User Data"),
    },
    "chromium": {
        "name": "Chromium",
        "linux": (["chromium", "chromium-browser"], XDG_CONFIG / "chromium"),
        "mac": ([mac_app("Chromium")], MAC_SUPPORT / "Chromium"),
        "windows": (win_paths(r"Chromium\Application\chrome.exe"), WIN_LOCAL / "Chromium" / "User Data"),
    },
    "brave": {
        "name": "Brave",
        "linux": (["brave", "brave-browser"], XDG_CONFIG / "BraveSoftware" / "Brave-Browser"),
        "mac": ([mac_app("Brave Browser")], MAC_SUPPORT / "BraveSoftware" / "Brave-Browser"),
        "windows": (win_paths(r"BraveSoftware\Brave-Browser\Application\brave.exe"), WIN_LOCAL / "BraveSoftware" / "Brave-Browser" / "User Data"),
    },
    "edge": {
        "name": "Microsoft Edge",
        "linux": (["microsoft-edge-stable", "microsoft-edge"], XDG_CONFIG / "microsoft-edge"),
        "mac": ([mac_app("Microsoft Edge")], MAC_SUPPORT / "Microsoft Edge"),
        "windows": (win_paths(r"Microsoft\Edge\Application\msedge.exe"), WIN_LOCAL / "Microsoft" / "Edge" / "User Data"),
    },
    "vivaldi": {
        "name": "Vivaldi",
        "linux": (["vivaldi-stable", "vivaldi"], XDG_CONFIG / "vivaldi"),
        "mac": ([mac_app("Vivaldi")], MAC_SUPPORT / "Vivaldi"),
        "windows": (win_paths(r"Vivaldi\Application\vivaldi.exe"), WIN_LOCAL / "Vivaldi" / "User Data"),
    },
}

FIREFOX = {
    "firefox": {
        "name": "Firefox",
        "linux": (["firefox"], [XDG_CONFIG / "mozilla" / "firefox", HOME / ".mozilla" / "firefox"]),
        "mac": (["/Applications/Firefox.app/Contents/MacOS/firefox"], [MAC_SUPPORT / "Firefox"]),
        "windows": (win_paths(r"Mozilla Firefox\firefox.exe"), [WIN_ROAMING / "Mozilla" / "Firefox"]),
    },
    "librewolf": {
        "name": "LibreWolf",
        "linux": (["librewolf"], [XDG_CONFIG / "librewolf" / "librewolf", HOME / ".librewolf"]),
        "mac": (["/Applications/LibreWolf.app/Contents/MacOS/librewolf"], [MAC_SUPPORT / "librewolf"]),
        "windows": (win_paths(r"LibreWolf\librewolf.exe"), [WIN_ROAMING / "librewolf"]),
    },
}


def find_executable(candidates):
    for candidate in candidates:
        if os.path.isabs(candidate):
            if os.path.isfile(candidate):
                return candidate
        elif found := shutil.which(candidate):
            return found
    return None


def chromium_profiles(user_data_dir):
    try:
        with open(user_data_dir / "Local State", encoding="utf-8") as f:
            info = json.load(f)["profile"]["info_cache"]
    except (OSError, ValueError, KeyError):
        return []
    profiles = [
        {"id": directory, "name": data.get("name") or directory, "email": data.get("user_name") or ""}
        for directory, data in info.items()
    ]
    return sorted(profiles, key=lambda p: (p["id"] != "Default", p["name"].lower()))


def firefox_profiles(roots):
    for root in roots:
        ini = root / "profiles.ini"
        if not ini.is_file():
            continue
        parser = configparser.RawConfigParser()
        parser.read(ini, encoding="utf-8")
        return [
            {"id": parser[s]["Name"], "name": parser[s]["Name"], "email": ""}
            for s in parser.sections()
            if s.startswith("Profile") and "Name" in parser[s]
        ]
    return []


def discover():
    browsers = []
    for browser_id, spec in CHROMIUM.items():
        candidates, data_dir = spec[PLATFORM]
        exe = find_executable(candidates)
        browsers.append({
            "id": browser_id, "name": spec["name"], "kind": "chromium", "exe": exe,
            "available": bool(exe), "profiles": chromium_profiles(data_dir) if exe else [],
        })
    for browser_id, spec in FIREFOX.items():
        candidates, roots = spec[PLATFORM]
        exe = find_executable(candidates)
        browsers.append({
            "id": browser_id, "name": spec["name"], "kind": "firefox", "exe": exe,
            "available": bool(exe), "profiles": firefox_profiles(roots) if exe else [],
        })
    return browsers


def launch(args):
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if PLATFORM == "windows":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Detach so the browser outlives this host when Thunderbird reaps it.
        options["start_new_session"] = True
    subprocess.Popen(args, **options)


def open_system(url):
    if PLATFORM == "windows":
        os.startfile(url)
    else:
        launch(["open" if PLATFORM == "mac" else "xdg-open", url])


def open_url(browser_id, profile_id, url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"refusing to open non-web URL: {url!r}")
    if browser_id == "system":
        open_system(url)
        return

    browser = next((b for b in discover() if b["id"] == browser_id), None)
    if not browser or not browser["available"]:
        raise ValueError(f"browser not available: {browser_id!r}")
    if not any(p["id"] == profile_id for p in browser["profiles"]):
        raise ValueError(f"unknown profile {profile_id!r} for {browser['name']}")

    if browser["kind"] == "chromium":
        launch([browser["exe"], f"--profile-directory={profile_id}", url])
    else:
        launch([browser["exe"], "-P", profile_id, "--new-tab", url])


def open_with_target(target, url):
    if target.get("mode") == "profile":
        open_url(target.get("browser"), target.get("profile"), url)
    else:
        open_url("system", None, url)


def set_context(target):
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    target = {k: str(target[k]) for k in ("mode", "browser", "profile") if k in target}
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = CONTEXT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(target), encoding="utf-8")
    tmp.replace(CONTEXT_FILE)


def read_context():
    try:
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mode": "system"}


def read_message():
    header = sys.stdin.buffer.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack("=I", header)
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def send_message(message):
    data = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def handle(message):
    cmd = message.get("cmd")
    if cmd == "listBrowsers":
        public = ("id", "name", "available", "profiles")
        return {"browsers": [{k: b[k] for k in public} for b in discover()]}
    if cmd == "open":
        open_url(message.get("browser"), message.get("profile"), message.get("url", ""))
        return {"ok": True}
    if cmd == "setContext":
        set_context(message.get("target"))
        return {"ok": True}
    raise ValueError(f"unknown command: {cmd!r}")


def main():
    while (message := read_message()) is not None:
        try:
            send_message(handle(message))
        except Exception as e:  # report every failure back to the add-on
            send_message({"error": str(e)})


if __name__ == "__main__":
    main()
