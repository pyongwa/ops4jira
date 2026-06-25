# Prior art & alternatives

Ops4Jira is one honest option in an active space — not the only one. Use whatever fits your need.

- **Anthropic's official [Atlassian plugin](https://claude.com/plugins/atlassian)** and hosted
  **Claude Agent for Jira** — natural-language Jira/Confluence from Claude. If you want LLM-driven,
  zero-setup actions, start there. Ops4Jira is the opposite stance: deterministic and scriptable.
- **Paid GUI bulk-edit apps** (e.g. codefortynine Advanced Bulk Edit) — point-and-click bulk edits
  inside Jira. Ops4Jira is for the command line / pipelines / agents instead.
- **`atlassian-cli`** and the **`jira` Python library** — general Jira CLIs/SDKs. Ops4Jira is
  narrower and opinionated: just deterministic decompose + audit, idempotent by stable key.
- **Native Jira** — "split issue" is a manual, one-at-a-time GUI action; automation rules do
  summary-similarity dedup per-project. Ops4Jira is batch, scriptable, and portable.
- **The idempotency gap** — Jira's REST API has no idempotent-create endpoint
  ([Atlassian developer community](https://community.developer.atlassian.com/t/how-do-i-ensure-issue-creation-is-idempotent/93517)).
  Ops4Jira closes it client-side with a stable per-item key.

This list reflects what we found while building the tool; it isn't exhaustive, and "not listed"
doesn't mean "doesn't exist." PRs adding alternatives we missed are welcome.
