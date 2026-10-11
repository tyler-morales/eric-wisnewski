"""Author invite: own section, draft stub, welcome email. CMS draft defaults stay."""

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
    "author stub",
    "draft",
    "own section",
    "don't use the posts section",
    "continue with email",
    "[comments password]",
    "your section is ready",
)

GOOD_INVITE = """
1. Author stub with Draft on, merged before they sign in.
2. Collaborators invite their email.
3. Welcome email: reply with your own section name. Continue with email.
   Don't use the Posts section. Comments password is [COMMENTS PASSWORD].
4. After they reply, build the section, then send "your section is ready".
"""

BAD_INVITE_NO_DRAFT = """
1. Author stub, already public.
2. Collaborators invite their email.
3. They get their own section. Continue with email.
   Don't use the Posts section. Comments password is [COMMENTS PASSWORD].
4. Send "your section is ready".
"""


def is_invite_doc(text: str) -> bool:
    """True when the invite copy covers the own-section flow, email sign-in, and drafts."""
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
            "invite doc must cover the stub, Collaborators, own section, Draft, "
            "Continue with email, and the comments-password placeholder",
        )

    def test_welcome_email_forbids_posts_and_github_save_failure_path(self) -> None:
        text = INVITE_DOC.read_text(encoding="utf-8")
        self.assertIn("don't use the Posts section", text)
        self.assertNotIn("Open Posts → New", text)
        self.assertIn("can open the CMS but can’t save", text)
        self.assertIn("Continue with email", text)
        self.assertIn("[NAME]", text)
        self.assertIn("[EMAIL]", text)
        self.assertIn("[COMMENTS PASSWORD]", text)
        self.assertNotRegex(
            text,
            r"(?i)password to access comments:\s*(?!\[COMMENTS PASSWORD\])\S+",
        )

    def test_readme_points_at_invite_doc_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("docs/invite-author.md", readme)

    def test_live_authors_are_not_drafts_success(self) -> None:
        for slug in (
            "eric-wisnewski",
            "grady-davis",
            "christian-pudlo",
            "tad",
            "tyler-morales",
        ):
            text = (AUTHORS_DIR / f"{slug}.md").read_text(encoding="utf-8")
            self.assertRegex(
                text,
                r"(?m)^draft:\s*false\s*$",
                f"{slug} must stay published (draft: false)",
            )

    def test_jeremy_profile_stays_draft_until_he_undrafts_failure(self) -> None:
        text = (AUTHORS_DIR / "jeremy-bryan.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^draft:\s*true\s*$")

    def test_john_peterson_stub_stays_draft_success(self) -> None:
        text = (AUTHORS_DIR / "john-peterson.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^name:\s*John Peterson\s*$")
        self.assertRegex(text, r"(?m)^slug:\s*john-peterson\s*$")
        self.assertRegex(text, r"(?m)^draft:\s*true\s*$")
        self.assertRegex(text, r"(?m)^bio:\s*\S.+$")
        self.assertNotRegex(text, r"(?m)^image:")


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

    def test_da_breakdown_draft_default_true_success(self) -> None:
        yaml_text = PAGES_YML.read_text(encoding="utf-8")
        self.assertEqual(
            field_default(collection_block(yaml_text, "da-breakdown-w-tad"), "draft"),
            "true",
        )

    def test_jeremy_on_tap_draft_default_true_success(self) -> None:
        yaml_text = PAGES_YML.read_text(encoding="utf-8")
        self.assertEqual(
            field_default(collection_block(yaml_text, "jeremy-on-tap"), "draft"),
            "true",
        )

    def test_missing_draft_field_failure(self) -> None:
        self.assertIsNone(field_default("      - name: bio\n        type: text\n", "draft"))
