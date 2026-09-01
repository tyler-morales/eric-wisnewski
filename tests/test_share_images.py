"""Open Graph share images: post photo on posts, JPEG default elsewhere."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"
OG_DEFAULT = REPO_ROOT / "static" / "images" / "og-default.jpg"
README = REPO_ROOT / "README.md"
HUGO_TIMEOUT_SECONDS = 120

OG_IMAGE_RE = re.compile(
    r'<meta\s+property="og:image"\s+content="([^"]+)"',
    re.IGNORECASE,
)
TWITTER_IMAGE_RE = re.compile(
    r'<meta\s+name="twitter:image"\s+content="([^"]+)"',
    re.IGNORECASE,
)


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Return (height, width) from a baseline JPEG SOF marker."""
    i = 2
    while i + 8 < len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 5 : i + 7], "big"), int.from_bytes(
                data[i + 7 : i + 9], "big"
            )
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    return (0, 0)


def meta_images(html: str) -> tuple[str, str]:
    og = OG_IMAGE_RE.search(html)
    twitter = TWITTER_IMAGE_RE.search(html)
    return (
        og.group(1) if og else "",
        twitter.group(1) if twitter else "",
    )


class ShareImageTemplateTests(unittest.TestCase):
    def test_default_share_image_is_jpeg_not_favicon_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("og-default.jpg", head)
        self.assertIn(".Params.image", head)
        self.assertIn("og:image", head)
        self.assertIn("twitter:image", head)

    def test_favicon_is_not_the_share_image_failure(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        share_block = head.split("og:type", 1)[-1]
        self.assertNotIn("favicon.svg", share_block)
        self.assertNotIn("favicon.png", share_block)
        self.assertNotIn("apple-touch-icon", share_block)


class ShareImageAssetTests(unittest.TestCase):
    def test_default_jpeg_exists_and_is_large_enough_success(self) -> None:
        self.assertTrue(OG_DEFAULT.is_file(), f"missing {OG_DEFAULT}")
        data = OG_DEFAULT.read_bytes()
        self.assertTrue(data.startswith(b"\xff\xd8\xff"), "og-default.jpg must be JPEG")
        self.assertGreater(len(data), 8_000, "share image is too small for Instagram")
        height, width = jpeg_size(data)
        self.assertEqual((width, height), (1200, 630), "share cards want 1200×630")

    def test_default_share_image_is_not_svg_failure(self) -> None:
        self.assertNotEqual(OG_DEFAULT.suffix.lower(), ".svg")
        self.assertFalse(OG_DEFAULT.read_bytes().lstrip().startswith(b"<svg"))


def write_share_fixture(content_dir: Path) -> None:
    """Minimal content so the Hugo build does not fetch School Sheets."""
    (content_dir / "posts").mkdir(parents=True)
    (content_dir / "gradys-tour").mkdir(parents=True)
    (content_dir / "posts" / "with-photo.md").write_text(
        "---\n"
        "title: With Photo\n"
        "slug: with-photo\n"
        "date: 2026-01-01T00:00:00Z\n"
        "draft: false\n"
        "image: /images/uploads/hero.jpg\n"
        "---\n"
        "Hello\n",
        encoding="utf-8",
    )
    (content_dir / "posts" / "no-photo.md").write_text(
        "---\n"
        "title: No Photo\n"
        "slug: no-photo\n"
        "date: 2026-01-02T00:00:00Z\n"
        "draft: false\n"
        "---\n"
        "Hello\n",
        encoding="utf-8",
    )
    (content_dir / "gradys-tour" / "_index.md").write_text(
        "---\ntitle: Grady's Tour\n---\n",
        encoding="utf-8",
    )


class ShareImageBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="share-images-")
        root = Path(cls._tmp.name)
        content_dir = root / "content"
        write_share_fixture(content_dir)
        dest = root / "public"
        cache_dir = root / "cache"
        cache_dir.mkdir()
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(dest),
                "--contentDir",
                str(content_dir),
                "--cacheDir",
                str(cache_dir),
                "--noBuildLock",
                "--quiet",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            cls._tmp.cleanup()
            raise RuntimeError(result.stderr or result.stdout or "hugo build failed")
        cls.dest = dest

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_home_uses_general_jpeg_success(self) -> None:
        html = (self.dest / "index.html").read_text(encoding="utf-8")
        og, twitter = meta_images(html)
        self.assertIn("og-default.jpg", og)
        self.assertIn("og-default.jpg", twitter)
        self.assertTrue(og.startswith("http"), og)
        self.assertNotIn(".svg", og)

    def test_section_without_featured_image_uses_default_success(self) -> None:
        html = (self.dest / "gradys-tour" / "index.html").read_text(encoding="utf-8")
        og, twitter = meta_images(html)
        self.assertIn("og-default.jpg", og)
        self.assertIn("og-default.jpg", twitter)
        self.assertNotIn("favicon", og)

    def test_post_uses_featured_image_success(self) -> None:
        html = (self.dest / "posts" / "with-photo" / "index.html").read_text(
            encoding="utf-8"
        )
        og, twitter = meta_images(html)
        self.assertIn("hero.jpg", og)
        self.assertIn("hero.jpg", twitter)
        self.assertNotIn("og-default.jpg", og)
        self.assertNotIn("favicon", og)

    def test_post_without_featured_image_falls_back_to_default_success(self) -> None:
        html = (self.dest / "posts" / "no-photo" / "index.html").read_text(
            encoding="utf-8"
        )
        og, twitter = meta_images(html)
        self.assertIn("og-default.jpg", og)
        self.assertIn("og-default.jpg", twitter)

    def test_built_pages_never_share_svg_failure(self) -> None:
        for rel in (
            "index.html",
            "gradys-tour/index.html",
            "posts/with-photo/index.html",
            "posts/no-photo/index.html",
        ):
            html = (self.dest / rel).read_text(encoding="utf-8")
            og, twitter = meta_images(html)
            self.assertTrue(og, rel)
            self.assertTrue(twitter, rel)
            self.assertFalse(og.lower().endswith(".svg"), rel)
            self.assertFalse(twitter.lower().endswith(".svg"), rel)


class ShareImageDocsTests(unittest.TestCase):
    def test_readme_documents_default_share_image_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("og-default.jpg", readme)
        self.assertIn("og:image", readme)
        self.assertIn("Eric’s portrait", readme)
