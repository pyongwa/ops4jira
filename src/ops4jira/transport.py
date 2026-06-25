#!/usr/bin/env python3
"""REST adapter for the Atlassian-transport contract (EXEC-442).

The Atlassian Companion skills speak to Jira/Confluence through a small
transport CONTRACT (see transport-contract.md). The Rovo MCP is the default
adapter; THIS is the REST adapter — so the pack runs with no MCP present, via
an Atlassian API token. Stdlib-only (`urllib`); deterministic; no third-party deps.

Config (env): ATLASSIAN_SITE (e.g. your-site.atlassian.net), ATLASSIAN_EMAIL,
ATLASSIAN_API_TOKEN. Auth is HTTP Basic (email:token), per Atlassian Cloud REST.

Testability: all network egress funnels through `Transport._send`; tests inject a
fake sender, so the suite makes zero live calls.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class TransportError(RuntimeError):
    """A transport-layer failure (HTTP error, missing config, bad response)."""


@dataclass
class Config:
    site: str        # "your-site.atlassian.net"
    email: str
    token: str

    @classmethod
    def from_env(cls) -> "Config":
        missing = [k for k in ("ATLASSIAN_SITE", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN")
                   if not os.environ.get(k)]
        if missing:
            raise TransportError(f"missing env for REST adapter: {', '.join(missing)}")
        return cls(os.environ["ATLASSIAN_SITE"],
                   os.environ["ATLASSIAN_EMAIL"],
                   os.environ["ATLASSIAN_API_TOKEN"])

    @property
    def auth_header(self) -> str:
        raw = f"{self.email}:{self.token}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")


class Transport:
    """The REST adapter — one method per contract operation.

    Pass a custom `sender` (callable: method, url, headers, body_bytes -> (status, dict))
    to test without network. Default sender uses urllib.
    """

    def __init__(self, config: Config, sender=None):
        self.config = config
        self._sender = sender or self._urllib_send

    # -- the contract -------------------------------------------------------

    # Jira
    def jira_search(self, jql: str, fields=None, max_results: int = 50) -> dict:
        body = {"jql": jql, "maxResults": max_results, "fields": fields or ["summary", "status"]}
        return self._send("POST", "/rest/api/3/search", body)

    def jira_get(self, key: str, fields=None) -> dict:
        q = "?fields=" + ",".join(fields) if fields else ""
        return self._send("GET", f"/rest/api/3/issue/{key}{q}")

    def jira_create(self, project: str, issuetype: str, fields: dict) -> dict:
        payload = {"fields": {"project": {"key": project}, "issuetype": {"name": issuetype}, **fields}}
        return self._send("POST", "/rest/api/3/issue", payload)

    def jira_update(self, key: str, fields: dict) -> dict:
        # 204 No Content on success; normalize to a dict.
        return self._send("PUT", f"/rest/api/3/issue/{key}", {"fields": fields})

    def jira_transition(self, key: str, transition_id: str) -> dict:
        return self._send("POST", f"/rest/api/3/issue/{key}/transitions",
                          {"transition": {"id": transition_id}})

    # Confluence
    def cf_get_page(self, page_id: str) -> dict:
        return self._send("GET", f"/wiki/api/v2/pages/{page_id}?body-format=storage")

    def cf_create_page(self, space_id: str, title: str, body_storage: str, parent_id: str = None) -> dict:
        payload = {"spaceId": space_id, "status": "current", "title": title,
                   "body": {"representation": "storage", "value": body_storage}}
        if parent_id:
            payload["parentId"] = parent_id
        return self._send("POST", "/wiki/api/v2/pages", payload)

    def cf_update_page(self, page_id: str, title: str, body_storage: str, version: int) -> dict:
        payload = {"id": page_id, "status": "current", "title": title,
                   "body": {"representation": "storage", "value": body_storage},
                   "version": {"number": version}}
        return self._send("PUT", f"/wiki/api/v2/pages/{page_id}", payload)

    # -- plumbing -----------------------------------------------------------

    def _send(self, method: str, path: str, body: dict = None) -> dict:
        url = f"https://{self.config.site}{path}"
        headers = {"Authorization": self.config.auth_header, "Accept": "application/json"}
        body_bytes = None
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, data = self._sender(method, url, headers, body_bytes)
        if not (200 <= status < 300):
            raise TransportError(f"{method} {path} -> HTTP {status}: {data}")
        return data if isinstance(data, dict) else {"status": status, "raw": data}

    @staticmethod
    def _urllib_send(method: str, url: str, headers: dict, body_bytes):
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8") or "{}"
                return resp.status, (json.loads(raw) if raw.strip() else {})
        except urllib.error.HTTPError as e:  # surface the body for diagnostics
            detail = e.read().decode("utf-8", "replace") if e.fp else ""
            return e.code, detail
