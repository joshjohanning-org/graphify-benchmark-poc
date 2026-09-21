import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from graphify_benchmark.skills import (
    SkillConfigurationError,
    parse_skill_list,
    read_skill_name,
    resolve_skill_source,
    skill_destination,
    stage_skill,
    validate_skill_condition,
)
from graphify_benchmark.runner import (
    _effective_prompt,
    _filtered_status,
    _forced_condition_validity,
    _graphify_mcp_args,
    _prepare_graph_condition,
    _prepare_skill_condition,
)


SKILL_LIST = """Project skills:
  graphify - Project graph skill
  other - Another skill

Personal skills:
  personal-only - Personal skill
"""


class SkillConfigurationTests(unittest.TestCase):
    def test_resolves_absolute_skill_source_and_reads_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: graphify\ndescription: Test\n---\n",
                encoding="utf-8",
            )

            resolved, name = resolve_skill_source(str(source), Path("/unused"))

            self.assertEqual(source.resolve(), resolved)
            self.assertEqual("graphify", name)
            self.assertEqual(Path(".github/skills/graphify"), skill_destination(name))

    def test_rejects_source_without_skill_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                SkillConfigurationError, "containing SKILL.md"
            ):
                read_skill_name(Path(temp_dir))


class SkillStagingTests(unittest.TestCase):
    def test_stages_only_at_project_skill_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            worktree = root / "worktree"
            source.mkdir()
            worktree.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: graphify\ndescription: Test\n---\n",
                encoding="utf-8",
            )
            (source / "reference.md").write_text("reference\n", encoding="utf-8")

            destination = stage_skill(source, worktree, "graphify")

            self.assertEqual(
                worktree / ".github/skills/graphify", destination
            )
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "reference.md").is_file())
            self.assertFalse((worktree / ".copilot/skills/graphify").exists())

    def test_refuses_to_overlay_existing_project_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            worktree = root / "worktree"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: graphify\ndescription: Test\n---\n",
                encoding="utf-8",
            )
            (worktree / ".github/skills/graphify").mkdir(parents=True)

            with self.assertRaisesRegex(
                SkillConfigurationError, "was not isolated"
            ):
                stage_skill(source, worktree, "graphify")

    def test_runner_stages_treatment_and_removes_skill_from_control(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: graphify\ndescription: Test\n---\n",
                encoding="utf-8",
            )
            fake = root / "fake-copilot"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "from pathlib import Path\n"
                "cwd = Path(sys.argv[sys.argv.index('-C') + 1])\n"
                "print('Project skills:')\n"
                "if (cwd / '.github/skills/graphify/SKILL.md').is_file():\n"
                "    print('  graphify - Test skill')\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)

            statuses = {}
            for condition in ("graphify_on", "graphify_off"):
                repo = root / condition
                (repo / ".copilot/skills/graphify").mkdir(parents=True)
                (repo / ".github/skills/graphify").mkdir(parents=True)
                (repo / "graphify-out").mkdir()
                for skill_path in (
                    repo / ".copilot/skills/graphify/SKILL.md",
                    repo / ".github/skills/graphify/SKILL.md",
                ):
                    skill_path.write_text(
                        "---\nname: graphify\ndescription: Existing\n---\n",
                        encoding="utf-8",
                    )
                (repo / "graphify-out/graph.json").write_text(
                    "{}\n", encoding="utf-8"
                )
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "add", "."], check=True
                )
                config = {
                    "copilot_command": str(fake),
                    "_resolved_graphify_skill_source": str(source),
                    "_graphify_skill_name": "graphify",
                    "worktree_exclude_paths": [
                        "graphify-out",
                        ".copilot/skills/graphify",
                    ],
                }

                _, statuses[condition] = _prepare_skill_condition(
                    config, repo, condition
                )

            self.assertTrue(statuses["graphify_on"]["staged"])
            self.assertTrue(statuses["graphify_on"]["loaded"])
            self.assertTrue(statuses["graphify_on"]["valid"])
            self.assertFalse(statuses["graphify_off"]["staged"])
            self.assertFalse(statuses["graphify_off"]["loaded"])
            self.assertTrue(statuses["graphify_off"]["valid"])

    def test_forced_mode_stages_read_only_graph_only_in_treatment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source-graph.json"
            source.write_text('{"nodes": []}\n', encoding="utf-8")
            config = {
                "treatment_mode": "forced_graphify_skill_cli",
                "_resolved_graphify_graph_source": str(source),
                "_graphify_graph_sha256": (
                    "62ba57bffc912f2a9213e9af01718f390a6e90ff965cac9b2880182c4e75c11b"
                ),
                "_graphify_graph_size_bytes": source.stat().st_size,
                "graphify_graph_build_duration_seconds": 12.5,
            }
            import hashlib
            config["_graphify_graph_sha256"] = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
            treatment = root / "treatment"
            control = root / "control"
            treatment.mkdir()
            control.mkdir()

            on = _prepare_graph_condition(config, treatment, "graphify_on")
            off = _prepare_graph_condition(config, control, "graphify_off")

            self.assertTrue(on["valid"])
            self.assertTrue(on["staged"])
            self.assertTrue(on["read_only"])
            self.assertEqual(on["source_sha256"], on["destination_sha256"])
            self.assertFalse(off["present"])
            self.assertTrue(off["valid"])

    def test_injected_graph_and_skill_are_excluded_from_source_status(self):
        status = (
            "?? graphify-out/\n"
            "?? .github/skills/graphify/\n"
            " M src/main.py\n"
        )

        filtered = _filtered_status(
            status,
            ["graphify-out", ".github/skills/graphify"],
        )

        self.assertEqual(" M src/main.py\n", filtered)

    def test_forced_prompt_and_mcp_isolation_are_treatment_specific(self):
        config = {
            "treatment_mode": "forced_graphify_skill_cli",
            "forced_graphify_directive": "Use Graphify CLI first.",
            "graphify_server": "graphify_adempiere",
        }

        treatment, treatment_applied = _effective_prompt(
            config, "graphify_on", "Base task."
        )
        control, control_applied = _effective_prompt(
            config, "graphify_off", "Base task."
        )

        self.assertEqual("Use Graphify CLI first.\n\nBase task.", treatment)
        self.assertTrue(treatment_applied)
        self.assertEqual("Base task.", control)
        self.assertFalse(control_applied)
        self.assertEqual(
            ["--disable-mcp-server", "graphify_adempiere"],
            _graphify_mcp_args(config, "graphify_on"),
        )
        self.assertEqual(
            ["--disable-mcp-server", "graphify_adempiere"],
            _graphify_mcp_args(config, "graphify_off"),
        )
        self.assertEqual(
            [],
            _graphify_mcp_args({**config, "graphify_server": None}, "graphify_on"),
        )

    def test_forced_validity_requires_cli_only_in_treatment(self):
        valid_skill = {"valid": True, "invalid_reason": None}
        valid_graph = {"valid": True, "invalid_reason": None}
        base_metrics = {
            "graphify_invocation_count": 0,
            "graphify_mcp_events": [],
            "graphify_cli_invocation_count": 0,
            "graphify_cli_success_count": 0,
        }

        self.assertFalse(
            _forced_condition_validity(
                "graphify_on", valid_skill, valid_graph, base_metrics
            )[0]
        )
        self.assertTrue(
            _forced_condition_validity(
                "graphify_on",
                valid_skill,
                valid_graph,
                {
                    **base_metrics,
                    "graphify_mcp_events": [
                        {"server": "graphify_adempiere", "status": "disabled"}
                    ],
                    "graphify_cli_invocation_count": 1,
                    "graphify_cli_success_count": 1,
                },
            )[0]
        )
        self.assertTrue(
            _forced_condition_validity(
                "graphify_on",
                valid_skill,
                valid_graph,
                {
                    **base_metrics,
                    "graphify_cli_invocation_count": 1,
                    "graphify_cli_success_count": 1,
                },
            )[0]
        )
        self.assertFalse(
            _forced_condition_validity(
                "graphify_off",
                valid_skill,
                valid_graph,
                {**base_metrics, "graphify_cli_invocation_count": 1},
            )[0]
        )


