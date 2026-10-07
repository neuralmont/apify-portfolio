# Shopify Products Scraper validation report

Observation date: 2026-10-07. This is a bounded source and packaging check, not a demand, freshness, or longitudinal-reliability study. The Actor was published as a paid beta on 2026-10-07; no schedule was created and the recorded runs are owner/test runs.

## Source decision

Individual product URLs use Shopify's documented unauthenticated Ajax Product API, `/{locale}/products/{handle}.js`. Shopify documents presentment-currency behavior and a maximum of 250 variants. The implementation normalizes the observed Ajax integer minor-unit values to major units and records the source unit and currency context.

Store URLs use the observed unauthenticated `/products.json?limit=N&page=N` storefront convention. It is not presented as a current official Shopify API contract. The Actor bounds requests, counts every source row returned, deduplicates by store and product ID, stops at a global cap, and reports that catalog coverage is bounded rather than complete. A shop-specific Storefront GraphQL token is not required or accepted in v1.

## Live observations

| Input/cohort | Result | Measured evidence |
| --- | --- | --- |
| Allbirds, ColourPop, Death Wish Coffee, UNTUCKit, Kylie Cosmetics store URLs | 5 successful bounded catalog retrievals | 10 delivered records, 50 fetched, 18 requests, 0 retries, 5,732,298 bytes, 1.909 seconds; asynchronous sample is not representative |
| Gymshark store URL | Failed honestly | HTTP 403 from observed `/products.json`; no records delivered; deterministic response was not retried unchanged |
| UNTUCKit individual product | Success | 1 record; product `7672658559054`; 3 requests; 24,765 bytes; 0.705 seconds; USD observed; first variant normalized to 88.0 |
| UNTUCKit catalog, `maxProducts=300` | Successful capped extraction | 300 delivered, 411 source rows counted, 2 catalog pages, 4 requests, 3,771,016 bytes, 2.042 seconds; `cap_truncated=true`, `pagination_complete=false` |

The multi-page observation is useful for pagination behavior, not a claim that 300 products represent the store. The endpoint returned more rows than the final requested allowance on page 2; the Actor counted those source rows and retained only the global cap.

Sanitized evidence is in [evidence/live_validation_20261007.json](evidence/live_validation_20261007.json). The reproducible extraction commands were the `shopify_actor.core.extract` invocations saved under `/private/tmp/shopify-*-final2.json`; committed evidence intentionally omits bulky raw catalogs.

## Packaging and tests

From `actors/shopify-products-scraper`:

```text
/private/tmp/shopify-actor-venv/bin/python -m pytest -q tests
14 passed in 0.53s
python -m json.tool .actor/input_schema.json
python -m json.tool .actor/output_schema.json
python -m json.tool .actor/dataset_schema.json
```

The isolated environment uses Python 3.11.14 and `apify==4.0.2`. The local PPE script exercised the real SDK charging manager and local storage:

| Case | Requested | Simulated budget | Dataset rows | `product-record` events | Exit | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Sufficient | 3 | $10 | 3 | 3 | 0 | complete |
| Partial limit | 3 | $4 | 2 | 2 | 0 | incomplete, spending-limit error preserved |
| Exact limit | 2 | $4 | 2 | 2 | 0 | complete, graceful limit stop |

The local SDK also emitted two/three synthetic `apify-default-dataset-item` events because local test mode defaults to simulated $1 events. Those are test-account artifacts, not product charges, and do not verify a future Console price of $0.003.

## Correction pass from commit `81ad95e`

The focused regression suite now reports **20 passed**. `RUN_SUMMARY` store/product outcomes are count/status/coverage/diagnostic objects only; a partial spending-limit test confirms no `records` arrays survive summary persistence. Collection is deterministic and sequential: the shared global cap is applied before opening later inputs, skipped inputs are listed, final-page allowance is used in the request, and repeated or duplicate-only pages fail with preserved partial output.

