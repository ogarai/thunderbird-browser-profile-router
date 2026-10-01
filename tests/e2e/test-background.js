/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

// Loaded after background.js in the e2e test build only. Drives the add-on
// through both link paths and reports each step to the bpr_test_reporter host.

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function report(step, data) {
  return browser.runtime.sendNativeMessage("bpr_test_reporter", { step, ...data }).catch(() => {});
}

async function step(name, fn) {
  try {
    const result = await fn();
    await report(name, { ok: true, result });
    return result;
  } catch (e) {
    await report(name, { ok: false, error: `${e}\n${e.stack ?? ""}` });
    throw e;
  }
}

// Record clicks that the content script hands to the background script.
const intercepted = [];
const originalOpenLinkFromTab = openLinkFromTab;
openLinkFromTab = (url, tabId) => {
  intercepted.push(url);
  return originalOpenLinkFromTab(url, tabId);
};

function eml(to, path) {
  return [
    "From: Sender <sender@example.org>",
    `To: ${to}`,
    `Subject: Link for ${to}`,
    "Date: Thu, 01 Oct 2026 12:00:00 +0000",
    `Message-ID: <${path}@example.org>`,
    "MIME-Version: 1.0",
    "Content-Type: text/html; charset=utf-8",
    "",
    `<html><body><p><a href="https://example.com/${path}">open</a></p></body></html>`,
    "",
  ].join("\r\n");
}

function findInbox(folder) {
  if (folder.type === "inbox" || folder.name === "Inbox") {
    return folder;
  }
  for (const sub of folder.subFolders ?? []) {
    const found = findInbox(sub);
    if (found) {
      return found;
    }
  }
  return null;
}

async function importInto(account, to, path) {
  let inbox = findInbox(account.rootFolder);
  if (!inbox) {
    inbox = await browser.folders.create(account.rootFolder.id, "Inbox");
  }
  const file = new File([eml(to, path)], `${path}.eml`, { type: "message/rfc822" });
  const message = await browser.messages.import(file, inbox.id);
  return { id: message.id, folderId: inbox.id, accountId: message.folder?.accountId };
}

async function run() {
  await sleep(3000);
  await report("start", { version: (await browser.runtime.getBrowserInfo()).version });

  await step("registeredScripts", async () =>
    (await browser.scripting.messageDisplay.getRegisteredScripts()).map(s => s.id));

  const accounts = await step("accounts", async () =>
    (await browser.accounts.list(true)).map(a => ({
      id: a.id, name: a.name, type: a.type, emails: a.identities.map(i => i.email), rootFolder: a.rootFolder,
    })));
  const work = accounts.find(a => a.emails.includes("work@example.com"));
  const personal = accounts.find(a => a.emails.includes("personal@example.com"));

  await step("browsers", async () => listBrowsers({ refresh: true }));

  const workMsg = await step("importWork", () => importInto(work, "Test Work <work@example.com>", "clicked-work"));
  const personalMsg = await step("importPersonal", () => importInto(personal, "personal@example.com", "unused"));

  // Path 1 (Thunderbird Conversations): another add-on calls
  // windows.openDefaultBrowser while a message is selected in the thread pane.
  await step("selectPersonal", async () => {
    let [mailTab] = await browser.mailTabs.query({});
    if (!mailTab) {
      mailTab = await browser.mailTabs.create({});
    }
    await browser.mailTabs.update(mailTab.id, { displayedFolderId: personalMsg.folderId });
    await browser.mailTabs.setSelectedMessages(mailTab.id, [personalMsg.id]);
    await sleep(2000);
    const selected = await browser.mailTabs.getSelectedMessages(mailTab.id);
    return (selected.messages ?? selected).map(m => m.id);
  });
  await step("openDefaultBrowser", async () => {
    await browser.windows.openDefaultBrowser("https://example.com/conversations");
    await sleep(2000);
  });

  // Path 2: a click on a link in a message tab, caught by link-interceptor.js.
  const tabId = await step("openMessage", async () =>
    (await browser.messageDisplay.open({ messageId: workMsg.id, location: "tab" })).id);
  await sleep(3000);
  await step("displayed", async () =>
    (await browser.messageDisplay.getDisplayedMessages(tabId)).messages.map(m => m.id));
  await step("clickLink", async () => {
    const [result] = await browser.scripting.executeScript({
      target: { tabId },
      func: () => {
        const link = document.querySelector("a[href]");
        if (!link) {
          return `no link in: ${document.body?.innerHTML?.slice(0, 200)}`;
        }
        link.click();
        return `clicked ${link.href}`;
      },
    });
    await sleep(2000);
    return { script: result?.result, intercepted };
  });
}

run()
  .catch(() => {})
  .finally(() => report("done", {}));
