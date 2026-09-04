"""Gym flip-card scoreboard from Pages CMS front matter on Eric’s Posts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHORTCODE = REPO_ROOT / "layouts" / "shortcodes" / "scoreboard.html"
PARTIAL = REPO_ROOT / "layouts" / "partials" / "scoreboard.html"
SINGLE_LAYOUT = REPO_ROOT / "layouts" / "_default" / "single.html"
PAGES_YML = REPO_ROOT / ".pages.yml"
SCOREBOARD_JS = REPO_ROOT / "static" / "js" / "scoreboard.js"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
BOSTON = REPO_ROOT / "content" / "posts" / "boston-college.md"
HUGO_TIMEOUT_SECONDS = 120

COLLECTION_RE = re.compile(
    r"(?m)^  - name: (posts|gradys-tour|da-breakdown-w-tad|jers-prospect-profiles)\n(.*?)(?=^  - name: |\Z)",
    re.DOTALL,
)

FIXTURE_POST = "\n".join(
    [
        "---",
        "title: Scoreboard Fixture",
        "slug: scoreboard-fixture",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:00:00Z",
        "draft: false",
        "scoreboard:",
        "  home: Boston College",
        "  home_score: 75",
        "  away: University of California",
        "  away_score: 86",
        "---",
        "Tip-off.",
        "",
    ]
)

FIXTURE_TRIPLE = "\n".join(
    [
        "---",
        "title: Triple Digit Fixture",
        "slug: scoreboard-triple",
        "author: eric-wisnewski",
        "date: 2026-09-04T00:01:00Z",
        "draft: false",
        "scoreboard:",
        "  home: DePaul",
        "  home_score: 102",
        "  away: UConn",
        "  away_score: 99",
        "---",
        "Overtime.",
        "",
    ]
)

FIXTURE_TOUR = "\n".join(
    [
        "---",
        "title: Tour Scoreboard Fixture",
        "slug: scoreboard-tour-fixture",
        "author: grady-davis",
        "date: 2026-09-04T00:02:00Z",
        "draft: false",
        "scoreboard:",
        "  home: Boston College",
        "  home_score: 75",
        "  away: University of California",
        "  away_score: 86",
        "---",
        "On the road.",
        "",
    ]
)

FIXTURE_OTHER_AUTHOR = "\n".join(
    [
        "---",
        "title: Other Author Scoreboard",
        "slug: scoreboard-other-author",
        "author: tyler-morales",
        "date: 2026-09-04T00:03:00Z",
        "draft: false",
        "scoreboard:",
        "  home: Boston College",
        "  home_score: 75",
        "  away: University of California",
        "  away_score: 86",
        "---",
        "Not Eric.",
        "",
    ]
)


def collection_block(pages_yml: str, name: str) -> str:
    for match in COLLECTION_RE.finditer(pages_yml):
        if match.group(1) == name:
            return match.group(0)
    return ""


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
    if not SCOREBOARD_JS.is_file():
        raise FileNotFoundError(SCOREBOARD_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(SCOREBOARD_JS.as_uri())};\n"
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


class ScoreboardSourceTests(unittest.TestCase):
    def test_cms_fields_live_only_on_posts_success(self) -> None:
        pages = PAGES_YML.read_text(encoding="utf-8")
        posts = collection_block(pages, "posts")
        self.assertIn("name: scoreboard", posts)
        self.assertIn("type: object", posts)
        self.assertIn("Home school", posts)
        self.assertIn("Visitor school", posts)
        self.assertIn("Home score", posts)
        self.assertIn("Visitor score", posts)
        self.assertIn("name: home_score", posts)
        self.assertIn("name: away_score", posts)
        layout = SINGLE_LAYOUT.read_text(encoding="utf-8")
        self.assertIn('partial "scoreboard.html"', layout)
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertTrue(PARTIAL.is_file())
        self.assertIn("eric-wisnewski", src)
        self.assertIn('eq .Section "posts"', src)
        self.assertIn('type="button"', src)
        self.assertIn("aria-label", src)
        self.assertIn("/js/scoreboard.js", src)
        self.assertNotIn("run it back", src.lower())
        self.assertNotIn("scoreboard-hint", src)

    def test_other_collections_and_shortcode_stay_out_failure(self) -> None:
        pages = PAGES_YML.read_text(encoding="utf-8")
        for name in ("gradys-tour", "da-breakdown-w-tad", "jers-prospect-profiles"):
            with self.subTest(collection=name):
                self.assertNotIn("name: scoreboard", collection_block(pages, name))
        self.assertFalse(SHORTCODE.is_file())
        src = PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("Boston College", src)
        self.assertNotIn('homeScore="75"', src)
        content = (REPO_ROOT / "layouts" / "partials" / "page-content.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("scoreboard.js", content)

    def test_flip_styles_look_like_gym_cards_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".scoreboard", css)
        self.assertIn(".scoreboard-digit", css)
        self.assertIn("perspective", css)
        self.assertIn("rotateX", css)
        self.assertIn(".scoreboard-digit-leaf-top", css)
        self.assertIn("@keyframes scoreboard-fold-top", css)
        self.assertIn("var(--font-sans)", css)
        js = SCOREBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", js)
        self.assertIn("isIntersecting", js)
        self.assertNotIn("extraLaps", js)
        self.assertIn("countUpFrames", js)
        self.assertIn("addEventListener", js)
        self.assertIn("var(--bg)", css)
        self.assertIn(".scoreboard:focus-visible", css)

    def test_board_is_not_a_dark_keyboard_trap_failure(self) -> None:
        src = PARTIAL.read_text(encoding="utf-8")
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertNotIn('role="img"', src)
        self.assertNotIn('tabindex="0"', src)
        self.assertNotIn("background: #141414", css)
        self.assertNotIn("background: #0b0b0b", css)
        self.assertNotIn("7-segment", css)
        self.assertNotIn("scoreboard-hint", css)
        self.assertNotIn("Tap to run it back", src)

    def test_readme_documents_cms_fields_success(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("scoreboard", text)
        self.assertIn("Home score", text)
        self.assertIn("Home school", text)
        self.assertNotIn("{{< scoreboard", text)

    def test_boston_college_post_mocks_cms_front_matter_success(self) -> None:
        post = BOSTON.read_text(encoding="utf-8")
        self.assertIn("scoreboard:", post)
        self.assertIn("home: Boston College", post)
        self.assertIn("away: University of California", post)
        self.assertNotIn("away: Cal", post)
        self.assertIn("home_score: 75", post)
        self.assertIn("away_score: 86", post)
        self.assertNotIn("{{< scoreboard", post)


class ScoreboardJsTests(unittest.TestCase):
    def test_clamp_score_keeps_basketball_totals_success(self) -> None:
        self.assertEqual(call_fn("clampScore", 75), 75)
        self.assertEqual(call_fn("clampScore", 102), 102)
        self.assertEqual(call_fn("clampScore", 0), 0)

    def test_clamp_score_rejects_junk_failure(self) -> None:
        self.assertEqual(call_fn("clampScore", -4), 0)
        self.assertEqual(call_fn("clampScore", "nope"), 0)
        self.assertEqual(call_fn("clampScore", 1000), 999)

    def test_score_width_pads_to_two_or_three_success(self) -> None:
        self.assertEqual(call_fn("scoreWidth", 75, 86), 2)
        self.assertEqual(call_fn("scoreWidth", 102, 99), 3)
        self.assertEqual(call_fn("scoreDigits", 75, 2), [7, 5])
        self.assertEqual(call_fn("scoreDigits", 8, 2), [0, 8])
        self.assertEqual(call_fn("scoreDigits", 102, 3), [1, 0, 2])

    def test_score_digits_do_not_drop_leading_zero_failure(self) -> None:
        self.assertNotEqual(call_fn("scoreDigits", 8, 2), [8])
        self.assertEqual(call_fn("scoreWidth", 99, 99), 2)

    def test_count_up_frames_rise_to_the_final_success(self) -> None:
        frames = call_fn("countUpFrames", 3, 5)
        self.assertEqual(
            frames,
            [
                {"home": 1, "away": 1},
                {"home": 2, "away": 2},
                {"home": 3, "away": 3},
                {"home": 3, "away": 4},
                {"home": 3, "away": 5},
            ],
        )
        long_frames = call_fn("countUpFrames", 75, 86)
        self.assertEqual(long_frames[-1], {"home": 75, "away": 86})
        self.assertEqual(len(long_frames), 86)
        self.assertEqual(sum(1 for frame in long_frames if frame == {"home": 75, "away": 86}), 1)

    def test_count_up_frames_do_not_wrap_through_zero_failure(self) -> None:
        frames = call_fn("countUpFrames", 12, 12)
        homes = [frame["home"] for frame in frames]
        self.assertNotIn(0, homes)
        self.assertEqual(homes, list(range(1, 13)))
        self.assertNotEqual(homes[-2:], [0, 12])

    def test_play_scoreboard_lands_on_the_final_success(self) -> None:
        payload = call_js(
            "playScoreboard",
            """
