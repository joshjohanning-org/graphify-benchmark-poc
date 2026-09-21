import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.report import (
    CSV_FIELDS,
    build_report,
    write_csv,
    write_json,
    write_markdown,
)


def make_run(
    pair_id,
    task_id,
    category,
    condition,
    objective_pass,
    correctness_score,
    wall_time_seconds,
    condition_valid=True,
    exploration_before_target=2,
):
    position = 1 if condition == "graphify_on" else 2
    return {
        "run_id": "%s-%s" % (pair_id, condition),
        "pair_id": pair_id,
        "task_id": task_id,
        "category": category,
        "condition": condition,
        "condition_valid": condition_valid,
        "condition_invalid_reason": None if condition_valid else "treatment mismatch",
        "position": position,
        "repetition": int(pair_id.rsplit("r", 1)[1]),
        "objective_pass": objective_pass,
        "correctness_score": correctness_score,
        "wall_time_seconds": wall_time_seconds,
        "session_duration_ms": wall_time_seconds * 1000,
        "ai_credits_nano": 100,
        "input_tokens": 20,
        "cache_read_tokens": 5,
        "cache_write_tokens": 0,
        "output_tokens": 10,
        "graphify_invocation_count": 1 if condition == "graphify_on" else 0,
        "graphify_targeted_follow_up_count": 1 if condition == "graphify_on" else 0,
        "search_call_count": 2,
        "broad_search_count": 1,
        "targeted_search_count": 1,
        "unique_files_read_count": 2,
        "exploration_before_first_correct_target": exploration_before_target,
        "tool_failure_count": 0,
        "model_failure_count": 0,
        "mcp_failure_count": 0,
        "validation_exit_code": 0,
        "copilot_exit_code": 0,
        "artifact_directory": "runs/%s-%s" % (pair_id, condition),
        "run_error": None,
    }


def sample_runs():
    return [
        make_run("analysis-flow-r1", "analysis-flow", "analysis", "graphify_on", True, 0.9, 4.0),
        make_run("analysis-flow-r1", "analysis-flow", "analysis", "graphify_off", True, 0.7, 6.0),
        make_run("implementation-change-r1", "implementation-change", "implementation", "graphify_on", False, 0.4, 8.0),
        make_run("implementation-change-r1", "implementation-change", "implementation", "graphify_off", True, 0.8, 10.0),
        make_run("analysis-flow-r2", "analysis-flow", "analysis", "graphify_on", True, 0.8, 12.0),
        make_run(
            "analysis-flow-r2",
            "analysis-flow",
            "analysis",
            "graphify_off",
            True,
            0.795,
            14.0,
            exploration_before_target=None,
        ),
        make_run(
            "implementation-change-r2",
            "implementation-change",
            "implementation",
            "graphify_on",
            True,
            1.0,
            1.0,
            condition_valid=False,
        ),
        make_run(
            "implementation-change-r2",
            "implementation-change",
            "implementation",
            "graphify_off",
            False,
            0.0,
            100.0,
        ),
    ]


def metadata():
    return {
        "created_at": "2026-09-16T14:00:00+00:00",
        "repo_ref": "abc123",
        "model": "test-model",
        "reasoning_effort": "medium",
        "graphify_server": "graphify-main",
        "treatment_mode": "mcp_only",
        "seed": 1729,
        "pilot": False,
        "repetitions": 2,
    }


