# SPDX-License-Identifier: AGPL-3.0-or-later
# pylint: disable=global-statement
# pylint: disable=missing-module-docstring, missing-class-docstring

__all__ = ["get_network"]

import typing as t
from collections.abc import Generator, Mapping


import atexit
import asyncio
import ipaddress
import re
import socket
from itertools import cycle
from urllib.parse import urlsplit

from curl_cffi import CurlHttpVersion, CurlOpt
from curl_cffi.requests.exceptions import (
    ConnectionError as CurlConnectionError,
    ProxyError,
    RequestException,
)

from searx import logger, sxng_debug
from searx.goreecloud_policy import safe_external_media_url
from searx.extended_types import SXNG_Response
from .client import DEFAULT_IMPERSONATE, AsyncClient, new_client, get_loop
from .raise_for_httperror import raise_for_httperror

logger = logger.getChild('network')
DEFAULT_NAME = '__DEFAULT__'
NETWORKS: dict[str, "Network"] = {}
# requests compatibility when reading proxy settings from settings.yml
PROXY_PATTERN_MAPPING = {
    'http': 'http://',
    'https': 'https://',
    'socks4': 'socks4://',
    'socks5': 'socks5://',
    'socks5h': 'socks5h://',
    'http:': 'http://',
    'https:': 'https://',
    'socks4:': 'socks4://',
    'socks5:': 'socks5://',
    'socks5h:': 'socks5h://',
}

ADDRESS_MAPPING = {'ipv4': '0.0.0.0', 'ipv6': '::'}
# Some IPv6 addresses that Python considers globally routable can encode a
# non-global IPv4 destination through NAT64. Deny these translation families
# instead of trusting the IPv6 wrapper's is_global property.
PROVIDER_TRANSLATION_NETWORKS = tuple(ipaddress.ip_network(prefix) for prefix in (
    '64:ff9b::/96', '64:ff9b:1::/48', '2002::/16', '2001::/32', '::/96',
))


