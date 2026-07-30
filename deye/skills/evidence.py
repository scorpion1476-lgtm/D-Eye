"""D-Eye Evidence Skill.

Records sources, tracks changes, detects duplicates, links claims to
evidence, and supports export + per-tenant deletion.
"""
from __future__ import annotations

from typing import Any

from deye.core.config import Config
from deye.core.evidence import EvidenceStore
from deye.core.graph import EvidenceGraph
from deye.core.quality import (
    change_monitor,
    deduplicate,
    quality_report,
)


def run(*, action: str,
        query: str = "",
        tenant: str | None = None,
        urls: list[str] | None = None,
        confirm_delete: bool = False,
        config: Config | None = None) -> dict:
    """Actions:
        - "query"        : return rows matching *query* under the tenant scope.
        - "graph"        : build the claims+entities graph over the tenant's rows.
        - "quality"      : score sources + surface dedup clusters.
        - "changes"      : batch-check the listed urls for content-change since last snapshot.
        - "export"       : return the full JSON bundle for a tenant.
        - "delete"       : delete a tenant's rows (requires confirm_delete=True, tenant != 'default').
        - "stats"        : {packets, sources, distinct_urls} scoped to tenant if given.
    """
    config = config or Config.load()
    store = EvidenceStore(config.evidence_db)
    if action == "query":
        rows = store.query(query, tenant=tenant, limit=50)
        return {"action": action, "rows": rows, "count": len(rows)}
    if action == "graph":
        rows = store.query(query or "", tenant=tenant, limit=200)
        g = EvidenceGraph.from_sources(rows)
        return {"action": action, "graph": g.to_dict()}
    if action == "quality":
        rows = store.query(query or "", tenant=tenant, limit=200)
        report = quality_report(rows)
        return {"action": action, "report": report}
    if action == "changes":
        results = change_monitor(store, urls or [])
        return {"action": action,
                "results": [r.to_dict() for r in results]}
    if action == "export":
        if tenant is None:
            return {"action": action, "ok": False,
                    "reason": "tenant is required for export"}
        return {"action": action, "ok": True,
                "export": store.export_tenant(tenant)}
    if action == "delete":
        if tenant is None:
            return {"action": action, "ok": False,
                    "reason": "tenant is required for delete"}
        return {"action": action,
                "result": store.delete_tenant(tenant, confirm=confirm_delete)}
    if action == "stats":
        return {"action": action, "stats": store.stats(tenant=tenant)}
    raise ValueError(f"unknown evidence action: {action}")


from deye.skills import Skill  # noqa: E402

SKILL = Skill(
    name="evidence",
    version="1.0.0",
    description=("Record + query + dedupe + change-monitor + export + delete "
                 "persistent evidence; per-tenant scoping enforced at the SQL layer."),
    run=run,
    requires_consent=False,  # 'delete' still requires confirm_delete=True
    tags=("evidence", "quality", "graph", "lifecycle"),
)
