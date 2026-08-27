"""Post share: byline + end of article; native sheet or copy/social menu."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARE_JS = REPO_ROOT / "static" / "js" / "share.js"
SHARE_PARTIAL = REPO_ROOT / "layouts" / "partials" / "share.html"
SINGLE_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "single.html"
UPDATES_ENTRY_LAYOUT = REPO_ROOT / "layouts" / "updates" / "single.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
HUGO_TIMEOUT_SECONDS = 120


def call_share(fn_name: str, script_body: str) -> object:
    if not SHARE_JS.is_file():
        raise FileNotFoundError(SHARE_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(SHARE_JS.as_uri())};\n"
        + script_body
    )
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


def layout_files() -> list[Path]:
    return sorted((REPO_ROOT / "layouts").rglob("*.html"))


class ShareTemplateTests(unittest.TestCase):
    def test_article_single_includes_share_twice_success(self) -> None:
        template = SINGLE_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(template.count('partial "share.html"'), 2)
        self.assertIn("post-meta", template)
        self.assertIn('id" "header"', template)
        self.assertIn('id" "footer"', template)
        self.assertIn("/js/share.js", template)
        self.assertIn('"/js/share.js"', template)
        self.assertNotIn('" /js/share.js"', template)
        header_at = template.find('id" "header"')
        footer_at = template.find('id" "footer"')
        bio_at = template.find('author-bio.html')
        self.assertGreater(footer_at, header_at)
        self.assertGreater(bio_at, footer_at)

    def test_share_partial_has_common_targets_success(self) -> None:
        partial = SHARE_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("Copy link", partial)
        self.assertIn("mailto:", partial)
        self.assertIn("sms:", partial)
        self.assertIn("wa.me", partial)
        self.assertIn("facebook.com/sharer", partial)
        self.assertIn("twitter.com/intent/tweet", partial)
        self.assertIn("aria-expanded", partial)
        self.assertIn("aria-controls", partial)
        self.assertIn('type="button"', partial)
        self.assertIn("post-share-toggle", partial)

    def test_share_absent_from_non_article_layouts_failure(self) -> None:
        offenders: list[str] = []
        for path in layout_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in {
                "layouts/partials/share.html",
                "layouts/_default/single.html",
            }:
                continue
            if 'partial "share.html"' in path.read_text(encoding="utf-8"):
                offenders.append(rel)
        self.assertEqual(offenders, [])
        updates = UPDATES_ENTRY_LAYOUT.read_text(encoding="utf-8")
        self.assertNotIn("share.html", updates)


class ShareCssTests(unittest.TestCase):
    def test_share_is_in_flow_sans_chrome_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".post-share", css)
        self.assertIn(".post-share-toggle:focus-visible", css)
        self.assertIn(".post-share-menu a:focus-visible", css)
        self.assertIn(".post-meta", css)
        share_block = css.split("\n.post-share {", 1)[-1].split("}", 1)[0]
        self.assertIn("var(--font-sans)", share_block)
        self.assertIn("position: relative", share_block)

    def test_share_is_not_a_sticky_rail_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        share_css = css[css.find(".post-share") :]
        share_css = share_css.split(".author-bio", 1)[0]
        self.assertNotIn("position: fixed", share_css)
        self.assertNotIn("position: sticky", share_css)
        self.assertNotIn("position:fixed", share_css)


class ShareHelperTests(unittest.TestCase):
    def test_share_payload_uses_title_and_url_success(self) -> None:
        payload = call_share(
            "sharePayload",
            """
console.log(JSON.stringify(sharePayload('  Hello  ', ' https://ex.test/p/ ')));
""",
        )
        self.assertEqual(
            payload,
            {"title": "Hello", "text": "Hello", "url": "https://ex.test/p/"},
        )

    def test_share_payload_blank_title_failure(self) -> None:
        payload = call_share(
            "sharePayload",
            """
console.log(JSON.stringify(sharePayload('   ', '')));
""",
        )
        self.assertEqual(payload, {"title": "", "text": "", "url": ""})

    def test_can_use_native_share_when_present_success(self) -> None:
        payload = call_share(
            "canUseNativeShare",
            """
