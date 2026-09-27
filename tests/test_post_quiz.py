"""Mock end-of-article quiz on the Sardinia post only."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARTIAL = REPO_ROOT / "layouts" / "partials" / "post-quiz.html"
SINGLE = REPO_ROOT / "layouts" / "_default" / "single.html"
QUIZ_JS = REPO_ROOT / "static" / "js" / "post-quiz.js"
SARDINIA = REPO_ROOT / "content" / "gradys-tour" / "sardinia-napoli.md"
NIU = REPO_ROOT / "content" / "posts" / "northern-illinois.md"
BOSTON = REPO_ROOT / "content" / "posts" / "boston-college.md"
PAGES_YML = REPO_ROOT / ".pages.yml"
HUGO_TIMEOUT_SECONDS = 120

OTHER_QUIZ = "\n".join(
    [
        "---",
        "title: Quiz Should Stay Hidden",
        "slug: quiz-other",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:00:00Z",
        "draft: false",
        "quiz: true",
        "---",
        "Not the Sardinia recap.",
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


def call_js(fn_name: str, script_body: str) -> object:
    script = (
        f"import {{ {fn_name} }} from {json.dumps(QUIZ_JS.as_uri())};\n" + script_body
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


class PostQuizSourceTests(unittest.TestCase):
    def test_flagged_post_partial_shape_success(self) -> None:
        post = SARDINIA.read_text(encoding="utf-8")
        self.assertIn("quiz: true", post)
        self.assertIn("Sardinia", post)
        layout = SINGLE.read_text(encoding="utf-8")
        self.assertIn('partial "post-quiz.html"', layout)
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertIn("sardinia-napoli", src)
        self.assertIn("Think you caught it all?", src)
        self.assertIn('type="button"', src)
        self.assertIn('aria-expanded="false"', src)
        self.assertIn('role="status"', src)
        self.assertIn("aria-live", src)
        self.assertIn("<fieldset", src)
        self.assertIn('name="flag"', src)
        self.assertIn('name="deal"', src)
        self.assertIn('name="bar"', src)
        self.assertIn('data-step="1" hidden', src)
        self.assertIn('data-step="2" hidden', src)
        self.assertIn(">Next<", src)
        self.assertIn(">1/3<", src)
        self.assertIn("Moorish heads", src)
        self.assertIn("Redskin", src)
        self.assertIn("Coming soon", src)
        self.assertIn("Email for the sticker", src)
        self.assertIn("disabled", src)
        self.assertIn("/js/post-quiz.js", src)
        css = (REPO_ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8")
        quiz_css = css.split("/* End-of-article quiz", 1)[1].split("article.post-content pre", 1)[0]
        self.assertNotIn(":hover,", quiz_css)
        self.assertNotIn(":hover {", quiz_css)
        self.assertIn(":focus-visible", quiz_css)
        self.assertNotIn("outline-offset: 4px", quiz_css)
        self.assertNotIn("northern-illinois", src)
        self.assertNotIn("Ball State", src)
        js = QUIZ_JS.read_text(encoding="utf-8")
        self.assertIn("sardinia-napoli", js)
        self.assertIn('flag: "true"', js)
        self.assertIn('deal: "ninety"', js)
        self.assertIn('bar: "redskin"', js)
        self.assertIn("you've earned a sticker", js)
        self.assertNotIn("northern-illinois", js)
        self.assertNotIn("ball-state", js)
        self.assertNotIn("answer:", src.lower())
        self.assertNotIn("data-correct", src)
        self.assertNotIn("name: quiz", PAGES_YML.read_text(encoding="utf-8"))

    def test_other_posts_do_not_carry_the_flag_failure(self) -> None:
        self.assertNotIn("quiz:", NIU.read_text(encoding="utf-8"))
        self.assertNotIn("quiz:", BOSTON.read_text(encoding="utf-8"))
        tour = (REPO_ROOT / "content" / "gradys-tour" / "italy.md").read_text(encoding="utf-8")
        self.assertNotIn("quiz:", tour)
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertIn('eq .Section "gradys-tour"', src)
        self.assertIn('eq .File.ContentBaseName "sardinia-napoli"', src)


class PostQuizJsTests(unittest.TestCase):
    def test_perfect_card_scores_three_success(self) -> None:
        answers = {"flag": "true", "deal": "ninety", "bar": "redskin"}
        picks = {"flag": "true", "deal": "ninety", "bar": "redskin"}
        self.assertEqual(call_fn("scoreQuiz", answers, picks), {"correct": 3, "total": 3})
        self.assertEqual(call_fn("missingKeys", answers, picks), [])
        self.assertTrue(call_fn("showStickerClaim", 3, 3))
        self.assertIn("sticker", call_fn("feedbackLine", 3, 3))
        self.assertEqual(call_fn("nextQuizStep", 0, 3, True), {"index": 1, "done": False, "needsAnswer": False})
        self.assertEqual(call_fn("stepLabel", 0, 3), "1/3")

    def test_partial_and_blank_picks_do_not_pass_failure(self) -> None:
        answers = {"flag": "true", "deal": "ninety", "bar": "redskin"}
        wrong = {"flag": "false", "deal": "one-forty", "bar": "redskin"}
        self.assertEqual(call_fn("scoreQuiz", answers, wrong), {"correct": 1, "total": 3})
        self.assertFalse(call_fn("showStickerClaim", 2, 3))
        self.assertNotIn("sticker", call_fn("feedbackLine", 2, 3))
        blank = {"flag": "true", "deal": "", "bar": "redskin"}
        self.assertEqual(call_fn("missingKeys", answers, blank), ["deal"])
        self.assertEqual(
            call_fn("nextQuizStep", 0, 3, False),
            {"index": 0, "done": False, "needsAnswer": True},
        )
        self.assertEqual(
            call_fn("nextQuizStep", 2, 3, True),
            {"index": 2, "done": True, "needsAnswer": False},
        )
        self.assertEqual(call_fn("scoreQuiz", answers, {}), {"correct": 0, "total": 3})
        self.assertEqual(call_fn("scoreQuiz", None, None), {"correct": 0, "total": 0})


class PostQuizBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="post-quiz-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "quiz-other.md").write_text(OTHER_QUIZ, encoding="utf-8")
        dest = cls._tmp / "out"
        result = run_hugo(destination=dest, content_dir=content_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        try:
            sardinia_pages = list((dest / "gradys-tour").glob("*/index.html"))
            sardinia_hit = [
                page.read_text(encoding="utf-8")
                for page in sardinia_pages
                if "post-quiz" in page.read_text(encoding="utf-8")
            ]
            if len(sardinia_hit) != 1:
                raise OSError(f"expected one quiz page, found {len(sardinia_hit)}")
            cls.sardinia = sardinia_hit[0]
            cls.niu = (dest / "posts" / "northern-illinois" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.boston = (dest / "posts" / "boston-college" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.other = (dest / "posts" / "quiz-other" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.tour = (dest / "gradys-tour" / "italy" / "index.html").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_sardinia_renders_hidden_questions_success(self) -> None:
        html = self.sardinia
        self.assertIn("Think you caught it all?", html)
        self.assertIn('class="post-quiz-panel"', html)
        self.assertIn('data-step="1" hidden', html)
        self.assertIn(">Next<", html)
        self.assertIn(">1/3<", html)
        self.assertIn("Moorish heads", html)
        self.assertIn("prosecco", html)
        self.assertIn(">Redskin<", html)
        self.assertIn('role="status"', html)
        self.assertIn("Coming soon", html)
        self.assertIn("disabled", html)
        self.assertNotIn("answer:", html.lower())
        self.assertNotIn("Ball State", html)
        quiz = html.split('class="post-quiz"', 1)[1].split("</aside>", 1)[0]
        self.assertNotIn("data-correct", quiz)
        self.assertIn('value="ninety"', quiz)
        self.assertNotIn(">ninety<", quiz)

    def test_other_pages_omit_the_quiz_failure(self) -> None:
        for html in (self.niu, self.boston, self.other, self.tour):
            self.assertNotIn("post-quiz", html)
            self.assertNotIn("Think you caught it all?", html)
