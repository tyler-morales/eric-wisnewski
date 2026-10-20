"""Pages CMS uploads in subfolders must publish at the same URL, original bytes."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC = REPO_ROOT / "scripts" / "sync-uploaded-images.sh"
HUGO_TIMEOUT_SECONDS = 120

# Same ballpark as the Loyola JPEGs (2–3 MB). Byte identity means the build
# copied the original instead of running it through Hugo's image pipeline.
LARGE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * (2_500_000 - 4)
NESTED_IMAGE = Path("images/uploads/Boston/arena.jpeg")
SPACED_IMAGE = Path("images/uploads/From Boat to Bike/dock.jpeg")
TOP_IMAGE = Path("images/uploads/featured.jpeg")
NESTED_AUDIO = Path("audio/uploads/sets/clip.m4a")
OUTSIDE = Path("images/not-uploads/sneaky.jpeg")


def write_upload(root: Path, relative: Path, payload: bytes) -> None:
    path = root / "assets" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


class NestedUploadPublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="nested-uploads-")
        root = Path(cls._tmp.name)
        write_upload(root, NESTED_IMAGE, LARGE_JPEG)
        write_upload(root, SPACED_IMAGE, b"spaced-original")
        write_upload(root, TOP_IMAGE, b"top-original")
        write_upload(root, NESTED_AUDIO, b"audio-original")
        write_upload(root, OUTSIDE, b"do-not-publish")
        script = root / "scripts" / "sync-uploaded-images.sh"
        script.parent.mkdir()
        shutil.copy(SYNC, script)
        script.chmod(0o755)
        synced = subprocess.run(
            ["sh", str(script)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if synced.returncode != 0:
            cls._tmp.cleanup()
            raise RuntimeError(synced.stderr or synced.stdout or "sync failed")
        (root / "content" / "posts").mkdir(parents=True)
        (root / "content" / "posts" / "nested.md").write_text(
            "---\n"
            "title: Nested\n"
            "slug: nested\n"
            "date: 2026-10-19T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            f"![](/{NESTED_IMAGE.as_posix()})\n"
            f"![](/{SPACED_IMAGE.as_posix()})\n",
            encoding="utf-8",
        )
        (root / "layouts" / "_default").mkdir(parents=True)
        (root / "layouts" / "_default" / "single.html").write_text(
            "<!doctype html><html><body>{{ .Content }}</body></html>\n",
            encoding="utf-8",
        )
        (root / "hugo.toml").write_text(
            "baseURL = 'https://ericwisnewski.com/'\n"
            "disableKinds = ['taxonomy', 'term', 'sitemap', 'rss']\n",
            encoding="utf-8",
        )
        dest = root / "public"
        hugo = shutil.which("hugo")
        if hugo is None:
            cls._tmp.cleanup()
            raise unittest.SkipTest("hugo is not on PATH")
        built = subprocess.run(
            [hugo, "--destination", str(dest), "--quiet", "--noBuildLock"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if built.returncode != 0:
            cls._tmp.cleanup()
            raise RuntimeError(built.stderr or built.stdout or "hugo build failed")
        cls.root = root
        cls.public = dest
        cls.html = (dest / "posts" / "nested" / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_nested_upload_is_published_with_original_bytes_success(self) -> None:
        published = self.public / NESTED_IMAGE
        self.assertTrue(published.is_file(), published)
        self.assertEqual(published.read_bytes(), LARGE_JPEG)
        self.assertGreater(published.stat().st_size, 2_000_000)
        spaced = self.public / SPACED_IMAGE
        self.assertEqual(spaced.read_bytes(), b"spaced-original")
        top = self.public / TOP_IMAGE
        self.assertEqual(top.read_bytes(), b"top-original")
        audio = self.public / NESTED_AUDIO
        self.assertEqual(audio.read_bytes(), b"audio-original")
        static_nested = self.root / "static" / NESTED_IMAGE
        self.assertEqual(static_nested.read_bytes(), LARGE_JPEG)
        self.assertIn('src="/images/uploads/Boston/arena.jpeg"', self.html)

    def test_outside_uploads_and_flattened_names_are_not_published_failure(self) -> None:
        self.assertFalse((self.public / OUTSIDE).exists())
        self.assertFalse((self.root / "static" / OUTSIDE).exists())
        self.assertFalse((self.public / "images" / "uploads" / "arena.jpeg").exists())
        self.assertFalse((self.public / "images" / "uploads" / "dock.jpeg").exists())
        self.assertFalse((self.public / "audio" / "uploads" / "clip.m4a").exists())
        self.assertNotIn("do-not-publish", self.html)
        self.assertNotIn("sneaky.jpeg", self.html)