function digit(n) {
  const texts = [{ textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }];
  return {
    dataset: { digit: String(n) },
    classList: { add() {}, remove() {} },
    querySelector() { return texts[0]; },
    querySelectorAll() { return texts; }
  };
}
const homeCards = [digit(0), digit(0)];
const awayCards = [digit(0), digit(0)];
const root = {
  dataset: {},
  classList: { add() {}, remove() {} },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return { querySelectorAll() { return homeCards; } };
    if (sel === '[data-side="away"]') return { querySelectorAll() { return awayCards; } };
    return null;
  }
};
playScoreboard(root, { homeScore: 75, awayScore: 86, width: 2 }, () => Promise.resolve()).then(() => {
  console.log(JSON.stringify({
    home: homeCards.map((c) => c.dataset.digit),
    away: awayCards.map((c) => c.dataset.digit),
    busy: root.dataset.busy
  }));
});
""",
        )
        self.assertEqual(payload["home"], ["7", "5"])
        self.assertEqual(payload["away"], ["8", "6"])
        self.assertNotEqual(payload["busy"], "1")

    def test_play_scoreboard_does_not_leave_zeros_failure(self) -> None:
        payload = call_js(
            "playScoreboard",
            """
function digit(n) {
  const texts = [{ textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }];
  return {
    dataset: { digit: String(n) },
    classList: { add() {}, remove() {} },
    querySelector() { return texts[0]; },
    querySelectorAll() { return texts; }
  };
}
const homeCards = [digit(0), digit(0)];
const awayCards = [digit(0), digit(0)];
const root = {
  dataset: {},
  classList: { add() {}, remove() {} },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return { querySelectorAll() { return homeCards; } };
    if (sel === '[data-side="away"]') return { querySelectorAll() { return awayCards; } };
    return null;
  }
};
playScoreboard(root, { homeScore: 75, awayScore: 86, width: 2 }, () => Promise.resolve()).then(() => {
  console.log(JSON.stringify({
    home: homeCards.map((c) => c.dataset.digit),
    away: awayCards.map((c) => c.dataset.digit)
  }));
});
""",
        )
        self.assertNotEqual(payload["home"], ["0", "0"])
        self.assertNotEqual(payload["away"], ["0", "0"])

    def test_play_scoreboard_counts_to_the_final_once_success(self) -> None:
        payload = call_js(
            "playScoreboard",
            """
