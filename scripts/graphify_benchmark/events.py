"""Copilot JSONL parsing and derived metric calculation."""

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Pattern, Sequence, Tuple


PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\."
    r"(?:java|py|js|ts|tsx|go|rs|cs|cpp|c|h|md|json|xml|yml|yaml|sh))"
)
GRAPHIFY_CLI_PATTERN = re.compile(
    r"""(?ix)
    (?:^|[;&|]\s*|\b(?:then|do)\s+)
    (?:env\s+)?
    (?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*
    (?P<executable>
        graphify
        |
        "(?:[^"]*[\\/])graphify(?:\.exe)?"
        |
        '(?:[^']*[\\/])graphify(?:\.exe)?'
        |
        (?:[A-Za-z]:[\\/]|/)[^\s;&|]*[\\/]graphify(?:\.exe)?
    )
    \s+
    (?P<subcommand>query|path|explain|affected|god-nodes)\b
    """
)


def load_events(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    events = []
    malformed = 0
    if not path.exists():
        return events, malformed
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            malformed += 1
    return events, malformed


def _event_type(event: Dict[str, Any]) -> str:
    return str(event.get("type") or event.get("event") or "")


def _data(event: Dict[str, Any]) -> Dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def build_tool_timeline(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    starts = {}
    timeline = []
    for sequence, event in enumerate(events):
        event_type = _event_type(event)
        data = _data(event)
        if event_type == "tool.execution_start":
            tool_call_id = str(data.get("toolCallId") or "start-%d" % sequence)
            record = {
                "sequence": sequence,
                "tool_call_id": tool_call_id,
                "tool_name": str(data.get("toolName") or ""),
                "timestamp": event.get("timestamp"),
                "arguments": data.get("arguments"),
                "success": None,
                "result": None,
                "telemetry": None,
            }
            starts[tool_call_id] = record
            timeline.append(record)
        elif event_type == "tool.execution_complete":
            tool_call_id = str(data.get("toolCallId") or "complete-%d" % sequence)
            record = starts.get(tool_call_id)
            if record is None:
                record = {
                    "sequence": sequence,
                    "tool_call_id": tool_call_id,
                    "tool_name": str(data.get("toolName") or ""),
                    "timestamp": event.get("timestamp"),
                    "arguments": None,
                    "success": None,
                    "result": None,
                    "telemetry": None,
                }
                timeline.append(record)
            record["success"] = data.get("success")
            result = data.get("result")
            if isinstance(result, dict):
                record["result"] = result.get("content", result)
                record["detailed_result"] = result.get("detailedContent")
            else:
                record["result"] = result
                record["detailed_result"] = None
            record["telemetry"] = data.get("toolTelemetry", data.get("telemetry"))
    return sorted(timeline, key=lambda item: item["sequence"])


def extract_final_answer(events: Sequence[Dict[str, Any]]) -> str:
    candidates = []
    for event in events:
        event_type = _event_type(event)
        data = _data(event)
        if event_type == "assistant.message":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                candidates.append(content.strip())
        elif event_type == "result":
            content = (
                event.get("content")
                or event.get("message")
                or data.get("content")
                or data.get("message")
            )
            if isinstance(content, str) and content.strip():
                candidates.append(content.strip())
    return candidates[-1] if candidates else ""


def extract_session_duration_ms(events: Sequence[Dict[str, Any]]) -> Optional[float]:
    for event in reversed(events):
        if _event_type(event) != "result":
            continue
        data = _data(event)
        usage = event.get("usage")
        if not isinstance(usage, dict):
            usage = data.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("sessionDurationMs"), (int, float)):
            return float(usage["sessionDurationMs"])
    return None


def result_exit_code(events: Sequence[Dict[str, Any]]) -> Optional[int]:
    for event in reversed(events):
        if _event_type(event) == "result":
            value = event.get("exitCode")
            if value is None:
                value = _data(event).get("exitCode")
            if isinstance(value, int):
                return value
    return None


def _compile_many(patterns: Iterable[str]) -> List[Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def _matches_any(value: str, patterns: Sequence[Pattern[str]]) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def _target_values(task: Dict[str, Any]) -> List[str]:
    values = []
    grader = task.get("grader", {})
    for target in grader.get("expected_targets", []):
        for value in target.get("values", []) + target.get("metric_values", []):
            if isinstance(value, str) and value:
                values.append(value)
    return values


def _contains_target(text: str, values: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(value.lower() in lowered for value in values)


def _extract_paths(text: str) -> List[str]:
    return [match.group(1) for match in PATH_PATTERN.finditer(text)]


def _shell_commands(arguments: Any) -> List[str]:
    if isinstance(arguments, str):
        return [arguments]
    if not isinstance(arguments, dict):
        return []
    commands = []
    for key in ("command", "cmd", "script", "code"):
        value = arguments.get(key)
        if isinstance(value, str):
            commands.append(value)
    return commands


def _graphify_cli_calls(
    timeline: Sequence[Dict[str, Any]],
    shell_patterns: Sequence[Pattern[str]],
) -> List[Dict[str, Any]]:
    calls = []
    for index, record in enumerate(timeline):
        if not _matches_any(record["tool_name"], shell_patterns):
            continue
        for command in _shell_commands(record.get("arguments")):
            for match in GRAPHIFY_CLI_PATTERN.finditer(command):
                calls.append(
                    {
                        "timeline_index": index,
                        "tool_name": record["tool_name"],
                        "tool_call_id": record["tool_call_id"],
                        "command": command,
                        "executable": match.group("executable"),
                        "subcommand": match.group("subcommand").lower(),
                        "success": record.get("success") is True,
                    }
                )
    return calls


def parse_usage(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        usage = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(usage, dict):
        return {}
    token_details = usage.get("tokenDetails")
    token_details = token_details if isinstance(token_details, dict) else {}

    def token_count(name: str) -> int:
        value = token_details.get(name)
        if isinstance(value, dict) and isinstance(value.get("tokenCount"), (int, float)):
            return int(value["tokenCount"])
        return 0

    return {
        "ai_credits_nano": usage.get("totalNanoAiu"),
        "api_duration_ms": usage.get("totalApiDurationMs"),
        "input_tokens": token_count("input"),
        "cache_read_tokens": token_count("cache_read"),
        "cache_write_tokens": token_count("cache_write"),
        "output_tokens": token_count("output"),
        "model_metrics": usage.get("modelMetrics"),
        "code_changes": usage.get("codeChanges"),
    }


def calculate_metrics(
    events: Sequence[Dict[str, Any]],
    usage_path: Path,
    task: Dict[str, Any],
    metrics_config: Dict[str, Any],
) -> Dict[str, Any]:
    timeline = build_tool_timeline(events)
    graphify_patterns = _compile_many(metrics_config["graphify_tool_name_patterns"])
    search_patterns = _compile_many(metrics_config["search_tool_name_patterns"])
    read_patterns = _compile_many(metrics_config["read_tool_name_patterns"])
    shell_patterns = _compile_many(
        list(metrics_config["shell_tool_name_patterns"])
        + [r"(?i)(powershell|pwsh|cmd)"]
    )
    shell_read_patterns = _compile_many(metrics_config["shell_read_command_patterns"])
    targeted_patterns = _compile_many(metrics_config["targeted_argument_patterns"])
    broad_patterns = _compile_many(metrics_config["broad_argument_patterns"])
    known_graphify = set(metrics_config.get("known_graphify_tool_names", []))
    expected_values = _target_values(task)
    graphify_cli_calls = _graphify_cli_calls(timeline, shell_patterns)

    graphify_calls = []
    search_calls = []
    read_files = set()
    first_correct_target = None
    tool_failures = []

    for index, record in enumerate(timeline):
        name = record["tool_name"]
        arguments = _stringify(record.get("arguments"))
        result = _stringify(record.get("result"))
        combined = arguments + "\n" + result
        is_graphify = name in known_graphify or _matches_any(name, graphify_patterns)
        is_search = not is_graphify and _matches_any(name, search_patterns)
        is_shell_read = _matches_any(name, shell_patterns) and _matches_any(
            arguments, shell_read_patterns
        )
        is_read = _matches_any(name, read_patterns) or is_shell_read
        if is_graphify:
            graphify_calls.append(index)
        if is_search:
            target_match = _contains_target(arguments, expected_values)
            targeted = target_match or _matches_any(arguments, targeted_patterns)
            broad_signal = _matches_any(arguments, broad_patterns)
            search_calls.append(
                {
                    "timeline_index": index,
                    "tool_name": name,
                    "classification": "targeted" if targeted and not broad_signal else "broad",
                    "target_match": target_match,
                }
            )
        if is_read:
            read_files.update(_extract_paths(arguments))
        if first_correct_target is None and _contains_target(combined, expected_values):
            first_correct_target = index
        if record.get("success") is False:
            tool_failures.append(
                {
                    "tool_name": name,
                    "tool_call_id": record["tool_call_id"],
                    "result": result[:500],
                }
            )

    follow_up_count = 0
    window = int(metrics_config.get("graphify_follow_up_window", 4))
    for graphify_index in graphify_calls:
        for search in search_calls:
            if (
                graphify_index < search["timeline_index"] <= graphify_index + window
                and search["classification"] == "targeted"
            ):
                follow_up_count += 1
                break
        else:
            for later_index in range(
                graphify_index + 1,
                min(len(timeline), graphify_index + window + 1),
            ):
                record = timeline[later_index]
                if _matches_any(record["tool_name"], read_patterns):
                    args = _stringify(record.get("arguments"))
                    if _contains_target(args, expected_values) or _matches_any(
                        args, targeted_patterns
                    ):
                        follow_up_count += 1
                        break

    cli_follow_up_count = 0
    for cli_call in graphify_cli_calls:
        cli_index = cli_call["timeline_index"]
        for search in search_calls:
            if (
                cli_index < search["timeline_index"] <= cli_index + window
                and search["classification"] == "targeted"
            ):
                cli_follow_up_count += 1
                break
        else:
            for later_index in range(
                cli_index + 1, min(len(timeline), cli_index + window + 1)
            ):
                record = timeline[later_index]
                if _matches_any(record["tool_name"], read_patterns):
                    args = _stringify(record.get("arguments"))
                    if _contains_target(args, expected_values) or _matches_any(
                        args, targeted_patterns
                    ):
                        cli_follow_up_count += 1
                        break

    model_failures = []
    mcp_failures = []
    graphify_statuses = []
    graphify_mcp_events = []
    for event in events:
        event_type = _event_type(event)
        data = _data(event)
        if event_type == "model.call_finished":
            outcome = data.get("outcome")
            if outcome not in (None, "success", "completed", "ok"):
                model_failures.append(outcome)
        elif event_type == "session.mcp_server_status_changed":
            server = str(data.get("serverName") or "")
            status = str(data.get("status") or "")
            if server == task.get("_graphify_server") or _matches_any(
                server, graphify_patterns
            ):
                graphify_statuses.append(status)
                graphify_mcp_events.append({"server": server, "status": status})
            if status.lower() in (
                "error",
                "failed",
                "disconnected",
                "unavailable",
                "needs-auth",
                "not_configured",
            ):
                mcp_failures.append({"server": server, "status": status})

    usage = parse_usage(usage_path)
    return {
        "tool_timeline": timeline,
        "tool_call_count": len(timeline),
        "graphify_invocation_count": len(graphify_calls),
        "graphify_targeted_follow_up_count": follow_up_count,
        "graphify_cli_calls": graphify_cli_calls,
        "graphify_cli_invocation_count": len(graphify_cli_calls),
        "graphify_cli_success_count": sum(
            1 for call in graphify_cli_calls if call["success"]
        ),
        "graphify_cli_targeted_follow_up_count": cli_follow_up_count,
        "search_call_count": len(search_calls),
        "broad_search_count": sum(
            1 for item in search_calls if item["classification"] == "broad"
        ),
        "targeted_search_count": sum(
            1 for item in search_calls if item["classification"] == "targeted"
        ),
        "search_calls": search_calls,
        "unique_files_read": sorted(read_files),
        "unique_files_read_count": len(read_files),
        "exploration_before_first_correct_target": first_correct_target,
        "tool_failures": tool_failures,
        "model_failures": model_failures,
        "mcp_failures": mcp_failures,
        "graphify_mcp_statuses": graphify_statuses,
        "graphify_mcp_events": graphify_mcp_events,
        "session_duration_ms": extract_session_duration_ms(events),
        "result_exit_code": result_exit_code(events),
        "usage": usage,
    }
