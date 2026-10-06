#!/usr/bin/env python3
"""Recalculate bounded quality statistics from a saved probe observation.

Usage: python3 audit_saved.py outputs/snapshots/20261006T204519Z > audit.json
Only source IDs and short work-description evidence are emitted; contact names
are deliberately omitted from the audit artifact.
"""
import argparse, collections, json
from pathlib import Path
from probe import SOURCES, normalize

def audit_file(path, city, cohort):
    raw=[json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows=[normalize(x,SOURCES[city],"saved-observation") for x in raw]
    commercial=[x for x in rows if x["commercial_classification"]=="commercial"]
    def present(field): return sum(x.get(field) not in (None,"",[]) for x in rows)
    audits=[]
    for x in rows[:10]:
        audits.append({"source_record_id":x["source_record_id"],"classification":x["commercial_classification"],"classification_evidence":x["classification_evidence"],"address_present":bool(x["address"]),"description_present":bool(x["work_description"]),"valuation_present":x["project_valuation"] not in (None,""),"contractor_present":bool(x["contractor_names"])})
    return {"city":city,"cohort":cohort,"n":len(rows),"classification":dict(collections.Counter(x["commercial_classification"] for x in rows)),"completeness":{"address":present("address"),"description":present("work_description"),"valuation":present("project_valuation"),"contractor":present("contractor_names"),"commercial_contractor":sum(bool(x["contractor_names"]) for x in commercial),"commercial_records":len(commercial),"postal":present("postal_code"),"latitude":present("latitude"),"longitude":present("longitude"),"status":present("status_raw")},"manual_audit_first_10":audits,"conflicting_classification_records":[x["source_record_id"] for x in rows if x["classification_evidence"] and x["classification_evidence"].startswith("ambiguous conflicting")]}

def main():
    p=argparse.ArgumentParser(); p.add_argument("observation"); args=p.parse_args(); root=Path(args.observation); result={}
    for city in ("chicago","seattle","austin"):
        for path in sorted((root/city).glob("*_raw.jsonl")):
            cohort=path.stem.removesuffix("_raw"); result[f"{city}:{cohort}"]=audit_file(path,city,cohort)
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
