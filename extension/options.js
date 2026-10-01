/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

const DEFAULT_SETTINGS = {
  rules: {},
  fallback: { mode: "system" },
};

let settings;
let browsers = [];

function encodeTarget(target) {
  return target.mode === "profile" ? `profile\n${target.browser}\n${target.profile}` : target.mode;
}

function decodeTarget(value) {
  const [mode, browserId, profile] = value.split("\n");
  return mode === "profile" ? { mode, browser: browserId, profile } : { mode };
}

function option(value, label) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = label;
  return element;
}

function targetSelect(current, { allowAuto }) {
  const select = document.createElement("select");
  if (allowAuto) {
    select.append(option("auto", "Auto (match by email)"));
  }
  select.append(option("system", "System default browser"));

  for (const b of browsers.filter(b => b.available)) {
    const group = document.createElement("optgroup");
    group.label = b.name;
    for (const p of b.profiles) {
      const label = p.email && p.email !== p.name ? `${p.name} (${p.email})` : p.name;
      group.append(option(encodeTarget({ mode: "profile", browser: b.id, profile: p.id }), label));
    }
    select.append(group);
  }

  const value = encodeTarget(current);
  if (![...select.options].some(o => o.value === value)) {
    // Keep a configured profile visible even if it is not installed right now.
    select.append(option(value, `${current.browser} / ${current.profile} (not found)`));
  }
  select.value = value;
  return select;
}

async function save() {
  await browser.storage.local.set({ settings });
  const saved = document.getElementById("saved");
  saved.hidden = false;
  setTimeout(() => (saved.hidden = true), 1500);
}

async function render() {
  const accounts = await browser.accounts.list(false);
  const tbody = document.getElementById("accounts");
  tbody.replaceChildren();

  for (const account of accounts) {
    const row = tbody.insertRow();
    const nameCell = row.insertCell();
    nameCell.textContent = account.name;
    const emails = (account.identities ?? []).map(i => i.email).join(", ");
    if (emails) {
      const span = document.createElement("span");
      span.className = "email";
      span.textContent = emails;
      nameCell.append(span);
    }

    const select = targetSelect(settings.rules[account.id] ?? { mode: "auto" }, { allowAuto: true });
    select.addEventListener("change", () => {
      const target = decodeTarget(select.value);
      if (target.mode === "auto") {
        delete settings.rules[account.id];
      } else {
        settings.rules[account.id] = target;
      }
      save();
    });
    row.insertCell().append(select);
  }

  const fallback = targetSelect(settings.fallback, { allowAuto: false });
  fallback.addEventListener("change", () => {
    settings.fallback = decodeTarget(fallback.value);
    save();
  });
  document.getElementById("fallback").replaceChildren(fallback);
}

async function loadBrowsers(refresh) {
  const status = document.getElementById("host-status");
  try {
    browsers = await browser.runtime.sendMessage({ type: "listBrowsers", refresh });
    const found = browsers.filter(b => b.available).map(b => b.name);
    status.className = "status";
    status.textContent = found.length
      ? `Native host connected. Browsers found: ${found.join(", ")}.`
      : "Native host connected, but no supported browsers were found.";
  } catch (e) {
    browsers = [];
    status.className = "status error";
    status.textContent = `Native host unavailable (${e.message}). Run install.sh, then restart Thunderbird. Links will open in the system default browser.`;
  }
}

async function init() {
  const stored = (await browser.storage.local.get("settings")).settings;
  settings = { ...DEFAULT_SETTINGS, ...stored };
  await loadBrowsers(false);
  await render();
}

document.getElementById("refresh").addEventListener("click", async () => {
  await loadBrowsers(true);
  await render();
});

init();
