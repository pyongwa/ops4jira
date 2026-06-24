#!/usr/bin/env python3
"""Tests for the REST transport adapter (EXEC-442). Stdlib unittest, no live calls.

Run: python3 meta/atlassian-transport/test_atlassian_rest.py
"""
import base64
import json
import os
import unittest

from jiraops import transport as A


def _cfg():
    return A.Config(site="example.atlassian.net", email="u@example.com", token="tok")


class Recorder:
    """Fake sender: records calls, returns a canned (status, dict)."""
    def __init__(self, status=200, data=None):
        self.status, self.data, self.calls = status, (data or {}), []

    def __call__(self, method, url, headers, body_bytes):
        body = json.loads(body_bytes.decode()) if body_bytes else None
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return self.status, self.data


class ConfigTests(unittest.TestCase):
    def test_from_env_missing_raises(self):
        old = {k: os.environ.pop(k, None) for k in
               ("ATLASSIAN_SITE", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN")}
        try:
            with self.assertRaises(A.TransportError):
                A.Config.from_env()
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v

    def test_from_env_present(self):
        os.environ.update(ATLASSIAN_SITE="s.atlassian.net",
                          ATLASSIAN_EMAIL="e@x.com", ATLASSIAN_API_TOKEN="t")
        c = A.Config.from_env()
        self.assertEqual(c.site, "s.atlassian.net")

    def test_auth_header_is_basic_b64(self):
        c = _cfg()
        expected = "Basic " + base64.b64encode(b"u@example.com:tok").decode()
        self.assertEqual(c.auth_header, expected)


class JiraTests(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder(data={"ok": True})
        self.t = A.Transport(_cfg(), sender=self.rec)

    def test_search_posts_jql(self):
        self.t.jira_search("project = EXEC", fields=["summary"], max_results=10)
        call = self.rec.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/rest/api/3/search"))
        self.assertEqual(call["body"]["jql"], "project = EXEC")
        self.assertEqual(call["body"]["maxResults"], 10)

    def test_create_wraps_project_and_type(self):
        self.t.jira_create("EXEC", "Task", {"summary": "x"})
        body = self.rec.calls[0]["body"]
        self.assertEqual(body["fields"]["project"], {"key": "EXEC"})
        self.assertEqual(body["fields"]["issuetype"], {"name": "Task"})
        self.assertEqual(body["fields"]["summary"], "x")

    def test_update_is_put_with_fields(self):
        self.t.jira_update("EXEC-1", {"assignee": {"accountId": "abc"}})
        call = self.rec.calls[0]
        self.assertEqual(call["method"], "PUT")
        self.assertTrue(call["url"].endswith("/rest/api/3/issue/EXEC-1"))
        self.assertEqual(call["body"], {"fields": {"assignee": {"accountId": "abc"}}})

    def test_transition_posts_id(self):
        self.t.jira_transition("EXEC-1", "31")
        call = self.rec.calls[0]
        self.assertTrue(call["url"].endswith("/rest/api/3/issue/EXEC-1/transitions"))
        self.assertEqual(call["body"], {"transition": {"id": "31"}})

    def test_get_appends_fields_query(self):
        self.t.jira_get("EXEC-1", fields=["summary", "status"])
        self.assertIn("?fields=summary,status", self.rec.calls[0]["url"])

    def test_auth_header_sent(self):
        self.t.jira_get("EXEC-1")
        self.assertIn("Authorization", self.rec.calls[0]["headers"])

    def test_non_2xx_raises(self):
        t = A.Transport(_cfg(), sender=Recorder(status=400, data="bad jql"))
        with self.assertRaises(A.TransportError):
            t.jira_search("garbage")


class ConfluenceTests(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder(data={"id": "123"})
        self.t = A.Transport(_cfg(), sender=self.rec)

    def test_create_page_payload(self):
        self.t.cf_create_page("65955", "Title", "<p>hi</p>", parent_id="9")
        body = self.rec.calls[0]["body"]
        self.assertEqual(body["spaceId"], "65955")
        self.assertEqual(body["title"], "Title")
        self.assertEqual(body["body"], {"representation": "storage", "value": "<p>hi</p>"})
        self.assertEqual(body["parentId"], "9")

    def test_update_page_requires_version(self):
        self.t.cf_update_page("123", "T", "<p>x</p>", version=4)
        call = self.rec.calls[0]
        self.assertEqual(call["method"], "PUT")
        self.assertEqual(call["body"]["version"], {"number": 4})


if __name__ == "__main__":
    unittest.main(verbosity=2)
