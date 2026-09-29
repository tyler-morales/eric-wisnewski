"""Installable PWA: manifest, service worker, offline cache for visited pages."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SW_JS = REPO_ROOT / "static" / "sw.js"
MANIFEST = REPO_ROOT / "static" / "manifest.webmanifest"
HEAD = REPO_ROOT / "layouts" / "partials" / "head.html"
BASEOF = REPO_ROOT / "layouts" / "_default" / "baseof.html"
OFFLINE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "offline.html"
OFFLINE_PAGE = REPO_ROOT / "content" / "offline.md"
ROBOTS = REPO_ROOT / "layouts" / "robots.txt"
HEADERS = REPO_ROOT / "static" / "_headers"
ICON_192 = REPO_ROOT / "static" / "icons" / "icon-192.png"
ICON_512 = REPO_ROOT / "static" / "icons" / "icon-512.png"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
HUGO_TIMEOUT_SECONDS = 120


def run_node(script: str) -> object:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "node failed")
    return json.loads(result.stdout)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(PNG_MAGIC):
        raise AssertionError(f"{path} is not a PNG")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


SCENARIO = r"""
import { createPwa, cachePlan, shellUrlsFromHomeHtml, cacheKey } from "__SW__";

const origin = "https://ericwisnewski.com";
const homeHtml = [
  '<!doctype html>',
  '<link rel="stylesheet" href="/css/style.min.abc.css" integrity="sha256-x">',
  '<script type="module" src="/js/media.js?v=aaa"></script>',
  '<script type="module" src="/js/nav-scroll.js?v=bbb"></script>',
  '<script type="module" src="/js/comments.js?v=ccc"></script>',
].join("");

const files = {
  "/": homeHtml,
  "/offline/": "<h1>You are offline</h1>",
  "/favicon.ico": "ico",
  "/favicon.png": "png",
  "/apple-touch-icon.png": "apple",
  "/icons/icon-192.png": "192",
  "/icons/icon-512.png": "512",
  "/manifest.webmanifest": "{}",
  "/css/style.min.abc.css": "css-body",
  "/js/media.js?v=aaa": "media",
  "/js/nav-scroll.js?v=bbb": "nav",
};

class MemoryCache {
  constructor() { this.map = new Map(); }
  async match(key) {
    const hit = this.map.get(key);
    return hit ? hit.clone() : undefined;
  }
  async put(key, response) { this.map.set(key, response.clone()); }
}
class MemoryCaches {
  constructor() { this.map = new Map(); }
  async open(name) {
    if (!this.map.has(name)) this.map.set(name, new MemoryCache());
    return this.map.get(name);
  }
  async keys() { return [...this.map.keys()]; }
  async delete(name) { return this.map.delete(name); }
  dump() {
    const out = {};
    for (const [name, cache] of this.map) out[name] = [...cache.map.keys()];
    return out;
  }
}

let offline = false;
let helloBody = "v1";
let helloStatus = 200;
let imageLength = null;

function responseFor(key) {
  if (key === "/posts/hello/") {
    return new Response(helloBody, {
      status: helloStatus,
      headers: { "Content-Type": "text/html" },
    });
  }
  if (key === "/images/pic.jpg") {
    const headers = { "Content-Type": "image/jpeg" };
    if (imageLength != null) headers["Content-Length"] = String(imageLength);
    return new Response("img", { status: 200, headers });
  }
  if (key.startsWith("/api/")) {
    return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
  }
  if (Object.prototype.hasOwnProperty.call(files, key)) {
    return new Response(files[key], { status: 200 });
  }
  return new Response("missing", { status: 404 });
}

async function fetchImpl(input) {
  if (offline) throw new Error("offline");
  const raw = typeof input === "string" ? input : input.url;
  return responseFor(cacheKey(raw, origin));
}

function doc(path) {
  return new Request(origin + path, {
    headers: {
      Accept: "text/html",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
    },
  });
}

function plan(path, extra) {
  const headers = new Headers((extra && extra.headers) || {});
  if (!headers.has("Sec-Fetch-Dest") && !(extra && extra.skipDest)) {
    headers.set("Sec-Fetch-Dest", "empty");
  }
  return cachePlan(new Request(origin + path, Object.assign({ headers }, extra || {})), origin);
}

