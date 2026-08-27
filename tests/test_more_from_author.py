"""More from this author: chronological older/newer under the post."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SINGLE_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "single.html"
AUTHOR_LAYOUT = REPO_ROOT / "layouts" / "authors" / "single.html"
MORE_FROM_PARTIAL = REPO_ROOT / "layouts" / "partials" / "more-from-author.html"
AUTHOR_POSTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "author-posts.html"
UPDATES_ENTRY_LAYOUT = REPO_ROOT / "layouts" / "updates" / "single.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
HUGO_TIMEOUT_SECONDS = 120

MORE_FROM_RE = re.compile(
    r'<nav\b[^>]*class="[^"]*\bmore-from-author\b[^"]*"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
OLDER_RE = re.compile(
    r'<a\b(?=[^>]*\brel="prev")(?=[^>]*\bhref="([^"]+)")[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
NEWER_RE = re.compile(
    r'<a\b(?=[^>]*\brel="next")(?=[^>]*\bhref="([^"]+)")[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
HEADING_LINK_RE = re.compile(
    r'<h2\b[^>]*id="more-from-heading"[^>]*>.*?href="([^"]+)"[^>]*>([^<]+)</a>',
    re.DOTALL | re.IGNORECASE,
)
LIST_TITLE_RE = re.compile(
    r'<ul[^>]*\bmore-from-list\b[^>]*>(.*?)</ul>',
    re.DOTALL,
)


def more_from_html(html: str) -> str:
    match = MORE_FROM_RE.search(html)
    return match.group(1) if match else ""


def layout_files() -> list[Path]:
    return sorted((REPO_ROOT / "layouts").rglob("*.html"))


def first_block(css: str, selector: str) -> str:
    pattern = re.compile(re.escape(selector) + r"\s*(?:,[^{]+)?\{([^}]+)\}")
    match = pattern.search(css)
    return match.group(1) if match else ""


def write_author(path: Path, slug: str, name: str) -> None:
    path.write_text(
        f"---\nname: {name}\nslug: {slug}\ndraft: false\nbio: Bio for {name}.\n---\n",
        encoding="utf-8",
    )


def write_post(path: Path, title: str, slug: str, author: str, date: str) -> None:
    path.write_text(
        "---\n"
        f"title: {title}\n"
        f"slug: {slug}\n"
        f"author: {author}\n"
        f"date: {date}\n"
        "draft: false\n"
        "---\n"
        "Body\n",
        encoding="utf-8",
    )


class MoreFromTemplateTests(unittest.TestCase):
    def test_article_single_includes_more_from_after_bio_success(self) -> None:
        template = SINGLE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('partial "more-from-author.html"', template)
        self.assertIn('partial "author-bio.html"', template)
        bio_at = template.find('author-bio.html')
        more_at = template.find('more-from-author.html')
        subscribe_at = template.find('subscribe.html')
        comments_at = template.find('comments.html')
        self.assertGreater(more_at, bio_at)
        self.assertGreater(subscribe_at, more_at)
        self.assertGreater(comments_at, more_at)
        article_end = template.find("</article>")
        self.assertGreater(more_at, article_end)

    def test_more_from_partial_is_author_scoped_pager_success(self) -> None:
        self.assertTrue(MORE_FROM_PARTIAL.is_file())
        self.assertTrue(AUTHOR_POSTS_PARTIAL.is_file())
        partial = MORE_FROM_PARTIAL.read_text(encoding="utf-8")
        posts = AUTHOR_POSTS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("author-posts.html", partial)
        self.assertIn("author-page.html", partial)
        self.assertIn("rel=\"prev\"", partial)
        self.assertIn("rel=\"next\"", partial)
        self.assertIn("Older", partial)
        self.assertIn("Newer", partial)
        self.assertIn("More from", partial)
        self.assertIn("aria-labelledby", partial)
        self.assertIn("more-from-heading", partial)
        self.assertIn("role=\"list\"", partial)
        self.assertIn('"posts"', posts)
        self.assertIn('"gradys-tour"', posts)
        self.assertIn('"da-breakdown-w-tad"', posts)

    def test_author_page_reuses_author_posts_partial_success(self) -> None:
        layout = AUTHOR_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("author-posts.html", layout)
        self.assertNotIn("is-tour-post.html", layout)

    def test_more_from_absent_from_non_article_layouts_failure(self) -> None:
        offenders: list[str] = []
        for path in layout_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in {
                "layouts/partials/more-from-author.html",
                "layouts/_default/single.html",
            }:
                continue
            if 'partial "more-from-author.html"' in path.read_text(encoding="utf-8"):
                offenders.append(rel)
        self.assertEqual(offenders, [])
        updates = UPDATES_ENTRY_LAYOUT.read_text(encoding="utf-8")
        self.assertNotIn("more-from-author.html", updates)


class MoreFromCssTests(unittest.TestCase):
    def test_more_from_is_sans_chrome_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".more-from-author", css)
        self.assertIn(".more-from-older:focus-visible", css)
        self.assertIn(".more-from-newer:focus-visible", css)
        self.assertIn(".more-from-heading a:focus-visible", css)
        block = first_block(css, ".more-from-author")
        self.assertIn("var(--font-sans)", block)
        self.assertIn("65ch", block)

    def test_more_from_is_not_a_sidebar_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        start = css.find(".more-from-author")
        self.assertGreater(start, -1)
        chunk = css[start : start + 1800]
        self.assertNotIn("position: fixed", chunk)
        self.assertNotIn("position: sticky", chunk)
        self.assertNotIn("position:fixed", chunk)


class MoreFromBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="more-from-author-")
        root = Path(cls._tmp.name)
        content_dir = root / "content"
        (content_dir / "authors").mkdir(parents=True)
        (content_dir / "posts").mkdir()
        (content_dir / "authors" / "_index.md").write_text(
            "---\ntitle: Authors\n---\n",
            encoding="utf-8",
        )
        write_author(content_dir / "authors" / "writer-a.md", "writer-a", "Writer A")
        write_author(content_dir / "authors" / "writer-b.md", "writer-b", "Writer B")
        write_post(
            content_dir / "posts" / "first.md",
            "First Post",
            "first",
            "writer-a",
            "2026-01-01T00:00:00Z",
        )
        write_post(
            content_dir / "posts" / "middle.md",
            "Middle Post",
            "middle",
            "writer-a",
            "2026-01-02T00:00:00Z",
        )
        write_post(
            content_dir / "posts" / "last.md",
            "Last Post",
            "last",
            "writer-a",
            "2026-01-03T00:00:00Z",
        )
        write_post(
            content_dir / "posts" / "extra.md",
            "Extra Post",
            "extra",
            "writer-a",
            "2026-01-04T00:00:00Z",
        )
        write_post(
            content_dir / "posts" / "other.md",
            "Other Author Post",
            "other",
            "writer-b",
            "2026-01-05T00:00:00Z",
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
        cls.first = (dest / "posts" / "first" / "index.html").read_text(encoding="utf-8")
        cls.middle = (dest / "posts" / "middle" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.last = (dest / "posts" / "last" / "index.html").read_text(encoding="utf-8")
        cls.extra = (dest / "posts" / "extra" / "index.html").read_text(encoding="utf-8")
        cls.other = (dest / "posts" / "other" / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_middle_post_pagers_to_immediate_neighbors_success(self) -> None:
        nav = more_from_html(self.middle)
        self.assertTrue(nav, "Middle post is missing the more-from nav")
        older = OLDER_RE.search(nav)
        newer = NEWER_RE.search(nav)
        self.assertIsNotNone(older)
        self.assertIsNotNone(newer)
        assert older is not None
        assert newer is not None
        self.assertIn("/posts/first/", older.group(1))
        self.assertIn("First Post", older.group(2))
        self.assertIn("Older", older.group(2))
        self.assertIn("/posts/last/", newer.group(1))
        self.assertIn("Last Post", newer.group(2))
        self.assertIn("Newer", newer.group(2))
        heading = HEADING_LINK_RE.search(self.middle)
        self.assertIsNotNone(heading)
        assert heading is not None
        self.assertIn("/authors/writer-a/", heading.group(1))
        self.assertEqual(heading.group(2).strip(), "Writer A")

    def test_first_post_has_newer_only_success(self) -> None:
        nav = more_from_html(self.first)
        self.assertTrue(nav)
        self.assertIsNone(OLDER_RE.search(nav))
        newer = NEWER_RE.search(nav)
        self.assertIsNotNone(newer)
        assert newer is not None
        self.assertIn("/posts/middle/", newer.group(1))
        self.assertIn("Middle Post", newer.group(2))

    def test_newest_post_has_older_only_success(self) -> None:
        nav = more_from_html(self.extra)
        self.assertTrue(nav)
        self.assertIsNone(NEWER_RE.search(nav))
        older = OLDER_RE.search(nav)
        self.assertIsNotNone(older)
        assert older is not None
        self.assertIn("/posts/last/", older.group(1))
        self.assertIn("Last Post", older.group(2))

    def test_leftover_posts_are_listed_newest_first_success(self) -> None:
        nav = more_from_html(self.first)
        list_match = LIST_TITLE_RE.search(nav)
        self.assertIsNotNone(list_match, "First post should list leftover posts")
        assert list_match is not None
        titles = re.findall(r'<a href="[^"]+">([^<]+)</a>', list_match.group(1))
        self.assertEqual(titles, ["Extra Post", "Last Post"])
        self.assertNotIn("First Post", list_match.group(1))
        self.assertNotIn("Middle Post", list_match.group(1))

    def test_other_authors_posts_are_excluded_failure(self) -> None:
        for html in (self.first, self.middle, self.last, self.extra):
            nav = more_from_html(html)
            self.assertNotIn("Other Author Post", nav)
            self.assertNotIn("/posts/other/", nav)
            self.assertNotIn("/authors/writer-b/", nav)

    def test_solo_author_omits_the_section_failure(self) -> None:
        self.assertFalse(more_from_html(self.other))
        self.assertNotIn("more-from-author", self.other)
        self.assertNotIn("First Post", self.other)


class MoreFromDocsTests(unittest.TestCase):
    def test_readme_documents_more_from_author_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        lowered = readme.lower()
        self.assertIn("more from", lowered)
        self.assertIn("older", lowered)
        self.assertIn("newer", lowered)


if __name__ == "__main__":
    unittest.main()

