from __future__ import annotations

import html
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPHandler, HTTPRedirectHandler, HTTPSHandler, Request, build_opener

MAX_PRODUCTS = 5000
CATALOG_PAGE_SIZE = 250
MAX_CATALOG_PAGES = 100
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}
DETERMINISTIC_HTTP = {400, 401, 403, 404}


class InputError(ValueError):
    pass


class ExtractionError(RuntimeError):
    pass


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", html.unescape(" ".join(self.parts))).strip()


def html_to_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    parser = TextExtractor()
    parser.feed(str(value))
    return parser.text()


def _public_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError("URLs must be non-empty strings")
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise InputError(f"URL must be a public HTTP(S) URL without credentials: {value}")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise InputError(f"private/local URL is not allowed: {value}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise InputError(f"non-public IP URL is not allowed: {value}")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def validate_input(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = dict(raw or {})
    stores = data.get("storeUrls") or []
    products = data.get("productUrls") or []
    if not isinstance(stores, list) or len(stores) > 100:
        raise InputError("storeUrls must be a list of at most 100 URLs")
    if not isinstance(products, list) or len(products) > 500:
        raise InputError("productUrls must be a list of at most 500 URLs")
    if not stores and not products:
        raise InputError("provide at least one storeUrls or productUrls URL")
    data["storeUrls"] = list(dict.fromkeys(_public_url(x) for x in stores))
    data["productUrls"] = list(dict.fromkeys(_public_url(x) for x in products))
    try:
        data["maxProducts"] = int(data.get("maxProducts", 100))
    except (TypeError, ValueError):
        raise InputError("maxProducts must be an integer")
    if not 1 <= data["maxProducts"] <= MAX_PRODUCTS:
        raise InputError("maxProducts must be between 1 and 5000")
    for key, default, low, high in (("requestTimeoutSecs", 30, 5, 60), ("retries", 2, 0, 3), ("maxConcurrencyPerDomain", 2, 1, 4)):
        try:
            data[key] = int(data.get(key, default))
        except (TypeError, ValueError):
            raise InputError(f"{key} must be an integer")
        if not low <= data[key] <= high:
            raise InputError(f"{key} must be between {low} and {high}")
    return data


def _validated_address(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ExtractionError(f"destination is not HTTP(S): {url}")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ExtractionError(f"destination is private/local: {url}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ExtractionError(f"destination DNS failed: {url}") from exc
        resolved = [item[4][0] for item in addresses]
        if not resolved or any(not ipaddress.ip_address(address).is_global for address in resolved):
            raise ExtractionError(f"destination does not resolve only to public addresses: {url}")
        return resolved[0]
    else:
        if not ip.is_global:
            raise ExtractionError(f"destination is non-public: {url}")
        return str(ip)


def _check_public_destination(url: str) -> None:
    _validated_address(url)


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Optional[Request]:
        resolved = urljoin(req.full_url, newurl)
        _check_public_destination(resolved)
        return super().redirect_request(req, fp, code, msg, headers, resolved)


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *args: Any, address: Optional[str] = None, **kwargs: Any):
        self.validated_address = address
        super().__init__(host, *args, **kwargs)

    def connect(self) -> None:
        self.sock = socket.create_connection((self.validated_address or self.host, self.port), self.timeout, self.source_address)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *args: Any, address: Optional[str] = None, **kwargs: Any):
        self.validated_address = address
        super().__init__(host, *args, **kwargs)

    def connect(self) -> None:
        self.sock = socket.create_connection((self.validated_address or self.host, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._tunnel_host or self.host)


class PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req: Request) -> Any:
        return self.do_open(PinnedHTTPConnection, req, address=_validated_address(req.full_url))


class PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req: Request) -> Any:
        context = self._context or ssl.create_default_context()
        check_hostname = getattr(self, "_check_hostname", None)
        if check_hostname is None:
            check_hostname = context.check_hostname
        return self.do_open(
            PinnedHTTPSConnection,
            req,
            context=context,
            check_hostname=check_hostname,
            address=_validated_address(req.full_url),
        )


class DomainLimiter:
    def __init__(self, limit: int):
        self.limit = limit
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}

    def acquire(self, host: str) -> threading.BoundedSemaphore:
        with self._lock:
            semaphore = self._semaphores.setdefault(host, threading.BoundedSemaphore(self.limit))
        semaphore.acquire()
        return semaphore


