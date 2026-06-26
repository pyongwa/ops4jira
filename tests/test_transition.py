"""Tests for the deterministic transition planner (EXEC-465).

Given an issue's current status and the transitions Jira offers, decide whether
to no-op (already there), which transition id to fire, or report the target
unreachable. Pure + deterministic; the live write is a thin transport call.
"""
import unittest

from ops4jira import transition

# Shape mirrors GET /rest/api/3/issue/{key}/transitions
TRANSITIONS = [
    {"id": "11", "name": "To Do", "to": {"name": "To Do"}},
    {"id": "21", "name": "Start", "to": {"name": "In Progress"}},
    {"id": "31", "name": "Done", "to": {"name": "Done"}},
]


class ResolveTransitionIdTest(unittest.TestCase):
    def test_match_by_target_status_name(self):
        self.assertEqual(transition.resolve_transition_id(TRANSITIONS, "In Progress"), "21")

    def test_case_insensitive(self):
        self.assertEqual(transition.resolve_transition_id(TRANSITIONS, "done"), "31")

    def test_match_falls_back_to_transition_name(self):
        # A transition whose `to.name` differs but whose own name matches the target.
        trs = [{"id": "99", "name": "Resolve", "to": {"name": "Closed"}}]
        self.assertEqual(transition.resolve_transition_id(trs, "Resolve"), "99")

    def test_unreachable_returns_none(self):
        self.assertIsNone(transition.resolve_transition_id(TRANSITIONS, "In Review"))


class PlanTest(unittest.TestCase):
    def test_already_in_target_is_noop(self):
        p = transition.plan("Done", TRANSITIONS, "Done")
        self.assertEqual(p.action, "noop")
        self.assertIsNone(p.transition_id)

    def test_noop_is_case_insensitive(self):
        p = transition.plan("done", TRANSITIONS, "Done")
        self.assertEqual(p.action, "noop")

    def test_reachable_target_plans_transition(self):
        p = transition.plan("To Do", TRANSITIONS, "Done")
        self.assertEqual(p.action, "transition")
        self.assertEqual(p.transition_id, "31")

    def test_unreachable_target_reported(self):
        p = transition.plan("To Do", TRANSITIONS, "In Review")
        self.assertEqual(p.action, "unreachable")
        self.assertIsNone(p.transition_id)
        self.assertIn("In Review", p.reason)


if __name__ == "__main__":
    unittest.main()
