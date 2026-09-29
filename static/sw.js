/**
 * Offline cache: pages this browser has already opened, the app shell, and a
 * background pack of the newest public posts (/recent.json).
 * /api/, /admin/, /add-photos/, and /subscribe/manage/ stay network-only.
 * The pages cache is not versioned so a new deploy does not wipe visited posts.
 * ponytail: assets cache has no entry cap (device quota is the ceiling); upgrade
 * path is a max-entry eviction if storage complaints show up. Bodies over 8MB
 * are not stored. Posts that age out of the newest 15 stay cached.
 */

export const PAGES_CACHE = "ericwiz-pages";
export const ASSETS_CACHE = "ericwiz-assets";
export const MAX_CACHED_BYTES = 8 * 1024 * 1024;
export const RECENT_PATH = "/recent.json";
export const PREFETCH_LIMIT = 15;

const SHELL_FILES = [
  "/offline/",
  "/favicon.ico",
  "/favicon.png",
  "/apple-touch-icon.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/manifest.webmanifest",
];

const BYPASS_PREFIXES = [
  "/api/",
  "/admin/",
  "/add-photos/",
  "/cdn-cgi/",
  "/subscribe/manage/",
];

const SHELL_ATTR = /(?:href|src)="([^"]+)"/g;

export function cacheKey(input, origin) {
  const raw = typeof input === "string" ? input : input.url;
  const url = new URL(raw, origin || "https://ericwisnewski.com");
  return url.pathname + url.search;
}

export function recentPostUrls(index, origin) {
  const posts = index && Array.isArray(index.posts) ? index.posts : [];
  const urls = [];
  const seen = new Set();
  const base = origin || "https://ericwisnewski.com";
  for (const raw of posts) {
    if (urls.length >= PREFETCH_LIMIT) break;
    if (typeof raw !== "string" || !raw) continue;
    let url;
    try {
      url = new URL(raw, base);
    } catch {
      continue;
    }
    if (url.origin !== new URL(base).origin) continue;
    if (isBypassPath(url.pathname)) continue;
    const key = url.pathname + url.search;
    if (seen.has(key)) continue;
    seen.add(key);
    urls.push(key);
  }
  return urls;
}

function attrValue(tag, name) {
  const quoted = tag.match(new RegExp("\\b" + name + "\\s*=\\s*([\"'])(.*?)\\1", "i"));
  if (quoted) return quoted[2].replace(/&amp;/g, "&");
  const bare = tag.match(new RegExp("\\b" + name + "\\s*=\\s*([^\\s>]+)", "i"));
  return bare ? bare[1].replace(/&amp;/g, "&") : "";
}

