"""Daily Pages rebuild: the stadium list is fetched at build time, so the cron must POST the hook."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily-rebuild.yml"
README = REPO_ROOT / "README.md"
TODOS = REPO_ROOT / "TODOS.md"
RUN_RE = re.compile(r"(?m)^        run: \|\n((?:          .*\n)+)")


def run_script(workflow: str) -> str:
    match = RUN_RE.search(workflow)
    if not match:
        raise AssertionError("daily-rebuild.yml is missing its run block")
    lines = [line[10:] for line in match.group(1).splitlines()]
    return "\n".join(lines) + "\n"


class DailyRebuildWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        self.script = run_script(self.workflow)

    def test_schedule_posts_production_hook_success(self) -> None:
        self.assertIn('cron: "0 12 * * *"', self.workflow)
        self.assertIn("America/Chicago", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("secrets.CLOUDFLARE_PAGES_DEPLOY_HOOK", self.workflow)
        self.assertIn("curl --fail", self.script)
        self.assertIn('"$CLOUDFLARE_PAGES_DEPLOY_HOOK"', self.script)

        hook = "https://example.invalid/pages-deploy-hook"
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            record = bin_dir / "curl-args"
            curl = bin_dir / "curl"
            curl.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$CURL_ARGS_FILE\"\nexit 0\n",
                encoding="utf-8",
            )
            curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CLOUDFLARE_PAGES_DEPLOY_HOOK"] = hook
            env["CURL_ARGS_FILE"] = str(record)
            result = subprocess.run(
                ["bash", "-c", self.script],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            args = record.read_text(encoding="utf-8").splitlines()
        self.assertIn("--fail", args)
        self.assertIn("POST", args)
        self.assertEqual(args[-1], hook)

    def test_missing_secret_fails_with_setup_hint_failure(self) -> None:
        for hook in (None, ""):
            env = os.environ.copy()
            if hook is None:
                env.pop("CLOUDFLARE_PAGES_DEPLOY_HOOK", None)
            else:
                env["CLOUDFLARE_PAGES_DEPLOY_HOOK"] = hook
            env["PATH"] = "/usr/bin:/bin"
            result = subprocess.run(
                ["bash", "-c", self.script],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            with self.subTest(hook=hook):
                self.assertEqual(result.returncode, 1)
                self.assertIn("CLOUDFLARE_PAGES_DEPLOY_HOOK is not set", result.stdout)
                self.assertIn("Add deploy hook", result.stdout)
                self.assertNotIn("curl:", result.stderr)

        readme = README.read_text(encoding="utf-8")
        self.assertIn("**Add deploy hook**", readme)
        self.assertIn("**Branch to build**", readme)
        self.assertIn("**New repository secret**", readme)
        self.assertIn("CLOUDFLARE_PAGES_DEPLOY_HOOK", readme)
        todos = TODOS.read_text(encoding="utf-8")
        self.assertNotIn(
            "- [ ] Consider cache-bust or refresh note for Eric",
            todos,
        )
        self.assertIn("daily-rebuild.yml", todos)
