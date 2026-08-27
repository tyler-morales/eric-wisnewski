"""Grady's travel posts live in content/gradys-tour/ and list on /gradys-tour/."""

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
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
HUGO_TIMEOUT_SECONDS = 120
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
TITLE_RE = re.compile(r'class="post-list-title"[^>]*>(.*?)</(?:span|a)>', re.DOTALL)
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _normalized_relpath(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix().lower()


def parse_simple_front_matter(path: Path) -> dict[str, str]:
    """Parse top-level YAML scalars from a Hugo markdown file."""
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


def tour_markdown() -> list[tuple[Path, dict[str, str]]]:
    """Return every Grady's Tour post file (including drafts), excluding _index.md."""
    posts: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(TOUR_SECTION_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        posts.append((path, parse_simple_front_matter(path)))
    return posts


def published_tour_markdown() -> list[tuple[Path, dict[str, str]]]:
    """Return Grady's Tour posts that should appear on the live /gradys-tour/ list."""
    return [
        (path, front_matter)
        for path, front_matter in tour_markdown()
        if front_matter.get("draft", "false").lower() != "true"
    ]


def tour_titles(posts: list[tuple[Path, dict[str, str]]]) -> set[str]:
    return {front_matter["title"] for _, front_matter in posts if "title" in front_matter}


def is_gradys_tour_content(path: Path) -> bool:
    """True when a markdown file lives in the Grady's Tour content folder.

    Also matches the old CMS folder `content/posts/Grady's Tour/` so a
    regression there fails tests instead of leaking onto the home page.
    """
    rel = _normalized_relpath(path)
    return "/gradys-tour/" in rel or "/grady's tour/" in rel


def post_list_titles(html: str) -> list[str]:
    match = POST_LIST_RE.search(html)
    if not match:
        return []
    return [re.sub(r"\s+", " ", title).strip() for title in TITLE_RE.findall(match.group(1))]


def run_hugo(*, destination: Path, content_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = ["hugo", "--destination", str(destination), "--quiet"]
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


def build_tour_titles_with_extra_post(front_matter: str, filename: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="gradys-tour-fixture-") as tmp:
        tmp_path = Path(tmp)
        content_dir = tmp_path / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "gradys-tour" / filename).write_text(front_matter, encoding="utf-8")
        dest = tmp_path / "public"
        result = run_hugo(destination=dest, content_dir=content_dir)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "hugo build failed")
        return post_list_titles((dest / "gradys-tour" / "index.html").read_text(encoding="utf-8"))


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

    def test_home_template_lists_posts_and_tour_when_home(self) -> None:
        list_template = (REPO_ROOT / "layouts" / "_default" / "list.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(".IsHome", list_template)
        self.assertIn('"posts"', list_template)
        self.assertIn('"gradys-tour"', list_template)

    def test_tour_template_lists_section_pages_only(self) -> None:
        tour_template = (REPO_ROOT / "layouts" / "_default" / "section-list.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(".RegularPages", tour_template)
        self.assertIn("section-empty", tour_template)
        self.assertNotIn('Section" "posts"', tour_template)

    def test_hugo_publishes_future_dated_content(self) -> None:
        hugo_toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertRegex(
            hugo_toml,
            r"(?m)^buildFuture\s*=\s*true\s*$",
            "CMS dates are stored with a literal Z and are often slightly in the "
            "future at deploy time; Hugo must still publish those posts",
        )

    def test_published_tour_slugs_match_lowercase_filenames(self) -> None:
        mismatches: list[str] = []
        for path, front_matter in published_tour_markdown():
            slug = front_matter.get("slug", "")
            expected = path.stem
            if slug != expected or slug != slug.lower():
                mismatches.append(f"{path.name}: slug={slug!r} expected={expected!r}")
        self.assertEqual(
            mismatches,
            [],
            "Published Grady's Tour slugs must be lowercase and match the filename",
        )

    def test_parse_simple_front_matter_success(self) -> None:
        front_matter = parse_simple_front_matter(TOUR_SECTION_DIR / "gearing-up.md")
        self.assertEqual(front_matter.get("title"), "From boat to bike")

    def test_parse_simple_front_matter_failure(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as handle:
            handle.write("no front matter here\n")
            path = Path(handle.name)
        try:
            self.assertEqual(parse_simple_front_matter(path), {})
        finally:
            path.unlink(missing_ok=True)


class GradyTourBuildIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="gradys-tour-hugo-"))
        result = run_hugo(destination=cls._output_dir)
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

    def test_home_post_list_includes_published_tour_posts(self) -> None:
        missing = tour_titles(published_tour_markdown()) - set(post_list_titles(self.home_html))
        self.assertEqual(
            missing,
            set(),
            f"Home list omitted published Grady's Tour posts: {missing}",
        )

    def test_tour_page_lists_every_published_post(self) -> None:
        titles = post_list_titles(self.tour_html)
        missing = tour_titles(published_tour_markdown()) - set(titles)
        self.assertEqual(
            missing,
            set(),
            f"Published Grady's Tour markdown did not appear on /gradys-tour/: {missing}",
        )

    def test_tour_page_excludes_drafts(self) -> None:
        titles = {title.lower() for title in post_list_titles(self.tour_html)}
        draft_titles = {
            front_matter["title"].lower()
            for _, front_matter in tour_markdown()
            if front_matter.get("draft", "false").lower() == "true" and "title" in front_matter
        }
        leaked_drafts = draft_titles & titles
        self.assertEqual(
            leaked_drafts,
            set(),
            f"Draft tour posts appeared on the live Grady's Tour list: {leaked_drafts}",
        )

    def test_tour_page_does_not_list_non_tour_posts(self) -> None:
        tour_titles_on_page = set(post_list_titles(self.tour_html))
        self.assertNotIn("An Introduction", tour_titles_on_page)
        self.assertTrue(tour_titles_on_page, "Grady's Tour list was empty")


class GradyTourFuturePublishTests(unittest.TestCase):
    def test_future_dated_published_tour_post_is_listed(self) -> None:
        titles = build_tour_titles_with_extra_post(
            "---\n"
            "title: Future Fixture Post\n"
            "slug: future-fixture\n"
            "author: grady-davis\n"
            "date: 2099-01-01T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            "Fixture body.\n",
            "future-fixture.md",
        )
        self.assertIn(
            "Future Fixture Post",
            titles,
            f"Future-dated published tour post was omitted from the list: {titles}",
        )

    def test_draft_tour_post_is_not_listed(self) -> None:
        titles = build_tour_titles_with_extra_post(
            "---\n"
            "title: Draft Fixture Post\n"
            "slug: draft-fixture\n"
            "author: grady-davis\n"
            "date: 2026-01-01T00:00:00Z\n"
            "draft: true\n"
            "---\n"
            "Fixture body.\n",
            "draft-fixture.md",
        )
        self.assertNotIn(
            "Draft Fixture Post",
            titles,
            f"Draft tour post leaked onto the live list: {titles}",
        )


if __name__ == "__main__":
    unittest.main()