const caches = new MemoryCaches();
const pwa = createPwa({ version: "sha256-test-1" });
await pwa.install(caches, fetchImpl, origin);

const shellUrls = shellUrlsFromHomeHtml(homeHtml);
offline = true;
const cssOffline = await (await pwa.handle(
  new Request(origin + "/css/style.min.abc.css"),
  { cacheStorage: caches, fetchImpl, origin }
)).text();
offline = false;

const visited = await pwa.handle(doc("/posts/hello/"), { cacheStorage: caches, fetchImpl, origin });
const visitedOnline = await visited.text();
helloStatus = 500;
helloBody = "v2";
const after500 = await (await pwa.handle(doc("/posts/hello/"), { cacheStorage: caches, fetchImpl, origin })).text();
offline = true;
const visitedOffline = await (await pwa.handle(doc("/posts/hello/"), { cacheStorage: caches, fetchImpl, origin })).text();
const freshOffline = await (await pwa.handle(doc("/posts/never/"), { cacheStorage: caches, fetchImpl, origin })).text();
const homeOffline = await (await pwa.handle(doc("/"), { cacheStorage: caches, fetchImpl, origin })).text();

let apiThrew = false;
try {
  await pwa.handle(new Request(origin + "/api/comments"), { cacheStorage: caches, fetchImpl, origin });
} catch (err) {
  apiThrew = err instanceof Error && err.message === "offline";
}
offline = false;
await pwa.handle(new Request(origin + "/api/comments"), { cacheStorage: caches, fetchImpl, origin });
await pwa.handle(new Request(origin + "/api/subscribe", { method: "POST", body: "{}" }), {
  cacheStorage: caches, fetchImpl, origin,
});

const imageOnline = await (await pwa.handle(
  new Request(origin + "/images/pic.jpg"),
  { cacheStorage: caches, fetchImpl, origin }
)).text();
offline = true;
const imageOffline = await (await pwa.handle(
  new Request(origin + "/images/pic.jpg"),
  { cacheStorage: caches, fetchImpl, origin }
)).text();
offline = false;
imageLength = 9 * 1024 * 1024;
await pwa.handle(new Request(origin + "/images/huge.jpg"), { cacheStorage: caches, fetchImpl, origin });
offline = true;
let hugeThrew = false;
try {
  await pwa.handle(new Request(origin + "/images/huge.jpg"), { cacheStorage: caches, fetchImpl, origin });
} catch (err) {
  hugeThrew = true;
}

await caches.open("ericwiz-shell-old");
let claimed = false;
await pwa.activate(caches, async () => { claimed = true; });
offline = true;
const stillOffline = await (await pwa.handle(doc("/posts/hello/"), { cacheStorage: caches, fetchImpl, origin })).text();

const stored = caches.dump();
const allKeys = Object.values(stored).flat();

