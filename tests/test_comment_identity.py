"""Comment identity is remembered in the browser and replies stay self-contained."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENTS_WIDGET = REPO_ROOT / "static" / "js" / "comments.js"
COMMENTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "comments.html"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
COMMENTS_CSS = REPO_ROOT / "assets" / "css" / "style.css"
REPLY_EMAIL_HINT = "We'll email you if someone replies — after you confirm that address."


def call_identity(fn_name: str, script_body: str) -> object:
    if not COMMENTS_WIDGET.is_file():
        raise FileNotFoundError(COMMENTS_WIDGET)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(COMMENTS_WIDGET.as_uri())};\n"
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


MEMORY_STORE = """
function memoryStore(initial) {
  const data = Object.assign({}, initial || {});
  return {
    getItem(key) { return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null; },
    setItem(key, value) { data[key] = String(value); },
    _data: data
  };
}
"""


class CommentIdentityHelperTests(unittest.TestCase):
    def test_write_then_read_identity_success(self) -> None:
        payload = call_identity(
            "writeIdentity, readIdentity",
            MEMORY_STORE
            + """
const store = memoryStore();
writeIdentity(store, '  Tyler  ', ' t@example.com ');
console.log(JSON.stringify(readIdentity(store)));
""",
        )
        self.assertEqual(payload, {"author": "Tyler", "email": "t@example.com"})

    def test_read_identity_empty_storage_failure(self) -> None:
        payload = call_identity(
            "readIdentity",
            MEMORY_STORE
            + """
console.log(JSON.stringify({
  empty: readIdentity(memoryStore()),
  missing: readIdentity(null)
}));
""",
        )
        self.assertEqual(payload["empty"], {"author": "", "email": ""})
        self.assertEqual(payload["missing"], {"author": "", "email": ""})

    def test_write_identity_ignores_blank_name_failure(self) -> None:
        payload = call_identity(
            "writeIdentity, readIdentity",
            MEMORY_STORE
            + """
const store = memoryStore({ comment_author: 'Kept' });
writeIdentity(store, '   ', 'new@example.com');
console.log(JSON.stringify(readIdentity(store)));
""",
        )
        self.assertEqual(payload["author"], "Kept")
        self.assertEqual(payload["email"], "new@example.com")

    def test_merge_identity_prefers_form_then_store_success(self) -> None:
        payload = call_identity(
            "mergeIdentity",
            """
console.log(JSON.stringify({
  form: mergeIdentity('Ada', '', { author: 'Stored', email: 's@example.com' }),
  stored: mergeIdentity('  ', '', { author: 'Stored', email: 's@example.com' })
}));
""",
        )
        self.assertEqual(payload["form"], {"author": "Ada", "email": "s@example.com"})
        self.assertEqual(payload["stored"], {"author": "Stored", "email": "s@example.com"})


def call_comments_api(fn_name: str, *args: object) -> object:
    if not COMMENTS_API.is_file():
        raise FileNotFoundError(COMMENTS_API)
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


class CommentReplyUxTests(unittest.TestCase):
    def test_reply_form_collects_name_inline_success(self) -> None:
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        html = COMMENTS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("comment-reply-author", js)
        self.assertIn("Replying as", js)
        self.assertIn("Leave a comment", html)
        self.assertIn("Post comment", html)
        self.assertIn('type="module"', html)
        self.assertIn("/js/comments.js", html)
        self.assertNotIn('" /js/comments.js"', html)
        self.assertIn("md5", html)
        self.assertIn("comments-identity-fields", html)
        self.assertIn("readIdentity", js)
        self.assertIn("writeIdentity", js)
        self.assertNotIn("authorInput.value = ''", js)
        self.assertNotIn("Enter your name in the form below", js)
        self.assertIn("JSON.stringify({ id: c.id, edit_token: token })", js)
        self.assertNotIn("&edit_token=", js)

    def test_reply_does_not_reuse_main_submit_label_failure(self) -> None:
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        self.assertIn("Reply</button>", js)
        self.assertNotIn("Post reply", js)
        self.assertNotIn("Join the discussion", COMMENTS_PARTIAL.read_text(encoding="utf-8"))

    def test_widget_import_does_not_require_document_success(self) -> None:
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                f"import {json.dumps(COMMENTS_WIDGET.as_uri())};\nconsole.log('ok');\n",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")


class CommentNestedThreadTests(unittest.TestCase):
    def test_build_thread_nests_reply_to_reply_success(self) -> None:
        payload = call_identity(
            "buildThread",
            """
