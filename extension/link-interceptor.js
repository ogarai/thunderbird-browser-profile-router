// Injected into every displayed message. Captures clicks on web links and
// hands them to the background script, which picks the browser profile.

function linkFromEvent(event) {
  const anchor = event.target.closest?.("a[href]");
  if (!anchor) {
    return null;
  }
  let url;
  try {
    url = new URL(anchor.href, document.baseURI);
  } catch {
    return null;
  }
  return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
}

function handle(event) {
  // Left click (button 0) or middle click (button 1); leave right click to
  // the context menu.
  if (event.button > 1 || event.defaultPrevented) {
    return;
  }
  const url = linkFromEvent(event);
  if (!url) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  browser.runtime.sendMessage({ type: "openLink", url });
}

document.addEventListener("click", handle, true);
document.addEventListener("auxclick", handle, true);
