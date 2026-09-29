/**
 * Offline cache for pages this browser has already opened, plus the app shell.
 * /api/, /admin/, /add-photos/, and /subscribe/manage/ stay network-only.
 * The pages cache is not versioned so a new deploy does not wipe visited posts.
 * ponytail: assets cache has no entry cap (device quota is the ceiling); upgrade
 * path is a max-entry eviction if storage complaints show up. Bodies over 8MB
 * are not stored.
 */

export const PAGES_CACHE = "ericwiz-pages";
export const ASSETS_CACHE = "ericwiz-assets";
export const MAX_CACHED_BYTES = 8 * 1024 * 1024;

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

    async activate(cacheStorage, claim) {
      const keep = new Set([shellName, PAGES_CACHE, ASSETS_CACHE]);
      const names = await cacheStorage.keys();
      await Promise.all(
        names.filter((name) => !keep.has(name)).map((name) => cacheStorage.delete(name))
      );
      if (claim) await claim();
    },

    async handle(request, { cacheStorage, fetchImpl, origin }) {
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
        return response;
      } catch (err) {
        const cached = await matchFirst(cacheStorage, [cacheName, shellName], key);
        if (cached) return cached;
        if (plan === "network-first-page") {
          const offline = await matchFirst(cacheStorage, [shellName, ASSETS_CACHE], cacheKey(offlineUrl, origin));
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
  self.addEventListener("install", (event) => {
    event.waitUntil(
      pwa.install(caches, (input) => fetch(input), self.location.origin).then(() => self.skipWaiting())
    );
  });
  self.addEventListener("activate", (event) => {
    event.waitUntil(pwa.activate(caches, () => self.clients.claim()));
  });
  self.addEventListener("fetch", (event) => {
    event.respondWith(
      pwa.handle(event.request, {
        cacheStorage: caches,
        fetchImpl: (input) => fetch(input),
        origin: self.location.origin,
      })
    );
  });
}