console.log(JSON.stringify({
  plans: {
    page: plan("/posts/hello/", { headers: { "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate" } }),
    css: plan("/css/style.min.abc.css"),
    js: plan("/js/media.js?v=aaa"),
    apiGet: plan("/api/comments"),
    apiPost: cachePlan(new Request(origin + "/api/subscribe", { method: "POST", body: "{}" }), origin),
    admin: plan("/admin/comments/", { headers: { "Sec-Fetch-Dest": "document" } }),
    adminBare: plan("/admin"),
    addPhotos: plan("/add-photos/"),
    manage: plan("/subscribe/manage/?token=abc", { headers: { "Sec-Fetch-Dest": "document" } }),
    cdn: plan("/cdn-cgi/trace"),
    sw: plan("/sw.js?v=1"),
    range: cachePlan(new Request(origin + "/audio/uploads/a.mp3", { headers: { Range: "bytes=0-1" } }), origin),
    cross: cachePlan(new Request("https://cdn.jsdelivr.net/npm/d3-geo@3"), origin),
    image: plan("/images/pic.jpg"),
  },
  shellUrls,
  cssOffline,
  visitedOnline,
  after500,
  visitedOffline,
  freshOffline,
  homeOffline,
  apiThrew,
  imageOnline,
  imageOffline,
  hugeThrew,
  claimed,
  stillOffline,
  cacheNames: Object.keys(stored),
  apiCached: allKeys.some((key) => key.startsWith("/api/")),
  hugeCached: allKeys.includes("/images/huge.jpg"),
  oldShell: stored["ericwiz-shell-old"] !== undefined,
}));
"""


class PwaLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        script = SCENARIO.replace("__SW__", SW_JS.as_uri())
        cls.report = run_node(script)

    def test_visited_page_is_served_offline_success(self) -> None:
        report = self.report
        self.assertEqual(report["plans"]["page"], "network-first-page")
        self.assertEqual(report["visitedOnline"], "v1")
        self.assertEqual(report["visitedOffline"], "v1")
        self.assertEqual(report["stillOffline"], "v1")
        self.assertIn("style.min.abc.css", report["homeOffline"])
        self.assertEqual(report["cssOffline"], "css-body")
        self.assertEqual(report["imageOnline"], "img")
        self.assertEqual(report["imageOffline"], "img")
        self.assertTrue(report["claimed"])
        self.assertFalse(report["oldShell"])
        self.assertIn("ericwiz-pages", report["cacheNames"])
        self.assertIn("ericwiz-shell-sha256-test-1", report["cacheNames"])

    def test_fresh_page_uses_offline_document_success(self) -> None:
        self.assertIn("You are offline", self.report["freshOffline"])
        self.assertNotIn("missing", self.report["freshOffline"])

    def test_failed_response_does_not_replace_cached_page_success(self) -> None:
        self.assertEqual(self.report["after500"], "v2")
        self.assertEqual(self.report["visitedOffline"], "v1")

    def test_api_admin_and_oversized_media_are_not_cached_failure(self) -> None:
        plans = self.report["plans"]
        self.assertEqual(plans["apiGet"], "network-only")
        self.assertEqual(plans["apiPost"], "network-only")
        self.assertEqual(plans["admin"], "network-only")
        self.assertEqual(plans["adminBare"], "network-only")
        self.assertEqual(plans["addPhotos"], "network-only")
        self.assertEqual(plans["manage"], "network-only")
        self.assertEqual(plans["cdn"], "network-only")
        self.assertEqual(plans["sw"], "network-only")
        self.assertEqual(plans["range"], "network-only")
        self.assertEqual(plans["cross"], "network-only")
        self.assertEqual(plans["css"], "cache-first")
        self.assertEqual(plans["js"], "cache-first")
        self.assertEqual(plans["image"], "network-first-asset")
        self.assertTrue(self.report["apiThrew"])
        self.assertFalse(self.report["apiCached"])
        self.assertTrue(self.report["hugeThrew"])
        self.assertFalse(self.report["hugeCached"])
        self.assertEqual(
            self.report["shellUrls"],
            ["/css/style.min.abc.css", "/js/media.js?v=aaa", "/js/nav-scroll.js?v=bbb"],
        )
        self.assertNotIn("/js/comments.js?v=ccc", self.report["shellUrls"])

    def test_install_fails_when_shell_file_is_missing_failure(self) -> None:
        script = f"""
        import {{ createPwa }} from {json.dumps(SW_JS.as_uri())};
        const caches = {{
          async open() {{ return {{ async put() {{}}, async match() {{ return undefined; }} }}; }},
          async keys() {{ return []; }},
          async delete() {{ return false; }},
        }};
        const fetchImpl = async (input) => new Response("no", {{ status: input === "/" ? 200 : 404 }});
        let failed = false;
        try {{
          await createPwa({{ version: "x" }}).install(caches, fetchImpl, "https://ericwisnewski.com");
        }} catch (err) {{
          failed = String(err && err.message || err).includes("precache failed");
        }}
        console.log(JSON.stringify({{ failed }}));
        """
        # Home HTML from the 200 response is empty, so shell files still 404.
        self.assertTrue(run_node(script)["failed"])


PREFETCH = r"""
import { createPwa, articleImageUrls, recentPostUrls, cacheKey } from "__SW__";

