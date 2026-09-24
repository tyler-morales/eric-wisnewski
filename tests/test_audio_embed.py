"""Uploaded audio URLs and the audio shortcode become a native player."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "layouts" / "_default" / "_markup" / "render-link.html"
EMBEDS = REPO_ROOT / "layouts" / "partials" / "html-embeds.html"
PLAYER = REPO_ROOT / "layouts" / "partials" / "audio-player.html"
SRC = REPO_ROOT / "layouts" / "partials" / "audio-src.html"
SHORTCODE = REPO_ROOT / "layouts" / "shortcodes" / "audio.html"
PARTS = REPO_ROOT / "layouts" / "partials" / "post-parts.html"
SINGLE = REPO_ROOT / "layouts" / "_default" / "single.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
PAGES_YML = REPO_ROOT / ".pages.yml"
README = REPO_ROOT / "README.md"
SYNC = REPO_ROOT / "scripts" / "sync-uploaded-images.sh"
HUGO_TIMEOUT_SECONDS = 120

CLIP = "/audio/uploads/halftime.m4a"
OGG = "https://ericwisnewski.com/audio/uploads/road.ogg"
LEFTOVER = "/audio/uploads/cms-leftover.mp3"
ABSOLUTE = "https://ericwisnewski.com/audio/uploads/absolute.mp3"
PART = "/audio/uploads/part-clip.m4a"
SHORT = "/audio/uploads/shortcode.mp3"
WAV = "/audio/uploads/raw.wav"
REMOTE = "https://example.com/episode.mp3"

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: Audio Embed Fixture",
        "slug: audio-embed-fixture",
        "author: eric-wisnewski",
        "date: 2026-09-24T12:00:00Z",
        "draft: false",
        "parts:",
        "  - author: eric-wisnewski",
        f'    body: \'<p><a href="{PART}">{PART}</a></p>\'',
        "---",
        f"[{CLIP}]({CLIP})",
        "",
        OGG,
        "",
        f"Listen to the [interview]({CLIP}) later.",
        "",
        "See [kenpom](http://kenpom.com).",
        "",
        f"[{WAV}]({WAV})",
        "",
        f"[{REMOTE}]({REMOTE})",
        "",
        f'<p><a href="{LEFTOVER}">{LEFTOVER}</a></p>',
        "",
        f'<p><a href="{ABSOLUTE}">{ABSOLUTE}</a></p>',
        "",
        f'<p><a href="{CLIP}">named clip</a></p>',
        "",
        '{{< audio src="/audio/uploads/shortcode.mp3" title="Locker room" caption="After the whistle" >}}',
        "",
        '{{< audio src="https://evil.example/track.mp3" title="nope" >}}',
        "",
        '{{< audio src="/audio/uploads/huge.wav" >}}',
        "",
        '{{< audio src="/images/uploads/photo.jpg" >}}',
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


class AudioEmbedSourceTests(unittest.TestCase):
    def test_link_hook_and_shortcode_embed_uploaded_audio_success(self) -> None:
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn('partial "audio-src.html"', hook)
        self.assertIn('partial "audio-player.html"', hook)
        self.assertIn(".PlainText", hook)
        player = PLAYER.read_text(encoding="utf-8")
        self.assertIn("<audio", player)
        self.assertIn("controls", player)
        self.assertIn('preload="none"', player)
        self.assertIn('class="audio-embed"', player)
        self.assertIn('aria-label=', player)
        self.assertIn("<figcaption>", player)
        self.assertIn(">Listen to audio</a>", player)
        src = SRC.read_text(encoding="utf-8")
        self.assertIn("/audio/uploads/", src)
        self.assertIn("mp3|m4a|ogg", src)
        self.assertNotIn("wav", src)
        shortcode = SHORTCODE.read_text(encoding="utf-8")
        self.assertIn('partial "audio-src.html"', shortcode)
        self.assertIn('partial "audio-player.html"', shortcode)
        embeds = EMBEDS.read_text(encoding="utf-8")
        self.assertIn('class="audio-embed"', embeds)
        self.assertIn('preload="none"', embeds)
        self.assertIn("/audio/uploads/", embeds)
        self.assertIn("youtube-nocookie.com/embed/$1", embeds)
        self.assertIn('partial "html-embeds.html"', PARTS.read_text(encoding="utf-8"))
        self.assertNotIn("audio_upload", SINGLE.read_text(encoding="utf-8"))

    def test_remote_and_wav_are_not_audio_embeds_failure(self) -> None:
        src = SRC.read_text(encoding="utf-8")
        self.assertNotIn("example.com", src)
        self.assertNotIn("wav", src)
        embeds = EMBEDS.read_text(encoding="utf-8")
        self.assertNotIn("wav", embeds.lower())

    def test_player_styles_are_native_and_focusable_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("audio.audio-embed", css)
        self.assertIn("figure.audio-embed", css)
        self.assertIn("audio.audio-embed:focus-visible", css)
        self.assertIn("width: 100%", css)
        self.assertIn("max-width: 100%", css)

    def test_player_is_not_a_fixed_pixel_widget_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        block = css.split("audio.audio-embed", 1)[-1].split("}", 1)[0]
        self.assertNotIn("width: 560px", block)
        self.assertNotIn("height: 315px", block)

    def test_cms_audio_folder_and_author_note_success(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        images_at = yml.find("name: images")
        audio_at = yml.find("name: audio")
        self.assertGreater(images_at, -1)
        self.assertGreater(audio_at, images_at)
        self.assertIn("input: assets/audio/uploads", yml)
        self.assertIn("output: /audio/uploads", yml)
        self.assertIn("extensions: [mp3, m4a, ogg]", yml)
        self.assertIn("extensions: [jpg, jpeg, png, webp, gif]", yml)
        self.assertGreaterEqual(yml.count("name: audio_upload"), 4)
        self.assertGreaterEqual(yml.count("media: audio"), 4)
        self.assertGreaterEqual(yml.count("10 MB"), 8)
        self.assertGreaterEqual(
            yml.count("Paste a YouTube or X/Twitter status URL on its own line"), 3
        )
        readme = README.read_text(encoding="utf-8")
        self.assertIn("/audio/uploads/", readme)
        self.assertIn("10 MB", readme)
        self.assertIn("audio shortcode", readme.lower())
        script = SYNC.read_text(encoding="utf-8")
        self.assertIn("assets/audio/uploads", script)
        self.assertIn("static/audio/uploads", script)
        self.assertIn("assets/images/uploads", script)

    def test_cms_does_not_allow_wav_failure(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        audio_block = yml.split("name: audio", 1)[1].split("content:", 1)[0]
        self.assertNotIn("wav", audio_block.lower())


class AudioEmbedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="audio-embed-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "audio-embed-fixture.md").write_text(
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
        html_path = dest / "posts" / "audio-embed-fixture" / "index.html"
        try:
            cls.html = html_path.read_text(encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_uploaded_audio_urls_and_shortcode_render_a_player_success(self) -> None:
        self.assertIn('class="audio-embed"', self.html)
        self.assertIn("<audio", self.html)
        self.assertIn("controls", self.html)
        self.assertIn('preload="none"', self.html)
        self.assertIn(f'src="{CLIP}"', self.html)
        self.assertIn('src="/audio/uploads/road.ogg"', self.html)
        self.assertIn(f'src="{LEFTOVER}"', self.html)
        self.assertIn('src="/audio/uploads/absolute.mp3"', self.html)
        self.assertIn(f'src="{PART}"', self.html)
        self.assertIn(f'src="{SHORT}"', self.html)
        self.assertIn('aria-label="Locker room"', self.html)
        self.assertIn("<figcaption>After the whistle</figcaption>", self.html)
        self.assertIn('class="post-part"', self.html)
        self.assertEqual(self.html.count('class="audio-embed"'), 6)
        self.assertNotIn(f'<a href="{CLIP}">{CLIP}</a>', self.html)
        self.assertNotIn(f'<a href="{LEFTOVER}">{LEFTOVER}</a>', self.html)
        self.assertNotIn("audio_upload", self.html)

    def test_named_links_wav_and_remote_audio_stay_links_failure(self) -> None:
        self.assertIn(f'<a href="{CLIP}">interview</a>', self.html)
        self.assertIn('<a href="http://kenpom.com">kenpom</a>', self.html)
        self.assertIn(f'<a href="{WAV}">{WAV}</a>', self.html)
        self.assertIn(f'<a href="{REMOTE}">{REMOTE}</a>', self.html)
        self.assertIn(f'<a href="{CLIP}">named clip</a>', self.html)
        self.assertNotIn('src="/audio/uploads/raw.wav"', self.html)
        self.assertNotIn("evil.example", self.html)
        self.assertNotIn("huge.wav", self.html)
        self.assertNotIn("photo.jpg", self.html)
        self.assertNotIn('aria-label="nope"', self.html)
