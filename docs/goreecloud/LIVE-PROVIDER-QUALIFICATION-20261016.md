# GoreeCloud Search — live provider qualification

**Lifecycle:** Development, **not Stable**. **Test window:** October 16–17, 2026 (America/Chicago; UTC crossed midnight). **Target:** authorized development checkout on `personal-laptop-ideapad3-01`, with `configs/goreecloud/settings.yml`. **Method:** (1) real provider traffic dispatched by Flask `searx.webapp.test_client`; (2) an additional real, private Granian HTTP listener with loopback POST and real Startpage provider traffic. Only fixed, nonpersonal public search terms were sent. **Not tested:** public ingress, production server, target VPS, TLS/reverse proxy, complete real-browser workflow, or identity authentication. No other providers were enabled.

## Live provider observations

Results are response counts **at the time of this single local test window**, not an availability guarantee. The JSON handler returned HTTP 200 even when upstream engines failed; inspect `unresponsive_engines` as well as `results`.

| Scenario | Results | Reported provider errors | Observation |
| --- | ---: | ---: | --- |
| Brave web; fixed synthetic verification phrase | 0 | 1 | HTTP error on outbound request |
| Startpage web; fixed synthetic verification phrase | 0 | 0 | Empty response, not sufficient to diagnose provider |
| Qwant web; fixed synthetic verification phrase | 0 | 1 | Provider error |
| Default federated web; fixed synthetic verification phrase | 0 | 2 | No results returned |
| Brave web; `python programming` | 0 | 1 | HTTP **429** rate limited |
| Startpage web; `python programming` | **10** | 0 | Live results returned |
| Qwant web; `python programming` | 0 | 1 | **Access denied** |
| Qwant images; `python programming` | 0 | 1 | **Access denied**; may also be temporarily suspended |
| Startpage images; `python programming` | **50** | 0 | Live image results returned |
| Startpage news; `python programming` | **8** | 0 | Live news results returned |
| Default federated web; `python programming` | **10** | 2 | Results represented Startpage only; Brave and Qwant failed |
| Startpage web HTML; `python programming` | — | — | HTTP 200, GoreeCloud-branded HTML, 46,592 response bytes, private `no-store` cache header |

The Startpage Web/Images/News JSON responses and federated Web response also carried `Cache-Control: private, no-store, max-age=0` and the exact selected-source metadata. Counts may vary between attempts. No traffic should be redirected through an unapproved provider to work around Brave or Qwant access restrictions; no CAPTCHA or access-denial bypass was attempted.

## Real Granian HTTP integration test

An additional, independently executed process started the installed Granian server with the GoreeCloud private profile on an OS-chosen ephemeral port. The actual socket list (`ss`) confirmed that **every listener** was bound to `127.0.0.1:<ephemeral port>`, not a wildcard interface. After a real GET home-page readiness check, a loopback HTTP **POST** to `/search` using `python programming`, `engines=startpage` and `format=json` returned **HTTP 200, 10 live results, 0 unresponsive engines**, and selected source `['startpage']`. The response included a `no-store` cache directive. The disposable Granian process group was then terminated and reaped successfully. This is a verified real HTTP/socket + approved external provider path, without VPS contact or public exposure.

## Privacy defect identified and corrected

The first Brave network error logged a query-bearing upstream GET URL via `searx/network/network.py`, even though the provider adapter's separate logging tests passed. This would expose search terms if real user queries were processed. In [network redaction commit ab43cbe](https://github.com/GoreeCloud/search/commit/ab43cbe306d8a82b3ac05192f45345fe20cff352) both the error and verbose HTTP response logs were changed to retain only method and numeric status, not request URLs. A new [network logger regression test](https://github.com/GoreeCloud/search/commit/6a80f82612029ecf3a0fb705a0e1a6f92b91d593) checks both paths against a synthetic marker. A subsequent live Brave HTTP 429 logged only `HTTP Request failed: GET status=429`. This is a **specific corrected leakage path**, not a full security or query-redaction audit.

## Independent verification and limits

- Local development checkout with the redaction change: **145/145** GoreeCloud `unittest` cases passed, including the new logger regression test.
- At [privacy-regression integration commit 6a80f826](https://github.com/GoreeCloud/search/commit/6a80f82612029ecf3a0fb705a0e1a6f92b91d593), [push CI 39004735827](https://github.com/GoreeCloud/search/actions/runs/39004735827) and [PR CI 39004737665](https://github.com/GoreeCloud/search/actions/runs/39004737665) both passed; the workflow matrix runs Python 3.10/3.12, synthetic Chromium browser and private Granian listener checks. These CI jobs do **not** contact real providers.
- Development startup emitted upstream SQLite multi-thread warnings and a missing `configs/goreecloud/limiter.toml` warning. They are still unresolved production gates. Application import under a new secret also warned that development SQLite caches were reset; repeated test startup must use isolated disposable caches and deterministic cleanup before promotion.
- The multi-provider result validates **partial availability and failure tolerance** on this laptop, not Brave or Qwant reliability, broad query relevance, external image-proxy safety, login/limiting, device accessibility, staging soak, target SQLite ABI/disk recovery, or rollback.
- In addition to the CI/private-listener and in-process provider tests, an actual local Granian HTTP socket with a real Startpage POST was separately verified, as described above. Public proxy/auth, production load and all-provider success are still untested.

**Next qualification:** resolve provider access policies without bypassing blocks; add repeatable, opt-in, synthetic, loopback live probes for all approved source/category adapters; test sustained all-provider Granian POST flows, query logging/retention audits, target storage and restart, Glaze/assistive technology, auth/limiter before any public release. Keep the PR draft and the default branch untouched.