const origin = "https://ericwisnewski.com";
const quoted = [
  '<img src="/images/chrome.png">',
  '<article class="post-content">',
  '<img src="https://ericwisnewski.com/images/uploads/hero.jpg">',
  '<img src="/images/uploads/inline.jpg">',
  '<img src="https://cdn.example/x.jpg">',
  '<img src="/audio/uploads/clip.mp3">',
  '<img src="/api/comments">',
  '</article>',
  '<img src="/images/uploads/more-from.jpg">',
].join("");
const minified = '<article class=post-content><img src=/images/uploads/hero.jpg></article>';

function postHtml(image) {
  return "<article class=post-content><img src=" + image + "><img src=/audio/uploads/clip.mp3></article><img src=/images/more.jpg>";
}

class MemoryCache {
  constructor() { this.map = new Map(); }
  async match(key) {
    const hit = this.map.get(key);
    return hit ? hit.clone() : undefined;
  }
  async put(key, response) { this.map.set(key, response.clone()); }
}
class MemoryCaches {
  constructor() { this.map = new Map(); }
  async open(name) {
    if (!this.map.has(name)) this.map.set(name, new MemoryCache());
    return this.map.get(name);
  }
  async keys() { return [...this.map.keys()]; }
  async delete(name) { return this.map.delete(name); }
  dump() {
    const out = {};
    for (const [name, cache] of this.map) out[name] = [...cache.map.keys()];
    return out;
  }
}

const pack = [];
for (let i = 1; i <= 14; i += 1) pack.push("/posts/p" + i + "/");
pack.push("/posts/huge/");
pack.push("/posts/sixteen/");
pack.splice(2, 0, "/api/comments");

let index = { rev: "a", posts: pack };
let offline = false;
const calls = [];
const files = {
  "/": "<!doctype html><link rel=stylesheet href=/css/style.min.abc.css>",
  "/offline/": "<h1>You are offline</h1>",
  "/favicon.ico": "ico",
  "/favicon.png": "png",
  "/apple-touch-icon.png": "apple",
  "/icons/icon-192.png": "192",
  "/icons/icon-512.png": "512",
  "/manifest.webmanifest": "{}",
  "/css/style.min.abc.css": "css",
  "/posts/extra/": postHtml("/images/extra.jpg"),
};

function bodyFor(key) {
  if (key === "/recent.json") return JSON.stringify(index);
  if (key === "/posts/huge/") return postHtml("/images/huge.jpg");
  if (key === "/posts/extra/") return postHtml("/images/extra.jpg");
  if (key.startsWith("/posts/")) return postHtml("/images/hero.jpg");
  if (key === "/images/huge.jpg") {
    return new Response("huge", { status: 200, headers: { "Content-Type": "image/jpeg", "Content-Length": String(9 * 1024 * 1024) } });
  }
  if (key.startsWith("/images/")) return "img";
  return files[key];
}

async function fetchImpl(input) {
  if (offline) throw new Error("offline");
  const key = cacheKey(typeof input === "string" ? input : input.url, origin);
  calls.push(key);
  const body = bodyFor(key);
  if (body instanceof Response) return body;
  if (body == null) return new Response("missing", { status: 404 });
  return new Response(body, { status: 200, headers: { "Content-Type": key.endsWith(".jpg") ? "image/jpeg" : "text/html" } });
}

function doc(path) {
  return new Request(origin + path, {
    headers: { "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate" },
  });
}

