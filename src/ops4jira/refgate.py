#!/usr/bin/env python3
"""Pre-merge ticket-reference gate (EXEC-464).

Deterministic, offline, no-LLM: decide whether a change is allowed to merge
based purely on its text (PR title + body, or a commit range's subjects). A
change passes iff it carries an `[EXEC-NNN]`/`[IDEA-NNN]` reference OR an
explicit, reasoned opt-out token `[no-ticket: <reason>]`.

This is the *prevention* half of the ambient-Jira loop: it keeps every merge
correlatable to a ticket, which is the data the EXEC-456 audit + gap-probe
depend on. The opt-out is explicit and reasoned so legitimately ticketless work
(infra chores) is a recorded decision, not a silent miss.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PROJECTS = ("EXEC", "IDEA")
# `[no-ticket: reason]` — reason required (non-empty after strip).
_OPTOUT_RE = re.compile(r"\[no-ticket:\s*([^\]]*?)\s*\]", re.IGNORECASE)


def _ref_re(projects) -> re.Pattern:
    keys = "|".join(re.escape(p) for p in projects)
    # Uppercase project key + number, with a word boundary; brackets optional.
    return re.compile(rf"\b(?:{keys})-\d+\b")


def find_refs(text: str, projects=DEFAULT_PROJECTS) -> list[str]:
    """Ordered, de-duplicated ticket references for the given projects."""
    seen, out = set(), []
    for m in _ref_re(projects).finditer(text or ""):
        ref = m.group(0)
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def find_optout(text: str):
    """The reason from a `[no-ticket: reason]` token, or None. Reason required."""
    m = _OPTOUT_RE.search(text or "")
    if not m:
        return None
    reason = m.group(1).strip()
    return reason or None


@dataclass
class CheckResult:
    ok: bool
    refs: list
    optout: object  # str | None
    reason: str     # human-readable explanation


def check(text: str, projects=DEFAULT_PROJECTS) -> CheckResult:
    refs = find_refs(text, projects)
    optout = find_optout(text)
    if refs:
        return CheckResult(True, refs, None, f"references {', '.join(refs)}")
    if optout:
        return CheckResult(True, [], optout, f"explicit opt-out: {optout}")
    return CheckResult(
        False, [], None,
        f"no {'/'.join(projects)} ticket reference and no '[no-ticket: reason]' opt-out",
    )
