"""Revalidate the checked-in Greenhouse directory against the public API.

This is an explicit, bounded refresh check. It never discovers or mutates
the directory; review changes to directory.json before committing them.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).parents[1]
API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true"


def main() -> int:
    directory = json.loads((ROOT / "greenhouse_actor/directory.json").read_text())
    seen = set()
    failures = []
    for company in directory["companies"]:
        token = company["board_token"]
        if token in seen:
            failures.append(f"duplicate token: {token}")
        seen.add(token)
        try:
            with urllib.request.urlopen(API.format(token), timeout=20) as response:
                payload = json.load(response)
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(jobs, list):
                failures.append(f"{token}: response has no jobs array")
            else:
                print(f"{company['company_name']}\t{token}\t{len(jobs)} jobs\t{company['source_url']}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            failures.append(f"{token}: {exc}")
    print(f"verified_entries={len(directory['companies'])} version={directory['version']}")
    if failures:
        print("failures:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
