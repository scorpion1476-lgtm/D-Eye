from deye.extract import html_to_text, extract_title

def test_strips_script_and_tags():
    html = "<title>Hi</title><body><script>evil()</script><p>Hello</p><p>World</p></body>"
    assert extract_title(html) == "Hi"
    t = html_to_text(html)
    assert "evil" not in t and "Hello" in t and "World" in t
