#!/usr/bin/env python3
"""Ops4Jira — deterministic Jira operations from the command line.

v0.1 is the read/offline wedge — deterministic, no-LLM commands that never write
to Jira:

  ops4jira decompose <file|->        parse a bundled description -> a per-item plan (offline)
  ops4jira decompose --issue KEY     read the issue from Jira, then print the plan (read-only)
  ops4jira audit --epic KEY          read an Epic's children from Jira, print a hygiene report
  ops4jira check-ref --title ...      gate: require an [EXEC-NNN]/[IDEA-NNN] ref (offline; exit 1 on fail)

The offline `decompose <file>` and `check-ref` paths need no Jira and are fully
deterministic. The live read paths (`--issue`, `--epic`) use the REST transport
and an Atlassian API token (env: ATLASSIAN_SITE / ATLASSIAN_EMAIL /
ATLASSIAN_API_TOKEN).

Write operations (create children from a plan, transition a ticket) are planned
for a future release — see ROADMAP.md. The modules are staged but not exposed in
the v0.1 CLI, pending live-instance validation.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import audit as _audit
from . import decompose as _decompose
from . import refgate as _refgate
from .transport import Config, Transport, TransportError


# ---------------------------------------------------------------------------
# ADF -> text (best-effort) so the deterministic parser can read a live issue.
# Jira Cloud returns issue descriptions as ADF (Atlassian Document Format) JSON.
# We reconstruct the markdown table/list shapes the parser expects. Plain
# strings pass through unchanged.
# ---------------------------------------------------------------------------

def adf_to_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "table":
        return _adf_table(node)
    children = node.get("content", []) or []
    if t in ("bulletList", "orderedList"):
        lines = []
        for li in children:
            txt = "".join(adf_to_text(c) for c in (li.get("content", []) or [])).strip()
            if txt:
                lines.append(f"- {txt}")
        return "\n".join(lines)
    if t in ("paragraph", "heading", "tableCell", "tableHeader", "listItem"):
        return "".join(adf_to_text(c) for c in children)
    # doc / unknown container: join block children with newlines
    return "\n".join(s for s in (adf_to_text(c) for c in children) if s)


def _adf_table(table) -> str:
    rows = []
    for row in table.get("content", []) or []:
        cells = ["".join(adf_to_text(c) for c in (cell.get("content", []) or [])).strip()
                 for cell in (row.get("content", []) or [])]
        rows.append("| " + " | ".join(cells) + " |")
    if len(rows) >= 1:
        ncols = rows[0].count("|") - 1
        sep = "| " + " | ".join(["---"] * max(ncols, 1)) + " |"
        rows.insert(1, sep)  # synthetic separator so the parser detects a table
    return "\n".join(rows)


def _description_text(issue: dict) -> str:
    desc = (issue.get("fields") or {}).get("description")
    if isinstance(desc, str):
        return desc
    return adf_to_text(desc)


# ---------------------------------------------------------------------------
# decompose
# ---------------------------------------------------------------------------

def cmd_decompose(args) -> int:
    if args.issue:
        tx = _transport()
        issue = tx.jira_get(args.issue, fields=["description", "project"])
        text = _description_text(issue)
        items = _decompose.parse(text)
        print(_decompose.format_plan(items, parent=args.issue))
        return 0

    # offline file/stdin path — fully deterministic, no Jira
    text = sys.stdin.read() if args.file in (None, "-") else open(args.file, encoding="utf-8").read()
    items = _decompose.parse(text)
    if args.json:
        print(json.dumps([it.as_dict() for it in items], indent=2))
    else:
        print(_decompose.format_plan(items, parent=args.parent))
    return 0


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def cmd_audit(args) -> int:
    tx = _transport()
    jql = f'parent = {args.epic} ORDER BY status'
    fields = ["summary", "status", "issuetype", "assignee", "updated"]
    res = tx.jira_search(jql, fields=fields, max_results=args.max)
    issues = [_compact(node) for node in res.get("issues", [])]

    inv = _audit.inventory(issues)
    out = _audit.outstanding(issues)
    dupes = _audit.duplicates(issues, threshold=args.dup_threshold)
    stale = _audit.stale(issues, args.stale_before) if args.stale_before else []

    print(f"AUDIT {args.epic} — {inv['total']} children")
    print(f"  by type:     {inv['by_type']}")
    print(f"  by status:   {inv['by_status']}")
    print(f"  by assignee: {inv['by_assignee']}")
    print(f"  outstanding (not Done): {len(out)}")
    if args.stale_before:
        print(f"  stale (open, not updated since {args.stale_before}): {len(stale)}")
        for i in stale:
            print(f"     {i['key']}  {i['summary']}  (updated {i.get('updated','?')[:10]})")
    if dupes:
        print(f"  possible duplicates (>= {args.dup_threshold} summary overlap):")
        for a, b, sim in dupes:
            print(f"     {a} ~ {b}  ({sim:.2f})")
    return 0


def _compact(node: dict) -> dict:
    f = node.get("fields", {}) or {}
    status = f.get("status") or {}
    assignee = f.get("assignee") or {}
    return {
        "key": node.get("key"),
        "summary": f.get("summary") or "",
        "type": (f.get("issuetype") or {}).get("name"),
        "status": status.get("name"),
        "statusCategory": (status.get("statusCategory") or {}).get("name"),
        "assignee": assignee.get("displayName"),
        "updated": f.get("updated"),
    }


# ---------------------------------------------------------------------------
# check-ref  (EXEC-464) — deterministic, offline pre-merge gate
# ---------------------------------------------------------------------------

def cmd_check_ref(args) -> int:
    if args.title is not None or args.body is not None:
        text = "\n".join(p for p in (args.title, args.body) if p)
    else:
        text = sys.stdin.read() if args.file in (None, "-") else open(args.file, encoding="utf-8").read()
    projects = tuple(p.strip() for p in args.projects.split(",") if p.strip())
    r = _refgate.check(text, projects=projects)
    print(f"{'PASS' if r.ok else 'FAIL'}: {r.reason}")
    return 0 if r.ok else 1


# ---------------------------------------------------------------------------

def _transport() -> Transport:
    try:
        return Transport(Config.from_env())
    except TransportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ops4jira", description="Deterministic Jira operations from the CLI.")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("decompose", help="Plan one child per item from a bundled ticket (read-only).")
    d.add_argument("file", nargs="?", help="File with the bundled description (or '-' for stdin). Offline.")
    d.add_argument("--issue", help="Read the bundled description from this Jira issue key (live, read-only).")
    d.add_argument("--parent", default="<PARENT>", help="Parent label for the offline plan header.")
    d.add_argument("--json", action="store_true", help="Emit items as JSON (offline path).")
    d.set_defaults(func=cmd_decompose)

    a = sub.add_parser("audit", help="Report hygiene for an Epic's children (read-only).")
    a.add_argument("--epic", required=True, help="Epic (or parent) key to audit.")
    a.add_argument("--stale-before", help="Flag open children not updated since this YYYY-MM-DD.")
    a.add_argument("--dup-threshold", type=float, default=0.7, help="Summary-overlap threshold (default 0.7).")
    a.add_argument("--max", type=int, default=100, help="Max children to fetch (default 100).")
    a.set_defaults(func=cmd_audit)

    c = sub.add_parser("check-ref", help="Gate: require an [EXEC-NNN]/[IDEA-NNN] ref (or [no-ticket: reason]). Offline; exit 1 on fail.")
    c.add_argument("file", nargs="?", help="File with the text to check (or '-'/omitted for stdin).")
    c.add_argument("--title", help="PR/commit title to check.")
    c.add_argument("--body", help="PR/commit body (combined with --title).")
    c.add_argument("--projects", default="EXEC,IDEA", help="Comma-separated project keys (default EXEC,IDEA).")
    c.set_defaults(func=cmd_check_ref)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