const caches = new MemoryCaches();
const pwa = createPwa({ version: "prefetch" });
await pwa.install(caches, fetchImpl, origin);
const first = await pwa.prefetchRecent(caches, fetchImpl, origin);
const afterFirst = calls.filter((key) => key.startsWith("/posts/") || key.startsWith("/images/") || key.startsWith("/api/") || key.startsWith("/audio/")).slice();
await pwa.prefetchRecent(caches, fetchImpl, origin);
const postFetchesAfterRepeat = calls.filter((key) => key === "/posts/p1/").length;
const heroFetchesAfterRepeat = calls.filter((key) => key === "/images/hero.jpg").length;
index = { rev: "b", posts: ["/posts/extra/", ...pack.slice(0, 14)] };
const third = await pwa.prefetchRecent(caches, fetchImpl, origin);
const heroFetchesAfterRefresh = calls.filter((key) => key === "/images/hero.jpg").length;
const extraImageFetches = calls.filter((key) => key === "/images/extra.jpg").length;
offline = true;
const extraOffline = await (await pwa.handle(doc("/posts/extra/"), { cacheStorage: caches, fetchImpl, origin })).text();
let outside = "";
try {
  outside = await (await pwa.handle(doc("/posts/never-in-pack/"), { cacheStorage: caches, fetchImpl, origin })).text();
} catch (err) {
  outside = "threw";
}
const stored = Object.values(caches.dump()).flat();

