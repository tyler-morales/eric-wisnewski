"""Tab icon and site emails use the PNG portrait, not the wizard SVG."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"
SHARED_API = REPO_ROOT / "lib" / "api.js"
SUBSCRIBE_API = REPO_ROOT / "functions" / "api" / "subscribe.js"
NEWSLETTER_API = REPO_ROOT / "functions" / "api" / "newsletter.js"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
FAVICON = REPO_ROOT / "static" / "favicon.png"
FAVICON_ICO = REPO_ROOT / "static" / "favicon.ico"
OLD_SVG = REPO_ROOT / "static" / "favicon.svg"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
ICO_MAGIC = b"\x00\x00\x01\x00"
PORTRAIT_PNG_URL = "https://ericwisnewski.com/favicon.png"


def call_js_fn(module: Path, fn_name: str, *args: object) -> object:
    if not module.is_file():
        raise FileNotFoundError(module)
    arg_list = ", ".join(json.dumps(a) for a in args)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(module.as_uri())};\n"
        f"const result = {fn_name}({arg_list});\n"
        f"Promise.resolve(result).then((v) => console.log(JSON.stringify(v)));\n"
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


def assert_portrait_email_html(test: unittest.TestCase, html: str) -> None:
    test.assertIn(PORTRAIT_PNG_URL, html)
    test.assertIn("<img", html)
    test.assertIn('alt="Eric Wisnewski"', html)
    test.assertNotIn("favicon.svg", html)
    test.assertNotIn("image/svg+xml", html)
    test.assertNotIn("🧙", html)


class FaviconTemplateTests(unittest.TestCase):
    def test_head_links_png_and_ico_icon_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('rel="icon"', head)
        self.assertIn("favicon.png", head)
        self.assertIn("favicon.ico", head)
        self.assertIn("image/png", head)
        self.assertIn("apple-touch-icon.png", head)

    def test_head_does_not_link_svg_icon_failure(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("favicon.svg", head)
        self.assertNotIn("image/svg+xml", head)
        self.assertNotIn("🧙", head)


class FaviconAssetTests(unittest.TestCase):
    def test_png_favicon_is_at_least_48px_for_google_success(self) -> None:
        data = FAVICON.read_bytes()
        self.assertTrue(data.startswith(PNG_MAGIC), "favicon.png must be PNG")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 48, "Google Search wants favicons ≥ 48×48")
        self.assertLess(len(data), 40_000, "favicon should stay small")

    def test_ico_favicon_is_the_same_portrait_size_success(self) -> None:
        data = FAVICON_ICO.read_bytes()
        self.assertTrue(data.startswith(ICO_MAGIC), "favicon.ico must be an ICO")
        self.assertEqual(data[6], 48, "ICO width should match the 48×48 PNG")
        self.assertEqual(data[7], 48, "ICO height should match the 48×48 PNG")
        self.assertLess(len(data), 40_000, "favicon.ico should stay small")

    def test_wizard_svg_favicon_is_gone_failure(self) -> None:
        self.assertFalse(OLD_SVG.is_file(), "static/favicon.svg is leftover wizard emoji")
        self.assertNotEqual(FAVICON.suffix.lower(), ".svg")
        ico = FAVICON_ICO.read_bytes()
        self.assertNotIn(b"svg", ico.lower())
        self.assertNotIn("🧙".encode(), ico)
        self.assertFalse(ico.startswith(PNG_MAGIC), "raw PNG at .ico 404s some mail clients")


class EmailPortraitTests(unittest.TestCase):
    def test_branded_email_html_prepends_portrait_success(self) -> None:
        html = call_js_fn(SHARED_API, "brandedEmailHtml", "<p>Hello</p>")
        assert_portrait_email_html(self, html)
        self.assertIn("<p>Hello</p>", html)
        self.assertLess(html.index(PORTRAIT_PNG_URL), html.index("Hello"))

    def test_branded_email_html_skips_wizard_failure(self) -> None:
        html = call_js_fn(SHARED_API, "brandedEmailHtml", "")
        assert_portrait_email_html(self, html)
        self.assertNotIn("favicon.svg", html)

    def test_outbound_mail_html_includes_portrait_success(self) -> None:
        confirm = call_js_fn(
            SUBSCRIBE_API,
            "confirmEmailBody",
            "https://ericwisnewski.com",
            "ab" * 24,
            ["posts"],
        )
        manage = call_js_fn(
            SUBSCRIBE_API,
            "manageEmailBody",
            "https://ericwisnewski.com",
            "ab" * 24,
        )
        post = call_js_fn(
            NEWSLETTER_API,
            "postEmailContent",
            "posts",
            {"title": "Hello", "url": "https://ericwisnewski.com/posts/hello/"},
            "https://ericwisnewski.com",
            "tok",
            "",
        )
        reply = call_js_fn(
            COMMENTS_API,
            "replyNotifyEmail",
            {
                "parentAuthor": "Pat",
                "replyAuthor": "Grady",
                "replyText": "See you at 6.",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        writer = call_js_fn(
            COMMENTS_API,
            "writerNotifyEmail",
            {
                "commentAuthor": "Pat",
                "commentText": "Great post.",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        for name, mail in (
            ("confirm", confirm),
            ("manage", manage),
            ("newsletter", post),
            ("reply", reply),
            ("writer", writer),
        ):
            with self.subTest(mail=name):
                assert_portrait_email_html(self, mail["html"])

    def test_outbound_mail_html_does_not_use_wizard_failure(self) -> None:
        sources = (
            SUBSCRIBE_API.read_text(encoding="utf-8")
            + NEWSLETTER_API.read_text(encoding="utf-8")
            + COMMENTS_API.read_text(encoding="utf-8")
            + SHARED_API.read_text(encoding="utf-8")
        )
        self.assertIn("brandedEmailHtml", sources)
        self.assertNotIn("favicon.svg", sources)
        self.assertNotIn("🧙", sources)
        self.assertNotIn("image/svg+xml", sources)
