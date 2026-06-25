# Ops4Jira

**Deterministic, no-LLM, idempotent Jira operations from the command line.**

Two things you do to a Jira backlog over and over — *split a bundled ticket into one
child per item*, and *audit a hierarchy for hygiene* — done by a small, scriptable,
**deterministic** tool. Same input, same result, every run. No LLM in the loop, so it's
safe to put in a pipeline or hand to an agent.

Why it exists: every other way to do this is either an LLM agent (non-deterministic) or a
paid GUI app, and Jira's REST API has **no idempotent-create** — so re-running a script
double-creates. Ops4Jira solves that with a stable per-item key, so re-apply never duplicates.

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

Live — read the issue from Jira, then create the children:

```bash
export ATLASSIAN_SITE=your-site.atlassian.net
export ATLASSIAN_EMAIL=you@example.com
export ATLASSIAN_API_TOKEN=...          # https://id.atlassian.com/manage-profile/security/api-tokens

ops4jira decompose --issue PROJ-123              # dry-run: prints the plan, writes nothing
ops4jira decompose --issue PROJ-123 --apply      # creates one child per item under PROJ-123
```

**Idempotent:** each child is labelled with the item's stable key; `--apply` skips any item
whose label already exists. Run it twice — the second run creates nothing. The original
ticket is never deleted.

### Audit an Epic's children (read-only)

```bash
ops4jira audit --epic PROJ-100                       # inventory by type/status/assignee + outstanding + duplicates
ops4jira audit --epic PROJ-100 --stale-before 2026-06-01   # also flag open items not updated since a date
```

`audit` performs **no writes**. Duplicate detection is a deterministic summary-token overlap
(Jaccard); stale detection takes the cutoff as an argument (no hidden "now").

## How it works

- **Decompose** auto-detects a markdown table vs a list, derives a readable+hashed **stable key**
  per row (identical rows → identical key = idempotent; similar rows → distinct keys = no collision).
- **Audit** reads workflow statuses from the data (never hardcoded); only Jira's `statusCategory`
  system field is treated as the canonical Done marker.
- **Transport** is stdlib `urllib` against the Jira Cloud REST API with an API token.

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
