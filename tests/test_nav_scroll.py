"""Main nav: one horizontal row that scrolls, with edge fades when more is off-screen."""

from __future__ import annotations

import json
import re
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


class NavScrollTemplateTests(unittest.TestCase):
    def test_header_loads_nav_scroll_script_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('"/js/nav-scroll.js"', header)
        self.assertNotIn('" /js/nav-scroll.js"', header)
        self.assertIn('type="module"', header)
        self.assertIn('aria-label="Main navigation"', header)

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


if __name__ == "__main__":
    unittest.main()
