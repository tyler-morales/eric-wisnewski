"""Sheet cells: http(s) URLs become links; everything else stays escaped text."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CELL = REPO_ROOT / "layouts" / "partials" / "school-sheets-cell.html"
SHEETS = REPO_ROOT / "layouts" / "partials" / "school-sheets.html"
STYLE = REPO_ROOT / "assets" / "css" / "style.css"
SHEETS_JS = REPO_ROOT / "static" / "js" / "school-sheets.js"
HUGO_TIMEOUT_SECONDS = 60

LAYOUT = """
DEPAUL={{ partial "school-sheets-cell.html" "https://ericwisnewski.com/posts/depaul/" }}
ERICWIZ={{ partial "school-sheets-cell.html" "https://ericwiz.com/posts/depaul/" }}
WWW={{ partial "school-sheets-cell.html" "https://www.ericwisnewski.com/posts/loyola/" }}
HTTP={{ partial "school-sheets-cell.html" "http://ericwisnewski.com/posts/boston-college" }}
MIX={{ partial "school-sheets-cell.html" "Notes: https://ericwisnewski.com/posts/depaul/ (recap)." }}
EXT={{ partial "school-sheets-cell.html" "https://example.com/a?b=1&c=2" }}
PLAIN={{ partial "school-sheets-cell.html" "A-" }}
GRADE={{ partial "school-sheets-cell.html" "N/A (A+)" }}
INJECT={{ partial "school-sheets-cell.html" `<script>alert(1)</script> <img src=x onerror=alert(1)>` }}
JS={{ partial "school-sheets-cell.html" "javascript:alert(1)" }}
BREAK={{ partial "school-sheets-cell.html" `https://evil.com/" onclick="alert(1)` }}
MISSING={{ partial "school-sheets-cell.html" "https://ericwisnewski.com/posts/not-a-real-post/" }}
QUOTE={{ partial "school-sheets-cell.html" `He said "hi" & <b>no</b>` }}
AMPTITLE={{ partial "school-sheets-cell.html" "https://ericwisnewski.com/posts/amp-school/" }}
SLASH={{ partial "school-sheets-cell.html" "https://ericwisnewski.com//posts/depaul/" }}
"""


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.starts: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.starts.append((tag, dict(attrs)))


def _line(html: str, label: str) -> str:
    prefix = label + "="
    for line in html.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"missing {label} in render")


def _tags(fragment: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = _Tags()
    parser.feed(fragment)
    return parser.starts


def call_search(script_body: str) -> object:
    script = (
        f"import {{ rowMatchesQuery }} from {json.dumps(SHEETS_JS.as_uri())};\n"
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


class SchoolSheetCellSourceTests(unittest.TestCase):
    def test_cell_partial_links_posts_and_escapes_success(self) -> None:
        cell = CELL.read_text(encoding="utf-8")
        sheets = SHEETS.read_text(encoding="utf-8")
        self.assertIn('partial "school-sheets-cell.html"', sheets)
        self.assertIn('data-value="{{ $cell }}"', sheets)
        self.assertIn("htmlEscape", cell)
        self.assertIn("Read the review", cell)
        self.assertIn('rel="noopener noreferrer"', cell)
        self.assertIn('target="_blank"', cell)
        self.assertIn("site.GetPage", cell)
        self.assertIn("ericwisnewski.com", cell)
        self.assertIn("ericwiz.com", cell)
        self.assertEqual(cell.count("safeHTML"), 1)
        css = STYLE.read_text(encoding="utf-8")
        self.assertIn(".school-sheets-table a:focus-visible", css)
        self.assertIn("text-underline-offset: 0.12em", css)
        self.assertIn("overflow-wrap: anywhere", css)
        js = SHEETS_JS.read_text(encoding="utf-8")
        self.assertIn("td.getAttribute('data-value') || td.textContent", js)
        self.assertIn("rowMatchesQuery(row.textContent, values, q)", js)

    def test_cell_partial_does_not_mark_raw_sheet_html_safe_failure(self) -> None:
        cell = CELL.read_text(encoding="utf-8")
        sheets = SHEETS.read_text(encoding="utf-8")
        self.assertNotIn(">{{ $cell }}</td>", sheets)
        self.assertNotIn("$cell | safeHTML", cell)
        self.assertNotIn("safeURL", cell)
        self.assertNotIn("safeJS", cell)


class SchoolSheetSearchTests(unittest.TestCase):
    def test_query_matches_link_text_or_raw_url_success(self) -> None:
        self.assertEqual(
            call_search(
                "console.log(JSON.stringify(["
                "rowMatchesQuery('Wintrust Arena - DePaul University', "
                "['https://ericwisnewski.com/posts/depaul/'], 'wintrust'),"
                "rowMatchesQuery('Wintrust Arena - DePaul University', "
                "['https://ericwisnewski.com/posts/depaul/'], 'posts/depaul'),"
                "rowMatchesQuery('A-', ['A-'], ''),"
                "rowMatchesQuery('DePaul', ['DePaul'], 'depaul')"
                "]));"
            ),
            [True, True, True, True],
        )

    def test_query_does_not_match_unrelated_cell_failure(self) -> None:
        self.assertEqual(
            call_search(
                "console.log(JSON.stringify(["
                "rowMatchesQuery('A-', ['A-'], 'depaul'),"
                "rowMatchesQuery('Read the review', "
                "['https://ericwisnewski.com/posts/depaul/'], 'loyola')"
                "]));"
            ),
            [False, False],
        )


class SchoolSheetCellRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="school-sheet-links-"))
        partials = cls._tmp / "layouts" / "partials"
        partials.mkdir(parents=True)
        shutil.copy(CELL, partials / "school-sheets-cell.html")
        layouts = cls._tmp / "layouts" / "_default"
        layouts.mkdir(parents=True)
        (layouts / "single.html").write_text(LAYOUT, encoding="utf-8")
        posts = cls._tmp / "content" / "posts"
        posts.mkdir(parents=True)
        (posts / "depaul.md").write_text(
            "---\ntitle: Wintrust Arena - DePaul University\nslug: depaul\ndate: 2026-11-09\n---\nHi\n",
            encoding="utf-8",
        )
        (posts / "loyola.md").write_text(
            "---\ntitle: Gentile Arena - Loyola University Chicago\nslug: loyola\ndate: 2026-10-19\n---\nHi\n",
            encoding="utf-8",
        )
        (posts / "boston-college.md").write_text(
            "---\ntitle: Boston College - Conte Fourm\nslug: boston-college\ndate: 2026-03-10\n---\nHi\n",
            encoding="utf-8",
        )
        (posts / "amp-school.md").write_text(
            "---\ntitle: 'A & B \"Arena\"'\nslug: amp-school\ndate: 2026-01-01\n---\nHi\n",
            encoding="utf-8",
        )
        (cls._tmp / "content" / "check.md").write_text(
            "---\ntitle: check\ndate: 2026-01-01\n---\n",
            encoding="utf-8",
        )
        (cls._tmp / "hugo.toml").write_text(
            "baseURL = 'http://localhost:1313/'\n"
            "disableKinds = ['taxonomy', 'term', 'sitemap', 'RSS']\n",
            encoding="utf-8",
        )
        dest = cls._tmp / "public"
        result = subprocess.run(
            ["hugo", "--destination", str(dest), "--quiet", "--noBuildLock"],
            cwd=cls._tmp,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"hugo failed:\n{result.stderr}")
        cls.html = (dest / "check" / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_post_urls_are_relative_titled_links_success(self) -> None:
        depaul = _line(self.html, "DEPAUL")
        self.assertEqual(
            depaul,
            '<a href="/posts/depaul/">Wintrust Arena - DePaul University</a>',
        )
        self.assertEqual(_line(self.html, "ERICWIZ"), depaul)
        self.assertEqual(
            _line(self.html, "WWW"),
            '<a href="/posts/loyola/">Gentile Arena - Loyola University Chicago</a>',
        )
        self.assertEqual(
            _line(self.html, "HTTP"),
            '<a href="/posts/boston-college/">Boston College - Conte Fourm</a>',
        )
        self.assertEqual(
            _line(self.html, "MIX"),
            'Notes: <a href="/posts/depaul/">Wintrust Arena - DePaul University</a> (recap).',
        )
        self.assertEqual(
            _line(self.html, "MISSING"),
            '<a href="/posts/not-a-real-post/">Read the review</a>',
        )
        self.assertEqual(
            _line(self.html, "AMPTITLE"),
            '<a href="/posts/amp-school/">A &amp; B &#34;Arena&#34;</a>',
        )
        for label in ("DEPAUL", "WWW", "HTTP", "MISSING", "AMPTITLE"):
            self.assertNotIn('target="_blank"', _line(self.html, label))

    def test_external_url_opens_in_a_new_tab_success(self) -> None:
        ext = _line(self.html, "EXT")
        tags = _tags(ext)
        anchors = [attrs for tag, attrs in tags if tag == "a"]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["href"], "https://example.com/a?b=1&c=2")
        self.assertEqual(anchors[0]["target"], "_blank")
        self.assertEqual(anchors[0]["rel"], "noopener noreferrer")
        self.assertIn("visually-hidden", ext)
        self.assertIn("opens in a new tab", ext)

    def test_sheet_html_grades_and_schemes_stay_text_failure(self) -> None:
        inject = _line(self.html, "INJECT")
        self.assertEqual(
            inject,
            "&lt;script&gt;alert(1)&lt;/script&gt; &lt;img src=x onerror=alert(1)&gt;",
        )
        self.assertEqual(_tags(inject), [])
        self.assertEqual(_line(self.html, "PLAIN"), "A-")
        self.assertEqual(_line(self.html, "GRADE"), "N/A (A+)")
        self.assertEqual(_line(self.html, "JS"), "javascript:alert(1)")
        self.assertEqual(_tags(_line(self.html, "JS")), [])
        self.assertEqual(
            _line(self.html, "QUOTE"),
            "He said &#34;hi&#34; &amp; &lt;b&gt;no&lt;/b&gt;",
        )
        self.assertEqual(_tags(_line(self.html, "QUOTE")), [])
        broken = _line(self.html, "BREAK")
        anchors = [attrs for tag, attrs in _tags(broken) if tag == "a"]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0].get("href"), "https://evil.com/")
        self.assertNotIn("onclick", anchors[0])
        slash = _line(self.html, "SLASH")
        slash_anchors = [attrs for tag, attrs in _tags(slash) if tag == "a"]
        self.assertEqual(
            slash_anchors[0].get("href"),
            "https://ericwisnewski.com//posts/depaul/",
        )
        self.assertEqual(slash_anchors[0].get("target"), "_blank")


if __name__ == "__main__":
    unittest.main()
