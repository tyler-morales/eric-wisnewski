"""Site-wide footer: copyright, privacy, updates, webmaster contact."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASEOF = REPO_ROOT / "layouts" / "_default" / "baseof.html"
FOOTER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "footer.html"
PRIVACY_PAGE = REPO_ROOT / "content" / "privacy.md"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
HUGO_TIMEOUT_SECONDS = 120

BUILDER_NAME = "Tyler Morales"
BUILDER_URL = "https://tylermorales.pro"


def footer_html(html: str) -> str:
    match = re.search(r"<footer\b[^>]*>.*?</footer>", html, re.DOTALL | re.IGNORECASE)
    return match.group(0) if match else ""


def has_webmaster_invite(html: str) -> bool:
    lowered = html.lower()
    if "webmaster" not in lowered:
        return False
    if "comment" not in lowered and "question" not in lowered:
        return False
    if BUILDER_NAME.lower() not in lowered:
        return False
    return BUILDER_URL in html


def has_copyright(html: str) -> bool:
    if "©" not in html and "copyright" not in html.lower():
        return False
    return "Eric Wisnewski" in html


def has_privacy_link(html: str) -> bool:
    return bool(
        re.search(
            r'<a\b[^>]*href="[^"]*privacy[^"]*"[^>]*>\s*Privacy\s*</a>',
            html,
            re.IGNORECASE,
        )
    )


class FooterTemplateTests(unittest.TestCase):
    def test_baseof_includes_footer_partial_success(self) -> None:
        template = BASEOF.read_text(encoding="utf-8")
        self.assertRegex(template, r'\{\{\s*partial\s+"footer\.html"')

    def test_baseof_puts_footer_after_main_block_success(self) -> None:
        template = BASEOF.read_text(encoding="utf-8")
        main_at = template.find('block "main"')
        footer_at = template.find('partial "footer.html"')
        self.assertGreater(main_at, 0)
        self.assertGreater(footer_at, main_at)

    def test_footer_partial_is_semantic_footer_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("<footer", partial)
        self.assertIn("</footer>", partial)

    def test_footer_partial_invites_webmaster_contact_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        lowered = partial.lower()
        self.assertIn("webmaster", lowered)
        self.assertTrue("comment" in lowered or "question" in lowered)
        self.assertIn("builder_url", partial)
        self.assertIn("tylermorales.pro", lowered)

    def test_footer_partial_omits_built_by_failure(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("Built by", partial)

    def test_footer_partial_has_copyright_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertTrue("©" in partial or "now.Year" in partial)
        self.assertTrue(".Site.Title" in partial or "Eric Wisnewski" in partial)

    def test_footer_partial_links_privacy_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("privacy/", partial)
        self.assertIn(">Privacy</a>", partial)

    def test_footer_updates_link_gates_on_the_page_having_a_url_success(self) -> None:
        """Staged sections render 'never', so the link must follow RelPermalink."""
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('.Site.GetPage "/updates"', partial)
        self.assertIn("RelPermalink", partial)
        self.assertIn(">Updates</a>", partial)
        self.assertNotIn('"updates/" | relURL', partial)

    def test_footer_authors_link_gates_on_the_page_having_a_url_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('.Site.GetPage "/authors"', partial)
        self.assertIn(">Contributors</a>", partial)
        self.assertNotIn('"authors/" | relURL', partial)

    def test_hugo_toml_has_builder_params_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIn("builder_name", toml)
        self.assertIn(BUILDER_NAME, toml)
        self.assertIn("builder_url", toml)
        self.assertIn(BUILDER_URL, toml)

    def test_builder_url_is_https_failure(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        match = re.search(r"builder_url\s*=\s*['\"]([^'\"]+)['\"]", toml)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertTrue(match.group(1).startswith("https://"))
        self.assertNotIn("http://", match.group(1))

    def test_privacy_page_exists_and_is_short_success(self) -> None:
        self.assertTrue(PRIVACY_PAGE.is_file())
        text = PRIVACY_PAGE.read_text(encoding="utf-8")
        self.assertIn("title: Privacy", text)
        body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL).strip()
        self.assertGreater(len(body), 40)
        self.assertLess(len(body), 800)

    def test_privacy_page_is_not_a_blog_post_failure(self) -> None:
        text = PRIVACY_PAGE.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^layout:\s*single\s*$")
        self.assertIn("layout:", text)

    def test_footer_css_has_focus_visible_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".site-footer", css)
        self.assertRegex(css, r"\.site-footer a:focus-visible")

    def test_baseof_marks_the_page_top_success(self) -> None:
        template = BASEOF.read_text(encoding="utf-8")
        self.assertRegex(template, r"<html\b[^>]*\bid=\"top\"")

    def test_baseof_omits_floating_back_to_top_failure(self) -> None:
        template = BASEOF.read_text(encoding="utf-8")
        self.assertNotIn("back-to-top", template)
        self.assertNotIn('href="#top"', template)


class FooterBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="site-footer-hugo-"))
        result = subprocess.run(
            ["hugo", "--destination", str(cls._output_dir), "--quiet", "--noBuildLock"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.map_html = (cls._output_dir / "map" / "index.html").read_text(encoding="utf-8")
        cls.privacy = (cls._output_dir / "privacy" / "index.html").read_text(
            encoding="utf-8"
        )
        admin = cls._output_dir / "admin" / "comments" / "index.html"
        cls.admin = admin.read_text(encoding="utf-8") if admin.is_file() else ""
        tour = cls._output_dir / "gradys-tour" / "index.html"
        cls.tour = tour.read_text(encoding="utf-8") if tour.is_file() else ""

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_home_footer_has_legal_and_credit_success(self) -> None:
        footer = footer_html(self.home)
        self.assertTrue(footer, "home page must include a <footer>")
        self.assertTrue(has_copyright(footer))
        self.assertTrue(has_privacy_link(footer))
        self.assertTrue(has_webmaster_invite(footer))
        self.assertRegex(
            footer,
            r'<a\b[^>]*href="[^"]*authors/?[^"]*"[^>]*>\s*Contributors\s*</a>',
        )

    def test_map_and_tour_and_admin_include_footer_success(self) -> None:
        for name, html in (
            ("map", self.map_html),
            ("gradys-tour", self.tour),
            ("admin", self.admin),
        ):
            with self.subTest(page=name):
                self.assertTrue(footer_html(html), f"{name} must include a <footer>")
                self.assertTrue(
                    has_webmaster_invite(html),
                    f"{name} footer must invite comments to webmaster {BUILDER_NAME}",
                )

    def test_privacy_page_builds_without_comments_success(self) -> None:
        self.assertIn("<footer", self.privacy)
        self.assertIn("Privacy", self.privacy)
        self.assertNotIn('id="comments"', self.privacy)

    def test_builder_link_points_at_tylermorales_pro_success(self) -> None:
        footer = footer_html(self.home)
        self.assertRegex(
            footer,
            rf'<a\b[^>]*href="{re.escape(BUILDER_URL)}"[^>]*>\s*{re.escape(BUILDER_NAME)}\s*</a>',
        )

    def test_privacy_is_not_listed_on_home_failure(self) -> None:
        list_html = re.search(r'<ul class="post-list">(.*?)</ul>', self.home, re.DOTALL)
        self.assertIsNotNone(list_html)
        assert list_html is not None
        self.assertNotIn("/privacy/", list_html.group(1))

    def test_non_posts_omit_back_to_top_failure(self) -> None:
        back_to_top = re.compile(
            r'<a\b[^>]*href="#top"[^>]*>\s*Back to top\s*</a>',
            re.IGNORECASE,
        )
        for name, html in (
            ("home", self.home),
            ("map", self.map_html),
            ("privacy", self.privacy),
            ("admin", self.admin),
            ("gradys-tour", self.tour),
        ):
            with self.subTest(page=name):
                self.assertTrue(html, f"{name} must be in the build")
                self.assertNotRegex(html, back_to_top)


if __name__ == "__main__":
    unittest.main()