console.log(JSON.stringify({
  quoted: articleImageUrls(quoted, origin),
  minified: articleImageUrls(minified, origin),
  capped: recentPostUrls({ posts: pack }, origin).length,
  apiDropped: recentPostUrls({ posts: ["/api/comments", "/posts/ok/"] }, origin),
  firstPosts: first.posts,
  firstFetched: first.fetched,
  afterFirst,
  postFetchesAfterRepeat,
  heroFetchesAfterRepeat,
  thirdFetched: third.fetched,
  heroFetchesAfterRefresh,
  extraImageFetches,
  extraOffline,
  outside,
  hugeStored: stored.includes("/images/huge.jpg"),
  heroStored: stored.includes("/images/hero.jpg"),
  apiStored: stored.some((key) => key.startsWith("/api/")),
  sixteenStored: stored.includes("/posts/sixteen/"),
  moreStored: stored.includes("/images/more.jpg"),
}));
"""


class PwaPrefetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_node(PREFETCH.replace("__SW__", SW_JS.as_uri()))

    def test_prefetch_caches_unvisited_posts_and_article_images_success(self) -> None:
        report = self.report
        self.assertEqual(
            report["quoted"],
            ["/images/uploads/hero.jpg", "/images/uploads/inline.jpg"],
        )
        self.assertEqual(report["minified"], ["/images/uploads/hero.jpg"])
        self.assertEqual(report["capped"], 15)
        self.assertIn("/images/extra.jpg", report["extraOffline"])
        self.assertIn("post-content", report["extraOffline"])
        self.assertEqual(report["outside"], "<h1>You are offline</h1>")
        self.assertTrue(report["heroStored"])
        self.assertEqual(report["heroFetchesAfterRepeat"], 1)
        self.assertEqual(report["postFetchesAfterRepeat"], 1)
        self.assertEqual(report["heroFetchesAfterRefresh"], 1)
        self.assertEqual(report["extraImageFetches"], 1)
        self.assertIn("/posts/extra/", report["thirdFetched"])

    def test_prefetch_skips_api_audio_and_oversized_images_failure(self) -> None:
        report = self.report
        self.assertEqual(report["apiDropped"], ["/posts/ok/"])
        self.assertFalse(report["apiStored"])
        self.assertFalse(report["sixteenStored"])
        self.assertFalse(report["hugeStored"])
        self.assertFalse(report["moreStored"])
        self.assertNotIn("/api/comments", report["afterFirst"])
        self.assertNotIn("/posts/sixteen/", report["afterFirst"])
        self.assertNotIn("/audio/uploads/clip.mp3", report["afterFirst"])
        self.assertNotIn("/images/more.jpg", report["afterFirst"])


class PwaAssetTests(unittest.TestCase):
    def test_manifest_names_colors_and_icons_success(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "Eric Wisnewski")
        self.assertEqual(manifest["short_name"], "Ericwiz")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["background_color"], "#ffffff")
        self.assertEqual(manifest["theme_color"], "#ffffff")
        self.assertNotIn("favicon.svg", MANIFEST.read_text(encoding="utf-8"))
        icons = {icon["sizes"]: icon for icon in manifest["icons"]}
        self.assertEqual(icons["192x192"]["src"], "/icons/icon-192.png")
        self.assertEqual(icons["192x192"]["type"], "image/png")
        self.assertEqual(icons["512x512"]["src"], "/icons/icon-512.png")
        self.assertEqual(icons["512x512"]["purpose"], "any")
        self.assertEqual(png_size(ICON_192), (192, 192))
        self.assertEqual(png_size(ICON_512), (512, 512))

    def test_head_links_manifest_and_baseof_skips_admin_success(self) -> None:
        head = HEAD.read_text(encoding="utf-8")
        self.assertIn('rel="manifest"', head)
        self.assertIn("manifest.webmanifest", head)
        self.assertIn('name="theme-color" content="#ffffff"', head)
        self.assertIn('name="apple-mobile-web-app-title" content="Ericwiz"', head)
        base = BASEOF.read_text(encoding="utf-8")
        self.assertIn("serviceWorker.register", base)
        self.assertIn('type: "module"', base)
        self.assertIn('eq .Type "admin"', base)
        self.assertIn('eq .Type "add-photos"', base)
        self.assertIn("/sw.js", base)
        self.assertIn("prefetch-recent", base)
        self.assertIn("requestIdleCallback", base)
        self.assertIn('printf "%s-2"', base)
        offline = OFFLINE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("You are offline", offline)
        self.assertIn("header.html", offline)
        self.assertIn("<h1>", offline)
        self.assertIn('href="{{ "/" | relURL }}"', offline)
        page = OFFLINE_PAGE.read_text(encoding="utf-8")
        self.assertIn("robots: noindex", page)
        self.assertIn("disable: true", page)
        robots = ROBOTS.read_text(encoding="utf-8")
        self.assertIn("Disallow: /offline/", robots)
        self.assertIn("Disallow: /recent.json", robots)
        headers = HEADERS.read_text(encoding="utf-8")
        self.assertIn("application/manifest+json", headers)
        self.assertIn("max-age=0, must-revalidate", headers)

    def test_worker_source_keeps_api_out_of_the_shell_failure(self) -> None:
        source = SW_JS.read_text(encoding="utf-8")
        self.assertIn('"/api/"', source)
        self.assertIn("network-only", source)
        self.assertNotIn('"/api/"', source.split("SHELL_FILES", 1)[1].split("];", 1)[0])
        self.assertIn("skipWaiting", source)
        self.assertIn("clients.claim", source)
        self.assertIn("ericwiz-pages", source)


class PwaBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="pwa-")
        root = Path(cls._tmp.name)
        content = root / "content"
        (content / "posts").mkdir(parents=True)
        (content / "admin").mkdir()
        (content / "posts" / "hello.md").write_text(
            "---\n"
            "title: Hello stadium\n"
            "slug: hello\n"
            "date: 2020-01-01T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            "A visited recap.\n",
            encoding="utf-8",
        )
        for day in range(1, 17):
            (content / "posts" / f"post-{day:02d}.md").write_text(
                "---\n"
                f"title: Post {day}\n"
                f"slug: post-{day:02d}\n"
                f"date: 2026-01-{day:02d}T00:00:00Z\n"
                "draft: false\n"
                "---\n"
                "Recap.\n",
                encoding="utf-8",
            )
        (content / "posts" / "secret.md").write_text(
            "---\n"
            "title: Secret\n"
            "slug: secret\n"
            "date: 2026-12-01T00:00:00Z\n"
            "draft: true\n"
            "---\n"
            "Hidden.\n",
            encoding="utf-8",
        )
        (content / "gradys-tour").mkdir()
        (content / "gradys-tour" / "rome.md").write_text(
            "---\n"
            "title: Rome\n"
            "slug: rome\n"
            "date: 2026-06-01T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            "Tour.\n",
            encoding="utf-8",
        )
        (content / "parking.md").write_text(
            "---\n"
            "title: Parking\n"
            "date: 2026-12-02T00:00:00Z\n"
            "---\n"
            "Not a post.\n",
            encoding="utf-8",
        )
        (content / "offline.md").write_text(OFFLINE_PAGE.read_text(encoding="utf-8"), encoding="utf-8")
        (content / "admin" / "comments.md").write_text(
            (REPO_ROOT / "content" / "admin" / "comments.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (content / "add-photos.md").write_text(
            (REPO_ROOT / "content" / "add-photos.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        dest = root / "public"
        cache_dir = root / "cache"
        cache_dir.mkdir()
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(dest),
                "--contentDir",
                str(content),
                "--cacheDir",
                str(cache_dir),
                "--noBuildLock",
                "--quiet",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "hugo failed")
        cls.public = dest

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_built_pages_link_manifest_and_register_sw_success(self) -> None:
        home = (self.public / "index.html").read_text(encoding="utf-8")
        offline = (self.public / "offline" / "index.html").read_text(encoding="utf-8")
        admin = (self.public / "admin" / "comments" / "index.html").read_text(encoding="utf-8")
        photos = (self.public / "add-photos" / "index.html").read_text(encoding="utf-8")
        self.assertIn('rel="manifest"', home)
        self.assertIn('href="/manifest.webmanifest"', home)
        self.assertNotIn("https://ericwisnewski.com/manifest.webmanifest", home)
        self.assertIn('name="theme-color" content="#ffffff"', home)
        self.assertIn("serviceWorker.register", home)
        self.assertIn("/sw.js?v=", home)
        self.assertIn('type: "module"', home)
        self.assertIn("requestIdleCallback", home)
        self.assertIn("prefetch-recent", home)
        self.assertNotIn("prefetch-recent", admin)
        self.assertIn("You are offline", offline)
        self.assertIn("Pages you already opened still work", offline)
        self.assertIn('href="/"', offline)
        self.assertNotIn("Get email when new posts go up", offline)
        self.assertIn("serviceWorker.register", offline)
        self.assertIn('name="robots" content="noindex, nofollow"', offline)
        self.assertNotIn("serviceWorker", admin)
        self.assertNotIn("serviceWorker", photos)
        self.assertTrue((self.public / "sw.js").is_file())
        self.assertTrue((self.public / "manifest.webmanifest").is_file())
        manifest = json.loads((self.public / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["short_name"], "Ericwiz")
        self.assertEqual(png_size(self.public / "icons" / "icon-192.png"), (192, 192))
        self.assertEqual(png_size(self.public / "icons" / "icon-512.png"), (512, 512))
        sitemap = (self.public / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/offline/", sitemap)
        robots = (self.public / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Disallow: /offline/", robots)
        self.assertIn("Disallow: /recent.json", robots)
        self.assertTrue((self.public / "index.xml").is_file())

    def test_recent_json_is_the_newest_15_posts_success(self) -> None:
        index = json.loads((self.public / "recent.json").read_text(encoding="utf-8"))
        posts = index["posts"]
        self.assertEqual(len(posts), 15)
        self.assertTrue(index["rev"])
        self.assertEqual(posts[0], "/gradys-tour/rome/")
        self.assertIn("/posts/post-16/", posts)
        self.assertNotIn("/posts/hello/", posts)
        self.assertNotIn("/posts/post-01/", posts)
        self.assertNotIn("/posts/post-02/", posts)
        self.assertNotIn("/posts/secret/", posts)
        self.assertNotIn("/parking/", posts)
        self.assertNotIn("/offline/", posts)
        sitemap = (self.public / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("recent.json", sitemap)

    def test_built_home_shell_urls_point_at_real_files_success(self) -> None:
        home = (self.public / "index.html").read_text(encoding="utf-8")
        script = (
            f"import {{ shellUrlsFromHomeHtml }} from {json.dumps(SW_JS.as_uri())};\n"
            f"console.log(JSON.stringify(shellUrlsFromHomeHtml({json.dumps(home)})));\n"
        )
        urls = run_node(script)
        self.assertIsInstance(urls, list)
        self.assertTrue(any(url.startswith("/css/") for url in urls), urls)
        self.assertTrue(any(url.startswith("/js/media.js?v=") for url in urls), urls)
        self.assertTrue(any(url.startswith("/js/nav-scroll.js?v=") for url in urls), urls)
        self.assertFalse(any("comments.js" in url for url in urls), urls)
        for url in urls:
            path = self.public / url.split("?", 1)[0].lstrip("/")
            self.assertTrue(path.is_file(), url)
