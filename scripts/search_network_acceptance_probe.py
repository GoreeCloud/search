#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only, fail-closed Search public/private HTTPS boundary acceptance.

Run this manually from a NetBird-connected client with explicit, previously
verified IP addresses. The probe never resolves a host, follows a redirect,
submits a query, contacts a search provider, or changes live configuration.
It proves only the specific routes/addresses checked, not firewall policy,
deployment provenance, or release readiness by itself.
"""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import socket
import ssl


PRIVATE_HOST = 'search-dev.goreecloud.com'
PUBLIC_HOST = 'search.goreecloud.com'
NETBIRD_RANGE = ipaddress.ip_network('100.64.0.0/10')


def _validated_address(raw: str, *, role: str) -> str:
    """Constrain all explicit test destinations to their approved IP roles."""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise ValueError('Invalid literal IP address') from exc
    if role == 'netbird':
        valid = address.version == 4 and address in NETBIRD_RANGE
    elif role == 'public_ipv4':
        valid = address.version == 4 and address.is_global
    elif role == 'public_ipv6':
        valid = address.version == 6 and address.is_global
    else:
        raise ValueError('Invalid network probe role')
    if not valid:
        raise ValueError('Address does not match requested network role')
    return str(address)


def _probe_https(host: str, address: str, path: str, timeout: float) -> tuple[int | None, str]:
    """Issue one fixed-path verified-TLS GET with target IP and Host/SNI pinned.

    Errors are reduced to fixed classes; no raw exception, IP, response headers,
    body, query, cookies, or credentials may enter the output report.
    """
    try:
        with socket.create_connection((address, 443), timeout=timeout) as client:
            client.settimeout(timeout)
            with ssl.create_default_context().wrap_socket(client, server_hostname=host) as tls:
                tls.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}\r\n'
                             'User-Agent: GoreeCloud-Search-ReadOnly-Acceptance/1\r\n'
                             'Connection: close\r\n\r\n').encode('ascii'))
                response = http.client.HTTPResponse(tls, method='GET')
                response.begin()
                status = response.status
                response.close()
                return status, 'verified_tls'
    except ssl.SSLError:
        return None, 'tls_failed'
    except (TimeoutError, socket.timeout):
        return None, 'timeout'
    except (OSError, http.client.HTTPException, ValueError):
        return None, 'transport_failed'


def evaluate(private_ip: str, public_ipv4: str, public_ipv6: str | None,
             *, timeout: float = 5.0) -> dict[str, object]:
    """Collect minimal isolated evidence; all required boundaries must pass."""
    if type(timeout) not in (int, float) or not 1 <= timeout <= 12:
        raise ValueError('Timeout must be 1 to 12 seconds')
    private = _validated_address(private_ip, role='netbird')
    ipv4 = _validated_address(public_ipv4, role='public_ipv4')
    ipv6 = (_validated_address(public_ipv6, role='public_ipv6')
            if public_ipv6 is not None else None)

    observed = [
        ('private_netbird', PRIVATE_HOST, private, '/readyz', 200),
        ('private_direct_ipv4_denial', PRIVATE_HOST, ipv4, '/readyz', 403),
        ('public_https_ipv4', PUBLIC_HOST, ipv4, '/', 200),
    ]
    if ipv6 is not None:
        observed.append(('private_direct_ipv6_denial', PRIVATE_HOST, ipv6, '/readyz', 403))

    probes: dict[str, dict[str, object]] = {}
    for name, host, ip, path, expected in observed:
        status, transport = _probe_https(host, ip, path, timeout)
        probes[name] = {
            'status': 'pass' if status == expected and transport == 'verified_tls' else 'blocked',
            'http_status': status,
            'tls': transport,
        }

    # Absence of an IPv6 check cannot establish an all-path network boundary,
    # even if all three IPv4 checks pass. Never hide missing test coverage.
    if ipv6 is None:
        probes['private_direct_ipv6_denial'] = {
            'status': 'not_tested', 'http_status': None, 'tls': 'not_tested',
        }
    passed = all(item['status'] == 'pass' for item in probes.values())
    return {
        'check': 'search_public_private_https_boundaries',
        'status': 'pass_sampled_paths_only' if passed else 'blocked_do_not_release',
        'runtime_probe': True,
        'no_search_provider_queries': True,
        'ipv6_negative_tested': ipv6 is not None,
        'probes': probes,
        'production_release_authorized': False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Read-only Search NetBird/public HTTPS acceptance')
    p.add_argument('--private-netbird-ip', required=True,
                   help='Verified NetBird IPv4 literal for Search Development')
    p.add_argument('--public-ipv4', required=True,
                   help='Verified public VPS IPv4 literal (forced destination, not DNS)')
    p.add_argument('--public-ipv6',
                   help='Verified public VPS IPv6 literal; omitted means incomplete acceptance')
    p.add_argument('--timeout', type=float, default=5.0)
    args = p.parse_args(argv)
    try:
        report = evaluate(args.private_netbird_ip, args.public_ipv4, args.public_ipv6,
                          timeout=args.timeout)
    except ValueError:
        report = {
            'check': 'search_public_private_https_boundaries',
            'status': 'blocked_invalid_probe_configuration',
            'runtime_probe': False,
            'production_release_authorized': False,
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'pass_sampled_paths_only' else 2


if __name__ == '__main__':
    raise SystemExit(main())
