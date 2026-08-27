"""Post reading: serif body, gray captions, mobile full-bleed photos."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"


def first_block(css: str, selector: str) -> str:
    """Return the first `{ ... }` whose selector list starts with selector."""
    pattern = re.compile(re.escape(selector) + r"\s*(?:,[^{]+)?\{([^}]+)\}")
    match = pattern.search(css)
    return match.group(1) if match else ""


class PostTypographyCssTests(unittest.TestCase):
    def setUp(self) -> None:
        self.css = STYLE_CSS.read_text(encoding="utf-8")

    def test_post_body_uses_serif_success(self) -> None:
        self.assertIn("--font-serif", self.css)
        self.assertIn("Iowan Old Style", self.css)
        self.assertIn("Georgia", self.css)
        block = first_block(self.css, "article.post-content")
        self.assertIn("var(--font-serif)", block)
        self.assertIn("1.125rem", block)
        self.assertIn("1.7", block)

    def test_site_chrome_stays_sans_failure(self) -> None:
        body = first_block(self.css, "body")
        self.assertIn("var(--font-sans)", body)
        self.assertNotIn("var(--font-serif)", body)
        self.assertNotIn("Georgia", body)
        bio = first_block(self.css, ".author-bio")
        self.assertIn("var(--font-sans)", bio)

    def test_captions_are_small_and_gray_success(self) -> None:
        self.assertIn("--text-muted", self.css)
        grouped = first_block(self.css, "article.post-content figcaption")
        self.assertIn("0.8125rem", grouped)
        self.assertIn("var(--text-muted)", grouped)
        self.assertIn("var(--font-sans)", grouped)
        self.assertIn(
            "p:has(> img:only-child)+p:has(> em:only-child)",
            self.css,
        )
        self.assertIn(
            "p:has(> img:only-child)+p:has(> i:only-child)",
            self.css,
        )

    def test_captions_are_not_body_copy_failure(self) -> None:
        grouped = first_block(self.css, "article.post-content figcaption")
        self.assertNotIn("1.125rem", grouped)
        self.assertNotIn("var(--font-serif)", grouped)
        self.assertNotIn("var(--text)", grouped)

    def test_mobile_images_span_the_device_success(self) -> None:
        mobile = self.css.split("@media (max-width: 768px)", 1)[-1]
        self.assertIn("100vw", mobile)
        self.assertIn("calc(50% - 50vw)", mobile)
        self.assertIn("p:has(> img:only-child)", mobile)
        self.assertIn(".post-featured-image", mobile)
        self.assertIn(".post-gallery", mobile)

    def test_mobile_does_not_stack_image_gaps_failure(self) -> None:
        self.assertNotIn("article.post-content img {", self.css)
        mobile = self.css.split("@media (max-width: 768px)", 1)[-1]
        self.assertNotIn("font-size: 112.5%", mobile)
        self.assertNotIn("margin-bottom: 1.35em", mobile)


if __name__ == "__main__":
    unittest.main()
