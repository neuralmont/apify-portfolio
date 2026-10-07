from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ORIGIN = "https://boards-api.greenhouse.io"
MAX_BOARDS = 50
MAX_JOBS = 5000
TRANSIENT = {408, 425, 429, 500, 502, 503, 504}
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
DIRECTORY_PATH = Path(__file__).with_name("directory.json")


class InputError(ValueError):
    pass


class ExtractionError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExtractionError(f"Greenhouse API redirected unexpectedly to {newurl}")


class _TextParser(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCKS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value: Any) -> str:
    if value is None:
        return ""
    parser = _TextParser()
    parser.feed(html.unescape(str(value)))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(parser.parts))).strip()


def _clean_keywords(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise InputError(f"{name} must be an array of strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InputError(f"{name} cannot contain empty or non-string values")
        result.append(item.strip().casefold())
    return result


def normalize_board(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError("boards must contain non-empty strings")
    value = value.strip()
    if "://" not in value:
        token = value
    else:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
            raise InputError("Greenhouse board URLs must use https://boards.greenhouse.io or https://job-boards.greenhouse.io")
        if parsed.query or parsed.fragment:
            raise InputError("Greenhouse board URLs cannot contain query strings or fragments")
        pieces = [piece for piece in parsed.path.split("/") if piece]
        if len(pieces) != 1:
            raise InputError("an individual Greenhouse job URL is not a board request; supply the board URL")
        token = pieces[0]
    if not TOKEN_RE.fullmatch(token):
        raise InputError(f"invalid Greenhouse board token: {token!r}")
    return token


def load_directory() -> dict[str, Any]:
    directory = json.loads(DIRECTORY_PATH.read_text())
    companies = directory.get("companies") if isinstance(directory, dict) else None
    if not isinstance(companies, list):
        raise InputError("tracked company directory is malformed")
    tokens = set()
    for company in companies:
        if not isinstance(company, dict) or not isinstance(company.get("board_token"), str) or not isinstance(company.get("company_name"), str):
            raise InputError("tracked company directory contains an invalid entry")
        if company["board_token"] in tokens:
            raise InputError("tracked company directory contains duplicate board tokens")
        tokens.add(company["board_token"])
    return directory


def validate_input(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputError("input must be a JSON object")
    directory = load_directory()
    mode = raw.get("mode")
    if mode is None:
        mode = "specific" if raw.get("boards") is not None else "directory"
    if mode not in {"directory", "specific"}:
        raise InputError("mode must be directory or specific")
    directory_by_token = {company["board_token"]: company for company in directory["companies"]}
    requested_company_tokens = raw.get("companyTokens") or []
    if not isinstance(requested_company_tokens, list) or any(not isinstance(token, str) or not token.strip() for token in requested_company_tokens):
        raise InputError("companyTokens must be an array of non-empty strings")
    requested_company_tokens = list(dict.fromkeys(token.strip() for token in requested_company_tokens))
    unknown_companies = [token for token in requested_company_tokens if token not in directory_by_token]
    if unknown_companies:
        raise InputError(f"companyTokens not found in tracked directory: {', '.join(unknown_companies)}")
    raw_additional = raw.get("additionalBoards") or []
    if not isinstance(raw_additional, list):
        raise InputError("additionalBoards must be an array")
    raw_legacy = raw.get("boards")
    if raw_legacy is not None and not isinstance(raw_legacy, list):
        raise InputError("boards must be an array")
    if mode == "directory":
        if raw.get("boards") is not None or raw_additional:
            raise InputError("directory mode searches tracked companies only; use specific mode for custom boards")
        if not any(raw.get(name) for name in ("titleKeywords", "locationKeywords", "departmentKeywords")):
            raise InputError("directory mode requires at least one nonempty title, location, or department filter")
        selected = [company for company in directory["companies"] if not requested_company_tokens or company["board_token"] in requested_company_tokens]
    else:
        selected = [directory_by_token[token] for token in requested_company_tokens]
        raw_boards = list(raw_additional) + (list(raw_legacy) if raw_legacy is not None else [])
        for value in raw_boards:
            token = normalize_board(value)
            if token not in {company["board_token"] for company in selected}:
                selected.append(directory_by_token.get(token, {"board_token": token, "company_name": None, "source_url": None}))
        if not selected:
            raise InputError("specific mode requires a tracked company, additional board, or legacy boards input")
    if len(selected) > MAX_BOARDS:
        raise InputError(f"the selected boards cannot exceed {MAX_BOARDS}")
    board_specs = []
    seen = set()
    for company in selected:
        token = normalize_board(company["board_token"])
        if token not in seen:
            seen.add(token)
            board_specs.append({"board_token": token, "company_name": company.get("company_name"), "source_url": company.get("source_url")})
    max_jobs = raw.get("maxJobs", 100)
    if isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or not 1 <= max_jobs <= MAX_JOBS:
        raise InputError(f"maxJobs must be an integer from 1 to {MAX_JOBS}")
    return {
        "mode": mode,
        "directory_version": directory["version"],
        "directory_size": len(directory["companies"]),
        "board_specs": board_specs,
        "boards": [spec["board_token"] for spec in board_specs],
        "maxJobs": max_jobs,
        "titleKeywords": _clean_keywords(raw.get("titleKeywords"), "titleKeywords"),
        "locationKeywords": _clean_keywords(raw.get("locationKeywords"), "locationKeywords"),
        "departmentKeywords": _clean_keywords(raw.get("departmentKeywords"), "departmentKeywords"),
        "requestTimeoutSecs": raw.get("requestTimeoutSecs", 30),
        "retries": raw.get("retries", 2),
    }


def _names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("name")) for item in items if isinstance(item, dict) and item.get("name") is not None]


def _matches(job: dict[str, Any], data: dict[str, Any]) -> bool:
    location_value = job.get("location")
    if location_value is not None and not isinstance(location_value, dict):
        raise ExtractionError("job location must be an object or null")
    if isinstance(location_value, dict) and location_value.get("name") is not None and not isinstance(location_value.get("name"), str):
        raise ExtractionError("job location.name must be a string or null")
    title = str(job.get("title") or "").casefold()
    location = str((location_value or {}).get("name") or "").casefold()
    departments = " ".join(_names(job.get("departments"))).casefold()
    return all(not group or any(keyword in haystack for keyword in group) for group, haystack in ((data["titleKeywords"], title), (data["locationKeywords"], location), (data["departmentKeywords"], departments)))


def normalize_job(board_token: str, job: dict[str, Any], retrieved_at: str, company_name: Optional[str] = None) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ExtractionError(f"board {board_token} returned a non-object job")
    location = job.get("location")
    if location is not None and not isinstance(location, dict):
        raise ExtractionError(f"board {board_token} returned a job with malformed location")
    job_id = job.get("id")
    if job_id is None:
        raise ExtractionError(f"board {board_token} returned a job without id")
    content = job.get("content")
    return {
        "source": "greenhouse",
        "company_name": company_name,
        "board_token": board_token,
        "job_id": str(job_id),
        "internal_job_id": str(job["internal_job_id"]) if job.get("internal_job_id") is not None else None,
        "title": job.get("title"),
        "location": (location or {}).get("name"),
        "departments": job.get("departments") if isinstance(job.get("departments"), list) else [],
        "offices": job.get("offices") if isinstance(job.get("offices"), list) else [],
        "description_html": content if content is not None else None,
        "description_text": html_to_text(content) if content is not None else None,
        "job_url": job.get("absolute_url"),
        "updated_at": job.get("updated_at"),
        "retrieved_at": retrieved_at,
    }


@dataclass
class HttpStats:
    requests: int = 0
    retries: int = 0
    bytes_received: int = 0


class GreenhouseClient:
    def __init__(self, timeout: int = 30, retries: int = 2, opener=None, sleep: Callable[[float], None] = time.sleep):
        self.timeout = timeout
        self.retries = retries
        self.opener = opener or build_opener(_NoRedirect())
        self.sleep = sleep
        self.stats = HttpStats()

    def get_board(self, token: str) -> dict[str, Any]:
        url = f"{API_ORIGIN}/v1/boards/{quote(token, safe='')}/jobs?content=true"
        last_error = None
        for attempt in range(self.retries + 1):
            self.stats.requests += 1
            try:
                with self.opener.open(Request(url, headers={"Accept": "application/json", "User-Agent": "GreenhouseJobsScraper/0.1"}), timeout=self.timeout) as response:
                    body = response.read()
                    self.stats.bytes_received += len(body)
                    parsed = json.loads(body)
                    if not isinstance(parsed, dict) or not isinstance(parsed.get("jobs"), list):
                        raise ExtractionError(f"board {token} returned malformed JSON response")
                    return parsed
            except HTTPError as exc:
                last_error = exc
                if exc.code not in TRANSIENT or attempt >= self.retries:
                    if exc.code in {400, 404}:
                        raise ExtractionError(f"invalid or unavailable Greenhouse board {token} (HTTP {exc.code})") from exc
                    raise ExtractionError(f"Greenhouse board {token} failed with HTTP {exc.code}") from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = min(float(retry_after), 30.0) if retry_after else min(2 ** attempt, 8)
                except ValueError:
                    delay = min(2 ** attempt, 8)
                self.stats.retries += 1
                self.sleep(delay)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise ExtractionError(f"Greenhouse board {token} request failed: {exc}") from exc
                self.stats.retries += 1
                self.sleep(min(2 ** attempt, 8))
        raise ExtractionError(f"Greenhouse board {token} request failed: {last_error}")


def _new_outcome(token: str) -> dict[str, Any]:
    return {
        "board_token": token,
        "status": "success",
        "jobs_fetched": 0,
        "jobs_matched": 0,
        "jobs_selected": 0,
        "jobs_delivered": 0,
        "jobs_charged": 0,
        "duplicates": 0,
        "errors": [],
        "coverage": "full_board_response",
    }


def extract_board(
    data: dict[str, Any],
    token: str,
    client: GreenhouseClient,
    allowance: int,
    identities: Optional[set[tuple[str, str]]] = None,
    retrieved_at: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch and select one board, returning only records within the allowance."""
    identities = identities if identities is not None else set()
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    outcome = _new_outcome(token)
    selected: list[dict[str, Any]] = []
    try:
        payload = client.get_board(token)
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ExtractionError(f"board {token} returned malformed JSON response")
        jobs = payload["jobs"]
        outcome["jobs_fetched"] = len(jobs)
        seen_board: set[str] = set()
        for item in jobs:
            if not isinstance(item, dict):
                raise ExtractionError(f"board {token} returned a non-object job")
            job_id = item.get("id")
            if job_id is None:
                raise ExtractionError(f"board {token} returned a job without id")
            identity = str(job_id)
            if identity in seen_board:
                outcome["duplicates"] += 1
                continue
            seen_board.add(identity)
            if not _matches(item, data):
                continue
            outcome["jobs_matched"] += 1
            if len(selected) >= allowance:
                outcome["coverage"] = "truncated_at_global_cap"
                continue
            record = normalize_job(token, item, retrieved_at, company_name)
            scoped_identity = (token, record["job_id"])
            if scoped_identity in identities:
                outcome["duplicates"] += 1
                continue
            identities.add(scoped_identity)
            selected.append(record)
            outcome["jobs_selected"] += 1
        if outcome["jobs_matched"] > outcome["jobs_selected"]:
            outcome["coverage"] = "truncated_at_global_cap"
    except ExtractionError as exc:
        outcome["status"] = "failed"
        outcome["errors"].append(str(exc))
    return {"records": selected, "outcome": outcome}


def extract(data: dict[str, Any], client: Optional[GreenhouseClient] = None) -> dict[str, Any]:
    """Compatibility aggregate used by tests and local callers.

    The Actor runtime uses extract_board incrementally so delivery happens
    between board requests. This helper aggregates the same board results.
    """
    data = validate_input(data)
    client = client or GreenhouseClient(data["requestTimeoutSecs"], data["retries"])
    started = time.monotonic()
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    records: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    outcomes: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped: list[str] = []
    cap_stop = False
    for index, spec in enumerate(data["board_specs"]):
        token = spec["board_token"]
        if len(records) >= data["maxJobs"]:
            cap_stop = True
            skipped.extend(data["boards"][index:])
            break
        result = extract_board(data, token, client, data["maxJobs"] - len(records), identities, retrieved_at, spec.get("company_name"))
        outcome = result["outcome"]
        records.extend(result["records"])
        if outcome["errors"]:
            errors.extend(outcome["errors"])
        if outcome["coverage"] == "truncated_at_global_cap":
            cap_stop = True
        outcomes.append(outcome)
        if cap_stop:
            skipped.extend(data["boards"][index + 1:])
            break
    for outcome in outcomes:
        outcome["jobs_delivered"] = outcome["jobs_selected"]
        outcome["jobs_charged"] = 0
    all_matching_delivered = not errors and not skipped and not cap_stop
    elapsed = round(time.monotonic() - started, 3)
    summary = {
        "search_mode": data["mode"],
        "directory_version": data["directory_version"],
        "directory_size": data["directory_size"],
        "boards_requested": len(data["boards"]),
        "boards_available": data["directory_size"] if data["mode"] == "directory" else len(data["board_specs"]),
        "boards_processed": len(outcomes),
        "boards_attempted": len(outcomes),
        "boards_succeeded": sum(outcome["status"] == "success" for outcome in outcomes),
        "boards_skipped": len(skipped),
        "boards_failed": sum(outcome["status"] == "failed" for outcome in outcomes),
        "records_fetched": sum(outcome["jobs_fetched"] for outcome in outcomes),
        "records_examined": sum(outcome["jobs_fetched"] for outcome in outcomes),
        "records_matched": sum(outcome["jobs_matched"] for outcome in outcomes),
        "records_selected": sum(outcome["jobs_selected"] for outcome in outcomes),
        "records_delivered": len(records),
        "duplicates": sum(outcome["duplicates"] for outcome in outcomes),
        "cap_truncated": cap_stop,
        "budget_stop": False,
        "skipped_boards": skipped,
        "requested_result_completion": "complete" if not errors and (len(records) >= data["maxJobs"] or all_matching_delivered) else "incomplete",
        "full_input_coverage": not skipped and not errors,
        "all_selected_boards_searched": not skipped and not errors,
        "all_matching_jobs_delivered": all_matching_delivered,
        "coverage": "bounded_global_cap" if cap_stop else ("partial_with_errors" if errors else "all_requested_boards"),
        "board_outcomes": outcomes,
        "errors": errors,
        "resource": {"requests": client.stats.requests, "retries": client.stats.retries, "bytes_received": client.stats.bytes_received, "elapsed_seconds": elapsed},
    }
    return {"records": records, "summary": summary, "schema": {"api": "Greenhouse Job Board API", "endpoint": f"{API_ORIGIN}/v1/boards/{{board_token}}/jobs?content=true", "content": "Descriptions are source data; HTML is preserved and plain text is derived with entity decoding.", "retrieved_at": retrieved_at}}
