---
name: repository_research
description: >
  Read-only public repository inspection. Returns metadata + recent
  commits + licence + primary language for a public repository, tagged
  as untrusted evidence with provenance.
tools: []
tags: [repository, code, public]
version: 1.0.0
---

# D-Eye Repository Research skill

**Trigger** when the user asks to look up a public code repository,
identify recent commits, check a repository's licence, or find where a
capability is implemented.

**How to use.** Invoke the in-process `repository_research` skill with
`repo="owner/name"` or a full repository URL.

**Safety rules.**

- Read-only. No commits, comments, or issue operations.
- SSRF-guarded HTTP; response body capped at 5 MiB.
- No credentials required for public repositories.

**Example.**

- User: "Search a repository and explain the relevant implementation."
- Action: `repository_research(repo="python/cpython")`.
- Expected: repo metadata + last 5 commits + licence, all as untrusted
  evidence with a `retrieved_at` timestamp.
