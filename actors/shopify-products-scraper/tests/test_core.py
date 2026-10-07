import json
from urllib.parse import parse_qs, urlparse

import pytest

from shopify_actor.core import ExtractionError, HttpClient, InputError, PinnedHTTPConnection, SafeRedirectHandler, _product_job, extract, normalize_product, validate_input


def product(pid, handle="one", **extra):
    value = {"id": pid, "handle": handle, "title": f"Product {pid}", "vendor": "Acme", "product_type": "Widget", "tags": "a, b", "body_html": "<p>Hello <b>world</b></p>", "variants": [{"id": f"v-{pid}", "title": "Default", "sku": None, "option1": "Blue", "price": "1250", "compare_at_price": None, "available": True}], "url": f"/products/{handle}"}
    value.update(extra)
    return value


class FakeClient:
    def __init__(self, pages, products=None, currency="CAD", fail_page=None):
        self.catalog = [item for page in pages for item in page]
        self.products = products or {}
        self.currency = currency
        self.fail_page = fail_page
        self.requests = 0
        self.retries_used = 0
        self.bytes = 0
        self.errors = []
        self.catalog_requests = []

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
        query = parse_qs(urlparse(url).query)
        page = int(query["page"][0])
        limit = int(query["limit"][0])
        self.catalog_requests.append((page, limit))
        if self.fail_page == page:
            raise ExtractionError("synthetic pagination failure")
        offset = (page - 1) * limit
        return {"products": self.catalog[offset:offset + limit]}, url


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


def test_endpoint_specific_fields_and_locale_path_are_preserved():
    ajax = {"id": 1, "handle": "one", "description": "<p>Ajax description</p>", "type": "Ajax type", "variants": []}
    record = normalize_product(ajax, "https://shop.example/en-us/products/one", "https://shop.example/en-us/products/one.js", "CAD", "now")
    assert record["description_text"] == "Ajax description"
    assert record["product_type"] == "Ajax type"
    assert record["canonical_product_url"].endswith("/en-us/products/one")


def test_ajax_root_relative_url_uses_origin_and_keeps_store_separate():
    ajax = {"id": 2, "handle": "shirt", "url": "/products/shirt", "description": "Ajax", "type": "Shirt", "variants": []}
    record = normalize_product(ajax, "https://shop.example", "https://shop.example/en-us/products/shirt.js", "CAD", "now")
    assert record["store_url"] == "https://shop.example"
    assert record["canonical_product_url"] == "https://shop.example/products/shirt"
    assert record["store_url"] != record["canonical_product_url"]


def test_product_job_uses_resolved_locale_path_for_ajax_endpoint():
    class LocaleClient(FakeClient):
        def __init__(self):
            super().__init__([])
            self.json_urls = []

        def get_bytes(self, url):
            self.requests += 1
            return b"<html />", "https://shop.example/en-us/products/resolved"

        def get_json(self, url):
            self.requests += 1
            self.json_urls.append(url)
            if url.endswith("/cart.js"):
                return {"currency": "CAD"}, url
            return {"id": 1, "handle": "resolved", "description": "Ajax", "type": "Type", "variants": []}, url

    client = LocaleClient()
    result = _product_job("https://shop.example/products/original", client)
    assert result["status"] == "success"
    assert "https://shop.example/en-us/products/resolved.js" in client.json_urls
    assert "https://shop.example/en-us/cart.js" in client.json_urls


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
    client = FakeClient([[product(i) for i in range(600)]])
    result = extract(data(maxProducts=300), client)
    assert [r["product_id"] for r in result["records"]] == [str(i) for i in range(300)]
    assert len({r["product_id"] for r in result["records"]}) == 300
    assert client.catalog_requests == [(1, 250), (2, 250)]
    assert result["summary"]["cap_truncated"] is True
    assert result["summary"]["records_fetched"] == 500


def test_multi_store_collection_stops_at_shared_cap_and_identifies_skips():
    client = FakeClient([[product(1), product(2)]])
    result = extract(data(storeUrls=["https://one.example", "https://two.example"], maxProducts=1), client)
    assert len(result["records"]) == 1
    assert result["summary"]["skipped_inputs"] == ["https://two.example"]
    assert len(result["summary"]["store_outcomes"]) == 1


def test_repeated_catalog_page_is_reported_as_no_progress():
    repeated = [product(i) for i in range(250)]
    client = FakeClient([repeated, repeated])
    result = extract(data(maxProducts=500), client)
    assert any("repeated page" in error for error in result["summary"]["errors"])
    assert result["summary"]["store_outcomes"][0]["status"] == "partial"


def test_duplicate_only_catalog_page_is_incomplete():
    client = FakeClient([[product(i) for i in range(250)], [product(0)]])
    result = extract(data(maxProducts=500), client)
    assert any("no new product IDs" in error for error in result["summary"]["errors"])
    assert result["summary"]["pagination_complete"] is False


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


def test_http_client_rejects_private_dns_before_open(monkeypatch):
    opened = False

    def fake_getaddrinfo(*args, **kwargs):
        return [(None, None, None, None, ("127.0.0.1", 80))]

    class NeverOpen:
        def open(self, *args, **kwargs):
            nonlocal opened
            opened = True
            raise AssertionError("private destination was opened")

    monkeypatch.setattr("shopify_actor.core.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ExtractionError):
        HttpClient(5, 0, 1, opener=NeverOpen()).get_bytes("https://evil.example/")
    assert not opened


def test_pinned_transport_connects_to_validated_address(monkeypatch):
    targets = []

    def fake_create_connection(address, timeout, source_address):
        targets.append(address)
        raise OSError("stop before network")

    monkeypatch.setattr("shopify_actor.core.socket.create_connection", fake_create_connection)
    with pytest.raises(OSError):
        PinnedHTTPConnection("shop.example", address="93.184.216.34").connect()
    assert targets == [("93.184.216.34", 80)]


def test_redirect_dns_is_rejected_before_following(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(None, None, None, None, ("127.0.0.1", 443))]

    monkeypatch.setattr("shopify_actor.core.socket.getaddrinfo", fake_getaddrinfo)
    from urllib.request import Request
    with pytest.raises(ExtractionError):
        SafeRedirectHandler().redirect_request(Request("https://public.example/"), None, 302, "Found", {}, "https://evil.example/")
