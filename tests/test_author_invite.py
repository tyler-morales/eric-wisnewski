"""Author invite stays drafts-only: checklist email plus CMS draft defaults."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INVITE_DOC = REPO_ROOT / "docs" / "invite-author.md"
PAGES_YML = REPO_ROOT / ".pages.yml"
README = REPO_ROOT / "README.md"
AUTHORS_DIR = REPO_ROOT / "content" / "authors"

REQUIRED_PHRASES = (
    "collaborators",
    "authors",
    "add-photos",
    "posts",
    "draft",
)

GOOD_INVITE = """
1. Collaborators invite their email.
2. Authors stub with Draft on.
3. They write Posts at /add-photos/ then Save as Draft.
"""

BAD_INVITE_NO_DRAFT = """
1. Collaborators invite their email.
2. Authors stub.
3. They write Posts and save. Photos at /add-photos/.
"""


def is_invite_doc(text: str) -> bool:
    """True when the invite copy covers CMS access, profile, photos, Posts, and drafts."""
    if not text or not text.strip():
        return False
    lowered = text.lower()
    return all(phrase in lowered for phrase in REQUIRED_PHRASES)


def collection_block(yaml_text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  - name: {re.escape(name)}\n(.*?)(?=^  - name: |\Z)",
        yaml_text,
    )
    return match.group(1) if match else ""


def field_default(block: str, field: str) -> str | None:
    match = re.search(
        rf"(?ms)^      - name: {re.escape(field)}\n(?:.*?\n)*?^        default: (\S+)",
        block,
    )
    return match.group(1) if match else None


class InviteDocLogicTests(unittest.TestCase):
    def test_complete_invite_copy_success(self) -> None:
        self.assertTrue(is_invite_doc(GOOD_INVITE))

    def test_invite_copy_without_draft_failure(self) -> None:
        self.assertFalse(is_invite_doc(BAD_INVITE_NO_DRAFT))

    def test_empty_copy_failure(self) -> None:
        self.assertFalse(is_invite_doc(""))


class InviteDocContentTests(unittest.TestCase):
    def test_invite_doc_covers_onboarding_steps_success(self) -> None:
        self.assertTrue(INVITE_DOC.is_file(), "docs/invite-author.md is required")
        text = INVITE_DOC.read_text(encoding="utf-8")
        self.assertTrue(
            is_invite_doc(text),
            "invite doc must mention Collaborators, Authors, add-photos, Posts, and Draft",
        )

    def test_readme_points_at_invite_doc_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("docs/invite-author.md", readme)

    def test_live_authors_are_not_drafts_success(self) -> None:
        for slug in ("eric-wisnewski", "grady-davis"):
            text = (AUTHORS_DIR / f"{slug}.md").read_text(encoding="utf-8")
            self.assertRegex(
                text,
                r"(?m)^draft:\s*false\s*$",
                f"{slug} must stay published (draft: false)",
            )


class CmsDraftDefaultTests(unittest.TestCase):
    def test_posts_and_authors_draft_default_true_success(self) -> None:
        yaml_text = PAGES_YML.read_text(encoding="utf-8")
        self.assertEqual(field_default(collection_block(yaml_text, "authors"), "draft"), "true")
        self.assertEqual(field_default(collection_block(yaml_text, "posts"), "draft"), "true")

    def test_gradys_tour_draft_default_stays_false_failure_path(self) -> None:
        yaml_text = PAGES_YML.read_text(encoding="utf-8")
        self.assertEqual(
            field_default(collection_block(yaml_text, "gradys-tour"), "draft"),
            "false",
        )

    def test_missing_draft_field_failure(self) -> None:
        self.assertIsNone(field_default("      - name: bio\n        type: text\n", "draft"))
