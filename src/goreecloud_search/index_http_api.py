from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import AddressValueError, IPv4Address, IPv6Address
import json
from typing import Any, Protocol
from unicodedata import category as unicode_category, normalize as unicode_normalize

from .models import ProviderOrigin
from .planner import (
    INDEX_ORIGINATED_DELEGATION_CONTRACT_VERSION,
    INDEX_ORIGINATED_DELEGATION_MODE,
    INDEX_ORIGINATED_FALLBACK_ALLOWED,
    INDEX_ORIGINATED_INDEX_PROVIDER_REENTRY_ALLOWED,
    SourcePlanningError,
)
from .service import SearchCore
from .execution import SearchAvailability
from .version import __version__


SEARCH_API_VERSION = "1"
SEARCH_QUERY_CAPABILITY_ID = "search.query"
SEARCH_QUERY_ENDPOINT = "/api/v1/search"
SEARCH_STATUS_ENDPOINT = "/api/v1/status"
SEARCH_HEALTH_ENDPOINT = "/healthz"
SEARCH_READINESS_ENDPOINT = "/readyz"
SEARCH_PRIVACY_HEADER = "X-GoreeCloud-Privacy-Capability"
SEARCH_IDENTITY_HEADER = "Authorization"
SEARCH_IDENTITY_SCHEME = "Bearer"
SEARCH_IDENTITY_AUTHORITY = "goreecloud-identity"
SEARCH_PRIVACY_SCHEME = "privacy_shield_capability_token_reference"
SEARCH_PRIVACY_ENFORCEMENT = "required"
SEARCH_INDEX_REQUESTER_ID = "goreecloud-index"
SEARCH_INDEX_REQUESTER_TYPE = "application"
SEARCH_VERIFICATION_CONSUMER_ID = "goreecloud-search"
SEARCH_RESOURCE_ID = "goreecloud.search.query"
SEARCH_PURPOSE = "internet_search"
SEARCH_PROCESSING_ZONE = "private_goreecloud"
SEARCH_DESTINATION = "https://search.goreecloud.com"
SEARCH_RETENTION_MODE = "none"
SEARCH_MAX_REQUEST_BYTES = 16 * 1024
SEARCH_MAX_QUERY_CHARS = 2048
SEARCH_MAX_RESULTS = 100
SEARCH_MAX_BEARER_CHARS = 16 * 1024
SEARCH_MAX_CAPABILITY_REFERENCE_CHARS = 512
SEARCH_REQUEST_TIMEOUT_SECONDS = 5.0


class IndexHTTPBoundaryError(ValueError):
    """Raised when an Index-originated HTTP request fails the Search boundary."""


@dataclass(frozen=True, slots=True)
class AuthenticatedRequester:
    requester_id: str
    requester_type: str
    authority: str = SEARCH_IDENTITY_AUTHORITY


@dataclass(frozen=True, slots=True)
class PrivacyCapabilityVerificationRequest:
    capability_reference: str = field(repr=False)
    requester_id: str = SEARCH_INDEX_REQUESTER_ID
    resource_id: str = SEARCH_RESOURCE_ID
    purpose: str = SEARCH_PURPOSE
    operation: str = SEARCH_QUERY_CAPABILITY_ID
    processing_zone: str = SEARCH_PROCESSING_ZONE
    destination: str = SEARCH_DESTINATION
    retention_mode: str = SEARCH_RETENTION_MODE
    verification_consumer_id: str = SEARCH_VERIFICATION_CONSUMER_ID
    consume: bool = True


@dataclass(frozen=True, slots=True)
class PrivacyCapabilityVerification:
    authorized: bool
    requester_id: str
    verification_consumer_id: str
    consumed: bool


class RequesterIdentityVerifier(Protocol):
    async def verify_bearer(self, bearer_credential: str) -> AuthenticatedRequester:
        ...


class PrivacyCapabilityVerifier(Protocol):
    async def verify_reference(
        self,
        request: PrivacyCapabilityVerificationRequest,
    ) -> PrivacyCapabilityVerification:
        ...


_BIDI_FORMAT_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


def _contains_unicode_control(value: str) -> bool:
    return any(
        unicode_category(char) in {"Cc", "Cs"} or char in _BIDI_FORMAT_CONTROLS
        for char in value
    )


def _is_bounded_opaque(value: str, *, prefix: str | None, maximum: int) -> bool:
    if not value or len(value) > maximum:
        return False
    if prefix is not None and (not value.startswith(prefix) or len(value) <= len(prefix)):
        return False
    return all(not char.isspace() for char in value) and not _contains_unicode_control(value)


