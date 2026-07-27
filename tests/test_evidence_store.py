import pathlib
from deye.core.evidence import EvidenceStore
from deye.core.provenance import Envelope, Source, ResearchPacket

def _packet():
    p = ResearchPacket(query="airline revenue management")
    p.envelopes.append(Envelope(content="continuous pricing overview",
        source=Source(url="https://ex.com/a", connector="web_fetch", title="Pricing")))
    p.envelopes.append(Envelope(content="NDC distribution",
        source=Source(url="https://ex.com/b", connector="web_fetch", title="NDC")))
    return p

def test_record_and_query(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    pid = store.record_packet(_packet())
    assert pid == 1
    hits = store.query("pricing")
    assert any("ex.com/a" in h["url"] for h in hits)
    assert store.stats()["sources"] == 2
    assert store.stats()["distinct_urls"] == 2

def test_change_detection(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    p1 = ResearchPacket(query="q"); p1.envelopes.append(
        Envelope(content="v1", source=Source(url="https://ex.com/x", connector="web_fetch")))
    p2 = ResearchPacket(query="q"); p2.envelopes.append(
        Envelope(content="v2-different", source=Source(url="https://ex.com/x", connector="web_fetch")))
    store.record_packet(p1); store.record_packet(p2)
    ch = store.changed_since("https://ex.com/x")
    assert ch and ch["changed"] is True
