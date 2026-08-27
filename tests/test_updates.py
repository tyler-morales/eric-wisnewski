"""Footer Updates log: a dated feed of linkable notes, not a changelog."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOOTER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "footer.html"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
LIST_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "list.html"
UPDATES_LIST_LAYOUT = REPO_ROOT / "layouts" / "updates" / "list.html"
UPDATES_ENTRY_LAYOUT = REPO_ROOT / "layouts" / "updates" / "single.html"
UPDATES_INDEX = REPO_ROOT / "content" / "updates" / "_index.md"
UPDATES_DIR = REPO_ROOT / "content" / "updates"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
HUGO_TIMEOUT_SECONDS = 120

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
DAY_HEADING_RE = re.compile(
    r'<time datetime="(\d{4}-\d{2}-\d{2})">\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*</time>'
)
TECHNICAL_TERMS = (
    "changelog",
    "cloudflare",
    "d1",
    "deploy",
    "hugo",
    "kv",
    "migration",
    "pages cms",
    "resend",
    "turnstile",
    "wrangler",
    "api",
)


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


def update_note_paths() -> list[Path]:
    return sorted(path for path in UPDATES_DIR.glob("*.md") if path.name != "_index.md")


def note_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def note_closing_line(path: Path) -> str:
    """Last paragraph of a note: belongs on the note's own page, not the feed."""
    lines = [line.strip() for line in note_body(path).splitlines() if line.strip()]
    return lines[-1] if lines else ""


def note_slug(path: Path) -> str:
    return parse_front_matter(path).get("slug") or path.stem


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


def is_staged() -> bool:
    match = FRONT_MATTER_RE.match(UPDATES_INDEX.read_text(encoding="utf-8"))
    return bool(match and "render: never" in match.group(1))


def unstage(text: str) -> str:
    """Front matter as it will read once the staging block is deleted."""
    match = FRONT_MATTER_RE.match(text)
    assert match is not None
    kept: list[str] = []
    in_block = False
    for line in match.group(1).splitlines():
        if line.startswith(("build:", "cascade:")):
            in_block = True
            continue
        if in_block:
            if not line.strip() or line.startswith((" ", "\t")):
                continue
            in_block = False
        if not line.startswith("#"):
            kept.append(line)
    return text.replace(match.group(1), "\n".join(kept), 1)


def unstaged_content_dir(tmp: Path) -> Path:
    """A copy of content/ with /updates/ published, to prove it still builds."""
    copy = tmp / "content"
    shutil.copytree(REPO_ROOT / "content", copy)
    index = copy / "updates" / "_index.md"
    index.write_text(unstage(index.read_text(encoding="utf-8")), encoding="utf-8")
    return copy


