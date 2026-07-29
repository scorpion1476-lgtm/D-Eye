from deye.core.redact import redact, redact_mapping

def test_bearer_and_user_token_redacted():
    s = "Authorization: Bearer sk_user_ABCDEFGHIJKLMNOP1234"
    out = redact(s)
    assert "sk_user_" not in out and "[REDACTED]" in out

def test_various_keys():
    assert "sk-ant-" not in redact("key sk-ant-abc123abc123abc123abc123")
    assert "AKIA" not in redact("AKIAABCDEFGHIJKLMNOP")
    assert "ghp_" not in redact("token ghp_abcdefghijklmnopqrstuvwx0123")

def test_mapping():
    m = redact_mapping({"Authorization": "Bearer sk_user_ZZZZZZZZZZZZZZZZ99", "x": "ok"})
    assert "[REDACTED]" in m["Authorization"] and m["x"] == "ok"


def test_mapping_redacts_non_bearer_auth_by_key():
    # Regression: Basic/Token/Digest values have no anchor the patterns match,
    # so value-scanning alone leaked them. Key-based redaction must catch them.
    m = redact_mapping({
        "Authorization": "Basic dXNlcjpwYXNzd29yZA==",
        "Proxy-Authorization": "Token 0123456789abcdef0123",
        "Cookie": "session=deadbeefdeadbeefdeadbeef",
        "X-Api-Key": "abcd1234abcd1234",
        "Accept": "application/json",
    })
    assert m["Authorization"] == "[REDACTED]"
    assert m["Proxy-Authorization"] == "[REDACTED]"
    assert "deadbeef" not in m["Cookie"]
    assert "abcd1234" not in m["X-Api-Key"]
    assert m["Accept"] == "application/json"


def test_inline_authorization_captures_whole_credential():
    # The credential after the scheme word must not survive.
    out = redact("Authorization: Token 0123456789abcdef0123")
    assert "0123456789abcdef0123" not in out and "[REDACTED]" in out
    out2 = redact("authorization=Basic dXNlcjpwYXNzd29yZA==")
    assert "dXNlcjpwYXNzd29yZA" not in out2
