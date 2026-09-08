"""Jeremy On Tap: nav and subscribe appear when the first post is published."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECTION_DIR = REPO_ROOT / "content" / "jeremy-on-tap"
SECTION_INDEX = SECTION_DIR / "_index.md"
AUTHOR_FILE = REPO_ROOT / "content" / "authors" / "jeremy-bryan.md"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
LIST_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "list.html"
SECTION_LAYOUT = REPO_ROOT / "layouts" / "_default" / "section-list.html"
HAS_POSTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "has-jeremy-on-tap-posts.html"
AUTHOR_LAYOUT = REPO_ROOT / "layouts" / "authors" / "single.html"
AUTHOR_POSTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "author-posts.html"
SUBSCRIBE_PARTIAL = REPO_ROOT / "layouts" / "partials" / "subscribe.html"
SUBSCRIBE_MANAGE = REPO_ROOT / "layouts" / "_default" / "subscribe-manage.html"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
NEWSLETTER_API = REPO_ROOT / "functions" / "api" / "newsletter.js"
SUBSCRIBE_API = REPO_ROOT / "functions" / "api" / "subscribe.js"
REDIRECTS = REPO_ROOT / "static" / "_redirects"
HUGO_TIMEOUT_SECONDS = 120

NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
TITLE_RE = re.compile(r'class="post-list-title"[^>]*>(.*?)</(?:span|a)>', re.DOTALL)
FIXTURE_POST = (
    "---\n"
    "title: Fixture Prospect\n"
    "slug: fixture\n"
    "author: jeremy-bryan\n"
    "date: 2026-09-04T12:00:00Z\n"
    "draft: false\n"
    "---\n"
    "Fixture body.\n"
)


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


def post_list_titles(html: str) -> list[str]:
    match = POST_LIST_RE.search(html)
    if not match:
        return []
    return [re.sub(r"\s+", " ", title).strip() for title in TITLE_RE.findall(match.group(1))]


def run_hugo(*, destination: Path, content_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = ["hugo", "--destination", str(destination), "--quiet", "--noBuildLock"]
    if content_dir is not None:
        command.extend(["--contentDir", str(content_dir)])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


def content_with_published_post(tmp: Path) -> Path:
    copy = tmp / "content"
    shutil.copytree(REPO_ROOT / "content", copy)
    (copy / "jeremy-on-tap" / "fixture.md").write_text(FIXTURE_POST, encoding="utf-8")
    return copy


class JeremyOnTapContractTests(unittest.TestCase):
    def test_section_index_is_not_staged_success(self) -> None:
        self.assertTrue(SECTION_INDEX.is_file())
        text = SECTION_INDEX.read_text(encoding="utf-8")
        self.assertIn("title: Jeremy On Tap", text)
        self.assertIn("layout: section-list", text)
        self.assertNotIn("render: never", text)
        self.assertNotIn("cascade:", text)
        self.assertNotIn("Prospect Profiles", text)

    def test_index_with_staging_block_fails_contract(self) -> None:
        self.assertNotIn("build:", SECTION_INDEX.read_text(encoding="utf-8"))

    def test_author_file_matches_cms_slug_success(self) -> None:
        self.assertTrue(AUTHOR_FILE.is_file())
        text = AUTHOR_FILE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^name:\s*Jeremy Bryan\s*$")
        self.assertRegex(text, r"(?m)^slug:\s*jeremy-bryan\s*$")
        self.assertRegex(text, r"(?m)^draft:\s*true\s*$")

    def test_nav_gates_on_published_posts_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        gate = HAS_POSTS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("has-jeremy-on-tap-posts.html", header)
        self.assertIn("Jeremy On Tap", header)
        self.assertIn("Da Breakdown w Tad", header)
        self.assertNotIn("jers-prospect-profiles", header)
        self.assertNotIn("Prospect Profiles", header)
        self.assertIn("RegularPages", gate)
        self.assertIn("GetPage", gate)
        self.assertIn("/jeremy-on-tap", gate)
        self.assertNotIn("jers-prospect-profiles", gate)

    def test_nav_without_post_gate_failure(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn(".Site.RegularPages", header)
        self.assertNotIn("render 'never'", header)

    def test_home_and_author_templates_include_section_success(self) -> None:
        home = LIST_TEMPLATE.read_text(encoding="utf-8")
        author_posts = AUTHOR_POSTS_PARTIAL.read_text(encoding="utf-8")
        author = AUTHOR_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('"jeremy-on-tap"', home)
        self.assertIn('"jeremy-on-tap"', author_posts)
        self.assertIn("author-posts.html", author)
        self.assertNotIn("jers-prospect-profiles", home)
        self.assertNotIn("jers-prospect-profiles", author_posts)

    def test_home_without_jer_section_fails_contract(self) -> None:
        home = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn('slice "posts" "gradys-tour" "da-breakdown-w-tad" }}', home)

    def test_subscribe_gates_on_published_posts_success(self) -> None:
        form = SUBSCRIBE_PARTIAL.read_text(encoding="utf-8")
        manage = SUBSCRIBE_MANAGE.read_text(encoding="utf-8")
        checkbox_at = form.find('value="jeremy-on-tap"')
        gate_at = form.find("has-jeremy-on-tap-posts.html")
        self.assertGreater(checkbox_at, -1)
        self.assertGreater(gate_at, -1)
        self.assertLess(gate_at, checkbox_at)
        self.assertIn("Jeremy On Tap", form)
        self.assertIn("has-jeremy-on-tap-posts.html", manage)
        self.assertNotIn("jers-prospect-profiles", form)
        self.assertNotIn("Prospect Profiles", form)
        self.assertNotIn("jers-prospect-profiles", manage)

    def test_section_layout_lists_own_pages_success(self) -> None:
        self.assertTrue(SECTION_LAYOUT.is_file())
        layout = SECTION_LAYOUT.read_text(encoding="utf-8")
        self.assertIn(".RegularPages", layout)
        self.assertIn("section-empty", layout)
        self.assertNotIn('Section" "posts"', layout)

    def test_permalinks_and_author_cascade_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertRegex(toml, r"jeremy-on-tap\s*=\s*'/jeremy-on-tap/:slug/'")
        self.assertIn("author = 'jeremy-bryan'", toml)
        self.assertIn("/jeremy-on-tap/**", toml)
        self.assertNotIn("jers-prospect-profiles", toml)
        self.assertNotIn("Prospect Profiles", toml)

    def test_cms_collection_exists_success(self) -> None:
        config = PAGES_YML.read_text(encoding="utf-8")
        self.assertEqual(config.count("- name: jeremy-on-tap"), 1)
        self.assertNotIn("jers-prospect-profiles", config)
        self.assertNotIn("Prospect Profiles", config)
        block = config.split("- name: jeremy-on-tap", 1)[-1]
        next_collection = block.find("\n  - name: ")
        if next_collection != -1:
            block = block[:next_collection]
        self.assertIn("path: content/jeremy-on-tap", block)
        self.assertIn("label: Jeremy On Tap", block)
        self.assertIn("default: jeremy-bryan", block)
        self.assertIn("default: true", block)
        self.assertIn("multiple:", block)

    def test_newsletter_list_is_wired_success(self) -> None:
        subscribe = SUBSCRIBE_API.read_text(encoding="utf-8")
        newsletter = NEWSLETTER_API.read_text(encoding="utf-8")
        form = SUBSCRIBE_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("'jeremy-on-tap'", subscribe)
        self.assertIn("/jeremy-on-tap/index.xml", newsletter)
        self.assertIn('value="jeremy-on-tap"', form)
        self.assertIn("has-jeremy-on-tap-posts.html", form)
        self.assertNotIn("jers-prospect-profiles", subscribe)
        self.assertNotIn("jers-prospect-profiles", newsletter)

    def test_old_urls_redirect_success(self) -> None:
        text = REDIRECTS.read_text(encoding="utf-8")
        self.assertIn("/jers-prospect-profiles/*", text)
        self.assertIn("/jeremy-on-tap/:splat", text)


class JeremyOnTapEmptyBuildTests(unittest.TestCase):
    """No published Jeremy posts: tab and checkbox stay off."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="jeremy-on-tap-empty-"))
        result = run_hugo(destination=cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(f"hugo build failed:\n{result.stderr}")
        cls.output_dir = cls._output_dir
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        section = cls._output_dir / "jeremy-on-tap" / "index.html"
        cls.section = section.read_text(encoding="utf-8") if section.is_file() else ""

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_section_page_exists_empty_success(self) -> None:
        self.assertTrue(self.section)
        self.assertIn("No posts yet. Check back soon.", self.section)
        self.assertIn("Jeremy On Tap", self.section)
        self.assertNotIn("Prospect Profiles", self.section)

    def test_nav_and_subscribe_hidden_without_posts_failure(self) -> None:
        nav = main_nav_html(self.home)
        self.assertIn("Grady's Tour", nav)
        self.assertNotIn("Jeremy On Tap", nav)
        self.assertNotIn("Prospect Profiles", nav)
        self.assertNotIn('value="jeremy-on-tap"', self.home)
        self.assertNotIn("Jeremy On Tap", main_nav_html(self.section))

    def test_home_omits_jer_urls_failure(self) -> None:
        self.assertNotIn("/jeremy-on-tap/", self.home)
        self.assertNotIn("/jers-prospect-profiles/", self.home)
        self.assertNotIn("Fixture Prospect", self.home)


class JeremyOnTapPublishedBuildTests(unittest.TestCase):
    """A published post turns on the tab, home mix, and newsletter checkbox."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="jeremy-on-tap-live-"))
        cls._output_dir = cls._tmp / "out"
        result = run_hugo(
            destination=cls._output_dir,
            content_dir=content_with_published_post(cls._tmp),
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed:\n{result.stderr}\n{result.stdout}"
            )
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        section = cls._output_dir / "jeremy-on-tap" / "index.html"
        cls.section = section.read_text(encoding="utf-8") if section.is_file() else ""
        fixture = cls._output_dir / "jeremy-on-tap" / "fixture" / "index.html"
        cls.fixture = fixture.read_text(encoding="utf-8") if fixture.is_file() else ""
        rss = cls._output_dir / "jeremy-on-tap" / "index.xml"
        cls.rss = rss.read_text(encoding="utf-8") if rss.is_file() else ""
        author = cls._output_dir / "authors" / "jeremy-bryan" / "index.html"
        cls.author = author.read_text(encoding="utf-8") if author.is_file() else ""

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_section_page_lists_fixture_success(self) -> None:
        self.assertTrue(self.section)
        self.assertIn("Jeremy On Tap", main_nav_html(self.section))
        self.assertNotIn("Prospect Profiles", self.section)
        self.assertIn("Fixture Prospect", post_list_titles(self.section))
        self.assertNotIn("An Introduction", post_list_titles(self.section))
        self.assertNotIn("From boat to bike", post_list_titles(self.section))

    def test_home_includes_fixture_with_other_authors_success(self) -> None:
        titles = post_list_titles(self.home)
        self.assertIn("Fixture Prospect", titles)
        self.assertIn("An Introduction", titles)

    def test_nav_sits_next_to_tad_success(self) -> None:
        nav = main_nav_html(self.home)
        self.assertIn("Da Breakdown w Tad", nav)
        self.assertIn("Jeremy On Tap", nav)
        self.assertIn("/jeremy-on-tap/", nav)
        self.assertNotIn("Prospect Profiles", nav)
        self.assertNotIn("/jers-prospect-profiles/", nav)
        self.assertLess(nav.find("Da Breakdown w Tad"), nav.find("Jeremy On Tap"))

    def test_subscribe_checkbox_and_default_success(self) -> None:
        self.assertIn('value="jeremy-on-tap"', self.home)
        self.assertIn('value="jeremy-on-tap"', self.section)
        self.assertIn('data-default-list="jeremy-on-tap"', self.section)
        self.assertIn('data-default-list="jeremy-on-tap"', self.fixture)
        self.assertIn("Jeremy On Tap", self.home)
        self.assertNotIn("jers-prospect-profiles", self.home)
        self.assertNotIn("Prospect Profiles", self.home)

    def test_author_page_lists_fixture_success(self) -> None:
        """Jeremy’s profile is still draft, so the fixture only shows on home/section."""
        self.assertFalse(self.author)
        self.assertIn("Fixture Prospect", post_list_titles(self.home))

    def test_rss_is_section_only_failure(self) -> None:
        self.assertTrue(self.rss.startswith("<?xml"))
        self.assertIn("Fixture Prospect", self.rss)
        self.assertNotIn("An Introduction", self.rss)

    def test_empty_list_message_absent_when_posts_exist_failure(self) -> None:
        self.assertNotIn("No posts yet. Check back soon.", self.section)


if __name__ == "__main__":
    unittest.main()
