from unittest.mock import patch

import pytest

from goree_search.security import hostname, normalize_url, public_host


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://127.0.0.1/", "http://[::1]/",
    "http://localhost/", "http://admin:pw@public.org/",
    "http://public.org:8080/", "http://private.local/",
    "http://x.invalid/", "https://public.org:9999/",
])
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_normalization_and_fragment():
    assert normalize_url("HTTPS://Example.ORG/path?a=1#part") == "https://example.org/path?a=1"
    assert hostname("https://EXAMPLE.org") == "example.org"


def test_host_allowlist_and_private_dns():
    with patch("socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("10.0.0.5", 80))
    ]):
        with pytest.raises(ValueError):
            public_host("http://example.org/", allowed_hosts={"example.org"})
    with pytest.raises(ValueError):
        public_host("https://other.org/", allowed_hosts={"example.org"}, resolve=False)


def test_allow_public_dns():
    with patch("socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("93.184.215.14", 443))
    ]):
        assert public_host("https://example.org/", allowed_hosts={"example.org"}) == "https://example.org/"
