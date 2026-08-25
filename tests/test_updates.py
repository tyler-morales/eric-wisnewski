"""Footer Updates log: reader notes, not a changelog, not in main nav."""

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
UPDATES_LAYOUT = REPO_ROOT / "layouts" / "updates" / "list.html"
UPDATES_INDEX = REPO_ROOT / "content" / "updates" / "_index.md"
UPDATES_DIR = REPO_ROOT / "content" / "updates"
PAGES_YML = REPO_ROOT / ".pages.yml"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
HUGO_TIMEOUT_SECONDS = 120

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
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
    return sorted(
        path
        for path in UPDATES_DIR.glob("*.md")
        if path.name != "_index.md"
    )


def note_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def footer_html(html: str) -> str:
    match = re.search(r"<footer\b[^>]*>.*?</footer>", html, re.DOTALL | re.IGNORECASE)
    return match.group(0) if match else ""


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


class UpdatesTemplateTests(unittest.TestCase):
    def test_footer_partial_links_updates_success(self) -> None:
        partial = FOOTER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("updates/", partial)
        self.assertIn(">Updates</a>", partial)

    def test_header_omits_updates_failure(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("updates/", header.lower())
        self.assertNotIn("Updates", header)

    def test_home_list_does_not_range_updates_failure(self) -> None:
        template = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn('"updates"', template)

    def test_updates_layout_exists_and_skips_comments_success(self) -> None:
        self.assertTrue(UPDATES_LAYOUT.is_file())
        layout = UPDATES_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("GroupByDate", layout)
        self.assertNotIn("comments.html", layout)
        self.assertNotIn("subscribe.html", layout)

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
                lowered = note_body(path).lower()
                for term in TECHNICAL_TERMS:
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(term)}\b", lowered),
                        f"{path.name} mentions {term!r}",
                    )

    def test_update_notes_have_dates_success(self) -> None:
        for path in update_note_paths():
            with self.subTest(note=path.name):
                front_matter = parse_front_matter(path)
                self.assertIn("title", front_matter)
                self.assertIn("date", front_matter)
                self.assertNotEqual(front_matter.get("draft", "false").lower(), "true")

    def test_pages_cms_has_updates_collection_success(self) -> None:
        config = PAGES_YML.read_text(encoding="utf-8")
        self.assertIn("path: content/updates", config)
        self.assertIn("label: Site updates", config)

    def test_updates_css_has_focus_visible_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".updates-note", css)
        self.assertRegex(
            css,
            r"\.updates-page a:focus-visible|\.post-content a:focus-visible",
        )


class UpdatesBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="site-updates-hugo-"))
        result = subprocess.run(
            ["hugo", "--destination", str(cls._output_dir), "--quiet"],
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
        updates = cls._output_dir / "updates" / "index.html"
        cls.updates = updates.read_text(encoding="utf-8") if updates.is_file() else ""
        cls.output_dir = cls._output_dir

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_updates_page_builds_success(self) -> None:
        self.assertTrue(self.updates)
        self.assertIn("<h1>", self.updates)
        self.assertIn("Updates", self.updates)

    def test_updates_page_has_no_comments_or_subscribe_failure(self) -> None:
        self.assertNotIn('id="comments"', self.updates)
        self.assertNotIn('id="subscribe"', self.updates)

    def test_home_footer_links_updates_success(self) -> None:
        footer = footer_html(self.home)
        self.assertRegex(
            footer,
            r'<a\b[^>]*href="[^"]*updates/[^"]*"[^>]*>\s*Updates\s*</a>',
        )

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

    def test_updates_groups_notes_by_month_success(self) -> None:
        self.assertRegex(self.updates, r"<h2[^>]*>\s*[A-Z][a-z]+ \d{4}\s*</h2>")
        for path in update_note_paths():
            title = parse_front_matter(path).get("title", "")
            if title:
                self.assertIn(title, self.updates)

    def test_update_notes_have_no_permalink_pages_failure(self) -> None:
        for path in update_note_paths():
            slug = parse_front_matter(path).get("slug") or path.stem
            note_page = self.output_dir / "updates" / slug / "index.html"
            with self.subTest(slug=slug):
                self.assertFalse(note_page.is_file())


if __name__ == "__main__":
    unittest.main()
