"""Post writers get email when someone comments on their post."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
README = REPO_ROOT / "README.md"
PRIVACY = REPO_ROOT / "content" / "privacy.md"
DEV_VARS = REPO_ROOT / ".dev.vars.example"


def call_comments_api(fn_name: str, *args: object) -> object:
    arg_list = ", ".join(json.dumps(a) for a in args)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(COMMENTS_API.as_uri())};\n"
        f"const result = {fn_name}({arg_list});\n"
        "Promise.resolve(result).then((v) => console.log(JSON.stringify(v)));\n"
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


class CommentListIdTests(unittest.TestCase):
    def test_comment_list_id_from_section_path_success(self) -> None:
        self.assertEqual(call_comments_api("commentListId", "/posts/hello/"), "posts")
        self.assertEqual(call_comments_api("commentListId", "/gradys-tour/day-1/"), "gradys-tour")
        self.assertEqual(
            call_comments_api("commentListId", "/da-breakdown-w-tad/week-1/"),
            "da-breakdown-w-tad",
        )
        self.assertEqual(
            call_comments_api("commentListId", "/posts/gradys-tour/day-1/"),
            "gradys-tour",
        )

    def test_comment_list_id_skips_non_posts_failure(self) -> None:
        self.assertEqual(call_comments_api("commentListId", "/privacy/"), "")
        self.assertEqual(call_comments_api("commentListId", "/"), "")
        self.assertEqual(call_comments_api("commentListId", ""), "")


class WriterNotifyToTests(unittest.TestCase):
    def test_writer_notify_to_reads_section_env_success(self) -> None:
        env = {
            "WRITER_EMAIL_POSTS": " eric@example.com ",
            "WRITER_EMAIL_GRADYS_TOUR": "grady@example.com",
            "WRITER_EMAIL_DA_BREAKDOWN_W_TAD": "tad@example.com",
        }
        self.assertEqual(call_comments_api("writerNotifyTo", "posts", env, "pat@x.co"), "eric@example.com")
        self.assertEqual(
            call_comments_api("writerNotifyTo", "gradys-tour", env, ""),
            "grady@example.com",
        )
        self.assertEqual(
            call_comments_api("writerNotifyTo", "da-breakdown-w-tad", env, "other@x.co"),
            "tad@example.com",
        )

    def test_writer_notify_to_skips_self_and_junk_failure(self) -> None:
        env = {"WRITER_EMAIL_POSTS": "eric@example.com"}
        self.assertEqual(call_comments_api("writerNotifyTo", "posts", env, "Eric@Example.com"), "")
        self.assertEqual(call_comments_api("writerNotifyTo", "posts", {"WRITER_EMAIL_POSTS": "nope"}, ""), "")
        self.assertEqual(call_comments_api("writerNotifyTo", "posts", {}, "pat@x.co"), "")
        self.assertEqual(call_comments_api("writerNotifyTo", "", env, "pat@x.co"), "")


class WriterNotifyEmailTests(unittest.TestCase):
    def test_writer_notify_email_includes_comment_and_link_success(self) -> None:
        mail = call_comments_api(
            "writerNotifyEmail",
            {
                "commentAuthor": "Pat",
                "commentText": "Great post.",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        self.assertEqual(mail["subject"], "Pat commented on your post")
        self.assertIn("Great post.", mail["text"])
        self.assertIn("https://ericwisnewski.com/posts/hi/#comments", mail["html"])
        self.assertIn("Pat", mail["html"])

    def test_writer_notify_email_escapes_html_failure(self) -> None:
        mail = call_comments_api(
            "writerNotifyEmail",
            {
                "commentAuthor": "<script>",
                "commentText": "Hi <b>there</b>",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        self.assertNotIn("<script>", mail["html"])
        self.assertNotIn("<b>there</b>", mail["html"])


class WriterNotifyWiringTests(unittest.TestCase):
    def test_api_queues_writer_notice_with_reply_mail_success(self) -> None:
        api = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("writerNotifyTo", api)
        self.assertIn("writerNotifyEmail", api)
        self.assertIn("commentListId", api)
        self.assertIn("queueCommentEmail", api)
        self.assertIn("context.waitUntil", api)
        self.assertIn("await queueCommentEmail", api)
        self.assertIn("WRITER_EMAIL_", api)

    def test_writer_notice_skips_same_inbox_as_reply_failure(self) -> None:
        api = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("writerTo.toLowerCase()", api)
        self.assertIn("notifyTo", api)
        self.assertNotIn("sendParentReplyEmail", api)


class WriterNotifyDocsTests(unittest.TestCase):
    def test_docs_name_writer_env_vars_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        privacy = PRIVACY.read_text(encoding="utf-8")
        dev_vars = DEV_VARS.read_text(encoding="utf-8")
        self.assertIn("WRITER_EMAIL_POSTS", readme)
        self.assertIn("WRITER_EMAIL_GRADYS_TOUR", readme)
        self.assertIn("WRITER_EMAIL_POSTS", dev_vars)
        self.assertIn("emailed to the writer", privacy.lower())

    def test_docs_do_not_put_writer_email_in_client_failure(self) -> None:
        widget = (REPO_ROOT / "static" / "js" / "comments.js").read_text(encoding="utf-8")
        self.assertNotIn("WRITER_EMAIL", widget)
        self.assertNotIn("writerNotifyTo", widget)


if __name__ == "__main__":
    unittest.main()
