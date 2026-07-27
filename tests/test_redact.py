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
