# Shopify Products Scraper validation report

Observation date: 2026-10-07. This is a bounded source and packaging check, not a demand, freshness, or longitudinal-reliability study. No monetization, public deployment, schedule, or customer run is enabled by this repository change.

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

Suggested initial review price: `$0.003` per delivered product record (`$3/1,000`), including nested variants and no separate diagnostic or summary charge. This is configurable but intentionally not enabled.

Public competitor pages checked on 2026-10-07 show materially different scopes and prices: [Hydrafetch](https://apify.com/hydrafetch/shopify-store-products-scraper) advertises from $1.80/1,000 results, [Monty Burrows](https://apify.com/montyburrows/shopify-products) advertises from $0.21/1,000 variants, and [Tenfold Fleet](https://apify.com/tenfoldfleet/shopify-products-scraper) advertises from $0.80/1,000 products. These are not directly comparable units. The proposed price is a review hypothesis for one product record with nested variants, descriptions, images, timestamps, and direct-product support; it is not a claim of demand or profitability.

## Remaining uncertainties

- `/products.json` availability, pagination semantics, and catalog completeness vary by storefront and are not treated as a universal Shopify guarantee.
- Some stores may block the endpoint or require a custom storefront/API token; those cases remain unsupported in v1.
- Currency is reported only when `/cart.js` exposes it; USD is never assumed.
- `available` is a boolean source signal, not inventory quantity.
- Apify's build output does not expose a Git SHA automatically for direct CLI deployment; this report records the source SHA supplied to the final build.
