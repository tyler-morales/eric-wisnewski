"""Main nav: one horizontal row that scrolls, with edge fades when more is off-screen."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NAV_JS = REPO_ROOT / "static" / "js" / "nav-scroll.js"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
HUGO_TIMEOUT_SECONDS = 120


def call_nav(fn_name: str, script_body: str) -> object:
    if not NAV_JS.is_file():
        raise FileNotFoundError(NAV_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(NAV_JS.as_uri())};\n"
        + script_body
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
    if not match:
        raise AssertionError(f"selector not found in CSS: {selector!r}")
    return match.group(1)


def run_hugo(*, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hugo", "--destination", str(destination), "--quiet", "--noBuildLock"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class NavScrollLogicTests(unittest.TestCase):
    def test_fade_when_more_content_exists_success(self) -> None:
        start = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(0, 320, 800)));",
        )
        middle = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(200, 320, 800)));",
        )
        end = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(480, 320, 800)));",
        )
        self.assertEqual(start, {"start": False, "end": True})
        self.assertEqual(middle, {"start": True, "end": True})
        self.assertEqual(end, {"start": True, "end": False})

    def test_no_fade_when_content_fits_failure(self) -> None:
        fits = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(0, 800, 400)));",
        )
        exact = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(0, 400, 400)));",
        )
        self.assertEqual(fits, {"start": False, "end": False})
        self.assertEqual(exact, {"start": False, "end": False})

    def test_scrollFadeState_invalid_inputs_failure(self) -> None:
        bogus = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState('x', 0, null)));",
        )
        zero_view = call_nav(
            "scrollFadeState",
            "console.log(JSON.stringify(scrollFadeState(0, 0, 800)));",
        )
        self.assertEqual(bogus, {"start": False, "end": False})
        self.assertEqual(zero_view, {"start": False, "end": False})

    def test_apply_toggles_fade_classes_success(self) -> None:
        result = call_nav(
            "applyScrollFade",
            """
            const classes = new Set();
            const nav = {
              classList: {
                toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }
              }
            };
            const state = applyScrollFade(nav, { scrollLeft: 80, clientWidth: 320, scrollWidth: 800 });
            console.log(JSON.stringify({ classes: [...classes].sort(), state }));
            """,
        )
        self.assertEqual(result["classes"], ["site-nav--fade-end", "site-nav--fade-start"])
        self.assertEqual(result["state"], {"start": True, "end": True})

    def test_apply_clears_fade_when_content_fits_failure(self) -> None:
        result = call_nav(
            "applyScrollFade",
            """
            const classes = new Set(['site-nav--fade-start', 'site-nav--fade-end']);
            const nav = {
              classList: {
                toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }
              }
            };
            const state = applyScrollFade(nav, { scrollLeft: 0, clientWidth: 800, scrollWidth: 400 });
            console.log(JSON.stringify({ classes: [...classes].sort(), state }));
            """,
        )
        self.assertEqual(result["classes"], [])
        self.assertEqual(result["state"], {"start": False, "end": False})


class ActiveTabScrollTests(unittest.TestCase):
    def test_centers_active_tab_success(self) -> None:
        centered = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft(0, 300, 1000, 600, 100, 0)));",
        )
        already = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft(100, 200, 1000, 150, 50, 50)));",
        )
        self.assertEqual(centered, 500)
        self.assertEqual(already, 125)

    def test_clamps_and_rejects_bogus_metrics_failure(self) -> None:
        at_start = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft(0, 400, 800, 10, 40, 0)));",
        )
        at_end = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft(0, 100, 200, 180, 20, 0)));",
        )
        bogus = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft('x', 0, null, 10, 10, 0)));",
        )
        zero_view = call_nav(
            "activeTabScrollLeft",
            "console.log(JSON.stringify(activeTabScrollLeft(12, 0, 800, 10, 10, 0)));",
        )
        self.assertEqual(at_start, 0)
        self.assertEqual(at_end, 100)
        self.assertEqual(bogus, 0)
        self.assertEqual(zero_view, 12)

    def test_reduced_motion_still_scrolls_the_nav_success(self) -> None:
        result = call_nav(
            "centerActiveTab, prefersReducedMotion",
            """
            globalThis.matchMedia = () => ({ matches: true });
            const calls = [];
            const active = { getBoundingClientRect() { return { left: 600, width: 100 }; } };
            const scroller = {
              scrollLeft: 0,
              clientWidth: 300,
              scrollWidth: 1000,
              querySelector() { return active; },
              getBoundingClientRect() { return { left: 0, width: 300 }; },
              scrollTo(opts) { calls.push(opts); }
            };
            const left = centerActiveTab(scroller);
            console.log(JSON.stringify({
              left,
              scrollLeft: scroller.scrollLeft,
              calls,
              reduced: prefersReducedMotion()
            }));
            """,
        )
        self.assertTrue(result["reduced"])
        self.assertEqual(result["left"], 500)
        self.assertEqual(result["scrollLeft"], 500)
        self.assertEqual(result["calls"], [])

    def test_missing_active_tab_does_not_scroll_failure(self) -> None:
        result = call_nav(
            "centerActiveTab",
            """
            globalThis.matchMedia = () => ({ matches: false });
            const scroller = {
              scrollLeft: 40,
              querySelector() { return null; },
              scrollTo() { throw new Error('should not scroll'); }
            };
            console.log(JSON.stringify({ left: centerActiveTab(scroller), scrollLeft: scroller.scrollLeft }));
            """,
        )
        self.assertIsNone(result["left"])
        self.assertEqual(result["scrollLeft"], 40)

    def test_nav_scroll_does_not_move_the_page_failure(self) -> None:
        js = NAV_JS.read_text(encoding="utf-8")
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        for text in (js, header):
            self.assertNotIn("scrollIntoView", text)
            self.assertNotIn("window.scroll", text)
            self.assertNotRegex(text, r"behavior:\s*['\"]smooth['\"]")
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("prefers-reduced-motion", header)
        self.assertIn("scrollLeft", js)
        self.assertIn("scrollLeft", header)


class NavScrollTemplateTests(unittest.TestCase):
    def test_header_loads_nav_scroll_script_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('"/js/nav-scroll.js"', header)
        self.assertNotIn('" /js/nav-scroll.js"', header)
        self.assertIn('type="module"', header)
        self.assertIn('aria-label="Main navigation"', header)

    def test_current_section_is_marked_in_the_header_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("not .IsHome", header)
        self.assertIn('eq .Section "posts"', header)
        self.assertIn('hasPrefix .RelPermalink "/erics-d1-mission"', header)
        self.assertIn('eq .Section "gradys-tour"', header)
        self.assertIn('eq .Section "da-breakdown-w-tad"', header)
        self.assertIn('eq .Section "jeremy-on-tap"', header)
        self.assertEqual(header.count('aria-current="page"{{ end }}'), 4)
        for gate, key in (
            ("has-da-breakdown-posts.html", "da-breakdown-w-tad"),
            ("has-jeremy-on-tap-posts.html", "jeremy-on-tap"),
        ):
            gate_at = header.find(gate)
            current_at = header.find(f'eq $navCurrent "{key}"')
            end_at = header.find("{{ end }}", current_at)
            self.assertGreater(gate_at, -1)
            self.assertGreater(current_at, gate_at)
            self.assertGreater(end_at, current_at)
            self.assertIn("aria-current=\"page\"", header[current_at:end_at])

    def test_load_scrolls_the_nav_not_the_page_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        ul_end = header.rfind("</ul>")
        inline_at = header.find("previousElementSibling")
        module_at = header.find('type="module"')
        self.assertGreater(ul_end, -1)
        self.assertLess(ul_end, inline_at)
        self.assertLess(inline_at, module_at)
        between = header[ul_end:inline_at]
        self.assertIn("<script>", between)
        self.assertNotIn('type="module"', between)
        self.assertIn("scrollLeft", header)
        self.assertNotIn("scrollIntoView", header)
        css = STYLE_CSS.read_text(encoding="utf-8")
        ul = first_block(css, ".site-nav ul")
        self.assertIn("scroll-behavior: auto", ul)
        current = first_block(css, '.site-nav a[aria-current="page"]')
        self.assertIn("font-weight: 700", current)
        self.assertIn("underline", current)

    def test_nav_list_does_not_wrap_failure(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        block = first_block(css, ".site-nav ul")
        self.assertIn("nowrap", block)
        self.assertIn("overflow-x: auto", block)
        self.assertNotIn("flex-wrap: wrap", block)

    def test_edge_fades_use_white_gradient_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("site-nav--fade-start", css)
        self.assertIn("site-nav--fade-end", css)
        self.assertIn("linear-gradient(to right, var(--bg)", css)
        self.assertIn("linear-gradient(to left, var(--bg)", css)
        before = first_block(css, ".site-nav::before")
        after = first_block(css, ".site-nav::after")
        self.assertIn("pointer-events: none", before)
        self.assertIn("pointer-events: none", after)

    def test_readme_documents_scroll_nav_success(self) -> None:
        text = README.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("scrolls horizontally", lower)
        self.assertIn("white fade", lower)

    def test_home_includes_nav_scroll_script_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "public"
            result = run_hugo(destination=dest)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = (dest / "index.html").read_text(encoding="utf-8")
            self.assertIn("/js/nav-scroll.js", html)
            self.assertNotIn("%20/js/nav-scroll.js", html)
            self.assertNotIn("/ /js/nav-scroll.js", html)
            self.assertIn('aria-label="Main navigation"', html)


NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
CURRENT_RE = re.compile(
    r'<a\b[^>]*\baria-current="page"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


def current_labels(html: str) -> list[str]:
    return [re.sub(r"\s+", " ", label).strip() for label in CURRENT_RE.findall(main_nav_html(html))]


class NavCurrentBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="nav-current-"))
        result = run_hugo(destination=cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(f"hugo build failed:\n{result.stderr}")
        cls.output_dir = cls._output_dir

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def read(self, *parts: str) -> str:
        path = self.output_dir.joinpath(*parts)
        self.assertTrue(path.is_file(), path)
        return path.read_text(encoding="utf-8")

    def test_section_index_and_posts_mark_that_tab_success(self) -> None:
        self.assertEqual(current_labels(self.read("gradys-tour", "index.html")), ["Grady's Tour"])
        grady_posts = [
            path
            for path in (self.output_dir / "gradys-tour").glob("*/index.html")
        ]
        self.assertTrue(grady_posts)
        for path in grady_posts:
            self.assertEqual(
                current_labels(path.read_text(encoding="utf-8")),
                ["Grady's Tour"],
                path,
            )
        self.assertEqual(
            current_labels(self.read("erics-d1-mission", "index.html")),
            ["Eric's D1 Mission"],
        )
        self.assertEqual(
            current_labels(self.read("posts", "boston-college", "index.html")),
            ["Eric's D1 Mission"],
        )
        self.assertEqual(
            current_labels(self.read("da-breakdown-w-tad", "index.html")),
            ["Da Breakdown w Tad"],
        )
        self.assertEqual(
            current_labels(self.read("da-breakdown-w-tad", "bears-week-1-recap", "index.html")),
            ["Da Breakdown w Tad"],
        )

    def test_home_profiles_and_gated_section_mark_nothing_failure(self) -> None:
        self.assertEqual(current_labels(self.read("index.html")), [])
        self.assertEqual(current_labels(self.read("authors", "grady-davis", "index.html")), [])
        self.assertEqual(current_labels(self.read("privacy", "index.html")), [])
        jeremy = self.read("jeremy-on-tap", "index.html")
        self.assertNotIn("Jeremy On Tap", main_nav_html(jeremy))
        self.assertEqual(current_labels(jeremy), [])
        self.assertIn("Grady's Tour", main_nav_html(jeremy))
        self.assertIn("Da Breakdown w Tad", main_nav_html(self.read("index.html")))


if __name__ == "__main__":
    unittest.main()
