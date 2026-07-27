from deye.core.provenance import Envelope, Source, ResearchPacket, content_hash

def test_envelope_and_packet_markdown():
    env = Envelope(content="hello world", source=Source(url="https://ex.com", connector="web_fetch", title="T"))
    env.add_evidence("hello")
    assert env.evidence[0].quote_hash == content_hash("hello")
    p = ResearchPacket(query="q"); p.envelopes.append(env)
    md = p.to_markdown()
    assert "https://ex.com" in md and "sha256:" in md and "untrusted evidence" in md
    assert "https://ex.com" in p.to_json()

def test_content_hash_stable():
    assert content_hash("abc") == content_hash("abc")
