"""Crawl/index SEO: 404, robots.txt, meta description, single H1, noindex utilities."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"
HEADER_PARTIAL = REPO_ROOT / "layouts" / "partials" / "header.html"
LIST_LAYOUT = REPO_ROOT / "layouts" / "_default" / "list.html"
JSON_LD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "json-ld.html"
HUGO_TOML = REPO_ROOT / "config" / "_default" / "hugo.toml"
ROBOTS_LAYOUT = REPO_ROOT / "layouts" / "robots.txt"
NOT_FOUND_LAYOUT = REPO_ROOT / "layouts" / "404.html"
README = REPO_ROOT / "README.md"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
HUGO_TIMEOUT_SECONDS = 120

META_DESCRIPTION_RE = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"',
    re.IGNORECASE,
)
ROBOTS_META_RE = re.compile(
    r'<meta\s+name="robots"\s+content="([^"]*)"',
    re.IGNORECASE,
)
LD_JSON_RE = re.compile(
    r'<script\s+type="application/ld\+json">(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def write_seo_fixture(content_dir: Path) -> None:
    """Minimal content so the Hugo build does not fetch School Sheets."""
    (content_dir / "posts").mkdir(parents=True)
    (content_dir / "gradys-tour").mkdir(parents=True)
    (content_dir / "subscribe").mkdir(parents=True)
    (content_dir / "admin").mkdir(parents=True)
    (content_dir / "posts" / "hello.md").write_text(
        "---\n"
        "title: Hello SEO\n"
        "slug: hello\n"
        "author: eric-wisnewski\n"
        "date: 2026-01-01T00:00:00Z\n"
        "draft: false\n"
        "---\n"
        "College basketball trip notes for search engines.\n",
        encoding="utf-8",
    )
    (content_dir / "authors").mkdir(parents=True)
    (content_dir / "authors" / "_index.md").write_text(
        "---\ntitle: Contributors\n---\n",
        encoding="utf-8",
    )
    (content_dir / "authors" / "eric-wisnewski.md").write_text(
        "---\n"
        "name: Eric Wisnewski\n"
        "slug: eric-wisnewski\n"
        "draft: false\n"
        "bio: Eric writes about college basketball.\n"
        "---\n",
        encoding="utf-8",
    )
    (content_dir / "gradys-tour" / "_index.md").write_text(
        "---\ntitle: Grady's Tour\n---\n",
        encoding="utf-8",
    )
    (content_dir / "subscribe" / "_index.md").write_text(
        "---\n"
        "title: Subscribe\n"
        "build:\n"
        "  list: never\n"
        "  render: never\n"
        "---\n",
        encoding="utf-8",
    )
    (content_dir / "admin" / "_index.md").write_text(
        "---\n"
        "title: Admin\n"
        "build:\n"
        "  list: never\n"
        "  render: never\n"
        "---\n",
        encoding="utf-8",
    )
    (content_dir / "subscribe" / "confirmed.md").write_text(
        "---\n"
        "title: Subscription confirmed\n"
        "layout: subscribe-status\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n"
        "Confirmed.\n",
        encoding="utf-8",
    )
    (content_dir / "subscribe" / "invalid.md").write_text(
        "---\n"
        "title: This link did not work\n"
        "layout: subscribe-status\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n"
        "Invalid.\n",
        encoding="utf-8",
    )
    (content_dir / "subscribe" / "unsubscribed.md").write_text(
        "---\n"
        "title: Unsubscribed\n"
        "layout: subscribe-status\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n"
        "Unsubscribed.\n",
        encoding="utf-8",
    )
    (content_dir / "subscribe" / "manage.md").write_text(
        "---\n"
        "title: Email preferences\n"
        "layout: subscribe-manage\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n",
        encoding="utf-8",
    )
    (content_dir / "admin" / "comments.md").write_text(
        "---\n"
        "title: Remove comments\n"
        "type: admin\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n"
        "Admin.\n",
        encoding="utf-8",
    )
    (content_dir / "add-photos.md").write_text(
        "---\n"
        "title: Add photos\n"
        "type: add-photos\n"
        "robots: noindex\n"
        "build:\n"
        "  list: never\n"
        "---\n"
        "Photos.\n",
        encoding="utf-8",
    )


class SeoTemplateTests(unittest.TestCase):
    def test_head_emits_meta_description_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('name="description"', head)
        self.assertIn("$headDescription", head)
        self.assertIn("truncate 170", head)
        self.assertIn('sizes="48x48"', head)

    def test_head_includes_json_ld_partial_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('partial "json-ld.html"', head)
        self.assertTrue(JSON_LD_PARTIAL.is_file())
        json_ld = JSON_LD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn("WebSite", json_ld)
        self.assertIn("BlogPosting", json_ld)
        self.assertIn("Person", json_ld)
        self.assertNotIn('"@type" "SearchAction"', json_ld)
        self.assertNotIn('"@type": "SearchAction"', json_ld)

    def test_home_list_has_no_site_lede_failure(self) -> None:
        layout = LIST_LAYOUT.read_text(encoding="utf-8")
        self.assertNotIn("site-lede", layout)

    def test_head_noindexes_404_kind_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('eq .Kind "404"', head)

    def test_robots_layout_lists_sitemap_and_disallows_success(self) -> None:
        robots = ROBOTS_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("Sitemap:", robots)
        self.assertIn("sitemap.xml", robots)
        self.assertIn("Disallow: /admin/", robots)
        self.assertIn("Disallow: /add-photos/", robots)
        self.assertIn("Disallow: /subscribe/manage/", robots)

    def test_hugo_enables_robots_txt_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIn("enableRobotsTXT = true", toml)
        self.assertIn("life long blog", toml)
        self.assertIn("division I college basketball", toml)
        self.assertNotIn("personal site and blog", toml)
        self.assertNotIn("College basketball writing from Eric Wisnewski", toml)

    def test_404_layout_exists_success(self) -> None:
        self.assertTrue(NOT_FOUND_LAYOUT.is_file())
        text = NOT_FOUND_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("Page not found", text)
        self.assertIn("header.html", text)

    def test_header_brand_is_h1_only_on_home_success(self) -> None:
        header = HEADER_PARTIAL.read_text(encoding="utf-8")
        self.assertIn(".IsHome", header)
        self.assertIn('<h1 class="brand-name">', header)
        self.assertIn('<p class="brand-name">', header)

    def test_brand_css_targets_class_not_only_h1_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".site-header .brand-name", css)
        self.assertNotIn(".site-header h1.brand-name", css)

    def test_subscribe_utility_front_matter_is_noindex_success(self) -> None:
        for rel in (
            "content/subscribe/confirmed.md",
            "content/subscribe/invalid.md",
            "content/subscribe/unsubscribed.md",
            "content/subscribe/manage.md",
        ):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("robots: noindex", text, rel)


class SeoBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="seo-")
        root = Path(cls._tmp.name)
        content_dir = root / "content"
        write_seo_fixture(content_dir)
        dest = root / "public"
        cache_dir = root / "cache"
        cache_dir.mkdir()
        result = subprocess.run(
            [
                "hugo",
                "--destination",
                str(dest),
                "--contentDir",
                str(content_dir),
                "--cacheDir",
                str(cache_dir),
                "--noBuildLock",
                "--quiet",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=HUGO_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            cls._tmp.cleanup()
            raise RuntimeError(result.stderr or result.stdout or "hugo build failed")
        cls.dest = dest

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_404_html_is_published_success(self) -> None:
        path = self.dest / "404.html"
        self.assertTrue(path.is_file(), "Cloudflare Pages needs public/404.html")
        html = path.read_text(encoding="utf-8")
        self.assertIn("Page not found", html)
        robots = ROBOTS_META_RE.search(html)
        self.assertIsNotNone(robots)
        assert robots is not None
        self.assertIn("noindex", robots.group(1))

    def test_robots_txt_has_sitemap_and_disallows_success(self) -> None:
        path = self.dest / "robots.txt"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Sitemap: https://ericwisnewski.com/sitemap.xml", text)
        self.assertIn("Disallow: /admin/", text)
        self.assertIn("Disallow: /add-photos/", text)
        self.assertIn("Disallow: /subscribe/manage/", text)
        self.assertIn("Allow: /", text)

    def test_home_and_post_have_meta_description_success(self) -> None:
        home = (self.dest / "index.html").read_text(encoding="utf-8")
        post = (self.dest / "posts" / "hello" / "index.html").read_text(encoding="utf-8")
        home_desc = META_DESCRIPTION_RE.search(home)
        post_desc = META_DESCRIPTION_RE.search(post)
        self.assertIsNotNone(home_desc)
        self.assertIsNotNone(post_desc)
        assert home_desc is not None and post_desc is not None
        self.assertIn("college basketball", home_desc.group(1).lower())
        self.assertIn("life long blog", home_desc.group(1).lower())
        self.assertNotIn("personal site and blog", home_desc.group(1).lower())
        self.assertNotIn("Notify me about", home_desc.group(1))
        self.assertIn("College basketball", post_desc.group(1))
        self.assertLessEqual(len(home_desc.group(1)), 175)
        self.assertLessEqual(len(post_desc.group(1)), 175)

    def test_home_has_no_visible_lede_failure(self) -> None:
        home = (self.dest / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("site-lede", home)
        # Description stays in meta only — not as homepage body copy.
        body = home.split("<main>", 1)[-1]
        self.assertNotIn("life long blog", body)

    def test_json_ld_website_blogposting_person_success(self) -> None:
        import json

        home = (self.dest / "index.html").read_text(encoding="utf-8")
        post = (self.dest / "posts" / "hello" / "index.html").read_text(encoding="utf-8")
        author = (self.dest / "authors" / "eric-wisnewski" / "index.html").read_text(
            encoding="utf-8"
        )
        home_ld = LD_JSON_RE.findall(home)
        post_ld = LD_JSON_RE.findall(post)
        author_ld = LD_JSON_RE.findall(author)
        self.assertEqual(len(home_ld), 1)
        self.assertEqual(len(post_ld), 1)
        self.assertEqual(len(author_ld), 1)
        self.assertEqual(json.loads(home_ld[0])["@type"], "WebSite")
        self.assertEqual(json.loads(post_ld[0])["@type"], "BlogPosting")
        self.assertEqual(json.loads(author_ld[0])["@type"], "Person")
        self.assertEqual(
            json.loads(post_ld[0])["author"]["name"], "Eric Wisnewski"
        )

    def test_noindex_pages_skip_json_ld_failure(self) -> None:
        html = (self.dest / "subscribe" / "confirmed" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertEqual(LD_JSON_RE.findall(html), [])

    def test_home_uses_h1_brand_post_uses_p_brand_success(self) -> None:
        home = (self.dest / "index.html").read_text(encoding="utf-8")
        post = (self.dest / "posts" / "hello" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<h1 class="brand-name">', home)
        self.assertNotIn('<p class="brand-name">', home)
        self.assertIn('<p class="brand-name">', post)
        self.assertNotIn('<h1 class="brand-name">', post)
        self.assertIn("<h1>Hello SEO</h1>", post)

    def test_sitemap_omits_admin_and_add_photos_success(self) -> None:
        sitemap = (self.dest / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/admin/", sitemap)
        self.assertNotIn("/add-photos/", sitemap)
        self.assertNotIn("/tags/", sitemap)
        self.assertNotIn("/categories/", sitemap)
        self.assertIn("/posts/hello/", sitemap)

    def test_empty_taxonomies_are_disabled_success(self) -> None:
        toml = HUGO_TOML.read_text(encoding="utf-8")
        self.assertIn("disableKinds", toml)
        self.assertIn("taxonomy", toml)
        self.assertIn("term", toml)
        self.assertFalse((self.dest / "tags" / "index.html").is_file())
        self.assertFalse((self.dest / "categories" / "index.html").is_file())

    def test_subscribe_status_pages_are_noindex_success(self) -> None:
        for rel in (
            "subscribe/confirmed/index.html",
            "subscribe/invalid/index.html",
            "subscribe/unsubscribed/index.html",
            "subscribe/manage/index.html",
        ):
            html = (self.dest / rel).read_text(encoding="utf-8")
            robots = ROBOTS_META_RE.search(html)
            self.assertIsNotNone(robots, rel)
            assert robots is not None
            self.assertIn("noindex", robots.group(1), rel)


class SeoDocsTests(unittest.TestCase):
    def test_readme_documents_seo_crawl_basics_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("404.html", readme)
        self.assertIn("robots.txt", readme)
        self.assertIn("sitemap.xml", readme)
        self.assertIn("Search Console", readme)
        self.assertIn("www", readme)
        self.assertIn("JSON-LD", readme)
        self.assertNotIn("site-lede", readme)
        self.assertTrue(
            "48x48" in readme or "48×48" in readme,
            "README should document Google’s 48×48 favicon minimum",
        )


if __name__ == "__main__":
    unittest.main()
