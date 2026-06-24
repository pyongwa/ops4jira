"""Tests for audit.py (EXEC-428). Stdlib unittest, no deps.

Run: python3 test_audit.py
"""

import unittest

from jiraops import audit


def issue(key, summary="", type="Story", status="To Do",
          statusCategory="To Do", assignee="Pyongwa",
          updated="2026-06-20T14:23:11.123-0400"):
    return {
        "key": key,
        "summary": summary,
        "type": type,
        "status": status,
        "statusCategory": statusCategory,
        "assignee": assignee,
        "updated": updated,
    }


class TestInventory(unittest.TestCase):
    def test_grouping_by_type_status_assignee(self):
        issues = [
            issue("E-1", type="Epic", status="In Progress",
                  statusCategory="In Progress", assignee="Fred"),
            issue("E-2", type="Story", status="Done",
                  statusCategory="Done", assignee="Pyongwa"),
            issue("E-3", type="Story", status="In Progress",
                  statusCategory="In Progress", assignee="Pyongwa"),
            issue("E-4", type="Story", status="To Do",
                  statusCategory="To Do", assignee=None),  # unassigned
        ]
        inv = audit.inventory(issues)
        self.assertEqual(inv["total"], 4)
        self.assertEqual(inv["by_type"], {"Epic": 1, "Story": 3})
        self.assertEqual(
            inv["by_status"],
            {"In Progress": 2, "Done": 1, "To Do": 1},
        )
        self.assertEqual(
            inv["by_assignee"],
            {"Fred": 1, "Pyongwa": 2, "Unassigned": 1},
        )

    def test_custom_workflow_status_not_hardcoded(self):
        # A non-standard workflow status must flow through unchanged.
        issues = [issue("E-1", status="Blocked", statusCategory="In Progress")]
        inv = audit.inventory(issues)
        self.assertEqual(inv["by_status"], {"Blocked": 1})


class TestOutstanding(unittest.TestCase):
    def test_filters_out_done(self):
        issues = [
            issue("E-1", statusCategory="Done"),
            issue("E-2", statusCategory="In Progress"),
            issue("E-3", statusCategory="To Do"),
        ]
        keys = [i["key"] for i in audit.outstanding(issues)]
        self.assertEqual(keys, ["E-2", "E-3"])

    def test_done_match_is_case_insensitive(self):
        issues = [issue("E-1", statusCategory="DONE")]
        self.assertEqual(audit.outstanding(issues), [])


class TestStale(unittest.TestCase):
    def test_stale_with_fixed_cutoff(self):
        # Real Jira timestamp format: millis + colon-less offset.
        issues = [
            issue("E-old", statusCategory="To Do",
                  updated="2026-05-01T09:00:00.000-0400"),   # before cutoff -> stale
            issue("E-new", statusCategory="In Progress",
                  updated="2026-06-23T18:30:00.500-0400"),   # after cutoff -> fresh
            issue("E-done", statusCategory="Done",
                  updated="2026-01-01T00:00:00.000-0400"),   # old but Done -> not outstanding
        ]
        stale = audit.stale(issues, cutoff="2026-06-01T00:00:00.000-0400")
        self.assertEqual([i["key"] for i in stale], ["E-old"])

    def test_cutoff_accepts_bare_date(self):
        issues = [issue("E-1", updated="2026-05-31T23:59:59.000-0400")]
        self.assertEqual([i["key"] for i in audit.stale(issues, "2026-06-01")], ["E-1"])

    def test_missing_updated_is_stale(self):
        issues = [issue("E-1", statusCategory="To Do", updated=None)]
        self.assertEqual([i["key"] for i in audit.stale(issues, "2026-06-01")], ["E-1"])


class TestDuplicates(unittest.TestCase):
    def test_detects_near_identical_summaries(self):
        issues = [
            issue("E-1", summary="Build the user login flow"),
            issue("E-2", summary="Build the user login flow!"),  # punctuation only
            issue("E-3", summary="Completely unrelated reporting dashboard"),
        ]
        dups = audit.duplicates(issues)
        self.assertEqual(dups, [("E-1", "E-2", 1.0)])

    def test_no_match_below_threshold(self):
        issues = [
            issue("E-1", summary="Build the login flow"),
            issue("E-2", summary="Refactor the billing exporter module"),
        ]
        self.assertEqual(audit.duplicates(issues), [])

    def test_no_self_or_double_reported_pairs(self):
        issues = [
            issue("E-2", summary="same exact title here"),
            issue("E-1", summary="same exact title here"),
        ]
        dups = audit.duplicates(issues)
        # exactly one pair, keys ordered, no (B,A) duplicate
        self.assertEqual(dups, [("E-1", "E-2", 1.0)])


class TestEmptyInput(unittest.TestCase):
    def test_all_functions_handle_empty(self):
        self.assertEqual(
            audit.inventory([]),
            {"total": 0, "by_type": {}, "by_status": {}, "by_assignee": {}},
        )
        self.assertEqual(audit.outstanding([]), [])
        self.assertEqual(audit.stale([], "2026-06-01"), [])
        self.assertEqual(audit.duplicates([]), [])


if __name__ == "__main__":
    unittest.main()