class ReportTests(unittest.TestCase):
    def test_build_report_summarizes_wins_ties_losses_and_conditions(self):
        report = build_report(sample_runs(), metadata(), tie_tolerance=0.01)

        self.assertEqual(
            {"win": 1, "tie": 1, "loss": 1, "invalid": 1},
            report["summary"]["win_tie_loss_for_graphify"],
        )
        analysis = report["summary"]["tasks"]["analysis-flow"]
        self.assertEqual(
            {"win": 1, "tie": 1, "loss": 0, "invalid": 0},
            analysis["win_tie_loss"],
        )
        self.assertEqual(0.85, analysis["graphify_on"]["mean_correctness_score"])
        self.assertEqual(0.748, analysis["graphify_off"]["mean_correctness_score"])
        self.assertEqual(8.0, analysis["graphify_on"]["median_wall_time_seconds"])
        self.assertEqual(10.0, analysis["graphify_off"]["median_wall_time_seconds"])
        self.assertEqual(1, analysis["graphify_off"]["never_found_target_count"])

        implementation = report["summary"]["tasks"]["implementation-change"]
        self.assertEqual(
            {"win": 0, "tie": 0, "loss": 1, "invalid": 1},
            implementation["win_tie_loss"],
        )
        self.assertEqual(1, implementation["graphify_on"]["invalid_runs"])
        self.assertEqual(0.4, implementation["graphify_on"]["mean_correctness_score"])
        self.assertEqual(
            "invalid",
            report["paired_results"][-1]["outcome_for_graphify"],
        )

    def test_writers_generate_parseable_customer_reports(self):
        runs = sample_runs()
        report = build_report(runs, metadata(), tie_tolerance=0.01)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            json_path = output / "report.json"
            csv_path = output / "runs.csv"
            markdown_path = output / "REPORT.md"

            write_json(json_path, report)
            write_csv(csv_path, runs)
            write_markdown(markdown_path, report)

            json_report = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(report, json_report)
        self.assertEqual(8, len(csv_rows))
        self.assertEqual(CSV_FIELDS, list(csv_rows[0]))
        self.assertEqual("analysis-flow-r1-graphify_on", csv_rows[0]["run_id"])
        self.assertIn("# Graphify MCP-only Copilot CLI benchmark", markdown)
        self.assertIn("- Treatment mode: `mcp_only`", markdown)
        self.assertIn("| 1 | 1 | 1 | 1 |", markdown)
        self.assertIn("| Task | W/T/L/I |", markdown)
        self.assertIn("Never found target", markdown)
        self.assertIn("| implementation | graphify_on | 1/1 |", markdown)
        self.assertIn("## Task comparison", markdown)
        self.assertIn("## Category comparison", markdown)
        self.assertIn("## Raw runs", markdown)
        self.assertIn("## Metric cautions", markdown)

    def test_markdown_title_preregisters_skill_and_mcp_treatment(self):
        report_metadata = metadata()
        report_metadata["treatment_mode"] = "skill_and_mcp"
        report = build_report(sample_runs(), report_metadata, tie_tolerance=0.01)

        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "REPORT.md"
            write_markdown(markdown_path, report)
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual("skill_and_mcp", report["metadata"]["treatment_mode"])
        self.assertIn(
            "# Graphify skill + MCP Copilot CLI benchmark", markdown
        )
        self.assertIn("- Treatment mode: `skill_and_mcp`", markdown)

    def test_markdown_preregisters_forced_graphify_skill_cli_metadata(self):
        report_metadata = metadata()
        report_metadata.update(
            {
                "treatment_mode": "forced_graphify_skill_cli",
                "graphify_server": "graphify_adempiere",
                "forced_graphify_directive": "Use Graphify CLI first.",
                "order_limitation": "All controls run before all treatments.",
                "graphify_graph_setup": {
                    "sha256": "abc123",
                    "size_bytes": 42,
                    "build_duration_seconds": 7.5,
                    "build_cost_usd": 1.25,
                    "included_in_run_timing": False,
                },
            }
        )
        report = build_report(sample_runs(), report_metadata, tie_tolerance=0.01)

        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "REPORT.md"
            write_markdown(markdown_path, report)
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertIn(
            "# Graphify forced skill + CLI Copilot CLI benchmark", markdown
        )
        self.assertIn("- Treatment mode: `forced_graphify_skill_cli`", markdown)
        self.assertIn("Use Graphify CLI first.", markdown)
        self.assertIn("abc123", markdown)
        self.assertIn("`7.500` seconds", markdown)
        self.assertIn("`$1.250`", markdown)
        self.assertIn("All controls run before all treatments.", markdown)


if __name__ == "__main__":
    unittest.main()