console.log(JSON.stringify({
  any: canUseNativeShare({ share: function () {} }),
  phone: canUseNativeShare({ share: function () {} }, 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
}));
""",
        )
        self.assertTrue(payload["any"])
        self.assertTrue(payload["phone"])

    def test_can_use_native_share_when_missing_failure(self) -> None:
        payload = call_share(
            "canUseNativeShare",
            """
console.log(JSON.stringify({
  empty: canUseNativeShare({}),
  missing: canUseNativeShare(null),
  desktop: canUseNativeShare({ share: function () {} }, 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0')
}));
""",
        )
        self.assertFalse(payload["empty"])
        self.assertFalse(payload["missing"])
        self.assertFalse(payload["desktop"])

    def test_share_or_fallback_prefers_native_success(self) -> None:
        payload = call_share(
            "shareOrFallback",
            """
const nav = { share: async () => { nav.called = true; } };
const calls = [];
await shareOrFallback(nav, { title: 'T', text: 'T', url: 'https://x' }, () => calls.push('fallback'));
console.log(JSON.stringify({ called: !!nav.called, fallback: calls }));
""",
        )
        self.assertTrue(payload["called"])
        self.assertEqual(payload["fallback"], [])

    def test_share_or_fallback_opens_menu_without_native_failure(self) -> None:
        payload = call_share(
            "shareOrFallback",
            """
const calls = [];
await shareOrFallback({}, { title: 'T', text: 'T', url: 'https://x' }, () => calls.push('fallback'));
console.log(JSON.stringify(calls));
""",
        )
        self.assertEqual(payload, ["fallback"])

    def test_share_or_fallback_ignores_abort_failure(self) -> None:
        payload = call_share(
            "shareOrFallback",
            """
const err = new Error('nope');
err.name = 'AbortError';
const nav = { share: async () => { throw err; } };
const calls = [];
await shareOrFallback(nav, { title: 'T', text: 'T', url: 'https://x' }, () => calls.push('fallback'));
console.log(JSON.stringify(calls));
""",
        )
        self.assertEqual(payload, [])

    def test_copy_link_writes_url_success(self) -> None:
        payload = call_share(
            "copyLink",
            """
const written = [];
await copyLink('https://ex.test/p/', { writeText: async (v) => written.push(v) });
console.log(JSON.stringify(written));
""",
        )
        self.assertEqual(payload, ["https://ex.test/p/"])

    def test_copy_link_falls_back_to_exec_command_success(self) -> None:
        payload = call_share(
            "copyLink",
            """
const copied = [];
const doc = {
  body: { appendChild() {}, removeChild() {} },
  createElement() { return { value: '', setAttribute() {}, style: {}, select() {} }; },
  execCommand(cmd) { copied.push(cmd); return true; }
};
await copyLink('https://ex.test/p/', { writeText: async () => { throw new Error('denied'); } }, doc);
console.log(JSON.stringify(copied));
""",
        )
        self.assertEqual(payload, ["copy"])

    def test_copy_link_without_clipboard_failure(self) -> None:
        payload = call_share(
            "copyLink",
            """
let failed = false;
try { await copyLink('https://ex.test/p/', null); } catch (e) { failed = true; }
console.log(JSON.stringify(failed));
""",
        )
        self.assertTrue(payload)


class ShareBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="post-share-")
        root = Path(cls._tmp.name)
        content_dir = root / "content"
        (content_dir / "posts").mkdir(parents=True)
        (content_dir / "posts" / "hello.md").write_text(
            "---\n"
            "title: Hello Share\n"
            "slug: hello\n"
            "date: 2026-01-01T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            "Body\n",
            encoding="utf-8",
        )
        (content_dir / "privacy.md").write_text(
            "---\ntitle: Privacy\nlayout: subscribe-status\n---\nHi\n",
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
                str(content_dir),
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
            cls._tmp.cleanup()
            raise RuntimeError(result.stderr or result.stdout or "hugo build failed")
        cls.dest = dest

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_built_post_has_header_and_footer_share_success(self) -> None:
        html = (self.dest / "posts" / "hello" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('class="post-share post-share--header"'), 1)
        self.assertEqual(html.count('class="post-share post-share--footer"'), 1)
        self.assertIn("Copy link", html)
        self.assertIn("mailto:", html)
        self.assertIn("/js/share.js", html)
        self.assertNotIn("/ /js/share.js", html)
        self.assertNotIn("%20/js/share.js", html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn("Hello Share", html)
        meta = html.split('class="post-meta"', 1)[-1].split("</div>", 1)[0]
        self.assertIn("<time", meta)

    def test_home_and_privacy_have_no_share_failure(self) -> None:
        home = (self.dest / "index.html").read_text(encoding="utf-8")
        privacy = (self.dest / "privacy" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("post-share", home)
        self.assertNotIn("post-share", privacy)
        self.assertNotIn("/js/share.js", home)


class ShareDocsTests(unittest.TestCase):
    def test_readme_documents_share_button_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("Share", readme)
        self.assertIn("share sheet", readme.lower())
        lowered = readme.lower()
        self.assertTrue("copy" in lowered and "share" in lowered)
