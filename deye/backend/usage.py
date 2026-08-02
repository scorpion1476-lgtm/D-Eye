"""Usage, cost, and rate reporting for connectors and optional adapters.

D-Eye's FOSS connectors are free (no external cost, no quota). Optional paid
adapters (a hosted search/LLM/vector backend behind an extras-only install) DO
have a cost and a rate limit, so operators need to see how often each adapter
was called and what it is estimated to cost.

`UsageMeter` records one line per connector invocation - connector name, its
manifest cost class, whether it succeeded, and the response size - and can
aggregate those into a per-adapter report with:

  * call counts (total / ok / error),
  * an estimated cost (calls x the per-call price for that adapter's cost
    class; free FOSS connectors are always 0),
  * a call rate (calls per minute over the observed window).

It is off by default (the Router only meters when handed a meter) and persists
to a plain JSONL file under DEYE_HOME so `deye usage` can report across runs.
Nothing here contacts a paid service; it only accounts for calls D-Eye made.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Default per-call price by manifest cost class, in an abstract unit (operators
# override with their real numbers). FOSS/local connectors are free.
DEFAULT_PRICES: dict[str, float] = {"free": 0.0, "metered": 0.001, "paid": 0.01}


@dataclass
class UsageRecord:
    connector: str
    capability: str
    cost_class: str
    ok: bool
    nbytes: int
    ts: float  # epoch seconds; supplied by the caller (never wall-clock here)

    def to_dict(self) -> dict:
        return {"connector": self.connector, "capability": self.capability,
                "cost_class": self.cost_class, "ok": self.ok,
                "nbytes": self.nbytes, "ts": self.ts}


@dataclass
class UsageMeter:
    """In-memory usage recorder with optional JSONL persistence."""

    records: list[UsageRecord] = field(default_factory=list)
    log_path: Path | None = None

    def record(self, connector: str, *, capability: str = "", cost_class: str = "free",
               ok: bool = True, nbytes: int = 0, ts: float = 0.0) -> UsageRecord:
        rec = UsageRecord(connector=connector, capability=capability,
                          cost_class=cost_class, ok=ok, nbytes=nbytes, ts=ts)
        self.records.append(rec)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec.to_dict()) + "\n")
        return rec

    @classmethod
    def from_log(cls, path: Path) -> "UsageMeter":
        m = cls(log_path=Path(path))
        p = Path(path)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                m.records.append(UsageRecord(
                    connector=d["connector"], capability=d.get("capability", ""),
                    cost_class=d.get("cost_class", "free"), ok=bool(d.get("ok", True)),
                    nbytes=int(d.get("nbytes", 0)), ts=float(d.get("ts", 0.0))))
        return m

    def report(self, *, prices: dict[str, float] | None = None) -> dict:
        prices = prices or DEFAULT_PRICES
        per: dict[str, dict] = {}
        for r in self.records:
            agg = per.setdefault(r.connector, {
                "connector": r.connector, "cost_class": r.cost_class,
                "calls": 0, "ok": 0, "errors": 0, "bytes": 0,
                "first_ts": r.ts, "last_ts": r.ts})
            agg["calls"] += 1
            agg["ok"] += 1 if r.ok else 0
            agg["errors"] += 0 if r.ok else 1
            agg["bytes"] += r.nbytes
            agg["first_ts"] = min(agg["first_ts"], r.ts)
            agg["last_ts"] = max(agg["last_ts"], r.ts)
        adapters = []
        total_cost = 0.0
        for agg in per.values():
            price = prices.get(agg["cost_class"], 0.0)
            est = round(agg["calls"] * price, 6)
            total_cost += est
            span_min = max((agg["last_ts"] - agg["first_ts"]) / 60.0, 0.0)
            rate = round(agg["calls"] / span_min, 4) if span_min > 0 else None
            adapters.append({**agg, "est_cost": est,
                             "calls_per_min": rate})
        adapters.sort(key=lambda a: (-a["est_cost"], a["connector"]))
        return {"adapters": adapters,
                "total_calls": sum(a["calls"] for a in adapters),
                "total_est_cost": round(total_cost, 6),
                "paid_adapters": [a["connector"] for a in adapters
                                  if a["cost_class"] != "free"]}
