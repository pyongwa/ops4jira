# Changelog

All notable changes to Ops4Jira are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-26

First public release — the **read/offline wedge**.

### Added
- `decompose` — plan how a bundled ticket splits into one child per item, from a
  markdown table or bullet/numbered list. Offline (file/stdin) or live read
  (`--issue`, read-only). Each planned child carries a stable per-item key.
- `audit` — read-only hygiene report for an Epic's children: inventory by
  type/status/assignee, outstanding count, deterministic duplicate detection
  (summary-token overlap), optional `--stale-before` cutoff.
- `check-ref` — offline pre-merge gate requiring an `[EXEC-NNN]`/`[IDEA-NNN]`
  reference or a recorded `[no-ticket: reason]` opt-out. Ships with a GitHub
  Actions template (`examples/github-actions/ref-gate.yml`); needs no secrets.
- Zero third-party dependencies (Python stdlib only). Split license:
  Apache-2.0 (code) / CC-BY-4.0 (docs).

### Not yet exposed
- Write operations — creating decomposed children (`decompose --apply`) and
  transitioning tickets (`transition`) — are implemented and unit-tested but held
  out of the v0.1 CLI pending live-instance validation. See [ROADMAP.md](ROADMAP.md).

[0.1.0]: https://github.com/pyongwa/ops4jira/releases/tag/v0.1.0