def _valid_bearer(value: str) -> bool:
    if not value or len(value) > SEARCH_MAX_BEARER_CHARS:
        return False
    return all(not char.isspace() for char in value) and not _contains_unicode_control(value)


def _valid_capability_reference(value: str) -> bool:
    if not value.startswith("psc_") or len(value) <= 4 or len(value) > SEARCH_MAX_CAPABILITY_REFERENCE_CHARS:
        return False
    return all(not char.isspace() for char in value) and not _contains_unicode_control(value)


def _looks_like_numeric_ipv4(host: str) -> bool:
    labels = host.split(".")

    def numeric_label(label: str) -> bool:
        if label.isdecimal():
            return True
        lowered = label.casefold()
        return (
            lowered.startswith("0x")
            and all(character in "0123456789abcdef" for character in lowered[2:])
        )

    # Browser URL parsers treat a final numeric label as an IPv4 candidate,
    # even when earlier labels are not numeric or there are too many labels.
    return numeric_label(labels[-1])


def _normalize_dns_or_ipv4_host(value: str) -> str:
    source = unicode_normalize("NFC", value.removesuffix(".")).lower()
    if not source or len(source) > 253:
        raise ValueError("host must contain a usable DNS or IPv4 identity")
    try:
        encoded_labels = []
        for label in source.split("."):
            encoded = label.encode("idna").decode("ascii").lower()
            decoded = encoded.encode("ascii").decode("idna")
            # The stdlib codec uses IDNA2003. Reject names whose normalization
            # changes their identity rather than silently mapping a browser's
            # non-transitional IDN to a different host (for example, sharp s).
            if decoded.encode("idna").decode("ascii").lower() != encoded:
                raise ValueError("host contains an invalid A-label")
            if not label.isascii() and unicode_normalize("NFC", decoded).lower() != label:
                raise ValueError("host requires unsupported IDN mapping")
            encoded_labels.append(encoded)
        normalized = ".".join(encoded_labels)
    except UnicodeError as exc:
        raise ValueError("host cannot be represented as a valid IDN") from exc

    if len(normalized) > 253:
        raise ValueError("host exceeds the DNS length limit")

    labels = normalized.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or any(
            not (character.isascii() and (character.isalnum() or character == "-"))
            for character in label
        )
        for label in labels
    ):
        raise ValueError("host contains invalid DNS label syntax")

    if _looks_like_numeric_ipv4(normalized):
        try:
            canonical_ipv4 = str(IPv4Address(normalized))
        except AddressValueError as exc:
            raise ValueError("host contains ambiguous numeric IPv4 syntax") from exc
        if normalized != canonical_ipv4:
            raise ValueError("host contains non-canonical IPv4 syntax")
        return canonical_ipv4

    return normalized


def _normalize_allowed_host(value: str) -> str:
    if not isinstance(value, str) or _contains_unicode_control(value):
        raise ValueError("allowed host must be text without control characters")
    raw = value.strip()
    if not raw or any(char.isspace() for char in raw) or _contains_unicode_control(raw):
        raise ValueError("allowed host is empty or contains unsupported whitespace/control characters")

    if "%" in raw:
        raise ValueError("allowed host must not contain an IPv6 scope identifier")
    if raw.startswith("["):
        if not raw.endswith("]") or raw.count("[") != 1 or raw.count("]") != 1:
            raise ValueError("bracketed allowed host must be a single IPv6 literal")
        try:
            return str(IPv6Address(raw[1:-1])).casefold()
        except AddressValueError as exc:
            raise ValueError("bracketed allowed host must contain valid IPv6") from exc

    if ":" in raw:
        try:
            return str(IPv6Address(raw)).casefold()
        except AddressValueError as exc:
            raise ValueError("allowed host must not include a port or malformed IPv6") from exc

    if any(character in raw for character in "@[]/\\"):
        raise ValueError("allowed host contains unsupported authority syntax")

    return _normalize_dns_or_ipv4_host(raw)


