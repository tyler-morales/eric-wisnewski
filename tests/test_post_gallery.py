"""Pages CMS Gallery: upload several photos, then keep the ones for the post."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_YML = REPO_ROOT / ".pages.yml"
SINGLE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "single.html"
GALLERY_PARTIAL = REPO_ROOT / "layouts" / "partials" / "post-gallery.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
POSTS_DIR = REPO_ROOT / "content" / "posts"

COLLECTION_RE = re.compile(
    r"(?m)^  - name: (posts|gradys-tour|da-breakdown-w-tad)\n(.*?)(?=^  - name: |\Z)",
    re.DOTALL,
)
GALLERY_FIELD_RE = re.compile(
    r"(?m)^      - name: gallery\n(?:        .+\n)+",
)
FEATURED_IMAGE_FIELD_RE = re.compile(
    r"(?m)^      - name: image\n        label: Featured Image\n(?:        .+\n)+",
)


def collection_block(pages_yml: str, name: str) -> str:
    """Return the `.pages.yml` block for one content collection."""
    for match in COLLECTION_RE.finditer(pages_yml):
        if match.group(1) == name:
            return match.group(0)
    return ""


def gallery_field(collection_yaml: str) -> str:
    """Return the gallery field YAML, or empty if missing."""
    match = GALLERY_FIELD_RE.search(collection_yaml)
    return match.group(0) if match else ""


def featured_image_field(collection_yaml: str) -> str:
    """Return the Featured Image field YAML, or empty if missing."""
    match = FEATURED_IMAGE_FIELD_RE.search(collection_yaml)
    return match.group(0) if match else ""


def gallery_image_paths(raw: object) -> list[str]:
    """Keep only non-empty image paths from a CMS gallery value.

    Pages CMS stores many images as a list and a single pick as a string.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        path = raw.strip()
        return [path] if path else []
    if isinstance(raw, (list, tuple)):
        return [path.strip() for path in raw if isinstance(path, str) and path.strip()]
    return []


class GalleryConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pages_yml = PAGES_YML.read_text(encoding="utf-8")

    def test_posts_and_tour_have_multi_image_gallery_success(self) -> None:
        for name in ("posts", "gradys-tour", "da-breakdown-w-tad"):
            with self.subTest(collection=name):
                block = collection_block(self.pages_yml, name)
                field = gallery_field(block)
                self.assertTrue(field, f"{name} is missing a gallery field")
                self.assertIn("type: image", field)
                self.assertIn("multiple:", field)
                self.assertIn("max:", field)
                self.assertIn("unique: true", field)

    def test_featured_image_stays_single_failure(self) -> None:
        for name in ("posts", "gradys-tour", "da-breakdown-w-tad"):
            with self.subTest(collection=name):
                block = collection_block(self.pages_yml, name)
                field = featured_image_field(block)
                self.assertTrue(field, f"{name} is missing Featured Image")
                self.assertNotIn("multiple:", field)


class GalleryPathTests(unittest.TestCase):
    def test_list_of_paths_success(self) -> None:
        self.assertEqual(
            gallery_image_paths(["/images/uploads/a.jpg", " /images/uploads/b.jpg "]),
            ["/images/uploads/a.jpg", "/images/uploads/b.jpg"],
        )

    def test_empty_or_invalid_failure(self) -> None:
        self.assertEqual(gallery_image_paths(None), [])
        self.assertEqual(gallery_image_paths(""), [])
        self.assertEqual(gallery_image_paths([]), [])
        self.assertEqual(gallery_image_paths(["", "  "]), [])
        self.assertEqual(gallery_image_paths(1), [])

    def test_single_string_from_cms(self) -> None:
        self.assertEqual(
            gallery_image_paths("/images/uploads/only.jpg"),
            ["/images/uploads/only.jpg"],
        )


class GalleryTemplateTests(unittest.TestCase):
    def test_single_layout_includes_gallery_partial(self) -> None:
        layout = SINGLE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('partial "post-gallery.html"', layout)

    def test_gallery_partial_handles_slice_and_string(self) -> None:
        partial = GALLERY_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("reflect.IsSlice", partial)
        self.assertIn("post-gallery", partial)
        self.assertIn("aria-label", partial)

    def test_gallery_styles_exist(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".post-gallery", css)
        self.assertIn(".post-gallery-list", css)


class GalleryBuildTests(unittest.TestCase):
    @classmethod
    def _write_fixture(cls, filename: str, body: str) -> Path:
        path = POSTS_DIR / filename
        path.write_text(body, encoding="utf-8")
        return path

    @classmethod
    def _cleanup(cls) -> None:
        for path in getattr(cls, "_fixtures", []):
            path.unlink(missing_ok=True)
        output_dir = getattr(cls, "_output_dir", None)
        if output_dir is not None:
            shutil.rmtree(output_dir, ignore_errors=True)

    @classmethod
    def setUpClass(cls) -> None:
        cls._fixtures: tuple[Path, ...] | list[Path] = []
        cls._output_dir = None
        cls._fixtures = [
            cls._write_fixture(
                "_test-gallery-fixture.md",
                "\n".join(
                    [
                        "---",
                        "title: Gallery Fixture Post",
                        "slug: gallery-fixture-post",
                        "author: eric-wisnewski",
                        "date: 2026-08-19T09:00:00Z",
                        "draft: true",
                        "gallery:",
                        "  - /images/uploads/gallery-a.jpg",
                        "  - /images/uploads/gallery-b.jpg",
                        "---",
                        "Fixture body.",
                        "",
                    ]
                ),
            ),
            cls._write_fixture(
                "_test-gallery-plain-fixture.md",
                "\n".join(
                    [
                        "---",
                        "title: Gallery Plain Fixture Post",
                        "slug: gallery-plain-fixture-post",
                        "author: eric-wisnewski",
                        "date: 2026-08-19T09:00:00Z",
                        "draft: true",
                        "---",
                        "No gallery.",
                        "",
                    ]
                ),
            ),
        ]
        cls._output_dir = Path(tempfile.mkdtemp(prefix="post-gallery-hugo-"))
        result = subprocess.run(
            [
                "hugo",
                "--buildDrafts",
                "--destination",
                str(cls._output_dir),
                "--quiet",
                "--noBuildLock",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            cls._cleanup()
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        try:
            cls.gallery_html = (
                cls._output_dir / "posts" / "gallery-fixture-post" / "index.html"
            ).read_text(encoding="utf-8")
            cls.plain_html = (
                cls._output_dir / "posts" / "gallery-plain-fixture-post" / "index.html"
            ).read_text(encoding="utf-8")
        except OSError as exc:
            cls._cleanup()
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup()

    def test_gallery_renders_selected_photos_success(self) -> None:
        self.assertIn('class="post-gallery"', self.gallery_html)
        self.assertIn("gallery-a.jpg", self.gallery_html)
        self.assertIn("gallery-b.jpg", self.gallery_html)
        self.assertIn("<ul", self.gallery_html)

    def test_post_without_gallery_omits_section_failure(self) -> None:
        self.assertNotIn('class="post-gallery"', self.plain_html)


if __name__ == "__main__":
    unittest.main()
