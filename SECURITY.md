# GoreeCloud Search — Security

## Lifecycle

GoreeCloud Search is currently in Development and is not production-qualified.

## Reporting security issues

Do not publish sensitive exploit details, credentials, tokens, private data, or active attack instructions in a public issue.

Use GitHub private vulnerability reporting when it is enabled for this repository, or another approved private GoreeCloud security-reporting channel.

## Current security boundary

Version `0.1.0.dev14` adds a bounded authenticated Index-originated HTTP source boundary around the provider-execution framework, but no deployed or production-accepted network transport. Implemented controls include input validation, deterministic source planning, a fail-closed rule preventing external-provider inclusion in GoreeCloud-only and offline/local modes, pre-execution third-party disclosure budgeting, execution only of plan-approved providers, bounded concurrency and per-provider timeouts, cancellation propagation, failure isolation, provider-provenance validation, strict Search ↔ Index contract-version/pagination validation, conservative result-URL validation, rejection of candidates from undeclared providers, and deterministic ranking that does not invoke network services.

The HTTP boundary rejects missing/duplicate/malformed authentication material, requires the authenticated requester to resolve exactly to `goreecloud-index`, requires a canonical bounded `psc_*` reference, calls the injected Privacy Shield verifier with exact expected resource/purpose/operation/zone/destination/retention claims and `consume=true`, rejects extra JSON fields, keeps query text out of request logs, and invokes only `SearchCore.search_from_index(...)`. Capability discovery explicitly reports `production_accepted=false`.

## TinyFish public-web-only boundary (owner directive — 2026-10-09)

Any TinyFish-backed research, extraction, or browser automation integrated into GoreeCloud Search **MUST** operate only on publicly accessible websites without website authentication. The owner prohibits TinyFish from logging in to websites and from storing passwords. This is a provider-specific implementation requirement; it does not remove the separately governed internal authentication boundary for GoreeCloud Search and GoreeCloud Index.

- **MUST NOT** log in to websites or complete authentication, SSO, OAuth, passkey, MFA, or account-recovery flows, including for GoreeCloud-owned websites.
- **MUST NOT** collect, receive, autofill, transmit, save, or manage passwords, passkeys, tokens, recovery codes, or reusable authentication secrets through TinyFish.
- **MUST NOT** use persistent authenticated browser profiles, imported sessions, saved credentials, authenticated session cookies, or credential-bearing browser storage with TinyFish.
- **MUST** restrict TinyFish tasks to unauthenticated public-web navigation, searching, reading, filtering, and information extraction. A task encountering authentication **MUST** stop or fail closed without trying to log in or bypass access controls.
- **MUST** treat TinyFish as read-only with respect to remote site state: no account changes, purchases, protected submissions, or transactions. Respect access controls and applicable law.
- **MUST** use separately authorized direct integrations or APIs instead of TinyFish when an otherwise permitted task needs authentication.
- **MUST** verify these fail-closed boundaries with tests before enabling any TinyFish integration. This record does not assert that controls or a live TinyFish provider are currently implemented.

GoreeCloud-wide ChatGPT plugin instructions remain owned by the existing canonical Drive record **Instructions — ChatGPT Plugins.docx**. This repository section describes only the corresponding Search implementation boundary; it does not replace the central governance document.

## Future requirements

Before network-capable or privileged service operation is production-accepted, Search must implement and verify applicable:

- GoreeCloud Identity authentication and authorization.
- Privacy Shield permitted-use enforcement.
- Wardveil Security trust and protection controls.
- Secret separation and secure configuration.
- Rate limiting and abuse resistance.
- Stronger provider sandboxing/isolation plus retry, rate, cost, and abuse controls beyond the implemented timeout/cancellation foundation.
- Dependency and artifact integrity.
- Security testing and evidence.

## Authenticated Index Delegation Candidate — 2026-09-21

The Development source now rejects Index HTTP query execution unless injected producer-authoritative GoreeCloud Identity and Privacy Shield verifiers approve the expected `goreecloud-index` application identity and the one-operation capability reference. Request structure is validated before the capability is consumed, so malformed bodies cannot burn a valid single-use reference. Credentials and capability references are not returned in responses or ordinary request logs.

This is source/CI evidence only. No production Identity verifier, Privacy Shield verifier transport, provider credential, reverse proxy, deployment, production security acceptance, or Stable qualification is established.