def _json_loads_strict(body: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"unsupported JSON constant: {value}")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    return json.loads(
        body.decode("utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_keys,
    )


def capability_record() -> dict[str, Any]:
    return {
        "id": SEARCH_QUERY_CAPABILITY_ID,
        "contract_version": SEARCH_API_VERSION,
        "authoritative": True,
        "current": True,
        "endpoint": SEARCH_QUERY_ENDPOINT,
        "max_results": SEARCH_MAX_RESULTS,
        "production_accepted": False,
        "discovery_endpoint": SEARCH_STATUS_ENDPOINT,
        "discovery_collection": "capability_evidence",
        "methods": ["POST"],
        "preferred_method": "POST",
        "preferred_query_transport": "json_body",
        "request_media_type": "application/json",
        "response_media_type": "application/json",
        "privacy_authorization_required": True,
        "privacy_authorization_scheme": SEARCH_PRIVACY_SCHEME,
        "privacy_authorization_header": SEARCH_PRIVACY_HEADER,
        "privacy_authorization_enforcement": SEARCH_PRIVACY_ENFORCEMENT,
        "authenticated_requester_required": True,
        "authenticated_requester_authority": SEARCH_IDENTITY_AUTHORITY,
        "authenticated_requester_scheme": "bearer",
        "authenticated_requester_header": SEARCH_IDENTITY_HEADER,
        "max_request_bytes": SEARCH_MAX_REQUEST_BYTES,
        "index_delegation_contract_version": INDEX_ORIGINATED_DELEGATION_CONTRACT_VERSION,
        "index_delegation_mode": INDEX_ORIGINATED_DELEGATION_MODE,
        "index_provider_reentry_allowed": INDEX_ORIGINATED_INDEX_PROVIDER_REENTRY_ALLOWED,
        "index_delegation_fallback_allowed": INDEX_ORIGINATED_FALLBACK_ALLOWED,
    }


class SearchIndexHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        core: SearchCore,
        identity_verifier: RequesterIdentityVerifier,
        privacy_verifier: PrivacyCapabilityVerifier,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "search.goreecloud.com"),
        authority_transports_ready: bool = False,
    ) -> None:
        normalized_hosts = frozenset(_normalize_allowed_host(item) for item in allowed_hosts)
        if not normalized_hosts:
            raise ValueError("allowed_hosts must contain at least one usable host")
        self.search_core = core
        self.identity_verifier = identity_verifier
        self.privacy_verifier = privacy_verifier
        self.allowed_hosts = normalized_hosts
        self.authority_transports_ready = bool(authority_transports_ready)
        super().__init__((host, port), _IndexRequestHandler)

    @property
    def ready(self) -> bool:
        return self.authority_transports_ready and any(
            descriptor.enabled and descriptor.origin is ProviderOrigin.EXTERNAL
            for descriptor in self.search_core.providers
        )


