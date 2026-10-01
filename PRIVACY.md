# Privacy Policy

Browser Profile Router does not collect, transmit or share any data. It makes
no network requests, has no analytics or telemetry, and everything it handles
stays on your computer.

## What the add-on reads

- **Your mail accounts and their identity email addresses**, to decide which
  browser profile belongs to which account.
- **The message you are viewing or have selected** (its folder, account and
  recipient addresses), to determine which account a clicked link belongs to.
  Message bodies are not read, except that a script in the message view
  watches for clicks on `http`/`https` links to get the link's address.

## Data exchanged with the native application

The add-on uses native messaging to talk to a helper program
(`profile_router_host.py`) that you install yourself. The helper runs locally
and is needed because add-ons cannot launch other programs.

Sent from the add-on to the helper:

- The **address (URL) of a link** you clicked, so the helper can open it.
- The **browser and profile identifiers** to open it with (for example
  `chrome-canary` and `Profile 2`).
- The same browser and profile identifiers whenever the selected message's
  target changes (see "Data stored on your computer" below).

Sent from the helper to the add-on:

- The **list of installed browsers and their profiles**, including each
  profile's display name and, for Chromium-based browsers, the email address
  of the account signed in to that profile. The helper reads this from the
  browsers' own local configuration files. It is used to fill the options
  page and to match profiles to your mail accounts automatically.

Your mail account addresses, message contents and message metadata are never
sent to the helper.

## Data stored on your computer

- **Add-on settings** (which account maps to which browser profile) are kept
  in Thunderbird's extension storage.
- **The current target** (browser and profile identifiers only) is written by
  the helper to `$XDG_RUNTIME_DIR/browser-profile-router/context.json`, a
  per-user directory that is cleared when you log out. It is read by the
  optional link handler (`thunderbird_url_handler.py`) for links opened by
  other add-ons.

## Removing your data

Uninstalling the add-on removes its settings. To remove the helper, delete
`browser_profile_router.json` from your native messaging hosts directory, run
`host/register_handler.py --uninstall` with Thunderbird closed, and delete the
repository.
