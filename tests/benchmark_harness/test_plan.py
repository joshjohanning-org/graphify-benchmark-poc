import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.config import (
    balanced_plan,
    forced_graphify_skill_cli_plan,
)


class BalancedPlanTests(unittest.TestCase):
    def test_balanced_plan_is_reproducible_for_a_seed(self):
        first = balanced_plan(["analysis-flow", "implementation-change"], 3, 1729)
        second = balanced_plan(["analysis-flow", "implementation-change"], 3, 1729)

        self.assertEqual(first, second)

    def test_balanced_plan_has_both_conditions_once_per_pair(self):
        plan = balanced_plan(["analysis-flow", "implementation-change"], 3, 1729)
        by_pair = defaultdict(list)
        for item in plan:
            by_pair[item["pair_id"]].append(item)

        self.assertEqual(12, len(plan))
        self.assertEqual(6, len(by_pair))
        for pair in by_pair.values():
            with self.subTest(pair_id=pair[0]["pair_id"]):
                self.assertEqual(
                    {"graphify_on", "graphify_off"},
                    {item["condition"] for item in pair},
                )
                self.assertEqual([1, 2], sorted(item["position"] for item in pair))
        self.assertEqual(
            Counter({"graphify_on": 6, "graphify_off": 6}),
            Counter(item["condition"] for item in plan),
        )

    def test_balanced_plan_counterbalances_first_position_per_task(self):
        task_ids = ["analysis-flow", "implementation-change", "edge-case"]
        plan = balanced_plan(task_ids, 5, 1729)

        for task_id in task_ids:
            first_positions = Counter(
                item["condition"]
                for item in plan
                if item["task_id"] == task_id and item["position"] == 1
            )
            with self.subTest(task_id=task_id):
                self.assertLessEqual(
                    abs(
                        first_positions["graphify_on"]
                        - first_positions["graphify_off"]
                    ),
                    1,
                )

    def test_single_repetition_balances_four_tasks_globally(self):
        plan = balanced_plan(["a", "b", "c", "d"], 1, 1729)
        first_positions = Counter(
            item["condition"] for item in plan if item["position"] == 1
        )

        self.assertEqual(
            Counter({"graphify_on": 2, "graphify_off": 2}),
            first_positions,
        )

    def test_single_repetition_odd_task_count_has_bounded_global_imbalance(self):
        plan = balanced_plan(["a", "b", "c", "d", "e"], 1, 1729)
        first_positions = Counter(
            item["condition"] for item in plan if item["position"] == 1
        )

        self.assertLessEqual(
            abs(
                first_positions["graphify_on"]
                - first_positions["graphify_off"]
            ),
            1,
        )

    def test_multiple_repetitions_alternate_first_condition_within_task(self):
        task_ids = ["analysis-flow", "implementation-change", "edge-case"]
        plan = balanced_plan(task_ids, 5, 1729)

        for task_id in task_ids:
            first_conditions = [
                item["condition"]
                for item in plan
                if item["task_id"] == task_id and item["position"] == 1
            ]
            with self.subTest(task_id=task_id):
                self.assertEqual(5, len(first_conditions))
                for previous, current in zip(
                    first_conditions, first_conditions[1:]
                ):
                    self.assertNotEqual(previous, current)

    def test_forced_graphify_skill_cli_plan_runs_controls_then_treatments(self):
        task_ids = ["a", "b", "c", "d"]

        plan = forced_graphify_skill_cli_plan(task_ids)

        self.assertEqual(
            ["graphify_off"] * 4 + ["graphify_on"] * 4,
            [item["condition"] for item in plan],
        )
        self.assertEqual(task_ids + task_ids, [item["task_id"] for item in plan])
        self.assertEqual([1] * 4 + [2] * 4, [item["position"] for item in plan])


if __name__ == "__main__":
    unittest.main()
