import json

import pytest

from shopify_actor.core import ExtractionError, InputError, extract, normalize_product, validate_input


def product(pid, handle="one", **extra):
    value = {"id": pid, "handle": handle, "title": f"Product {pid}", "vendor": "Acme", "product_type": "Widget", "tags": "a, b", "body_html": "<p>Hello <b>world</b></p>", "variants": [{"id": f"v-{pid}", "title": "Default", "sku": None, "option1": "Blue", "price": "1250", "compare_at_price": None, "available": True}], "url": f"/products/{handle}"}
    value.update(extra)
    return value


class FakeClient:
    def __init__(self, pages, products=None, currency="CAD", fail_page=None):
        self.pages = pages
        self.products = products or {}
        self.currency = currency
        self.fail_page = fail_page
        self.requests = 0
        self.retries_used = 0
        self.bytes = 0
        self.errors = []

    def get_bytes(self, url):
        self.requests += 1
        return b"<html>Shopify</html>", url

    def get_json(self, url):
        self.requests += 1
        self.bytes += 10
        if url.endswith("/cart.js"):
            return {"currency": self.currency}, url
        if "/products/" in url and url.endswith(".js"):
            handle = url.rsplit("/", 1)[-1][:-3]
            return self.products[handle], url
        page = int(url.rsplit("page=", 1)[-1])
        if self.fail_page == page:
            raise ExtractionError("synthetic pagination failure")
        return {"products": self.pages[page - 1] if page <= len(self.pages) else []}, url


def data(**overrides):
    value = validate_input({"storeUrls": ["https://shop.example"], "maxProducts": 100})
    value.update(overrides)
    return value


def test_normalization_preserves_nulls_and_presentment_currency():
    record = normalize_product(product(1), "https://shop.example", "https://shop.example/products/one.js", "CAD", "2026-10-07T00:00:00Z")
    assert record["currency_code"] == "CAD"
    assert record["variants"][0]["price"] == 12.5
    assert record["variants"][0]["compare_at_price"] is None
    assert record["description_text"] == "Hello world"


def test_overlapping_store_and_product_inputs_deduplicate_by_store_and_product_id():
    client = FakeClient([[product(1, "one")]], {"one": product(1, "one")})
    result = extract(data(productUrls=["https://shop.example/products/one"]), client)
    assert len(result["records"]) == 1
    assert result["summary"]["duplicates"] == 1


def test_individual_product_exact_cap_is_not_catalog_truncation():
    client = FakeClient([], {"one": product(1, "one")})
    result = extract(data(storeUrls=[], productUrls=["https://shop.example/products/one"], maxProducts=1), client)
    assert result["summary"]["cap_truncated"] is False


def test_multi_page_catalog_and_global_cap():
    client = FakeClient([[product(i) for i in range(250)], [product(i) for i in range(250, 350)], []])
    result = extract(data(maxProducts=300), client)
    assert [r["product_id"] for r in result["records"]] == [str(i) for i in range(300)]
    assert result["summary"]["cap_truncated"] is True
    assert result["summary"]["records_fetched"] == 350


def test_pagination_failure_is_preserved_with_partial_records():
    client = FakeClient([[product(i) for i in range(250)], [product(250)]], fail_page=2)
    result = extract(data(maxProducts=300), client)
    assert len(result["records"]) == 250
    assert any("synthetic pagination failure" in error for error in result["summary"]["errors"])
    assert result["summary"]["store_outcomes"][0]["status"] == "partial"


def test_blocked_store_is_reported_without_inventing_records():
    class Blocked(FakeClient):
        def get_bytes(self, url):
            raise ExtractionError("HTTP 403: bot protection")

    result = extract(data(), Blocked([]))
    assert result["records"] == []
    assert "HTTP 403" in result["summary"]["errors"][0]


def test_input_rejects_non_public_destinations_and_requires_input():
    with pytest.raises(InputError):
        validate_input({})
    with pytest.raises(InputError):
        validate_input({"storeUrls": ["http://127.0.0.1"]})
