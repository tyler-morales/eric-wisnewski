"""Comment likes are a heart plus a count, one vote per browser."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENTS_WIDGET = REPO_ROOT / "static" / "js" / "comments.js"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
LIKES_API = REPO_ROOT / "functions" / "api" / "comment-likes.js"
SHARED_API = REPO_ROOT / "lib" / "api.js"
COMMENTS_CSS = REPO_ROOT / "assets" / "css" / "style.css"
MIGRATION = REPO_ROOT / "migrations" / "0006_comment_likes.sql"
README = REPO_ROOT / "README.md"
PRIVACY = REPO_ROOT / "content" / "privacy.md"
UUID = "11111111-1111-4111-8111-111111111111"


def call_js(module: Path, fn_name: str, script_body: str) -> object:
    if not module.is_file():
        raise FileNotFoundError(module)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(module.as_uri())};\n" + script_body
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


def call_fn(module: Path, fn_name: str, *args: object) -> object:
    arg_list = ", ".join(json.dumps(a) for a in args)
    return call_js(
        module,
        fn_name,
        f"const result = {fn_name}({arg_list});\n"
        "Promise.resolve(result).then((v) => console.log(JSON.stringify(v)));\n",
    )


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


class VisitorIdHelperTests(unittest.TestCase):
    def test_ensure_visitor_id_reuses_stored_success(self) -> None:
        payload = call_js(
            COMMENTS_WIDGET,
            "ensureVisitorId, readVisitorId",
            MEMORY_STORE
            + f"""
const store = memoryStore({{ comment_visitor_id: {json.dumps(UUID)} }});
const id = ensureVisitorId(store, () => 'should-not-run');
console.log(JSON.stringify({{ id, stored: readVisitorId(store) }}));
""",
        )
        self.assertEqual(payload["id"], UUID)
        self.assertEqual(payload["stored"], UUID)

    def test_ensure_visitor_id_mints_when_missing_failure(self) -> None:
        payload = call_js(
            COMMENTS_WIDGET,
            "ensureVisitorId, readVisitorId",
            MEMORY_STORE
            + f"""