class HttpClient:
    def __init__(self, timeout: int, retries: int, concurrency: int, opener: Any = None):
        self.timeout = timeout
        self.retries = retries
        self.limiter = DomainLimiter(concurrency)
        self.opener = opener or build_opener(SafeRedirectHandler(), PinnedHTTPHandler(), PinnedHTTPSHandler())
        self.lock = threading.Lock()
        self.requests = 0
        self.retries_used = 0
        self.bytes = 0
        self.errors: list[dict[str, Any]] = []

    def get_bytes(self, url: str) -> tuple[bytes, str]:
        last: Optional[str] = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(min(2 ** attempt, 8))
                with self.lock:
                    self.retries_used += 1
            _check_public_destination(url)
            parsed = urlparse(url)
            semaphore = self.limiter.acquire(parsed.hostname or "")
            try:
                with self.lock:
                    self.requests += 1
                request = Request(url, headers={"User-Agent": "shopify-products-scraper-beta/0.1", "Accept": "application/json"})
                with self.opener.open(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    _check_public_destination(final_url)
                    body = response.read()
                    with self.lock:
                        self.bytes += len(body)
                    return body, final_url
            except HTTPError as exc:
                detail = exc.read(2048).decode("utf-8", "replace")
                last = f"HTTP {exc.code}: {detail[:500]}"
                with self.lock:
                    self.errors.append({"url": url, "status": exc.code, "error": last})
                if exc.code in DETERMINISTIC_HTTP or exc.code not in TRANSIENT_HTTP:
                    break
            except (URLError, TimeoutError, ValueError, ExtractionError) as exc:
                last = str(exc)
                if isinstance(exc, ExtractionError):
                    break
            finally:
                semaphore.release()
        raise ExtractionError(last or f"request failed: {url}")

    def get_json(self, url: str) -> tuple[Any, str]:
        body, final_url = self.get_bytes(url)
        try:
            return json.loads(body.decode("utf-8")), final_url
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"response was not JSON: {url}") from exc


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _identity(store_url: str, product_id: Any) -> tuple[str, str]:
    return ((urlparse(store_url).hostname or urlparse(store_url).netloc).lower(), str(product_id))


def _handle_from_url(url: str) -> Optional[str]:
    match = re.search(r"/(?:[a-z]{2}(?:-[A-Z]{2})?/)?products/([^/?#]+)", urlparse(url).path)
    return match.group(1) if match else None


def _tag_list(value: Any) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x) for x in value]
    return [x.strip() for x in str(value).split(",") if x.strip()]


