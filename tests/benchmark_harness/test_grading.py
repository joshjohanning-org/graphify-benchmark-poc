import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.grading import (
    TaskDefinitionError,
    grade_task,
    validate_task,
)


def analysis_task():
    return {
        "id": "analysis-flow",
        "title": "Trace the order flow",
        "category": "analysis",
        "prompt": "Explain the order flow.",
        "grader": {
            "expected_targets": [
                {
                    "id": "service",
                    "values": ["OrderService"],
                    "sources": ["answer"],
                    "weight": 2,
                },
                {
                    "id": "repository",
                    "values": [r"OrderRepository"],
                    "match": "regex",
                    "sources": ["events"],
                    "weight": 1,
                },
            ],
            "false_positive_patterns": [
                {"pattern": r"always safe", "penalty": 0.2},
            ],
            "objective_pass_score": 0.8,
        },
    }


def implementation_task():
    return {
        "id": "implementation-change",
        "title": "Add total calculation",
        "category": "implementation",
        "prompt": "Implement total calculation.",
        "validation": {"command": "python3 -m unittest"},
        "grader": {
            "expected_targets": [
                {
                    "id": "function",
                    "values": ["def calculate_total"],
                    "sources": ["diff"],
                },
                {
                    "id": "changed-file",
                    "values": ["src/calculator.py"],
                    "sources": ["status"],
                },
            ],
            "validation_weight": 0.25,
            "validation_required": True,
            "objective_pass_score": 0.9,
        },
    }


class TaskValidationTests(unittest.TestCase):
    def test_validate_task_accepts_supported_analysis_definition(self):
        validate_task(analysis_task(), "analysis.json")

    def test_validate_task_rejects_invalid_target_regex(self):
        task = analysis_task()
        task["grader"]["expected_targets"][1]["values"] = ["("]

        with self.assertRaisesRegex(TaskDefinitionError, "invalid regex"):
            validate_task(task, "analysis.json")

    def test_validate_task_rejects_missing_required_field(self):
        task = analysis_task()
        del task["prompt"]

        with self.assertRaisesRegex(TaskDefinitionError, "missing required field"):
            validate_task(task, "analysis.json")

    def test_validate_task_rejects_validation_weight_without_command(self):
        task = implementation_task()
        del task["validation"]

        with self.assertRaisesRegex(
            TaskDefinitionError,
            "assigns validation_weight but has no validation.command",
        ):
            validate_task(task, "implementation.json")


class GradingTests(unittest.TestCase):
    def test_analysis_grade_applies_false_positive_penalty(self):
        task = analysis_task()

        grade = grade_task(
            task,
            final_answer="OrderService is always safe.",
            events_text='{"content":"OrderRepository"}',
            git_diff="",
            git_status="",
            validation_exit_code=None,
        )

        self.assertEqual(1.0, grade["target_score_before_penalty"])
        self.assertEqual(0.8, grade["correctness_score"])
        self.assertEqual(["service", "repository"], grade["found_expected_targets"])
        self.assertEqual([], grade["missing_expected_targets"])
        self.assertEqual([r"always safe"], grade["false_positives"])
        self.assertEqual(0.2, grade["false_positive_penalty"])
        self.assertTrue(grade["objective_pass"])
        self.assertFalse(grade["validation_passed"])

    def test_implementation_grade_requires_successful_validation(self):
        task = implementation_task()
        common = {
            "task": task,
            "final_answer": "Implemented the requested function.",
            "events_text": "",
            "git_diff": "+def calculate_total(items):\n+    return sum(items)\n",
            "git_status": " M src/calculator.py\n",
        }

        failed = grade_task(validation_exit_code=1, **common)
        passed = grade_task(validation_exit_code=0, **common)

        self.assertEqual(0.75, failed["correctness_score"])
        self.assertFalse(failed["objective_pass"])
        self.assertFalse(failed["validation_passed"])
        self.assertEqual(1.0, passed["correctness_score"])
        self.assertTrue(passed["objective_pass"])
        self.assertTrue(passed["validation_passed"])


if __name__ == "__main__":
    unittest.main()
