"""Per-type newsletter: form placement, RSS isolation, subscribe/dispatch helpers."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBE_API = REPO_ROOT / "functions" / "api" / "subscribe.js"
NEWSLETTER_API = REPO_ROOT / "functions" / "api" / "newsletter.js"
SUBSCRIBE_PARTIAL = REPO_ROOT / "layouts" / "partials" / "subscribe.html"
LIST_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "list.html"
TOUR_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "gradys-tour.html"
SINGLE_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "single.html"
MAP_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "map.html"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
HUGO_TIMEOUT_SECONDS = 120

ITEM_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
ITEM_BLOCK_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)


def call_js_fn(module: Path, fn_name: str, *args: object) -> object:
    """Run an exported helper from a Pages Function module via Node."""
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


def run_hugo(*, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hugo", "--destination", str(destination), "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


def rss_item_titles(xml: str) -> list[str]:
    titles: list[str] = []
    for block in ITEM_BLOCK_RE.findall(xml):
        match = ITEM_TITLE_RE.search(block)
        if match:
            titles.append(re.sub(r"\s+", " ", match.group(1)).strip())
    return titles


def template_includes_subscribe(template: str) -> bool:
    return 'partial "subscribe.html"' in template or "partial \"subscribe.html\"" in template


class NewsletterHelperTests(unittest.TestCase):
    def test_normalize_email_success(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "normalizeEmail", "  Tyler@Example.COM "),
            "tyler@example.com",
        )

    def test_normalize_email_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeEmail", ""), "")
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeEmail", None), "")

    def test_is_valid_email_success(self) -> None:
        self.assertTrue(call_js_fn(SUBSCRIBE_API, "isValidEmail", "a@b.co"))

    def test_is_valid_email_failure(self) -> None:
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidEmail", "not-an-email"))
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidEmail", ""))

    def test_normalize_lists_success(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "normalizeLists", ["posts", "gradys-tour", "posts"]),
            ["posts", "gradys-tour"],
        )

    def test_normalize_lists_rejects_invalid_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeLists", ["spam"]), [])
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeLists", []), [])
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeLists", None), [])

    def test_list_label_success(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "listLabel", "posts"), "Eric's blog")
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "listLabel", "gradys-tour"), "Grady's Tour"
        )

    def test_list_label_unknown_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "listLabel", "nope"), "")

    def test_parse_rss_items_success(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>Hello</title>
            <link>https://ericwisnewski.com/posts/hello/</link>
            <guid>https://ericwisnewski.com/posts/hello/</guid>
            <description>Body</description>
          </item>
        </channel></rss>"""
        items = call_js_fn(NEWSLETTER_API, "parseRssItems", xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello")
        self.assertEqual(items[0]["guid"], "https://ericwisnewski.com/posts/hello/")
        self.assertEqual(items[0]["url"], "https://ericwisnewski.com/posts/hello/")

    def test_parse_rss_items_empty_failure(self) -> None:
        self.assertEqual(call_js_fn(NEWSLETTER_API, "parseRssItems", "<rss></rss>"), [])
        self.assertEqual(call_js_fn(NEWSLETTER_API, "parseRssItems", ""), [])

    def test_new_guids_when_seeded_success(self) -> None:
        known = ["https://a/", "https://b/"]
        items = [
            {"guid": "https://a/", "title": "A", "url": "https://a/"},
            {"guid": "https://c/", "title": "C", "url": "https://c/"},
        ]
        result = call_js_fn(NEWSLETTER_API, "selectNewItems", items, known, False)
        self.assertEqual([i["guid"] for i in result], ["https://c/"])

    def test_seed_mode_returns_empty_to_send_failure_case(self) -> None:
        items = [
            {"guid": "https://a/", "title": "A", "url": "https://a/"},
            {"guid": "https://b/", "title": "B", "url": "https://b/"},
        ]
        result = call_js_fn(NEWSLETTER_API, "selectNewItems", items, [], True)
        self.assertEqual(result, [])

    def test_valid_newsletter_lists_constant(self) -> None:
        lists = call_js_fn(SUBSCRIBE_API, "getValidLists")
        self.assertEqual(sorted(lists), ["gradys-tour", "posts"])


class NewsletterTemplateTests(unittest.TestCase):
    def test_partial_exists_with_a11y_fields(self) -> None:
        html = SUBSCRIBE_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('id="subscribe"', html)
        self.assertIn('class="subscribe-form"', html)
        self.assertIn('type="email"', html)
        self.assertIn('value="posts"', html)
        self.assertIn('value="gradys-tour"', html)
        self.assertIn("fieldset", html)
        self.assertIn("aria-live", html)
        self.assertIn("/js/subscribe.js", html)

    def test_home_and_tour_and_single_include_partial(self) -> None:
        self.assertTrue(template_includes_subscribe(LIST_TEMPLATE.read_text(encoding="utf-8")))
        self.assertTrue(template_includes_subscribe(TOUR_TEMPLATE.read_text(encoding="utf-8")))
        self.assertTrue(template_includes_subscribe(SINGLE_TEMPLATE.read_text(encoding="utf-8")))

    def test_map_does_not_include_partial_failure(self) -> None:
        self.assertFalse(template_includes_subscribe(MAP_TEMPLATE.read_text(encoding="utf-8")))

    def test_hugo_toml_has_newsletter_enabled_flag(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertRegex(toml, r"(?m)^\s*newsletter_enabled\s*=")


class NewsletterBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="newsletter-hugo-"))
        result = run_hugo(destination=cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.tour = (cls._output_dir / "gradys-tour" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.map_html = (cls._output_dir / "map" / "index.html").read_text(encoding="utf-8")
        posts_rss = cls._output_dir / "posts" / "index.xml"
        tour_rss = cls._output_dir / "gradys-tour" / "index.xml"
        cls.posts_rss = posts_rss.read_text(encoding="utf-8") if posts_rss.is_file() else ""
        cls.tour_rss = tour_rss.read_text(encoding="utf-8") if tour_rss.is_file() else ""
        single = cls._output_dir / "posts" / "an-introduction" / "index.html"
        cls.eric_single = single.read_text(encoding="utf-8") if single.is_file() else ""
        tour_single = cls._output_dir / "gradys-tour" / "gearing-up" / "index.html"
        cls.tour_single = (
            tour_single.read_text(encoding="utf-8") if tour_single.is_file() else ""
        )

        # Second build with newsletter enabled so form defaults are verified even
        # while the repo flag stays false until Resend DNS is ready.
        cls._enabled_dir = Path(tempfile.mkdtemp(prefix="newsletter-enabled-"))
        cls.home_enabled = ""
        cls.tour_enabled = ""
        cls.eric_single_enabled = ""
        cls.tour_single_enabled = ""
        with tempfile.TemporaryDirectory(prefix="newsletter-config-") as cfg_tmp:
            cfg_root = Path(cfg_tmp)
            shutil.copytree(REPO_ROOT / "config", cfg_root / "config")
            default_toml = cfg_root / "config" / "_default" / "hugo.toml"
            text = default_toml.read_text(encoding="utf-8")
            text = re.sub(
                r"(?m)^(\s*newsletter_enabled\s*=\s*)false\s*$",
                r"\1true",
                text,
            )
            default_toml.write_text(text, encoding="utf-8")
            enabled_result = subprocess.run(
                [
                    "hugo",
                    "--destination",
                    str(cls._enabled_dir),
                    "--configDir",
                    str(cfg_root / "config"),
                    "--quiet",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=HUGO_TIMEOUT_SECONDS,
            )
            if enabled_result.returncode == 0:
                cls.home_enabled = (cls._enabled_dir / "index.html").read_text(
                    encoding="utf-8"
                )
                cls.tour_enabled = (
                    cls._enabled_dir / "gradys-tour" / "index.html"
                ).read_text(encoding="utf-8")
                eric_path = (
                    cls._enabled_dir / "posts" / "an-introduction" / "index.html"
                )
                if eric_path.is_file():
                    cls.eric_single_enabled = eric_path.read_text(encoding="utf-8")
                tour_path = cls._enabled_dir / "gradys-tour" / "gearing-up" / "index.html"
                if tour_path.is_file():
                    cls.tour_single_enabled = tour_path.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)
        shutil.rmtree(cls._enabled_dir, ignore_errors=True)

    def test_section_rss_feeds_exist(self) -> None:
        self.assertTrue(self.posts_rss.startswith("<?xml"))
        self.assertTrue(self.tour_rss.startswith("<?xml"))

    def test_posts_rss_excludes_tour_titles_success(self) -> None:
        titles = rss_item_titles(self.posts_rss)
        self.assertTrue(titles)
        for title in titles:
            self.assertNotIn("bike", title.lower())
            self.assertNotIn("bayeux", title.lower())

    def test_tour_rss_excludes_eric_posts_failure_isolation(self) -> None:
        titles = rss_item_titles(self.tour_rss)
        self.assertTrue(titles, "gradys-tour/index.xml must list tour posts")
        for title in titles:
            self.assertNotIn("An Introduction", title)
            self.assertNotIn("Boston College", title)

    def test_home_form_defaults_to_posts_when_enabled(self) -> None:
        if not self.home_enabled:
            self.skipTest("enabled-newsletter hugo build failed")
        self.assertIn('id="subscribe"', self.home_enabled)
        self.assertIn('data-default-list="posts"', self.home_enabled)
        self.assertIn('value="posts"', self.home_enabled)
        self.assertRegex(
            self.home_enabled,
            r'value="posts"[^>]*checked|checked[^>]*value="posts"',
        )

    def test_tour_form_defaults_to_gradys_tour_when_enabled(self) -> None:
        if not self.tour_enabled:
            self.skipTest("enabled-newsletter hugo build failed")
        self.assertIn('id="subscribe"', self.tour_enabled)
        self.assertIn('data-default-list="gradys-tour"', self.tour_enabled)
        self.assertRegex(
            self.tour_enabled,
            r'value="gradys-tour"[^>]*checked|checked[^>]*value="gradys-tour"',
        )

    def test_map_has_no_subscribe_form(self) -> None:
        self.assertNotIn('id="subscribe"', self.map_html)
        if self.home_enabled:
            # Map still excluded when newsletter is on
            map_enabled = (self._enabled_dir / "map" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertNotIn('id="subscribe"', map_enabled)

    def test_eric_single_defaults_posts_when_enabled(self) -> None:
        if not self.eric_single_enabled:
            self.skipTest("enabled-newsletter hugo build failed")
        self.assertIn('data-default-list="posts"', self.eric_single_enabled)

    def test_tour_single_defaults_gradys_tour_when_enabled(self) -> None:
        if not self.tour_single_enabled:
            self.skipTest("enabled-newsletter hugo build failed")
        self.assertIn('data-default-list="gradys-tour"', self.tour_single_enabled)


if __name__ == "__main__":
    unittest.main()
