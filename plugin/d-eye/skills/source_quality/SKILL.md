---
name: source_quality
description: >
  Deterministic source-quality scoring + candidate contradiction
  detection over a set of source rows. Every score exposes its factor
  breakdown so a reviewer can adjudicate.
tools: []
tags: [quality, contradiction, explainable]
version: 1.0.0
---

# D-Eye Source Quality skill

**Trigger** when the user asks to compare sources, judge source
quality, or identify disagreements between sources.

**How to use.** Invoke the in-process `source_quality` skill with a
list of source rows (URL + title + excerpt + content_hash) and an
optional `min_confidence` floor for contradiction findings.

**Safety rules.**

- Confidence scores are heuristic (polarity + numeric), NOT learned NLI.
  Present them as leads for human review, never as facts.
- Every score exposes its `factors` and `reasons` under
  `quality.scores_by_url`.

**Example.**

- User: "Compare two public technical sources and identify
  disagreements."
- Action: query the evidence store for the two URLs, pass them to
  `source_quality(rows=[...])`.
- Expected: per-URL quality scores with factor breakdown + any
  polarity/numeric contradictions above the confidence floor.
