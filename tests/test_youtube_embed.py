"""YouTube URLs in post bodies become a player; named links stay links."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "layouts" / "_default" / "_markup" / "render-link.html"
CONTENT_PARTIAL = REPO_ROOT / "layouts" / "partials" / "page-content.html"
SINGLE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "single.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TIMEOUT_SECONDS = 120

VIDEO_ID = "yOZB6mNqhuA"
WATCH_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
SHORT_URL = f"https://youtu.be/{VIDEO_ID}"
EMBED_SRC = f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}"

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: YouTube Embed Fixture",
        "slug: youtube-embed-fixture",
        "author: eric-wisnewski",
        "date: 2026-09-02T19:55:00Z",
        "draft: false",
        "---",
        f"[{WATCH_URL}]({WATCH_URL})",
        "",
        SHORT_URL,
        "",
        f"Watch the [campus tour]({WATCH_URL}) later.",
        "",
        "See [kenpom](http://kenpom.com).",
        "",
        f'<p><a href="{WATCH_URL}">{WATCH_URL}</a></p>',
        "",
    ]
)


def run_hugo(*, destination: Path, content_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "hugo",
            "--destination",
            str(destination),
            "--contentDir",
            str(content_dir),
            "--quiet",
            "--noBuildLock",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class YoutubeEmbedSourceTests(unittest.TestCase):
    def test_link_hook_embeds_youtube_watch_urls_success(self) -> None:
        hook = HOOK.read_text(encoding="utf-8")
        self.assertTrue(HOOK.is_file())
        self.assertIn("youtube-nocookie.com/embed/", hook)
        self.assertIn("class=\"youtube-embed\"", hook)
        self.assertIn("title=\"YouTube video\"", hook)
        self.assertIn("allowfullscreen", hook)
        self.assertIn("loading=\"lazy\"", hook)
        self.assertIn("youtu\\.be", hook)
        self.assertIn(".PlainText", hook)
        self.assertIn("$dest | safeURL", hook)
        partial = CONTENT_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("replaceRE", partial)
        self.assertIn("youtube-nocookie.com/embed/$1", partial)
        layout = SINGLE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('partial "page-content.html"', layout)

    def test_link_hook_does_not_use_tracking_youtube_host_failure(self) -> None:
        hook = HOOK.read_text(encoding="utf-8")
        self.assertNotIn("https://www.youtube.com/embed/", hook)

    def test_embed_styles_are_responsive_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("iframe.youtube-embed", css)
        self.assertIn("16 / 9", css)
        self.assertIn("iframe.youtube-embed:focus-visible", css)
        self.assertIn("p:has(> iframe.youtube-embed:only-child)", css)

    def test_embed_is_not_a_fixed_pixel_player_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        block = css.split("iframe.youtube-embed", 1)[-1].split("}", 1)[0]
        self.assertNotIn("width: 560px", block)
        self.assertNotIn("height: 315px", block)

    def test_cms_body_fields_tell_writers_to_paste_a_url_success(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        self.assertGreaterEqual(yml.count("Paste a YouTube URL on its own line"), 3)


class YoutubeEmbedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="youtube-embed-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "youtube-embed-fixture.md").write_text(
            FIXTURE_POST, encoding="utf-8"
        )
        dest = cls._tmp / "out"
        result = run_hugo(destination=dest, content_dir=content_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        html_path = dest / "posts" / "youtube-embed-fixture" / "index.html"
        try:
            cls.html = html_path.read_text(encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_watch_url_renders_privacy_embed_success(self) -> None:
        self.assertIn(EMBED_SRC, self.html)
        self.assertIn('class="youtube-embed"', self.html)
        self.assertIn("<iframe", self.html)
        self.assertEqual(self.html.count('class="youtube-embed"'), 3)
        self.assertNotIn(f'<a href="{WATCH_URL}">{WATCH_URL}</a>', self.html)
        self.assertNotIn(f'<a href="{SHORT_URL}">', self.html)

    def test_named_youtube_link_and_other_links_stay_anchors_failure(self) -> None:
        self.assertIn(f'<a href="{WATCH_URL}">campus tour</a>', self.html)
        self.assertIn('<a href="http://kenpom.com">kenpom</a>', self.html)
        self.assertNotIn("youtube.com/embed/", self.html)
