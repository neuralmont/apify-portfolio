from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://data.austintexas.gov"
DATASET = "3syk-w9eu"
RESOURCE_URL = f"{BASE_URL}/resource/{DATASET}.json"
METADATA_URL = f"{BASE_URL}/api/views/{DATASET}"
LANDING_URL = f"{BASE_URL}/Building-and-Development/Issued-Construction-Permits/{DATASET}"
MAX_RESULTS = 5000
PAGE_SIZE = 1000
MAX_PAGE_REQUESTS = 100
PERMIT_TYPES = ("BP", "EP", "MP", "PP", "DS")
TRADES = ("General Contractor", "Electrical Contractor", "Plumbing Contractor", "Mechanical Contractor")
REQUIRED_FIELDS = ("permit_number", "issue_date", "permittype", "permit_class_mapped", "description", "status_current", "permit_location", "total_job_valuation", "contractor_trade", "contractor_company_name")


class ActorInputError(ValueError):
    pass


class ExtractionError(RuntimeError):
    pass


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def default_dates(today: Optional[date] = None) -> Tuple[str, str]:
    # The source issue_date is date-only. America/Chicago is used only to
    # choose calendar dates; the source value is never labeled a timestamp.
    end = today or datetime.now(ZoneInfo("America/Chicago")).date()
    return (end - timedelta(days=6)).isoformat(), end.isoformat()


