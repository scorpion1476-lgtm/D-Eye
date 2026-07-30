---
name: evidence
description: >
  Interact with the persistent D-Eye evidence store: query captured
  sources, dedupe, check for source changes, export or delete a tenant's
  data. All operations are scoped by tenant at the SQL layer.
tools: [query_evidence]
tags: [evidence, export, delete, quality, graph]
version: 1.0.0
---

# D-Eye Evidence skill

**Trigger** when the user asks to inspect prior research, compare
sources, check for updates on a URL, export their data, or delete a
tenant's stored evidence.

**How to use.** For simple lookups, call `query_evidence(query="...")`.
For richer analysis (graph view, quality scoring, contradiction
detection, change monitoring) use `deye evidence --graph|--quality|
--changes ...` on the CLI, or invoke the `evidence` skill in-process
via `deye.skills.invoke("evidence", action="graph|quality|...")`.

**Safety rules.**

- `delete` requires `confirm_delete=True` AND `tenant != 'default'`.
  The default tenant is the owner scope and cannot be deleted via a
  tenant-scoped call.
- `export` returns a JSON bundle scoped strictly to the requested tenant.
- Contradiction confidences are heuristic - treat as leads for review.

**Example.**

- User: "Export everything captured under tenant 'acme' and then delete it."
- Action: `evidence(action="export", tenant="acme")` then
  `evidence(action="delete", tenant="acme", confirm_delete=True)`.
- Expected: JSON bundle returned first; deletion report with
  `removed_sources` + `removed_packets` returned second; owner-scope
  rows unchanged.
