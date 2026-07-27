import pytest
from deye.core.policy import evaluate_url, resolve_public_ips, ConsentPolicy

BLOCKED = [
    "http://127.0.0.1/admin",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://172.16.5.5/",
    "http://[::1]/",
    "http://0.0.0.0/",
    "http://metadata.google.internal/",
    "file:///etc/passwd",                          # scheme not allowed
    "ftp://example.com/x",                         # scheme not allowed
    "http://user:pass@example.com/",               # userinfo smuggling
    "http://example.com@127.0.0.1/",               # lookalike/userinfo
    "gopher://127.0.0.1:70/",
]

@pytest.mark.parametrize("url", BLOCKED)
def test_dangerous_urls_blocked(url):
    assert evaluate_url(url).allowed is False, f"should block {url}"

def test_ipv4_mapped_ipv6_private_blocked():
    assert evaluate_url("http://[::ffff:127.0.0.1]/").allowed is False

def test_bare_private_ip_literal_blocked():
    ips, err = resolve_public_ips("10.1.2.3")
    assert ips == [] and "non-public" in err

def test_allowlist_enforced():
    # A public host not on the allowlist is rejected even though it is routable.
    d = evaluate_url("https://example.com/", allowed_domains=["github.com"])
    assert d.allowed is False and "allowlist" in d.reason

def test_consent_read_default():
    c = ConsentPolicy()
    assert c.permits("web_fetch", is_write=False).allowed is True
    assert c.permits("browser.click", is_write=True).allowed is False
    c2 = ConsentPolicy(allow_write=True, granted_actions={"browser.click"})
    assert c2.permits("browser.click", is_write=True).allowed is True