Final private build: `CzeJQMFtFqxcuqGug` (`0.1.6`) for Actor `6p2A8KHhUDOXewSXQ`, from source commit `81ad95e`.

| Check | Run | Status | Delivered/dataset rows | Diagnostics | Runtime / usage |
| --- | --- | --- | ---: | --- | --- |
| Individual product | `qxHMUxq8hIYk48KyS` | SUCCEEDED | 1 / 1 | none | 3.441 s / $0.0008180468088189762 |
| Three-store shared cap (`maxProducts=3`) | `d8gCcwf8Qnjp57yvp` | SUCCEEDED | 3 / 3 | ColourPop and Allbirds skipped after cap | 4.381 s / $0.001028090537700388 |
| UNTUCKit multi-page (`maxProducts=300`) | `Svr22N2SxAvQwl0Eb` | FAILED, partial preserved | 250 / 250; 300 source rows counted | duplicate-only page detected; no product payload in summary | 18.633 s / $0.005124556330705681 |

The multi-page failure is an honest limitation of the observed catalog endpoint: page 2 returned only duplicate IDs. The actor no longer claims complete coverage for that response. The source produced 250 usable records and the default dataset retained them while `RUN_SUMMARY` retained only diagnostics and counts. The three runs were owner/test runs with monetization disabled; usage totals are platform test costs, not customer charges. Sanitized IDs and results are in [evidence/correction_validation_20261007.json](evidence/correction_validation_20261007.json).

## Private Apify smoke verification

The new Actor was created privately as `6p2A8KHhUDOXewSXQ`. Final build `450Vthn9TlQ3X9xCl` (`0.1.4`) succeeded from the committed source tree after the Apify schema validator checks. Smoke runs used the preceding equivalent build `CBzRj7a0143tHlgZK` (`0.1.3`): store input run `cJ0vBiFpCda5DyvWf` succeeded with 3 dataset rows, 4.451 seconds, 63,893,504-byte maximum memory, and $0.001043984722144074 actual platform usage; individual-product run `pbo21ylSTwHCSUKeJ` succeeded with 1 dataset row, 4.070 seconds, 81,461,248-byte maximum memory, and $0.0009557784709003238 actual platform usage. Storage-ID reads confirmed dataset records and `RUN_SUMMARY` outputs. These are owner/test runs, not customer billing, and signed output URLs are intentionally not committed.

Docker verification is blocked locally because `docker` is not installed; Apify's cloud build did build the image successfully. The nested manifest uses `dockerContextDir: ".."` and paths relative to `.actor`; the packaging test and successful cloud build verify those paths. Run `docker build -f actors/shopify-products-scraper/Dockerfile actors/shopify-products-scraper` when Docker is available.

## Suggested beta price and competitor context

The paid-beta price is `$0.0015` per delivered product record (`$1.50/1,000`), including nested variants and no separate diagnostic or summary charge. Platform usage pass-through is off. The saved pricing contains no synthetic dataset-item or Actor-start events.

