#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Conservative, offline verification of Search's private Development vhost.

This is a *source/configuration* guard, not a network test or a public release
permit. It intentionally accepts only the small Caddy directive subset used by
GoreeCloud Search's private Development vhost, and fails closed on unfamiliar
directives. The caller must still validate Caddy with its actual binary and
prove the NetBird/public-client behavior against the running deployment.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PRIVATE_HOST = "search-dev.goreecloud.com"
PUBLIC_HOST = "search.goreecloud.com"
NETBIRD = "@netbird_client remote_ip 100.64.0.0/10"
DENY = 'respond "Forbidden" 403'
_ENV = re.compile(r"\{\$[A-Z][A-Z0-9_]*\}")
_HOST_TOKEN_BOUNDARY = r"(?<![A-Za-z0-9.-]){}(?![A-Za-z0-9.-])"
_PROXY = re.compile(r"^reverse_proxy\s+(.+)$", re.IGNORECASE)
# A wildcard vhost or a hostless listener can match Search Development
# without ever spelling out its exact hostname. Such site addresses need a
# separate, adapted-Caddyfile and live-routing review before cutover.
_WILDCARD_SEARCH_HOST = re.compile(
    r"(?<![a-z0-9.-])(?:https?://)?\*\.goreecloud\.com(?=\s|[:,{]|$)",
    re.IGNORECASE,
)
_HOSTLESS_LISTENER = re.compile(
    r"^(?:(?:https?://)?:(?:80|443)|https?://|\*|(?:0\.0\.0\.0|\[::\]):(?:80|443))\s*\{$",
    re.IGNORECASE,
)
# Restrict private backend identities even when they are not suffixed with
# `gateway`: an ingress/container DNS alias is still the same release domain.
_PRIVATE_BACKENDS = re.compile(
    r"\bgoreecloud-search-(?:gateway|(?:free|dev|development|private|staging|test|preview)"
    r"(?:-[a-z0-9]+)*)(?::[0-9]{1,5})?\b",
    re.IGNORECASE,
)
_PUBLIC_BACKEND = re.compile(r"goreecloud-search-(?:public|prod)-[a-z0-9-]+:8080", re.IGNORECASE)
_ALLOWED_HEADERS = {
    'Strict-Transport-Security "max-age=31536000"',
    'X-Content-Type-Options nosniff',
    'Referrer-Policy no-referrer',
    'X-Robots-Tag "noindex, nofollow"',
    'Cache-Control no-store',
}
_PUBLIC_HOLD = re.compile(r'^respond\s+"[^"\r\n]{1,100}"\s+503$')


def _clean(line: str) -> str:
    # Caddy's ${...} style is not used here; braces in {$ENV} are values.
    # In the supported directive subset there are no embedded '#' values.
    return line.split("#", 1)[0].strip()


def _site_lines(config: str, hostname: str) -> list[str] | None:
    """Extract exactly one complete, top-level exact-host block, or fail."""
    lines = config.splitlines()
    starts = []
    nesting = 0
    for i, line in enumerate(lines):
        cleaned = _clean(line)
        if cleaned.casefold() == hostname.casefold() + " {":
            # A nested header resembling a vhost does not establish any host
            # isolation. It can live inside another site/route/snippet.
            if nesting != 0:
                return None
            starts.append(i)
        safe = _ENV.sub("ENV", cleaned)
        nesting += safe.count("{") - safe.count("}")
        if nesting < 0:
            return None
    if nesting != 0:
        return None
    if len(starts) != 1:
        return None
    start = starts[0]
    content: list[str] = []
    depth = 0
    for i in range(start, len(lines)):
        line = _clean(lines[i])
        if not line:
            continue
        safe = _ENV.sub("ENV", line)
        depth += safe.count("{") - safe.count("}")
        if i != start:
            content.append(line)
        if depth == 0:
            return content[:-1] if content and content[-1] == "}" else None
        if depth < 0:
            return None
    return None


