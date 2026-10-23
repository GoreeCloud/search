# GoreeCloud Search — deterministic result-quality benchmark

**Scope:** Development source check only. This benchmark neither runs providers
nor qualifies a release. It complements—not replaces—the seven-provider
category-adapter tests and 24-adapter provider-qualification report gate.

## Why this gate exists

A visually full search results page can still be poor: dozens of copies of the
same asset, one provider silently failing, or many top results missing the
known-relevant content. The first owned fusion primitive already deduplicates
URLs and image assets and ranks source votes. This CLI gives that behavior a
repeatable, privacy-preserving quality gate using **pinned synthetic data**.

Run from the Search repository root:

```bash
python3 -m scripts.search_quality_benchmark \
  tests/goreecloud/fixtures/search_quality/images_multi_source.json
python3 -m unittest discover -s tests/goreecloud -p 'test_search_quality_benchmark.py' -v
```

The fixture contains two invented sources and six generated image cards. Two
URLs refer to duplicate image assets even though their hosting pages differ.
Expected outcome: **four distinct images, two duplicate cards collapsed, two
contributing sources, three relevant assets in top ten, 100% recall of three
prejudged relevant assets, no missing original/media identity**.

This is an offline contract assertion. The invented sources are **not** Google,
Bing, Brave or any other live provider. These synthetic metrics are **not** a
measurement of actual web, shopping or image quality.

## Evidence contract and pass/fail semantics

Each fixture is bounded and has exactly five root fields:

| Field | Meaning |
| --- | --- |
| `development_only` | Must be `true`; never infer live-provider or public release approval. |
| `category` | One implemented fusion category: `web`, `images`, `videos`, `news`. Shopping, Maps and More are roadmap only. |
| `sources` | Unique sanitized source IDs with explicit `ok`, `empty`, `timeout`, `rate_limited`, `access_denied` or `error` states. Only `ok` can contain candidate cards; errors may not disguise partial results as success. |
| `relevant` | A small, hand-judged set of result URLs; for Images, the asset URLs rather than hosting-page URLs. |
| `gates` | Minimum diversity, unique result count, relevant@10, recall@10, maximum images without original-media IDs, and optional full-source-health requirement. |

The evaluator emits only aggregate counts, source IDs and fixed failure codes:

- `distinct_results` and `collapsed_duplicates` show how much the fusion
  engine truly adds rather than duplicating cards. `contributing_sources`
  counts distinct sources with at least one vote, not simply configured names.
- `failed_sources` and `empty_sources` distinguish upstream unavailability
  from a valid zero-result response. Missing source diversity fails a configured
  gate even if one source has enough cards to fill the page.
- `missing_image_media_identity` catches image cards that cannot be reliably
  deduplicated because no media URL was supplied. The example allows zero.
- `relevant_at_10`, `recall_percent_at_10`, `precision_percent_at_10`, and
  `reciprocal_rank_at_10` check the ranking of a fixed relevance corpus. A
  recalled result elsewhere beyond top ten does not satisfy the top-ten gate.

An executable gate requires positive minimum relevance, diversity, results and
recall thresholds; zero-threshold "success" cannot bypass the quality checks.
No user query, URL, title, page, media data, file path or provider response
body is included in the CLI output. Unexpected fixture keys (including raw
queries), malformed source identities, unsafe URLs, contradictory source
statuses, duplicate judgments and oversized fixtures are rejected.

CLI exit codes: `0` = all offline fixture gates passed; `1` = legitimate but
poor quality; `2` = malformed/untrusted fixture; `64` = no fixture supplied.
The JSON output always includes `release_qualified: false`.

## Real result coverage still unqualified

As of this Development milestone, users have reported missing Image results
and poor relevance. The existing private Search runtime can show Bing Images
while other image providers may be blocked, broken, rate-limited or disabled by
the selected preset. These are separate cases with different remedies, not a
justification to claim more results than actually arrived.

Before the real user-visible image experience can pass acceptance:

1. Establish provider-by-provider approved use and correct egress, image use,
   cache, redistribution and attribution rights. Google and Bing API product
   changes and Brave terms require up-to-date direct verification.
2. Obtain a repeatable, explicitly approved and appropriately rate-limited
   provider health sample by category. Never evade denials, challenge pages,
   throttling or license limits to make a coverage number pass.
3. In an isolated Development implementation, record **sanitized counts** of
   selected, contacted, successful, empty, denied, timed out and invalid-card
   providers; keep all user queries and image links out of telemetry.
4. Build a lawfully obtained, privacy-reviewed and pinned relevance corpus
   with human judgments. Re-run this exact algorithm against admitted provider
   fixtures with evaluated diversity, asset dedup, recall and ranking evidence.
5. Verify the real Web/Images/Videos/News UI renders truly fused cards,
   distinct unavailable-source state, keyboard/touch accessibility, responsive
   loading and image fallback, using exact candidate screenshots and browser
   tests. Shopping and Maps require separate implemented contracts.
6. Finish privacy, abuse/rate controls, security, native OS packaging, release
   provenance, rollbacks and actual ingress/user acceptance; do not infer
   public readiness or Anchor status from offline quality checks.

No public traffic, NetBird policy, deployed image, API credentials, external
provider request or persistent user data is touched by this benchmark.
