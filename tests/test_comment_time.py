"""Comment posted times are UTC instants, not the browser's local clock."""

from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMENTS_WIDGET = REPO_ROOT / "static" / "js" / "comments.js"
COMMENTS_API = REPO_ROOT / "functions" / "api" / "comments.js"
ADMIN_JS = REPO_ROOT / "static" / "js" / "admin-comments.js"


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


def utc_ms(year: int, month: int, day: int, hour: int, minute: int = 0) -> int:
    return int(
        datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000
    )


class AsIsoUtcTests(unittest.TestCase):
    def test_sqlite_datetime_now_becomes_utc_success(self) -> None:
        payload = call_js(
            COMMENTS_API,
            "asIsoUtc, withIsoCreatedAt, withPublicLikeFields",
            """
console.log(JSON.stringify({
  sqlite: asIsoUtc('2026-08-31 12:00:00'),
  naiveIso: asIsoUtc('2026-08-31T12:00:00'),
  row: withIsoCreatedAt({ id: 1, created_at: '2026-08-31 12:00:00' }),
  likes: withPublicLikeFields({ created_at: '2026-08-31 12:00:00', like_count: 2, liked: 1 })
}));
""",
        )
        self.assertEqual(payload["sqlite"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["naiveIso"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["row"]["created_at"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["likes"]["created_at"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["likes"]["like_count"], 2)

    def test_zoned_and_empty_are_left_alone_failure(self) -> None:
        payload = call_js(
            COMMENTS_API,
            "asIsoUtc, withIsoCreatedAt",
            """
console.log(JSON.stringify({
  z: asIsoUtc('2026-08-31T12:00:00Z'),
  offset: asIsoUtc('2026-08-31T14:00:00+02:00'),
  empty: asIsoUtc(''),
  missing: asIsoUtc(null),
  row: withIsoCreatedAt({ id: 1, created_at: '2026-08-31T12:00:00.000Z' })
}));
""",
        )
        self.assertEqual(payload["z"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["offset"], "2026-08-31T14:00:00+02:00")
        self.assertEqual(payload["empty"], "")
        self.assertIsNone(payload["missing"])
        self.assertEqual(payload["row"]["created_at"], "2026-08-31T12:00:00.000Z")


class TimeAgoTests(unittest.TestCase):
    def test_sqlite_stamp_is_utc_not_local_success(self) -> None:
        posted = utc_ms(2026, 8, 31, 12, 0)
        now = utc_ms(2026, 8, 31, 13, 30)
        payload = call_js(
            COMMENTS_WIDGET,
            "asIsoUtc, parseCommentTime, timeAgo",
            f"""
const posted = parseCommentTime('2026-08-31 12:00:00');
const zoned = parseCommentTime('2026-08-31T12:00:00Z');
console.log(JSON.stringify({{
  iso: asIsoUtc('2026-08-31 12:00:00'),
  posted,
  zoned,
  label: timeAgo('2026-08-31 12:00:00', {now}),
  justNow: timeAgo('2026-08-31T12:00:00Z', {posted + 30_000})
}}));
""",
        )
        self.assertEqual(payload["iso"], "2026-08-31T12:00:00Z")
        self.assertEqual(payload["posted"], posted)
        self.assertEqual(payload["zoned"], posted)
        self.assertEqual(payload["label"], "1 hour ago")
        self.assertEqual(payload["justNow"], "just now")

    def test_invalid_stamp_returns_raw_failure(self) -> None:
        payload = call_js(
            COMMENTS_WIDGET,
            "parseCommentTime, timeAgo",
            """
const t = parseCommentTime('not-a-date');
console.log(JSON.stringify({
  nan: Number.isNaN(t),
  empty: timeAgo(''),
  missing: timeAgo(null),
  garbage: timeAgo('not-a-date')
}));
""",
        )
        self.assertTrue(payload["nan"])
        self.assertEqual(payload["empty"], "")
        self.assertEqual(payload["missing"], "")
        self.assertEqual(payload["garbage"], "not-a-date")


class CommentTimeSourceTests(unittest.TestCase):
    def test_api_and_admin_treat_sqlite_as_utc_success(self) -> None:
        api = COMMENTS_API.read_text(encoding="utf-8")
        widget = COMMENTS_WIDGET.read_text(encoding="utf-8")
        admin = ADMIN_JS.read_text(encoding="utf-8")
        self.assertIn("withIsoCreatedAt", api)
        self.assertIn(".map(withIsoCreatedAt)", api)
        self.assertIn("withIsoCreatedAt({ ...row, edit_token: editToken })", api)
        self.assertIn("asIsoUtc", widget)
        self.assertIn("parseCommentTime", widget)
        self.assertIn("s.replace(' ', 'T') + 'Z'", admin)
        self.assertIn("formatPostedAt", admin)

    def test_admin_does_not_parse_naive_stamp_as_local_failure(self) -> None:
        admin = ADMIN_JS.read_text(encoding="utf-8")
        widget = COMMENTS_WIDGET.read_text(encoding="utf-8")
        self.assertNotIn("var t = Date.parse(raw);", admin)
        self.assertNotIn("new Date(a.created_at)", widget)
        self.assertNotIn("new Date(iso)", widget)


if __name__ == "__main__":
    unittest.main()
