"""Grady's Tour country chip + index globe → /gradys-tour/?country=france."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_YML = REPO_ROOT / ".pages.yml"
TOUR_LAYOUT = REPO_ROOT / "layouts" / "_default" / "gradys-tour.html"
SINGLE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "single.html"
LIST_ITEM = REPO_ROOT / "layouts" / "partials" / "post-list-item.html"
COUNTRY_NAV = REPO_ROOT / "layouts" / "partials" / "gradys-tour-country-nav.html"
POST_BYLINE = REPO_ROOT / "layouts" / "partials" / "post-byline.html"
POST_COUNTRY_CHIP = REPO_ROOT / "layouts" / "partials" / "post-country-chip.html"
COUNTRY_JS = REPO_ROOT / "static" / "js" / "gradys-tour-country.js"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
TOUR_DIR = REPO_ROOT / "content" / "gradys-tour"
WORLD_MAP = REPO_ROOT / "static" / "maps" / "countries-110m.json"
HUGO_TIMEOUT_SECONDS = 120

COLLECTION_RE = re.compile(
    r"(?m)^  - name: (posts|gradys-tour|da-breakdown-w-tad|jeremy-on-tap)\n(.*?)(?=^  - name: |\Z)",
    re.DOTALL,
)
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
CMS_COUNTRY_VALUES_RE = re.compile(
    r"(?m)^      - name: country\n(?:.*\n)*?          values:\n((?:            - [^\n]+\n)+)",
)


def collection_block(pages_yml: str, name: str) -> str:
    for match in COLLECTION_RE.finditer(pages_yml):
        if match.group(1) == name:
            return match.group(0)
    return ""


def cms_country_values(pages_yml: str) -> list[str]:
    tour = collection_block(pages_yml, "gradys-tour")
    match = CMS_COUNTRY_VALUES_RE.search(tour)
    if not match:
        return []
    names: list[str] = []
    for line in match.group(1).splitlines():
        raw = line.strip()
        if not raw.startswith("- "):
            continue
        value = raw[2:].strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        names.append(value)
    return names


def natural_earth_names() -> list[str]:
    data = json.loads(WORLD_MAP.read_text(encoding="utf-8"))
    names = []
    for geom in data["objects"]["countries"]["geometries"]:
        name = (geom.get("properties") or {}).get("name")
        if name:
            names.append(name)
    return names


def parse_simple_front_matter(path: Path) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("-"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def call_js(fn_name: str, script_body: str) -> object:
    if not COUNTRY_JS.is_file():
        raise FileNotFoundError(COUNTRY_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(COUNTRY_JS.as_uri())};\n"
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


def call_fn(fn_name: str, *args: object) -> object:
    arg_list = ", ".join(json.dumps(a) for a in args)
    return call_js(
        fn_name,
        f"console.log(JSON.stringify({fn_name}({arg_list})));\n",
    )


def read_export(name: str) -> object:
    return call_js(name, f"console.log(JSON.stringify({name}));\n")


def run_hugo(*, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hugo", "--destination", str(destination), "--quiet", "--noBuildLock"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=HUGO_TIMEOUT_SECONDS,
    )


class CountryHelperTests(unittest.TestCase):
    def test_slug_and_url_success(self) -> None:
        self.assertEqual(call_fn("countrySlug", "France"), "france")
        self.assertEqual(call_fn("countrySlug", "United States"), "united-states")
        self.assertEqual(call_fn("countrySlug", "Côte d'Ivoire"), "cote-divoire")
        self.assertEqual(call_fn("countryFromSearch", "?country=france"), "france")
        self.assertEqual(
            call_fn("tourListUrl", "France"),
            "/gradys-tour/?country=france",
        )
        self.assertEqual(call_fn("titleForCountry", "france"), "Grady's Tour · France")
        self.assertTrue(call_fn("itemVisible", "france", "France"))
        self.assertTrue(call_fn("itemVisible", "germany", ""))
        self.assertEqual(
            call_fn(
                "countByCountry",
                [{"country": "france"}, {"country": "France"}, {"country": ""}],
            ),
            {"france": 2},
        )
        self.assertEqual(call_fn("optionLabel", "france", 6), "France (6)")
        self.assertEqual(call_fn("countLabel", "france", 6), "6 posts in France")
        self.assertEqual(call_fn("postCountLabel", 12), "12 posts")
        self.assertEqual(call_fn("postCountLabel", 1), "1 post")
        self.assertEqual(
            call_fn("featureCountrySlug", "United States of America"),
            "united-states",
        )
        self.assertEqual(
            call_fn("featureCountrySlug", "Bosnia and Herz."),
            "bosnia-and-herzegovina",
        )
        self.assertEqual(
            call_fn("featureCountrySlug", "Macedonia"),
            "north-macedonia",
        )
        self.assertEqual(
            call_fn(
                "countByCountry",
                [{"countries": ["italy", "switzerland", "germany"]}],
            ),
            {"italy": 1, "switzerland": 1, "germany": 1},
        )
        self.assertTrue(call_fn("itemVisible", "italy switzerland germany", "Switzerland"))
        self.assertEqual(
            call_fn(
                "parseCatalogJson",
                json.dumps({"posts": [{"country": "france"}], "listPage": True}),
            )["listPage"],
            True,
        )
        double = json.dumps(json.dumps({"posts": [{"country": "france"}]}))
        self.assertEqual(len(call_fn("parseCatalogJson", double)["posts"]), 1)
        scale_min = read_export("GLOBE_SCALE_MIN")
        scale_max = read_export("GLOBE_SCALE_MAX")
        self.assertEqual(call_fn("clampGlobeScale", 10), scale_min)
        self.assertAlmostEqual(float(call_fn("pinchScale", scale_min, 100, 140)), float(scale_min) * 1.4)
        self.assertEqual(call_fn("pinchScale", scale_min, 10, 10), scale_min)
        self.assertEqual(call_fn("pinchScale", scale_max, 10, 100), scale_max)
        wide = call_fn("scaleToFit", [[0, 0], [320, 320]], scale_min, 640, 0.82)
        self.assertGreater(float(wide), float(scale_min))
        self.assertLessEqual(float(wide), float(scale_max))
        self.assertTrue(call_fn("pointOnGlobe", [320, 320], 320, 320, 297.67))
        self.assertTrue(call_fn("pointOnGlobe", [320, 20], 320, 320, 300))

    def test_unknown_or_empty_country_failure(self) -> None:
        self.assertEqual(call_fn("countrySlug", "   "), "")
        self.assertEqual(call_fn("countryFromSearch", ""), "")
        self.assertEqual(call_fn("countryFromSearch", "?country="), "")
        self.assertEqual(call_fn("tourListUrl", ""), "/gradys-tour/")
        self.assertEqual(call_fn("titleForCountry", ""), "Grady's Tour")
        self.assertFalse(call_fn("itemVisible", "germany", "france"))
        self.assertFalse(call_fn("itemVisible", "", "france"))
        self.assertEqual(call_fn("countByCountry", []), {})
        self.assertEqual(call_fn("featureCountrySlug", ""), "")
        self.assertFalse(call_fn("itemVisible", "italy switzerland", "france"))
        self.assertEqual(call_fn("postCountLabel", "nope"), "0 posts")
        self.assertEqual(call_fn("postCountLabel", -4), "0 posts")
        scale_min = read_export("GLOBE_SCALE_MIN")
        self.assertEqual(call_fn("clampGlobeScale", "nope"), scale_min)
        self.assertEqual(call_fn("pinchScale", "nope", 10, 20), scale_min)
        self.assertEqual(call_fn("pinchScale", scale_min, 0, 20), scale_min)
        self.assertEqual(call_fn("pinchScale", scale_min, 10, -4), scale_min)
        self.assertEqual(call_fn("scaleToFit", None, 100, 640, 0.82), scale_min)
        self.assertFalse(call_fn("pointOnGlobe", [10, 10], 320, 320, 297.67))
        self.assertFalse(call_fn("pointOnGlobe", None, 320, 320, 297.67))


class CountrySourceTests(unittest.TestCase):
    def test_cms_country_field_only_on_tour_success(self) -> None:
        pages = PAGES_YML.read_text(encoding="utf-8")
        tour = collection_block(pages, "gradys-tour")
        self.assertIn("name: country", tour)
        self.assertIn("type: select", tour)
        self.assertIn("multiple: true", tour)
        names = cms_country_values(pages)
        self.assertGreaterEqual(len(names), 150)
        for needed in (
            "France",
            "Germany",
            "Italy",
            "Switzerland",
            "Japan",
            "Morocco",
            "Brazil",
            "Australia",
            "Kenya",
            "India",
            "United States",
            "Côte d'Ivoire",
        ):
            with self.subTest(country=needed):
                self.assertIn(needed, names)
        self.assertNotIn("Antarctica", names)
        self.assertNotIn("United States of America", names)
        cms_slugs = {call_fn("countrySlug", name) for name in names}
        globe_slugs = {call_fn("featureCountrySlug", name) for name in natural_earth_names()}
        self.assertEqual(sorted(cms_slugs - globe_slugs), [])
        for name in ("posts", "da-breakdown-w-tad", "jeremy-on-tap"):
            with self.subTest(collection=name):
                self.assertNotIn("name: country", collection_block(pages, name))

    def test_templates_put_globe_on_index_and_chip_on_posts_success(self) -> None:
        tour = TOUR_LAYOUT.read_text(encoding="utf-8")
        single = SINGLE_LAYOUT.read_text(encoding="utf-8")
        nav = COUNTRY_NAV.read_text(encoding="utf-8")
        item = LIST_ITEM.read_text(encoding="utf-8")
        byline = POST_BYLINE.read_text(encoding="utf-8")
        chip = POST_COUNTRY_CHIP.read_text(encoding="utf-8")
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn('partial "gradys-tour-country-nav.html"', tour)
        self.assertIn('partial "post-count.html"', tour)
        self.assertIn('"live" true', tour)
        self.assertNotIn('partial "gradys-tour-country-nav.html"', single)
        self.assertIn('partial "post-byline.html"', single)
        self.assertIn('partial "post-country-chip.html"', byline)
        self.assertIn('partial "post-country-chip.html"', item)
        self.assertIn("post-country-chip", chip)
        self.assertIn("?country=", chip)
        self.assertIn("<details", chip)
        self.assertIn('partial "tour-country-slugs.html"', item)
        self.assertIn('partial "tour-country-slugs.html"', byline)
        self.assertIn('partial "tour-country-slugs.html"', chip)
        self.assertIn('data-country="{{', item)
        self.assertIn("post-list-media", item)
        self.assertNotIn("post-byline-row", item)
        self.assertIn("post-country-chip.html\" $", item)
        self.assertIn('name="country"', nav)
        self.assertIn("data-tour-country-select", nav)
        self.assertIn("data-tour-country-nav", nav)
        self.assertIn("tour-country-map", nav)
        self.assertIn("data-tour-zoom-in", nav)
        self.assertIn("data-tour-zoom-out", nav)
        self.assertIn("data-tour-catalog", nav)
        self.assertIn("jsonify", nav)
        self.assertIn("safeHTML", nav)
        self.assertIn("data-tour-globe", nav)
        self.assertIn("countries-110m.json", nav)
        world_names = natural_earth_names()
        self.assertIn("France", world_names)
        self.assertIn("Japan", world_names)
        self.assertIn("/js/gradys-tour-country.js", nav)
        self.assertNotIn('" /js/gradys-tour-country.js"', nav)
        self.assertNotIn('readFile " static/js', nav)
        self.assertNotIn('" /maps/countries-110m.json"', nav)
        self.assertNotIn("data-tour-preview", nav)
        self.assertNotIn("data-tour-view-all", nav)
        self.assertRegex(
            css,
            r"\.post-byline-row\s*\{[^}]*justify-content:\s*space-between",
        )
        self.assertRegex(
            css,
            r"\.post-list li\s*\{[^}]*max-width:\s*640px",
        )
        self.assertIn(".post-list-media .post-country-chip", css)
        self.assertRegex(
            css,
            r"\.post-list-media \.post-country-chip\s*\{[^}]*left:\s*0\.5rem",
        )
        self.assertNotIn(".post-list-meta .post-byline-row", css)
        self.assertRegex(
            css,
            r"\.tour-country-svg \[data-slug\]\.has-posts\s*\{[^}]*outline:\s*none",
        )
        self.assertNotIn(
            ".tour-country-svg [data-slug].has-posts:focus-visible",
            css,
        )
        self.assertIn("article.post-content a.post-country-chip", css)
        self.assertIn("article.post-content .post-country-chip--menu a", css)
        self.assertNotIn(".post-country-chip:hover", css)
        self.assertNotIn(".post-country-chip--menu a:hover", css)
        chip_css = css[css.find(".post-country-chip") : css.find("article.post-content>header .post-meta")]
        self.assertNotIn("text-decoration: underline", chip_css)
        self.assertIn(".post-country-chip:focus-visible", css)
        summary_css = re.search(r"\.post-country-chip--menu summary\s*\{([^}]*)\}", css)
        self.assertIsNotNone(summary_css)
        summary_body = summary_css.group(1)
        self.assertIn("background: var(--bg)", summary_body)
        self.assertIn("color: var(--text)", summary_body)
        self.assertNotIn("transparent", summary_body)
        self.assertIn(".tour-country-map-tools button:focus-visible", css)
        self.assertIn("tour-country-layout", css)
        self.assertIn("All countries", nav)
        self.assertNotIn("data-tour-status", nav)
        self.assertNotIn("tour-country-status", nav)
        js = COUNTRY_JS.read_text(encoding="utf-8")
        self.assertIn("history.pushState", js)
        self.assertIn("(!opts || opts.push !== false)", js)
        self.assertNotIn("opts && opts.push !== false", js)
        self.assertIn("preventDefault", js)
        self.assertIn("export function pinchScale", js)
        self.assertIn("(hover: none) and (pointer: coarse)", js)
        self.assertIn("pointerType", js)
        self.assertIn("touch-action: pan-y", css)
        self.assertIn("touch-action: none", css)
        self.assertRegex(
            css,
            r"@media \(hover: none\) and \(pointer: coarse\) \{\s*"
            r"\.tour-country-map-tools \{\s*display: none;",
        )
        self.assertIn("tour-country-map-hint-touch", nav)
        self.assertIn("One finger scrolls the page.", nav)
        self.assertIn("geoOrthographic", js)
        self.assertIn("clampGlobeScale", js)
        self.assertIn("tour-globe-clip", js)
        self.assertIn("pointOnGlobe", js)
        self.assertIn("pressedSlug", js)
        self.assertIn("select.value = selected", js)
        self.assertIn("NFD", js)
        self.assertNotIn("setAttribute('tabindex'", js)
        self.assertNotIn("location.assign", js)
        self.assertNotIn("function previewPosts", js)
        self.assertNotIn("function viewAllLabel", js)
        self.assertFalse((REPO_ROOT / "static" / "maps" / "europe.svg").is_file())

    def test_nav_is_not_a_google_embed_failure(self) -> None:
        nav = COUNTRY_NAV.read_text(encoding="utf-8")
        js = COUNTRY_JS.read_text(encoding="utf-8")
        self.assertNotIn("google.com/maps", nav)
        self.assertNotIn("<iframe", nav)
        self.assertNotIn("leaflet", nav.lower())
        self.assertNotIn("google.com/maps", js)


class CountryContentTests(unittest.TestCase):
    def test_france_posts_have_country_success(self) -> None:
        france = parse_simple_front_matter(TOUR_DIR / "no-bikes.md")
        self.assertEqual(france.get("country"), "France")
        fin = parse_simple_front_matter(TOUR_DIR / "fin.md")
        self.assertEqual(fin.get("country"), "France")
        coming = (TOUR_DIR / "comingsoon.md").read_text(encoding="utf-8")
        self.assertIn("\n  - Italy\n", coming)
        self.assertIn("\n  - Switzerland\n", coming)
        self.assertIn("\n  - Germany\n", coming)

    def test_prep_post_is_not_a_country_failure(self) -> None:
        prep = parse_simple_front_matter(TOUR_DIR / "gearing-up.md")
        self.assertNotIn("country", prep)
        self.assertNotIn("country", parse_simple_front_matter(TOUR_DIR / "_index.md"))


class CountryBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_dir = Path(tempfile.mkdtemp(prefix="gradys-tour-country-"))
        result = run_hugo(destination=cls._output_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._output_dir, ignore_errors=True)
            raise unittest.SkipTest(
                f"hugo build failed; check that hugo is on PATH:\n{result.stderr}"
            )
        cls.tour = (cls._output_dir / "gradys-tour" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.france = (
            cls._output_dir / "gradys-tour" / "no-bikes" / "index.html"
        ).read_text(encoding="utf-8")
        cls.coming = (
            cls._output_dir / "gradys-tour" / "comingsoon" / "index.html"
        ).read_text(encoding="utf-8")
        cls.prep = (
            cls._output_dir / "gradys-tour" / "gearing-up" / "index.html"
        ).read_text(encoding="utf-8")
        cls.eric = (
            cls._output_dir / "posts" / "an-introduction" / "index.html"
        ).read_text(encoding="utf-8")
        cls.home = (cls._output_dir / "index.html").read_text(encoding="utf-8")
        cls.eric_author = (
            cls._output_dir / "authors" / "eric-wisnewski" / "index.html"
        ).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._output_dir, ignore_errors=True)

    def test_index_globe_filters_and_post_chip_navigates_success(self) -> None:
        self.assertIn("data-tour-index", self.tour)
        self.assertIn('data-country="france"', self.tour)
        self.assertIn('id="tour-country"', self.tour)
        self.assertIn("tour-country-map", self.tour)
        self.assertIn("data-tour-zoom-in", self.tour)
        self.assertIn("data-tour-zoom-out", self.tour)
        self.assertIn("Pinch to zoom.", self.tour)
        self.assertIn("One finger scrolls the page.", self.tour)
        self.assertIn("France (6)", self.tour)
        self.assertIn("Italy (3)", self.tour)
        self.assertIn("Germany (2)", self.tour)
        self.assertIn("Switzerland (2)", self.tour)
        self.assertIn("data-tour-catalog", self.tour)
        match = re.search(
            r'<script type="application/json" data-tour-catalog>(.*?)</script>',
            self.tour,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        catalog = json.loads(match.group(1))
        if isinstance(catalog, str):
            catalog = json.loads(catalog)
        self.assertEqual(catalog.get("listPage"), True)

        def countries_of(post: dict) -> list:
            raw = post.get("countries", post.get("country") or [])
            if isinstance(raw, str):
                return [raw]
            return list(raw or [])

        self.assertGreaterEqual(
            sum(1 for post in catalog["posts"] if "france" in countries_of(post)),
            6,
        )
        self.assertTrue(any("italy" in countries_of(post) for post in catalog["posts"]))
        self.assertIn('class="post-country-chip"', self.france)
        self.assertIn("?country=france", self.france)
        self.assertIn(">France<", self.france)
        self.assertNotIn("data-tour-country-nav", self.france)
        self.assertNotIn("tour-country-map", self.france)
        self.assertNotIn("data-tour-preview", self.france)
        self.assertIn("post-country-chip--menu", self.coming)
        self.assertIn("?country=italy", self.coming)
        self.assertIn("?country=switzerland", self.coming)
        self.assertIn("?country=germany", self.coming)
        self.assertNotIn("data-tour-country-nav", self.coming)
        self.assertNotIn("class=\"post-country-chip\"", self.prep)
        self.assertNotIn("data-tour-country-nav", self.prep)
        self.assertIn('class="post-country-chip"', self.tour)
        self.assertIn("post-country-chip--menu", self.tour)
        self.assertRegex(
            self.tour,
            r'class="post-country-chip"[^>]*\?country=france',
        )
        self.assertIn('class="post-country-chip"', self.home)
        self.assertIn("post-country-chip--menu", self.home)

    def test_controls_stay_off_eric_posts_failure(self) -> None:
        self.assertNotIn("data-tour-country-nav", self.eric)
        self.assertNotIn("tour-country-map", self.eric)
        self.assertNotIn("post-country-chip", self.eric)
        self.assertNotIn("?country=france", self.eric)
        self.assertNotIn("data-tour-globe", self.eric)
        self.assertNotIn("post-country-chip", self.eric_author)


class CountryDocsTests(unittest.TestCase):
    def test_readme_documents_query_urls_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("?country=", readme)
        self.assertIn("Country", readme)
        self.assertIn("chip", readme.lower())
        self.assertIn("list cards", readme)


if __name__ == "__main__":
    unittest.main()
