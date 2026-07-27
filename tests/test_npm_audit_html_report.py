import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nodeutils import npm_audit_html_report as report


class NpmAuditHtmlReportTest(unittest.TestCase):
    def write_json(self, directory, filename, data):
        path = Path(directory) / filename
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_load_json_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            path.write_text("{not json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                report.load_json(path)

    def test_load_json_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Expected top-level JSON object"):
                report.load_json(path)

    def test_normalize_audit_handles_empty_vulnerabilities(self):
        rows = report.normalize_audit({"vulnerabilities": {}})

        self.assertEqual(rows, [])

    def test_normalize_audit_handles_missing_vulnerabilities(self):
        rows = report.normalize_audit({"metadata": {}})

        self.assertEqual(rows, [])

    def test_normalize_audit_handles_malformed_vulnerabilities(self):
        rows = report.normalize_audit({"vulnerabilities": []})

        self.assertEqual(rows, [])

    def test_render_html_for_empty_report_contains_zero_summary(self):
        rows = []
        metadata = report._build_metadata(
            rows,
            {"metadata": {"vulnerabilities": {"total": 0}}},
        )

        html = report.render_html(rows, metadata)

        self.assertIn("npm audit HTML report", html)
        self.assertIn('"total": 0', html)
        self.assertIn('"critical": 0', html)

    def test_main_writes_html_report_for_empty_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = self.write_json(
                tmpdir,
                "audit.json",
                {"vulnerabilities": {}, "metadata": {}},
            )
            package_json_path = self.write_json(
                tmpdir,
                "package.json",
                {"dependencies": {}},
            )
            package_lock_path = self.write_json(
                tmpdir,
                "package-lock.json",
                {"packages": {"": {"name": "sample"}}},
            )
            output_path = Path(tmpdir) / "audit report.html"

            exit_code = report.main(
                [
                    "--audit",
                    str(audit_path),
                    "--package-json",
                    str(package_json_path),
                    "--package-lock",
                    str(package_lock_path),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertIn("npm audit HTML report", output_path.read_text(encoding="utf-8"))

    def test_main_returns_error_for_malformed_audit_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.json"
            audit_path.write_text("{not json", encoding="utf-8")
            package_json_path = self.write_json(tmpdir, "package.json", {"dependencies": {}})
            package_lock_path = self.write_json(
                tmpdir,
                "package-lock.json",
                {"packages": {"": {"name": "sample"}}},
            )
            output_path = Path(tmpdir) / "audit-report.html"

            with patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                exit_code = report.main(
                    [
                        "--audit",
                        str(audit_path),
                        "--package-json",
                        str(package_json_path),
                        "--package-lock",
                        str(package_lock_path),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse(output_path.exists())
            self.assertIn("Invalid JSON", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
