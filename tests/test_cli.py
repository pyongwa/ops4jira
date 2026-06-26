"""Tests for the Ops4Jira CLI wiring (deterministic; no live calls)."""
import io
import unittest
from contextlib import redirect_stdout

from ops4jira import cli


class TestAdfToText(unittest.TestCase):
    def test_table_reconstructs_with_separator(self):
        table = {"type": "table", "content": [
            {"type": "tableRow", "content": [
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item"}]}]},
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Build X"}]}]},
            ]},
        ]}
        text = cli.adf_to_text(table)
        self.assertIn("| Item |", text)
        self.assertIn("---", text)          # synthetic separator so parser detects a table
        self.assertIn("| Build X |", text)

    def test_bullet_list(self):
        doc = {"type": "doc", "content": [
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "alpha"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "beta"}]}]},
            ]},
        ]}
        text = cli.adf_to_text(doc)
        self.assertIn("- alpha", text)
        self.assertIn("- beta", text)

    def test_plain_string_passthrough(self):
        self.assertEqual(cli._description_text({"fields": {"description": "- a\n- b"}}), "- a\n- b")


class TestAuditProjection(unittest.TestCase):
    def test_compact_maps_nested_jira_fields(self):
        node = {"key": "EXEC-9", "fields": {
            "summary": "Do the thing", "issuetype": {"name": "Story"},
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "assignee": {"displayName": "Pyongwa"}, "updated": "2026-06-20T10:00:00.000-0400"}}
        c = cli._compact(node)
        self.assertEqual(c["key"], "EXEC-9")
        self.assertEqual(c["type"], "Story")
        self.assertEqual(c["statusCategory"], "In Progress")
        self.assertEqual(c["assignee"], "Pyongwa")

    def test_compact_handles_unassigned_and_missing(self):
        c = cli._compact({"key": "EXEC-10", "fields": {"summary": "x", "status": {"name": "To Do"}}})
        self.assertIsNone(c["assignee"])
        self.assertIsNone(c["type"])


class TestCheckRefCommand(unittest.TestCase):
    def _run(self, argv):
        with redirect_stdout(io.StringIO()) as buf:
            rc = cli.main(argv)
        return rc, buf.getvalue()

    def test_ref_present_exits_zero(self):
        rc, _ = self._run(["check-ref", "--title", "[EXEC-456] Slice 2"])
        self.assertEqual(rc, 0)

    def test_refless_exits_one(self):
        rc, out = self._run(["check-ref", "--title", "Paramount+ era triage tools"])
        self.assertEqual(rc, 1)               # nonzero so it fails a CI gate / git hook
        self.assertIn("no", out.lower())

    def test_optout_exits_zero(self):
        rc, _ = self._run(["check-ref", "--title", "tidy gitignore [no-ticket: chore]"])
        self.assertEqual(rc, 0)

    def test_title_and_body_combined(self):
        # ref only in the body still passes
        rc, _ = self._run(["check-ref", "--title", "no ref here", "--body", "closes EXEC-7"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