const store = memoryStore();
const id = ensureVisitorId(store, () => {json.dumps(UUID)});
console.log(JSON.stringify({{ id, stored: readVisitorId(store), empty: readVisitorId(null) }}));
""",
        )
        self.assertEqual(payload["id"], UUID)
        self.assertEqual(payload["stored"], UUID)
        self.assertEqual(payload["empty"], "")


class LikeLabelHelperTests(unittest.TestCase):
    def test_like_aria_label_includes_count_success(self) -> None:
        self.assertEqual(
            call_fn(COMMENTS_WIDGET, "likeAriaLabel", False, 3),
            "Like this comment. 3 likes",
        )
        self.assertEqual(
            call_fn(COMMENTS_WIDGET, "likeAriaLabel", True, 1),
            "Unlike this comment. 1 like",
        )

    def test_like_aria_label_zero_and_junk_failure(self) -> None:
        self.assertEqual(
            call_fn(COMMENTS_WIDGET, "likeAriaLabel", False, 0),
            "Like this comment. 0 likes",
        )
        self.assertEqual(
            call_fn(COMMENTS_WIDGET, "likeAriaLabel", False, -4),
            "Like this comment. 0 likes",
        )


class LikeCountSlideTests(unittest.TestCase):
    def test_like_count_slide_direction_success(self) -> None:
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", 3, 4), "up")
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", 4, 3), "down")
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", "2", 3), "up")

    def test_like_count_slide_unchanged_failure(self) -> None:
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", 3, 3), "")
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", 0, -2), "")
        self.assertEqual(call_fn(COMMENTS_WIDGET, "likeCountSlide", "nope", 0), "")


class LikeToggleParseTests(unittest.TestCase):
    def test_parse_like_toggle_body_success(self) -> None:
        parsed = call_fn(
            LIKES_API,
            "parseLikeToggleBody",
            {"comment_id": 7, "visitor_id": UUID},
        )
        self.assertEqual(parsed, {"commentId": 7, "visitorId": UUID})

    def test_parse_like_toggle_body_rejects_bad_ids_failure(self) -> None:
        missing = call_fn(LIKES_API, "parseLikeToggleBody", {})
        self.assertEqual(missing["status"], 400)
        bad_visitor = call_fn(
            LIKES_API, "parseLikeToggleBody", {"comment_id": 1, "visitor_id": "nope"}
        )
        self.assertEqual(bad_visitor["status"], 400)
        self.assertFalse(call_fn(SHARED_API, "isValidVisitorId", ""))
        self.assertFalse(call_fn(SHARED_API, "isValidVisitorId", "abc"))
        self.assertTrue(call_fn(SHARED_API, "isValidVisitorId", UUID))


class LikeFieldHelperTests(unittest.TestCase):
    def test_with_public_like_fields_success(self) -> None:
        payload = call_fn(
            COMMENTS_API,
            "withPublicLikeFields",
            {"id": 1, "like_count": "4", "liked": 1, "body": "hi"},
        )
        self.assertEqual(payload["like_count"], 4)
        self.assertTrue(payload["liked"])
        self.assertEqual(payload["id"], 1)

    def test_with_public_like_fields_defaults_failure(self) -> None:
        payload = call_fn(COMMENTS_API, "withPublicLikeFields", {"id": 2, "body": "x"})
        self.assertEqual(payload["like_count"], 0)
        self.assertFalse(payload["liked"])


class LikeWidgetSourceTests(unittest.TestCase):
    def test_heart_button_shows_count_success(self) -> None:
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        css = COMMENTS_CSS.read_text(encoding="utf-8")
        api = COMMENTS_API.read_text(encoding="utf-8")
        likes = LIKES_API.read_text(encoding="utf-8")
        self.assertIn("comment-like-btn", js)
        self.assertIn("comment-like-heart", js)
        self.assertIn("comment-like-count", js)
        self.assertIn("aria-pressed", js)
        self.assertIn("/api/comment-likes", js)
        self.assertIn("visitor_id", js)
        self.assertIn("like_count", api)
        self.assertIn("FROM comment_likes", api)
        self.assertIn("DELETE FROM comment_likes", api)
        self.assertIn("onRequestPost", likes)
        self.assertIn("ponytail:", likes)
        self.assertIn("#comments .comment-like-btn", css)
        self.assertIn("aria-pressed=\"true\"", css)
        self.assertIn(":focus-visible", css[css.find("#comments .comment-like-btn") :])
        self.assertIn("likeCountSlide", js)
        self.assertIn("comment-like-count--up", js)
        self.assertIn("comment-like-count--down", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("@keyframes comment-like-count-up", css)
        self.assertIn("@keyframes comment-like-count-down", css)
        self.assertIn("translateY(-1.2em)", css)
        self.assertIn("width: 1.125em", css)
        self.assertIn("font-size: 0.9375rem", css[css.find("#comments .comment-like-btn") :])

    def test_likes_are_hearts_not_votes_failure(self) -> None:
        js = COMMENTS_WIDGET.read_text(encoding="utf-8")
        css = COMMENTS_CSS.read_text(encoding="utf-8")
        likes = LIKES_API.read_text(encoding="utf-8")
        self.assertNotIn("downvote", js.lower())
        self.assertNotIn("thumbs-down", js.lower())
        self.assertNotIn("comment-dislike", js)
        self.assertNotIn("TURNSTILE", likes)
        self.assertIn("createElementNS", js)
        self.assertIn("http://www.w3.org/2000/svg", js)
        self.assertNotIn("text-decoration: underline", css.split("#comments .comment-like-btn")[1][:400])


class LikeSchemaAndDocsTests(unittest.TestCase):
    def test_migration_and_docs_success(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        privacy = PRIVACY.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS comment_likes", sql)
        self.assertIn("PRIMARY KEY (comment_id, visitor_id)", sql)
        self.assertIn("0006_comment_likes.sql", readme)
        self.assertIn("/api/comment-likes", readme)
        self.assertIn("liked", privacy.lower())
        self.assertIn("eight", readme.lower())

    def test_migration_has_no_downvote_column_failure(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertNotIn("dislike", sql.lower())
        self.assertNotIn("vote", sql.lower())
        self.assertNotIn("like_count", sql)


if __name__ == "__main__":
    unittest.main()