class UpdatesTemplateTests(unittest.TestCase):
    def test_header_omits_updates_failure(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("updates/", header.lower())
        self.assertNotIn("Updates", header)

    def test_home_list_does_not_range_updates_failure(self) -> None:
        template = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn('"updates"', template)

    def test_feed_layout_groups_by_day_and_links_entries_success(self) -> None:
        self.assertTrue(UPDATES_LIST_LAYOUT.is_file())
        layout = UPDATES_LIST_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("GroupByDate", layout)
        self.assertIn("updates-day", layout)
        self.assertIn("updates-entry", layout)
        self.assertIn("RelPermalink", layout)

    def test_feed_layout_has_no_comments_or_subscribe_failure(self) -> None:
        layout = UPDATES_LIST_LAYOUT.read_text(encoding="utf-8")
        self.assertNotIn("comments.html", layout)
        self.assertNotIn("subscribe.html", layout)
        self.assertNotIn("share.html", layout)

    def test_entry_layout_exists_and_links_back_success(self) -> None:
        self.assertTrue(UPDATES_ENTRY_LAYOUT.is_file())
        layout = UPDATES_ENTRY_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("updates/", layout)
        self.assertNotIn("comments.html", layout)
        self.assertNotIn("subscribe.html", layout)
        self.assertNotIn("share.html", layout)

    def test_updates_index_exists_success(self) -> None:
        self.assertTrue(UPDATES_INDEX.is_file())
        text = UPDATES_INDEX.read_text(encoding="utf-8")
        self.assertIn("title: Updates", text)
        body = note_body(UPDATES_INDEX).strip()
        self.assertGreater(len(body), 40)
        self.assertLess(len(body), 600)

    def test_update_notes_are_plain_language_failure(self) -> None:
        self.assertGreaterEqual(len(update_note_paths()), 2)
        for path in update_note_paths():
            with self.subTest(note=path.name):
                lowered = f"{parse_front_matter(path).get('summary', '')}\n{note_body(path)}".lower()
                for term in TECHNICAL_TERMS:
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(term)}\b", lowered),
                        f"{path.name} mentions {term!r}",
                    )

    def test_update_notes_have_date_slug_and_summary_success(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                front_matter = parse_front_matter(path)
                self.assertIn("title", front_matter)
                self.assertIn("date", front_matter)
                self.assertEqual(front_matter.get("slug"), path.stem)
                summary = front_matter.get("summary", "")
                self.assertGreater(len(summary), 20, "each note needs a feed summary")
                self.assertLess(len(summary), 200, "summaries stay one sentence")
                self.assertNotEqual(front_matter.get("draft", "false").lower(), "true")

    def test_note_bodies_say_more_than_their_summary_failure(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                summary = parse_front_matter(path).get("summary", "")
                self.assertNotIn(
                    summary,
                    note_closing_line(path),
                    "the note page must add detail the feed does not show",
                )

    def test_hugo_pins_update_permalinks_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertRegex(toml, r"updates\s*=\s*'/updates/:slug/'")

    def test_staging_is_one_deletable_block_success(self) -> None:
        """Publishing must stay a delete: no other file holds the switch."""
        text = UPDATES_INDEX.read_text(encoding="utf-8")
        self.assertNotIn("render: never", unstage(text))
        self.assertIn("title: Updates", unstage(text))
        self.assertNotIn("render = 'never'", HUGO_TOML.read_text(encoding="utf-8").split("/updates")[-1])
        if is_staged():
            front_matter = FRONT_MATTER_RE.match(text)
            assert front_matter is not None
            self.assertIn("cascade:", front_matter.group(1), "notes must be staged too")

    def test_pages_cms_updates_collection_has_feed_fields_success(self) -> None:
        config = PAGES_YML.read_text(encoding="utf-8")
        self.assertIn("path: content/updates", config)
        self.assertIn("label: Site updates", config)
        updates_block = config.split("- name: updates", 1)[-1]
        self.assertIn("name: summary", updates_block)
        self.assertIn("name: image", updates_block)

    def test_updates_css_has_feed_and_focus_styles_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        for selector in (".updates-day", ".updates-entry", ".updates-page a:focus-visible"):
            self.assertTrue(selector in css, f"style.css needs {selector}")

    def test_updates_css_drops_month_grouping_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertFalse(".updates-month" in css, "month grouping styles are dead")
        self.assertFalse(".updates-note" in css, "note styles replaced by entry styles")


class UpdatesBuildTests(unittest.TestCase):
    """Staged, so it builds against an unstaged copy of content/ to stay honest."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="site-updates-live-"))
        cls._output_dir = cls._tmp / "out"
        result = subprocess.run(
            [
                "hugo",
                "--contentDir",
                str(unstaged_content_dir(cls._tmp)),
                "--destination",
                str(cls._output_dir),
                "--quiet",
                "--noBuildLock",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        feed = cls._output_dir / "updates" / "index.html"
        cls.feed = feed.read_text(encoding="utf-8") if feed.is_file() else ""
        cls.output_dir = cls._output_dir

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def entry_html(self, path: Path) -> str:
        page = self.output_dir / "updates" / note_slug(path) / "index.html"
        self.assertTrue(page.is_file(), f"{note_slug(path)} must have its own page")
        return page.read_text(encoding="utf-8")

    def test_feed_page_builds_success(self) -> None:
        self.assertTrue(self.feed)
        self.assertIn("<h1>Updates</h1>", self.feed)

    def test_feed_has_no_comments_or_subscribe_failure(self) -> None:
        self.assertNotIn('id="comments"', self.feed)
        self.assertNotIn('id="subscribe"', self.feed)

    def test_updates_link_is_on_every_page_success(self) -> None:
        self.assertIn('<a href="/updates/">Updates</a>', self.home)
        self.assertIn('<a href="/updates/">Updates</a>', self.feed)

    def test_updates_is_not_in_main_nav_failure(self) -> None:
        nav = main_nav_html(self.home)
        self.assertTrue(nav)
        self.assertNotIn("Updates", nav)
        self.assertNotIn("/updates/", nav)

    def test_updates_notes_are_not_on_home_failure(self) -> None:
        list_html = POST_LIST_RE.search(self.home)
        self.assertIsNotNone(list_html)
        assert list_html is not None
        self.assertNotIn("/updates/", list_html.group(1))
        for path in update_note_paths():
            title = parse_front_matter(path).get("title", "")
            if title:
                self.assertNotIn(title, list_html.group(1))

    def test_feed_groups_entries_under_machine_readable_days_success(self) -> None:
        days = DAY_HEADING_RE.findall(self.feed)
        self.assertGreaterEqual(len(days), 2, "feed groups entries by day")
        note_days = {parse_front_matter(p).get("date", "")[:10] for p in update_note_paths()}
        for iso, _human in days:
            self.assertIn(iso, note_days)

    def test_feed_links_every_note_to_its_own_page_success(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                self.assertIn(f'href="/updates/{note_slug(path)}/"', self.feed)
                self.assertIn(parse_front_matter(path)["title"], self.feed)

    def test_feed_shows_summaries_not_full_notes_failure(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                summary = parse_front_matter(path).get("summary", "")
                self.assertIn(summary, self.feed)
                self.assertNotIn(note_closing_line(path), self.feed)

    def test_note_pages_show_full_text_and_link_back_success(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                html = self.entry_html(path)
                self.assertIn(parse_front_matter(path)["title"], html)
                self.assertIn(note_closing_line(path), html)
                self.assertIn('href="/updates/"', html)

    def test_note_pages_have_no_comments_or_subscribe_failure(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                html = self.entry_html(path)
                self.assertNotIn('id="comments"', html)
                self.assertNotIn('id="subscribe"', html)


class UpdatesVisibilityTests(unittest.TestCase):
    """The live build must agree with the staging block, whichever way it is set."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="site-updates-prod-"))
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
            raise unittest.SkipTest(f"hugo build failed:\n{result.stderr}")
        cls.output_dir = cls._output_dir
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_feed_and_note_pages_match_staging_failure(self) -> None:
        published = not is_staged()
        self.assertEqual((self.output_dir / "updates" / "index.html").is_file(), published)
        for path in update_note_paths():
            with self.subTest(note=path.name):
                page = self.output_dir / "updates" / note_slug(path) / "index.html"
                self.assertEqual(page.is_file(), published)

    def test_footer_link_matches_staging_failure(self) -> None:
        """A staged page has no URL, so a link to it would be a dead link."""
        self.assertEqual('href="/updates/"' in self.home, not is_staged())

    def test_updates_stay_out_of_the_sitemap_failure(self) -> None:
        """Footer-only either way: the section lists 'never', so it is never indexed."""
        sitemap = self.output_dir / "sitemap.xml"
        self.assertTrue(sitemap.is_file())
        self.assertNotIn("/updates/", sitemap.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
