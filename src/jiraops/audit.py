"""Pure analysis helpers for jira-hierarchy-audit (EXEC-428).

These functions operate over a COMPACT issue list — the output of the
"compact inventory first" step in SKILL.md. Each issue is a dict with the
keys produced by the jq projection:

    {
        "key":            "EXEC-123",
        "summary":        "Build the widget",
        "type":           "Story",
        "status":         "In Progress",       # workflow status (variable, read from data)
        "statusCategory": "In Progress",       # system field: To Do / In Progress / Done
        "assignee":       "Pyongwa",           # display name or None/"" if unassigned
        "updated":        "2026-06-20T14:23:11.123-0400",
    }

Design constraints (deliberate):
- Deterministic. No live Jira calls, no network, no `datetime.now()`.
  `stale()` takes the cutoff as an argument so the caller owns "now".
- Workflow status names are NEVER hardcoded — `inventory()` reads whatever
  statuses appear in the data. Only `statusCategory` is treated as a stable
  system field (its three values are fixed by Jira: To Do / In Progress / Done).
- Stdlib only.
"""

from collections import Counter

# The single canonical "completed" marker. statusCategory is a Jira *system*
# field (not a workflow status), so comparing against "done" is safe and is
# NOT a hardcoded-status violation. Matched case-insensitively.
DONE_CATEGORY = "done"


def _assignee_label(issue):
    """Normalize a possibly-missing assignee to a stable bucket label."""
    name = issue.get("assignee")
    if name is None or (isinstance(name, str) and not name.strip()):
        return "Unassigned"
    return name


def _is_done(issue):
    """True when the issue's statusCategory marks it complete."""
    cat = issue.get("statusCategory") or ""
    return cat.strip().lower() == DONE_CATEGORY


def inventory(issues):
    """Count issues grouped by type, by status, and by assignee.

    Status counts use the workflow status field as-is (read from data —
    never a hardcoded set). Returns plain dicts so the result is JSON-friendly
    and order-independent for testing.
    """
    by_type = Counter()
    by_status = Counter()
    by_assignee = Counter()
    for issue in issues:
        by_type[issue.get("type") or "Unknown"] += 1
        by_status[issue.get("status") or "Unknown"] += 1
        by_assignee[_assignee_label(issue)] += 1
    return {
        "total": len(issues),
        "by_type": dict(by_type),
        "by_status": dict(by_status),
        "by_assignee": dict(by_assignee),
    }


def outstanding(issues):
    """Return the open issues — those whose statusCategory is not Done.

    Order is preserved from the input.
    """
    return [issue for issue in issues if not _is_done(issue)]


def stale(issues, cutoff):
    """Return open issues not updated since `cutoff`.

    `cutoff` is supplied by the caller (no real-time call here). Comparison is
    done on the leading date prefix (YYYY-MM-DD): ISO-8601 dates sort
    lexicographically in chronological order, which sidesteps the millisecond /
    colon-less-timezone parsing pitfalls of real Jira `updated` timestamps
    (e.g. "2026-06-20T14:23:11.123-0400") across Python versions.

    `cutoff` may be a full timestamp or a "YYYY-MM-DD" date; only its first 10
    characters are used. An issue with an empty/missing `updated` is treated as
    stale (it has no evidence of recent activity).
    """
    cutoff_day = (cutoff or "")[:10]
    result = []
    for issue in outstanding(issues):
        updated_day = (issue.get("updated") or "")[:10]
        if updated_day < cutoff_day:
            result.append(issue)
    return result


def _normalize_tokens(summary):
    """Lowercase, strip punctuation, return a set of alphanumeric tokens."""
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in (summary or ""))
    return set(cleaned.split())


def _jaccard(a, b):
    """Token-overlap similarity (Jaccard) of two token sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def duplicates(issues, threshold=0.7):
    """Find near-identical pairs of issues by normalized summary token overlap.

    Returns a list of (key_a, key_b, similarity) tuples where similarity >=
    threshold. Pairs are symmetric and de-duplicated: each unordered pair is
    reported at most once, no self-pairs, and (A,B) is never also (B,A). Keys
    within each pair are ordered for stable output.
    """
    tokens = [(issue.get("key"), _normalize_tokens(issue.get("summary"))) for issue in issues]
    pairs = []
    for i in range(len(tokens)):
        key_a, tok_a = tokens[i]
        for j in range(i + 1, len(tokens)):
            key_b, tok_b = tokens[j]
            sim = _jaccard(tok_a, tok_b)
            if sim >= threshold:
                lo, hi = sorted([key_a, key_b])
                pairs.append((lo, hi, sim))
    return pairs
