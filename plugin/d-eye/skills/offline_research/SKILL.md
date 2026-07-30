---
name: offline_research
description: >
  Zero-network research over the local evidence store: FTS5 keyword
  search (fast + deep modes) + extractive grounded answer built from
  real excerpts. Honours DEYE_OFFLINE=1.
tools: [query_evidence]
tags: [offline, local, grounded]
version: 1.0.0
---

# D-Eye Offline Research skill

**Trigger** when the user asks to research using local evidence only,
run without network, or answer from previously captured sources.

**How to use.** Invoke the in-process `offline_research` skill:

- `mode="fast"` — BM25 top-N.
- `mode="deep"` — wider recall + phrase-boost re-rank.
- `mode="answer"` — extractive grounded answer over the top hits.

**Safety rules.**

- Never touches the network.
- Never invents tokens — every answer is composed of verbatim excerpts
  with citations.
- Reports `offline_env=True` iff `DEYE_OFFLINE=1` is set.

**Example.**

- User: "Run a research task offline using local evidence."
- Action: `offline_research(query="continuous pricing", mode="answer")`.
- Expected: an answer object with `citations` referencing the local
  evidence rows and `confidence` ∈ [0, 1].
