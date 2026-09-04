"""School report card from Pages CMS front matter on Eric’s Posts."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHORTCODE = REPO_ROOT / "layouts" / "shortcodes" / "report-card.html"
PARTIAL = REPO_ROOT / "layouts" / "partials" / "report-card.html"
SINGLE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "single.html"
PAGES_YML = REPO_ROOT / ".pages.yml"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
BOSTON = REPO_ROOT / "content" / "posts" / "boston-college.md"
NIU = REPO_ROOT / "content" / "posts" / "northern-illinois.md"
HUGO_TIMEOUT_SECONDS = 120

COLLECTION_RE = re.compile(
    r"(?m)^  - name: (posts|gradys-tour|da-breakdown-w-tad|jers-prospect-profiles)\n(.*?)(?=^  - name: |\Z)",
    re.DOTALL,
)

# Same 4.0 scale as /school-sheets/ (A+ = 4.3, minus = −0.3). F is 0, not missing.
GRADE_POINTS = {
    "A+": 4.3,
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D+": 1.3,
    "D": 1.0,
    "D-": 0.7,
    "F": 0.0,
    "N/A (A+)": 4.3,
}

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: Report Card Fixture",
        "slug: report-card-fixture",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:00:00Z",
        "draft: false",
        "report_card:",
        "  school: Boston College",
        "  stadium: D",
        "  fan_base: F",
        "  campus: B",
        "---",
        "Tip-off.",
        "",
    ]
)

FIXTURE_NIU = "\n".join(
    [
        "---",
        "title: NIU Card Fixture",
        "slug: report-card-niu",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:01:00Z",
        "draft: false",
        "report_card:",
        "  school: Northern Illinois",
        "  stadium: C-",
        "  fan_base: D",
        "  campus: F",
        "---",
        "DeKalb.",
        "",
    ]
)

FIXTURE_IOWA = "\n".join(
    [
        "---",
        "title: Iowa Card Fixture",
        "slug: report-card-iowa",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:02:00Z",
        "draft: false",
        "report_card:",
        "  school: University of Iowa",
        "  stadium: B",
        "  fan_base: A",
        '  campus: "N/A (A+)"',
        "---",
        "Iowa City.",
        "",
    ]
)

FIXTURE_BAD_GRADE = "\n".join(
    [
        "---",
        "title: Bogus Grade Fixture",
        "slug: report-card-bogus",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:03:00Z",
        "draft: false",
        "report_card:",
        "  school: Bogus",
        "  stadium: Q",
        "  fan_base: F",
        "  campus: B",
        "---",
        "Nope.",
        "",
    ]
)

FIXTURE_TOUR = "\n".join(
    [
        "---",
        "title: Tour Report Card Fixture",
        "slug: report-card-tour-fixture",
        "author: grady-davis",
        "date: 2026-09-04T00:04:00Z",
        "draft: false",
        "report_card:",
        "  school: Boston College",
        "  stadium: D",
        "  fan_base: F",
        "  campus: B",
        "---",
        "On the road.",
        "",
    ]
)

FIXTURE_OTHER_AUTHOR = "\n".join(
    [
        "---",
        "title: Other Author Report Card",
        "slug: report-card-other-author",
        "author: tyler-morales",
        "date: 2026-09-04T00:05:00Z",
        "draft: false",
        "report_card:",
        "  school: Boston College",
        "  stadium: D",
        "  fan_base: F",
        "  campus: B",
        "---",
        "Not Eric.",
        "",
    ]
)


def collection_block(pages_yml: str, name: str) -> str:
    for match in COLLECTION_RE.finditer(pages_yml):
        if match.group(1) == name:
            return match.group(0)
    return ""


def report_gpa(stadium: str, fans: str, campus: str) -> str | None:
    try:
        points = [GRADE_POINTS[stadium], GRADE_POINTS[fans], GRADE_POINTS[campus]]
    except KeyError:
        return None
    return f"{sum(points) / 3:.2f}"


def run_hugo(*, destination: Path, content_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "hugo",
            "--destination",
            str(destination),
            "--contentDir",
            str(content_dir),
            "--quiet",
            "--noBuildLock",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class ReportCardGradeTests(unittest.TestCase):
    def test_gpa_averages_the_three_marks_success(self) -> None:
        self.assertEqual(report_gpa("D", "F", "B"), "1.33")
        self.assertEqual(report_gpa("C-", "D", "F"), "0.90")
        self.assertEqual(report_gpa("B", "A", "N/A (A+)"), "3.77")
        self.assertEqual(GRADE_POINTS["F"], 0.0)
        self.assertEqual(GRADE_POINTS["A+"], GRADE_POINTS["N/A (A+)"])

    def test_gpa_rejects_unknown_marks_failure(self) -> None:
        self.assertIsNone(report_gpa("Q", "F", "B"))
        self.assertIsNone(report_gpa("B", "", "B"))
        self.assertNotIn("A++", GRADE_POINTS)
        self.assertEqual(report_gpa("F", "F", "F"), "0.00")


class ReportCardSourceTests(unittest.TestCase):
    def test_cms_fields_live_only_on_posts_success(self) -> None:
        pages = PAGES_YML.read_text(encoding="utf-8")
        posts = collection_block(pages, "posts")
        self.assertIn("name: report_card", posts)
        self.assertIn("type: object", posts)
        self.assertIn("Stadium grade", posts)
        self.assertIn("Fan base grade", posts)
        self.assertIn("Campus grade", posts)
        self.assertIn("name: fan_base", posts)
        self.assertIn("name: stadium", posts)
        self.assertIn("name: campus", posts)
        self.assertGreaterEqual(posts.count("type: select"), 3)
        self.assertIn("N/A (A+)", posts)
        self.assertIn("placeholder: Select a grade", posts)
        layout = SINGLE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('partial "report-card.html"', layout)
        rc_at = layout.find('partial "report-card.html"')
        self.assertGreater(rc_at, layout.find('partial "page-content.html"'))
        self.assertGreater(rc_at, layout.find('partial "post-gallery.html"'))
        self.assertLess(layout.find('partial "scoreboard.html"'), layout.find('partial "page-content.html"'))
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertTrue(PARTIAL.is_file())
        self.assertIn("eric-wisnewski", src)
        self.assertIn('eq .Section "posts"', src)
        self.assertIn("<aside", src)
        self.assertIn("<table", src)
        self.assertIn("<caption", src)
        self.assertIn("Stadium", src)
        self.assertIn("Fan Base", src)
        self.assertIn("Campus", src)
        self.assertIn("GPA", src)
        self.assertIn("isset", src)
        for mark in GRADE_POINTS:
            self.assertIn(mark, src)

    def test_other_collections_and_shortcode_stay_out_failure(self) -> None:
        pages = PAGES_YML.read_text(encoding="utf-8")
        for name in ("gradys-tour", "da-breakdown-w-tad", "jers-prospect-profiles"):
            with self.subTest(collection=name):
                self.assertNotIn("name: report_card", collection_block(pages, name))
        self.assertFalse(SHORTCODE.is_file())
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("Boston College", src)
        self.assertNotIn('stadium="D"', src)
        self.assertNotIn("<button", src)
        posts = collection_block(pages, "posts")
        stadium_block = posts[posts.find("name: stadium") : posts.find("name: fan_base")]
        self.assertIn("type: select", stadium_block)
        self.assertNotIn("type: string", stadium_block)

    def test_card_styles_look_like_a_paper_report_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        start = css.find("/* School report card */")
        end = css.find("/* Captions", start)
        block = css[start:end] if start >= 0 and end > start else ""
        self.assertIn(".report-card", block)
        self.assertIn(".report-card-banner", block)
        self.assertIn(".report-card-school", block)
        self.assertIn(".report-card-grade", block)
        self.assertIn(".report-card-gpa", block)
        self.assertIn("var(--font-serif)", block)
        self.assertIn("#f1dcab", block)
        self.assertIn("fractalNoise", block)
        self.assertIn("#7a2a2a", block)
        self.assertIn("#b42318", block)
        src = (REPO_ROOT / "layouts" / "partials" / "report-card.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("Student", src)

    def test_card_is_not_a_gym_flip_board_failure(self) -> None:
        src = PARTIAL.read_text(encoding="utf-8")
        css = STYLE_CSS.read_text(encoding="utf-8")
        start = css.find("/* School report card */")
        end = css.find("/* Captions", start)
        block = css[start:end] if start >= 0 and end > start else ""
        self.assertNotIn("report-card-digit", src)
        self.assertNotIn("rotateX", block)
        self.assertNotIn("IntersectionObserver", src)
        self.assertNotIn('role="img"', src)
        self.assertNotIn("<button", src)
        self.assertNotIn("{{< report-card", src)
        self.assertNotIn("var(--bg)", block)
        self.assertNotIn("background: #fff", block)

    def test_readme_documents_cms_fields_success(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("report_card", text)
        self.assertIn("dropdowns", text)
        self.assertIn("Fan base", text)
        self.assertNotIn("{{< report-card", text)

    def test_recap_posts_use_sheet_grades_success(self) -> None:
        boston = BOSTON.read_text(encoding="utf-8")
        niu = NIU.read_text(encoding="utf-8")
        self.assertIn("report_card:", boston)
        self.assertIn("school: Boston College", boston)
        self.assertIn("stadium: D", boston)
        self.assertIn("fan_base: F", boston)
        self.assertIn("campus: B", boston)
        self.assertIn("report_card:", niu)
        self.assertIn("school: Northern Illinois", niu)
        self.assertIn("stadium: C-", niu)
        self.assertIn("fan_base: D", niu)
        self.assertIn("campus: F", niu)

    def test_recap_posts_do_not_invent_grades_failure(self) -> None:
        boston = BOSTON.read_text(encoding="utf-8")
        niu = NIU.read_text(encoding="utf-8")
        self.assertNotIn("stadium: A", boston)
        self.assertNotIn("campus: A", niu)
        self.assertNotIn("fan_base: A", boston)
        self.assertNotIn("{{< report-card", boston)
        self.assertNotIn("{{< report-card", niu)


class ReportCardBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="report-card-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "report-card-fixture.md").write_text(
            FIXTURE_POST, encoding="utf-8"
        )
        (content_dir / "posts" / "report-card-niu.md").write_text(
            FIXTURE_NIU, encoding="utf-8"
        )
        (content_dir / "posts" / "report-card-iowa.md").write_text(
            FIXTURE_IOWA, encoding="utf-8"
        )
        (content_dir / "posts" / "report-card-bogus.md").write_text(
            FIXTURE_BAD_GRADE, encoding="utf-8"
        )
        (content_dir / "posts" / "report-card-other-author.md").write_text(
            FIXTURE_OTHER_AUTHOR, encoding="utf-8"
        )
        (content_dir / "gradys-tour" / "report-card-tour-fixture.md").write_text(
            FIXTURE_TOUR, encoding="utf-8"
        )
        dest = cls._tmp / "out"
        result = run_hugo(destination=dest, content_dir=content_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        try:
            cls.fixture = (dest / "posts" / "report-card-fixture" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.niu_fix = (dest / "posts" / "report-card-niu" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.iowa = (dest / "posts" / "report-card-iowa" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.bogus = (dest / "posts" / "report-card-bogus" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.other = (
                dest / "posts" / "report-card-other-author" / "index.html"
            ).read_text(encoding="utf-8")
            cls.tour = (
                dest / "gradys-tour" / "report-card-tour-fixture" / "index.html"
            ).read_text(encoding="utf-8")
            cls.boston = (dest / "posts" / "boston-college" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.niu = (dest / "posts" / "northern-illinois" / "index.html").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_partial_renders_subjects_grades_and_gpa_success(self) -> None:
        from html import unescape

        html = self.fixture
        self.assertEqual(html.count('class="report-card"'), 1)
        self.assertIn("Boston College", html)
        self.assertIn('data-grade="D"', html)
        self.assertIn('data-grade="F"', html)
        self.assertIn('data-grade="B"', html)
        self.assertIn(report_gpa("D", "F", "B") or "", html)
        self.assertIn("<table", html)
        self.assertIn("Fan Base", html)
        self.assertIn("GPA", html)
        self.assertIn('data-grade="C-"', self.niu_fix)
        self.assertIn(report_gpa("C-", "D", "F") or "", self.niu_fix)
        iowa = unescape(self.iowa)
        self.assertIn("N/A (A+)", iowa)
        self.assertIn(report_gpa("B", "A", "N/A (A+)") or "", iowa)

    def test_partial_omits_invalid_and_non_eric_cards_failure(self) -> None:
        self.assertNotIn('class="report-card"', self.bogus)
        self.assertNotIn('data-grade="Q"', self.bogus)
        self.assertNotIn('class="report-card"', self.tour)
        self.assertNotIn('class="report-card"', self.other)
        self.assertNotIn("{{< report-card", self.fixture)

    def test_boston_college_page_includes_the_sheet_card_success(self) -> None:
        self.assertIn('class="report-card"', self.boston)
        self.assertIn('data-grade="D"', self.boston)
        self.assertIn('data-grade="F"', self.boston)
        self.assertIn('data-grade="B"', self.boston)
        self.assertIn(report_gpa("D", "F", "B") or "", self.boston)
        self.assertIn('class="scoreboard"', self.boston)
        body = self.boston.find("Do not waste your time in Boston")
        self.assertGreater(body, 0)
        self.assertLess(self.boston.find('class="scoreboard"'), body)
        self.assertGreater(self.boston.find('class="report-card"'), body)

    def test_niu_page_includes_the_sheet_card_success(self) -> None:
        self.assertIn('class="report-card"', self.niu)
        self.assertIn('data-grade="C-"', self.niu)
        self.assertIn('data-grade="F"', self.niu)
        self.assertIn(report_gpa("C-", "D", "F") or "", self.niu)
        thanks = self.niu.find("Thank you, Northern Illinois")
        self.assertGreater(thanks, 0)
        self.assertGreater(self.niu.find('class="report-card"'), thanks)


if __name__ == "__main__":
    unittest.main()
