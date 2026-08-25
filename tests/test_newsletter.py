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
SUBSCRIBE_JS = REPO_ROOT / "static" / "js" / "subscribe.js"
SUBSCRIBE_PARTIAL = REPO_ROOT / "layouts" / "partials" / "subscribe.html"
SUBSCRIBE_MANAGE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "subscribe-manage.html"
SUBSCRIBE_MANAGE_CONTENT = REPO_ROOT / "content" / "subscribe" / "manage.md"
SUBSCRIBE_INVALID_CONTENT = REPO_ROOT / "content" / "subscribe" / "invalid.md"
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

    def test_newsletter_from_header_uses_from_email_success(self) -> None:
        env = {"NEWSLETTER_FROM_EMAIL": "hello@ericwisnewski.com"}
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "newsletterFromHeader", env, "Eric Wisnewski"),
            "Eric Wisnewski <hello@ericwisnewski.com>",
        )
        self.assertEqual(
            call_js_fn(NEWSLETTER_API, "newsletterFromHeader", env, "Grady's Tour"),
            "Grady's Tour <hello@ericwisnewski.com>",
        )

    def test_newsletter_from_header_defaults_when_unset_failure(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "newsletterFromHeader", {}, "Eric Wisnewski"),
            "Eric Wisnewski <hello@ericwisnewski.com>",
        )

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

    def test_already_subscribed_message_success(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "subscriptionStatusMessage", ["posts"], []),
            "You're already subscribed to Eric's blog.",
        )
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "subscriptionStatusMessage",
                ["posts", "gradys-tour"],
                [],
            ),
            "You're already subscribed to Eric's blog and Grady's Tour.",
        )

    def test_already_subscribed_message_mixed_success(self) -> None:
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "subscriptionStatusMessage",
                ["posts"],
                ["gradys-tour"],
            ),
            "You're already subscribed to Eric's blog. Check your inbox to confirm Grady's Tour.",
        )

    def test_already_subscribed_message_new_signup_failure(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "subscriptionStatusMessage", [], ["posts"]),
            "Check your inbox to confirm your subscription. If you don't see it, look in spam.",
        )
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "subscriptionStatusMessage", [], []),
            "Check your inbox to confirm your subscription. If you don't see it, look in spam.",
        )

    def test_is_valid_token_success(self) -> None:
        self.assertTrue(call_js_fn(SUBSCRIBE_API, "isValidToken", "ab" * 24))

    def test_is_valid_token_failure(self) -> None:
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidToken", ""))
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidToken", None))
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidToken", "abc123"))
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidToken", "g" + ("a" * 47)))
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidToken", ("a" * 48) + "a"))

    def test_confirm_outcome_pending_success(self) -> None:
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "confirmOutcome",
                [{"status": "pending"}, {"status": "confirmed"}],
            ),
            "confirm",
        )

    def test_confirm_outcome_already_confirmed_success(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "confirmOutcome", [{"status": "confirmed"}]),
            "already",
        )

    def test_confirm_outcome_invalid_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "confirmOutcome", []), "invalid")
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "confirmOutcome", None), "invalid")
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "confirmOutcome",
                [{"status": "unsubscribed"}],
            ),
            "invalid",
        )

    def test_confirm_redirect_path_success(self) -> None:
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "confirmRedirectPath",
                [{"status": "pending"}],
            ),
            "/subscribe/confirmed/",
        )
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "confirmRedirectPath",
                [{"status": "confirmed"}],
            ),
            "/subscribe/confirmed/",
        )

    def test_confirm_redirect_path_invalid_failure(self) -> None:
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "confirmRedirectPath", []),
            "/subscribe/invalid/",
        )
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "confirmRedirectPath",
                [{"status": "unsubscribed"}],
            ),
            "/subscribe/invalid/",
        )

    def test_public_origin_pinned_success(self) -> None:
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "publicOrigin",
                {"NEWSLETTER_SITE_ORIGIN": "https://ericwisnewski.com/"},
                {"url": "https://evil.example/api/subscribe"},
            ),
            "https://ericwisnewski.com",
        )

    def test_public_origin_rejects_non_http_failure(self) -> None:
        self.assertEqual(
            call_js_fn(
                SUBSCRIBE_API,
                "publicOrigin",
                {"NEWSLETTER_SITE_ORIGIN": "javascript:alert(1)"},
                {"url": "https://ericwisnewski.com/api/subscribe"},
            ),
            "https://ericwisnewski.com",
        )

    def test_normalize_lists_accepts_single_string_success(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeLists", "posts"), ["posts"])

    def test_normalize_lists_string_invalid_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "normalizeLists", "spam"), [])

    def test_is_valid_email_rejects_header_injection_failure(self) -> None:
        self.assertFalse(call_js_fn(SUBSCRIBE_API, "isValidEmail", "a@b.com\nCc:x@y.z"))

    def test_preference_update_plan_pending_confirms_success(self) -> None:
        current = [{"list": "posts", "status": "pending"}]
        plan = call_js_fn(SUBSCRIBE_API, "preferenceUpdatePlan", current, ["posts"])
        self.assertEqual(plan["subscribe"], ["posts"])
        self.assertEqual(plan["unsubscribe"], [])

    def test_preference_update_plan_subscribe_success(self) -> None:
        current = [{"list": "posts", "status": "confirmed"}]
        plan = call_js_fn(
            SUBSCRIBE_API, "preferenceUpdatePlan", current, ["posts", "gradys-tour"]
        )
        self.assertEqual(plan["subscribe"], ["gradys-tour"])
        self.assertEqual(plan["unsubscribe"], [])

    def test_preference_update_plan_unsubscribe_success(self) -> None:
        current = [
            {"list": "posts", "status": "confirmed"},
            {"list": "gradys-tour", "status": "confirmed"},
        ]
        plan = call_js_fn(SUBSCRIBE_API, "preferenceUpdatePlan", current, ["posts"])
        self.assertEqual(plan["subscribe"], [])
        self.assertEqual(plan["unsubscribe"], ["gradys-tour"])

    def test_preference_update_plan_empty_unsubscribes_all_failure(self) -> None:
        current = [{"list": "posts", "status": "confirmed"}]
        plan = call_js_fn(SUBSCRIBE_API, "preferenceUpdatePlan", current, [])
        self.assertEqual(plan["subscribe"], [])
        self.assertEqual(plan["unsubscribe"], ["posts"])

    def test_preference_update_plan_ignores_invalid_lists_failure(self) -> None:
        current = [{"list": "posts", "status": "confirmed"}]
        plan = call_js_fn(SUBSCRIBE_API, "preferenceUpdatePlan", current, ["spam"])
        self.assertEqual(plan["subscribe"], [])
        self.assertEqual(plan["unsubscribe"], ["posts"])

    def test_preferences_payload_success(self) -> None:
        payload = call_js_fn(
            SUBSCRIBE_API,
            "preferencesPayload",
            "a@b.co",
            [
                {"list": "posts", "status": "confirmed"},
                {"list": "gradys-tour", "status": "unsubscribed"},
            ],
        )
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["email"], "a@b.co")
        self.assertEqual(payload["lists"], ["posts"])

    def test_preferences_payload_empty_failure(self) -> None:
        payload = call_js_fn(SUBSCRIBE_API, "preferencesPayload", "a@b.co", [])
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["lists"], [])

    def test_newsletter_links_manage_and_one_click_success(self) -> None:
        links = call_js_fn(
            NEWSLETTER_API,
            "newsletterLinks",
            "https://ericwisnewski.com",
            "abc123",
        )
        self.assertEqual(
            links["manageUrl"],
            "https://ericwisnewski.com/subscribe/manage/?token=abc123",
        )
        self.assertEqual(
            links["oneClickUrl"],
            "https://ericwisnewski.com/api/subscribe?unsubscribe=abc123",
        )

    def test_newsletter_links_encodes_token_failure(self) -> None:
        links = call_js_fn(
            NEWSLETTER_API,
            "newsletterLinks",
            "https://ericwisnewski.com",
            "a b",
        )
        self.assertIn("token=a%20b", links["manageUrl"])
        self.assertNotEqual(links["manageUrl"], links["oneClickUrl"])


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
        self.assertNotIn("Choose Eric", html)
        self.assertNotIn("confirmation link", html)
        self.assertNotIn("subscribe-intro", html)

    def test_subscribe_js_keeps_checkboxes_after_submit_success(self) -> None:
        js = SUBSCRIBE_JS.read_text(encoding="utf-8")
        self.assertNotIn("formEl.reset()", js)
        self.assertNotIn("form.reset()", js)
        self.assertIn("selectedLists(formEl)", js)

    def test_subscribe_js_reset_form_failure(self) -> None:
        js = SUBSCRIBE_JS.read_text(encoding="utf-8")
        self.assertNotRegex(js, r"dataset\.defaultList")

    def test_manage_page_has_list_checkboxes_success(self) -> None:
        self.assertTrue(SUBSCRIBE_MANAGE_LAYOUT.is_file())
        self.assertTrue(SUBSCRIBE_MANAGE_CONTENT.is_file())
        html = SUBSCRIBE_MANAGE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('id="subscribe-manage"', html)
        self.assertIn('value="posts"', html)
        self.assertIn('value="gradys-tour"', html)
        self.assertIn("fieldset", html)
        self.assertIn("aria-live", html)
        self.assertIn("/js/subscribe.js", html)
        self.assertIn('type="submit"', html)

    def test_manage_page_missing_token_copy_failure(self) -> None:
        html = SUBSCRIBE_MANAGE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("role=\"alert\"", html)
        self.assertNotIn("cf-turnstile", html.lower())
        self.assertNotIn("turnstile", html.lower())

    def test_invalid_link_page_exists_success(self) -> None:
        self.assertTrue(SUBSCRIBE_INVALID_CONTENT.is_file())
        text = SUBSCRIBE_INVALID_CONTENT.read_text(encoding="utf-8")
        self.assertIn("invalid", text.lower())
        self.assertNotIn("You’re confirmed", text)
        self.assertNotIn("You're confirmed", text)

    def test_subscribe_js_parses_non_json_safely_success(self) -> None:
        js = SUBSCRIBE_JS.read_text(encoding="utf-8")
        self.assertIn("JSON.parse", js)
        self.assertIn("res.text()", js)

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
        manage_page = cls._output_dir / "subscribe" / "manage" / "index.html"
        cls.manage_html = (
            manage_page.read_text(encoding="utf-8") if manage_page.is_file() else ""
        )
        invalid_page = cls._output_dir / "subscribe" / "invalid" / "index.html"
        cls.invalid_html = (
            invalid_page.read_text(encoding="utf-8") if invalid_page.is_file() else ""
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

    def test_manage_page_builds_with_preference_form_success(self) -> None:
        self.assertTrue(self.manage_html, "/subscribe/manage/ must build")
        self.assertIn('id="subscribe-manage"', self.manage_html)
        self.assertIn('value="posts"', self.manage_html)
        self.assertIn('value="gradys-tour"', self.manage_html)
        self.assertIn("Save preferences", self.manage_html)

    def test_home_form_omits_intro_copy_when_enabled(self) -> None:
        if not self.home_enabled:
            self.skipTest("enabled-newsletter hugo build failed")
        self.assertNotIn("Choose Eric", self.home_enabled)
        self.assertNotIn("confirmation link", self.home_enabled)

    def test_invalid_link_page_builds_success(self) -> None:
        self.assertTrue(self.invalid_html, "/subscribe/invalid/ must build")
        self.assertNotIn("You’re confirmed", self.invalid_html)
        self.assertIn("home page", self.invalid_html.lower())


if __name__ == "__main__":
    unittest.main()
