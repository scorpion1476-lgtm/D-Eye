# D-Eye - User Guide

_Task-oriented guide for people who want to use D-Eye, not extend it._

## Concept map (30 seconds)

- **Capability** - a verb the router understands (`search`, `fetch`, `feed`, `repo.inspect`, `extract`).
- **Connector** - a plugin that implements one or more capabilities.
- **Envelope** - one search result / fetched page + provenance + trust + warnings.
- **Research packet** - a bundle of envelopes with one query header, exportable as Markdown or JSON.
- **Evidence store** - SQLite database at `~/.deye/evidence.db` that persists every packet + source.
- **Skill** - a named orchestration recipe (see [`SKILLS_GUIDE.md`](SKILLS_GUIDE.md)).

## Common tasks

### Do research and save the result

```bash
deye research "your question here" --max-sources 5 -o out.md
```

The Markdown is fully cited (URL + timestamp + content hash per source).

### Ask the local evidence store what you already know

```bash
deye evidence "keyword"
```

### Fetch one specific page

```bash
deye fetch https://example.org/article
```

The fetch goes through the SSRF-guarded stack (private-IP block, IP
pinning, size cap, gzip-bomb guard, redirect re-validation).

### Look up a public GitHub repository

```bash
deye repo owner/name
```

Returns metadata + latest 5 commits.

### Build the evidence graph over what you've captured

```bash
deye graph "topic" --markdown -o graph.md
```

Includes entity list + candidate contradictions with confidence scores.
Contradiction confidences are heuristic - treat them as leads for review.

### Check that every connector is healthy

```bash
deye doctor
```

Reports N/M usable connectors + a per-connector status.

### List every configured skill + capability

```bash
deye capabilities
deye connectors
```

## Data + privacy

- Every source you capture lives on your machine at `~/.deye/evidence.db`.
  Nothing is uploaded off-device.
- Cookies used by the optional browser adapter live under
  `~/.deye/browser-profiles/` with owner-only permissions.
- There is no telemetry endpoint anywhere in D-Eye - enforced by
  `tests/test_no_telemetry_and_no_remote_skills.py`.
- To export or delete a tenant's data:

  ```python
  from deye.skills import invoke
  invoke("evidence", action="export", tenant="acme")
  invoke("evidence", action="delete", tenant="acme", confirm_delete=True)
  ```

  The default tenant (owner scope) is protected against tenant-scoped
  deletion.

## Consent for anything that writes

D-Eye is **read-only by default**. Any action that writes (browser
click, form fill, external POST, etc.) is refused unless the caller
explicitly sets `ConsentPolicy.allow_write=True` **and** adds the
specific action name to `granted_actions`. The consent gate runs
BEFORE the browser is even launched.

## Troubleshooting

Head to [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