function digit(n) {
  const texts = [{ textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }];
  return {
    dataset: { digit: String(n) },
    classList: { add() {}, remove() {} },
    querySelector() { return texts[0]; },
    querySelectorAll() { return texts; }
  };
}
const homeCards = [digit(0), digit(0)];
const awayCards = [digit(0), digit(0)];
const root = {
  dataset: {},
  classList: { add() {}, remove() {} },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return { querySelectorAll() { return homeCards; } };
    if (sel === '[data-side="away"]') return { querySelectorAll() { return awayCards; } };
    return null;
  }
};
const history = [];
playScoreboard(root, { homeScore: 12, awayScore: 12, width: 2 }, () => {
  history.push({
    home: Number(homeCards.map((c) => c.dataset.digit).join('')),
    away: Number(awayCards.map((c) => c.dataset.digit).join(''))
  });
  return Promise.resolve();
}).then(() => {
  console.log(JSON.stringify({
    history,
    finals: history.filter((frame) => frame.home === 12 && frame.away === 12).length
  }));
});
""",
        )
        homes = [frame["home"] for frame in payload["history"]]
        aways = [frame["away"] for frame in payload["history"]]
        self.assertEqual(payload["history"][0], {"home": 1, "away": 1})
        self.assertEqual(payload["history"][-1], {"home": 12, "away": 12})
        self.assertEqual(homes, list(range(1, 13)))
        self.assertEqual(aways, list(range(1, 13)))
        self.assertEqual(payload["finals"], 1)
        self.assertEqual(len(payload["history"]), 12)

    def test_play_scoreboard_does_not_run_a_second_lap_failure(self) -> None:
        payload = call_js(
            "playScoreboard",
            """
