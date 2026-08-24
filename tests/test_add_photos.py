"""Authors add large photos via /add-photos/, not Pages CMS."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHOTOS_API = REPO_ROOT / "functions" / "api" / "photos.js"
ADD_PHOTOS_PAGE = REPO_ROOT / "content" / "add-photos.md"
ADD_PHOTOS_LAYOUT = REPO_ROOT / "layouts" / "add-photos" / "single.html"
ADD_PHOTOS_JS = REPO_ROOT / "static" / "js" / "add-photos.js"
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
GRADY_GUIDE = REPO_ROOT / "content" / "gradys-tour" / "how-to-use-this-blog.md"
README = REPO_ROOT / "README.md"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"


def call_photos_fn(fn_name: str, arg: object) -> object:
    """Run an exported helper from functions/api/photos.js via Node."""
    if not PHOTOS_API.is_file():
        raise FileNotFoundError(PHOTOS_API)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(PHOTOS_API.as_uri())};\n"
        f"console.log(JSON.stringify({fn_name}({json.dumps(arg)})));\n"
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


class SanitizeFilenameTests(unittest.TestCase):
    def test_keeps_safe_jpeg_name_success(self) -> None:
        self.assertEqual(
            call_photos_fn("sanitizeUploadFilename", "IMG_0846.jpeg"),
            "IMG_0846.jpg",
        )

    def test_rejects_path_traversal_failure(self) -> None:
        self.assertEqual(call_photos_fn("sanitizeUploadFilename", "../etc/passwd.jpg"), "")
        self.assertEqual(call_photos_fn("sanitizeUploadFilename", "ok.png.exe"), "")


class SecretMatchTests(unittest.TestCase):
    def test_matching_secrets_success(self) -> None:
        self.assertTrue(call_photos_fn("secretsMatch", ["grady-pass", "grady-pass"]))

    def test_mismatch_or_empty_failure(self) -> None:
        self.assertFalse(call_photos_fn("secretsMatch", ["grady-pass", "nope"]))
        self.assertFalse(call_photos_fn("secretsMatch", ["", ""]))


class ImageBytesTests(unittest.TestCase):
    def test_jpeg_header_success(self) -> None:
        self.assertTrue(call_photos_fn("isAllowedImageBytes", [255, 216, 255, 224, 0, 16]))

    def test_plain_text_failure(self) -> None:
        self.assertFalse(call_photos_fn("isAllowedImageBytes", [60, 104, 116, 109, 108]))


class GoogleHostTests(unittest.TestCase):
    def test_google_photo_host_success(self) -> None:
        self.assertTrue(
            call_photos_fn(
                "isAllowedGoogleMediaUrl",
                "https://lh3.googleusercontent.com/pw/abc",
            )
        )

    def test_other_host_failure(self) -> None:
        self.assertFalse(
            call_photos_fn("isAllowedGoogleMediaUrl", "https://evil.example/steal")
        )


class AddPhotosPageTests(unittest.TestCase):
    def test_page_is_noindex_and_not_in_nav(self) -> None:
        page = ADD_PHOTOS_PAGE.read_text(encoding="utf-8")
        layout = ADD_PHOTOS_LAYOUT.read_text(encoding="utf-8")
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("robots: noindex", page)
        self.assertIn("add-photos.js", layout)
        self.assertIn("Google Photos", layout)
        self.assertIn("noindex", head)
        self.assertNotIn("add-photos", header)

    def test_guide_and_readme_point_at_add_photos(self) -> None:
        guide = GRADY_GUIDE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        css = STYLE_CSS.read_text(encoding="utf-8")
        js = ADD_PHOTOS_JS.read_text(encoding="utf-8")
        self.assertIn("/add-photos/", guide)
        self.assertIn("UPLOAD_SECRET", readme)
        self.assertIn("GOOGLE_CLIENT_ID", readme)
        self.assertIn("add-photos", css)
        self.assertIn("compressImage", js)
        self.assertIn("photospicker.mediaitems.readonly", PHOTOS_API.read_text(encoding="utf-8"))