const thread = buildThread([
  { id: 1, parent_id: null, created_at: '2026-01-01T00:00:00Z', author: 'Brian' },
  { id: 2, parent_id: 1, created_at: '2026-01-01T01:00:00Z', author: 'Grady' },
  { id: 3, parent_id: 2, created_at: '2026-01-01T02:00:00Z', author: 'Jack' }
]);
console.log(JSON.stringify({
  top: thread.top.map((c) => c.id),
  under1: (thread.byParent[1] || []).map((c) => c.id),
  under2: (thread.byParent[2] || []).map((c) => c.id)
}));
""",
        )
        self.assertEqual(payload["top"], [1])
        self.assertEqual(payload["under1"], [2])
        self.assertEqual(payload["under2"], [3])

    def test_build_thread_keeps_orphans_out_of_top_failure(self) -> None:
        payload = call_identity(
            "buildThread",
            """
const thread = buildThread([
  { id: 9, parent_id: 404, created_at: '2026-01-01T00:00:00Z', author: 'Lost' }
]);
console.log(JSON.stringify({
  top: thread.top.map((c) => c.id),
  under404: (thread.byParent[404] || []).map((c) => c.id)
}));
""",
        )
        self.assertEqual(payload["top"], [])
        self.assertEqual(payload["under404"], [9])

    def test_reply_is_offered_on_nested_comments_success(self) -> None:
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        api = (REPO_ROOT / "functions" / "api" / "comments.js").read_text(encoding="utf-8")
        self.assertIn("comment-reply-btn", js)
        self.assertIn("renderComment(r, true, thread", js)
        self.assertIn("setAttribute('role', 'list')", js)
        self.assertIn("WITH RECURSIVE tree(id)", api)
        self.assertIn("DELETE FROM comments WHERE id IN (SELECT id FROM tree)", api)
        self.assertNotIn("if (!isReply)", js)
        self.assertNotIn("Replies can only be to top-level comments", api)

    def test_api_no_longer_blocks_reply_to_reply_failure(self) -> None:
        api = COMMENTS_API.read_text(encoding="utf-8")
        self.assertNotIn("Replies can only be to top-level comments", api)
        self.assertNotIn("DELETE FROM comments WHERE id = ? OR parent_id = ?", api)
        self.assertIn("Parent comment not found", api)

    def test_nested_replies_share_parent_width_success(self) -> None:
        css = COMMENTS_CSS.read_text(encoding="utf-8")
        start = css.find("#comments .comment-replies {")
        self.assertNotEqual(start, -1)
        first_list = css[start : css.find("}", start)]
        self.assertIn("grid-column: 2", first_list)
        self.assertIn(
            "#comments .comment-replies .comment-replies {\n  grid-column: 1 / -1;\n}",
            css,
        )
        mobile = css.split("@media (max-width: 768px)", 1)[-1]
        flatten = mobile.split("#comments .comment-replies .comment-replies", 1)[1][:180]
        self.assertIn("padding-left: 0", flatten)
        self.assertIn("border-left: 0", flatten)

    def test_replies_do_not_compound_avatar_columns_failure(self) -> None:
        css = COMMENTS_CSS.read_text(encoding="utf-8")
        reply_item = css[
            css.find("#comments .comment-reply {") : css.find("}", css.find("#comments .comment-reply {"))
        ]
        self.assertNotIn("margin-left:", reply_item)
        self.assertNotIn(
            "#comments .comment-replies .comment-replies .comment-replies .comment-replies",
            css,
        )


class CommentReplyEmailHintTests(unittest.TestCase):
    def test_email_field_explains_reply_notice_success(self) -> None:
        html = COMMENTS_PARTIAL.read_text(encoding="utf-8")
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        css = COMMENTS_CSS.read_text(encoding="utf-8")
        self.assertIn(REPLY_EMAIL_HINT, html)
        self.assertIn(REPLY_EMAIL_HINT, js)
        self.assertIn('aria-describedby="comment-email-hint"', html)
        self.assertIn("comment-reply-email-hint", js)
        self.assertIn("comments-email-hint", css)
        self.assertIn("identity.author && identity.email", js)
        self.assertNotIn('required', html.split('id="comment-email"', 1)[1][:200])

    def test_email_stays_optional_failure(self) -> None:
        html = COMMENTS_PARTIAL.read_text(encoding="utf-8")
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        self.assertIn("comments-optional", html)
        self.assertIn("(optional)", html)
        self.assertIn("(optional)", js)
        self.assertNotIn("required", js.split('id="comment-reply-email"', 1)[1][:180])


class CommentReplyNotifyHelperTests(unittest.TestCase):
    def test_parent_reply_notify_to_success(self) -> None:
        self.assertEqual(
            call_comments_api("parentReplyNotifyTo", " Pat@Example.com ", "other@example.com", True),
            "Pat@Example.com",
        )

    def test_parent_reply_notify_to_skips_self_and_junk_failure(self) -> None:
        self.assertEqual(call_comments_api("parentReplyNotifyTo", "a@b.co", "A@B.co", True), "")
        self.assertEqual(call_comments_api("parentReplyNotifyTo", "not-an-email", "b@c.co", True), "")
        self.assertEqual(call_comments_api("parentReplyNotifyTo", "", "b@c.co", True), "")
        self.assertEqual(call_comments_api("parentReplyNotifyTo", "a@b.co\nbad@c.co", "d@e.co", True), "")
        self.assertEqual(
            call_comments_api("parentReplyNotifyTo", "a@b.co", "other@example.com", False),
            "",
        )
        self.assertEqual(
            call_comments_api("parentReplyNotifyTo", "a@b.co", "other@example.com"),
            "",
        )

    def test_reply_notify_email_includes_reply_and_link_success(self) -> None:
        mail = call_comments_api(
            "replyNotifyEmail",
            {
                "parentAuthor": "Pat",
                "replyAuthor": "Grady",
                "replyText": "See you at 6.",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        self.assertEqual(mail["subject"], "Grady replied to your comment")
        self.assertIn("See you at 6.", mail["text"])
        self.assertIn("https://ericwisnewski.com/posts/hi/#comments", mail["html"])
        self.assertIn("Grady", mail["html"])

    def test_reply_notify_email_escapes_html_failure(self) -> None:
        mail = call_comments_api(
            "replyNotifyEmail",
            {
                "parentAuthor": "Pat",
                "replyAuthor": "<script>",
                "replyText": "Hi <b>there</b>",
                "postUrl": "https://ericwisnewski.com/posts/hi/#comments",
            },
        )
        self.assertNotIn("<script>", mail["html"])
        self.assertNotIn("<b>there</b>", mail["html"])
    def test_confirm_comment_email_requires_click_success(self) -> None:
        mail = call_comments_api(
            "confirmCommentEmailBody",
            "https://ericwisnewski.com",
            "ab" * 24,
        )
        self.assertIn("/api/comments?confirm=", mail["text"])
        self.assertIn("We won't send reply emails until you click", mail["html"])

    def test_confirm_comment_email_omits_tokens_in_copy_failure(self) -> None:
        mail = call_comments_api(
            "confirmCommentEmailBody",
            "https://ericwisnewski.com",
            "ab" * 24,
        )
        self.assertNotIn("edit_token", mail["html"])
        self.assertNotIn("You're already", mail["text"])

    def test_api_sends_reply_notice_in_background_success(self) -> None:
        api = COMMENTS_API.read_text(encoding="utf-8")
        self.assertIn("parentReplyNotifyTo", api)
        self.assertIn("sendResendEmail", api)
        self.assertIn("context.waitUntil", api)
        self.assertIn("email_confirmed_at", api)
        self.assertIn("UPDATE comments SET author = ? WHERE id = ?", api)
        self.assertNotIn("UPDATE comments SET author = ? WHERE email = ?", api)
        self.assertIn("confirmCommentEmailBody", api)
        self.assertNotIn("searchParams.get('admin_secret')", api)
        self.assertNotIn("searchParams.get('edit_token')", api)


if __name__ == "__main__":
    unittest.main()
