#!/usr/bin/env python3
"""Bounded Socrata feasibility probe for commercial construction permits.

Uses only the Python standard library.  The live command makes at most two
requests per city (one sample and one count/completeness query) plus bounded
metadata/schema requests.  Source mappings are explicit but tolerate the
minor field-name differences between the three portals.
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
FIELDS = ["city","source_dataset","source_record_id","permit_number","source_url","application_date","issue_date","source_updated_at","observed_at","status_raw","status_normalized","permit_type","work_description","address","postal_code","latitude","longitude","project_valuation","valuation_currency","contractor_names","commercial_classification","classification_evidence","possible_project_group_id"]

SOURCES = {
 "chicago": dict(city="Chicago", dataset="ydr8-5enu", domain="https://data.cityofchicago.org", date="issue_date", id="id", permit="permit_", url="https://data.cityofchicago.org/resource/ydr8-5enu.json"),
 "seattle": dict(city="Seattle", dataset="76t5-zqzr", domain="https://data.seattle.gov", date="issueddate", id="permitnum", permit="permitnum", url="https://data.seattle.gov/resource/76t5-zqzr.json"),
 "austin": dict(city="Austin", dataset="3syk-w9eu", domain="https://data.austintexas.gov", date="issue_date", id="permit_number", permit="permit_number", url="https://data.austintexas.gov/resource/3syk-w9eu.json"),
}

ALIASES = {
 "id":["id","permitnum","permit_number","permit"], "permit":["permit_","permitnum","permit_number","permit"],
 "application":["application_start_date","applicationdate","application_date","applieddate","application_date"],
 "issue":["issue_date","issueddate","issued_date"], "updated":["_updated_at","updated_at","lastupdateddate","last_updated"],
 "status":["permit_status","statuscurrent","status","status_current"], "type":["permit_type","permitclassmapped","permitclass","permit_type_desc","permittypedesc"],
 "description":["work_description","description","projectdescription","workdescription"],
 "address":["street_address","originaladdress1","address","project_address","address1"], "postal":["zip_code","originalzip","zip","zipcode"],
 "valuation":["reported_cost","valuation","total_job_valuation","estprojectcost","total_valuation","project_valuation"],
 "contractor":["contractor_company_name","contractor_name","contractorname","contractor_full_name","contractor"],
 "lat":["latitude","lat"], "lon":["longitude","lon","lng"], "location":["location"],
}

def val(row, key, explicit=None):
    for k in ([explicit] if explicit else []) + ALIASES.get(key, []):
        if k and k in row and row[k] not in (None, ""):
            return row[k]
    return None

def iso_date(v):
    if not v: return None
    return str(v)[:10]

def parse_location(v):
    if isinstance(v, dict):
        p = v.get("coordinates") or []
        if len(p) >= 2: return p[1], p[0]
        return v.get("latitude"), v.get("longitude")
    return None, None

def classify(row):
    # Official categories take precedence. Text is explicitly heuristic.
    category = " ".join(str(val(row,k) or "") for k in ("type",)) .lower()
    if any(x in category for x in ("commercial", "non-residential", "non residential")): return "commercial", "source category: " + str(val(row,"type"))
    if "residential" in category or "single family" in category or "multifamily" in category: return "residential", "source category: " + str(val(row,"type"))
    text = " ".join(str(val(row,k) or "") for k in ("description","address")).lower()
    if any(x in text for x in ("office", "warehouse", "retail", "restaurant", "tenant improvement", "commercial")): return "commercial", "heuristic text match: " + text[:300]
    if any(x in text for x in ("single family", "duplex", "residence", "residential")): return "residential", "heuristic text match: " + text[:300]
    return "unknown", None

def normalize(row, source, observed):
    lat, lon = parse_location(val(row,"location"))
    lat = val(row,"lat") or lat; lon = val(row,"lon") or lon
    classification, evidence = classify(row)
    rid = val(row,"id",source["id"]) or val(row,"permit",source["permit"])
    return {"city":source["city"],"source_dataset":source["dataset"],"source_record_id":rid,"permit_number":val(row,"permit",source["permit"]),"source_url":f"{source['domain']}/d/{source['dataset']}","application_date":iso_date(val(row,"application")),"issue_date":iso_date(val(row,"issue",source["date"])),"source_updated_at":val(row,"updated"),"observed_at":observed,"status_raw":val(row,"status"),"status_normalized":normalize_status(val(row,"status")),"permit_type":val(row,"type"),"work_description":val(row,"description"),"address":val(row,"address"),"postal_code":val(row,"postal"),"latitude":lat,"longitude":lon,"project_valuation":val(row,"valuation"),"valuation_currency":"USD" if val(row,"valuation") is not None else None,"contractor_names":[val(row,"contractor")] if val(row,"contractor") else [],"commercial_classification":classification,"classification_evidence":evidence,"possible_project_group_id":None}

def normalize_status(v):
    if not v: return None
    s = str(v).lower()
    if any(x in s for x in ("complete","closed","final")): return "complete"
    if any(x in s for x in ("cancel","void","revok","denied","expired")): return "closed_or_negative"
    if any(x in s for x in ("issued","active","in progress","review","pending")): return "in_progress_or_issued"
    return "other"

class Client:
    def __init__(self, retries=2): self.retries=retries; self.requests=0; self.retries_used=0; self.bytes=0; self.errors=[]
    def get(self, url, params):
        full=url+"?"+urlencode(params); last=None
        for attempt in range(self.retries+1):
            if attempt: self.retries_used+=1; time.sleep(min(2**attempt,4))
            self.requests+=1
            try:
                req=Request(full,headers={"User-Agent":"commercial-permit-feasibility-probe/1.0"})
                with urlopen(req,timeout=25) as r:
                    body=r.read(); self.bytes+=len(body); return json.loads(body)
            except (HTTPError,URLError,TimeoutError,ValueError) as e: last=str(e)
        self.errors.append({"url":full,"error":last}); raise RuntimeError(last)

def query_city(client, source, since, until, limit):
    where=f"{source['date']} between '{since}T00:00:00' and '{until}T23:59:59'"
    order=f"{source['date']} DESC, {source['id']} ASC"
    sample=client.get(source["url"],{"$where":where,"$order":order,"$limit":min(limit,100)})
    count=client.get(source["url"],{"$select":"count(*) as n","$where":where})
    return sample, int(count[0]["n"]) if count else 0, where, order

def write_rows(rows, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for r in rows: w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(list,dict)) else r[k] for k in FIELDS})
    with path.with_suffix(".jsonl").open("w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")

def live(args):
    until=datetime.now(timezone.utc).date(); since=until-timedelta(days=30); observed=datetime.now(timezone.utc).isoformat()
    client=Client(args.retries); allrows=[]; meta={"observed_at":observed,"window":{"since":str(since),"until":str(until)},"cities":{},"resource":{"requests":0,"retries":0,"bytes_received":0,"errors":[]}}
    for name in args.cities:
        s=SOURCES[name]; start=time.monotonic()
        try:
            raw,n,where,order=query_city(client,s,since,until,args.limit)
            rows=[normalize(x,s,observed) for x in raw]; allrows+=rows
            meta["cities"][name]={"records_returned":len(rows),"full_window_count":n,"sample_completeness":{k:sum(r.get(k) not in (None,[],"") for r in rows)/len(rows) if rows else 0 for k in FIELDS},"where":where,"order":order,"elapsed_seconds":round(time.monotonic()-start,3),"errors":[]}
        except Exception as e:
            meta["cities"][name]={"records_returned":0,"full_window_count":None,"errors":[str(e)],"elapsed_seconds":round(time.monotonic()-start,3)}
    meta["resource"]={"requests":client.requests,"retries":client.retries_used,"bytes_received":client.bytes,"errors":client.errors}
    output_path=Path(args.out)
    failed_cities=sum(bool(x.get("errors")) for x in meta["cities"].values())
    if not allrows and failed_cities == len(args.cities) and output_path.exists():
        meta["snapshot_write"]="skipped: every city failed; existing output preserved"
    else:
        write_rows(allrows,output_path); meta["snapshot_write"]="written"
    output_path.with_name("run_metrics.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))

def compare(old,new,out):
    def load(p):
        return {str(x.get("source_record_id")):x for x in (json.loads(l) for l in Path(p).read_text().splitlines() if l.strip())}
    a,b=load(old),load(new); events=[]
    for k in sorted(set(b)-set(a)): events.append(event("new",b[k]))
    for k in sorted(set(a)&set(b)):
        changes={f:{"old":a[k].get(f),"new":b[k].get(f)} for f in ("status_raw","project_valuation","work_description","contractor_names") if a[k].get(f)!=b[k].get(f)}
        if changes: events.append({"event_id":f"changed:{b[k]['source_dataset']}:{k}","event_type":"changed","source_record_id":k,"changes":changes})
    Path(out).write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in events)); print(json.dumps({"new":sum(x["event_type"]=="new" for x in events),"changed":sum(x["event_type"]=="changed" for x in events),"output":out},indent=2))

def event(kind,row): return {"event_id":f"{kind}:{row['source_dataset']}:{row['source_record_id']}","event_type":kind,"source_record_id":row["source_record_id"],"record":row}

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    l=sub.add_parser("live"); l.add_argument("--cities",nargs="+",choices=SOURCES,default=list(SOURCES)); l.add_argument("--limit",type=int,default=100); l.add_argument("--retries",type=int,default=2); l.add_argument("--out",default="outputs/live.csv"); l.set_defaults(func=live)
    c=sub.add_parser("compare"); c.add_argument("old"); c.add_argument("new"); c.add_argument("--out",default="outputs/events.jsonl"); c.set_defaults(func=lambda a:compare(a.old,a.new,a.out))
    a=p.parse_args(); a.func(a)
if __name__=="__main__": main()
