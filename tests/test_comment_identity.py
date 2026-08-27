"""Comment identity is remembered in the browser and replies stay self-contained."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENTS_WIDGET = REPO_ROOT / "static" / "js" / "comments.js"
COMMENTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "comments.html"


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
        self.assertIn("md5", html)
        self.assertIn("comments-identity-fields", html)
        self.assertIn("readIdentity", js)
        self.assertIn("writeIdentity", js)
        self.assertNotIn("authorInput.value = ''", js)
        self.assertNotIn("Enter your name in the form below", js)

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
        self.assertIn("WITH RECURSIVE tree(id)", api)
        self.assertNotIn("if (!isReply)", js)
        self.assertNotIn("Replies can only be to top-level comments", api)

    def test_api_no_longer_blocks_reply_to_reply_failure(self) -> None:
        api = (REPO_ROOT / "functions" / "api" / "comments.js").read_text(encoding="utf-8")
        self.assertNotIn("Replies can only be to top-level comments", api)
        self.assertNotIn("DELETE FROM comments WHERE id = ? OR parent_id = ?", api)
        self.assertIn("Parent comment not found", api)


if __name__ == "__main__":
    unittest.main()