def validate_input(raw: Optional[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    data = dict(raw or {})
    if data.get("startDate") is None and data.get("endDate") is None:
        data["startDate"], data["endDate"] = default_dates(today)
    elif bool(data.get("startDate")) != bool(data.get("endDate")):
        raise ActorInputError("startDate and endDate must be provided together")
    for key in ("startDate", "endDate"):
        try:
            date.fromisoformat(str(data[key]))
        except (KeyError, ValueError):
            raise ActorInputError(f"{key} must be YYYY-MM-DD")
    if data["startDate"] > data["endDate"]:
        raise ActorInputError("startDate must be on or before endDate")
    data["permitClass"] = data.get("permitClass", "Commercial")
    if data["permitClass"] not in ("Commercial", "Residential", "All"):
        raise ActorInputError("permitClass must be Commercial, Residential, or All")
    for key, allowed in (("permitTypes", PERMIT_TYPES), ("contractorTrades", TRADES)):
        values = data.get(key, []) or []
        if not isinstance(values, list) or any(v not in allowed for v in values):
            raise ActorInputError(f"{key} contains an unsupported source value")
        data[key] = list(dict.fromkeys(values))
    keywords = data.get("descriptionKeywords", []) or []
    if isinstance(keywords, str):
        keywords = [item.strip() for item in keywords.split(",")]
    if not isinstance(keywords, list) or any(not isinstance(v, str) or not v.strip() or len(v) > 100 for v in keywords):
        raise ActorInputError("descriptionKeywords must be non-empty strings of at most 100 characters")
    data["descriptionKeywords"] = list(dict.fromkeys(v.strip() for v in keywords))
    data["requireContractor"] = bool(data.get("requireContractor", False))
    data["includeContractorSummary"] = bool(data.get("includeContractorSummary", True))
    try:
        data["maxResults"] = int(data.get("maxResults", 100))
    except (ValueError, TypeError):
        raise ActorInputError("maxResults must be an integer")
    if not 1 <= data["maxResults"] <= MAX_RESULTS:
        raise ActorInputError(f"maxResults must be between 1 and {MAX_RESULTS}")
    return data


def quote_soql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_where(data: Dict[str, Any]) -> str:
    clauses = [f"issue_date between {quote_soql(data['startDate'] + 'T00:00:00')} and {quote_soql(data['endDate'] + 'T23:59:59')}"]
    if data["permitClass"] != "All":
        clauses.append(f"permit_class_mapped = {quote_soql(data['permitClass'])}")
    if data["permitTypes"]:
        clauses.append("permittype in (" + ",".join(quote_soql(v) for v in data["permitTypes"]) + ")")
    if data["contractorTrades"]:
        clauses.append("contractor_trade in (" + ",".join(quote_soql(v) for v in data["contractorTrades"]) + ")")
    if data["requireContractor"]:
        clauses.append("contractor_company_name is not null and contractor_company_name != ''")
    if data["descriptionKeywords"]:
        clauses.append("(" + " or ".join(f"lower(description) like {quote_soql('%' + v.lower() + '%')}" for v in data["descriptionKeywords"]) + ")")
    return " and ".join(clauses)


def normalize_record(row: Dict[str, Any], observed_at: str) -> Dict[str, Any]:
    permit_id = row.get("permit_number")
    if not permit_id:
        raise ExtractionError("source row missing permit_number")
    link = row.get("link") or {}
    source_link = link.get("url") if isinstance(link, dict) else None
    if not source_link:
        source_link = RESOURCE_URL + "?" + urlencode({"$where": f"permit_number={quote_soql(str(permit_id))}"})
    location = row.get("location") or {}
    return {
        "source_record_id": str(permit_id), "permit_number": str(permit_id),
        "issue_date": row.get("issue_date"), "status_raw": row.get("status_current"),
        "source_permit_type": row.get("permittype"), "source_permit_type_description": row.get("permit_type_desc"),
        "source_class": row.get("permit_class_mapped"), "work_class": row.get("work_class"),
        "work_description": row.get("description"), "project_address": row.get("permit_location"),
        "latitude": row.get("latitude") or location.get("latitude"), "longitude": row.get("longitude") or location.get("longitude"),
        "contractor_name": row.get("contractor_company_name"), "contractor_trade": row.get("contractor_trade"),
        "project_valuation": row.get("total_job_valuation"), "observation_timestamp": observed_at,
        "source_link": source_link,
    }


def completeness(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    keys = ("issue_date", "status_raw", "source_permit_type", "source_class", "work_description", "project_address", "latitude", "longitude", "contractor_name", "contractor_trade", "project_valuation")
    return {key: sum(row.get(key) not in (None, "") for row in rows) for key in keys}


def contractor_summary(rows: List[Dict[str, Any]], incomplete: bool) -> List[Dict[str, Any]]:
    groups = defaultdict(list)
    for row in rows:
        if row.get("contractor_name"):
            groups[(row["contractor_name"], row.get("contractor_trade"))].append(row)
    output = []
    for (name, trade), items in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        dates = sorted(str(x["issue_date"]) for x in items if x.get("issue_date"))
        output.append({"contractor_name_original": name, "contractor_trade": trade, "activity_scope": "activity within delivered records", "delivered_permit_count": len(items), "first_issue_date": dates[0] if dates else None, "latest_issue_date": dates[-1] if dates else None, "permit_types": sorted({x.get("source_permit_type") for x in items if x.get("source_permit_type")}), "supporting_permit_ids": [x["source_record_id"] for x in items], "extraction_incomplete": incomplete, "count_is_not_project_count": True})
    return output


class HttpClient:
    def __init__(self, retries: int = 2, timeout: int = 30):
        self.retries = retries; self.timeout = timeout; self.requests = 0; self.retries_used = 0; self.bytes = 0; self.errors: List[Dict[str, Any]] = []

    def get_json(self, url: str, params: Dict[str, Any]) -> Any:
        full = url + "?" + urlencode(params); last = None
        for attempt in range(self.retries + 1):
            if attempt: self.retries_used += 1; time.sleep(min(2 ** attempt, 8))
            self.requests += 1
            try:
                request = Request(full, headers={"User-Agent":"austin-commercial-permits-beta/0.1","Accept":"application/json"})
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read(); self.bytes += len(body); return json.loads(body)
            except HTTPError as exc:
                detail = exc.read(2048).decode("utf-8", "replace")
                if exc.code == 400:
                    last = f"HTTP 400 Bad Request: {detail}"; self.errors.append({"url":full,"error":last}); raise ExtractionError(last)
                retry_after = exc.headers.get("Retry-After")
                if retry_after and attempt < self.retries:
                    try: time.sleep(max(0, float(retry_after)))
                    except ValueError:
                        try: time.sleep(max(0, (parsedate_to_datetime(retry_after).timestamp() - time.time())))
                        except Exception: pass
                last = f"HTTP {exc.code}: {detail}"
            except (URLError, TimeoutError, ValueError) as exc: last = str(exc)
        self.errors.append({"url":full,"error":last}); raise ExtractionError(last)


def verify_schema(client: HttpClient) -> Dict[str, Any]:
    metadata = client.get_json(METADATA_URL, {})
    fields = {column.get("fieldName") for column in metadata.get("columns", [])}
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing: raise ExtractionError("Austin schema missing required fields: " + ", ".join(missing))
    return {"metadata_url": METADATA_URL, "verified_fields": sorted(fields), "missing_required_fields": []}


def _empty_summary(data: Dict[str, Any], started: float, client: HttpClient, errors: List[str], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "completion": "incomplete", "effective_input": data,
        "source": {"dataset": DATASET, "metadata_url": METADATA_URL, "landing_url": LANDING_URL,
                   "date_semantics": "issue_date is a source date-only field; inclusive America/Chicago calendar dates are sent as source date boundaries without claiming UTC timestamp precision"},
        "matching_source_count": None, "records_fetched": 0, "records_delivered": 0,
        "records_filtered": 0, "records_deduplicated": 0, "server_side_filtering": True,
        "pagination_complete": False, "cap_truncated": False, "cap_truncation_reason": None,
        "pagination": {"page_requests": [], "guard_limit": MAX_PAGE_REQUESTS},
        "errors": errors, "resource": {"requests": getattr(client, "requests", 0), "retries": getattr(client, "retries_used", 0), "bytes_received": getattr(client, "bytes", 0), "elapsed_seconds": round(time.monotonic() - started, 3)},
        "field_completeness": completeness([]),
    }, schema


def run_extraction(data: Dict[str, Any], client: Optional[HttpClient] = None, observed_at: Optional[str] = None) -> Dict[str, Any]:
    client = client or HttpClient(); observed_at = observed_at or datetime.now().astimezone().isoformat(); started = time.monotonic(); rows: List[Dict[str, Any]] = []; raw_ids = set(); errors: List[str] = []; records_seen = 0; duplicate_count = 0
    try:
        schema = verify_schema(client)
    except ExtractionError as exc:
        errors.append("metadata request/validation failed: " + str(exc))
        summary, schema = _empty_summary(data, started, client, errors)
        return {"records": [], "contractor_summary": [], "summary": summary, "schema": schema}
    where = build_where(data)
    try:
        count_data = client.get_json(RESOURCE_URL, {"$select":"count(*) as n", "$where":where})
        matching_count = int(count_data[0]["n"]) if count_data else 0
    except (ExtractionError, KeyError, TypeError, ValueError) as exc:
        errors.append("count request failed: " + str(exc))
        summary, schema = _empty_summary(data, started, client, errors, schema)
        return {"records": [], "contractor_summary": [], "summary": summary, "schema": schema}
    offset = 0; pagination_complete = True; stop_reason = None; seen_page_signatures = set(); page_requests = 0; page_log: List[Dict[str, int]] = []
    while len(rows) < data["maxResults"]:
        page_requests += 1
        if page_requests > MAX_PAGE_REQUESTS:
            errors.append(f"pagination exceeded {MAX_PAGE_REQUESTS} page requests")
            pagination_complete = False; stop_reason = "pagination_guard"; break
        remaining = data["maxResults"] - len(rows)
        page_size = min(PAGE_SIZE, remaining)
        try:
            page = client.get_json(RESOURCE_URL, {"$where":where,"$order":"issue_date DESC, permit_number ASC","$limit":page_size,"$offset":offset})
        except ExtractionError as exc:
            errors.append(str(exc)); pagination_complete = False; stop_reason = "request_error"; break
        if not page: break
        records_seen += len(page)
        page_log.append({"offset": offset, "requested_limit": page_size, "returned": len(page)})
        signature = tuple(str(item.get("permit_number")) for item in page if isinstance(item, dict))
        if signature in seen_page_signatures:
            errors.append("repeated page detected at offset " + str(offset)); pagination_complete = False; stop_reason = "repeated_page"; break
        seen_page_signatures.add(signature)
        for raw in page:
            try: record = normalize_record(raw, observed_at)
            except ExtractionError as exc: errors.append(str(exc)); pagination_complete = False; continue
            if record["source_record_id"] in raw_ids:
                duplicate_count += 1; errors.append("duplicate source ID: " + record["source_record_id"]); pagination_complete = False; continue
            raw_ids.add(record["source_record_id"]); rows.append(record)
            if len(rows) >= data["maxResults"]: break
        offset += len(page)
        if len(page) < page_size: break
    cap_truncated = matching_count > data["maxResults"] or (len(rows) >= data["maxResults"] and matching_count > len(rows))
    if cap_truncated and not errors: stop_reason = "maxResults_cap"
    # A cap is an intentional successful termination. The full source window is
    # explicitly marked truncated, but the requested result is still complete.
    cap_success = cap_truncated and len(rows) == data["maxResults"] and not errors
    if cap_truncated: pagination_complete = False
    if pagination_complete and not cap_truncated and len(rows) < matching_count: pagination_complete = False; stop_reason = stop_reason or "short_or_inconsistent_pagination"
    complete = (pagination_complete and not errors and not cap_truncated) or cap_success
    if not cap_truncated and len(rows) > matching_count:
        pagination_complete = False
        stop_reason = "inconsistent_count"
        errors.append("inconsistent pagination: delivered rows exceed source count")
        complete = False
    if not complete and not errors and len(rows) < matching_count and not cap_truncated:
        errors.append("inconsistent pagination: source count exceeds delivered rows")
    summary = {"completion":"complete" if complete else "incomplete","effective_input":data,"source":{"dataset":DATASET,"metadata_url":METADATA_URL,"landing_url":LANDING_URL,"date_semantics":"issue_date is a source date-only field; inclusive America/Chicago calendar dates are sent as source date boundaries without claiming UTC timestamp precision"},"matching_source_count":matching_count,"records_fetched":records_seen,"records_delivered":len(rows),"records_filtered":0,"records_deduplicated":duplicate_count,"server_side_filtering":True,"pagination_complete":pagination_complete,"cap_truncated":cap_truncated,"cap_truncation_reason":stop_reason,"pagination":{"page_requests":page_log,"guard_limit":MAX_PAGE_REQUESTS},"errors":errors,"resource":{"requests":getattr(client,"requests",0),"retries":getattr(client,"retries_used",0),"bytes_received":getattr(client,"bytes",0),"elapsed_seconds":round(time.monotonic()-started,3)},"field_completeness":completeness(rows)}
    return {"records":rows,"contractor_summary":contractor_summary(rows,not complete),"summary":summary,"schema":schema}


def write_local_result(result: Dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(output_dir/"permits.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result["records"]))
    atomic_write(output_dir/"contractor_summary.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result["contractor_summary"]))
    atomic_write(output_dir/"run_summary.json", json.dumps(result["summary"], indent=2) + "\n")
