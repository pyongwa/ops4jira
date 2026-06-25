#!/usr/bin/env python3
"""Decompose a bundled Jira ticket description into a structured per-item list.

A "bundled" ticket is one whose description carries N items in a markdown table
or a bullet/numbered list, where each item should really be its own child
ticket. This module is the deterministic, stdlib-only *parser* half of the
`jira-bundled-ticket-decomposer` skill. It does NOT talk to Jira — the live
create/link/transition writes are the SKILL.md's session-mediated MCP steps.

Design (documented so the skill's apply step can rely on it):

- Auto-detect table vs list. Precedence: if any line looks like a markdown
  table row (contains a pipe `|`) AND a separator row (e.g. `|---|---|`) is
  present, parse as a table; otherwise parse as a list. Empty / unrecognized
  input yields an empty item list (never raises).
- Title heuristic: table -> first column cell; list -> the line's text (minus
  the bullet/number marker).
- Stable key: a readable slug of the title PLUS a short hash digest of the
  *full normalized row text*. Two rows with similar titles still get distinct
  keys (the digest differs); byte-identical rows collapse to the same key
  (idempotency). The key is what the apply step writes onto each child and
  searches for before creating, so re-apply never duplicates.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """One decomposed item -> one proposed child ticket."""

    title: str
    source: str  # the raw row/line text, preserved verbatim for traceability
    key: str     # stable, deterministic per-item key (slug + hash digest)
    columns: tuple = field(default=())  # extra table columns, if any

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "key": self.key,
            "columns": list(self.columns),
        }


# ---------------------------------------------------------------------------
# Normalization & key derivation
# ---------------------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase for stable hashing/comparison."""
    return _WS.sub(" ", text).strip().lower()


def _slug(text: str, max_len: int = 40) -> str:
    s = _SLUG_STRIP.sub("-", text.strip().lower()).strip("-")
    return s[:max_len].strip("-") or "item"


def stable_key(source_row: str) -> str:
    """Deterministic key for a row.

    slug-of-title + short digest of the *full normalized row* so that:
      - identical rows -> identical key (idempotent re-apply)
      - similar-titled but different rows -> distinct keys (no collision)
    """
    normalized = _normalize(source_row)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    # Title for the slug is the first column / the line text.
    title = _title_from_row(source_row)
    return f"{_slug(title)}-{digest}"


def _title_from_row(source_row: str) -> str:
    row = source_row.strip()
    if "|" in row:
        cells = _split_table_row(row)
        if cells:
            return cells[0]
    return _LIST_MARKER.sub("", row).strip()


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

_SEP_CELL = re.compile(r"^:?-{2,}:?$")


def _split_table_row(line: str) -> list:
    """Split a markdown table row into trimmed cells, dropping the outer pipes."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(_SEP_CELL.match(c.replace(" ", "")) for c in cells if c != "")


def _looks_like_table(lines: list) -> bool:
    pipe_rows = [ln for ln in lines if "|" in ln]
    has_sep = any(_is_separator_row(ln) for ln in lines if "|" in ln)
    return len(pipe_rows) >= 2 and has_sep


def parse_table(text: str) -> list:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows = [ln for ln in lines if "|" in ln]
    if not rows:
        return []

    sep_idx = next((i for i, ln in enumerate(rows) if _is_separator_row(ln)), None)
    if sep_idx is None:
        return []

    # Everything after the separator row is a data row (header precedes it).
    data_rows = rows[sep_idx + 1:]
    items = []
    for raw in data_rows:
        cells = _split_table_row(raw)
        if not cells or not any(cells):
            continue
        title = cells[0].strip()
        if not title:
            continue
        items.append(
            Item(
                title=title,
                source=raw.strip(),
                key=stable_key(raw),
                columns=tuple(cells),
            )
        )
    return items


# ---------------------------------------------------------------------------
# List parsing
# ---------------------------------------------------------------------------

def parse_list(text: str) -> list:
    items = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if not _LIST_MARKER.match(raw):
            continue
        title = _LIST_MARKER.sub("", raw).strip()
        if not title:
            continue
        items.append(
            Item(
                title=title,
                source=raw.strip(),
                key=stable_key(raw.strip()),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------

def parse(text: str) -> list:
    """Parse a bundled description into items. Never raises on bad input."""
    if not text or not text.strip():
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if _looks_like_table(lines):
        items = parse_table(text)
        if items:
            return items
    return parse_list(text)


# ---------------------------------------------------------------------------
# Dry-run plan formatter (no side effects)
# ---------------------------------------------------------------------------

def format_plan(items: list, parent: str = "<PARENT>") -> str:
    """Render the proposed children for human review. No Jira calls."""
    if not items:
        return "DRY RUN — no items parsed from the bundled description. Nothing to create."

    out = []
    out.append(f"DRY RUN — decompose {parent} into {len(items)} child ticket(s).")
    out.append(f"Original {parent} is PRESERVED (never deleted).")
    out.append("")
    for i, it in enumerate(items, 1):
        out.append(f"{i:>3}. {it.title}")
        out.append(f"     key:    {it.key}")
        out.append(f"     source: {it.source}")
    out.append("")
    out.append(f"Planned children: {len(items)}. On apply, created MUST equal {len(items)}.")
    out.append("Re-apply is idempotent: each child carries its key; existing keys are skipped.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Parse a bundled Jira ticket description into a per-item plan (dry-run; no Jira writes)."
    )
    ap.add_argument(
        "file",
        nargs="?",
        help="Path to a file containing the bundled description. Reads stdin if omitted.",
    )
    ap.add_argument("--parent", default="<PARENT>", help="Parent ticket key, for the plan header.")
    ap.add_argument("--json", action="store_true", help="Emit the item list as JSON instead of a plan.")
    args = ap.parse_args(argv)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()

    items = parse(text)

    if args.json:
        import json

        print(json.dumps([it.as_dict() for it in items], indent=2))
    else:
        print(format_plan(items, parent=args.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
