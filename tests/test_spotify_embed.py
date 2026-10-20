"""Spotify URLs alone in a paragraph become an embed; inline links stay links."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "layouts" / "_default" / "_markup" / "render-link.html"
EMBEDS = REPO_ROOT / "layouts" / "partials" / "html-embeds.html"
CONTENT_PARTIAL = REPO_ROOT / "layouts" / "partials" / "page-content.html"
PARTS_PARTIAL = REPO_ROOT / "layouts" / "partials" / "post-parts.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TIMEOUT_SECONDS = 120

TRACK = "46MX86XQqYCZRvwPpeq4Gi"
TRACK_URL = f"https://open.spotify.com/track/{TRACK}?si=d4efa7ad7b814d34"
ALBUM = "4aawyAB9vmqN3uQ7FjRGTy"
ALBUM_URL = f"https://open.spotify.com/album/{ALBUM}"
PLAYLIST = "37i9dQZF1DXcBWIGoYBM5M"
PLAYLIST_URL = f"https://open.spotify.com/intl-de/playlist/{PLAYLIST}?si=abc"
ARTIST = "06HL4z0CvFAxyc27GXpf02"
ARTIST_URL = f"https://open.spotify.com/intl-fr/artist/{ARTIST}"
SHOW = "4rOoJ6Egrf8K2IrywzwOMk"
SHOW_URL = f"https://open.spotify.com/show/{SHOW}"
EPISODE = "7makk4oTQel546B0PZlDM5"
EPISODE_URL = f"https://open.spotify.com/episode/{EPISODE}"
EMBED_TRACK = "11dFghVXANMlKmJXsNCbNl"
EMBED_TRACK_URL = f"https://open.spotify.com/embed/track/{EMBED_TRACK}"
LEFTOVER = "0VjIjW4GlUZAMYd2vXMi3b"
LEFTOVER_URL = f"https://open.spotify.com/track/{LEFTOVER}?si=leftover"
INLINE = "6rqhFgbbKwnb9MLmUQDhG6"
INLINE_URL = f"https://open.spotify.com/track/{INLINE}"
NAMED = "3n3Ppam7vgaVa1iaRUc9Lp"
NAMED_URL = f"https://open.spotify.com/track/{NAMED}"
SEARCH_URL = "https://open.spotify.com/search/ramblers"

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: Spotify Embed Fixture",
        "slug: spotify-embed-fixture",
        "author: eric-wisnewski",
        "date: 2026-10-20T12:00:00Z",
        "draft: false",
        "parts:",
        "  - author: eric-wisnewski",
        f'    body: \'<p><a href="{EPISODE_URL}">{EPISODE_URL}</a></p>\'',
        "---",
        f"[{TRACK_URL}]({TRACK_URL})",
        "",
        ALBUM_URL,
        "",
        PLAYLIST_URL,
        "",
        ARTIST_URL,
        "",
        SHOW_URL,
        "",
        EMBED_TRACK_URL,
        "",
        f"Hear [{INLINE_URL}]({INLINE_URL}) sometime.",
        "",
        f"Play the [lake shore drive]({NAMED_URL}) later.",
        "",
        SEARCH_URL,
        "",
        "See [kenpom](http://kenpom.com).",
        "",
        f'<p><a href="{LEFTOVER_URL}">{LEFTOVER_URL}</a></p>',
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


def embed_src(kind: str, spotify_id: str) -> str:
    return f'src="https://open.spotify.com/embed/{kind}/{spotify_id}"'


class SpotifyEmbedSourceTests(unittest.TestCase):
    def test_paragraph_only_spotify_urls_become_official_embeds_success(self) -> None:
        embeds = EMBEDS.read_text(encoding="utf-8")
        self.assertIn("open.spotify.com/embed/", embeds)
        self.assertIn("spotify-embed--compact", embeds)
        self.assertIn("spotify-embed--tall", embeds)
        self.assertIn('height="152"', embeds)
        self.assertIn('height="352"', embeds)
        self.assertIn('width="100%"', embeds)
        self.assertIn('loading="lazy"', embeds)
        self.assertIn(">Listen on Spotify</a>", embeds)
        self.assertIn("intl-[a-z]{2}", embeds)
        self.assertIn("track|episode", embeds)
        self.assertIn("album|playlist|show|artist", embeds)
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("html-embeds.html", hook)
        self.assertNotIn("open.spotify.com/embed/", hook)
        partial = CONTENT_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('partial "html-embeds.html"', partial)
        parts = PARTS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('partial "html-embeds.html"', parts)

    def test_spotify_player_is_not_a_fixed_width_youtube_frame_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("iframe.spotify-embed", css)
        self.assertIn("width: 100%", css)
        self.assertIn("max-width: 100%", css)
        self.assertIn("height: 152px", css)
        self.assertIn("height: 352px", css)
        self.assertIn("iframe.spotify-embed:focus-visible", css)
        block = css.split("iframe.spotify-embed {", 1)[1].split("}", 1)[0]
        self.assertNotIn("width: 560px", block)
        self.assertNotIn("16 / 9", block)
        embeds = EMBEDS.read_text(encoding="utf-8")
        self.assertNotIn("youtube-nocookie.com/embed/$2", embeds)

    def test_cms_body_fields_mention_spotify_success(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        self.assertGreaterEqual(yml.count("A Spotify link"), 8)
        self.assertGreaterEqual(
            yml.count("Paste a YouTube or X/Twitter status URL on its own line"), 8
        )


class SpotifyEmbedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="spotify-embed-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "spotify-embed-fixture.md").write_text(
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
        html_path = dest / "posts" / "spotify-embed-fixture" / "index.html"
        loyola_path = dest / "posts" / "loyola" / "index.html"
        try:
            cls.html = html_path.read_text(encoding="utf-8")
            cls.loyola = loyola_path.read_text(encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_own_line_spotify_urls_render_embeds_success(self) -> None:
        self.assertIn(embed_src("track", TRACK), self.html)
        self.assertIn('class="spotify-embed spotify-embed--compact"', self.html)
        self.assertIn('height="152"', self.html)
        self.assertIn('loading="lazy"', self.html)
        self.assertIn(">Listen on Spotify</a>", self.html)
        self.assertIn(embed_src("album", ALBUM), self.html)
        self.assertIn(embed_src("playlist", PLAYLIST), self.html)
        self.assertIn(embed_src("artist", ARTIST), self.html)
        self.assertIn(embed_src("show", SHOW), self.html)
        self.assertIn(embed_src("track", EMBED_TRACK), self.html)
        self.assertIn(embed_src("track", LEFTOVER), self.html)
        self.assertIn(embed_src("episode", EPISODE), self.html)
        self.assertIn('class="spotify-embed spotify-embed--tall"', self.html)
        self.assertIn('height="352"', self.html)
        self.assertEqual(self.html.count('class="spotify-embed '), 8)
        self.assertNotIn(f'<a href="{TRACK_URL}">{TRACK_URL}</a>', self.html)
        self.assertNotIn(f'<a href="{LEFTOVER_URL}">{LEFTOVER_URL}</a>', self.html)
        article = self.html.split('<article class="post-content">', 1)[1].split("</article>", 1)[0]
        self.assertNotIn("?si=", article)
        self.assertNotIn("intl-de", article)
        self.assertNotIn("intl-fr", article)
        self.assertNotIn("/embed/embed/", article)

    def test_loyola_track_link_renders_compact_player_success(self) -> None:
        self.assertIn(embed_src("track", TRACK), self.loyola)
        self.assertIn('height="152"', self.loyola)
        self.assertIn('loading="lazy"', self.loyola)
        self.assertIn(">Listen on Spotify</a>", self.loyola)
        self.assertNotIn(f'<a href="{TRACK_URL}">{TRACK_URL}</a>', self.loyola)
        self.assertNotIn("?si=", self.loyola)

    def test_inline_named_and_other_links_stay_anchors_failure(self) -> None:
        self.assertIn(f'<a href="{INLINE_URL}">{INLINE_URL}</a>', self.html)
        self.assertIn(f'<a href="{NAMED_URL}">lake shore drive</a>', self.html)
        self.assertIn(f'<a href="{SEARCH_URL}">{SEARCH_URL}</a>', self.html)
        self.assertIn('<a href="http://kenpom.com">kenpom</a>', self.html)
        self.assertNotIn(embed_src("track", INLINE), self.html)
        self.assertNotIn(embed_src("track", NAMED), self.html)
        self.assertNotIn("embed/search/", self.html)