Public competitor pages checked on 2026-10-07 show materially different scopes and prices: [Hydrafetch](https://apify.com/hydrafetch/shopify-store-products-scraper) advertises from $1.80/1,000 results, [Monty Burrows](https://apify.com/montyburrows/shopify-products) advertises from $0.21/1,000 variants, and [Tenfold Fleet](https://apify.com/tenfoldfleet/shopify-products-scraper) advertises from $0.80/1,000 products. These are not directly comparable units. The proposed price is a review hypothesis for one product record with nested variants, descriptions, images, timestamps, and direct-product support; it is not a claim of demand or profitability.

## Remaining uncertainties

- `/products.json` availability, pagination semantics, and catalog completeness vary by storefront and are not treated as a universal Shopify guarantee.
- Some stores may block the endpoint or require a custom storefront/API token; those cases remain unsupported in v1.
- Currency is reported only when `/cart.js` exposes it; USD is never assumed.
- `available` is a boolean source signal, not inventory quantity.
- Apify's build output does not expose a Git SHA automatically for direct CLI deployment; this report records the source SHA supplied to the final build.

## Paid-beta release verification

The customer-facing listing change was committed as `7e5f106` and built privately as `0.1.10`, build `VSEaZGI7v0f19TR8q`, from the reviewed Actor source. The complete suite passed **24 tests**. The Actor was then published at [apify.com/purple_beep_boop/shopify-products-scraper](https://apify.com/purple_beep_boop/shopify-products-scraper) on 2026-10-07. The public page displayed `$1.50 / 1,000 product records`, the updated README, the working example input, the global 5,000 cap, nested variants, and unsupported-store limitations. The public API confirmed `latest` selects build `0.1.10`.

| Private check | Run | Status | Dataset / unique IDs | Charged `product-record` events | Completion |
| --- | --- | --- | ---: | ---: | --- |
| 3 products, budget `$0.0045` | `Xbxw1d4gVw7L4VxMu` | SUCCEEDED, exit 0 | 3 / 3 | 3 | complete |
| 3 products, budget `$0.003` | `cmcp5JmmuQ3tFyVKo` | SUCCEEDED, exit 0 | 2 / 2 | 2 | incomplete; spending-limit diagnostic preserved |
| 2 products, budget `$0.003` | `Yr1KYVAmN3oF5mIMI` | SUCCEEDED, exit 0 | 2 / 2 | 2 | complete; exact-budget delivery |

All three summaries were count/status/diagnostic-only outputs with no product payload arrays. No duplicate, diagnostic, summary, synthetic dataset-item, or Actor-start charges were recorded. Measured platform usage was `$0.0010587413545714484`, `$0.0009638672931061851`, and `$0.0009556037201616499`, respectively; these are owner/test accounting, not customer billing. Full sanitized evidence is in [evidence/release_validation_20261007.json](evidence/release_validation_20261007.json).

## Final pagination and transport pass from commit `601fa21`

The focused suite passed **17 tests**. The private Actor `6p2A8KHhUDOXewSXQ` built successfully as version `0.1.9`, build `cO7dN55vDwS4k0k7Z`, from this commit. Monetization remains disabled. The build also verified the nested Actor packaging and installed `apify==4.0.2` in the cloud image.

| Check | Run | Result | Dataset / unique IDs | Summary and measured usage |
| --- | --- | --- | ---: | --- |
| Individual product | `iuBPmjKRtxg9Vmfzr` | SUCCEEDED, exit 0 | 1 / 1 | 3 requests, 0 retries, 64,297 bytes, 4.831 s, 83,615,744-byte max memory, platform usage `$0.001126311152789328`; requested result complete, full-window coverage not claimed |
| UNTUCKit catalog, `maxProducts=300` | `BuD8Dtpu7m1K9cxfz` | SUCCEEDED, exit 0 | 300 / 300 | 4 requests, 0 retries, 4,256,755 bytes, 17.175 s, 91,660,288-byte max memory, platform usage `$0.004636043386931221`; 411 source rows fetched across 2 pages, 300 delivered, 0 duplicates, `cap_truncated=true`, `pagination_complete=false` |

The 300 catalog records all had unique product IDs and valid `https://www.untuckit.com/products/...` canonical links; a direct HTTPS check of the individual canonical link returned HTTP 200. The source sample is bounded and must not be treated as complete store coverage. The prior exact-build smoke attempts failed before making source requests because Python 3.14 rejected two custom HTTPS-handler assumptions; those failures are retained as diagnostics in [evidence/final_validation_20261007.json](evidence/final_validation_20261007.json), and are not included as successful validation.

The final transport uses the DNS-validated address for the socket connection while retaining the requested hostname for TLS SNI and certificate verification. Redirect targets are prevalidated before following. No IP addresses were hard-coded and TLS verification was not disabled.
