# Ops4Jira roadmap

Direction, not dated commitments. Versions follow [SemVer](https://semver.org/);
shipped detail lives in [CHANGELOG.md](CHANGELOG.md).

## v0.1.0 — read/offline wedge · released 2026-06-26

Plan (`decompose`), audit (`audit`), gate (`check-ref`). Deterministic, no-LLM,
no writes to Jira.

## v0.2.0 — write operations · planned

The write half, gated behind a real live-instance validation first:

- `decompose --apply` — idempotently create one child per planned item (the stable
  per-item key means re-runs never duplicate, the thing Jira's REST API can't do).
- `transition` — idempotently move a ticket to a target status (no-op if already there).
- `auto-transition` GitHub Action — on PR merge, transition every referenced ticket.

The code for these is already present and unit-tested against a fake transport; the
release gate is a real round-trip against a live Jira instance, not more unit tests.

## Later — exploratory

- Sprint / board operations (pending whether the Agile API is required).
- Additional read-only reports.

---

Part of the **Agentic Software Operations** line —
[ops4atlassian](https://github.com/pyongwa/ops4atlassian) ·
[product-ops-2](https://github.com/pyongwa/product-ops-2) ·
[agentic-software-operations](https://github.com/pyongwa/agentic-software-operations).