def private_search_ingress_is_safe(config: str, expected_upstream: str) -> bool:
    """Require a single gated NetBird handler, single upstream and deny-all.

    The public hostname is a separate future release target. If it exists in a
    shared Caddyfile, it must not proxy into the private Development gateways;
    this function is NOT an assessment of that separate public service.
    """
    if (not isinstance(expected_upstream, str)
            or not expected_upstream.endswith(":8080")
            or not _PRIVATE_BACKENDS.fullmatch(expected_upstream)):
        return False
    if not isinstance(config, str) or not config:
        return False
    # Caddy `import` is evaluated before directive validation: an apparently
    # safe inline host can be silently widened by a separate imported file or
    # snippet. Fail until the exact adapted/fully expanded config is reviewed.
    clean_config = "\n".join(_clean(line) for line in config.splitlines())
    if any(re.match(r"import(?:\s|$)", line, flags=re.IGNORECASE)
           for line in clean_config.splitlines()):
        return False
    if _WILDCARD_SEARCH_HOST.search(clean_config):
        return False
    # This is intentionally conservative even if Caddy would prioritize an
    # exact host matcher today: a second default listener is an unreviewed
    # alternate ingress route for all hosts, including Development.
    if any(_HOSTLESS_LISTENER.fullmatch(line) for line in clean_config.splitlines()):
        return False
    lines = _site_lines(config, PRIVATE_HOST)
    if lines is None:
        return False
    # A second alias containing the dev host (e.g. a combined public vhost)
    # must not silently bypass the private-only Caddy route under review.
    private_host_token = _HOST_TOKEN_BOUNDARY.format(re.escape(PRIVATE_HOST))
    if len(re.findall(private_host_token, clean_config, flags=re.IGNORECASE)) != 1:
        return False
    # The sole approved Development gateway must not appear in another site,
    # even if hidden behind a Caddy map/vars alias instead of reverse_proxy.
    if clean_config.casefold().count(expected_upstream.casefold()) != 1:
        return False
    # A second Development/private backend, including non-gateway aliases or
    # alternate ports, must not be referenced by any other vhost. Keep only
    # independently public/prod-named Search backends valid.
    if [item.casefold() for item in _PRIVATE_BACKENDS.findall(clean_config)] != [expected_upstream.casefold()]:
        return False
    public = _site_lines(config, PUBLIC_HOST)
    public_host_token = _HOST_TOKEN_BOUNDARY.format(re.escape(PUBLIC_HOST))
    public_mentioned = bool(re.search(public_host_token, clean_config, flags=re.IGNORECASE))
    if public_mentioned:
        if public is None:
            return False
        # A future public site may give a static 503 or proxy only to an
        # explicitly public/prod-named backend. Generic service aliases are
        # ambiguous and cannot demonstrate static separation from Development.
        # This is a naming/structure gate, never runtime network isolation.
        if any(re.match(r"^(?:map|vars|rewrite|handle_path|route|php_fastcgi|forward_auth|invoke)\b", line,
                        flags=re.IGNORECASE) for line in public):
            return False
        for line in public:
            match = _PROXY.fullmatch(line)
            if match and not _PUBLIC_BACKEND.fullmatch(match.group(1)):
                return False

    children = {
        "site": {"tls", "header", "handle @netbird_client", "handle"},
        "tls": {"dns porkbun"},
    }
    stack = ["site"]
    observed: dict[str, int] = {}

    def seen(token: str) -> None:
        observed[token] = observed.get(token, 0) + 1

    for line in lines:
        if line == "}":
            if len(stack) == 1:
                return False
            stack.pop()
            continue
        if line.endswith(" {"):
            directive = line[:-2]
            if directive not in children.get(stack[-1], set()):
                return False
            stack.append(directive)
            seen("block:" + directive)
            continue
        if "{" in _ENV.sub("ENV", line) or "}" in _ENV.sub("ENV", line):
            return False
        section = stack[-1]
        if section == "site":
            if line == NETBIRD:
                seen("netbird")
            elif line == DENY:
                seen("deny")
            else:
                return False
        elif section == "handle @netbird_client":
            if line != "reverse_proxy " + expected_upstream:
                return False
            seen("proxy")
        elif section == "handle":
            if line != DENY:
                return False
            seen("deny")
        elif section == "tls":
            if not (line.startswith("propagation_delay ") or
                    line.startswith("propagation_timeout ") or
                    line.startswith("resolvers ")):
                return False
        elif section == "dns porkbun":
            if line not in ("api_key {$PORKBUN_API_KEY}",
                            "api_secret_key {$PORKBUN_API_SECRET_KEY}"):
                return False
            seen(line)
        elif section == "header":
            if line not in _ALLOWED_HEADERS:
                return False
        else:
            return False

    return stack == ["site"] and all(observed.get(key) == 1 for key in (
        "netbird", "proxy", "deny", "block:handle @netbird_client")) and (
        observed.get("block:handle", 0) in (0, 1)
        and observed.get("block:tls", 0) in (0, 1)
        and observed.get("block:header", 0) in (0, 1)
        and observed.get("block:dns porkbun", 0) in (0, 1)
        and (not observed.get("block:tls") or (
            observed.get("block:dns porkbun") == 1
            and observed.get("api_key {$PORKBUN_API_KEY}") == 1
            and observed.get("api_secret_key {$PORKBUN_API_SECRET_KEY}") == 1)))


