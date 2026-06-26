#!/usr/bin/env python3
"""Deterministic transition planner (EXEC-465).

Given an issue's current status and the transitions Jira currently offers for
it, decide the action: no-op (already in the target), fire a specific
transition id, or report the target unreachable. Pure + deterministic — the
live REST write is a thin transport call made by the CLI; all the decision
logic lives here and is fully unit-tested with no network.

This is the *automate* half of the ambient-Jira loop: a merged PR's ticket
moves itself (e.g. -> Done) instead of waiting for someone to drag a card.
"""
from __future__ import annotations

from dataclasses import dataclass


def _norm(s) -> str:
    return (s or "").strip().lower()


def resolve_transition_id(transitions, target_status: str):
    """The transition id that lands the issue in `target_status`, or None.

    Prefers a transition whose destination (`to.name`) matches the target;
    falls back to a transition whose own `name` matches. Case-insensitive."""
    target = _norm(target_status)
    for t in transitions:
        if _norm((t.get("to") or {}).get("name")) == target:
            return t.get("id")
    for t in transitions:
        if _norm(t.get("name")) == target:
            return t.get("id")
    return None


@dataclass
class Plan:
    action: str           # "noop" | "transition" | "unreachable"
    transition_id: object  # str | None
    reason: str


def plan(current_status: str, transitions, target_status: str) -> Plan:
    if _norm(current_status) == _norm(target_status):
        return Plan("noop", None, f"already in '{target_status}'")
    tid = resolve_transition_id(transitions, target_status)
    if tid is None:
        return Plan("unreachable", None,
                    f"no transition reaches '{target_status}' from '{current_status}'")
    return Plan("transition", tid, f"transition {tid} -> '{target_status}'")
