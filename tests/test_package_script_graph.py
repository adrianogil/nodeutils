import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nodeutils import package_script_graph as graph


class PackageScriptGraphTest(unittest.TestCase):
    def write_package(self, directory, data):
        path = Path(directory) / "package.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_finds_quoted_targets_and_ignores_quoted_text(self):
        command = (
            'echo "npm run ignored" && npm run "build:client" '
            "&& npm run 'build server'; npm run-script format; npm test || npm start"
        )

        self.assertEqual(
            graph.find_npm_targets(command),
            ("build server", "build:client", "format", "start", "test"),
        )

    def test_finds_targets_in_chained_commands_with_options_and_env(self):
        command = (
            "npm --silent run clean && npm run --if-present build; "
            "env NODE_ENV=test npm test | tee npm run ignored\nnpm start"
        )

        self.assertEqual(
            graph.find_npm_targets(command),
            ("build", "clean", "start", "test"),
        )

    def test_build_graph_adds_pre_and_post_lifecycle_relationships(self):
        result = graph.build_graph(
            {
                "build": "vite build",
                "prebuild": "npm run prepare",
                "postbuild": "node report.js",
                "prepare": "node prepare.js",
            }
        )

        self.assertIn(graph.Edge("build", "prebuild", "pre"), result.edges)
        self.assertIn(graph.Edge("build", "postbuild", "post"), result.edges)
        self.assertIn(graph.Edge("prebuild", "prepare", "npm"), result.edges)
        self.assertEqual(result.missing_targets, ())

    def test_cycles_and_missing_targets_are_reported_and_rendered(self):
        result = graph.build_graph(
            {
                "a": "npm run b",
                "b": "npm run a",
                "caller": "npm run absent",
            }
        )

        self.assertEqual(result.cycles, (("a", "b"),))
        self.assertEqual(result.missing_targets, ("absent",))
        self.assertEqual(
            graph.diagnostics(result),
            (
                "Missing script target 'absent', referenced by: caller",
                "Cycle detected among scripts: a, b",
            ),
        )

        mermaid = graph.render_mermaid(result)
        self.assertIn('["absent (missing)"]', mermaid)
        self.assertIn("class script_0,script_2 cycle", mermaid)
        self.assertIn("%% Cycle: a, b", mermaid)

    def test_lifecycle_recursion_is_detected_as_a_cycle(self):
        result = graph.build_graph(
            {
                "build": "vite build",
                "prebuild": "npm run build",
            }
        )

        self.assertEqual(result.cycles, (("build", "prebuild"),))

    def test_load_scripts_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "package.json"
            path.write_text("{not json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                graph.load_scripts(path)

    def test_load_scripts_rejects_non_string_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_package(tmpdir, {"scripts": {"test": ["not", "a", "command"]}})

            with self.assertRaisesRegex(ValueError, "name and command to be a string"):
                graph.load_scripts(path)

    def test_invalid_shell_quoting_names_the_script(self):
        with self.assertRaisesRegex(ValueError, "Script 'build'.*Invalid shell quoting"):
            graph.build_graph({"build": 'npm run "unfinished'})

    def test_package_without_scripts_renders_an_empty_graph(self):
        result = graph.build_graph({})

        self.assertEqual(graph.render_mermaid(result), "flowchart LR\n    %% No npm scripts found\n")
        self.assertIn("// No npm scripts found", graph.render_dot(result))

    def test_main_defaults_to_mermaid_and_returns_error_for_bad_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package_path = self.write_package(tmpdir, {"scripts": {"test": "node test.js"}})
            with patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
                exit_code = graph.main([str(package_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(stdout.getvalue().startswith("flowchart LR\n"))

            package_path.write_text("{bad", encoding="utf-8")
            with patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                exit_code = graph.main([str(package_path)])

            self.assertEqual(exit_code, 1)
            self.assertIn("Invalid JSON", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
