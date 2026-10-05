from __future__ import annotations

from contextlib import contextmanager
import http.client
import json
import socket
import threading
import unittest
from unittest.mock import AsyncMock, patch

from goreecloud_search import (
    ProviderDescriptor,
    ProviderOrigin,
    ProviderSearchBatch,
    ResultCandidate,
    SearchCategory,
    SearchCore,
)
from goreecloud_search.index_http_api import (
    AuthenticatedRequester,
    PrivacyCapabilityVerification,
    SEARCH_DESTINATION,
    SEARCH_INDEX_REQUESTER_ID,
    SEARCH_PROCESSING_ZONE,
    SEARCH_QUERY_CAPABILITY_ID,
    SEARCH_RESOURCE_ID,
    SEARCH_RETENTION_MODE,
    SEARCH_VERIFICATION_CONSUMER_ID,
    capability_record,
    create_index_http_server,
)


class FakeProvider:
    def __init__(self, name: str, origin: ProviderOrigin, *, fail: bool = False) -> None:
        self._descriptor = ProviderDescriptor(
            name=name,
            origin=origin,
            categories=frozenset({SearchCategory.GENERAL}),
            priority=10,
        )
        self.fail = fail
        self.calls = 0

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    async def search(self, query, *, limit: int) -> ProviderSearchBatch:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        return ProviderSearchBatch(
            candidates=(
                ResultCandidate(
                    title=f"{self._descriptor.name} result",
                    url="https://example.com/result?utm_source=test",
                    snippet="goreecloud authenticated result",
                    provider=self._descriptor.name,
                ),
            )[:limit],
        )


class IdentityVerifier:
    def __init__(self, *, requester_id: str = SEARCH_INDEX_REQUESTER_ID) -> None:
        self.requester_id = requester_id
        self.credentials: list[str] = []

    async def verify_bearer(self, bearer_credential: str) -> AuthenticatedRequester:
        self.credentials.append(bearer_credential)
        return AuthenticatedRequester(
            requester_id=self.requester_id,
            requester_type="application",
        )


class PrivacyVerifier:
    def __init__(self, *, authorized: bool = True) -> None:
        self.authorized = authorized
        self.requests = []

    async def verify_reference(self, request):
        self.requests.append(request)
        return PrivacyCapabilityVerification(
            authorized=self.authorized,
            requester_id=request.requester_id,
            verification_consumer_id=SEARCH_VERIFICATION_CONSUMER_ID,
            consumed=self.authorized,
        )