def _number_or_null(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _image_urls(value: Any, store_url: str) -> Optional[list[str]]:
    if not isinstance(value, list):
        return None
    urls = []
    for image in value:
        candidate = image.get("src") if isinstance(image, dict) else image
        if candidate:
            urls.append(urljoin(store_url.rstrip("/") + "/", str(candidate)))
    return urls or None


def normalize_product(product: dict[str, Any], store_url: str, endpoint: str, currency_code: Optional[str], observed_at: str, resolved_product_url: Optional[str] = None) -> dict[str, Any]:
    ajax_money = endpoint.endswith(".js")

    def money(value: Any) -> Optional[float]:
        raw = _number_or_null(value)
        # Ajax Product JSON observed values are integer minor units (e.g. 8800
        # for USD 88.00); the undocumented products.json feed returns decimal
        # major-unit strings. Keep the source distinction explicit.
        return None if raw is None else (raw / 100 if ajax_money else raw)

    pid = product.get("id")
    handle = product.get("handle")
    description = product.get("description") if ajax_money else product.get("body_html")
    if description is None:
        description = product.get("body_html")
    product_type = product.get("type") if ajax_money else product.get("product_type")
    if product_type is None:
        product_type = product.get("product_type")
    variants = []
    for variant in product.get("variants") or []:
        options = variant.get("options")
        if options is None:
            options = [x for x in (variant.get("option1"), variant.get("option2"), variant.get("option3")) if x not in (None, "")]
        variants.append({
            "id": str(variant["id"]) if variant.get("id") is not None else None,
            "title": variant.get("title"),
            "sku": variant.get("sku"),
            "options": options,
            "price": money(variant.get("price")),
            "compare_at_price": money(variant.get("compare_at_price")),
            "price_unit": "major currency unit",
            "price_source_unit": "minor currency units from documented Ajax Product API" if ajax_money else "major currency units observed in storefront products.json",
            "available": variant.get("available") if isinstance(variant.get("available"), bool) else None,
            "availability_known": isinstance(variant.get("available"), bool),
        })
    path = product.get("url") or (f"/products/{handle}" if handle else None)
    if resolved_product_url and not product.get("url"):
        parsed_resolved = urlparse(resolved_product_url)
        canonical = urlunparse((parsed_resolved.scheme, parsed_resolved.netloc, parsed_resolved.path, "", "", ""))
    elif not product.get("url") and "/products/" in urlparse(store_url).path:
        parsed_store = urlparse(store_url)
        canonical = urlunparse((parsed_store.scheme, parsed_store.netloc, parsed_store.path, "", "", ""))
    elif path and urlparse(str(path)).scheme in {"http", "https"}:
        canonical = str(path)
    elif path and str(path).startswith("/"):
        canonical = urljoin(_origin(store_url) + "/", str(path).lstrip("/"))
    else:
        canonical = urljoin(store_url.rstrip("/") + "/", str(path).lstrip("/")) if path else None
    return {
        "store_url": store_url,
        "product_id": str(pid) if pid is not None else None,
        "handle": handle,
        "canonical_product_url": canonical,
        "title": product.get("title"),
        "vendor": product.get("vendor"),
        "product_type": product_type,
        "tags": _tag_list(product.get("tags")),
        "description_text": html_to_text(description),
        "description_html": description,
        "images": _image_urls(product.get("images"), store_url),
        "source_created_at": product.get("created_at"),
        "source_published_at": product.get("published_at"),
        "source_updated_at": product.get("updated_at"),
        "observed_at": observed_at,
        "currency_code": currency_code,
        "currency_context": ("Ajax monetary values are in the customer's presentment currency; code read from /cart.js; source minor units normalized to major units" if ajax_money else "Storefront products.json monetary values observed as major-unit amounts; code read from /cart.js" ) if currency_code else ("Ajax monetary values are presentment-currency amounts; source minor units normalized to major units; currency code unavailable" if ajax_money else "Storefront products.json monetary units observed as major-unit amounts; currency code unavailable"),
        "money_source_unit": "minor currency units" if ajax_money else "major currency units",
        "variants": variants,
        "source_endpoint": endpoint,
    }


def _currency(client: HttpClient, base_url: str) -> Optional[str]:
    try:
        parsed = urlparse(base_url)
        path = parsed.path
        if "/products/" in path:
            path = path.split("/products/", 1)[0].rstrip("/") + "/cart.js"
        else:
            path = path.rstrip("/") + "/cart.js"
        cart_url = urlunparse((parsed.scheme, parsed.netloc, path or "/cart.js", "", "", ""))
        payload, resolved = client.get_json(cart_url)
        if urlparse(resolved).hostname != urlparse(base_url).hostname:
            return None
        value = payload.get("currency") if isinstance(payload, dict) else None
        return str(value) if value else None
    except ExtractionError:
        return None


def _store_job(store_input: str, data: dict[str, Any], client: HttpClient, allowance: int, existing_identities: set[tuple[str, str]]) -> dict[str, Any]:
    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {"input_url": store_input, "resolved_store_url": None, "status": "failed", "endpoint_mode": "observed_unauthenticated_products_json", "pages_requested": 0, "products_fetched": 0, "duplicates": 0, "records": [], "errors": [], "coverage": "not_available"}
    try:
        _, resolved = client.get_bytes(store_input)
        origin = _origin(resolved)
        result["resolved_store_url"] = resolved
        currency = _currency(client, resolved)
        seen: set[str] = set()
        page_signatures: set[str] = set()
        page_size = min(CATALOG_PAGE_SIZE, allowance)
        for page in range(1, MAX_CATALOG_PAGES + 1):
            endpoint = urljoin(resolved.rstrip("/") + "/", f"products.json?limit={page_size}&page={page}")
            payload, _ = client.get_json(endpoint)
            result["pages_requested"] += 1
            rows = payload.get("products") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ExtractionError("catalog response lacked a products array")
            result["products_fetched"] += len(rows)
            signature = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
            if signature in page_signatures:
                raise ExtractionError("catalog pagination made no progress: repeated page")
            page_signatures.add(signature)
            if not rows:
                result["coverage"] = "complete_until_empty_page"
                break
            new_page_records = 0
            for product in rows:
                pid = product.get("id")
                key = str(pid) if pid is not None else None
                if key is None:
                    result["errors"].append("catalog product missing id")
                    continue
                if key in seen:
                    result["duplicates"] += 1
                    continue
                seen.add(key)
                identity = _identity(origin, key)
                if identity in existing_identities:
                    result["duplicates"] += 1
                    continue
                if len(result["records"]) < allowance:
                    result["records"].append(normalize_product(product, origin, endpoint, currency, observed))
                    existing_identities.add(identity)
                    new_page_records += 1
                if len(result["records"]) >= allowance:
                    result["coverage"] = "truncated_at_global_cap"
                    break
            if len(result["records"]) >= allowance:
                break
            if new_page_records == 0:
                raise ExtractionError("catalog pagination made no progress: page had no new product IDs")
            if len(rows) < page_size:
                result["coverage"] = "complete_short_page"
                break
        else:
            raise ExtractionError("catalog pagination guard reached")
        result["status"] = "success" if not result["errors"] else "partial"
        # Explicit product URLs are handled separately so store pagination remains source-scoped.
    except ExtractionError as exc:
        result["errors"].append(str(exc))
        result["status"] = "failed" if not result["records"] else "partial"
    return result


def _product_job(url: str, client: HttpClient) -> dict[str, Any]:
    result = {"input_url": url, "status": "failed", "records": [], "errors": []}
    handle = _handle_from_url(url)
    if not handle:
        result["errors"].append("URL is not an individual /products/{handle} URL")
        return result
    try:
        _, resolved_home = client.get_bytes(url)
        resolved_handle = _handle_from_url(resolved_home)
        if not resolved_handle:
            raise ExtractionError("redirected product URL lacked a /products/{handle} path")
        product_path = urlparse(resolved_home).path.rstrip("/") + ".js"
        endpoint = urlunparse((urlparse(resolved_home).scheme, urlparse(resolved_home).netloc, product_path, "", "", ""))
        currency = _currency(client, resolved_home)
        product, _ = client.get_json(endpoint)
        if not isinstance(product, dict) or product.get("id") is None:
            raise ExtractionError("product response lacked a product ID")
        result["records"].append(normalize_product(product, _origin(resolved_home), endpoint, currency, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), resolved_home))
        result["status"] = "success"
    except ExtractionError as exc:
        result["errors"].append(str(exc))
    return result


