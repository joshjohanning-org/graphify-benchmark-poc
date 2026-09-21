import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.cli import main
from graphify_benchmark.runner import BenchmarkRunner


class SmokeSafetyTests(unittest.TestCase):
    def test_smoke_requires_explicit_paid_run_confirmation(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["smoke", "--task", "trace-trade-submission"])

        self.assertEqual(2, exit_code)
        self.assertIn("--confirm-paid-run", stderr.getvalue())

    def test_smoke_creates_one_non_scored_treatment_run_without_pair_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / "tasks"
            results_dir = root / "results"
            tasks_dir.mkdir()
            (tasks_dir / "task.json").write_text(
                json.dumps(
                    {
                        "id": "one-task",
                        "title": "One task",
                        "category": "analysis",
                        "prompt": "Inspect one thing.",
                        "grader": {
                            "expected_targets": [
                                {"id": "target", "values": ["Target"]}
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner = BenchmarkRunner(
                {
                    "repo_ref": "abc123",
                    "graphify_server": "graphify",
                    "_resolved_graphify_skill_source": "/tmp/graphify",
                },
                root,
                tasks_dir,
                results_dir,
            )
            metrics = {
                "condition_valid": True,
                "graphify_skill_staged": True,
                "graphify_skill_loaded": True,
                "graphify_skill_runtime_loaded": None,
                "graphify_skill_valid": True,
            }

            with mock.patch.object(
                runner, "_run_one", return_value=metrics
            ) as run_one:
                output = runner.smoke("one-task")

            args, kwargs = run_one.call_args
            self.assertEqual("graphify_on", args[1]["condition"])
            self.assertEqual("one-task", args[2]["id"])
            self.assertFalse(kwargs["scored"])
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertFalse(manifest["scored"])
            self.assertEqual(1, len(manifest["plan"]))
            self.assertTrue((output / "SMOKE.md").is_file())
            self.assertTrue((output / "smoke.json").is_file())
            self.assertFalse((output / "report.json").exists())
            self.assertFalse((output / "runs.csv").exists())


if __name__ == "__main__":
    unittest.main()
