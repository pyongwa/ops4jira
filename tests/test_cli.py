"""Tests for the jiraops CLI wiring (deterministic; no live calls)."""
import io
import unittest
from contextlib import redirect_stdout

from jiraops import cli


class FakeTransport:
    """Stand-in for Transport: records creates, simulates label search."""

    def __init__(self, issue=None, existing_labels=()):
        self._issue = issue or {}
        self._labels = set(existing_labels)
        self.created = []

    def jira_get(self, key, fields=None):
        return self._issue

    def jira_search(self, jql, fields=None, max_results=50):
        # crude: treat `labels = "X"` as a membership check against self._labels
        for lbl in self._labels:
            if f'"{lbl}"' in jql:
                return {"issues": [{"key": "EXIST-1"}]}
        return {"issues": []}

    def jira_create(self, project, issuetype, fields):
        self.created.append((project, issuetype, fields))
        # newly created labels become "existing" for idempotency within a run
        for lbl in fields.get("labels", []):
            self._labels.add(lbl)
        return {"key": f"NEW-{len(self.created)}"}


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


class TestApplyIdempotency(unittest.TestCase):
    ISSUE = {"fields": {"project": {"key": "EXEC"}}}

    def _items(self):
        from jiraops import decompose
        return decompose.parse("- alpha\n- beta\n")

    def test_apply_creates_then_skips_on_rerun(self):
        tx = FakeTransport(issue=self.ISSUE)
        items = self._items()
        with redirect_stdout(io.StringIO()):
            rc1 = cli._apply(tx, self.ISSUE, "EXEC-1", items, "Task")
        self.assertEqual(rc1, 0)
        self.assertEqual(len(tx.created), 2)         # both created first time
        # second apply: labels now exist -> all skipped, nothing new created
        with redirect_stdout(io.StringIO()):
            rc2 = cli._apply(tx, self.ISSUE, "EXEC-1", items, "Task")
        self.assertEqual(rc2, 0)
        self.assertEqual(len(tx.created), 2)         # unchanged — idempotent

    def test_created_children_carry_stable_key_label_and_parent(self):
        tx = FakeTransport(issue=self.ISSUE)
        with redirect_stdout(io.StringIO()):
            cli._apply(tx, self.ISSUE, "EXEC-1", self._items(), "Task")
        _, _, fields = tx.created[0]
        self.assertTrue(fields["labels"][0].startswith("jiraops-"))
        self.assertEqual(fields["parent"], {"key": "EXEC-1"})


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


if __name__ == "__main__":
    unittest.main()
