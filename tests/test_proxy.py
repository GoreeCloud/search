import socket

import pytest

from goree_search.egress_proxy import (
    connect_host, local_https_proxy, select_global_address
)


@pytest.mark.parametrize("target", [
    "127.0.0.1:443", "localhost:443", "other.org:443",
    "example.org:80", "example.org:8443", "user@example.org:443",
    "example.org:443/robots.txt", "[::1]:443",
])
def test_reject_invalid_connect_target(target):
    with pytest.raises(ValueError):
        connect_host(target, {"example.org"})


def test_accept_only_explicit_hostname():
    assert connect_host("example.org:443", {"example.org"}) == "example.org"


def test_dns_answers_must_all_be_global():
    public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))
    private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
    assert select_global_address([public])[0] == "93.184.215.14"
    with pytest.raises(ValueError):
        select_global_address([public, private])
    with pytest.raises(ValueError):
        select_global_address([])


def test_proxy_refuses_non_connect_requests_without_network():
    with local_https_proxy({"example.org"}) as url:
        host, port = url.split("//", 1)[1].split(":")
        with socket.create_connection((host, int(port)), timeout=5) as sock:
            sock.sendall(b"GET http://example.org/ HTTP/1.1\r\nHost: example.org\r\n\r\n")
            reply = sock.recv(256)
    assert b"403 Forbidden" in reply