function digit(n) {
  const texts = [{ textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }, { textContent: String(n) }];
  return {
    dataset: { digit: String(n) },
    classList: { add() {}, remove() {} },
    querySelector() { return texts[0]; },
    querySelectorAll() { return texts; }
  };
}
const homeCards = [digit(0), digit(0)];
const awayCards = [digit(0), digit(0)];
const root = {
  dataset: {},
  classList: { add() {}, remove() {} },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return { querySelectorAll() { return homeCards; } };
    if (sel === '[data-side="away"]') return { querySelectorAll() { return awayCards; } };
    return null;
  }
};
const history = [];
playScoreboard(root, { homeScore: 12, awayScore: 12, width: 2, extraLaps: 1 }, () => {
  history.push(Number(homeCards.map((c) => c.dataset.digit).join('')));
  return Promise.resolve();
}).then(() => {
  console.log(JSON.stringify({
    history,
    zerosAfterStart: history.slice(1).includes(0),
    len: history.length
  }));
});
""",
        )
        self.assertEqual(payload["len"], 12)
        self.assertFalse(payload["zerosAfterStart"])
        self.assertNotEqual(payload["history"][-2:], [0, 12])
        js = SCOREBOARD_JS.read_text(encoding="utf-8")
        self.assertNotIn("extraLaps", js)

    def test_board_in_view_when_rect_crosses_the_fold_success(self) -> None:
        payload = call_js(
            "isBoardInView",
            """
const visible = isBoardInView({ getBoundingClientRect() { return { top: 400, bottom: 700 }; } }, 800);
const below = isBoardInView({ getBoundingClientRect() { return { top: 900, bottom: 1100 }; } }, 800);
console.log(JSON.stringify({ visible, below }));
""",
        )
        self.assertTrue(payload["visible"])
        self.assertFalse(payload["below"])
        self.assertEqual(call_fn("digitStaggerMs", 0), 0)
        self.assertEqual(call_fn("digitStaggerMs", 1), 70)
        self.assertGreater(call_fn("digitStaggerMs", 1), call_fn("digitStaggerMs", 0))

    def test_mount_builds_digits_and_lands_on_the_score_success(self) -> None:
        payload = call_js(
            "mountScoreboard",
            """
const home = { innerHTML: '' };
const away = { innerHTML: '' };
const root = {
  dataset: { homeScore: '75', awayScore: '86' },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return home;
    if (sel === '[data-side="away"]') return away;
    return null;
  }
};
mountScoreboard(root, { animate: false });
console.log(JSON.stringify({ home: home.innerHTML, away: away.innerHTML }));
""",
        )
        self.assertIn('data-digit="7"', payload["home"])
        self.assertIn('data-digit="5"', payload["home"])
        self.assertIn('data-digit="8"', payload["away"])
        self.assertIn('data-digit="6"', payload["away"])
        self.assertIn("scoreboard-digit-leaf-top", payload["home"])

    def test_mount_does_not_leave_zeros_when_motion_is_off_failure(self) -> None:
        payload = call_js(
            "mountScoreboard",
            """
