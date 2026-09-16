from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories that hold generated, vendored, or per-session files. `__marimo__`
# is marimo's own session cache (gitignored); the rest never contain notebooks.
_SKIP_DIRS = {".git", ".venv", "__marimo__", "__pycache__", "node_modules", "results"}

# Every notebook marimo generates carries this line at column zero. Matching on
# it (rather than on a hand-maintained list) means a newly scaffolded bot is
# covered the moment it lands, which is the whole point of this test. The
# column-zero anchor matters: tests that assert *about* notebooks quote this
# same text as an indented string literal and must not be mistaken for one.
_NOTEBOOK_MARKER = "app = marimo.App("


def is_notebook(path: Path) -> bool:
    return any(
        line.startswith(_NOTEBOOK_MARKER)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def discover_notebooks() -> list[Path]:
    """Every marimo notebook tracked in the repo, sorted for stable output."""
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.py")
        if not _SKIP_DIRS.intersection(path.parts) and is_notebook(path)
    )


class MarimoNotebookCheckTests(unittest.TestCase):
    def test_discovery_finds_the_known_notebooks(self) -> None:
        # Guards the glob itself: if discovery silently matched nothing, the
        # check below would pass vacuously and stop protecting anything.
        relative = {str(path.relative_to(REPO_ROOT)) for path in discover_notebooks()}

        expected = {
            "applications/notebook_harness/replay.py",
            "integrations/external/bots/random_bot.py",
            "integrations/external/templates/bots/build_your_bot_here.py",
            "operations/research/bot_lab_dashboard.py",
            "operations/research/map_metrics_dashboard.py",
            "operations/research/xg_bot_training_dashboard.py",
        }
        self.assertTrue(
            expected.issubset(relative),
            msg=f"missing notebooks: {sorted(expected - relative)}",
        )

    def test_every_notebook_passes_marimo_check(self) -> None:
        notebooks = discover_notebooks()
        self.assertGreater(len(notebooks), 1, "no marimo notebooks discovered")

        # One invocation over every file: marimo check reports each issue with
        # its own path and line, so a single failure message stays actionable.
        result = subprocess.run(
            [sys.executable, "-m", "marimo", "check", *[str(path) for path in notebooks]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stdout or result.stderr)


if __name__ == "__main__":
    unittest.main()
