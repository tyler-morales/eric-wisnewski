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


if __name__ == "__main__":
    unittest.main()
