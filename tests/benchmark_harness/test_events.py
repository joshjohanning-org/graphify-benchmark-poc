import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.config import DEFAULT_METRICS
from graphify_benchmark.events import (
    build_tool_timeline,
    calculate_metrics,
    extract_final_answer,
    load_events,
    parse_usage,
)


FIXTURES = Path(__file__).parent / "fixtures"


class EventParsingTests(unittest.TestCase):
    def setUp(self):
        self.events, self.malformed = load_events(FIXTURES / "events.jsonl")

    def test_load_events_keeps_objects_and_counts_malformed_lines(self):
        self.assertEqual(22, len(self.events))
        self.assertEqual(2, self.malformed)

    def test_build_tool_timeline_merges_completions_with_starts(self):
        timeline = build_tool_timeline(self.events)

        self.assertEqual(8, len(timeline))
        self.assertEqual("broad-1", timeline[0]["tool_call_id"])
        self.assertEqual({"pattern": "**/*.py", "paths": "."}, timeline[0]["arguments"])
        self.assertTrue(timeline[0]["success"])
        self.assertEqual("2 matches", timeline[0]["result"])
        self.assertEqual(
            "src/order.py\nsrc/customer.py",
            timeline[0]["detailed_result"],
        )
        self.assertEqual({"durationMs": 10}, timeline[0]["telemetry"])

    def test_build_tool_timeline_retains_orphan_completion(self):
        timeline = build_tool_timeline(self.events)
        orphan = next(item for item in timeline if item["tool_call_id"] == "orphan-1")

        self.assertEqual("shell", orphan["tool_name"])
        self.assertIsNone(orphan["arguments"])
        self.assertEqual("done", orphan["result"])

    def test_extract_final_answer_uses_last_answer_candidate(self):
        self.assertEqual(
            "Final: OrderService calls OrderRepository.",
            extract_final_answer(self.events),
        )

    def test_result_event_reads_top_level_usage_duration(self):
        task = {"grader": {"expected_targets": [{"id": "x", "values": ["x"]}]}}

        metrics = calculate_metrics(
            self.events,
            FIXTURES / "missing-usage.json",
            task,
            DEFAULT_METRICS,
        )

        self.assertEqual(4321.0, metrics["session_duration_ms"])


class UsageParsingTests(unittest.TestCase):
    def test_parse_usage_extracts_standard_token_and_metadata_fields(self):
        usage = parse_usage(FIXTURES / "usage.json")

        self.assertEqual(123456, usage["ai_credits_nano"])
        self.assertEqual(987.5, usage["api_duration_ms"])
        self.assertEqual(101, usage["input_tokens"])
        self.assertEqual(40, usage["cache_read_tokens"])
        self.assertEqual(0, usage["cache_write_tokens"])
        self.assertEqual(22, usage["output_tokens"])
        self.assertEqual({"gpt-test": {"requests": 2}}, usage["model_metrics"])
        self.assertEqual({"added": 3, "deleted": 1}, usage["code_changes"])

    def test_parse_usage_returns_empty_mapping_for_missing_file(self):
        self.assertEqual({}, parse_usage(FIXTURES / "missing-usage.json"))


class DerivedMetricsTests(unittest.TestCase):
    def test_calculate_metrics_classifies_exploration_and_failures(self):
        events, _ = load_events(FIXTURES / "events.jsonl")
        task = {
            "grader": {
                "expected_targets": [
                    {"id": "service", "values": ["OrderService"]},
                ]
            },
            "_graphify_server": "graphify-main",
        }

        metrics = calculate_metrics(
            events,
            FIXTURES / "usage.json",
            task,
            DEFAULT_METRICS,
        )

        self.assertEqual(8, metrics["tool_call_count"])
        self.assertEqual(2, metrics["graphify_invocation_count"])
        self.assertEqual(2, metrics["graphify_targeted_follow_up_count"])
        self.assertEqual(2, metrics["search_call_count"])
        self.assertEqual(1, metrics["broad_search_count"])
        self.assertEqual(1, metrics["targeted_search_count"])
        self.assertEqual(
            ["rg", "search_code"],
            [item["tool_name"] for item in metrics["search_calls"]],
        )
        self.assertEqual(
            ["pom.xml", "src/order.py", "tests/test_order.py"],
            metrics["unique_files_read"],
        )
        self.assertEqual(3, metrics["unique_files_read_count"])
        self.assertEqual(3, metrics["exploration_before_first_correct_target"])
        self.assertEqual("read-2", metrics["tool_failures"][0]["tool_call_id"])
        self.assertEqual(["timeout"], metrics["model_failures"])
        self.assertEqual(
            [
                {"server": "graphify-main", "status": "unavailable"},
                {"server": "auth-server", "status": "needs-auth"},
                {"server": "missing-server", "status": "not_configured"},
            ],
            metrics["mcp_failures"],
        )
        self.assertEqual(
            ["connected", "unavailable"],
            metrics["graphify_mcp_statuses"],
        )
        self.assertEqual(4321.0, metrics["session_duration_ms"])
        self.assertEqual(7, metrics["result_exit_code"])
        self.assertEqual(123456, metrics["usage"]["ai_credits_nano"])

    def test_graphify_cli_detection_uses_shell_arguments_and_completion_success(self):
        events = [
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "cli-1",
                    "toolName": "bash",
                    "arguments": {
                        "command": "cd repo && graphify query 'orders' --budget 50"
                    },
                },
            },
            {
                "type": "tool.execution_complete",
                "data": {"toolCallId": "cli-1", "success": True, "result": {}},
            },
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "targeted-1",
                    "toolName": "rg",
                    "arguments": {"pattern": "OrderService", "path": "src"},
                },
            },
            {
                "type": "tool.execution_complete",
                "data": {
                    "toolCallId": "targeted-1",
                    "success": True,
                    "result": {},
                },
            },
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "cli-2",
                    "toolName": "powershell",
                    "arguments": {
                        "command": "& 'C:\\tools\\graphify.exe' path Order Customer"
                    },
                },
            },
            {
                "type": "tool.execution_complete",
                "data": {"toolCallId": "cli-2", "success": False, "result": {}},
            },
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "not-cli",
                    "toolName": "bash",
                    "arguments": {"command": "echo 'graphify explain Order'"},
                },
            },
            {
                "type": "tool.execution_complete",
                "data": {"toolCallId": "not-cli", "success": True, "result": {}},
            },
            {
                "type": "assistant.message",
                "data": {"content": "graphify affected Order"},
            },
        ]
        task = {"grader": {"expected_targets": [{"id": "x", "values": ["Order"]}]}}

        metrics = calculate_metrics(
            events,
            FIXTURES / "missing-usage.json",
            task,
            DEFAULT_METRICS,
        )

        self.assertEqual(2, metrics["graphify_cli_invocation_count"])
        self.assertEqual(1, metrics["graphify_cli_success_count"])
        self.assertEqual(1, metrics["graphify_cli_targeted_follow_up_count"])
        self.assertEqual(
            ["query", "path"],
            [call["subcommand"] for call in metrics["graphify_cli_calls"]],
        )
        self.assertEqual(
            "cd repo && graphify query 'orders' --budget 50",
            metrics["graphify_cli_calls"][0]["command"],
        )


if __name__ == "__main__":
    unittest.main()