function articleHtml(html) {
  if (!html) return "";
  const start = html.search(/<article\b[^>]*\bclass\s*=\s*["']?[^"'>]*\bpost-content\b/i);
  if (start < 0) return "";
  const end = html.toLowerCase().indexOf("</article>", start);
  return end < 0 ? html.slice(start) : html.slice(start, end + "</article>".length);
}

export function articleImageUrls(html, origin) {
  const urls = [];
  const seen = new Set();
  const base = origin || "https://ericwisnewski.com";
  const article = articleHtml(html);
  for (const tag of article.matchAll(/<img\b[^>]*>/gi)) {
    const src = attrValue(tag[0], "src");
    if (!src || src.startsWith("data:") || src.startsWith("blob:")) continue;
    let url;
    try {
      url = new URL(src, base);
    } catch {
      continue;
    }
    if (url.origin !== new URL(base).origin) continue;
    if (isBypassPath(url.pathname)) continue;
    if (/\.(?:mp3|m4a|ogg|mp4|webm|wav)(?:$|\?)/i.test(url.pathname)) continue;
    const key = url.pathname + url.search;
    if (seen.has(key)) continue;
    seen.add(key);
    urls.push(key);
  }
  return urls;
}

function mediaType(response) {
  return ((response && response.headers.get("content-type")) || "").toLowerCase();
}

export function shellUrlsFromHomeHtml(html) {
  const urls = [];
  const seen = new Set();
  if (!html) return urls;
  for (const match of html.matchAll(SHELL_ATTR)) {
    const raw = match[1];
    const keep =
      raw.startsWith("/css/") ||
      raw.startsWith("/js/media.js") ||
      raw.startsWith("/js/nav-scroll.js");
    if (keep && !seen.has(raw)) {
      seen.add(raw);
      urls.push(raw);
    }
  }
  return urls;
}

function isBypassPath(pathname) {
  return BYPASS_PREFIXES.some(
    (prefix) => pathname === prefix.slice(0, -1) || pathname.startsWith(prefix)
  );
}

function isDocumentRequest(request) {
  if (request.mode === "navigate" || request.destination === "document") return true;
  const headers = request.headers;
  if (!headers || !headers.get) return false;
  return headers.get("sec-fetch-dest") === "document" || headers.get("sec-fetch-mode") === "navigate";
}

function isCodeAsset(pathname) {
  return (
    pathname.startsWith("/css/") ||
    pathname.startsWith("/js/") ||
    pathname.endsWith(".css") ||
    pathname.endsWith(".js") ||
    pathname.endsWith(".woff2")
  );
}

export function cachePlan(request, origin) {
  const method = (request && request.method) || "GET";
  if (method !== "GET") return "network-only";
  let url;
  try {
    url = new URL(request.url, origin || "https://ericwisnewski.com");
  } catch {
    return "network-only";
  }
  if (origin && url.origin !== origin) return "network-only";
  if (request.headers && request.headers.has && request.headers.has("range")) return "network-only";
  if (isBypassPath(url.pathname) || url.pathname === "/sw.js") return "network-only";
  if (isDocumentRequest(request)) return "network-first-page";
  if (isCodeAsset(url.pathname)) return "cache-first";
  return "network-first-asset";
}

function canStore(response) {
  if (!response || response.status !== 200 || response.type === "opaque") return false;
  const cacheControl = response.headers.get("cache-control") || "";
  if (/no-store|private/i.test(cacheControl)) return false;
  if ((response.headers.get("vary") || "").trim() === "*") return false;
  const length = response.headers.get("content-length");
  if (length && Number(length) > MAX_CACHED_BYTES) return false;
  return true;
}

async function snapshot(response) {
  const headers = new Headers(response.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");
  headers.delete("vary");
  const body = await response.arrayBuffer();
  return () => new Response(body.slice(0), { status: 200, statusText: "OK", headers });
}

async function store(cache, key, response) {
  if (!canStore(response)) return false;
  const make = await snapshot(response.clone());
  await cache.put(key, make());
  return true;
}

async function matchFirst(cacheStorage, names, key) {
  for (const name of names) {
    const cache = await cacheStorage.open(name);
    const hit = await cache.match(key);
    if (hit) return hit;
  }
  return undefined;
}

export function createPwa({ version, offlineUrl = "/offline/" } = {}) {
  const shellName = "ericwiz-shell-" + (version || "dev");
  return {
    shellName,
    pagesName: PAGES_CACHE,
    assetsName: ASSETS_CACHE,
    offlineUrl,

    async install(cacheStorage, fetchImpl, origin) {
      const base = origin || "https://ericwisnewski.com";
      const shell = await cacheStorage.open(shellName);
      const assets = await cacheStorage.open(ASSETS_CACHE);
      const home = await fetchImpl("/");
      if (!home || home.status !== 200) throw new Error("precache failed: /");
      const html = await home.clone().text();
      const urls = [cacheKey("/", base), ...SHELL_FILES, ...shellUrlsFromHomeHtml(html)];
      const seen = new Set();
      const bodies = new Map([[cacheKey("/", base), home]]);
      for (const url of urls) {
        const key = cacheKey(url, base);
        if (seen.has(key)) continue;
        seen.add(key);
        let response = bodies.get(key);
        if (!response) response = await fetchImpl(url);
        if (!response || response.status !== 200) throw new Error("precache failed: " + key);
        if (!canStore(response)) throw new Error("precache failed: " + key);
        const make = await snapshot(response.clone ? response.clone() : response);
        await shell.put(key, make());
        await assets.put(key, make());
      }
    },

    async prefetchRecent(cacheStorage, fetchImpl, origin) {
      if (this._prefetching) return this._prefetching;
      this._prefetching = this._prefetchRecent(cacheStorage, fetchImpl, origin).finally(() => {
        this._prefetching = null;
      });
      return this._prefetching;
    },

    async _prefetchRecent(cacheStorage, fetchImpl, origin) {
      const base = origin || "https://ericwisnewski.com";
      let indexRes;
      try {
        indexRes = await fetchImpl(RECENT_PATH);
      } catch {
        return { ok: false, reason: "offline" };
      }
      if (!indexRes || indexRes.status !== 200) return { ok: false, reason: "index" };
      const text = await indexRes.clone().text();
      let index;
      try {
        index = JSON.parse(text);
      } catch {
        return { ok: false, reason: "parse" };
      }
      const posts = recentPostUrls(index, base);
      const pages = await cacheStorage.open(PAGES_CACHE);
      const assets = await cacheStorage.open(ASSETS_CACHE);
      const previous = await pages.match(RECENT_PATH);
      const previousText = previous ? await previous.text() : "";
      const changed = previousText !== text;
      const fetched = [];
      for (const post of posts) {
        const cachedPage = changed ? undefined : await pages.match(post);
        let html = "";
        if (cachedPage) {
          html = await cachedPage.text();
        } else {
          let response;
          try {
            response = await fetchImpl(post);
          } catch {
            continue;
          }
          if (!response || response.status !== 200 || !canStore(response)) continue;
          html = await response.clone().text();
          await store(pages, post, response);
          fetched.push(post);
        }
        for (const image of articleImageUrls(html, base)) {
          if (await assets.match(image)) continue;
          let response;
          try {
            response = await fetchImpl(image);
          } catch {
            continue;
          }
          if (!response || !canStore(response)) continue;
          const type = mediaType(response);
          if (type.startsWith("audio/") || type.startsWith("video/")) continue;
          await store(assets, image, response);
        }
      }
      const saved = new Response(text, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
      await store(pages, RECENT_PATH, saved);
      return { ok: true, posts, fetched, changed };
    },

    async activate(cacheStorage, claim) {
      const keep = new Set([shellName, PAGES_CACHE, ASSETS_CACHE]);
      const names = await cacheStorage.keys();
      await Promise.all(
        names.filter((name) => !keep.has(name)).map((name) => cacheStorage.delete(name))
      );
      if (claim) await claim();
    },

    async handle(request, { cacheStorage, fetchImpl, origin, noteOffline, noteOnline }) {
      const plan = cachePlan(request, origin);
      if (plan === "network-only") return fetchImpl(request);

      const key = cacheKey(request, origin);
      if (plan === "cache-first") {
        const cached = await matchFirst(cacheStorage, [shellName, ASSETS_CACHE], key);
        if (cached) return cached;
        const response = await fetchImpl(request);
        if (canStore(response)) {
          await store(await cacheStorage.open(ASSETS_CACHE), key, response);
        }
        return response;
      }

      const cacheName = plan === "network-first-page" ? PAGES_CACHE : ASSETS_CACHE;
      try {
        const response = await fetchImpl(request);
        if (canStore(response)) {
          await store(await cacheStorage.open(cacheName), key, response);
        }
        if (plan === "network-first-page" && noteOnline) noteOnline();
        return response;
      } catch (err) {
        const cached = await matchFirst(cacheStorage, [cacheName, shellName], key);
        if (cached) {
          if (plan === "network-first-page" && noteOffline) noteOffline();
          return cached;
        }
        if (plan === "network-first-page") {
          const offline = await matchFirst(cacheStorage, [shellName, ASSETS_CACHE], cacheKey(offlineUrl, origin));
          if (offline && noteOffline) noteOffline();
          if (offline) return offline;
        }
        throw err;
      }
    },
  };
}

const inWorker =
  typeof ServiceWorkerGlobalScope !== "undefined" &&
  typeof self !== "undefined" &&
  self instanceof ServiceWorkerGlobalScope;

if (inWorker) {
  const version = new URL(self.location.href).searchParams.get("v") || "dev";
  const pwa = createPwa({ version });
  const offlineClients = new Set();
  self.addEventListener("install", (event) => {
    event.waitUntil(
      pwa.install(caches, (input) => fetch(input), self.location.origin).then(() => self.skipWaiting())
    );
  });
  self.addEventListener("activate", (event) => {
    event.waitUntil(pwa.activate(caches, () => self.clients.claim()));
  });
  self.addEventListener("message", (event) => {
    const data = event.data;
    if (!data) return;
    if (data.type === "prefetch-recent") {
      event.waitUntil(pwa.prefetchRecent(caches, (input) => fetch(input), self.location.origin));
      return;
    }
    if (data.type === "offline-nav" && event.source) {
      event.source.postMessage({
        type: "offline-nav",
        offline: offlineClients.has(event.source.id),
      });
    }
  });
  self.addEventListener("fetch", (event) => {
    const id = event.resultingClientId || event.clientId || "";
    event.respondWith(
      pwa.handle(event.request, {
        cacheStorage: caches,
        fetchImpl: (input) => fetch(input),
        origin: self.location.origin,
        noteOffline() {
          if (id) offlineClients.add(id);
        },
        noteOnline() {
          if (id) offlineClients.delete(id);
        },
      })
    );
  });
}
