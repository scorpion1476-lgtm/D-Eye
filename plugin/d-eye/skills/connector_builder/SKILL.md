---
name: connector_builder
description: >
  Scaffold a new D-Eye connector against the connector contract:
  SSRF-hardened networking, health check, untrusted Envelope, registry
  manifest, rate-limit + size + decompression guarantees.
tools: []
tags: [scaffold, connector, developer]
version: 1.0.0
---

# D-Eye Connector Builder skill

**Trigger** when the user asks to create a new connector, extend
D-Eye with a new source, or scaffold connector boilerplate.

**How to use.** Invoke the in-process `connector_builder` skill with:

- `name`         - snake_case module name (validated).
- `capability`   - one of `search`, `fetch`, `feed`, `repo.inspect`, `extract`.
- `description`  - one-line docstring.
- `license`      - SPDX identifier for the target-service licence.
- `out_path`     - optional path; if omitted, module text is returned.

**Safety rules.**

- Generated code routes through `safe_get` - never raw `urllib`.
- Every generated connector returns `trust.untrusted=True`.
- The user must still: customise the `run()` method, add a test with a
  monkeypatched `safe_get`, and register the manifest in
  `deye/app.py::build_registry`.

**Example.**

- User: "Scaffold a new fetch connector called 'my_source'."
- Action: `connector_builder(name="my_source", capability="fetch")`.
- Expected: a Python module text ready to drop into
  `deye/connectors/my_source.py` + a `next_steps` list.
