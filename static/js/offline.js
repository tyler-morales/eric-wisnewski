export var READY_COPY = "Ready offline";
export var BANNER_COPY = "You're offline — reading cached pages.";
export var COMMENTS_COPY = "Comments need a connection.";
export var LIKES_COPY = "Likes unavailable offline.";
export var NEWSLETTER_COPY = "Newsletter signup needs the internet.";
export var MANAGE_COPY = "Email preferences need a connection.";
export var VIDEO_COPY = "This video needs a connection.";
export var POST_COPY = "This post needs a connection.";
export var MAP_COPY = "This map needs a connection.";
export var GLOBE_COPY = "The globe needs a connection.";
export var DISMISS_KEY = "ericwiz-offline-dismissed";
export var READY_DISMISS_KEY = "ericwiz-ready-dismissed";

var SERVED_FLAG = "ericwizServedOffline";

export function markServedFromCache(value) {
  if (typeof window === "undefined") return;
  window[SERVED_FLAG] = !!value;
}

export function servedFromCache() {
  return typeof window !== "undefined" && window[SERVED_FLAG] === true;
}

export function isOffline() {
  var onLine = typeof navigator === "undefined" ? true : navigator.onLine;
  return onLine === false || servedFromCache();
}

export function isNetworkFailure(err) {
  if (!err) return false;
  if (err.name === "TypeError" || err.name === "NetworkError") return true;
  var msg = String(err.message || "");
  return /failed to fetch|networkerror|load failed|internet connection appears to be offline/i.test(msg);
}

export function shouldShowReady(state) {
  if (!state || !state.ready || state.dismissed || state.offline) return false;
  var path = state.path || "";
  if (path === "/offline" || path === "/offline/") return false;
  return true;
}

export function shouldShowOfflineBanner(state) {
  var path = (state && state.path) || "";
  if (state && state.offlinePage) return false;
  if (path === "/offline" || path === "/offline/") return false;
  var offline = !!(state && (state.onLine === false || state.servedFromCache));
  if (!offline) return false;
  return !state.dismissed;
}

export function youtubeWatchUrl(src) {
  var match = String(src || "").match(/\/embed\/([A-Za-z0-9_-]{11})/);
  return match ? "https://www.youtube.com/watch?v=" + match[1] : "";
}

export function onConnection(fn) {
  if (typeof window === "undefined" || typeof fn !== "function") return;
  window.addEventListener("ericwiz-connection", function (event) {
    fn(!!(event.detail && event.detail.offline));
  });
}

function dispatch(offline) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("ericwiz-connection", { detail: { offline: !!offline } }));
}

function dismissed() {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "1";
  } catch (err) {
    return false;
  }
}

function readyDismissed() {
  try {
    return sessionStorage.getItem(READY_DISMISS_KEY) === "1";
  } catch (err) {
    return false;
  }
}

function rememberReadyDismiss() {
  try {
    sessionStorage.setItem(READY_DISMISS_KEY, "1");
  } catch (err) {}
}

function rememberDismiss() {
  try {
    sessionStorage.setItem(DISMISS_KEY, "1");
  } catch (err) {}
}

function clearDismiss() {
  try {
    sessionStorage.removeItem(DISMISS_KEY);
  } catch (err) {}
}

function replaceEmbed(node, text, href, label) {
  var doc = node.ownerDocument;
  var note = doc.createElement("p");
  note.className = "offline-embed";
  note.appendChild(doc.createTextNode(text));
  if (href) {
    note.appendChild(doc.createTextNode(" "));
    var link = doc.createElement("a");
    link.href = href;
    link.textContent = label;
    note.appendChild(link);
  }
  var parent = node.parentNode;
  if (parent && parent.tagName === "P" && parent.childNodes.length === 1) parent.replaceWith(note);
  else node.replaceWith(note);
}

