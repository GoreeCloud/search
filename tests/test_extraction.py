from goree_search.extraction import excludes_index, extract_document


def test_robots_exclusions():
    assert excludes_index(["index, follow"], "googlebot: noindex")
    assert excludes_index(["none"])
    assert not excludes_index(["index, follow"])


def test_extraction_returns_document():
    paragraphs = [
        "Public search engines collect links from eligible web pages and build a searchable index with useful titles and descriptions.",
        "A careful crawler checks a site's robots policy before fetching and follows appropriate limits for traffic, file sizes and timeouts.",
        "The indexing pipeline extracts readable article content and creates deterministic identifiers so repeated updates do not create duplicates.",
        "People can search this independent collection without depending on another company to provide the underlying search results.",
    ]
    html = (
        "<html><head><title>Goree</title></head><body><main><article>"
        + "".join("<p>" + paragraph + "</p>" for paragraph in paragraphs)
        + "</article></main></body></html>"
    )
    item = extract_document(html, "https://example.org/a", "Goree", "")
    assert item is not None
    assert item["title"] == "Goree"
    assert item["url"] == "https://example.org/a"
    assert len(item["content_hash"]) == 64


def test_short_page_not_indexed():
    assert extract_document("<html><p>Hello</p></html>", "https://example.org/") is None