@contextmanager
def running_server(core, identity=None, privacy=None, *, authority_transports_ready=False):
    server = create_index_http_server(
        core,
        identity or IdentityVerifier(),
        privacy or PrivacyVerifier(),
        host="127.0.0.1",
        port=0,
        authority_transports_ready=authority_transports_ready,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, method: str, path: str, *, headers=None, body: bytes | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, dict(response.getheaders()), payload
    finally:
        connection.close()


def request_with_headers(server, method: str, path: str, headers: list[tuple[str, str]], body: bytes = b""):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    try:
        connection.putrequest(method, path, skip_host=True)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(body)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, payload
    finally:
        connection.close()


class IndexHTTPAPITests(unittest.TestCase):
    def test_allowed_host_configuration_normalizes_and_rejects_empty_values(self) -> None:
        core = SearchCore(provider_adapters=(FakeProvider("external", ProviderOrigin.EXTERNAL),))
        server = create_index_http_server(
            core,
            IdentityVerifier(),
            PrivacyVerifier(),
            host="127.0.0.1",
            port=0,
            allowed_hosts=(" LOCALHOST. ", "[::1]", "BÜCHER.example.", "127.0.0.1"),
        )
        try:
            self.assertEqual(
                frozenset({"localhost", "::1", "xn--bcher-kva.example", "127.0.0.1"}),
                server.allowed_hosts,
            )
        finally:
            server.server_close()

        for invalid_hosts in (
            (),
            (" ",),
            (".",),
            ("...",),
            ("localhost:443",),
            ("[localhost]",),
            ("local host",),
            ("local\u202ehost",),
            ("exa_mple.com",),
            ("-example.com",),
            ("example-.com",),
            ("127.1",),
            ("2130706433",),
            ("0177.0.0.1",),
            ("0x7f.0.0.1",),
            ("example.123",),
            ("example.0x",),
            ("0x",),
            ("1.2.3.4.5",),
            ("faß.de",),
            ("xn--fa-hia.de",),
            ("xn--invalid-.example",),
            ("ab\u200dcd.example",),
            ("example..",),
            ("\nlocalhost",),
            ("[fe80::1%eth0]",),
            (None,),
        ):
            with self.subTest(invalid_hosts=invalid_hosts):
                with self.assertRaises(ValueError):
                    create_index_http_server(
                        core,
                        IdentityVerifier(),
                        PrivacyVerifier(),
                        host="127.0.0.1",
                        port=0,
                        allowed_hosts=invalid_hosts,
                    )

    def test_unicode_allowed_host_matches_ascii_alabel_request_authority(self) -> None:
        core = SearchCore(provider_adapters=(FakeProvider("external", ProviderOrigin.EXTERNAL),))
        server = create_index_http_server(
            core,
            IdentityVerifier(),
            PrivacyVerifier(),
            host="127.0.0.1",
            port=0,
            allowed_hosts=("bücher.example",),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, payload = request_with_headers(
                server,
                "GET",
                "/healthz",
                [("Host", "xn--bcher-kva.example")],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])

    def test_duplicate_and_malformed_host_authorities_fail_closed(self) -> None:
        core = SearchCore(provider_adapters=(FakeProvider("external", ProviderOrigin.EXTERNAL),))
        with running_server(core) as server:
            for hosts in (
                ["127.0.0.1", "localhost"],
                ["localhost:invalid"],
                ["localhost:65536"],
                ["localhost:80:extra"],
                ["localhost@untrusted.invalid"],
                ["[127.0.0.1]"],
                ["[localhost]"],
                ["[search.goreecloud.com]"],
                ["[::1]]"],
                ["localhost:" + "9" * 5000],
                ["[::1]:" + "9" * 5000],
                ["localhost:000080"],
                ["localhost:0"],
                ["localhost:"],
                ["localhost.."],
                ["[fe80::1%eth0]"],
            ):
                with self.subTest(hosts=hosts):
                    status, payload = request_with_headers(
                        server,
                        "GET",
                        "/healthz",
                        [("Host", host) for host in hosts],
                    )
                    self.assertEqual(421, status)
                    self.assertEqual("misdirected_request", payload["error"])

            valid_status, valid_payload = request_with_headers(
                server, "GET", "/healthz", [("Host", "localhost:65535")]
            )
            self.assertEqual(200, valid_status)
            self.assertEqual("ok", valid_payload["status"])

    def test_incomplete_body_times_out_before_authority_or_provider_calls(self) -> None:
        provider = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(provider,))
        with patch("goreecloud_search.index_http_api.SEARCH_REQUEST_TIMEOUT_SECONDS", 0.05):
            with running_server(core, identity, privacy) as server:
                status, payload = request_with_headers(
                    server,
                    "POST",
                    "/api/v1/search",
                    [
                        ("Host", "127.0.0.1"),
                        ("Content-Type", "application/json"),
                        ("Content-Length", "100"),
                        ("Authorization", "Bearer identity_test_token"),
                        ("X-GoreeCloud-Privacy-Capability", "psc_test_reference"),
                    ],
                    b"{",
                )
        self.assertEqual(400, status)
        self.assertEqual("invalid_search_request", payload["error"])
        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, provider.calls)

    def test_controls_in_header_values_fail_before_authority_or_provider_calls(self) -> None:
        provider = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(provider,))
        body = json.dumps({"query": "privacy", "category": "general", "limit": 1}).encode()
        headers = [
            ("Host", "127.0.0.1"),
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Authorization", "Bearer identity_test_token"),
            ("X-GoreeCloud-Privacy-Capability", "psc_test_reference"),
        ]
        with running_server(core, identity, privacy) as server:
            for name, value, expected in (
                ("Host", "localhost\x85", 421),
                ("Content-Type", "application/json\x85", 400),
                ("Content-Length", str(len(body)) + "\x85", 400),
                ("Authorization", "Bearer identity_test_token\x85", 401),
                ("X-GoreeCloud-Privacy-Capability", "psc_test_reference\x85", 401),
            ):
                with self.subTest(header=name):
                    changed = [(n, value if n == name else v) for n, v in headers]
                    status, _ = request_with_headers(server, "POST", "/api/v1/search", changed, body)
                    self.assertEqual(expected, status)
        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, provider.calls)

    def test_valid_json_with_incomplete_declared_length_fails_before_authentication(self) -> None:
        provider = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(provider,))
        body = json.dumps({"query": "privacy", "category": "general", "limit": 1}).encode()
        with running_server(core, identity, privacy) as server:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
            try:
                connection.request("POST", "/api/v1/search", body=body, headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body) + 1),
                    "Authorization": "Bearer identity_test_token",
                    "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                })
                connection.sock.shutdown(socket.SHUT_WR)
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(400, response.status)
                self.assertEqual({"error": "invalid_search_request"}, payload)
            finally:
                connection.close()
        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, provider.calls)

    def test_unsupported_methods_validate_host_before_method_response(self) -> None:
        provider = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(provider,))

        with running_server(core, identity, privacy) as server:
            for method in ("PUT", "DELETE", "PATCH", "OPTIONS", "TRACE"):
                with self.subTest(method=method):
                    bad_status, bad_payload = request_with_headers(
                        server,
                        method,
                        "/api/v1/search",
                        [("Host", "untrusted.invalid")],
                    )
                    self.assertEqual(421, bad_status)
                    self.assertEqual("misdirected_request", bad_payload["error"])

                    good_status, _, good_payload = request(
                        server,
                        method,
                        "/api/v1/search",
                    )
                    self.assertEqual(405, good_status)
                    self.assertEqual("method_not_allowed", good_payload["error"])

        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, provider.calls)

    def test_ambiguous_json_and_length_headers_fail_before_authentication(self) -> None:
        provider = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(provider,))
        body = json.dumps({"query": "goreecloud", "category": "general", "limit": 1}).encode()
        required = [
            ("Host", "127.0.0.1"),
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Authorization", "Bearer identity_test_token"),
            ("X-GoreeCloud-Privacy-Capability", "psc_test_reference"),
        ]
        with running_server(core, identity, privacy) as server:
            for extras in (
                [("Content-Type", "application/json")],
                [("Content-Length", str(len(body)))],
                [("Content-Length", "9" * 5000)],
                [("Transfer-Encoding", "chunked")],
            ):
                with self.subTest(extras=extras):
                    status, payload = request_with_headers(
                        server, "POST", "/api/v1/search", required + extras, body
                    )
                    self.assertEqual(400, status)
                    self.assertEqual("invalid_search_request", payload["error"])
        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, provider.calls)

    def test_capability_is_production_shaped_but_not_production_accepted(self) -> None:
        record = capability_record()

        self.assertEqual("search.query", record["id"])
        self.assertEqual("POST", record["preferred_method"])
        self.assertEqual("json_body", record["preferred_query_transport"])
        self.assertTrue(record["privacy_authorization_required"])
        self.assertEqual("required", record["privacy_authorization_enforcement"])
        self.assertTrue(record["authenticated_requester_required"])
        self.assertFalse(record["production_accepted"])
        self.assertEqual(
            "goreecloud.search-index-delegation.v1",
            record["index_delegation_contract_version"],
        )
        self.assertEqual("external_only", record["index_delegation_mode"])
        self.assertFalse(record["index_provider_reentry_allowed"])
        self.assertFalse(record["index_delegation_fallback_allowed"])

    def test_status_and_health_are_non_secret_and_readiness_requires_external_provider(self) -> None:
        core = SearchCore(provider_adapters=(FakeProvider("local", ProviderOrigin.LOCAL),))
        with running_server(core, authority_transports_ready=True) as server:
            health_status, _, health = request(server, "GET", "/healthz")
            ready_status, _, ready = request(server, "GET", "/readyz")
            status_code, _, status = request(server, "GET", "/api/v1/status")

        self.assertEqual(200, health_status)
        self.assertEqual("ok", health["status"])
        self.assertEqual(503, ready_status)
        self.assertEqual("not_ready", ready["status"])
        self.assertEqual(200, status_code)
        self.assertEqual("development", status["lifecycle"])
        self.assertFalse(status["production_accepted"])
        self.assertEqual(["search.query"], [item["id"] for item in status["capability_evidence"]])

    def test_readiness_requires_explicit_authority_transport_acceptance(self) -> None:
        core = SearchCore(provider_adapters=(FakeProvider("external", ProviderOrigin.EXTERNAL),))

        with running_server(core) as blocked_server:
            blocked_status, _, blocked = request(blocked_server, "GET", "/readyz")

        with running_server(core, authority_transports_ready=True) as accepted_server:
            accepted_status, _, accepted = request(accepted_server, "GET", "/readyz")

        self.assertEqual(503, blocked_status)
        self.assertEqual("not_ready", blocked["status"])
        self.assertEqual(200, accepted_status)
        self.assertEqual("ready", accepted["status"])

    def test_missing_authority_fails_before_verifiers_and_provider(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(external,))

        with running_server(core, identity, privacy) as server:
            body = json.dumps({"query": "goreecloud", "category": "general", "limit": 3}).encode()
            status, headers, payload = request(
                server,
                "POST",
                "/api/v1/search",
                headers={"Content-Type": "application/json"},
                body=body,
            )

        self.assertEqual(401, status)
        self.assertEqual("Bearer", headers["WWW-Authenticate"])
        self.assertEqual("authorization_required", payload["error"])
        self.assertEqual([], identity.credentials)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, external.calls)

    def test_authenticated_request_consumes_privacy_reference_and_executes_external_only(self) -> None:
        index = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX)
        local = FakeProvider("local", ProviderOrigin.LOCAL)
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(index, local, external))

        with running_server(core, identity, privacy) as server:
            body = json.dumps({"query": "goreecloud", "category": "general", "limit": 3}).encode()
            status, _, payload = request(
                server,
                "POST",
                "/api/v1/search",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer identity_test_token",
                    "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                },
                body=body,
            )

        self.assertEqual(200, status)
        self.assertEqual(["identity_test_token"], identity.credentials)
        self.assertEqual(1, len(privacy.requests))
        verification = privacy.requests[0]
        self.assertEqual("psc_test_reference", verification.capability_reference)
        self.assertEqual(SEARCH_INDEX_REQUESTER_ID, verification.requester_id)
        self.assertEqual(SEARCH_RESOURCE_ID, verification.resource_id)
        self.assertEqual(SEARCH_QUERY_CAPABILITY_ID, verification.operation)
        self.assertEqual(SEARCH_PROCESSING_ZONE, verification.processing_zone)
        self.assertEqual(SEARCH_DESTINATION, verification.destination)
        self.assertEqual(SEARCH_RETENTION_MODE, verification.retention_mode)
        self.assertEqual(SEARCH_VERIFICATION_CONSUMER_ID, verification.verification_consumer_id)
        self.assertTrue(verification.consume)
        self.assertEqual(0, index.calls)
        self.assertEqual(0, local.calls)
        self.assertEqual(1, external.calls)
        self.assertEqual("1", payload["apiVersion"])
        self.assertEqual("goreecloud", payload["query"])
        self.assertEqual("general", payload["category"])
        self.assertEqual("https://example.com/result", payload["results"][0]["url"])

    def test_wrong_authenticated_requester_fails_before_privacy_and_provider(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier(requester_id="untrusted-client")
        privacy = PrivacyVerifier()
        core = SearchCore(provider_adapters=(external,))

        with running_server(core, identity, privacy) as server:
            body = json.dumps({"query": "goreecloud", "category": "general", "limit": 1}).encode()
            status, _, payload = request(
                server,
                "POST",
                "/api/v1/search",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer identity_test_token",
                    "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                },
                body=body,
            )

        self.assertEqual(401, status)
        self.assertEqual("authorization_required", payload["error"])
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, external.calls)

    def test_privacy_denial_fails_before_provider_execution(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        privacy = PrivacyVerifier(authorized=False)
        core = SearchCore(provider_adapters=(external,))

        with running_server(core, privacy=privacy) as server:
            body = json.dumps({"query": "goreecloud", "category": "general", "limit": 1}).encode()
            status, _, payload = request(
                server,
                "POST",
                "/api/v1/search",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer identity_test_token",
                    "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                },
                body=body,
            )

        self.assertEqual(401, status)
        self.assertEqual("authorization_required", payload["error"])
        self.assertEqual(0, external.calls)

    def test_malformed_identity_records_fail_before_privacy_and_provider(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        identity = IdentityVerifier()
        privacy = PrivacyVerifier()
        identity.verify_bearer = AsyncMock()
        core = SearchCore(provider_adapters=(external,))
        body = json.dumps({"query": "privacy", "category": "general", "limit": 1}).encode()
        with running_server(core, identity, privacy) as server:
            for malformed in (
                None,
                {"requester_id": SEARCH_INDEX_REQUESTER_ID, "requester_type": "application"},
                AuthenticatedRequester(requester_id=None, requester_type="application"),
                AuthenticatedRequester(requester_id=SEARCH_INDEX_REQUESTER_ID, requester_type=True),
                AuthenticatedRequester(requester_id=SEARCH_INDEX_REQUESTER_ID, requester_type="application", authority=None),
            ):
                with self.subTest(record=malformed):
                    identity.verify_bearer.return_value = malformed
                    status, _, payload = request(server, "POST", "/api/v1/search", body=body, headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer identity_test_token",
                        "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                    })
                    self.assertEqual(401, status)
                    self.assertEqual({"error": "authorization_required"}, payload)
        self.assertEqual([], privacy.requests)
        self.assertEqual(0, external.calls)

    def test_privacy_requires_typed_record_and_explicit_boolean_authorization(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        privacy = PrivacyVerifier()
        privacy.verify_reference = AsyncMock()
        core = SearchCore(provider_adapters=(external,))
        body = json.dumps({"query": "privacy", "category": "general", "limit": 1}).encode()
        with running_server(core, privacy=privacy) as server:
            for malformed in (
                None,
                {"authorized": True, "consumed": True, "requester_id": SEARCH_INDEX_REQUESTER_ID, "verification_consumer_id": SEARCH_VERIFICATION_CONSUMER_ID},
                PrivacyCapabilityVerification("false", SEARCH_INDEX_REQUESTER_ID, SEARCH_VERIFICATION_CONSUMER_ID, "false"),
                PrivacyCapabilityVerification(1, SEARCH_INDEX_REQUESTER_ID, SEARCH_VERIFICATION_CONSUMER_ID, True),
                PrivacyCapabilityVerification(True, SEARCH_INDEX_REQUESTER_ID, SEARCH_VERIFICATION_CONSUMER_ID, 1),
                PrivacyCapabilityVerification(True, None, SEARCH_VERIFICATION_CONSUMER_ID, True),
                PrivacyCapabilityVerification(True, SEARCH_INDEX_REQUESTER_ID, None, True),
                PrivacyCapabilityVerification(True, SEARCH_INDEX_REQUESTER_ID, SEARCH_VERIFICATION_CONSUMER_ID, False),
            ):
                with self.subTest(record=malformed):
                    privacy.verify_reference.return_value = malformed
                    status, _, payload = request(server, "POST", "/api/v1/search", body=body, headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer identity_test_token",
                        "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                    })
                    self.assertEqual(401, status)
                    self.assertEqual({"error": "authorization_required"}, payload)
        self.assertEqual(0, external.calls)

    def test_invalid_provider_batch_or_url_returns_generic_error_and_recovers(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        valid = ResultCandidate(title="valid result", url="https://example.com/result", snippet="safe", provider="external")
        external.search = AsyncMock()
        core = SearchCore(provider_adapters=(external,))
        body = json.dumps({"query": "privacy", "category": "general", "limit": 1}).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer identity_test_token",
            "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
        }
        with running_server(core) as server:
            for invalid in (
                ProviderSearchBatch(candidates=(valid, valid)),
                ProviderSearchBatch(candidates=(ResultCandidate(
                    title="invalid result", url="javascript:private", snippet="safe", canonical_url="https://example.com/alias", provider="external"
                ),)),
            ):
                with self.subTest(batch=invalid):
                    external.search.return_value = invalid
                    status, _, payload = request(server, "POST", "/api/v1/search", body=body, headers=headers)
                    self.assertEqual(503, status)
                    self.assertEqual({"error": "search_unavailable"}, payload)
                    external.search.return_value = ProviderSearchBatch(candidates=(valid,))
                    recovered_status, _, recovered = request(server, "POST", "/api/v1/search", body=body, headers=headers)
                    self.assertEqual(200, recovered_status)
                    self.assertEqual("https://example.com/result", recovered["results"][0]["url"])

    def test_query_control_characters_fail_closed_before_provider_execution(self) -> None:
        for query in (
            "goreecloud\nmail",
            "goreecloud\tmail",
            "goreecloud\rmail",
            "goreecloud\x7fmail",
            "goreecloud\u0085mail",
            "goreecloud\u009fmail",
            "goreecloud\u061cmail",
            "goreecloud\u202email",
            "goreecloud\u2066mail",
            "\ngoreecloud",
            "goreecloud\n",
            "\tgoreecloud",
            "goreecloud\r",
            "\u0085goreecloud",
            "goreecloud\ud800",
            "goreecloud\udfff",
            " " * 2048 + "goreecloud",
        ):
            with self.subTest(query=repr(query)):
                external = FakeProvider("external", ProviderOrigin.EXTERNAL)
                core = SearchCore(provider_adapters=(external,))
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer identity_test_token",
                    "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
                }

                with running_server(core) as server:
                    body = json.dumps({"query": query, "category": "general", "limit": 1}).encode()
                    status, _, payload = request(
                        server,
                        "POST",
                        "/api/v1/search",
                        headers=headers,
                        body=body,
                    )

                self.assertEqual(400, status)
                self.assertEqual("invalid_search_request", payload["error"])
                self.assertEqual(0, external.calls)

    def test_search_get_and_unbounded_or_extra_json_fields_fail_closed(self) -> None:
        external = FakeProvider("external", ProviderOrigin.EXTERNAL)
        core = SearchCore(provider_adapters=(external,))
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer identity_test_token",
            "X-GoreeCloud-Privacy-Capability": "psc_test_reference",
        }

        with running_server(core) as server:
            get_status, _, _ = request(server, "GET", "/api/v1/search")
            extra_body = json.dumps(
                {"query": "goreecloud", "category": "general", "limit": 1, "local_results": ["secret"]}
            ).encode()
            post_status, _, payload = request(
                server,
                "POST",
                "/api/v1/search",
                headers=headers,
                body=extra_body,
            )

        self.assertEqual(405, get_status)
        self.assertEqual(400, post_status)
        self.assertEqual("invalid_search_request", payload["error"])
        self.assertEqual(0, external.calls)


if __name__ == "__main__":
    unittest.main()
