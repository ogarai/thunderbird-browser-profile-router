/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

const HOST = "browser_profile_router";
const SCRIPT_ID = "link-interceptor";
const BROWSER_CACHE_MS = 60 * 1000;

// Stored settings shape:
// {
//   rules: { [accountId]: Target },  // missing entry means { mode: "auto" }
//   fallback: Target,                // used when nothing else matches
// }
// Target: { mode: "auto" | "system" | "profile", browser?, profile? }
const DEFAULT_SETTINGS = {
  rules: {},
  fallback: { mode: "system" },
};

async function getSettings() {
  const { settings } = await browser.storage.local.get("settings");
  return { ...DEFAULT_SETTINGS, ...settings };
}

// --- Native host --------------------------------------------------------

let browserCache = null;

async function callHost(message) {
  const response = await browser.runtime.sendNativeMessage(HOST, message);
  if (response?.error) {
    throw new Error(response.error);
  }
  return response;
}

async function listBrowsers({ refresh = false } = {}) {
  if (!refresh && browserCache && Date.now() - browserCache.time < BROWSER_CACHE_MS) {
    return browserCache.browsers;
  }
  const { browsers } = await callHost({ cmd: "listBrowsers" });
  browserCache = { time: Date.now(), browsers };
  return browsers;
}

// --- Account resolution -------------------------------------------------

function extractEmails(addresses = []) {
  return addresses
    .map(address => (address.match(/<([^>]+)>/)?.[1] ?? address).trim().toLowerCase())
    .filter(Boolean);
}

function accountEmails(account) {
  return (account.identities ?? []).map(identity => identity.email.toLowerCase());
}

function firstMessage(list) {
  return (list?.messages ?? list ?? [])[0] ?? null;
}

// The message shown in a tab. Add-ons that replace the message reader (e.g.
// Thunderbird Conversations) may leave nothing "displayed", so fall back to
// the thread pane selection.
async function messageForTab(tabId) {
  try {
    const displayed = firstMessage(await browser.messageDisplay.getDisplayedMessages(tabId));
    if (displayed) {
      return displayed;
    }
  } catch {
    // Not a tab that displays messages.
  }
  try {
    return firstMessage(await browser.mailTabs.getSelectedMessages(tabId));
  } catch {
    return null;
  }
}

// Returns the account the message lives in. For messages without one (opened
// .eml files, attachments, Local Folders), falls back to the account whose
// identity the message was addressed to.
async function accountForMessage(message) {
  const accounts = await browser.accounts.list(false);
  const accountId = message?.folder?.accountId;
  const owner = accounts.find(account => account.id === accountId);
  if (owner && owner.identities?.length) {
    return owner;
  }
  if (!message) {
    return owner ?? null;
  }
  const recipients = new Set(
    extractEmails([...(message.recipients ?? []), ...(message.ccList ?? []), ...(message.bccList ?? [])])
  );
  return accounts.find(account => accountEmails(account).some(email => recipients.has(email))) ?? owner ?? null;
}

// --- Target resolution --------------------------------------------------

async function autoMatch(account) {
  const emails = new Set(accountEmails(account));
  if (!emails.size) {
    return null;
  }
  for (const b of await listBrowsers()) {
    const profile = b.profiles.find(p => p.email && emails.has(p.email.toLowerCase()));
    if (profile) {
      return { mode: "profile", browser: b.id, profile: profile.id };
    }
  }
  return null;
}

async function resolveTarget(account) {
  const settings = await getSettings();
  const rule = (account && settings.rules[account.id]) || { mode: "auto" };
  if (rule.mode === "profile" || rule.mode === "system") {
    return rule;
  }
  if (account) {
    try {
      const match = await autoMatch(account);
      if (match) {
        return match;
      }
    } catch (e) {
      console.warn("Profile router: auto-match failed:", e);
    }
  }
  return settings.fallback;
}

async function targetForMessage(message) {
  let account = null;
  try {
    account = await accountForMessage(message);
  } catch (e) {
    console.warn("Profile router: could not determine account:", e);
  }
  return resolveTarget(account);
}

async function openUrl(url, target) {
  // "system" goes through the host too: windows.openDefaultBrowser would hit
  // Thunderbird's http handler, which may be thunderbird_url_handler.py.
  const [browserId, profile] = target.mode === "profile" ? [target.browser, target.profile] : ["system", null];
  try {
    await callHost({ cmd: "open", browser: browserId, profile, url });
  } catch (e) {
    console.error("Profile router: native host failed, using default browser:", e);
    await browser.windows.openDefaultBrowser(url);
  }
}

async function openLinkFromTab(url, tabId) {
  await openUrl(url, await targetForMessage(await messageForTab(tabId)));
}

// --- Selection context ----------------------------------------------------
//
// Links opened by other add-ons (Thunderbird Conversations calls
// windows.openDefaultBrowser itself) bypass link-interceptor.js. They reach
// thunderbird_url_handler.py instead, which opens them using the target for
// the most recently selected message, saved here.

let lastContext = null;

async function updateContext(message) {
  if (!message) {
    return;
  }
  const target = await targetForMessage(message);
  const key = JSON.stringify(target);
  if (key === lastContext) {
    return;
  }
  try {
    await callHost({ cmd: "setContext", target });
    lastContext = key;
  } catch (e) {
    console.warn("Profile router: could not save context:", e);
  }
}

async function updateContextForTab(tabId) {
  await updateContext(await messageForTab(tabId));
}

// --- Wiring -------------------------------------------------------------

async function registerScripts() {
  const existing = await browser.scripting.messageDisplay.getRegisteredScripts({ ids: [SCRIPT_ID] });
  if (existing.length) {
    return;
  }
  await browser.scripting.messageDisplay.registerScripts([
    { id: SCRIPT_ID, js: ["link-interceptor.js"], runAt: "document_start" },
  ]);
}

browser.runtime.onInstalled.addListener(() => {
  browser.menus.create({
    id: "open-in-profile",
    title: "Open Link in Matching Browser Profile",
    contexts: ["link"],
  });
});

browser.menus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "open-in-profile" && info.linkUrl) {
    openLinkFromTab(info.linkUrl, tab.id);
  }
});

browser.mailTabs.onSelectedMessagesChanged.addListener((tab, list) => updateContext(firstMessage(list)));
browser.messageDisplay.onMessagesDisplayed.addListener((tab, list) => updateContext(firstMessage(list)));
browser.tabs.onActivated.addListener(({ tabId }) => updateContextForTab(tabId));
browser.storage.onChanged.addListener(async () => {
  lastContext = null;
  const [tab] = await browser.tabs.query({ active: true, lastFocusedWindow: true });
  if (tab) {
    updateContextForTab(tab.id);
  }
});

browser.runtime.onMessage.addListener((message, sender) => {
  switch (message?.type) {
    case "openLink":
      if (sender.tab) {
        openLinkFromTab(message.url, sender.tab.id);
      }
      return;
    case "listBrowsers":
      return listBrowsers({ refresh: message.refresh });
  }
});

registerScripts();
