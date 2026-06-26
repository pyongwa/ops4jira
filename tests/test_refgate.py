"""Tests for the pre-merge ticket-reference gate (EXEC-464).

Deterministic, offline: given a PR title/body or commit text, a merge is allowed
iff it carries an [EXEC-NNN]/[IDEA-NNN] reference OR an explicit, reasoned
opt-out token. No Jira, no LLM.
"""
import unittest

from ops4jira import refgate


class FindRefsTest(unittest.TestCase):
    def test_bracketed_ref_found(self):
        self.assertEqual(refgate.find_refs("[EXEC-456] Slice 2: write-tagging"), ["EXEC-456"])

    def test_bare_ref_found(self):
        self.assertEqual(refgate.find_refs("fixes EXEC-12 and IDEA-3"), ["EXEC-12", "IDEA-3"])

    def test_multiple_refs_deduped_in_order(self):
        self.assertEqual(
            refgate.find_refs("[EXEC-1] body mentions EXEC-1 again and EXEC-2"),
            ["EXEC-1", "EXEC-2"],
        )

    def test_lowercase_is_not_a_ref(self):
        self.assertEqual(refgate.find_refs("exec-456 lowercase doesn't count"), [])

    def test_other_project_keys_ignored_by_default(self):
        # Default projects are EXEC/IDEA; an unrelated key must not satisfy the gate.
        self.assertEqual(refgate.find_refs("ABC-9 is not one of ours"), [])

    def test_custom_projects(self):
        self.assertEqual(refgate.find_refs("ABC-9 here", projects=("ABC",)), ["ABC-9"])


class FindOptoutTest(unittest.TestCase):
    def test_optout_with_reason(self):
        self.assertEqual(refgate.find_optout("chore [no-ticket: dependency bump]"), "dependency bump")

    def test_optout_requires_nonempty_reason(self):
        self.assertIsNone(refgate.find_optout("[no-ticket: ]"))
        self.assertIsNone(refgate.find_optout("[no-ticket:]"))

    def test_no_optout(self):
        self.assertIsNone(refgate.find_optout("just a normal title"))


class CheckTest(unittest.TestCase):
    def test_pass_on_ref(self):
        r = refgate.check("[EXEC-456] do the thing")
        self.assertTrue(r.ok)
        self.assertEqual(r.refs, ["EXEC-456"])
        self.assertIsNone(r.optout)

    def test_pass_on_optout(self):
        r = refgate.check("infra tidy [no-ticket: gitignore only]")
        self.assertTrue(r.ok)
        self.assertEqual(r.refs, [])
        self.assertEqual(r.optout, "gitignore only")

    def test_fail_on_refless_and_no_optout(self):
        r = refgate.check("Paramount+ era triage tools + RV dedup")  # a real ref-less merge
        self.assertFalse(r.ok)
        self.assertEqual(r.refs, [])
        self.assertIsNone(r.optout)
        self.assertIn("no", r.reason.lower())  # message explains the failure

    def test_empty_optout_does_not_pass(self):
        r = refgate.check("oops [no-ticket:]")
        self.assertFalse(r.ok)


if __name__ == "__main__":
    unittest.main()