const home = { innerHTML: '' };
const root = {
  dataset: { homeScore: '75', awayScore: '86' },
  querySelector(sel) {
    return sel === '[data-side="home"]' ? home : { innerHTML: '' };
  }
};
mountScoreboard(root, { animate: false });
console.log(JSON.stringify(home.innerHTML.includes('data-digit="0"') && !home.innerHTML.includes('data-digit="7"')));
""",
        )
        self.assertFalse(payload)

    def test_mount_holds_zeros_until_the_flip_runs_success(self) -> None:
        payload = call_js(
            "mountScoreboard",
            """
const home = { innerHTML: '' };
const away = { innerHTML: '' };
const root = {
  dataset: { homeScore: '75', awayScore: '86' },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return home;
    if (sel === '[data-side="away"]') return away;
    return null;
  }
};
mountScoreboard(root, { animate: true, play: false });
console.log(JSON.stringify({
  home: home.innerHTML,
  away: away.innerHTML
}));
""",
        )
        self.assertIn('data-digit="0"', payload["home"])
        self.assertNotIn('data-digit="7"', payload["home"])
        self.assertIn('data-digit="0"', payload["away"])
        self.assertNotIn('data-digit="8"', payload["away"])

    def test_init_plays_when_the_board_scrolls_into_view_success(self) -> None:
        payload = call_js(
            "initScoreboards",
            """
const home = { innerHTML: '' };
const away = { innerHTML: '' };
let observed = 0;
let disconnected = 0;
let handler;
const board = {
  classList: { add() {}, remove() {} },
  dataset: { homeScore: '75', awayScore: '86' },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return home;
    if (sel === '[data-side="away"]') return away;
    return null;
  }
};
const doc = { querySelectorAll() { return [board]; } };
initScoreboards(doc, (cb) => {
  handler = cb;
  return {
    observe() { observed += 1; },
    disconnect() { disconnected += 1; }
  };
}, { reducedMotion: false, wait: () => Promise.resolve() });
const beforePlayed = board.dataset.played;
const beforeSeven = home.innerHTML.includes('data-digit="7"');
handler([{ isIntersecting: true }]);
console.log(JSON.stringify({
  observed,
  disconnected,
  beforePlayed: beforePlayed === '1',
  beforeSeven,
  zeros: home.innerHTML.includes('data-digit="0"'),
  played: board.dataset.played === '1'
}));
""",
        )
        self.assertEqual(payload["observed"], 1)
        self.assertEqual(payload["disconnected"], 1)
        self.assertFalse(payload["beforePlayed"])
        self.assertFalse(payload["beforeSeven"])
        self.assertTrue(payload["zeros"])
        self.assertTrue(payload["played"])

    def test_init_does_not_play_before_intersection_failure(self) -> None:
        payload = call_js(
            "initScoreboards",
            """
const home = { innerHTML: '' };
const board = {
  classList: { add() {}, remove() {} },
  dataset: { homeScore: '75', awayScore: '86' },
  querySelector() { return home; }
};
const doc = { querySelectorAll() { return [board]; } };
initScoreboards(doc, () => ({ observe() {}, disconnect() {} }), {
  reducedMotion: false,
  wait: () => Promise.resolve()
});
console.log(JSON.stringify({
  played: board.dataset.played === '1',
  landed: home.innerHTML.includes('data-digit="7"')
}));
""",
        )
        self.assertFalse(payload["played"])
        self.assertFalse(payload["landed"])

    def test_replay_runs_the_board_again_success(self) -> None:
        payload = call_js(
            "replayScoreboard",
            """
const home = { innerHTML: 'old' };
const away = { innerHTML: 'old' };
const root = {
  dataset: {},
  classList: { add() {}, remove() {} },
  querySelector(sel) {
    if (sel === '[data-side="home"]') return home;
    if (sel === '[data-side="away"]') return away;
    return null;
  }
};
root.dataset.homeScore = '75';
root.dataset.awayScore = '86';
const result = replayScoreboard(root, { animate: true, wait: () => Promise.resolve() });
Promise.resolve(result).then((ok) => {
  console.log(JSON.stringify({
    ok,
    zeros: home.innerHTML.includes('data-digit="0"'),
    busyCleared: root.dataset.busy !== '1'
  }));
});
""",
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["zeros"])
        self.assertTrue(payload["busyCleared"])

    def test_replay_does_not_stack_while_busy_failure(self) -> None:
        payload = call_js(
            "replayScoreboard",
            """
