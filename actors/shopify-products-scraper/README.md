# Shopify Products Scraper

Extract public Shopify products from storefront home URLs and individual product URLs. The Actor returns one default-dataset record per product, with nested variants, and supports multiple stores under one global result cap.

This is a small paid-beta candidate, not a universal Shopify crawler. It does not discover stores, log in, access Shopify Admin data, probe inventory quantities, track historical changes, or use a browser fallback. Some stores disable public catalog endpoints or use custom storefronts; those stores are reported in `RUN_SUMMARY` and do not produce invented records.

## What is supported

- Public `http://` or `https://` storefront and product destinations only. Credentials, localhost, private IPs, and non-public redirects are rejected.
- Store URLs use the observed unauthenticated `/products.json?limit=250&page=N` storefront convention. Shopify's current official documentation does not define this endpoint as a public API, so catalog pagination is labelled observed behavior and its coverage is not guaranteed.
- Individual product URLs use Shopify's documented unauthenticated Ajax Product API, `/products/{handle}.js`. Shopify documents presentment-currency monetary values and a maximum of 250 variants per product.
- Multiple stores and product URLs can be supplied. Overlapping records are deduplicated by `(store domain, product ID)`.
- `maxProducts` defaults to 100 and is capped at 5,000 across the entire run. Reaching the cap succeeds with `cap_truncated: true`.

## Pricing proposal

Suggested initial beta price: `$0.003` per delivered product record (`$3 per 1,000`). Variants are included in the product record. Diagnostics, duplicate records, and failed fetches are not charged. Platform usage should remain included while testing; monetization is intentionally not enabled by this repository change.

## Example input

```json
{
  "storeUrls": ["https://example.myshopify.com"],
  "productUrls": ["https://example.myshopify.com/products/example-product"],
  "maxProducts": 100,
  "requestTimeoutSecs": 30,
  "retries": 2,
  "maxConcurrencyPerDomain": 2
}
```

At least one of `storeUrls` or `productUrls` is required. Storefront URLs may redirect; the final destination must remain public HTTP(S). A product URL is identified by a `/products/{handle}` path.

## Output

The default dataset contains records like:

```json
{
  "store_url": "https://www.untuckit.com",
  "product_id": "7672658559054",
  "handle": "sydney-4",
  "canonical_product_url": "https://www.untuckit.com/products/sydney-4",
  "title": "Stretch Cotton Sydney Shirt Dress",
  "vendor": "UNTUCKit",
  "product_type": null,
  "tags": null,
  "description_text": "Observed public product sample; source text abbreviated here.",
  "description_html": null,
  "currency_code": "USD",
  "currency_context": "Shopify Ajax monetary values are in the customer's presentment currency; code read from /cart.js; source minor units normalized to major units",
  "money_source_unit": "minor currency units",
  "variants": [{
    "id": "44553638936654",
    "title": "Default Title",
    "sku": null,
    "options": [],
    "price": 88.0,
    "compare_at_price": null,
    "price_unit": "major currency unit",
    "price_source_unit": "minor currency units from documented Ajax Product API",
    "available": true,
    "availability_known": true
  }],
  "source_created_at": null,
  "source_published_at": null,
  "source_updated_at": null,
  "observed_at": "2026-10-07T00:00:00Z",
  "source_endpoint": "https://www.untuckit.com/products/sydney-4.js"
}
```

The sample above is a sanitized observation from the public Ajax product endpoint on 2026-10-07; it is illustrative evidence, not a guarantee that the product remains published.

Missing fields remain `null`. Prices are numeric amounts in the source endpoint's presentment currency, normalized to major units; the Actor never assumes USD. The documented Ajax endpoint was observed returning minor units, while the observed `products.json` feed returned major-unit values, and the output records that distinction. `available` is a source availability signal, not a known inventory quantity. Open `RUN_SUMMARY` for per-store outcomes, fetched/delivered counts, duplicates, pagination coverage, truncation, errors, and request metrics. `SCHEMA_METADATA` records endpoint and monetary limitations.

## Official documentation and limits

The [Shopify Ajax API overview](https://shopify.dev/docs/api/ajax) documents an unauthenticated API hosted by Shopify themes and states that product JSON responses have a maximum of 250 variants. The [Ajax Product API reference](https://shopify.dev/docs/api/ajax/reference/product) documents `/{locale}/products/{product-handle}.js` and presentment-currency behavior. Shopify's [Storefront API products query](https://shopify.dev/docs/api/storefront/latest/queries/products) is a separate paginated GraphQL API requiring a shop-specific public token; this Actor does not ask users for tokens, so it does not claim to use that API.

See [validation_report.md](validation_report.md) for the bounded live sample, failures, measured local verification, and remaining uncertainties.
