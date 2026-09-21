"""Objective task grading for analysis and implementation runs."""

import re
from typing import Any, Dict, Iterable, List


class TaskDefinitionError(RuntimeError):
    """Raised when a benchmark task is malformed."""


def validate_task(task: Dict[str, Any], source: str = "<task>") -> None:
    for key in ("id", "title", "category", "prompt", "grader"):
        if key not in task:
            raise TaskDefinitionError("%s is missing required field %r" % (source, key))
    if task["category"] not in ("analysis", "implementation"):
        raise TaskDefinitionError(
            "%s category must be 'analysis' or 'implementation'" % source
        )
    if not isinstance(task["grader"], dict):
        raise TaskDefinitionError("%s grader must be an object" % source)
    targets = task["grader"].get("expected_targets")
    if not isinstance(targets, list) or not targets:
        raise TaskDefinitionError("%s grader.expected_targets must not be empty" % source)
    for target in targets:
        if not isinstance(target.get("id"), str):
            raise TaskDefinitionError("%s target is missing a string id" % source)
        values = target.get("values")
        if not isinstance(values, list) or not values:
            raise TaskDefinitionError("%s target %r has no values" % (source, target["id"]))
        if target.get("match", "substring") not in ("substring", "regex"):
            raise TaskDefinitionError(
                "%s target %r has unsupported match mode" % (source, target["id"])
            )
        metric_values = target.get("metric_values", [])
        if not isinstance(metric_values, list) or not all(
            isinstance(value, str) and value for value in metric_values
        ):
            raise TaskDefinitionError(
            "%s target %r metric_values must be an array of strings"
            % (source, target["id"])
            )
        if target.get("match") == "regex":
            for value in values:
                try:
                    re.compile(value, re.IGNORECASE | re.DOTALL)
                except re.error as error:
                    raise TaskDefinitionError(
                        "%s target %r has invalid regex: %s"
                        % (source, target["id"], error)
                    )
    validation_weight = float(task["grader"].get("validation_weight", 0.0))
    if validation_weight < 0.0 or validation_weight > 1.0:
        raise TaskDefinitionError("%s validation_weight must be between 0 and 1" % source)
    validation_command = task.get("validation", {}).get("command")
    if validation_weight > 0.0 and not validation_command:
        raise TaskDefinitionError(
            "%s assigns validation_weight but has no validation.command" % source
        )


def _source_texts(
    sources: Iterable[str],
    final_answer: str,
    events_text: str,
    git_diff: str,
    git_status: str,
) -> List[str]:
    mapping = {
        "answer": final_answer,
        "events": events_text,
        "diff": git_diff,
        "status": git_status,
    }
    return [mapping[source] for source in sources if source in mapping]


def _target_found(target: Dict[str, Any], texts: List[str]) -> bool:
    match_mode = target.get("match", "substring")
    for value in target["values"]:
        if match_mode == "regex":
            if any(re.search(value, text, re.IGNORECASE | re.DOTALL) for text in texts):
                return True
        elif any(value.lower() in text.lower() for text in texts):
            return True
    return False


def grade_task(
    task: Dict[str, Any],
    final_answer: str,
    events_text: str,
    git_diff: str,
    git_status: str,
    validation_exit_code: Any,
) -> Dict[str, Any]:
    grader = task["grader"]
    expected = grader["expected_targets"]
    found_targets = []
    missing_targets = []
    earned_weight = 0.0
    total_weight = 0.0
    for target in expected:
        weight = float(target.get("weight", 1.0))
        total_weight += weight
        texts = _source_texts(
            target.get("sources", ["answer"]),
            final_answer,
            events_text,
            git_diff,
            git_status,
        )
        if _target_found(target, texts):
            earned_weight += weight
            found_targets.append(target["id"])
        else:
            missing_targets.append(target["id"])

    target_score = earned_weight / total_weight if total_weight else 0.0
    validation_weight = float(grader.get("validation_weight", 0.0))
    validation_passed = validation_exit_code == 0
    score = target_score * (1.0 - validation_weight)
    if validation_passed:
        score += validation_weight

    false_positives = []
    penalty = 0.0
    for rule in grader.get("false_positive_patterns", []):
        pattern = rule["pattern"] if isinstance(rule, dict) else str(rule)
        rule_penalty = float(rule.get("penalty", 0.1)) if isinstance(rule, dict) else 0.1
        if re.search(pattern, final_answer, re.IGNORECASE | re.DOTALL):
            false_positives.append(pattern)
            penalty += rule_penalty
    score = max(0.0, min(1.0, score - penalty))

    threshold = float(grader.get("objective_pass_score", 0.8))
    validation_required = bool(grader.get("validation_required", False))
    objective_pass = score >= threshold and (
        not validation_required or validation_passed
    )
    return {
        "correctness_score": round(score, 4),
        "target_score_before_penalty": round(target_score, 4),
        "objective_pass": objective_pass,
        "objective_pass_score": threshold,
        "found_expected_targets": found_targets,
        "missing_expected_targets": missing_targets,
        "false_positives": false_positives,
        "false_positive_penalty": round(penalty, 4),
        "validation_passed": validation_passed,
        "validation_required": validation_required,
    }