@t.final
class Network:

    __slots__ = (
        'enable_http',
        'verify',
        'enable_http2',
        'enable_http3',
        'max_connections',
        'local_addresses',
        'proxies',
        'using_tor_proxy',
        'privacy_proxy_required',
        'provider_target_guard_required',
        'max_redirects',
        'retries',
        'retry_on_http_error',
        '_local_addresses_cycle',
        '_proxies_cycle',
        '_clients',
        '_logger',
    )

    _CLIENT_KWARGS = ('verify', 'max_redirects', 'impersonate', 'curl_options', 'enable_http3')

    def __init__(
        # pylint: disable=too-many-arguments
        self,
        enable_http: bool = True,
        verify: bool = True,
        enable_http2: bool = False,
        enable_http3: bool = False,
        max_connections: int = None,  # pyright: ignore[reportArgumentType]
        proxies: str | dict[str, str] | None = None,
        using_tor_proxy: bool = False,
        privacy_proxy_required: bool = False,
        provider_target_guard_required: bool = False,
        local_addresses: str | list[str] | None = None,
        retries: int = 0,
        retry_on_http_error: bool = False,
        max_redirects: int = 30,
        logger_name: str = None,  # pyright: ignore[reportArgumentType]
    ):

        self.enable_http = enable_http
        self.verify = verify
        self.enable_http2 = enable_http2
        self.enable_http3 = enable_http3
        self.max_connections = max_connections
        self.proxies = proxies
        self.using_tor_proxy = using_tor_proxy
        self.privacy_proxy_required = privacy_proxy_required
        # Branded free-first Search still needs SSRF/redirect protection even
        # though it deliberately does not use the optional Tor relay.
        self.provider_target_guard_required = provider_target_guard_required or privacy_proxy_required
        self.local_addresses = local_addresses
        self.retries = retries
        self.retry_on_http_error = retry_on_http_error
        self.max_redirects = max_redirects
        self._local_addresses_cycle = self.get_ipaddress_cycle()
        self._proxies_cycle = self.get_proxy_cycles()
        self._clients = {}
        self._logger = logger.getChild(logger_name) if logger_name else logger
        self.check_parameters()

    def check_parameters(self):
        for address in self.iter_ipaddresses():
            if '/' in address:
                ipaddress.ip_network(address, False)
            else:
                ipaddress.ip_address(address)

        if self.proxies is not None and not isinstance(self.proxies, (str, dict)):
            raise ValueError('proxies type has to be str, dict or None')

    def iter_ipaddresses(self) -> Generator[str]:
        local_addresses = self.local_addresses
        if not local_addresses:
            return
        if isinstance(local_addresses, str):
            local_addresses = [local_addresses]
        yield from local_addresses

    def get_ipaddress_cycle(self):
        while True:
            count = 0
            for address in self.iter_ipaddresses():
                if '/' in address:
                    for a in ipaddress.ip_network(address, False).hosts():
                        yield str(a)
                        count += 1
                else:
                    a = ipaddress.ip_address(address)
                    yield str(a)
                    count += 1
            if count == 0:
                yield None

    def iter_proxies(self) -> Generator[tuple[str, list[str]]]:
        if not self.proxies:
            return
        if isinstance(self.proxies, str):
            yield 'all://', [self.proxies]
        else:
            for pattern, proxy_url in self.proxies.items():
                pattern: str = PROXY_PATTERN_MAPPING.get(pattern, pattern)
                if isinstance(proxy_url, str):
                    proxy_url = [proxy_url]
                yield pattern, proxy_url

    def get_proxy_cycles(self) -> Generator[tuple[tuple[str, str], ...], str, str]:  # not sure type is correct
        proxy_settings: dict[str, t.Any] = {}
        for pattern, proxy_urls in self.iter_proxies():
            proxy_settings[pattern] = cycle(proxy_urls)
        while True:
            # pylint: disable=stop-iteration-return
            yield tuple((pattern, next(proxy_url_cycle)) for pattern, proxy_url_cycle in proxy_settings.items())

    _HTTP_VERSION = {
        int(CurlHttpVersion.V1_0): "HTTP/1.0",
        int(CurlHttpVersion.V1_1): "HTTP/1.1",
        int(CurlHttpVersion.V2_0): "HTTP/2",
        int(CurlHttpVersion.V2TLS): "HTTP/2",
        int(CurlHttpVersion.V2_PRIOR_KNOWLEDGE): "HTTP/2",
        int(CurlHttpVersion.V3): "HTTP/3",
        int(CurlHttpVersion.V3ONLY): "HTTP/3",
    }

    async def log_response(self, response: SXNG_Response):
        request = response.request
        method = request.method if request else "?"
        # Do not log the upstream URL: its query string may contain user searches.
        self._logger.debug("HTTP Response: %s status=%s", method, response.status_code)

    @staticmethod
    async def check_tor_proxy(client: AsyncClient, proxies) -> bool:
        """Attest this client via its relay; never reuse an old proxy verdict."""
        if not proxies or not all(url.startswith('socks5h://') for _, url in proxies):
            return False
        try:
            response = await client.get(
                "https://check.torproject.org/api/ip", timeout=8, allow_redirects=False
            )
            if response.status_code != 200:
                return False
            payload = response.json()
            return isinstance(payload, dict) and payload.get('IsTor') is True
        except (RequestException, OSError, ValueError, TypeError, AttributeError):
            # A failed or malformed verification cannot authorize private egress.
            return False

    @staticmethod
    def valid_private_proxy(proxies: tuple[tuple[str, str], ...]) -> bool:
        """Only a single local SOCKS5H gateway can carry private Search traffic.

        SOCKS5H delegates DNS lookup to the relay. A local gateway must separately
        be verified as Tor or another owner-approved privacy network.
        """
        if len(proxies) != 1 or proxies[0][0] != 'all://':
            return False
        url = proxies[0][1]
        if not isinstance(url, str) or not url or url != url.strip():
            return False
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == 'socks5h'
            and parsed.hostname in ('127.0.0.1', '::1')
            and port is not None and port > 0
            and not parsed.username and not parsed.password
            and not parsed.path and not parsed.query and not parsed.fragment
            and '#' not in url and '?' not in url
        )

    @staticmethod
    async def resolve_public_provider(host: str) -> tuple[str, tuple[str, ...]]:
        """Resolve once, vet *every* answer, then pin the curl connection.

        A hostname syntax check by itself cannot stop a DNS rebinding answer
        from connecting Search to a loopback, private or metadata endpoint.
        Do not leak the hostname into errors: upstream URLs can carry secrets.
        """
        try:
            ascii_host = host.encode('idna').decode('ascii').lower()
            answers = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(
                    ascii_host, 443, type=socket.SOCK_STREAM,
                ),
                timeout=3.0,
            )
            addresses = tuple(sorted({entry[4][0] for entry in answers}))
            if not 1 <= len(addresses) <= 16 or not all(
                Network.public_provider_address(address) for address in addresses
            ):
                raise ValueError('Unsafe provider address')
            return ascii_host, addresses
        except (OSError, ValueError, UnicodeError, asyncio.TimeoutError) as exc:
            raise ProxyError('Search provider egress blocked: DNS resolution not publicly pinned') from exc

    @staticmethod
    def public_provider_address(value: str) -> bool:
        address = ipaddress.ip_address(value)
        return bool(address.is_global and not (
            isinstance(address, ipaddress.IPv6Address)
            and (address.ipv4_mapped is not None or any(
                address in network for network in PROVIDER_TRANSLATION_NETWORKS
            ))
        ))

    async def get_client(
        self,
        verify: bool | None = None,
        max_redirects: int | None = None,
        impersonate: str | None = None,
        curl_options: dict[int, t.Any] | None = None,
        enable_http3: bool | None = None,
        _trusted_dns_pin: tuple[str, tuple[str, ...]] | None = None,
    ) -> AsyncClient:
        verify = self.verify if verify is None else verify
        max_redirects = self.max_redirects if max_redirects is None else max_redirects
        impersonate = impersonate or DEFAULT_IMPERSONATE
        enable_http3 = self.enable_http3 if enable_http3 is None else enable_http3
        local_address = next(self._local_addresses_cycle)
        proxies = next(self._proxies_cycle)  # is a tuple so it can be part of the key
        if self.provider_target_guard_required:
            if verify is not True or self.enable_http or curl_options:
                raise ProxyError('Search provider egress blocked: insecure transport override')
            # Some upstream engines opt into HTTP/3 independently of the
            # network's defaults.  The guarded provider route must stay on
            # HTTPS over TCP; QUIC uses UDP and can bypass TCP-only egress
            # controls.  Downgrade to HTTP/2 (or 1.1) without dropping the
            # provider's results.
            enable_http3 = False
            if not self.privacy_proxy_required:
                # Direct free-first Search is safe only if a vetted address
                # is installed into curl's resolver cache for this connection.
                # Proxies resolve destinations elsewhere and bypass this pin.
                if proxies or not _trusted_dns_pin or not _trusted_dns_pin[1]:
                    raise ProxyError('Search provider egress blocked: verified direct DNS pin required')
        if self.privacy_proxy_required:
            # Anonymous Search must prove the gateway is Tor, not merely SOCKS5H.
            # Fail before opening a connection if the verification flag was omitted.
            if not self.using_tor_proxy:
                raise ProxyError('Private Search egress blocked: Tor verification required')
            if not self.valid_private_proxy(proxies):
                raise ProxyError('Private Search egress blocked: approved local SOCKS5H proxy required')
        curl_key = tuple(sorted((int(k), v) for k, v in (curl_options or {}).items()))
        key = (verify, max_redirects, local_address, proxies, impersonate, curl_key, enable_http3, _trusted_dns_pin)
        if key not in self._clients or self._clients[key].is_closed:
            effective_curl_options = curl_options
            if _trusted_dns_pin is not None and self.provider_target_guard_required:
                hostname, addresses = _trusted_dns_pin
                # CURLOPT_RESOLVE binds HTTPS host:port to these IPs while
                # retaining the original hostname for SNI/cert verification.
                # Every address was checked before the client was created.
                ip_list = ','.join(f'[{ip}]' if ':' in ip else ip for ip in addresses)
                effective_curl_options = {
                    CurlOpt.RESOLVE: [f'{hostname}:443:{ip_list}'],
                    # libcurl otherwise honors HTTPS_PROXY/ALL_PROXY from the
                    # process environment and could bypass our local DNS pin.
                    CurlOpt.PROXY: '',
                }
            client = new_client(
                self.enable_http,
                verify,
                self.enable_http2,
                enable_http3,
                self.max_connections,
                dict(proxies),
                local_address,
                max_redirects,
                impersonate=impersonate,
                curl_options=effective_curl_options,
            )
            self._clients[key] = client
        client = self._clients[key]
        # Even a reused connection must be verified: the local SOCKS gateway
        # can change independently of the search client's lifetime.
        if self.using_tor_proxy and not await self.check_tor_proxy(client, proxies):
            self._clients.pop(key, None)
            await client.aclose()
            raise ProxyError('Private Search egress blocked: Tor verification failed')
        return client

    async def aclose(self):
        async def close_client(client):
            try:
                await client.aclose()
            except RequestException:
                pass

        await asyncio.gather(*[close_client(client) for client in self._clients.values()], return_exceptions=False)

    @staticmethod
    def extract_kwargs_clients(kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {key: kwargs.pop(key) for key in Network._CLIENT_KWARGS if key in kwargs}

    @staticmethod
    def extract_do_raise_for_httperror(kwargs: dict[str, t.Any]):
        do_raise_for_httperror = True
        if 'raise_for_httperror' in kwargs:
            do_raise_for_httperror = kwargs['raise_for_httperror']
            del kwargs['raise_for_httperror']
        return do_raise_for_httperror

    def patch_response(self, response: SXNG_Response, do_raise_for_httperror: bool) -> SXNG_Response:
        if do_raise_for_httperror:
            try:
                raise_for_httperror(response)
            except:
                method = response.request.method if response.request else "?"
                # Upstream URLs can contain search terms, tokens or private parameters.
                self._logger.warning("HTTP Request failed: %s status=%s", method, response.status_code)
                raise
        return response

    def is_valid_response(self, response: SXNG_Response):
        # pylint: disable=too-many-boolean-expressions
        if (
            (self.retry_on_http_error is True and 400 <= response.status_code <= 599)
            or (isinstance(self.retry_on_http_error, list) and response.status_code in self.retry_on_http_error)
            or (isinstance(self.retry_on_http_error, int) and response.status_code == self.retry_on_http_error)
        ):
            return False
        return True

    async def call_client(self, stream: bool, method: str, url: str, **kwargs: t.Any) -> SXNG_Response:
        retries = self.retries
        was_disconnected = False
        do_raise_for_httperror = Network.extract_do_raise_for_httperror(kwargs)
        kwargs_clients = Network.extract_kwargs_clients(kwargs)
        trusted_dns_pin = None
        if self.provider_target_guard_required:
            # These were extracted into client arguments; reject before any
            # resolver work just like request-level transport overrides.
            if 'verify' in kwargs_clients or 'curl_options' in kwargs_clients:
                raise ProxyError('Search provider egress blocked: insecure transport override')
            # curl_cffi accepts these per-request controls in addition to
            # client options.  In particular, doh_url can silently replace
            # the resolver and make a second outbound request to an unvetted
            # endpoint even when the provider URL itself passes validation.
            if any(key in kwargs for key in (
                'proxy', 'proxies', 'proxy_auth', 'interface',
                'curl_options', 'doh_url', 'http_version',
                # Request-level TLS and authentication arguments override
                # the trusted client's verified defaults.  A provider must
                # never opt out of certificate validation or send credentials
                # supplied through the engine's request path.
                'verify', 'cert', 'auth',
            )):
                raise ProxyError('Search provider egress blocked: per-request transport override')
            if not safe_external_media_url(url):
                raise ProxyError('Search provider egress blocked: unsafe HTTPS destination')
            # Never follow provider redirects to an unvalidated host, even on
            # the direct-HTTPS free-first profile.
            kwargs['allow_redirects'] = False
            # Do not forward upstream cookies or client-identifying headers.
            # Provider challenges might need cookies; privacy takes precedence.
            kwargs.pop('cookies', None)
            # curl_cffi's dedicated referer argument bypasses the header
            # scrubber below. Never leak a query-bearing referrer upstream.
            kwargs.pop('referer', None)
            if kwargs.get('headers'):
                # Deny ambiguous/binary header names before opening a client.
                # Otherwise a forged Host may evade text-only casefolding.
                if not isinstance(kwargs['headers'], Mapping) or any(
                    not isinstance(name, str)
                    or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
                    for name in kwargs['headers']
                ):
                    raise ProxyError('Search provider egress blocked: invalid request header')
                identifying = {
                    'host', ':authority',
                    'cookie', 'authorization', 'proxy-authorization', 'x-api-key',
                    'forwarded', 'x-forwarded-for', 'x-real-ip', 'x-client-ip',
                    'cf-connecting-ip', 'true-client-ip', 'x-forwarded-host',
                    'x-forwarded-proto', 'x-original-forwarded-for',
                    'x-original-ip', 'x-cluster-client-ip', 'x-proxyuser-ip',
                    'referer', 'referrer', 'origin', 'x-requested-with',
                    'x-amzn-trace-id', 'x-cloud-trace-context',
                    'traceparent', 'tracestate', 'baggage', 'b3',
                }
                identifying_prefixes = (
                    'x-forwarded-', 'x-b3-', 'sec-ch-', 'sec-fetch-',
                )
                kwargs['headers'] = {
                    name: value for name, value in kwargs['headers'].items()
                    if name.lower() not in identifying
                    and not name.lower().startswith(identifying_prefixes)
                }
            # Resolve only after every synchronous rejection/sanitization;
            # a rejected request must not cause even a DNS lookup.
            if not self.privacy_proxy_required:
                trusted_dns_pin = await self.resolve_public_provider(urlsplit(url).hostname)
        while retries >= 0:  # pragma: no cover
            client = await self.get_client(_trusted_dns_pin=trusted_dns_pin, **kwargs_clients)
            try:
                method = method.upper()
                if stream:
                    return client.stream(method, url, **kwargs)

                response = await client.request(method, url, **kwargs)
                if sxng_debug:
                    await self.log_response(response)
                if self.is_valid_response(response) or retries <= 0:
                    return self.patch_response(response, do_raise_for_httperror)
                await client.aclose()
            except CurlConnectionError as e:
                if not was_disconnected:
                    # the server has closed the connection:
                    # try again without decreasing the retries variable & with a new HTTP client
                    was_disconnected = True
                    await client.aclose()
                    self._logger.warning('ConnectionError: the server has disconnected, retrying')
                    continue
                if retries <= 0:
                    raise e
            except RequestException as e:
                if retries <= 0:
                    raise e
            retries -= 1

    async def request(self, method: str, url: str, **kwargs: t.Any) -> SXNG_Response:
        return await self.call_client(False, method, url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs):
        return await self.call_client(True, method, url, **kwargs)

    @classmethod
    async def aclose_all(cls):
        await asyncio.gather(*[network.aclose() for network in NETWORKS.values()], return_exceptions=False)


def get_network(name: str | None = None) -> "Network":
    return NETWORKS.get(name or DEFAULT_NAME)  # pyright: ignore[reportReturnType]


def check_network_configuration():
    async def check():
        exception_count = 0
        for network in NETWORKS.values():
            if network.privacy_proxy_required:
                # Startup/readiness checks must be offline and deterministic.
                # Live Tor exit attestation is mandatory on each actual request
                # in get_client(), and never authorizes a direct fallback.
                proxies = next(network._proxies_cycle)  # pylint: disable=protected-access
                if not network.using_tor_proxy or not network.valid_private_proxy(proxies):
                    network._logger.error('Private Search Tor gateway misconfigured')  # pylint: disable=protected-access
                    exception_count += 1
                continue
            if network.using_tor_proxy:
                try:
                    await network.get_client()
                except Exception:  # pylint: disable=broad-except
                    network._logger.exception('Error')  # pylint: disable=protected-access
                    exception_count += 1
        return exception_count

    future = asyncio.run_coroutine_threadsafe(check(), get_loop())
    exception_count = future.result()
    if exception_count > 0:
        raise RuntimeError("Invalid network configuration")


def initialize(
    settings_engines: list[dict[str, t.Any]] = None,  # pyright: ignore[reportArgumentType]
    settings_outgoing: dict[str, t.Any] = None,  # pyright: ignore[reportArgumentType]
) -> None:
    # pylint: disable=import-outside-toplevel)
    from searx.engines import engines
    from searx import settings

    # pylint: enable=import-outside-toplevel)

    settings_engines = settings_engines or settings['engines']
    settings_outgoing = settings_outgoing or settings['outgoing']

    default_params: dict[str, t.Any] = {
        'enable_http': False,
        'verify': settings_outgoing['verify'],
        'enable_http2': settings_outgoing['enable_http2'],
        'enable_http3': False,
        'max_connections': settings_outgoing['pool_connections'],
        'local_addresses': settings_outgoing['source_ips'],
        'using_tor_proxy': settings_outgoing['using_tor_proxy'],
        'privacy_proxy_required': bool(settings.get('goreecloud', {}).get('require_anonymous_egress')),
        'provider_target_guard_required': bool(settings.get('goreecloud', {}).get('private_search')),
        'proxies': settings_outgoing['proxies'],
        'max_redirects': settings_outgoing['max_redirects'],
        'retries': settings_outgoing['retries'],
        'retry_on_http_error': False,
    }

    def new_network(params: dict[str, t.Any], logger_name: str | None = None):
        nonlocal default_params
        result = {}
        result.update(default_params)  # pyright: ignore[reportUnknownMemberType]
        result.update(params)  # pyright: ignore[reportUnknownMemberType]
        # Engine-specific overrides cannot disable mandatory private Tor
        # verification. A disabled global Tor flag still fails closed.
        result['privacy_proxy_required'] = default_params['privacy_proxy_required']
        # Per-engine configuration must never turn off GoreeCloud's shared
        # outbound provider-target guard.
        result['provider_target_guard_required'] = (
            default_params['provider_target_guard_required'] or result['privacy_proxy_required']
        )
        if result['privacy_proxy_required']:
            result['using_tor_proxy'] = default_params['using_tor_proxy']
        if logger_name:
            result['logger_name'] = logger_name
        return Network(**result)  # type: ignore

    def iter_networks():
        nonlocal settings_engines
        for engine_spec in settings_engines:
            engine_name = engine_spec['name']
            engine = engines.get(engine_name)
            if engine is None:
                continue
            network = getattr(engine, 'network', None)
            yield engine_name, engine, network

    if NETWORKS:
        done()
    NETWORKS.clear()
    NETWORKS[DEFAULT_NAME] = new_network({}, logger_name='default')
    NETWORKS['ipv4'] = new_network({'local_addresses': '0.0.0.0'}, logger_name='ipv4')
    NETWORKS['ipv6'] = new_network({'local_addresses': '::'}, logger_name='ipv6')

    # define networks from outgoing.networks
    for network_name, network in settings_outgoing['networks'].items():
        NETWORKS[network_name] = new_network(network, logger_name=network_name)

    # define networks from engines.[i].network (except references)
    for engine_name, engine, network in iter_networks():
        if network is None:
            network = {}
            for attribute_name, attribute_value in default_params.items():
                if hasattr(engine, attribute_name):
                    network[attribute_name] = getattr(engine, attribute_name)
                else:
                    network[attribute_name] = attribute_value
            NETWORKS[engine_name] = new_network(network, logger_name=engine_name)
        elif isinstance(network, dict):
            NETWORKS[engine_name] = new_network(network, logger_name=engine_name)

    # define networks from engines.[i].network (references)
    for engine_name, engine, network in iter_networks():
        if isinstance(network, str):
            NETWORKS[engine_name] = NETWORKS[network]

    # the /image_proxy endpoint has a dedicated network.
    # same parameters than the default network, but HTTP/2 is disabled.
    # It decreases the CPU load average, and the total time is more or less the same
    if 'image_proxy' not in NETWORKS:
        image_proxy_params = default_params.copy()
        image_proxy_params['enable_http2'] = False
        NETWORKS['image_proxy'] = new_network(image_proxy_params, logger_name='image_proxy')


@atexit.register
def done():
    """Close all HTTP client

    Note: since Network.aclose has to be async, it is not possible to call this method on Network.__del__
    So Network.aclose is called here using atexit.register
    """
    try:
        loop = get_loop()
        if loop:
            future = asyncio.run_coroutine_threadsafe(Network.aclose_all(), loop)
            # wait 3 seconds to close the HTTP clients
            future.result(3)
    finally:
        NETWORKS.clear()


NETWORKS[DEFAULT_NAME] = Network()
