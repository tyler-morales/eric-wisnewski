"""Tour comments stay attached after posts move from /posts/ to /gradys-tour/."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENT_URLS_JS = REPO_ROOT / "functions" / "_lib" / "comment-urls.js"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
ADMIN_LAYOUT = REPO_ROOT / "layouts" / "admin" / "single.html"
ISSO_PARTIAL = REPO_ROOT / "layouts" / "partials" / "isso.html"
COMMENTS_WIDGET = REPO_ROOT / "static" / "js" / "comments.js"
REDIRECTS = REPO_ROOT / "static" / "_redirects"
GEARING_UP = REPO_ROOT / "content" / "gradys-tour" / "gearing-up.md"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"


def call_comment_url_fn(fn_name: str, arg: str | None) -> str | list[str]:
    """Run an exported helper from functions/_lib/comment-urls.js via Node."""
    if not COMMENT_URLS_JS.is_file():
        raise FileNotFoundError(COMMENT_URLS_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(COMMENT_URLS_JS.as_uri())};\n"
        f"console.log(JSON.stringify({fn_name}({json.dumps(arg)})));\n"
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


class RelocateCommentUrlTests(unittest.TestCase):
    def test_relocate_old_tour_post_path_success(self) -> None:
        self.assertEqual(
            call_comment_url_fn("relocateCommentUrl", "/posts/gradys-tour/gearing-up/"),
            "/gradys-tour/gearing-up/",
        )

    def test_relocate_eric_post_path_unchanged_failure_case(self) -> None:
        self.assertEqual(
            call_comment_url_fn("relocateCommentUrl", "/posts/my-first-post/"),
            "/posts/my-first-post/",
        )

    def test_relocate_rejects_empty_url(self) -> None:
        self.assertEqual(call_comment_url_fn("relocateCommentUrl", ""), "")
        self.assertEqual(call_comment_url_fn("relocateCommentUrl", None), "")

    def test_canonical_adds_trailing_slash_success(self) -> None:
        self.assertEqual(
            call_comment_url_fn("canonicalCommentUrl", "/gradys-tour/gearing-up"),
            "/gradys-tour/gearing-up/",
        )

    def test_canonical_rejects_non_path_failure_case(self) -> None:
        self.assertEqual(
            call_comment_url_fn("canonicalCommentUrl", "https://evil.example/"),
            "",
        )


class CommentUrlLookupVariantTests(unittest.TestCase):
    def test_live_tour_url_finds_legacy_posts_path_success(self) -> None:
        variants = call_comment_url_fn(
            "commentUrlLookupVariants", "/gradys-tour/gearing-up/"
        )
        self.assertIn("/gradys-tour/gearing-up/", variants)
        self.assertIn("/posts/gradys-tour/gearing-up/", variants)

    def test_eric_post_does_not_include_tour_paths_failure_case(self) -> None:
        variants = call_comment_url_fn(
            "commentUrlLookupVariants", "/posts/my-first-post/"
        )
        self.assertIn("/posts/my-first-post/", variants)
        self.assertNotIn("/gradys-tour/my-first-post/", variants)
        self.assertFalse(any("gradys-tour" in item for item in variants))


class CommentUrlWiringTests(unittest.TestCase):
    def test_api_imports_and_queries_url_variants(self) -> None:
        source = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("commentUrlLookupVariants", source)
        self.assertIn("relocateCommentUrl", source)
        self.assertIn("url IN (", source)

    def test_widget_uses_hugo_permalink_not_only_location(self) -> None:
        isso = ISSO_PARTIAL.read_text(encoding="utf-8")
        widget = COMMENTS_WIDGET.read_text(encoding="utf-8")
        self.assertIn("data-page-url", isso)
        self.assertIn(".RelPermalink", isso)
        self.assertIn("dataset.pageUrl", widget)

    def test_admin_links_use_live_post_url(self) -> None:
        template = ADMIN_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("relocateCommentUrl", template)
        self.assertIn("link.href = relocateCommentUrl", template)


class TourRedirectAndPermalinkTests(unittest.TestCase):
    def test_redirects_map_legacy_posts_tour_prefix(self) -> None:
        text = REDIRECTS.read_text(encoding="utf-8")
        self.assertIn("/posts/gradys-tour/", text)
        self.assertIn("/gradys-tour/", text)

    def test_gearing_up_keeps_legacy_alias(self) -> None:
        text = GEARING_UP.read_text(encoding="utf-8")
        self.assertIn("/posts/gradys-tour/gearing-up/", text)

    def test_permalinks_pin_author_sections(self) -> None:
        text = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIn("gradys-tour", text)
        self.assertRegex(text, r'posts\s*=\s*[\'"]/posts/:slug/')
        self.assertRegex(text, r'gradys-tour\s*=\s*[\'"]/gradys-tour/:slug/')


class TourPermalinkBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output_dir = Path(tempfile.mkdtemp(prefix="comment-url-hugo-"))
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(cls.output_dir),
                "--quiet",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            shutil.rmtree(cls.output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.output_dir, ignore_errors=True)

    def test_gearing_up_is_published_under_gradys_tour(self) -> None:
        live = self.output_dir / "gradys-tour" / "gearing-up" / "index.html"
        self.assertTrue(live.is_file(), f"missing live post at {live}")
        html = live.read_text(encoding="utf-8")
        self.assertIn('data-page-url="/gradys-tour/gearing-up/', html)

    def test_legacy_posts_tour_path_is_not_a_home_page(self) -> None:
        redirects = self.output_dir / "_redirects"
        self.assertTrue(redirects.is_file(), "static/_redirects must copy into the build")
        self.assertIn("/posts/gradys-tour/*", redirects.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
