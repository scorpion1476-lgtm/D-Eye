# D-Eye validation & test report (v0.2.0)

_Generated 2026-07-27T17:02:15Z. Independently executed in an isolated venv._

## Environment (actual)
- Python: Python 3.12.3
- pytest: pytest 9.1.1
- mcp SDK: installed (streamable-http verified)
- OS: Linux 6.18.5 x86_64

## Test suite (actually executed)
```
$ python -m pytest -q
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
51 passed, 1 warning in 0.69s
```

Tests discovered: 51 (with the optional mcp/starlette/uvicorn extras installed). Result: all passed. Without those extras the 4 remote-auth tests skip cleanly (47 passed, 1 skipped) -- they are the only tests needing optional dependencies.

## Live checks actually performed during remediation
- `py_compile` across all modules: OK.
- CLI console script on PATH; `deye --version` -> 0.2.0; runs from arbitrary CWD (/tmp).
- MCP self-test (SDK-free): OK. MCP tool dispatch: OK.
- Connection-pinned HTTPS fetch of https://example.com: 200, cert validated.
- SSRF: `fetch http://169.254.169.254/...` -> blocked ('non-public IP'), exit 1.
- Evidence persistence: research wrote evidence.db; `deye evidence` queried it in a SEPARATE process.
- Remote HTTP MCP (live uvicorn): refuses start w/o token; /healthz=200; /mcp no-token=401; wrong-token=401.

## NOT verifiable in this environment (stated honestly)
- Docker image BUILD/RUN: no Docker daemon in this sandbox. Dockerfile/compose provided and lint-reviewed, not built here.
- Live end-to-end handshake from the actual Claude web client to the remote service (requires a hosted deployment).
- macOS/Windows path handling: code uses pathlib + os-agnostic APIs; only Linux executed here. (v0.2.0-validated: init-claude path building exercised on macOS via Desktop Commander during install.)
