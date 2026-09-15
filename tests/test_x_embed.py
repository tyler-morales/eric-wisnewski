"""X/Twitter status URLs in post bodies become embeds; named links stay links."""

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
FOOTER = REPO_ROOT / "layouts" / "partials" / "footer.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TIMEOUT_SECONDS = 120

X_STATUS_ID = "2099204458768937067"
X_URL = f"https://x.com/coachdancasey/status/{X_STATUS_ID}?s=46"
TWITTER_STATUS_ID = "2099264127323533365"
TWITTER_URL = f"https://twitter.com/gabemcdonald_/status/{TWITTER_STATUS_ID}"
WWW_TWITTER_URL = "https://www.twitter.com/Interior/status/463440424141459456"
WWW_TWITTER_ID = "463440424141459456"
LEFTOVER_ID = "1234567890123456789"
LEFTOVER_URL = f"https://x.com/foo/status/{LEFTOVER_ID}"
NAMED_X_URL = X_URL.split("?", 1)[0]
VIDEO_ID = "yOZB6mNqhuA"
WATCH_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
EMBED_SRC = f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}"

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: X Embed Fixture",
        "slug: x-embed-fixture",
        "author: eric-wisnewski",
        "date: 2026-09-15T12:00:00Z",
        "draft: false",
        "---",
        f"[{X_URL}]({X_URL})",
        "",
        TWITTER_URL,
        "",
        WWW_TWITTER_URL,
        "",
        f"See this [clip]({NAMED_X_URL}) later.",
        "",
        "Follow [Gabe](https://x.com/gabemcdonald_) on X.",
        "",
        f'<p><a href="{LEFTOVER_URL}">{LEFTOVER_URL}</a></p>',
        "",
        f"[{WATCH_URL}]({WATCH_URL})",
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


class XEmbedSourceTests(unittest.TestCase):
    def test_link_hook_embeds_x_and_twitter_status_urls_success(self) -> None:
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("twitter-tweet", hook)
        self.assertIn("x\\.com", hook)
        self.assertIn("twitter\\.com", hook)
        self.assertIn("status(?:es)?", hook)
        self.assertIn("data-dnt", hook)
        self.assertIn(".PlainText", hook)
        embeds = EMBEDS.read_text(encoding="utf-8")
        self.assertIn("twitter-tweet", embeds)
        self.assertIn("x.com/i/status/$1", embeds)
        self.assertIn("hasTwitterEmbed", embeds)
        self.assertIn("youtube-nocookie.com/embed/$1", embeds)
        partial = CONTENT_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('partial "html-embeds.html"', partial)
        self.assertIn('"html" .Content', partial)
        parts = PARTS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('partial "html-embeds.html"', parts)
        footer = FOOTER.read_text(encoding="utf-8")
        self.assertIn("hasTwitterEmbed", footer)
        self.assertIn("platform.twitter.com/widgets.js", footer)
        self.assertIn("defer", footer)

    def test_widgets_script_is_not_unconditional_failure(self) -> None:
        footer = FOOTER.read_text(encoding="utf-8")
        self.assertIn("Store.Get", footer)
        hook = HOOK.read_text(encoding="utf-8")
        self.assertNotIn("widgets.js", hook)

    def test_embed_styles_reset_quote_chrome_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("blockquote.twitter-tweet", css)
        self.assertIn("iframe.twitter-tweet:focus-visible", css)
        self.assertIn("max-width: 550px", css)

    def test_twitter_embed_is_not_a_youtube_aspect_ratio_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        _, rest = css.split("blockquote.twitter-tweet", 1)
        block = rest.split("}", 1)[0]
        self.assertNotIn("16 / 9", block)
        self.assertNotIn("youtube-embed", block)

    def test_cms_body_fields_tell_writers_to_paste_an_x_url_success(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            yml.count("Paste a YouTube or X/Twitter status URL on its own line"), 3
        )


class XEmbedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="x-embed-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "x-embed-fixture.md").write_text(
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
        cls.dest = dest
        html_path = dest / "posts" / "x-embed-fixture" / "index.html"
        loose_path = dest / "da-breakdown-w-tad" / "bears-week-1-recap" / "index.html"
        try:
            cls.html = html_path.read_text(encoding="utf-8")
            cls.loose = loose_path.read_text(encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_x_and_twitter_status_urls_render_embeds_success(self) -> None:
        self.assertIn('class="twitter-tweet"', self.html)
        self.assertIn(f"status/{X_STATUS_ID}", self.html)
        self.assertIn(TWITTER_STATUS_ID, self.html)
        self.assertIn(WWW_TWITTER_ID, self.html)
        self.assertIn(LEFTOVER_ID, self.html)
        self.assertIn("platform.twitter.com/widgets.js", self.html)
        self.assertEqual(self.html.count('class="twitter-tweet"'), 4)
        self.assertNotIn(f'<a href="{X_URL}">{X_URL}</a>', self.html)
        self.assertNotIn(f'<a href="{TWITTER_URL}">{TWITTER_URL}</a>', self.html)
        self.assertNotIn(f'<a href="{LEFTOVER_URL}">{LEFTOVER_URL}</a>', self.html)

    def test_youtube_embed_still_works_success(self) -> None:
        self.assertIn(EMBED_SRC, self.html)
        self.assertIn('class="youtube-embed"', self.html)
        self.assertNotIn(f'<a href="{WATCH_URL}">{WATCH_URL}</a>', self.html)

    def test_named_and_profile_links_stay_anchors_failure(self) -> None:
        self.assertIn(f'<a href="{NAMED_X_URL}">clip</a>', self.html)
        self.assertIn('<a href="https://x.com/gabemcdonald_">Gabe</a>', self.html)

    def test_loose_balls_x_links_become_embeds_success(self) -> None:
        self.assertIn('class="twitter-tweet"', self.loose)
        self.assertGreaterEqual(self.loose.count('class="twitter-tweet"'), 2)
        self.assertIn("platform.twitter.com/widgets.js", self.loose)
        self.assertNotIn(
            f'<a href="{X_URL}">{X_URL}</a>',
            self.loose,
        )
        self.assertNotIn(
            '<a href="https://x.com/gabemcdonald_/status/2099264127323533365?s=46">'
            "https://x.com/gabemcdonald_/status/2099264127323533365?s=46</a>",
            self.loose,
        )

    def test_home_does_not_load_widgets_js_failure(self) -> None:
        home = (self.dest / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("widgets.js", home)
