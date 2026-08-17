"""Grady's travel posts belong on /gradys-tour/, never on the home list."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOUR_SECTION_DIR = REPO_ROOT / "content" / "gradys-tour"
POSTS_DIR = REPO_ROOT / "content" / "posts"
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
TITLE_RE = re.compile(r'class="post-list-title">(.*?)</span>', re.DOTALL)


def _normalized_relpath(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix().lower()


def is_gradys_tour_content(path: Path) -> bool:
    """True when a markdown file lives in the Grady's Tour content folder.

    Also matches the old CMS folder `content/posts/Grady's Tour/` so a
    regression there fails tests instead of leaking onto the home page.
    """
    rel = _normalized_relpath(path)
    return "/gradys-tour/" in rel or "/grady's tour/" in rel


def is_gradys_tour_title(title: str) -> bool:
    lowered = title.lower()
    return "from boat to bike" in lowered or "how to use this blog (grady)" in lowered


def post_list_titles(html: str) -> list[str]:
    match = POST_LIST_RE.search(html)
    if not match:
        return []
    return [re.sub(r"\s+", " ", title).strip() for title in TITLE_RE.findall(match.group(1))]


class GradyTourFolderConventionTests(unittest.TestCase):
    def test_is_gradys_tour_content_success(self) -> None:
        self.assertTrue(is_gradys_tour_content(TOUR_SECTION_DIR / "gearing-up.md"))

    def test_is_gradys_tour_content_failure(self) -> None:
        self.assertFalse(is_gradys_tour_content(POSTS_DIR / "{{slug}}.md"))

    def test_tour_markdown_is_not_nested_under_posts(self) -> None:
        nested_under_posts = [
            path
            for path in POSTS_DIR.rglob("*.md")
            if is_gradys_tour_content(path)
        ]
        self.assertEqual(
            nested_under_posts,
            [],
            "Grady's Tour posts must live in content/gradys-tour/, not content/posts/",
        )
        self.assertTrue(TOUR_SECTION_DIR.is_dir(), "content/gradys-tour/ must exist")

    def test_home_template_does_not_list_tour_section(self) -> None:
        list_template = (REPO_ROOT / "layouts" / "_default" / "list.html").read_text(
            encoding="utf-8"
        )
        self.assertRegex(list_template, r'where\s+\S+\s+"Section"\s+"posts"')
        self.assertNotIn('"gradys-tour"', list_template)

    def test_tour_template_lists_section_pages_only(self) -> None:
        tour_template = (REPO_ROOT / "layouts" / "_default" / "gradys-tour.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(".RegularPages", tour_template)
        self.assertNotIn('Section" "posts"', tour_template)


class GradyTourBuildIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="gradys-tour-hugo-"))
        result = subprocess.run(
            [
                "hugo",
                "--buildDrafts",
                "--destination",
                str(cls._output_dir),
                "--quiet",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH and the site is valid:\n{result.stderr}"
            )
        cls.home_html = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.tour_html = (cls._output_dir / "gradys-tour" / "index.html").read_text(
            encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_home_post_list_excludes_tour_posts(self) -> None:
        titles = post_list_titles(self.home_html)
        self.assertFalse(
            any(is_gradys_tour_title(title) for title in titles),
            f"Home list included Grady's Tour posts: {titles}",
        )

    def test_tour_page_lists_folder_posts(self) -> None:
        titles = post_list_titles(self.tour_html)
        self.assertTrue(
            titles,
            "Grady's Tour page should list posts from content/gradys-tour/",
        )
        lowered = [title.lower() for title in titles]
        self.assertIn(
            "from boat to bike",
            lowered,
            f"Grady's Tour page missing travel posts: {titles}",
        )
        home_titles = post_list_titles(self.home_html)
        overlap = set(titles) & set(home_titles)
        self.assertEqual(overlap, set(), f"Posts appeared on both home and tour: {overlap}")


if __name__ == "__main__":
    unittest.main()