export function softenEmbeds(doc) {
  if (!doc || !isOffline()) return;
  var videos = doc.querySelectorAll("iframe.youtube-embed");
  var i;
  for (i = videos.length - 1; i >= 0; i--) {
    var frame = videos[i];
    var watch = youtubeWatchUrl(frame.getAttribute("src"));
    replaceEmbed(frame, VIDEO_COPY, watch, "Watch on YouTube");
  }
  var tweets = doc.querySelectorAll("iframe.twitter-tweet");
  for (i = tweets.length - 1; i >= 0; i--) {
    replaceEmbed(tweets[i], POST_COPY, "https://x.com", "View on X");
  }
  var map = doc.querySelector(".map-embed-wrapper iframe");
  if (map) {
    var wrap = map.parentNode;
    replaceEmbed(map, MAP_COPY, "", "");
    if (wrap && wrap.classList) wrap.classList.add("is-offline");
  }
}

function bannerState(doc) {
  return {
    onLine: typeof navigator === "undefined" ? true : navigator.onLine,
    servedFromCache: servedFromCache(),
    dismissed: dismissed(),
    path: typeof location === "undefined" ? "" : location.pathname,
    offlinePage: !!(doc && doc.querySelector && doc.querySelector("[data-offline-page]")),
  };
}

var packReady = false;

function renderReady(doc) {
  var banner = doc.getElementById("offline-banner");
  var offlineVisible = !!(banner && !banner.hidden);
  var show = shouldShowReady({
    ready: packReady,
    dismissed: readyDismissed(),
    offline: isOffline() || offlineVisible,
    path: typeof location === "undefined" ? "" : location.pathname,
  });
  var chip = doc.getElementById("offline-ready");
  if (!show) {
    if (chip) chip.hidden = true;
    return;
  }
  if (!chip) {
    chip = doc.createElement("div");
    chip.id = "offline-ready";
    chip.className = "offline-banner";
    chip.setAttribute("role", "status");
    var text = doc.createElement("p");
    text.textContent = READY_COPY;
    var button = doc.createElement("button");
    button.type = "button";
    button.textContent = "Dismiss";
    button.addEventListener("click", function () {
      rememberReadyDismiss();
      renderReady(doc);
    });
    chip.appendChild(text);
    chip.appendChild(button);
    var header = doc.querySelector(".site-header");
    if (header && header.parentNode) header.parentNode.insertBefore(chip, header.nextSibling);
    else doc.body.appendChild(chip);
  }
  chip.hidden = false;
}

function renderBanner(doc) {
  var show = shouldShowOfflineBanner(bannerState(doc));
  var banner = doc.getElementById("offline-banner");
  if (!show) {
    if (banner) banner.hidden = true;
    return;
  }
  if (!banner) {
    banner = doc.createElement("div");
    banner.id = "offline-banner";
    banner.className = "offline-banner";
    banner.setAttribute("role", "status");
    var text = doc.createElement("p");
    text.textContent = BANNER_COPY;
    var button = doc.createElement("button");
    button.type = "button";
    button.textContent = "Dismiss";
    button.addEventListener("click", function () {
      rememberDismiss();
      renderBanner(doc);
    });
    banner.appendChild(text);
    banner.appendChild(button);
    var header = doc.querySelector(".site-header");
    if (header && header.parentNode) header.parentNode.insertBefore(banner, header.nextSibling);
    else doc.body.appendChild(banner);
  }
  banner.hidden = false;
}

function refresh(doc, offline) {
  renderBanner(doc);
  renderReady(doc);
  softenEmbeds(doc);
  dispatch(offline);
}

export function startOfflineUx(doc) {
  var root = doc || (typeof document === "undefined" ? null : document);
  if (!root || root.documentElement.dataset.offlineUx === "1") return;
  root.documentElement.dataset.offlineUx = "1";

  function sync(offline) {
    refresh(root, offline);
  }

  window.addEventListener("offline", function () {
    sync(true);
  });
  window.addEventListener("online", function () {
    markServedFromCache(false);
    clearDismiss();
    sync(false);
  });

  if (navigator.serviceWorker) {
    navigator.serviceWorker.addEventListener("message", function (event) {
      var data = event.data;
      if (!data) return;
      if (data.type === "offline-ready") {
        packReady = !!data.ok;
        renderReady(root);
        return;
      }
      if (data.type !== "offline-nav" || !data.offline) return;
      markServedFromCache(true);
      sync(true);
    });
    navigator.serviceWorker.ready.then(function (reg) {
      if (!reg.active) return;
      reg.active.postMessage({ type: "offline-nav" });
      reg.active.postMessage({ type: "offline-ready-query" });
    }).catch(function () {});
  }

  sync(isOffline());
}
