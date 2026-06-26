# Ops4Jira

**Deterministic, no-LLM Jira operations from the command line.**

> **v0.1 — read/offline wedge.** This release covers the read and offline operations:
> plan a bundled ticket into one child per item, audit a hierarchy for hygiene, and gate
> merges on a ticket reference. **Write operations** (creating the children, transitioning
> tickets) are implemented and unit-tested but not exposed in this release, pending
> live-instance validation — see [`ROADMAP.md`](ROADMAP.md) and [`CHANGELOG.md`](CHANGELOG.md).

Things you do to a Jira backlog over and over — *plan how a bundled ticket splits into one
child per item*, *audit a hierarchy for hygiene*, and *keep every merge tied to a ticket* —
done by a small, scriptable, **deterministic** tool. Same input, same result, every run. No
LLM in the loop, so it's safe to put in a pipeline or hand to an agent.

Why it exists: every other way to do this is either an LLM agent (non-deterministic) or a
paid GUI app. The deterministic core derives a **stable per-item key** for each planned
child, so when the write release lands, re-running never duplicates (Jira's REST API has no
idempotent-create of its own).

## Install

```bash
pip install ops4jira          # (once public)
# or from source:
pip install -e .
```

Zero third-party dependencies — Python stdlib only.

## Use

### Decompose a bundled ticket → one child per item

Offline (no Jira needed) — parse a description and see the plan:

```bash
ops4jira decompose bundled.md            # markdown table or bullet/numbered list
cat bundled.md | ops4jira decompose -    # stdin
ops4jira decompose bundled.md --json     # machine-readable items
```

Live (read-only) — read the bundled description from a Jira issue, then print the plan:

```bash
export ATLASSIAN_SITE=your-site.atlassian.net
export ATLASSIAN_EMAIL=you@example.com
export ATLASSIAN_API_TOKEN=...          # https://id.atlassian.com/manage-profile/security/api-tokens

ops4jira decompose --issue PROJ-123     # reads the issue, prints the plan — writes nothing
```

Each planned child carries a **stable per-item key** (the basis for idempotent creation in the
write release). Creating the children is a write op planned for the next release — see
[`ROADMAP.md`](ROADMAP.md).

### Audit an Epic's children (read-only)

```bash
ops4jira audit --epic PROJ-100                       # inventory by type/status/assignee + outstanding + duplicates
ops4jira audit --epic PROJ-100 --stale-before 2026-06-01   # also flag open items not updated since a date
```

`audit` performs **no writes**. Duplicate detection is a deterministic summary-token overlap
(Jaccard); stale detection takes the cutoff as an argument (no hidden "now").

### Gate a merge on a ticket reference (offline)

```bash
ops4jira check-ref --title "[EXEC-456] Slice 2"      # exit 0: passes
ops4jira check-ref --title "Paramount+ era triage"   # exit 1: no ref, no opt-out
ops4jira check-ref --title "tidy [no-ticket: gitignore only]"   # exit 0: explicit opt-out
git log -1 --format=%B | ops4jira check-ref          # check a commit message from stdin
```

Fully offline and deterministic — no Jira. Passes iff the text carries an `[EXEC-NNN]`/`[IDEA-NNN]`
reference **or** an explicit `[no-ticket: reason]` opt-out (reason required, so a ticketless change
is a recorded decision, not a silent miss). Exit 1 on failure, so it drops straight into a
`commit-msg`/`pre-push` git hook or a PR check. Configurable keys via `--projects EXEC,IDEA,ABC`.

### Run it in CI / git

A drop-in template lives in [`examples/github-actions/`](examples/github-actions/): `ref-gate.yml`
fails any PR whose title/body lacks an `[EXEC-NNN]`/`[IDEA-NNN]` reference (or a recorded
`[no-ticket: reason]` opt-out). It's offline and needs no secrets. (An on-merge auto-transition
Action ships with the write release — see [`ROADMAP.md`](ROADMAP.md).)

## How it works

- **Decompose** auto-detects a markdown table vs a list, derives a readable+hashed **stable key**
  per row (identical rows → identical key = idempotent; similar rows → distinct keys = no collision).
- **Audit** reads workflow statuses from the data (never hardcoded); only Jira's `statusCategory`
  system field is treated as the canonical Done marker.
- **Check-ref** is a pure text gate (no Jira): one regex for `PROJECT-NNN` refs, one for the
  reasoned opt-out token — the *prevention* half of keeping every merge ticket-correlatable.
- **Transport** is stdlib `urllib` against the Jira Cloud REST API with an API token (used by
  the live read paths `--issue` / `--epic`).

## Prior art & alternatives

Ops4Jira is one option in an active space — see [`PRIOR-ART.md`](PRIOR-ART.md). If a first-party
tool or a GUI app fits your need better, use it. Ops4Jira's niche is *deterministic, scriptable,
idempotent* operations for pipelines and agents.

## Use it freely

The code is **Apache-2.0** — use it, modify it, ship it, commercially or not. The one thing
reserved is the name: please don't release a fork, product, or company *as* "Ops4Jira" (saying
your tool is *based on* or *a fork of* Ops4Jira is fine — just don't present it *as* Ops4Jira).
Apache-2.0 §6 already grants no rights to the name; this note just says plainly why it's held
back — so there's one clear Ops4Jira, and forks are honestly their own thing.

Not affiliated with or endorsed by Atlassian. Jira is a trademark of Atlassian, used here only
to describe compatibility.

## License

Split-licensed — see [`LICENSE`](LICENSE): code **Apache-2.0** ([`LICENSE-CODE`](LICENSE-CODE)),
docs **CC-BY-4.0** ([`LICENSE-SPEC`](LICENSE-SPEC)). See [`NOTICE`](NOTICE) for attribution and
the name reservation.

By **Fred Chong Rutherford** — 20+ years with Jira/Atlassian and agile frameworks (CSPO, CSM, SAFe).
Part of the Agentic Software Operations line.