def public_search_hostname_is_separate(config: str, expected_upstream: str) -> bool:
    """Require an explicit public vhost without using the private Search app.

    This optional *static* gate detects the missing public hostname seen on the
    VPS. A 503 hold page is an acceptable TLS placeholder, never a live-service
    or release pass. Only the narrowly reviewed public/prod backend form can
    be routed to a service. Do not infer effective Caddy routes or TLS issuance
    from a text check alone.
    """
    if not private_search_ingress_is_safe(config, expected_upstream):
        return False
    lines = _site_lines(config, PUBLIC_HOST)
    if lines is None:
        return False
    public_token = _HOST_TOKEN_BOUNDARY.format(re.escape(PUBLIC_HOST))
    cleaned = '\n'.join(_clean(line) for line in config.splitlines())
    if len(re.findall(public_token, cleaned, flags=re.IGNORECASE)) != 1:
        return False
    stack = ['site']
    destinations = 0
    seen_tls = 0
    seen_header = 0
    seen_dns = 0
    dns_env: set[str] = set()
    for line in lines:
        if line == '}':
            if len(stack) == 1:
                return False
            stack.pop()
            continue
        if line.endswith(' {'):
            directive = line[:-2]
            if ((stack[-1] == 'site' and directive in ('tls', 'header'))
                    or (stack[-1] == 'tls' and directive == 'dns porkbun')):
                stack.append(directive)
                if directive == 'tls':
                    seen_tls += 1
                elif directive == 'header':
                    seen_header += 1
                else:
                    seen_dns += 1
                if max(seen_tls, seen_header, seen_dns) > 1:
                    return False
                continue
            return False
        if '{' in _ENV.sub('ENV', line) or '}' in _ENV.sub('ENV', line):
            return False
        section = stack[-1]
        if section == 'site':
            if _PUBLIC_HOLD.fullmatch(line):
                destinations += 1
            else:
                proxy = _PROXY.fullmatch(line)
                if not proxy or not _PUBLIC_BACKEND.fullmatch(proxy.group(1)):
                    return False
                destinations += 1
        elif section == 'header':
            if line not in _ALLOWED_HEADERS or line == 'X-Robots-Tag "noindex, nofollow"':
                return False
        elif section == 'tls':
            if not (line.startswith('propagation_delay ')
                    or line.startswith('propagation_timeout ')
                    or line.startswith('resolvers ')):
                return False
        elif section == 'dns porkbun':
            if line not in ('api_key {$PORKBUN_API_KEY}',
                            'api_secret_key {$PORKBUN_API_SECRET_KEY}'):
                return False
            if line in dns_env:
                return False
            dns_env.add(line)
        else:
            return False
    return (stack == ['site'] and destinations == 1
            and (not seen_tls or (seen_dns == 1 and dns_env == {
                'api_key {$PORKBUN_API_KEY}',
                'api_secret_key {$PORKBUN_API_SECRET_KEY}',
            })))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only private Development Caddy structural guard")
    p.add_argument("--caddyfile", type=Path, required=True,
                   help="Explicit local Caddy configuration to inspect without mutating it")
    p.add_argument("--expected-upstream", required=True,
                   help="Exact approved Development gateway host:8080")
    p.add_argument('--require-public-host', action='store_true',
                   help='Also require an explicit, strictly separate public TLS vhost (static only)')
    args = p.parse_args(argv)
    try:
        if args.caddyfile.is_symlink() or not args.caddyfile.is_file():
            raise OSError("missing file or symlink")
        config = args.caddyfile.read_text(encoding="utf-8")
        ok = (public_search_hostname_is_separate(config, args.expected_upstream)
              if args.require_public_host else
              private_search_ingress_is_safe(config, args.expected_upstream))
    except (OSError, UnicodeError):
        ok = False
    print(json.dumps({"check": ("search_public_private_site_separation"
                                if args.require_public_host else
                                "development_caddy_private_acl_structure"),
                      "status": "pass_static_only" if ok else "blocked_do_not_cutover",
                      "runtime_verified": False}, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
