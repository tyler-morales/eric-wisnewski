"""404 airball gym: Matter.js basketball on the not-found page."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOT_FOUND_LAYOUT = REPO_ROOT / "layouts" / "404.html"
AIRBALL_JS = REPO_ROOT / "static" / "js" / "airball.js"
STYLE_CSS = REPO_ROOT / "assets" / "css" / "style.css"
README = REPO_ROOT / "README.md"
HEAD_PARTIAL = REPO_ROOT / "layouts" / "partials" / "head.html"


def call_airball(fn_name: str, script_body: str) -> object:
    if not AIRBALL_JS.is_file():
        raise FileNotFoundError(AIRBALL_JS)
    script = (
        f"import {{ {fn_name} }} from {json.dumps(AIRBALL_JS.as_uri())};\n"
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


class AirballTemplateTests(unittest.TestCase):
    def test_404_layout_wires_gym_and_escape_success(self) -> None:
        text = NOT_FOUND_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("header.html", text)
        self.assertIn("404 — airball", text)
        self.assertIn("Page not found", text)
        self.assertIn("Sink one to feel better", text)
        self.assertIn('data-airball', text)
        self.assertIn("airball-court", text)
        self.assertIn("matter-js", text)
        self.assertIn("/js/airball.js", text)
        self.assertIn('href="{{ "/" | relURL }}"', text)
        self.assertIn("Back to the home page", text)
        self.assertIn("Eric's D1 Mission", text)
        self.assertIn("aria-live", text)
        self.assertNotIn("gradys-tour-country", text)

    def test_404_css_is_touch_and_keyboard_friendly_success(self) -> None:
        css = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn(".airball-court", css)
        self.assertIn("touch-action: none", css)
        self.assertIn(".airball-cta a:focus-visible", css)

    def test_404_stays_noindex_success(self) -> None:
        head = HEAD_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('eq .Kind "404"', head)
        self.assertIn("noindex", head)

    def test_readme_mentions_airball_404_success(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("404.html", text)
        self.assertIn("airball", text.lower())
        self.assertIn("Matter.js", text)


class AirballLogicTests(unittest.TestCase):
    def test_fling_toward_hoop_success(self) -> None:
        shot = call_airball(
            "flingVelocity",
            "console.log(JSON.stringify(flingVelocity(40, 200, 10, 280, 180)));",
        )
        self.assertGreater(shot["vx"], 0)
        self.assertLess(shot["vy"], 0)
        self.assertGreater(shot["dist"], 14)

    def test_fling_rejects_tiny_drag_failure(self) -> None:
        shot = call_airball(
            "flingVelocity",
            "console.log(JSON.stringify(flingVelocity(40, 200, 44, 198, 80)));",
        )
        self.assertEqual(shot["vx"], 0)
        self.assertEqual(shot["vy"], 0)

    def test_fling_clamps_max_speed_failure(self) -> None:
        shot = call_airball(
            "flingVelocity",
            "console.log(JSON.stringify(flingVelocity(0, 0, 800, -800, 32, { maxSpeed: 15, capDist: 100 })));",
        )
        speed = (shot["vx"] ** 2 + shot["vy"] ** 2) ** 0.5
        self.assertLessEqual(speed, 15.01)

    def test_make_when_ball_drops_through_rim_success(self) -> None:
        zone = {"left": 200, "right": 260, "top": 80, "bottom": 110}
        made = call_airball(
            "isMake",
            "console.log(JSON.stringify(isMake("
            '{ x: 230, y: 70, vx: 2, vy: 6, radius: 16 },'
            '{ x: 232, y: 92, vx: 2, vy: 7, radius: 16 },'
            f"{json.dumps(zone)})));",
        )
        self.assertTrue(made)

    def test_make_rejects_upward_or_wide_shots_failure(self) -> None:
        zone = {"left": 200, "right": 260, "top": 80, "bottom": 110}
        upward = call_airball(
            "isMake",
            "console.log(JSON.stringify(isMake("
            '{ x: 230, y: 92, vx: 1, vy: -4, radius: 16 },'
            '{ x: 230, y: 70, vx: 1, vy: -4, radius: 16 },'
            f"{json.dumps(zone)})));",
        )
        wide = call_airball(
            "isMake",
            "console.log(JSON.stringify(isMake("
            '{ x: 120, y: 70, vx: 2, vy: 6, radius: 16 },'
            '{ x: 120, y: 92, vx: 2, vy: 7, radius: 16 },'
            f"{json.dumps(zone)})));",
        )
        self.assertFalse(upward)
        self.assertFalse(wide)

    def test_court_puts_hoop_right_of_ball_success(self) -> None:
        layout = call_airball(
            "courtLayout",
            "console.log(JSON.stringify(courtLayout(800, 420)));",
        )
        self.assertGreater(layout["rimFrontX"], layout["ballX"])
        self.assertGreater(layout["rimBackX"], layout["rimFrontX"])
        self.assertLess(layout["hoopY"], layout["floorTop"])
        self.assertGreater(layout["zone"]["right"], layout["zone"]["left"])

    def test_reset_after_miss_not_before_shot_failure(self) -> None:
        layout = call_airball(
            "courtLayout",
            "console.log(JSON.stringify(courtLayout(800, 420)));",
        )
        idle = call_airball(
            "shouldResetBall",
            "const layout = "
            + json.dumps(layout)
            + ";\n"
            "const ball = { x: layout.ballX, y: layout.ballY, radius: layout.ballR, vx: 0, vy: 0 };\n"
            'console.log(JSON.stringify(shouldResetBall(ball, layout, { hasShot: false, aiming: false, made: false })));',
        )
        missed = call_airball(
            "shouldResetBall",
            "const layout = "
            + json.dumps(layout)
            + ";\n"
            "const ball = { x: -80, y: 200, radius: 16, vx: 1, vy: 2 };\n"
            'console.log(JSON.stringify(shouldResetBall(ball, layout, { hasShot: true, aiming: false, made: false })));',
        )
        self.assertFalse(idle)
        self.assertTrue(missed)

    def test_swish_velocity_aims_at_hoop_success(self) -> None:
        layout = call_airball(
            "courtLayout",
            "console.log(JSON.stringify(courtLayout(800, 420)));",
        )
        shot = call_airball(
            "swishVelocity",
            "console.log(JSON.stringify(swishVelocity(" + json.dumps(layout) + ")));",
        )
        self.assertGreater(shot["vx"], 0)
        self.assertLess(shot["vy"], 0)

    def test_mix_shot_idle_stays_zero_failure(self) -> None:
        mixed = call_airball(
            "mixShot",
            "console.log(JSON.stringify(mixShot({ vx: 0, vy: 0, dist: 4 }, { vx: 6, vy: -14 }, 0.9)));",
        )
        self.assertEqual(mixed["vx"], 0)
        self.assertEqual(mixed["vy"], 0)

    def test_mix_shot_committed_pull_uses_swish_success(self) -> None:
        mixed = call_airball(
            "mixShot",
            "console.log(JSON.stringify(mixShot({ vx: 3, vy: -8, dist: 80 }, { vx: 6, vy: -12.4 }, 0.8)));",
        )
        self.assertAlmostEqual(mixed["vx"], 6)
        self.assertAlmostEqual(mixed["vy"], -12.4)

    def test_pointer_hit_target_success(self) -> None:
        hit = call_airball(
            "pointerInBall",
            "console.log(JSON.stringify(pointerInBall(50, 50, { x: 50, y: 50, radius: 16 }, 10)));",
        )
        miss = call_airball(
            "pointerInBall",
            "console.log(JSON.stringify(pointerInBall(200, 50, { x: 50, y: 50, radius: 16 }, 10)));",
        )
        self.assertTrue(hit)
        self.assertFalse(miss)
