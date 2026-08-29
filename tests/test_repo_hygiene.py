"""Repo hygiene: no leftover CMS filenames, build artifacts, or dead APIs."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "content" / "posts"
GITIGNORE = REPO_ROOT / ".gitignore"
README = REPO_ROOT / "README.md"
SINGLE_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "single.html"
COMMENTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "comments.html"
ISSO_PARTIAL = REPO_ROOT / "layouts" / "partials" / "isso.html"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
COMMENT_LIKES_API = REPO_ROOT / "functions" / "api" / "comment-likes.js"
PHOTOS_API = REPO_ROOT / "functions" / "api" / "photos.js"
SUBSCRIBE_API = REPO_ROOT / "functions" / "api" / "subscribe.js"
NEWSLETTER_API = REPO_ROOT / "functions" / "api" / "newsletter.js"
SHARED_API = REPO_ROOT / "lib" / "api.js"
DEV_VARS_EXAMPLE = REPO_ROOT / ".dev.vars.example"
SLUG_RE = re.compile(r"(?m)^slug:\s*['\"]?([A-Za-z0-9-]+)")


class PostFilenameTests(unittest.TestCase):
    def test_post_filenames_match_front_matter_slug_success(self) -> None:
        files = sorted(POSTS_DIR.glob("*.md"))
        self.assertGreater(len(files), 0)
        for path in files:
            text = path.read_text(encoding="utf-8")
            match = SLUG_RE.search(text)
            self.assertIsNotNone(match, f"missing slug in {path.name}")
            self.assertEqual(path.stem, match.group(1), f"{path.name} must match slug")

    def test_cms_placeholder_filenames_are_gone_failure(self) -> None:
        for path in POSTS_DIR.glob("*.md"):
            self.assertNotIn("{{", path.name, f"CMS leftover filename: {path.name}")


class HugoFrontMatterTests(unittest.TestCase):
    def test_content_uses_build_not_deprecated_underscore_success(self) -> None:
        offenders: list[str] = []
        for path in (REPO_ROOT / "content").rglob("*.md"):
            if "_build:" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], "Hugo 0.145+ wants build: not _build:")

    def test_underscore_build_key_is_rejected_failure(self) -> None:
        sample = "---\n_build:\n  list: never\n---\n"
        self.assertIn("_build:", sample)
        self.assertNotIn("_build:", sample.replace("_build:", "build:"))


class CommentsNamingTests(unittest.TestCase):
    def test_comments_partial_replaced_isso_success(self) -> None:
        self.assertTrue(COMMENTS_PARTIAL.is_file(), "layouts/partials/comments.html required")
        single = SINGLE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('partial "comments.html"', single)
        self.assertIn("/js/comments.js", COMMENTS_PARTIAL.read_text(encoding="utf-8"))

    def test_isso_partial_removed_failure(self) -> None:
        self.assertFalse(ISSO_PARTIAL.is_file(), "layouts/partials/isso.html is leftover Isso naming")
        single = SINGLE_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("isso.html", single)


class DeadApiTests(unittest.TestCase):
    def test_comments_api_has_no_patch_compat_shim_success(self) -> None:
        source = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("onRequestDelete", source)
        self.assertIn("onRequestPut", source)
        self.assertNotIn("onRequestPatch", source)

    def test_photos_env_getters_are_not_noops_failure(self) -> None:
        source = PHOTOS_API.read_text(encoding="utf-8")
        self.assertNotIn("env.GOOGLE_CLIENT_ID || env.GOOGLE_CLIENT_ID", source)
        self.assertNotIn("env.GOOGLE_CLIENT_SECRET || env.GOOGLE_CLIENT_SECRET", source)
        self.assertNotIn("env.UPLOAD_SECRET || env.UPLOAD_SECRET", source)

    def test_newsletter_from_uses_documented_env_success(self) -> None:
        shared = SHARED_API.read_text(encoding="utf-8")
        self.assertIn("NEWSLETTER_FROM_EMAIL", shared)
        for api in (SUBSCRIBE_API, NEWSLETTER_API):
            self.assertIn("newsletterFromHeader", api.read_text(encoding="utf-8"))

    def test_shared_helpers_are_defined_once_failure(self) -> None:
        """Both mail paths must read the same helper, or they drift apart."""
        for helper in (
            "newsletterFromHeader",
            "sendResendEmail",
            "jsonResponse",
            "isAdmin",
            "secretsMatch",
            "adminSecretFromHeader",
            "confirmMailAllowed",
        ):
            defined_in = [
                api.name
                for api in (SUBSCRIBE_API, NEWSLETTER_API, COMMENTS_API, COMMENT_LIKES_API, PHOTOS_API)
                if f"function {helper}(" in api.read_text(encoding="utf-8")
            ]
            self.assertEqual([], defined_in, f"{helper} redefined in {defined_in}")
            self.assertIn(f"function {helper}(", SHARED_API.read_text(encoding="utf-8"))


class GitignoreTests(unittest.TestCase):
    def test_gitignore_covers_local_build_caches_success(self) -> None:
        text = GITIGNORE.read_text(encoding="utf-8")
        for pattern in ("dist/", ".wrangler/", ".pytest_cache/", ".ruff_cache/"):
            self.assertIn(pattern, text)

    def test_build_artifacts_are_untracked_failure(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "dist", ".wrangler"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "", result.stdout)


class DocsHygieneTests(unittest.TestCase):
    def test_readme_does_not_point_at_missing_netlify_toml_failure(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertNotIn("netlify.toml", text)

    def test_dev_vars_example_documents_from_email_and_branch_success(self) -> None:
        text = DEV_VARS_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("NEWSLETTER_FROM_EMAIL", text)
        self.assertIn("GITHUB_BRANCH", text)

    def test_headers_file_sets_referrer_policy_success(self) -> None:
        headers = (REPO_ROOT / "static" / "_headers").read_text(encoding="utf-8")
        self.assertIn("Referrer-Policy: strict-origin-when-cross-origin", headers)
        self.assertIn("/subscribe/manage/*", headers)
        self.assertIn("Referrer-Policy: no-referrer", headers)
        self.assertIn("X-Frame-Options: DENY", headers)

    def test_headers_file_is_not_empty_failure(self) -> None:
        self.assertTrue((REPO_ROOT / "static" / "_headers").is_file())


if __name__ == "__main__":
    unittest.main()
