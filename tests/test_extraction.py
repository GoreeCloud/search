from goree_search.extraction import excludes_index, extract_document


def test_robots_exclusions():
    assert excludes_index(["index, follow"], "googlebot: noindex")
    assert excludes_index(["none"])
    assert not excludes_index(["index, follow"])


def test_extraction_returns_document():
    html = "<html><title>Goree</title><body><article><p>" + (
        "Public web search is useful when we control how content is indexed. " * 6
    ) + "</p></article></body></html>"
    item = extract_document(html, "https://example.org/a", "Goree", "")
    assert item is not None
    assert item["title"] == "Goree"
    assert item["url"] == "https://example.org/a"
    assert len(item["content_hash"]) == 64


def test_short_page_not_indexed():
    assert extract_document("<html><p>Hello</p></html>", "https://example.org/") is None
