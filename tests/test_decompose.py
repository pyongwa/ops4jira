#!/usr/bin/env python3
"""Tests for decompose.py — stdlib unittest, no deps.

Run: python3 meta/.claude/skills/jira-bundled-ticket-decomposer/test_decompose.py
"""

import unittest

from jiraops import decompose


TABLE = """
| Item | Owner | Notes |
|------|-------|-------|
| Build the poller | Pyongwa | 6 ATS platforms |
| Wire the scorer  | Pyongwa | EXEC-191 |
| Surface to /roles | Pyongwa | UI |
"""

TABLE_NO_OUTER_PIPES = """
Item | Owner
--- | ---
Build the poller | Pyongwa
Wire the scorer | Pyongwa
"""

BULLETS = """
Things to do:
- Build the poller
- Wire the scorer
- Surface to /roles
"""

NUMBERED = """
1. Build the poller
2. Wire the scorer
3) Surface to /roles
"""


class TestTableParsing(unittest.TestCase):
    def test_counts_data_rows_only(self):
        items = decompose.parse(TABLE)
        self.assertEqual(len(items), 3)

    def test_drops_separator_and_header(self):
        items = decompose.parse(TABLE)
        titles = [it.title for it in items]
        self.assertEqual(titles, ["Build the poller", "Wire the scorer", "Surface to /roles"])
        # separator row must never appear as an item
        self.assertFalse(any("---" in it.title for it in items))

    def test_title_is_first_column(self):
        items = decompose.parse(TABLE)
        self.assertEqual(items[0].title, "Build the poller")
        self.assertEqual(items[0].columns[1], "Pyongwa")

    def test_table_without_outer_pipes(self):
        items = decompose.parse(TABLE_NO_OUTER_PIPES)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Build the poller")

    def test_source_preserved(self):
        items = decompose.parse(TABLE)
        self.assertIn("Build the poller", items[0].source)


class TestListParsing(unittest.TestCase):
    def test_bullets(self):
        items = decompose.parse(BULLETS)
        titles = [it.title for it in items]
        self.assertEqual(titles, ["Build the poller", "Wire the scorer", "Surface to /roles"])
        # the "Things to do:" line is not a list marker -> excluded
        self.assertNotIn("Things to do:", titles)

    def test_numbered_mixed_markers(self):
        items = decompose.parse(NUMBERED)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[2].title, "Surface to /roles")

    def test_marker_stripped_from_title(self):
        items = decompose.parse(BULLETS)
        self.assertFalse(any(it.title.startswith("-") for it in items))


class TestStableKeyIdempotency(unittest.TestCase):
    def test_same_input_same_keys(self):
        a = decompose.parse(TABLE)
        b = decompose.parse(TABLE)
        self.assertEqual([it.key for it in a], [it.key for it in b])

    def test_keys_are_unique_within_a_bundle(self):
        items = decompose.parse(TABLE)
        keys = [it.key for it in items]
        self.assertEqual(len(keys), len(set(keys)))

    def test_similar_titles_distinct_keys(self):
        text = """
| Item |
|------|
| Phase 1 |
| Phase 2 |
"""
        items = decompose.parse(text)
        self.assertNotEqual(items[0].key, items[1].key)

    def test_identical_rows_collapse_to_same_key(self):
        k1 = decompose.stable_key("| Build the poller | Pyongwa |")
        k2 = decompose.stable_key("|  Build the poller  |  Pyongwa  |")  # whitespace differs only
        self.assertEqual(k1, k2)

    def test_key_is_readable_slug_plus_digest(self):
        items = decompose.parse(BULLETS)
        self.assertTrue(items[0].key.startswith("build-the-poller-"))
        # 8-char hex digest suffix
        suffix = items[0].key.rsplit("-", 1)[-1]
        self.assertEqual(len(suffix), 8)


class TestEmptyAndMalformed(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(decompose.parse(""), [])

    def test_whitespace_only(self):
        self.assertEqual(decompose.parse("   \n\n  \t "), [])

    def test_none_safe(self):
        self.assertEqual(decompose.parse(None), [])

    def test_prose_no_list_no_table(self):
        text = "This is just a paragraph describing the work with no structure at all."
        self.assertEqual(decompose.parse(text), [])

    def test_table_header_but_no_data_rows(self):
        text = "| Item | Owner |\n|------|-------|\n"
        self.assertEqual(decompose.parse(text), [])

    def test_pipes_but_no_separator_falls_back_to_list(self):
        # pipes present but no separator row -> not a table; no list markers -> empty
        text = "Item | Owner\nBuild the poller | Pyongwa"
        self.assertEqual(decompose.parse(text), [])


class TestPlanFormatter(unittest.TestCase):
    def test_plan_mentions_counts_and_preservation(self):
        items = decompose.parse(TABLE)
        plan = decompose.format_plan(items, parent="EXEC-999")
        self.assertIn("EXEC-999", plan)
        self.assertIn("3 child", plan)
        self.assertIn("PRESERVED", plan)
        self.assertIn("idempotent", plan.lower())

    def test_empty_plan(self):
        plan = decompose.format_plan([], parent="EXEC-999")
        self.assertIn("no items", plan.lower())

    def test_plan_has_no_side_effects(self):
        # purely a string render; calling twice yields identical output
        items = decompose.parse(BULLETS)
        self.assertEqual(decompose.format_plan(items), decompose.format_plan(items))


if __name__ == "__main__":
    unittest.main()
