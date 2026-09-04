"""Tab icon is a PNG portrait, not the wizard SVG."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"
FAVICON = REPO_ROOT / "static" / "favicon.png"
OLD_SVG = REPO_ROOT / "static" / "favicon.svg"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class FaviconTemplateTests(unittest.TestCase):
    def test_head_links_png_icon_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('rel="icon"', head)
        self.assertIn("favicon.png", head)
        self.assertIn("image/png", head)
        self.assertIn("apple-touch-icon.png", head)

    def test_head_does_not_link_svg_icon_failure(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("favicon.svg", head)
        self.assertNotIn("image/svg+xml", head)


class FaviconAssetTests(unittest.TestCase):
    def test_png_favicon_is_at_least_48px_for_google_success(self) -> None:
        data = FAVICON.read_bytes()
        self.assertTrue(data.startswith(PNG_MAGIC), "favicon.png must be PNG")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 48, "Google Search wants favicons ≥ 48×48")
        self.assertLess(len(data), 40_000, "favicon should stay small")

    def test_wizard_svg_favicon_is_gone_failure(self) -> None:
        self.assertFalse(OLD_SVG.is_file(), "static/favicon.svg is leftover wizard emoji")
        self.assertNotEqual(FAVICON.suffix.lower(), ".svg")