def extract(data: dict[str, Any], client: Optional[HttpClient] = None) -> dict[str, Any]:
    started = time.monotonic()
    client = client or HttpClient(data["requestTimeoutSecs"], data["retries"], data["maxConcurrencyPerDomain"])
    stores = list(dict.fromkeys(data["storeUrls"]))
    products = list(dict.fromkeys(data["productUrls"]))
    outcomes = []
    skipped_inputs: list[str] = []
    records: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    duplicates = 0
    errors: list[str] = []
    for store in stores:
        if len(records) >= data["maxProducts"]:
            skipped_inputs.append(store)
            continue
        outcome = _store_job(store, data, client, data["maxProducts"] - len(records), identities)
        outcomes.append(outcome)
        errors.extend(f"{outcome['input_url']}: {e}" for e in outcome.get("errors", []))
        for record in outcome.get("records", []):
            records.append(record)
        duplicates += int(outcome.get("duplicates", 0))
    for product in products:
        if len(records) >= data["maxProducts"]:
            skipped_inputs.append(product)
            continue
        outcome = _product_job(product, client)
        outcomes.append(outcome)
        errors.extend(f"{outcome['input_url']}: {e}" for e in outcome.get("errors", []))
        for record in outcome.get("records", []):
            identity = _identity(record["store_url"], record["product_id"])
            if identity in identities:
                duplicates += 1
                continue
            identities.add(identity)
            if len(records) < data["maxProducts"]:
                records.append(record)
    store_outcomes = [x for x in outcomes if "resolved_store_url" in x]
    candidate_count = sum(int(x.get("products_fetched", len(x.get("records", [])))) for x in outcomes)
    cap = len(records) >= data["maxProducts"] and (bool(skipped_inputs) or candidate_count > data["maxProducts"] or any(x.get("coverage") == "truncated_at_global_cap" for x in store_outcomes))
    summary = {
        "effective_input": data,
        "records_fetched": sum(int(x.get("products_fetched", len(x.get("records", [])))) for x in outcomes),
        "records_delivered": len(records),
        "duplicates": duplicates,
        "cap_truncated": cap,
        "pagination_complete": bool(store_outcomes) and all(
            x.get("status") == "success"
            and x.get("coverage") in {"complete_until_empty_page", "complete_short_page"}
            for x in store_outcomes
        ),
        "coverage": "bounded_global_cap" if cap else "per-store endpoint coverage only; no territory completeness claim",
        "store_outcomes": [{k: v for k, v in x.items() if k != "records"} for x in store_outcomes],
        "product_outcomes": [{k: v for k, v in x.items() if k != "records"} for x in outcomes if "resolved_store_url" not in x],
        "skipped_inputs": skipped_inputs,
        "errors": errors,
        "resource": {"requests": client.requests, "retries": client.retries_used, "bytes_received": client.bytes, "elapsed_seconds": round(time.monotonic() - started, 3), "http_errors": client.errors[:50]},
        "source_handling": {"individual_product_endpoint": "documented Shopify Ajax Product API /products/{handle}.js", "catalog_endpoint": "observed unauthenticated storefront /products.json pagination; not presented as an official Shopify API contract", "browser_fallback": False},
    }
    return {"records": records, "summary": summary, "schema": {"monetary_context": "Ajax product monetary values are presentment-currency amounts; currency_code is populated only when /cart.js exposes it", "availability": "available is a boolean availability signal, not a known inventory quantity"}}
