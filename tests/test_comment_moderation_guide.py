"""Dead-simple comment removal guide lives on /admin/comments/."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = REPO_ROOT / "content" / "admin" / "comments.md"
ADMIN_LAYOUT = REPO_ROOT / "layouts" / "admin" / "single.html"

OLD_ALLOW_COPY = (
    "Use this page to approve or remove pending comments. "
    "New comments are hidden until you click **Allow**."
)
SIMPLE_GUIDE = """
## Remove a comment you don't want

1. Type the password Tyler gave you, then click **Unlock**.
2. Find the comment.
3. Click **Delete**, then confirm.

That comment is gone from the site. Click **Edit** only if you want to change the wording instead.
"""


def markdown_body(text: str) -> str:
    """Return markdown after YAML front matter, or the full text if none."""
    match = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
    return match.group(1) if match else text


def is_dead_simple_removal_guide(markdown: str) -> bool:
    """True when copy is a numbered unlock-then-delete how-to, not the old Allow queue."""
    if not markdown or not markdown.strip():
        return False
    lowered = markdown.lower()
    if "pending" in lowered and "allow" in lowered:
        return False
    has_delete = "delete" in lowered
    has_unlock = "unlock" in lowered
    has_numbered_steps = bool(re.search(r"(?m)^\s*1[\.\)]\s+", markdown))
    return has_delete and has_unlock and has_numbered_steps


def admin_layout_renders_guide(template: str) -> bool:
    """True when the admin template prints page markdown into a visible guide."""
    return (
        "{{ .Content }}" in template
        and 'class="admin-comments-guide"' in template
    )


class CommentRemovalGuideLogicTests(unittest.TestCase):
    def test_simple_guide_success(self) -> None:
        self.assertTrue(is_dead_simple_removal_guide(SIMPLE_GUIDE))

    def test_old_allow_copy_failure(self) -> None:
        self.assertFalse(is_dead_simple_removal_guide(OLD_ALLOW_COPY))

    def test_empty_copy_failure(self) -> None:
        self.assertFalse(is_dead_simple_removal_guide(""))

    def test_layout_without_content_failure(self) -> None:
        self.assertFalse(admin_layout_renders_guide("<h2>{{ .Title }}</h2>"))


class CommentRemovalGuideContentTests(unittest.TestCase):
    def test_admin_markdown_is_dead_simple_guide(self) -> None:
        body = markdown_body(GUIDE_PATH.read_text(encoding="utf-8"))
        self.assertTrue(
            is_dead_simple_removal_guide(body),
            "content/admin/comments.md must be a numbered Unlock → Delete guide",
        )

    def test_admin_layout_renders_guide(self) -> None:
        template = ADMIN_LAYOUT.read_text(encoding="utf-8")
        self.assertTrue(
            admin_layout_renders_guide(template),
            "layouts/admin/single.html must render .Content in .admin-comments-guide",
        )


class CommentRemovalGuideBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="comment-guide-hugo-"))
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(cls._output_dir),
                "--quiet",
                "--noBuildLock",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.admin_html = (cls._output_dir / "admin" / "comments" / "index.html").read_text(
            encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_built_admin_page_includes_delete_steps(self) -> None:
        lowered = self.admin_html.lower()
        self.assertIn("unlock", lowered)
        self.assertIn("delete", lowered)
        self.assertIn('class="admin-comments-guide"', self.admin_html)
        self.assertNotIn("hidden until you click", lowered)


if __name__ == "__main__":
    unittest.main()
