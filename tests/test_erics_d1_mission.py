"""Eric's D1 Mission hub: map iframe + school list + his posts, one nav tab."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
NAV_SECTIONS = REPO_ROOT / "layouts" / "partials" / "nav-section-pages.html"
MISSION_LAYOUT = REPO_ROOT / "layouts" / "_default" / "erics-d1-mission.html"
MISSION_CONTENT = REPO_ROOT / "content" / "erics-d1-mission.md"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
REDIRECTS = REPO_ROOT / "static" / "_redirects"
README = REPO_ROOT / "README.md"
MISSION_JS = REPO_ROOT / "static" / "js" / "d1-mission.js"
HUGO_TIMEOUT_SECONDS = 120

NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label="Main navigation"[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
POST_LIST_RE = re.compile(r'<ul class="post-list">(.*?)</ul>', re.DOTALL)
TITLE_RE = re.compile(r'class="post-list-title"[^>]*>(.*?)</(?:span|a)>', re.DOTALL)


def main_nav_html(html: str) -> str:
    match = NAV_RE.search(html)
    return match.group(1) if match else ""


def post_list_titles(html: str) -> list[str]:
    match = POST_LIST_RE.search(html)
    if not match:
        return []
    return [re.sub(r"\s+", " ", title).strip() for title in TITLE_RE.findall(match.group(1))]


def call_mission(fn_name: str, script_body: str) -> object:
    if not MISSION_JS.is_file():
        raise FileNotFoundError(MISSION_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(MISSION_JS.as_uri())};\n"
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


def run_hugo(*, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hugo", "--destination", str(destination), "--quiet", "--noBuildLock"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class EricsD1MissionTemplateTests(unittest.TestCase):
    def test_nav_has_one_mission_tab_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("Eric's D1 Mission", header)
        self.assertIn("nav_erics_d1_mission", header)
        self.assertIn("/erics-d1-mission/", header)
        self.assertNotIn("nav_school_sheets", header)
        self.assertNotIn("nav_map", header)
        self.assertNotIn("List of College Stadiums", header)
        self.assertNotRegex(header, r">Map</a>")

    def test_nav_sections_point_at_the_hub_success(self) -> None:
        nav = NAV_SECTIONS.read_text(encoding="utf-8")
        self.assertIn("/erics-d1-mission", nav)
        self.assertNotIn("/school-sheets", nav)
        self.assertNotIn("/map", nav)

    def test_hub_layout_embeds_map_list_and_posts_success(self) -> None:
        layout = MISSION_LAYOUT.read_text(encoding="utf-8")
        self.assertTrue(MISSION_CONTENT.is_file())
        content = MISSION_CONTENT.read_text(encoding="utf-8")
        self.assertIn("layout: erics-d1-mission", content)
        self.assertRegex(content, r"(?m)^description:")
        self.assertIn("stadium", content.lower())
        self.assertIn("maps/d/embed", layout)
        self.assertIn('id="map"', layout)
        self.assertIn('id="list"', layout)
        self.assertIn('id="posts"', layout)
        self.assertIn('partial "school-sheets.html"', layout)
        self.assertIn('partial "post-list-item.html"', layout)
        self.assertIn('Section" "eq" "posts"', layout)
        self.assertIn('partial "subscribe.html"', layout)
        self.assertIn("/js/school-sheets.js", layout)
        self.assertNotIn('" /js/school-sheets.js"', layout)
        self.assertIn('data-d1-nav', layout)
        self.assertIn('aria-label="Eric\'s D1 Mission sections"', layout)
        self.assertIn('href="#posts"', layout)
        self.assertIn('href="#map"', layout)
        self.assertIn('href="#list"', layout)
        self.assertIn("/js/d1-mission.js", layout)
        self.assertNotIn('" /js/d1-mission.js"', layout)
        posts_at = layout.find('href="#posts"')
        map_at = layout.find('href="#map"')
        list_at = layout.find('href="#list"')
        self.assertLess(posts_at, map_at)
        self.assertLess(map_at, list_at)
        self.assertLess(layout.find('id="posts"'), layout.find('id="map"'))
        self.assertLess(layout.find('id="map"'), layout.find('id="list"'))

    def test_hub_layout_does_not_mix_other_authors_failure(self) -> None:
        layout = MISSION_LAYOUT.read_text(encoding="utf-8")
        self.assertNotIn("gradys-tour", layout)
        self.assertNotIn("da-breakdown-w-tad", layout)
        self.assertNotIn("jeremy-on-tap", layout)

    def test_old_urls_redirect_to_the_hub_success(self) -> None:
        text = REDIRECTS.read_text(encoding="utf-8")
        self.assertIn("/map /erics-d1-mission/", text)
        self.assertIn("/map/ /erics-d1-mission/", text)
        self.assertIn("/school-sheets /erics-d1-mission/", text)
        self.assertIn("/school-sheets/ /erics-d1-mission/", text)

    def test_hugo_toml_drops_old_nav_params_failure(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIn("nav_erics_d1_mission", toml)
        self.assertNotIn("nav_school_sheets", toml)
        self.assertNotIn("nav_map", toml)
        self.assertIn("school_sheets_csv_url", toml)
        self.assertIn("map_viewer_url", toml)

    def test_readme_documents_the_hub_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("Eric's D1 Mission", readme)
        self.assertIn("/erics-d1-mission/", readme)
        self.assertIn("nav_erics_d1_mission", readme)
        self.assertIn("sub-nav", readme)


class EricsD1MissionPanelTests(unittest.TestCase):
    def test_hash_selects_known_panels_success(self) -> None:
        self.assertEqual(
            call_mission(
                "panelFromHash",
                "console.log(JSON.stringify(["
                "panelFromHash('#map'),"
                "panelFromHash('#list'),"
                "panelFromHash('#posts')"
                "]));",
            ),
            ["map", "list", "posts"],
        )

    def test_unknown_hash_falls_back_to_posts_failure(self) -> None:
        self.assertEqual(
            call_mission(
                "panelFromHash",
                "console.log(JSON.stringify(["
                "panelFromHash(''),"
                "panelFromHash('#nope'),"
                "panelFromHash('MAP')"
                "]));",
            ),
            ["posts", "posts", "map"],
        )


class EricsD1MissionBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="d1-mission-hugo-"))
        result = run_hugo(destination=cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        hub = cls._output_dir / "erics-d1-mission" / "index.html"
        cls.hub = hub.read_text(encoding="utf-8") if hub.is_file() else ""
        home = cls._output_dir / "index.html"
        cls.home = home.read_text(encoding="utf-8") if home.is_file() else ""

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_hub_page_builds_with_map_list_and_eric_posts_success(self) -> None:
        self.assertTrue(self.hub, "erics-d1-mission must be in the build")
        nav = main_nav_html(self.hub)
        self.assertIn("Eric's D1 Mission", nav)
        self.assertIn("/erics-d1-mission/", nav)
        self.assertIn('id="map"', self.hub)
        self.assertIn("google.com/maps/d/embed", self.hub)
        self.assertIn('title="Map of Division I college basketball stadiums"', self.hub)
        self.assertIn('id="list"', self.hub)
        self.assertTrue(
            'id="school-sheets-table"' in self.hub
            or "school-sheets-fallback" in self.hub,
            "hub must render the school table or the CSV fallback",
        )
        self.assertIn("/js/school-sheets.js", self.hub)
        self.assertIn('data-d1-nav', self.hub)
        self.assertIn('aria-label="Eric\'s D1 Mission sections"', self.hub)
        self.assertIn('href="#posts"', self.hub)
        self.assertIn("/js/d1-mission.js", self.hub)
        titles = post_list_titles(self.hub)
        self.assertTrue(titles, "hub must list Eric's posts")
        blob = " ".join(titles)
        self.assertIn("An Introduction", blob)
        self.assertIn("Boston College", blob)
        self.assertIn("Northern Illinois", blob)
        self.assertIn('id="subscribe"', self.hub)
        self.assertIn('data-default-list="posts"', self.hub)
        self.assertIn('data-d1-nav', self.hub)
        self.assertIn("/js/d1-mission.js", self.hub)
        self.assertRegex(self.hub, r'href="#posts">\s*Posts\s*</a>')
        self.assertRegex(self.hub, r'href="#map">\s*Map\s*</a>')
        self.assertRegex(self.hub, r'href="#list">\s*List of Stadiums\s*</a>')
        self.assertIn('aria-label="Eric\'s D1 Mission sections"', self.hub)
        self.assertIn(">Posts</a>", self.hub)
        self.assertIn(">Map</a>", self.hub)
        self.assertIn(">List of Stadiums</a>", self.hub)
        self.assertIn("/js/d1-mission.js", self.hub)

    def test_hub_post_list_excludes_other_sections_failure(self) -> None:
        titles = post_list_titles(self.hub)
        blob = " ".join(titles).lower()
        self.assertNotIn("bike", blob)
        self.assertNotIn("bayeux", blob)
        self.assertNotIn("bears", blob)
        self.assertNotIn("blackhawk", blob)

    def test_old_nav_labels_are_gone_failure(self) -> None:
        nav = main_nav_html(self.home)
        self.assertNotIn("List of College Stadiums", nav)
        self.assertNotRegex(nav, r">Map</a>")
        self.assertFalse((self._output_dir / "map" / "index.html").is_file())
        self.assertFalse((self._output_dir / "school-sheets" / "index.html").is_file())

    def test_redirects_copy_into_the_build_success(self) -> None:
        built = self._output_dir / "_redirects"
        self.assertTrue(built.is_file(), "static/_redirects must copy into the build")
        text = built.read_text(encoding="utf-8")
        self.assertIn("/map/ /erics-d1-mission/", text)
        self.assertIn("/school-sheets/ /erics-d1-mission/", text)


if __name__ == "__main__":
    unittest.main()
