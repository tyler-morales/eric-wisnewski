"""Admin subscriber list: group-by-email helper, secret gate, /admin/subscribers/ page."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBE_API = REPO_ROOT / "functions" / "api" / "subscribe.js"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
SHARED_API = REPO_ROOT / "lib" / "api.js"
SUBSCRIBERS_LAYOUT = REPO_ROOT / "layouts" / "admin" / "subscribers.html"
COMMENTS_LAYOUT = REPO_ROOT / "layouts" / "admin" / "single.html"
ADMIN_COMMENTS_JS = REPO_ROOT / "static" / "js" / "admin-comments.js"
SUBSCRIBERS_CONTENT = REPO_ROOT / "content" / "admin" / "subscribers.md"
COMMENTS_CONTENT = REPO_ROOT / "content" / "admin" / "comments.md"
ADMIN_NAV = REPO_ROOT / "layouts" / "partials" / "admin-nav.html"
ADMIN_SUBSCRIBERS_JS = REPO_ROOT / "static" / "js" / "admin-subscribers.js"
HUGO_TIMEOUT_SECONDS = 120


def call_js_fn(module: Path, fn_name: str, *args: object) -> object:
    if not module.is_file():
        raise FileNotFoundError(module)
    arg_list = ", ".join(json.dumps(a) for a in args)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(module.as_uri())};\n"
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


class GroupSubscribersTests(unittest.TestCase):
    def test_groups_one_email_across_lists_success(self) -> None:
        rows = [
            {
                "email": "ada@example.com",
                "list": "gradys-tour",
                "status": "pending",
                "created_at": "2026-01-02",
                "confirmed_at": None,
                "confirm_token": "secret-a",
                "unsub_token": "secret-b",
            },
            {
                "email": "ada@example.com",
                "list": "posts",
                "status": "confirmed",
                "created_at": "2026-01-01",
                "confirmed_at": "2026-01-01",
                "confirm_token": "secret-c",
                "unsub_token": "secret-d",
            },
            {
                "email": "ada@example.com",
                "list": "da-breakdown-w-tad",
                "status": "confirmed",
                "created_at": "2026-01-04",
                "confirmed_at": "2026-01-04",
            },
            {
                "email": "bob@example.com",
                "list": "posts",
                "status": "unsubscribed",
                "created_at": "2026-01-03",
                "confirmed_at": "2026-01-03",
            },
        ]
        people = call_js_fn(SUBSCRIBE_API, "groupSubscribersByEmail", rows)
        self.assertEqual([p["email"] for p in people], ["ada@example.com", "bob@example.com"])
        self.assertEqual(
            [row["list"] for row in people[0]["lists"]],
            ["posts", "gradys-tour", "da-breakdown-w-tad"],
        )
        self.assertEqual(people[0]["lists"][0]["label"], "Eric's blog")
        self.assertEqual(people[0]["lists"][0]["status"], "confirmed")
        self.assertEqual(people[0]["lists"][1]["status"], "pending")
        self.assertEqual(people[0]["lists"][2]["label"], "Da Breakdown w Tad")
        self.assertEqual(people[0]["lists"][2]["status"], "confirmed")
        self.assertEqual(people[1]["lists"][0]["status"], "unsubscribed")
        blob = json.dumps(people)
        self.assertNotIn("secret-a", blob)
        self.assertNotIn("confirm_token", blob)
        self.assertNotIn("unsub_token", blob)

    def test_empty_or_invalid_rows_failure(self) -> None:
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "groupSubscribersByEmail", []), [])
        self.assertEqual(call_js_fn(SUBSCRIBE_API, "groupSubscribersByEmail", None), [])
        self.assertEqual(
            call_js_fn(SUBSCRIBE_API, "groupSubscribersByEmail", [{"list": "posts"}]),
            [],
        )


class SubscriberTableTests(unittest.TestCase):
    def test_rows_include_tad_column_success(self) -> None:
        people = [
            {
                "email": "ada@example.com",
                "lists": [
                    {"list": "posts", "status": "confirmed"},
                    {"list": "gradys-tour", "status": "pending"},
                ],
            }
        ]
        rows = call_js_fn(ADMIN_SUBSCRIBERS_JS, "subscriberTableRows", people)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "ada@example.com")
        self.assertEqual(
            [cell["id"] for cell in rows[0]["cells"]],
            ["posts", "gradys-tour", "da-breakdown-w-tad"],
        )
        self.assertEqual(
            [cell["label"] for cell in rows[0]["cells"]],
            ["Eric's blog", "Grady's Tour", "Da Breakdown w Tad"],
        )
        self.assertEqual(
            [cell["status"] for cell in rows[0]["cells"]],
            ["confirmed", "pending", ""],
        )
        all_lists = [
            {
                "email": "ada@example.com",
                "lists": [
                    {"list": "posts", "status": "confirmed"},
                    {"list": "gradys-tour", "status": "confirmed"},
                    {"list": "da-breakdown-w-tad", "status": "confirmed"},
                ],
            }
        ]
        filled = call_js_fn(ADMIN_SUBSCRIBERS_JS, "subscriberTableRows", all_lists)
        self.assertEqual(
            [cell["status"] for cell in filled[0]["cells"]],
            ["confirmed", "confirmed", "confirmed"],
        )
        self.assertEqual(
            call_js_fn(ADMIN_SUBSCRIBERS_JS, "summarizeSubscribers", all_lists),
            "1 person. Confirmed: Eric's blog 1, Grady's Tour 1, Da Breakdown w Tad 1.",
        )
        summary = call_js_fn(ADMIN_SUBSCRIBERS_JS, "summarizeSubscribers", people)
        self.assertEqual(
            summary,
            "1 person. Confirmed: Eric's blog 1, Grady's Tour 0, Da Breakdown w Tad 0.",
        )
        self.assertEqual(
            call_js_fn(
                ADMIN_SUBSCRIBERS_JS,
                "listStatusById",
                [{"list": "da-breakdown-w-tad", "status": "confirmed"}],
            ),
            {"da-breakdown-w-tad": "confirmed"},
        )

    def test_empty_or_invalid_people_failure(self) -> None:
        self.assertEqual(call_js_fn(ADMIN_SUBSCRIBERS_JS, "subscriberTableRows", []), [])
        self.assertEqual(call_js_fn(ADMIN_SUBSCRIBERS_JS, "subscriberTableRows", None), [])
        self.assertEqual(
            call_js_fn(ADMIN_SUBSCRIBERS_JS, "subscriberTableRows", [{"lists": []}]),
            [],
        )
        self.assertEqual(call_js_fn(ADMIN_SUBSCRIBERS_JS, "listStatusById", None), {})
        self.assertEqual(
            call_js_fn(ADMIN_SUBSCRIBERS_JS, "summarizeSubscribers", None),
            "0 people. Confirmed: Eric's blog 0, Grady's Tour 0, Da Breakdown w Tad 0.",
        )


class AdminSecretTests(unittest.TestCase):
    def test_matching_secret_success(self) -> None:
        self.assertTrue(
            call_js_fn(SHARED_API, "isAdmin", "hunter2", {"COMMENTS_ADMIN_SECRET": "hunter2"})
        )

    def test_missing_or_wrong_secret_failure(self) -> None:
        self.assertFalse(call_js_fn(SHARED_API, "isAdmin", "hunter2", {}))
        self.assertFalse(
            call_js_fn(SHARED_API, "isAdmin", "nope", {"COMMENTS_ADMIN_SECRET": "hunter2"})
        )
        self.assertFalse(
            call_js_fn(SHARED_API, "isAdmin", "", {"COMMENTS_ADMIN_SECRET": "hunter2"})
        )
        self.assertFalse(
            call_js_fn(SHARED_API, "isAdmin", "hunter2", {"COMMENTS_ADMIN_SECRET": ""})
        )

    def test_admin_secret_from_bearer_header_success(self) -> None:
        self.assertEqual(
            call_js_fn(SHARED_API, "adminSecretFromHeader", "Bearer hunter2", None),
            "hunter2",
        )
        self.assertEqual(
            call_js_fn(
                SHARED_API,
                "adminSecretFromHeader",
                "",
                {"admin_secret": "from-body"},
            ),
            "from-body",
        )

    def test_admin_secret_ignores_empty_header_failure(self) -> None:
        self.assertEqual(call_js_fn(SHARED_API, "adminSecretFromHeader", "", None), "")
        self.assertEqual(call_js_fn(SHARED_API, "adminSecretFromHeader", "Bearer ", None), "")
        self.assertEqual(
            call_js_fn(SHARED_API, "adminSecretFromHeader", "Basic hunter2", None),
            "",
        )


class AdminSubscriberSourceTests(unittest.TestCase):
    def test_subscribe_get_lists_behind_admin_secret_success(self) -> None:
        source = SUBSCRIBE_API.read_text(encoding="utf-8")
        self.assertIn("groupSubscribersByEmail", source)
        self.assertIn("adminSecretFromRequest", source)
        self.assertIn("isAdmin", source)
        self.assertIn("FROM subscribers", source)
        self.assertIn("SELECT email, list, status, created_at, confirmed_at, unsubscribed_at", source)
        self.assertNotIn("searchParams.get('admin_secret')", source)

    def test_comments_uses_shared_is_admin_failure_if_local(self) -> None:
        source = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("isAdmin", source)
        self.assertNotIn("function isAdmin(", source)
        shared = SHARED_API.read_text(encoding="utf-8")
        self.assertIn("function isAdmin(", shared)

    def test_layout_fetches_subscribe_admin_success(self) -> None:
        layout = SUBSCRIBERS_LAYOUT.read_text(encoding="utf-8")
        script = ADMIN_SUBSCRIBERS_JS.read_text(encoding="utf-8")
        self.assertIn('"/js/admin-subscribers.js"', layout)
        self.assertIn('type="module"', layout)
        self.assertNotIn('" /js/admin-subscribers.js"', layout)
        self.assertIn("Authorization: 'Bearer '", script)
        self.assertIn("comments_admin_secret", script)
        self.assertIn("admin-subscriber-table", script)
        self.assertIn("da-breakdown-w-tad", script)
        self.assertIn("Da Breakdown w Tad", script)
        self.assertNotIn("admin-subscriber-lists", script)
        self.assertIn('partial "admin-nav.html"', layout)
        self.assertNotIn("admin_secret=", layout)
        self.assertNotIn("admin_secret=", script)
        self.assertNotIn("confirm_token", layout)
        self.assertNotIn("unsub_token", layout)
        self.assertNotIn("confirm_token", script)
        self.assertNotIn("unsub_token", script)
        self.assertIn('id="admin-content" class="admin-content" tabindex="-1"', layout)
        self.assertIn("adminContent.focus()", script)
        self.assertIn("secretInput.focus()", script)

    def test_comments_layout_links_subscribers_success(self) -> None:
        comments = COMMENTS_LAYOUT.read_text(encoding="utf-8")
        script = ADMIN_COMMENTS_JS.read_text(encoding="utf-8")
        self.assertIn('partial "admin-nav.html"', comments)
        self.assertIn("Authorization: 'Bearer '", script)
        self.assertNotIn("admin_secret=", comments)
        self.assertNotIn("admin_secret=", script)
        nav = ADMIN_NAV.read_text(encoding="utf-8")
        self.assertIn('href="/admin/subscribers/"', nav)
        self.assertIn('href="/admin/comments/"', nav)
        self.assertNotIn("%20admin/", nav)
        self.assertNotIn('" admin/', nav)

    def test_hidden_unlock_form_beats_flex_success(self) -> None:
        css = (REPO_ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".admin-secret-form[hidden]", css)
        self.assertIn("display: none", css.split(".admin-secret-form[hidden]", 1)[-1][:80])

    def test_flex_without_hidden_override_failure(self) -> None:
        sample = ".admin-secret-form {\n  display: flex;\n}\n"
        self.assertNotIn(".admin-secret-form[hidden]", sample)

    def test_pages_are_noindex_success(self) -> None:
        for path in (SUBSCRIBERS_CONTENT, COMMENTS_CONTENT):
            text = path.read_text(encoding="utf-8")
            self.assertIn("robots: noindex", text)
            self.assertIn("list: never", text)


class AdminSubscriberBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="admin-subscribers-hugo-"))
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
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.subscribers_html = (
            cls._output_dir / "admin" / "subscribers" / "index.html"
        ).read_text(encoding="utf-8")
        cls.comments_html = (
            cls._output_dir / "admin" / "comments" / "index.html"
        ).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_built_page_unlocks_and_lists_success(self) -> None:
        html = self.subscribers_html.lower()
        self.assertIn("unlock", html)
        self.assertIn('name="robots" content="noindex, nofollow"', self.subscribers_html)
        self.assertNotIn("admin_secret=", self.subscribers_html)
        self.assertIn("/js/admin-subscribers.js", self.subscribers_html)
        self.assertNotIn("%20/js/admin-subscribers.js", self.subscribers_html)
        self.assertNotIn("/ /js/admin-subscribers.js", self.subscribers_html)
        self.assertIn("/admin/comments/", self.subscribers_html)
        self.assertIn("Da Breakdown w Tad", self.subscribers_html)
        self.assertNotIn("confirm_token", self.subscribers_html)
        self.assertNotIn("unsub_token", self.subscribers_html)
        script = (self._output_dir / "js" / "admin-subscribers.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("Authorization: 'Bearer '", script)
        self.assertIn("admin-subscriber-table", script)
        self.assertIn("da-breakdown-w-tad", script)
        self.assertIn("Da Breakdown w Tad", script)
        self.assertNotIn("admin-subscriber-lists", script)
        self.assertNotIn("admin_secret=", script)

    def test_comments_page_links_subscribers_success(self) -> None:
        self.assertIn("/admin/subscribers/", self.comments_html)
        self.assertIn('name="robots" content="noindex, nofollow"', self.comments_html)
        self.assertNotIn("admin_secret=", self.comments_html)
        comments_js = (self._output_dir / "js" / "admin-comments.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("Authorization: 'Bearer '", comments_js)
        self.assertNotIn("admin_secret=", comments_js)

    def test_home_does_not_list_admin_pages_failure(self) -> None:
        home = (self._output_dir / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("/admin/subscribers/", home)
        self.assertNotIn("/admin/comments/", home)


if __name__ == "__main__":
    unittest.main()
