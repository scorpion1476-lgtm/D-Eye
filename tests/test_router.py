from deye.core.registry import Registry, ConnectorManifest, HealthReport
from deye.core.router import Router, RouterError
from deye.core.provenance import Envelope, Source

class Flaky:
    name="flaky"; capability="search"; is_write=False
    def health(self): return HealthReport("flaky","ok")
    def run(self, request): raise RuntimeError("boom")

class Good:
    name="good"; capability="search"; is_write=False
    def health(self): return HealthReport("good","ok")
    def run(self, request):
        return Envelope(content="ok", source=Source(url="https://x", connector="good"))

def _reg():
    r = Registry()
    r.register(ConnectorManifest("flaky","search","MIT",preference=10,factory=lambda:Flaky()))
    r.register(ConnectorManifest("good","search","MIT",preference=20,factory=lambda:Good()))
    return r

def test_falls_back_to_healthy_backend():
    env = Router(_reg()).route("search", {"query":"hi"})
    assert env.content == "ok"

def test_no_connector_raises():
    import pytest
    with pytest.raises(RouterError):
        Router(Registry()).route("nope", {})

def test_write_blocked_by_default():
    import pytest
    r = Registry()
    class W:
        name="w"; capability="act"; is_write=True
        def health(self): return HealthReport("w","ok")
        def run(self, request): return Envelope("x", Source("u","w"))
    r.register(ConnectorManifest("w","act","MIT",is_write=True,factory=lambda:W()))
    with pytest.raises(RouterError):
        Router(r).route("act", {})
