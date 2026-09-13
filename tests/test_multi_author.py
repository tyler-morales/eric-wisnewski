"""Shared posts: multiple authors plus labeled Who wrote what parts."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_YML = REPO_ROOT / ".pages.yml"
README = REPO_ROOT / "README.md"
INVITE = REPO_ROOT / "docs" / "invite-author.md"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
SINGLE = REPO_ROOT / "layouts" / "_default" / "single.html"
SLUGS = REPO_ROOT / "layouts" / "partials" / "post-author-slugs.html"
PAGES = REPO_ROOT / "layouts" / "partials" / "post-author-pages.html"
PARTS = REPO_ROOT / "layouts" / "partials" / "post-parts.html"
AUTHOR_POSTS = REPO_ROOT / "layouts" / "partials" / "author-posts.html"
HUGO_TIMEOUT_SECONDS = 120

LD_JSON_RE = re.compile(
    r'<script\s+type="application/ld\+json">(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def collection_block(yaml_text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  - name: {re.escape(name)}\n(.*?)(?=^  - name: |\Z)",
        yaml_text,
    )
    return match.group(1) if match else ""


def write_author(path: Path, slug: str, name: str) -> None:
    path.write_text(
        f"---\nname: {name}\nslug: {slug}\ndraft: false\nbio: Bio for {name}.\n---\n",
        encoding="utf-8",
    )


class MultiAuthorSourceTests(unittest.TestCase):
    def test_cms_author_field_allows_multiple_success(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        for name in ("posts", "gradys-tour", "da-breakdown-w-tad", "jeremy-on-tap"):
            block = collection_block(yml, name)
            with self.subTest(collection=name):
                self.assertIn("label: Authors", block)
                self.assertIn("multiple: true", block)
                self.assertIn("name: parts", block)
                self.assertIn("Who wrote what", block)

    def test_cms_without_parts_fails_contract(self) -> None:
        yml = PAGES_YML.read_text(encoding="utf-8")
        self.assertGreaterEqual(yml.count("name: parts"), 4)

    def test_templates_normalize_author_list_success(self) -> None:
        slugs = SLUGS.read_text(encoding="utf-8")
        pages = PAGES.read_text(encoding="utf-8")
        parts = PARTS.read_text(encoding="utf-8")
        posts = AUTHOR_POSTS.read_text(encoding="utf-8")
        single = SINGLE.read_text(encoding="utf-8")
        self.assertIn("reflect.IsSlice", slugs)
        self.assertIn("post-author-slugs.html", pages)
        self.assertIn("post-part", parts)
        self.assertIn("intersect", posts)
        self.assertIn('partial "post-parts.html"', single)
        self.assertGreater(single.find("post-parts.html"), single.find("page-content.html"))

    def test_templates_do_not_eq_scalar_author_failure(self) -> None:
        posts = AUTHOR_POSTS.read_text(encoding="utf-8")
        self.assertNotIn('"Params.author" "in"', posts)

    def test_docs_cover_christian_and_collabs_success(self) -> None:
        readme = README.read_text(encoding="utf-8")
        invite = INVITE.read_text(encoding="utf-8")
        self.assertIn("christian-pudlo", readme)
        self.assertIn("Who wrote what", readme)
        self.assertIn("cpudlo@outlook.com", invite)
        self.assertIn("Christian Pudlo", invite)
        self.assertIn("Who wrote what", invite)
        self.assertIn("Grady’s Tour", invite)

    def test_part_byline_has_focus_visible_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".post-part-byline", css)
        self.assertIn(".post-part-byline .author-name-link:focus-visible", css)
        self.assertIn(".author-bios", css)
        self.assertIn(".post-list-author a:focus-visible", css)


class MultiAuthorBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="multi-author-")
        root = Path(cls._tmp.name)
        content_dir = root / "content"
        (content_dir / "authors").mkdir(parents=True)
        (content_dir / "posts").mkdir()
        (content_dir / "gradys-tour").mkdir()
        (content_dir / "authors" / "_index.md").write_text(
            "---\ntitle: Contributors\n---\n",
            encoding="utf-8",
        )
        (content_dir / "gradys-tour" / "_index.md").write_text(
            "---\ntitle: Grady's Tour\n---\n",
            encoding="utf-8",
        )
        write_author(content_dir / "authors" / "writer-a.md", "writer-a", "Writer A")
        write_author(content_dir / "authors" / "writer-b.md", "writer-b", "Writer B")
        (content_dir / "posts" / "solo.md").write_text(
            "---\n"
            "title: Solo Post\n"
            "slug: solo\n"
            "author: writer-a\n"
            "date: 2026-01-01T00:00:00Z\n"
            "draft: false\n"
            "---\n"
            "Just A.\n",
            encoding="utf-8",
        )
        (content_dir / "gradys-tour" / "collab.md").write_text(
            "---\n"
            "title: Collab Post\n"
            "slug: collab\n"
            "author:\n"
            "  - writer-a\n"
            "  - writer-b\n"
            "date: 2026-01-02T00:00:00Z\n"
            "draft: false\n"
            "parts:\n"
            "  - author: writer-a\n"
            '    body: "<p>Alpha wrote this.</p>"\n'
            "  - author: writer-b\n"
            '    body: "<p>Beta wrote this.</p>"\n'
            "---\n"
            "<p>Shared intro.</p>\n",
            encoding="utf-8",
        )
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
        cls.collab = (dest / "gradys-tour" / "collab" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.solo = (dest / "posts" / "solo" / "index.html").read_text(encoding="utf-8")
        cls.home = (dest / "index.html").read_text(encoding="utf-8")
        cls.a_html = (dest / "authors" / "writer-a" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.b_html = (dest / "authors" / "writer-b" / "index.html").read_text(
            encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_collab_byline_and_parts_success(self) -> None:
        html = self.collab
        byline = re.search(r'<p class="post-byline">(.*?)</p>', html, re.DOTALL)
        self.assertIsNotNone(byline)
        assert byline is not None
        line = byline.group(1)
        self.assertIn("Writer A", line)
        self.assertIn("Writer B", line)
        self.assertIn(" and ", line)
        self.assertIn("/authors/writer-a/", line)
        self.assertIn("/authors/writer-b/", line)
        self.assertGreater(line.find("Writer A"), -1)
        self.assertGreater(line.find("Writer B"), line.find(" and "))
        self.assertIn("Shared intro.", html)
        self.assertIn("Alpha wrote this.", html)
        self.assertIn("Beta wrote this.", html)
        self.assertIn('class="post-part"', html)
        self.assertIn('class="post-part-byline"', html)

    def test_collab_lists_on_both_author_pages_success(self) -> None:
        self.assertIn("Collab Post", self.a_html)
        self.assertIn("Collab Post", self.b_html)
        self.assertIn("Solo Post", self.a_html)
        self.assertNotIn("Solo Post", self.b_html)
        home_authors = re.findall(
            r'<p class="post-list-author">(.*?)</p>', self.home, re.DOTALL
        )
        joined = " ".join(home_authors)
        self.assertIn("Writer A", joined)
        self.assertIn("Writer B", joined)
        self.assertTrue(any(" and " in block for block in home_authors))

    def test_solo_string_author_still_works_failure(self) -> None:
        byline = re.search(r'<p class="post-byline">(.*?)</p>', self.solo, re.DOTALL)
        self.assertIsNotNone(byline)
        assert byline is not None
        line = byline.group(1)
        self.assertIn("Writer A", line)
        self.assertNotIn("Writer B", line)
        self.assertNotIn(" and ", line)
        self.assertNotIn("post-part", self.solo)

    def test_collab_json_ld_authors_are_a_list_success(self) -> None:
        blobs = [
            json.loads(match)
            for match in LD_JSON_RE.findall(self.collab)
            if '"BlogPosting"' in match or '"@type":"BlogPosting"' in match
        ]
        self.assertTrue(blobs, "collab post missing BlogPosting JSON-LD")
        author = blobs[0]["author"]
        self.assertIsInstance(author, list)
        names = [item["name"] for item in author]
        self.assertEqual(names, ["Writer A", "Writer B"])

    def test_solo_json_ld_author_stays_an_object_failure(self) -> None:
        blobs = [
            json.loads(match)
            for match in LD_JSON_RE.findall(self.solo)
            if '"BlogPosting"' in match or '"@type":"BlogPosting"' in match
        ]
        self.assertTrue(blobs)
        author = blobs[0]["author"]
        self.assertIsInstance(author, dict)
        self.assertEqual(author["name"], "Writer A")


if __name__ == "__main__":
    unittest.main()