class SkillDiscoveryTests(unittest.TestCase):
    def test_parses_skill_sources(self):
        self.assertEqual(
            {"project": ["graphify", "other"], "personal": ["personal-only"]},
            parse_skill_list(SKILL_LIST),
        )

    def test_treatment_requires_staged_project_discovery(self):
        discovery = {
            "command_exit_code": 0,
            "project_discovered": True,
            "non_project_matches": [],
        }
        self.assertEqual(
            (True, None),
            validate_skill_condition("graphify_on", True, True, discovery),
        )
        valid, reason = validate_skill_condition(
            "graphify_on",
            True,
            False,
            {**discovery, "project_discovered": False},
        )
        self.assertFalse(valid)
        self.assertIn("not staged", reason)

    def test_control_requires_absence(self):
        discovery = {
            "command_exit_code": 0,
            "project_discovered": False,
            "non_project_matches": [],
        }
        self.assertEqual(
            (True, None),
            validate_skill_condition("graphify_off", True, False, discovery),
        )
        valid, reason = validate_skill_condition(
            "graphify_off",
            True,
            False,
            {**discovery, "project_discovered": True},
        )
        self.assertFalse(valid)
        self.assertIn("control", reason)

    def test_non_project_graphify_skill_invalidates_both_conditions(self):
        discovery = {
            "command_exit_code": 0,
            "project_discovered": True,
            "non_project_matches": ["personal"],
        }
        for condition, staged in (("graphify_on", True), ("graphify_off", False)):
            with self.subTest(condition=condition):
                valid, reason = validate_skill_condition(
                    condition, True, staged, discovery
                )
                self.assertFalse(valid)
                self.assertIn("contamination", reason)

    def test_mcp_only_mode_preserves_existing_behavior(self):
        self.assertEqual(
            (True, None),
            validate_skill_condition("graphify_on", False, False, None),
        )
        self.assertEqual(
            (True, None),
            validate_skill_condition("graphify_off", False, False, None),
        )


if __name__ == "__main__":
    unittest.main()