class _IndexRequestHandler(BaseHTTPRequestHandler):
    server: SearchIndexHTTPServer
    server_version = "GoreeCloudSearch"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(SEARCH_REQUEST_TIMEOUT_SECONDS)

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        authenticate: bool = False,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if authenticate:
            self.send_header("WWW-Authenticate", "Bearer")
        self.end_headers()
        self.wfile.write(body)

    def _send_method_not_allowed(self, *, write_body: bool = True) -> None:
        if not self._host_allowed():
            if write_body:
                self._send_json(421, {"error": "misdirected_request"})
            else:
                body = json.dumps(
                    {"error": "misdirected_request"},
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                self.send_response(421)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
            return

        if write_body:
            self._send_json(405, {"error": "method_not_allowed"})
        else:
            body = json.dumps(
                {"error": "method_not_allowed"},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(405)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()

    def _normalized_host(self) -> str:
        # Do not trust the first of multiple Host headers or silently discard an
        # invalid port: proxy and application routing must see one authority.
        hosts = self.headers.get_all("Host") or []
        if len(hosts) != 1:
            return ""
        if _contains_unicode_control(hosts[0]):
            return ""
        raw = hosts[0].strip()
        if not raw or any(char.isspace() for char in raw) or _contains_unicode_control(raw):
            return ""

        if raw.startswith("["):
            closing = raw.find("]")
            if closing <= 1 or raw.count("[") != 1 or raw.count("]") != 1:
                return ""
            host = raw[1:closing]
            if "%" in host:
                return ""
            try:
                normalized_host = str(IPv6Address(host))
            except AddressValueError:
                return ""
            suffix = raw[closing + 1:]
            if suffix and (not suffix.startswith(":") or not self._valid_port(suffix[1:])):
                return ""
            return normalized_host.casefold()

        # Unbracketed IPv6, user-info and ambiguous separators are invalid Host
        # authorities even if a substring would match an allowed host.
        if raw.count(":") > 1:
            return ""
        host, separator, port = raw.partition(":")
        if not host or any(character in host for character in "@[]/\\"):
            return ""
        if separator and not self._valid_port(port):
            return ""
        try:
            return _normalize_dns_or_ipv4_host(host)
        except ValueError:
            return ""

    @staticmethod
    def _valid_port(value: str) -> bool:
        return 1 <= len(value) <= 5 and value.isascii() and value.isdecimal() and 1 <= int(value) <= 65535

    def _host_allowed(self) -> bool:
        return self._normalized_host() in self.server.allowed_hosts

    def _single_header(self, name: str) -> str:
        values = self.headers.get_all(name) or []
        if len(values) != 1:
            raise IndexHTTPBoundaryError(f"{name} must be supplied exactly once")
        if _contains_unicode_control(values[0]):
            raise IndexHTTPBoundaryError(f"{name} contains unsupported control characters")
        value = values[0].strip()
        if not value:
            raise IndexHTTPBoundaryError(f"{name} must not be empty")
        return value

    def _authenticate(self) -> tuple[AuthenticatedRequester, str]:
        authorization = self._single_header(SEARCH_IDENTITY_HEADER)
        prefix = f"{SEARCH_IDENTITY_SCHEME} "
        if not authorization.startswith(prefix):
            raise IndexHTTPBoundaryError("requester authentication scheme is unsupported")
        bearer = authorization[len(prefix):]
        if not _valid_bearer(bearer):
            raise IndexHTTPBoundaryError("requester authentication credential is invalid")

        privacy_reference = self._single_header(SEARCH_PRIVACY_HEADER)
        if not _valid_capability_reference(privacy_reference):
            raise IndexHTTPBoundaryError("privacy capability reference is invalid")

        try:
            requester = asyncio.run(self.server.identity_verifier.verify_bearer(bearer))
        except Exception as exc:
            raise IndexHTTPBoundaryError("requester authentication failed") from exc

        if (
            not isinstance(requester, AuthenticatedRequester)
            or not all(isinstance(value, str) for value in (
                requester.requester_id, requester.requester_type, requester.authority
            ))
            or requester.requester_id != SEARCH_INDEX_REQUESTER_ID
            or requester.requester_type != SEARCH_INDEX_REQUESTER_TYPE
            or requester.authority != SEARCH_IDENTITY_AUTHORITY
        ):
            raise IndexHTTPBoundaryError("authenticated requester is not authorized for Index delegation")

        verification_request = PrivacyCapabilityVerificationRequest(
            capability_reference=privacy_reference,
            requester_id=requester.requester_id,
        )
        try:
            verification = asyncio.run(
                self.server.privacy_verifier.verify_reference(verification_request)
            )
        except Exception as exc:
            raise IndexHTTPBoundaryError("privacy authorization verification failed") from exc

        if not (
            isinstance(verification, PrivacyCapabilityVerification)
            and verification.authorized is True
            and verification.consumed is True
            and isinstance(verification.requester_id, str)
            and isinstance(verification.verification_consumer_id, str)
            and verification.requester_id == requester.requester_id
            and verification.verification_consumer_id == SEARCH_VERIFICATION_CONSUMER_ID
        ):
            raise IndexHTTPBoundaryError("privacy authorization is not valid for this Search execution")
        return requester, privacy_reference

    def _read_search_request(self) -> tuple[str, int]:
        content_types = self.headers.get_all("Content-Type") or []
        if len(content_types) != 1 or _contains_unicode_control(content_types[0]) or content_types[0].split(";", 1)[0].strip().casefold() != "application/json":
            raise IndexHTTPBoundaryError("content type must be supplied exactly once as application/json")
        if self.headers.get_all("Transfer-Encoding"):
            raise IndexHTTPBoundaryError("transfer encoding is not supported")
        content_lengths = self.headers.get_all("Content-Length") or []
        if len(content_lengths) != 1:
            raise IndexHTTPBoundaryError("content length must be supplied exactly once")
        if _contains_unicode_control(content_lengths[0]):
            raise IndexHTTPBoundaryError("content length contains unsupported controls")
        raw_length = content_lengths[0].strip()
        if not raw_length or len(raw_length) > 5 or not raw_length.isascii() or not raw_length.isdecimal():
            raise IndexHTTPBoundaryError("content length is invalid")
        content_length = int(raw_length)
        if content_length < 2 or content_length > SEARCH_MAX_REQUEST_BYTES:
            raise IndexHTTPBoundaryError("request body size is invalid")

        try:
            body = self.rfile.read(content_length)
            if len(body) != content_length:
                raise IndexHTTPBoundaryError("request body length is incomplete")
            payload = _json_loads_strict(body)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError, OSError) as exc:
            raise IndexHTTPBoundaryError("request body is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise IndexHTTPBoundaryError("request body must be a JSON object")
        if set(payload) != {"query", "category", "limit"}:
            raise IndexHTTPBoundaryError("request body fields are unsupported")

        query = payload["query"]
        category = payload["category"]
        limit = payload["limit"]
        if not isinstance(query, str):
            raise IndexHTTPBoundaryError("query must be a string")
        # Reject original untrusted text before normalization. Unicode Cc
        # includes C0 and DEL/C1 controls; surrogates and bidi-format controls are
        # also rejected so untrusted query text cannot visually reorder later
        # presentation merely because it survives whitespace normalization.
        if len(query) > SEARCH_MAX_QUERY_CHARS or _contains_unicode_control(query):
            raise IndexHTTPBoundaryError("query contains unsupported control characters")
        query = query.strip()
        if not query or len(query) > SEARCH_MAX_QUERY_CHARS:
            raise IndexHTTPBoundaryError("query is empty or too large")
        if category != "general":
            raise IndexHTTPBoundaryError("only the initial general category is accepted")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= SEARCH_MAX_RESULTS:
            raise IndexHTTPBoundaryError("limit is outside the accepted range")
        return query, limit

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._send_json(421, {"error": "misdirected_request"})
            return
        if self.path == SEARCH_HEALTH_ENDPOINT:
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "goreecloud-search",
                    "version": __version__,
                    "lifecycle": "development",
                },
            )
            return
        if self.path == SEARCH_READINESS_ENDPOINT:
            status = 200 if self.server.ready else 503
            self._send_json(
                status,
                {
                    "status": "ready" if self.server.ready else "not_ready",
                    "service": "goreecloud-search",
                    "version": __version__,
                    "lifecycle": "development",
                },
            )
            return
        if self.path == SEARCH_STATUS_ENDPOINT:
            self._send_json(
                200,
                {
                    "service": "goreecloud-search",
                    "version": __version__,
                    "lifecycle": "development",
                    "production_accepted": False,
                    "capability_evidence": [capability_record()],
                },
            )
            return
        if self.path == SEARCH_QUERY_ENDPOINT:
            self._send_json(405, {"error": "method_not_allowed"})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._host_allowed():
            self._send_json(421, {"error": "misdirected_request"})
            return
        if self.path != SEARCH_QUERY_ENDPOINT:
            self._send_json(404, {"error": "not_found"})
            return

        try:
            query, limit = self._read_search_request()
        except IndexHTTPBoundaryError:
            self._send_json(400, {"error": "invalid_search_request"})
            return

        try:
            self._authenticate()
        except IndexHTTPBoundaryError:
            self._send_json(401, {"error": "authorization_required"}, authenticate=True)
            return

        try:
            response = asyncio.run(
                self.server.search_core.search_from_index(query, limit=limit)
            )
        except SourcePlanningError:
            self._send_json(503, {"error": "search_unavailable"})
            return
        except Exception:
            self._send_json(503, {"error": "search_unavailable"})
            return

        if response.execution.availability is SearchAvailability.UNAVAILABLE:
            self._send_json(503, {"error": "search_unavailable"})
            return

        results = [
            {
                "title": item.result.title,
                "url": item.result.canonical_url,
                "snippet": item.result.snippet or None,
                "searchScore": int(round(item.score * 1000)),
            }
            for item in response.results[:limit]
        ]
        self._send_json(
            200,
            {
                "apiVersion": SEARCH_API_VERSION,
                "query": query,
                "category": "general",
                "results": results,
                "degraded": response.execution.availability is SearchAvailability.DEGRADED,
            },
        )

    def do_PUT(self) -> None:
        self._send_method_not_allowed()

    def do_DELETE(self) -> None:
        self._send_method_not_allowed()

    def do_PATCH(self) -> None:
        self._send_method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._send_method_not_allowed()

    def do_TRACE(self) -> None:
        self._send_method_not_allowed()

    def do_CONNECT(self) -> None:
        self._send_method_not_allowed()

    def do_HEAD(self) -> None:
        self._send_method_not_allowed(write_body=False)


def create_index_http_server(
    core: SearchCore,
    identity_verifier: RequesterIdentityVerifier,
    privacy_verifier: PrivacyCapabilityVerifier,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "search.goreecloud.com"),
    authority_transports_ready: bool = False,
) -> SearchIndexHTTPServer:
    """Create the bounded Index-originated Search HTTP server.

    This factory does not start the server, configure TLS, provide credentials,
    register a provider, or establish deployment/production acceptance.
    """

    return SearchIndexHTTPServer(
        core,
        identity_verifier,
        privacy_verifier,
        host=host,
        port=port,
        allowed_hosts=allowed_hosts,
        authority_transports_ready=authority_transports_ready,
    )
