"""Admin comments are grouped by post author, newest first."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = REPO_ROOT / "static" / "js" / "admin-comments.js"
ADMIN_LAYOUT = REPO_ROOT / "layouts" / "admin" / "single.html"
HUGO_TIMEOUT_SECONDS = 120

POST_INDEX = {
    "/posts/northern-illinois/": {
        "title": "Northern Illinois",
        "author": "Eric Wisnewski",
        "slug": "eric-wisnewski",
    },
    "/gradys-tour/day-5-6/": {
        "title": "Days 5–6",
        "author": "Grady Davis",
        "slug": "grady-davis",
    },
    "/da-breakdown-w-tad/intro/": {
        "title": "Intro",
        "author": "Tad",
        "slug": "tad",
    },
}

COMMENTS = [
    {
        "id": 1,
        "url": "/posts/northern-illinois/",
        "author": "Sam",
        "body": "old eric",
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": 2,
        "url": "/gradys-tour/day-5-6/",
        "author": "Lee",
        "body": "grady earlier",
        "created_at": "2026-08-01T00:00:00Z",
    },
    {
        "id": 3,
        "url": "/posts/northern-illinois/",
        "author": "Sam",
        "body": "new eric",
        "created_at": "2026-07-01T00:00:00Z",
    },
    {
        "id": 4,
        "url": "/posts/gone/",
        "author": "X",
        "body": "orphan",
        "created_at": "2026-06-01T00:00:00Z",
    },
    {
        "id": 5,
        "url": "/posts/gradys-tour/day-5-6/",
        "author": "Lee",
        "body": "grady newest",
        "created_at": "2026-08-02T00:00:00Z",
    },
]


def call_js_fn(fn_name: str, *args: object) -> object:
    if not ADMIN_JS.is_file():
        raise FileNotFoundError(ADMIN_JS)
    arg_list = ", ".join(json.dumps(a) for a in args)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(ADMIN_JS.as_uri())};\n"
        f"const result = {fn_name}({arg_list});\n"
        f"Promise.resolve(result).then((v) => console.log(JSON.stringify(v)));\n"
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


class OrganizeAdminCommentsTests(unittest.TestCase):
    def test_groups_by_author_newest_first_success(self) -> None:
        grouped = call_js_fn("organizeAdminComments", COMMENTS, POST_INDEX, "")
        slugs = [author["slug"] for author in grouped]
        self.assertEqual(slugs, ["grady-davis", "eric-wisnewski", ""])
        self.assertEqual(grouped[0]["name"], "Grady Davis")
        grady_posts = grouped[0]["posts"]
        self.assertEqual([post["url"] for post in grady_posts], ["/gradys-tour/day-5-6/"])
        self.assertEqual([c["id"] for c in grady_posts[0]["comments"]], [5, 2])
        eric_ids = [c["id"] for c in grouped[1]["posts"][0]["comments"]]
        self.assertEqual(eric_ids, [3, 1])
        self.assertEqual(grouped[2]["name"], "Other")
        self.assertEqual(grouped[2]["posts"][0]["url"], "/posts/gone/")

    def test_filter_keeps_one_author_success(self) -> None:
        grouped = call_js_fn(
            "organizeAdminComments", COMMENTS, POST_INDEX, "eric-wisnewski"
        )
        self.assertEqual([author["slug"] for author in grouped], ["eric-wisnewski"])
        self.assertEqual(grouped[0]["count"], 2)

    def test_empty_and_unknown_filter_failure(self) -> None:
        self.assertEqual(call_js_fn("organizeAdminComments", [], POST_INDEX, ""), [])
        self.assertEqual(
            call_js_fn("organizeAdminComments", COMMENTS, POST_INDEX, "no-such-author"),
            [],
        )

    def test_relocate_legacy_tour_url_success(self) -> None:
        self.assertEqual(
            call_js_fn("relocateCommentUrl", "/posts/gradys-tour/day-5-6/"),
            "/gradys-tour/day-5-6/",
        )

    def test_relocate_rejects_empty_failure(self) -> None:
        self.assertEqual(call_js_fn("relocateCommentUrl", ""), "")
        self.assertEqual(call_js_fn("relocateCommentUrl", None), "")


class AdminCommentsLayoutTests(unittest.TestCase):
    def test_layout_filters_by_author_and_imports_helper(self) -> None:
        template = ADMIN_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('id="admin-author-filter"', template)
        self.assertIn('name="admin-author-filter"', template)
        self.assertIn('id="admin-post-index"', template)
        self.assertIn('"/js/admin-comments.js"', template)
        self.assertIn('type="module"', template)
        self.assertNotIn('" /js/admin-comments.js"', template)
        self.assertNotIn("groupByUrl", template)
        self.assertNotIn("Object.keys(byUrl).sort()", template)


class AdminCommentsBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="admin-comments-hugo-"))
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
            timeout=HUGO_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.admin_html = (
            cls._output_dir / "admin" / "comments" / "index.html"
        ).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_built_page_has_author_filter_and_post_index(self) -> None:
        html = self.admin_html
        self.assertIn('id="admin-author-filter"', html)
        self.assertIn("Eric Wisnewski", html)
        self.assertIn("Grady Davis", html)
        self.assertIn('value="eric-wisnewski"', html)
        self.assertIn('value="grady-davis"', html)
        self.assertIn("/js/admin-comments.js", html)
        self.assertNotIn("%20/js/admin-comments.js", html)
        self.assertNotIn("/ /js/admin-comments.js", html)
        self.assertNotIn("groupByUrl", html)
        match = re.search(
            r'id="admin-post-index">(.*?)</script>', html, flags=re.S
        )
        self.assertIsNotNone(match, "admin-post-index JSON is missing")
        data = json.loads(match.group(1))
        self.assertIsInstance(data, dict, "post index must be a JSON object, not a string")
        self.assertIn("/posts/northern-illinois/", data)
        self.assertEqual(data["/posts/northern-illinois/"]["slug"], "eric-wisnewski")
        self.assertTrue(any(url.startswith("/gradys-tour/") for url in data))


if __name__ == "__main__":
    unittest.main()
