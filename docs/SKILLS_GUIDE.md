# D-Eye - Skills Guide

D-Eye skills are named orchestration recipes composed from the well-
tested D-Eye primitives (router, evidence store, quality, research,
browser, backend). Every skill:

- has a `SKILL.md` under `plugin/d-eye/skills/<name>/SKILL.md` (plugin-
  facing metadata + safety framing);
- has a Python module `deye/skills/<name>.py` (executable code);
- is registered in `deye.skills.REGISTRY`;
- has one or more acceptance tests in `tests/test_skills.py`.

## Invoking a skill in-process

```python
from deye.skills import invoke, list_skills

for s in list_skills():
    print(s["name"], s["version"], "-", s["description"])

result = invoke("research", query="continuous pricing", max_sources=3)
```

`invoke("<name>", **kwargs)` - the skill name is positional-only, so
kwargs like `name="my_source"` (used by `connector_builder`) never
collide with the lookup key.

## The 8 skills

### `research`

Search → fetch → cite → persist → grounded extractive answer.

```python
r = invoke("research",
           query="continuous pricing airline revenue management",
           max_sources=3)
r["source_count"]    # 3
r["answer"]["text"]  # grounded extractive answer
r["packet"]          # serialised ResearchPacket
```

### `evidence`

Query, dedupe, change-check, export, delete captured evidence.

```python
invoke("evidence", action="stats", tenant="acme")
invoke("evidence", action="query", query="pricing", tenant="acme")
invoke("evidence", action="export", tenant="acme")
invoke("evidence", action="delete", tenant="acme", confirm_delete=True)
```

### `web_discovery`

Routed public-web discovery.

```python
invoke("web_discovery", capability="search", query="topic")
invoke("web_discovery", capability="fetch", url="https://example.org")
invoke("web_discovery", capability="feed", url="https://example.org/feed.xml")
```

### `browser_research`

Consent-gated isolated browser (optional `[browser]` extras).

```python
from deye.core.policy import ConsentPolicy
invoke("browser_research", action="status")
invoke("browser_research", action="render_html", url="https://example.org")

consent = ConsentPolicy(allow_write=True, granted_actions={"browser.click"})
invoke("browser_research", action="click",
       url="https://example.org", selector="button.submit", consent=consent)
```

### `repository_research`

Read-only public repo lookup.

```python
invoke("repository_research", repo="python/cpython")
```

### `source_quality`

Explainable quality scores + polarity/numeric contradiction detection.

```python
rows = invoke("evidence", action="query", query="topic")["rows"]
report = invoke("source_quality", rows=rows, min_confidence=0.5)
```

### `offline_research`

Zero-network research over local evidence.

```python
invoke("offline_research", query="fts5", mode="fast")
invoke("offline_research", query="fts5 tokenizer", mode="answer")
```

Honours `DEYE_OFFLINE=1`.

### `connector_builder`

Scaffold a new connector.

```python
r = invoke("connector_builder",
           name="my_source", capability="fetch",
           description="Public JSON connector.")
open("deye/connectors/my_source.py", "w").write(r["module_text"])
```

## Writing your own skill

1. Create `deye/skills/<name>.py` with a top-level `SKILL` object built
   via the `Skill` dataclass (name, version, description, run callable,
   requires_consent, tags).
2. Add an import + a REGISTRY entry to `deye/skills/__init__.py`.
3. Add `plugin/d-eye/skills/<name>/SKILL.md` with YAML frontmatter
   (name, description, version, tools, tags).
4. Add an acceptance test in `tests/test_skills.py` that invokes the
   skill with representative kwargs and asserts the output shape.
5. Run `pytest tests/test_skills.py`.

The registry test enforces the name-consistency invariant: every
registered skill must have a matching `SKILL.md`, and vice versa.
