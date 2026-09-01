"""Home lists every author's posts; /authors/ lists writers; /authors/<slug>/ lists one."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORS_DIR = REPO_ROOT / "content" / "authors"
LIST_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "list.html"
AUTHOR_LIST_LAYOUT = REPO_ROOT / "layouts" / "authors" / "list.html"
AUTHOR_LAYOUT = REPO_ROOT / "layouts" / "authors" / "single.html"
AUTHOR_CARD = REPO_ROOT / "layouts" / "partials" / "author-card.html"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
POST_LIST_ITEM = REPO_ROOT / "layouts" / "partials" / "post-list-item.html"
POST_BYLINE = REPO_ROOT / "layouts" / "partials" / "post-byline.html"
AUTHOR_BIO = REPO_ROOT / "layouts" / "partials" / "author-bio.html"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
HUGO_TIMEOUT_SECONDS = 120

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
TITLE_RE = re.compile(r'class="post-list-title"[^>]*>(.*?)</(?:span|a)>', re.DOTALL)
DATE_RE = re.compile(r'<time class="post-date" datetime="([^"]+)"')
AUTHOR_LINK_RE = re.compile(
    r'<a\b[^>]*href="([^"]*\/authors\/[^"]+)"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)
POST_LINK_BLOCK_RE = re.compile(
    r'<a\b[^>]*class="[^"]*post-list-(?:title|image-link)[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL,
)
AUTHOR_LIST_RE = re.compile(r'<ul class="author-list"[^>]*>(.*?)</ul>', re.DOTALL)
NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)


def post_list_html(html: str) -> str:
    match = POST_LIST_RE.search(html)
    return match.group(1) if match else ""


def post_list_titles(html: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", title).strip()
        for title in TITLE_RE.findall(post_list_html(html))
    ]


def post_list_dates(html: str) -> list[str]:
    return DATE_RE.findall(post_list_html(html))


def parse_front_matter(path: Path) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("-"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def published_article_titles() -> set[str]:
    """Every non-draft post in Posts and Grady's Tour."""
    titles: set[str] = set()
    for section in ("posts", "gradys-tour", "da-breakdown-w-tad"):
        for path in sorted((REPO_ROOT / "content" / section).glob("*.md")):
            if path.name.startswith("_"):
                continue
            front_matter = parse_front_matter(path)
            if front_matter.get("draft", "false").lower() == "true":
                continue
            title = front_matter.get("title")
            if title:
                titles.add(title)
    return titles


def author_list_html(html: str) -> str:
    match = AUTHOR_LIST_RE.search(html)
    return match.group(1) if match else ""


def author_list_names(html: str) -> list[str]:
    return [name.strip() for _href, name in AUTHOR_LINK_RE.findall(author_list_html(html))]


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


