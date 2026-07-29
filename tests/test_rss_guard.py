import xml.etree.ElementTree as ET  # nosec B405 - test only

import pytest

from deye.connectors.rss import _safe_fromstring


def test_doctype_is_rejected():
    billion_laughs = (
        b'<?xml version="1.0"?>\n'
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;">]>\n'
        b'<rss><item><title>&lol2;</title></item></rss>'
    )
    with pytest.raises(ET.ParseError):
        _safe_fromstring(billion_laughs)


def test_normal_feed_still_parses():
    feed = b"<rss><channel><item><title>Hello</title></item></channel></rss>"
    root = _safe_fromstring(feed)
    titles = [n.text for n in root.iter() if n.tag == "title"]
    assert titles == ["Hello"]


def test_doctype_hidden_behind_large_comment_is_rejected():
    # Regression: scanning only the first 8 KiB let an attacker push the DOCTYPE
    # past the window with a big leading comment. The prolog scanner skips the
    # comment (any length) and still catches the declaration.
    hidden = (
        b"<!-- " + b"A" * 9000 + b" -->"
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        b"<rss><item><title>&lol;</title></item></rss>"
    )
    with pytest.raises(ET.ParseError):
        _safe_fromstring(hidden)


def test_doctype_text_inside_cdata_is_not_a_false_positive():
    # A feed whose content legitimately contains the literal "<!DOCTYPE html>"
    # inside CDATA must still parse -- it is element content, not a declaration.
    feed = (
        b"<rss><channel><item><description>"
        b"<![CDATA[<!DOCTYPE html><p>hi</p>]]>"
        b"</description></item></channel></rss>"
    )
    root = _safe_fromstring(feed)
    assert root.tag == "rss"
