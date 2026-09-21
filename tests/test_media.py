"""Home Show more + image skeleton frames (native lazy + shimmer)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEDIA_JS = REPO_ROOT / "static" / "js" / "media.js"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
LIST_TEMPLATE = REPO_ROOT / "layouts" / "_default" / "list.html"
BASEOF = REPO_ROOT / "layouts" / "_default" / "baseof.html"
RENDER_IMAGE = REPO_ROOT / "layouts" / "_default" / "_markup" / "render-image.html"
HTML_EMBEDS = REPO_ROOT / "layouts" / "partials" / "html-embeds.html"
POST_LIST_ITEM = REPO_ROOT / "layouts" / "partials" / "post-list-item.html"
GALLERY_PARTIAL = REPO_ROOT / "layouts" / "partials" / "post-gallery.html"
AUTHOR_CARD = REPO_ROOT / "layouts" / "partials" / "author-card.html"
MORE_FROM = REPO_ROOT / "layouts" / "partials" / "more-from-author.html"
SINGLE = REPO_ROOT / "layouts" / "_default" / "single.html"
README = REPO_ROOT / "README.md"
HUGO_TIMEOUT_SECONDS = 120


def call_media(fn_name: str, script_body: str) -> object:
    if not MEDIA_JS.is_file():
        raise FileNotFoundError(MEDIA_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(MEDIA_JS.as_uri())};\n" + script_body
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


def first_block(css: str, selector: str) -> str:
    pattern = re.compile(re.escape(selector) + r"\s*(?:,[^{]+)?\{([^}]+)\}")
    match = pattern.search(css)
    return match.group(1) if match else ""


class MediaLogicTests(unittest.TestCase):
    def test_next_page_stops_at_total_success(self) -> None:
        self.assertEqual(
            call_media(
                "nextShownCount",
                "console.log(JSON.stringify(nextShownCount(8, 19, 8)));",
            ),
            16,
        )
        self.assertEqual(
            call_media(
                "nextShownCount",
                "console.log(JSON.stringify(nextShownCount(16, 19, 8)));",
            ),
            19,
        )

    def test_next_page_rejects_bad_inputs_failure(self) -> None:
        self.assertEqual(
            call_media(
                "nextShownCount",
                "console.log(JSON.stringify(nextShownCount('x', 20, 0)));",
            ),
            8,
        )
        self.assertEqual(
            call_media(
                "remainingCount",
                "console.log(JSON.stringify(remainingCount(20, 4)));",
            ),
            0,
        )

    def test_more_label_counts_remaining_success(self) -> None:
        self.assertEqual(
            call_media("moreLabel", "console.log(JSON.stringify(moreLabel(11)));"),
            "Show 11 more posts",
        )
        self.assertEqual(
            call_media("moreLabel", "console.log(JSON.stringify(moreLabel(1)));"),
            "Show 1 more post",
        )

    def test_apply_hides_items_beyond_page_success(self) -> None:
        result = call_media(
            "applyPostListPage",
            """
            const items = [0, 1, 2, 3, 4].map(() => {
              const classes = new Set();
              return {
                classList: {
                  toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
                  _classes: classes,
                },
              };
            });
            const state = applyPostListPage(items, 2);
            console.log(JSON.stringify({
              state,
              paged: items.map((item) => item.classList._classes.has('is-paged-out')),
            }));
            """,
        )
        self.assertEqual(result["state"], {"shown": 2, "total": 5, "remaining": 3})
        self.assertEqual(result["paged"], [False, False, True, True, True])

    def test_apply_empty_list_failure(self) -> None:
        result = call_media(
            "applyPostListPage",
            "console.log(JSON.stringify(applyPostListPage(null, 8)));",
        )
        self.assertEqual(result, {"shown": 0, "total": 0, "remaining": 0})

    def test_frame_loaded_and_error_success(self) -> None:
        loaded = call_media(
            "setMediaFrameState",
            """
            const classes = new Set();
            const frame = {
              classList: {
                add(name) { classes.add(name); },
                remove(name) { classes.delete(name); },
              },
            };
            const status = setMediaFrameState(frame, { complete: true, naturalWidth: 640 });
            console.log(JSON.stringify({ status, classes: [...classes].sort() }));
            """,
        )
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(loaded["classes"], ["is-loaded"])

        broken = call_media(
            "setMediaFrameState",
            """
            const classes = new Set();
            const frame = {
              classList: {
                add(name) { classes.add(name); },
                remove(name) { classes.delete(name); },
              },
            };
            const status = setMediaFrameState(frame, { complete: true, naturalWidth: 0 });
            console.log(JSON.stringify({ status, classes: [...classes].sort() }));
            """,
        )
        self.assertEqual(broken["status"], "error")
        self.assertEqual(broken["classes"], ["is-error"])

    def test_frame_still_loading_failure(self) -> None:
        result = call_media(
            "setMediaFrameState",
            """
            const classes = new Set(['is-loaded']);
            const frame = {
              classList: {
                add(name) { classes.add(name); },
                remove(name) { classes.delete(name); },
              },
            };
            const status = setMediaFrameState(frame, { complete: false, naturalWidth: 0 });
            console.log(JSON.stringify({ status, classes: [...classes].sort() }));
            """,
        )
        self.assertEqual(result["status"], "loading")
        self.assertEqual(result["classes"], [])
        self.assertFalse(
            call_media(
                "mediaFrameLoaded",
                "console.log(JSON.stringify(mediaFrameLoaded({ complete: true, naturalWidth: 0 })));",
            )
        )


class MediaSourceTests(unittest.TestCase):
    def test_home_has_show_more_not_paginator_success(self) -> None:
        template = LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(".IsHome", template)
        self.assertIn("data-post-list-more", template)
        self.assertIn("Show more posts", template)
        self.assertIn("<button type=\"button\"", template)
        self.assertNotIn(".Paginate", template)
        self.assertNotIn("pagination", template)
        self.assertIn('partial "post-count.html"', template)

    def test_images_use_media_frame_and_native_lazy_success(self) -> None:
        item = POST_LIST_ITEM.read_text(encoding="utf-8")
        hook = RENDER_IMAGE.read_text(encoding="utf-8")
        gallery = GALLERY_PARTIAL.read_text(encoding="utf-8")
        card = AUTHOR_CARD.read_text(encoding="utf-8")
        more = MORE_FROM.read_text(encoding="utf-8")
        single = SINGLE.read_text(encoding="utf-8")
        embeds = HTML_EMBEDS.read_text(encoding="utf-8")
        self.assertIn("media-frame", item)
        self.assertIn('loading="lazy"', item)
        self.assertIn("media-frame", hook)
        self.assertIn('loading="lazy"', hook)
        self.assertIn("media-frame", gallery)
        self.assertIn("media-frame", card)
        self.assertIn("media-frame", more)
        self.assertIn("media-frame", single)
        self.assertIn('fetchpriority="high"', single)
        self.assertIn("media-frame", embeds)
        self.assertIn("<p", embeds)

    def test_no_infinite_scroll_observer_failure(self) -> None:
        js = MEDIA_JS.read_text(encoding="utf-8")
        self.assertNotIn("IntersectionObserver", js)
        self.assertNotIn("infinite", js.lower())
        baseof = BASEOF.read_text(encoding="utf-8")
        self.assertIn("static/js/media.js", baseof)
        self.assertIn("$mediaJS", baseof)

    def test_shimmer_respects_reduced_motion_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("@keyframes media-shimmer", css)
        self.assertIn(".media-frame::after", css)
        self.assertIn(".media-frame.is-loaded::after", css)
        self.assertIn(".post-list-item.is-paged-out", css)
        reduced = css.split("@media (prefers-reduced-motion: reduce)", 1)[-1]
        self.assertIn("media-shimmer", reduced)
        self.assertIn("animation: none", first_block(reduced, ".media-frame::after") or reduced)
        self.assertIn(".post-list-more-button:focus-visible", css)
        self.assertIn(".post-count", css)


class MediaBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="media-hugo-"))
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(cls._output_dir),
                "--quiet",
                "--noBuildLock",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.intro = (
            cls._output_dir / "posts" / "an-introduction" / "index.html"
        ).read_text(encoding="utf-8")
        cls.bc = (
            cls._output_dir / "posts" / "boston-college" / "index.html"
        ).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        output_dir = getattr(cls, "_output_dir", None)
        if output_dir is not None:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_home_keeps_every_post_in_html_success(self) -> None:
        items = re.findall(r'class="[^"]*\bpost-list-item\b', self.home)
        self.assertGreater(len(items), 8)
        self.assertIn("data-post-list-more", self.home)
        self.assertIn("Show more posts", self.home)
        self.assertIn("/js/media.js", self.home)
        self.assertNotIn("/page/2/", self.home)
        self.assertIn('class="post-count"', self.home)
        self.assertIn(f"{len(items)} posts", self.home)

    def test_body_images_are_framed_and_lazy_success(self) -> None:
        self.assertIn("media-frame", self.intro)
        self.assertIn('loading="lazy"', self.intro)
        self.assertIn("media-frame", self.bc)
        self.assertIn("/images/uploads/IMG_3648.jpeg", self.bc)

    def test_home_does_not_use_numbered_pager_failure(self) -> None:
        self.assertNotIn("class=\"pagination\"", self.home)
        self.assertNotRegex(self.home, r">\s*Next\s*<")
        self.assertNotIn("IntersectionObserver", self.home)


class MediaDocsTests(unittest.TestCase):
    def test_readme_covers_show_more_and_skeletons_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("Show more", readme)
        self.assertIn("skeleton", readme.lower())
        self.assertIn("loading=\"lazy\"", readme)

    def test_readme_does_not_promise_infinite_scroll_failure(self) -> None:
        readme = README.read_text(encoding="utf-8").lower()
        self.assertNotIn("infinite scroll", readme)
        self.assertNotIn("/page/2", readme)


if __name__ == "__main__":
    unittest.main()
