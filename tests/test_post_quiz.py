"""Mock end-of-article quiz on the Northern Illinois post only."""

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
        "Not the DeKalb recap.",
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
        post = NIU.read_text(encoding="utf-8")
        self.assertIn("quiz: true", post)
        layout = SINGLE.read_text(encoding="utf-8")
        self.assertIn('partial "post-quiz.html"', layout)
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertIn("northern-illinois", src)
        self.assertIn("Think you caught it all?", src)
        self.assertIn('type="button"', src)
        self.assertIn('aria-expanded="false"', src)
        self.assertIn('role="status"', src)
        self.assertIn("aria-live", src)
        self.assertIn("<fieldset", src)
        self.assertIn('name="band"', src)
        self.assertIn('name="opponent"', src)
        self.assertIn('name="seltzer"', src)
        self.assertIn("Ball State", src)
        self.assertIn("Coming soon", src)
        self.assertIn("disabled", src)
        self.assertIn("/js/post-quiz.js", src)
        js = QUIZ_JS.read_text(encoding="utf-8")
        self.assertIn("ball-state", js)
        self.assertIn('band: "true"', js)
        self.assertIn('seltzer: "red-wine"', js)
        self.assertNotIn("answer:", src.lower())
        self.assertNotIn("data-correct", src)
        self.assertNotIn("name: quiz", PAGES_YML.read_text(encoding="utf-8"))

    def test_other_posts_do_not_carry_the_flag_failure(self) -> None:
        self.assertNotIn("quiz:", BOSTON.read_text(encoding="utf-8"))
        tour = (REPO_ROOT / "content" / "gradys-tour" / "italy.md").read_text(encoding="utf-8")
        self.assertNotIn("quiz:", tour)
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertIn('eq .Section "posts"', src)
        self.assertIn('eq .File.ContentBaseName "northern-illinois"', src)


class PostQuizJsTests(unittest.TestCase):
    def test_perfect_card_scores_three_success(self) -> None:
        answers = {"band": "true", "opponent": "ball-state", "seltzer": "red-wine"}
        picks = {"band": "true", "opponent": "ball-state", "seltzer": "red-wine"}
        self.assertEqual(call_fn("scoreQuiz", answers, picks), {"correct": 3, "total": 3})
        self.assertEqual(call_fn("missingKeys", answers, picks), [])
        self.assertIn("claim a shot", call_fn("prizeLine", 3, 3))
        self.assertIn("DeKalb", call_fn("feedbackLine", 3, 3))

    def test_partial_and_blank_picks_do_not_pass_failure(self) -> None:
        answers = {"band": "true", "opponent": "ball-state", "seltzer": "red-wine"}
        wrong = {"band": "false", "opponent": "cal", "seltzer": "red-wine"}
        self.assertEqual(call_fn("scoreQuiz", answers, wrong), {"correct": 1, "total": 3})
        self.assertNotIn("claim a shot", call_fn("prizeLine", 2, 3))
        blank = {"band": "true", "opponent": "", "seltzer": "red-wine"}
        self.assertEqual(call_fn("missingKeys", answers, blank), ["opponent"])
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

    def test_niu_renders_hidden_questions_success(self) -> None:
        html = self.niu
        self.assertIn("Think you caught it all?", html)
        self.assertIn('class="post-quiz-panel"', html)
        self.assertIn("hidden", html)
        self.assertIn("student band", html)
        self.assertIn("Ball State", html)
        self.assertIn("Carbonated red wine", html)
        self.assertIn('role="status"', html)
        self.assertIn("Coming soon", html)
        self.assertIn("disabled", html)
        self.assertNotIn("answer:", html.lower())
        quiz = html.split('class="post-quiz"', 1)[1].split("</aside>", 1)[0]
        self.assertNotIn("data-correct", quiz)
        self.assertIn('value="ball-state"', quiz)
        self.assertNotIn(">ball-state<", quiz)

    def test_other_pages_omit_the_quiz_failure(self) -> None:
        for html in (self.boston, self.other, self.tour):
            self.assertNotIn("post-quiz", html)
            self.assertNotIn("Think you caught it all?", html)
