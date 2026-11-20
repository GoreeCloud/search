"""Local XML and compressed sitemap fixtures; no HTTP or DNS requests."""
from gzip import compress

import pytest

from goree_search.sitemaps import read_sitemap_file

SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    '<url><loc>https://example.org/a</loc></url>'
    '<url><loc>https://example.org/b</loc></url>'
    '<url><loc>https://example.org/a</loc></url>'
    '</urlset>'
)


def test_namespaced_urlset_and_dedup(tmp_path):
    path = tmp_path / "sitemap.xml"
    path.write_text(SITEMAP, encoding="utf-8")
    assert read_sitemap_file(path, host="example.org") == [
        "https://example.org/a", "https://example.org/b"
    ]


def test_gzip_supported_with_both_size_limits(tmp_path):
    path = tmp_path / "sitemap.xml.gz"
    path.write_bytes(compress(SITEMAP.encode()))
    assert len(read_sitemap_file(path, host="example.org")) == 2
    with pytest.raises(ValueError):
        read_sitemap_file(path, host="example.org", max_bytes=50)


@pytest.mark.parametrize("markup", [
    "<sitemapindex><sitemap><loc>https://example.org/a</loc></sitemap></sitemapindex>",
    "<urlset><url><loc>http://example.org/unsafe</loc></url></urlset>",
    "<urlset><url><loc>https://other.org/</loc></url></urlset>",
    "<urlset><url><loc>http://127.0.0.1/</loc></url></urlset>",
    '<!DOCTYPE a [ <!ENTITY bomb "BOMB"> ]><urlset><url><loc>&bomb;</loc></url></urlset>',
    "<urlset><url>",
])
def test_reject_untrusted_sources_and_structures(tmp_path, markup):
    path = tmp_path / "bad.xml"
    path.write_text(markup, encoding="utf-8")
    with pytest.raises(ValueError):
        read_sitemap_file(path, host="example.org")


def test_url_limit_is_enforced(tmp_path):
    path = tmp_path / "sitemap.xml"
    path.write_text(SITEMAP, encoding="utf-8")
    with pytest.raises(ValueError, match="URL count"):
        read_sitemap_file(path, host="example.org", max_urls=1)


def test_reject_symlink_and_oversize(tmp_path):
    path = tmp_path / "real.xml"
    path.write_text(SITEMAP, encoding="utf-8")
    link = tmp_path / "link.xml"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        read_sitemap_file(link, host="example.org")
    with pytest.raises(ValueError):
        read_sitemap_file(path, host="example.org", max_bytes=10)