def run_hugo(destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hugo", "--destination", str(destination), "--quiet", "--noBuildLock"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class AuthorTemplateContractTests(unittest.TestCase):
    def test_home_lists_posts_and_tour_sections_success(self) -> None:
        template = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(".IsHome", template)
        self.assertIn('"posts"', template)
        self.assertIn('"gradys-tour"', template)
        self.assertIn('"da-breakdown-w-tad"', template)
        self.assertNotIn("is-tour-post.html", template)

    def test_home_without_section_mix_fails_contract(self) -> None:
        template = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotRegex(
            template,
            r'(?s)where\s+\S+\s+"Section"\s+"posts"\s*$',
        )

    def test_author_layout_exists_and_skips_comments_success(self) -> None:
        self.assertTrue(AUTHOR_LAYOUT.is_file(), "layouts/authors/single.html is required")
        layout = AUTHOR_LAYOUT.read_text(encoding="utf-8")
        card = AUTHOR_CARD.read_text(encoding="utf-8")
        self.assertIn("author-card.html", layout)
        self.assertIn("author-profile", card)
        self.assertIn("post-list", layout)
        self.assertNotIn("comments.html", layout)
        self.assertNotIn("isso.html", layout)

    def test_author_names_are_links_not_nested_success(self) -> None:
        item = POST_LIST_ITEM.read_text(encoding="utf-8")
        byline = POST_BYLINE.read_text(encoding="utf-8")
        bio = AUTHOR_BIO.read_text(encoding="utf-8")
        card = AUTHOR_CARD.read_text(encoding="utf-8")
        self.assertIn("RelPermalink", item)
        self.assertIn("RelPermalink", byline)
        self.assertIn("link_name", bio)
        self.assertIn("RelPermalink", card)
        link_open = item.find("<a")
        link_close = item.find("</a>")
        author_href = item.find("RelPermalink")
        self.assertGreater(link_open, -1)
        self.assertGreater(link_close, -1)
        self.assertGreater(
            author_href,
            link_close,
            "Author permalink must sit outside the post list link so names are clickable",
        )

    def test_authors_index_layout_lists_cards_not_posts_success(self) -> None:
        self.assertTrue(AUTHOR_LIST_LAYOUT.is_file(), "layouts/authors/list.html is required")
        layout = AUTHOR_LIST_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("author-card.html", layout)
        self.assertIn("link_name", layout)
        self.assertIn("author-list", layout)
        self.assertIn("eric-wisnewski", layout)
        self.assertIn("Params.name", layout)
        self.assertNotIn("post-list", layout)
        self.assertNotIn("subscribe.html", layout)
        self.assertNotIn("comments.html", layout)

    def test_authors_index_is_not_the_default_post_list_failure(self) -> None:
        layout = AUTHOR_LIST_LAYOUT.read_text(encoding="utf-8")
        home = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("author-list", home)
        self.assertNotIn("post-list-item.html", layout)

    def test_header_omits_authors_index_failure(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("Authors", header)
        self.assertNotIn("Contributors", header)
        self.assertNotIn("/authors/", header)

    def test_author_profile_links_up_to_the_index_success(self) -> None:
        layout = AUTHOR_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('.Site.GetPage "/authors"', layout)
        self.assertIn("All contributors", layout)

    def test_authors_index_cascade_no_longer_unpublishes_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"path\s*=\s*['\"]/?authors['\"]", toml))
        self.assertNotIn("render = 'never'", toml)

    def test_author_list_css_has_focus_visible_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".author-list", css)
        self.assertIn(".author-all", css)
        self.assertIn("repeat(3, 1fr)", css)
        self.assertIn("display: grid", css)
        self.assertIn(".author-name-link:focus-visible", css)
        self.assertIn(".author-all a:focus-visible", css)
        self.assertRegex(css, r"\.author-all a\s*,|\.author-all a\s*\{")
        list_at = css.find(".author-list {")
        media_at = css.find("@media (min-width: 640px)", list_at)
        self.assertGreater(list_at, -1)
        self.assertGreater(media_at, list_at)
        base = css[list_at:media_at]
        self.assertIn("flex-direction: column", base)
        self.assertIn("align-items: flex-start", base)
        self.assertIn("10rem", base)

    def test_author_list_does_not_keep_tiny_side_photos_on_mobile_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        list_at = css.find(".author-list {")
        media_at = css.find("@media (min-width: 640px)", list_at)
        self.assertGreater(list_at, -1)
        self.assertGreater(media_at, list_at)
        base = css[list_at:media_at]
        self.assertNotIn("4.5rem", base)
        self.assertNotIn("flex-direction: row", base)

    def test_author_files_exist_failure_when_missing(self) -> None:
        self.assertTrue((AUTHORS_DIR / "eric-wisnewski.md").is_file())
        self.assertTrue((AUTHORS_DIR / "grady-davis.md").is_file())
        self.assertTrue((AUTHORS_DIR / "tyler-morales.md").is_file())
        grady = (AUTHORS_DIR / "grady-davis.md").read_text(encoding="utf-8")
        self.assertIn("slug: grady-davis", grady)
        tyler = (AUTHORS_DIR / "tyler-morales.md").read_text(encoding="utf-8")
        self.assertIn("slug: tyler-morales", tyler)
        self.assertIn("develops and maintains", tyler)
        self.assertIn("image: /images/uploads/tyler-morales.jpg", tyler)
        self.assertTrue(
            (REPO_ROOT / "assets" / "images" / "uploads" / "tyler-morales.jpg").is_file()
        )
        index = (AUTHORS_DIR / "_index.md").read_text(encoding="utf-8")
        self.assertIn("title: Contributors", index)
        self.assertNotIn("The writers on this site", index)

    def test_published_article_titles_includes_quoted_tour_title_success(self) -> None:
        titles = published_article_titles()
        self.assertIn("Chipping Away: Day 2-4", titles)
        self.assertIn("An Introduction", titles)

    def test_published_article_titles_excludes_drafts_failure_path(self) -> None:
        titles = {title.lower() for title in published_article_titles()}
        self.assertNotIn("how to use this blog (grady)", titles)


class AuthorBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="authors-hugo-"))
        result = run_hugo(cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH and the site is valid:\n{result.stderr}"
            )
        cls.home_html = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.eric = cls._output_dir / "authors" / "eric-wisnewski" / "index.html"
        cls.grady = cls._output_dir / "authors" / "grady-davis" / "index.html"
        cls.intro = (
            cls._output_dir / "posts" / "an-introduction" / "index.html"
        ).read_text(encoding="utf-8")
        cls.tour_post = (
            cls._output_dir / "gradys-tour" / "gearing-up" / "index.html"
        ).read_text(encoding="utf-8")
        cls.eric_html = cls.eric.read_text(encoding="utf-8") if cls.eric.is_file() else ""
        cls.grady_html = cls.grady.read_text(encoding="utf-8") if cls.grady.is_file() else ""
        cls.tyler = cls._output_dir / "authors" / "tyler-morales" / "index.html"
        cls.tyler_html = cls.tyler.read_text(encoding="utf-8") if cls.tyler.is_file() else ""
        cls.authors_index = cls._output_dir / "authors" / "index.html"
        cls.authors_index_html = (
            cls.authors_index.read_text(encoding="utf-8") if cls.authors_index.is_file() else ""
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_home_lists_every_published_post_from_every_section_success(self) -> None:
        expected = published_article_titles()
        titles = set(post_list_titles(self.home_html))
        self.assertTrue(expected, "No published posts found in content/")
        missing = expected - titles
        self.assertEqual(
            missing,
            set(),
            f"Home omitted published posts: {missing}. Home had: {sorted(titles)}",
        )

    def test_home_is_latest_first_success(self) -> None:
        dates = post_list_dates(self.home_html)
        self.assertTrue(dates, "Home post list is missing datetime values")
        self.assertEqual(dates, sorted(dates, reverse=True), f"Home dates were not descending: {dates}")

    def test_draft_guide_stays_off_home_failure_path(self) -> None:
        titles = {title.lower() for title in post_list_titles(self.home_html)}
        self.assertNotIn("how to use this blog (grady)", titles)

    def test_author_pages_render_success(self) -> None:
        self.assertTrue(self.eric.is_file(), "Missing /authors/eric-wisnewski/")
        self.assertTrue(self.grady.is_file(), "Missing /authors/grady-davis/")
        self.assertTrue(self.authors_index.is_file(), "Missing /authors/ index")
        self.assertTrue(self.tyler.is_file(), "Missing /authors/tyler-morales/")

    def test_authors_index_lists_eric_first_then_name_success(self) -> None:
        names = author_list_names(self.authors_index_html)
        self.assertGreaterEqual(len(names), 4, f"Expected a roster, got {names}")
        self.assertEqual(names[0], "Eric Wisnewski")
        self.assertEqual(names[1:], sorted(names[1:]))
        self.assertIn("Grady Davis", names)
        self.assertIn("Tad Davis", names)
        self.assertIn("Tyler Morales", names)
        self.assertIn("All contributors", self.eric_html)
        self.assertIn("All contributors", self.grady_html)
        self.assertIn("/authors/", self.eric_html)
        self.assertIn("develops and maintains", self.authors_index_html)
        self.assertIn("Contributors", self.authors_index_html)
        self.assertIn("/images/uploads/tyler-morales.jpg", self.authors_index_html)
        self.assertIn("/images/uploads/tyler-morales.jpg", self.tyler_html)

    def test_authors_index_is_not_a_post_feed_failure(self) -> None:
        self.assertNotIn('class="post-list"', self.authors_index_html)
        self.assertNotIn("The writers on this site", self.authors_index_html)
        self.assertNotIn('id="comments"', self.authors_index_html)
        self.assertNotIn("subscribe-form", self.authors_index_html)
        self.assertNotIn("id=\"subscribe\"", self.authors_index_html)
        nav = main_nav_html(self.authors_index_html)
        self.assertTrue(nav, "authors index must keep the main nav")
        self.assertNotIn(">Authors</a>", nav)
        self.assertNotIn(">Contributors</a>", nav)
        self.assertNotIn("/authors/", nav)

    def test_author_page_shows_profile_then_that_authors_posts_success(self) -> None:
        self.assertIn("Grady Davis", self.grady_html)
        self.assertIn("cycling and travel", self.grady_html.lower())
        self.assertIn("/images/uploads/IMG_0846.jpeg", self.grady_html)
        self.assertIn('<header class="author-bio author-profile"', self.grady_html)
        self.assertNotIn("&lt;header", self.grady_html)
        titles = post_list_titles(self.grady_html)
        self.assertIn("From boat to bike", titles)
        self.assertIn("Bike-less in Bayeux", titles)
        self.assertNotIn("An Introduction", titles)
        profile_at = self.grady_html.find("author-profile")
        list_at = self.grady_html.find('class="post-list"')
        self.assertGreater(profile_at, -1)
        self.assertGreater(list_at, profile_at)

    def test_eric_page_excludes_grady_posts_failure_path(self) -> None:
        titles = post_list_titles(self.eric_html)
        self.assertIn("An Introduction", titles)
        self.assertNotIn("From boat to bike", titles)
        self.assertNotIn("Bike-less in Bayeux", titles)

    def test_author_page_has_no_comments_success(self) -> None:
        self.assertNotIn('id="comments"', self.eric_html)
        self.assertNotIn('id="comments"', self.grady_html)

    def test_author_name_links_from_home_and_posts_success(self) -> None:
        home_links = AUTHOR_LINK_RE.findall(self.home_html)
        self.assertTrue(home_links, "Home list has no author links")
        hrefs = {href.rstrip("/") for href, _name in home_links}
        self.assertTrue(any(href.endswith("/authors/eric-wisnewski") for href in hrefs))
        self.assertTrue(any(href.endswith("/authors/grady-davis") for href in hrefs))

        for html, slug, name in (
            (self.intro, "eric-wisnewski", "Eric Wisnewski"),
            (self.tour_post, "grady-davis", "Grady Davis"),
        ):
            with self.subTest(slug=slug):
                self.assertIn(f"/authors/{slug}/", html)
                self.assertIn(name, html)

    def test_author_link_is_not_nested_in_post_link_failure_path(self) -> None:
        for block in POST_LINK_BLOCK_RE.findall(self.home_html):
            self.assertNotIn(
                "/authors/",
                block,
                "Author URL nested inside the post link; click would not open the author page",
            )


if __name__ == "__main__":
    unittest.main()