const root = {
  dataset: { busy: '1', homeScore: '75', awayScore: '86' },
  querySelector() { return { innerHTML: 'stay' }; }
};
console.log(JSON.stringify(replayScoreboard(root, { animate: true })));
""",
        )
        self.assertFalse(payload)


class ScoreboardBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = Path(tempfile.mkdtemp(prefix="scoreboard-hugo-"))
        content_dir = cls._tmp / "content"
        shutil.copytree(REPO_ROOT / "content", content_dir)
        (content_dir / "posts" / "scoreboard-fixture.md").write_text(
            FIXTURE_POST, encoding="utf-8"
        )
        (content_dir / "posts" / "scoreboard-triple.md").write_text(
            FIXTURE_TRIPLE, encoding="utf-8"
        )
        (content_dir / "posts" / "scoreboard-other-author.md").write_text(
            FIXTURE_OTHER_AUTHOR, encoding="utf-8"
        )
        (content_dir / "gradys-tour" / "scoreboard-tour-fixture.md").write_text(
            FIXTURE_TOUR, encoding="utf-8"
        )
        dest = cls._tmp / "out"
        result = run_hugo(destination=dest, content_dir=content_dir)
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(
                "hugo build failed; check that hugo is on PATH and the site is valid:"
                f"\n{result.stderr}"
            )
        try:
            cls.fixture = (dest / "posts" / "scoreboard-fixture" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.triple = (dest / "posts" / "scoreboard-triple" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.other = (
                dest / "posts" / "scoreboard-other-author" / "index.html"
            ).read_text(encoding="utf-8")
            cls.tour = (
                dest / "gradys-tour" / "scoreboard-tour-fixture" / "index.html"
            ).read_text(encoding="utf-8")
            cls.boston = (dest / "posts" / "boston-college" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.hello = (dest / "posts" / "hello-again" / "index.html").read_text(
                encoding="utf-8"
            )
            cls.niu = (dest / "posts" / "northern-illinois" / "index.html").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest(f"built output missing: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_front_matter_renders_teams_and_final_success(self) -> None:
        html = self.fixture
        self.assertEqual(html.count('class="scoreboard"'), 1)
        self.assertIn('data-home-score="75"', html)
        self.assertIn('data-away-score="86"', html)
        self.assertIn("Boston College", html)
        self.assertIn("University of California", html)
        self.assertIn(
            'aria-label="Final score: Boston College 75, University of California 86"',
            html,
        )
        self.assertIn("<button", html)
        self.assertIn('type="button"', html)
        self.assertIn("/js/scoreboard.js", html)
        self.assertEqual(html.count("/js/scoreboard.js"), 1)
        self.assertIn("DePaul", self.triple)
        self.assertIn('data-width="3"', self.triple)
        self.assertIn('data-home-score="102"', self.triple)

    def test_board_stays_off_non_eric_pages_failure(self) -> None:
        self.assertNotIn('class="scoreboard"', self.tour)
        self.assertNotIn("/js/scoreboard.js", self.tour)
        self.assertNotIn('class="scoreboard"', self.other)
        self.assertNotIn("/js/scoreboard.js", self.other)
        self.assertNotIn("{{< scoreboard", self.fixture)

    def test_board_stays_off_when_cms_fields_are_empty_failure(self) -> None:
        self.assertNotIn('class="scoreboard"', self.hello)
        self.assertNotIn("/js/scoreboard.js", self.hello)
        self.assertNotIn('class="scoreboard"', self.niu)
        self.assertNotIn("/js/scoreboard.js", self.niu)

    def test_boston_college_page_includes_the_demo_board_success(self) -> None:
        self.assertIn('class="scoreboard"', self.boston)
        self.assertIn('data-home-score="75"', self.boston)
        self.assertIn('data-away-score="86"', self.boston)
        self.assertIn("/js/scoreboard.js", self.boston)


if __name__ == "__main__":
    unittest.main()
