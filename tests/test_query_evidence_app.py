import os, pathlib
from deye.core.config import Config
from deye.core.evidence import EvidenceStore
from deye.core.provenance import Envelope, Source, ResearchPacket
from deye.app import query_evidence

def test_query_evidence_reads_store(tmp_path, monkeypatch):
    cfg = Config(home=tmp_path)
    p = ResearchPacket(query="crew optimization")
    p.envelopes.append(Envelope(content="IROPS recovery text",
        source=Source(url="https://ex.com/irops", connector="web_fetch", title="IROPS")))
    EvidenceStore(cfg.evidence_db).record_packet(p)
    out = query_evidence("IROPS", config=cfg)
    assert out["results"] and "irops" in out["results"][0]["url"]
    assert out["stats"]["sources"] >= 1
