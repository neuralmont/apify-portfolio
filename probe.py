#!/usr/bin/env python3
"""Bounded, failure-safe Socrata feasibility probe (Python standard library)."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, sys, tempfile, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FIELDS = ["city","source_dataset","source_record_id","permit_number","source_url","application_date","issue_date","source_updated_at","observed_at","status_raw","status_normalized","permit_type","work_description","address","postal_code","latitude","longitude","project_valuation","valuation_currency","contractor_names","commercial_classification","classification_evidence","possible_project_group_id"]

# Explicit mappings are accepted only after /api/views/{id} confirms fields.
SOURCES = {
 "chicago": {"city":"Chicago","dataset":"ydr8-5enu","domain":"https://data.cityofchicago.org","date":"issue_date","id":"id","permit":"permit_","url":"https://data.cityofchicago.org/resource/ydr8-5enu.json","mapping":{"application":"application_start_date","issue":"issue_date","status":"permit_status","type":"permit_type","description":"work_description","valuation":"reported_cost","postal":"zip_code","updated":"_updated_at","category":None,"address_parts":["street_number","street_direction","street_name","street_type","street_suffix"],"lat":"latitude","lon":"longitude","contractor_fields":[["contact_1_type","contact_1_name"],["contact_2_type","contact_2_name"],["contact_3_type","contact_3_name"],["contact_4_type","contact_4_name"],["contact_5_type","contact_5_name"],["contact_6_type","contact_6_name"],["contact_7_type","contact_7_name"],["contact_8_type","contact_8_name"],["contact_9_type","contact_9_name"],["contact_10_type","contact_10_name"]]}},
 "seattle": {"city":"Seattle","dataset":"76t5-zqzr","domain":"https://data.seattle.gov","date":"issueddate","application_date":"applieddate","id":"permitnum","permit":"permitnum","url":"https://data.seattle.gov/resource/76t5-zqzr.json","mapping":{"application":"applieddate","issue":"issueddate","status":"statuscurrent","type":"permitclassmapped","description":"description","updated":"_updated_at","category":"permitclassmapped","address":"originaladdress1","postal":"originalzip","lat":"latitude","lon":"longitude","valuation":"estprojectcost","contractor_fields":[["contractorcompanyname","contractorcompanyname"]],"verified_company_fields":["contractorcompanyname"]}},
 "austin": {"city":"Austin","dataset":"3syk-w9eu","domain":"https://data.austintexas.gov","date":"issue_date","id":"permit_number","permit":"permit_number","url":"https://data.austintexas.gov/resource/3syk-w9eu.json","mapping":{"application":"application_date","issue":"issue_date","status":"status_current","type":"permittype","description":"description","updated":"_updated_at","category":"permit_class_mapped","address":"permit_location","postal":"zip_code","lat":"latitude","lon":"longitude","valuation":"total_job_valuation","contractor_fields":[["contractor_trade","contractor_company_name"]]}}
}
class ProbeError(Exception): pass
def atom_write(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def text(v): return None if v in (None,"") else str(v)
def iso(v): return str(v)[:10] if v not in (None,"") else None
def normalize_status(v):
    if not v: return None
    s=str(v).lower()
    if any(x in s for x in ("complete","closed","final")): return "complete"
    if any(x in s for x in ("cancel","void","revok","denied","expired")): return "closed_or_negative"
    if any(x in s for x in ("issued","active","in progress","review","pending")): return "in_progress_or_issued"
    return "other"
def classify(row,s):
    m=s["mapping"]; field=m.get("category"); raw=text(row.get(field)) if field else None
    if raw:
        low=raw.lower()
        if any(x in low for x in ("commercial","non-residential","non residential")): return "commercial",f"source category {field}={raw}"
        if any(x in low for x in ("residential","single family","multifamily")): return "residential",f"source category {field}={raw}"
    desc=text(row.get(m.get("description"))) or ""; low=desc.lower()
    commercial=any(x in low for x in ("office","warehouse","retail","restaurant","tenant improvement","commercial"))
    residential=any(x in low for x in ("single family","duplex","residence","residential","dwelling","apartment","mixed use"))
    if commercial and residential: return "unknown",f"ambiguous conflicting work_description cues: commercial and residential; text={desc[:300]}"
    if commercial: return "commercial",f"heuristic work_description={desc[:300]}"
    if residential: return "residential",f"heuristic work_description={desc[:300]}"
    return "unknown",None
def address(row,s):
    m=s["mapping"]
    if m.get("address") and text(row.get(m["address"])): return text(row[m["address"]])
    return " ".join(text(row.get(x)) for x in m.get("address_parts",[]) if text(row.get(x))) or None
def contractors(row,s):
    out=[]
    for field in s["mapping"].get("verified_company_fields",[]):
        name=text(row.get(field))
        if name: out.append(name)
    for role_field,name_field in s["mapping"].get("contractor_fields",[]):
        if role_field == name_field: continue
        role=text(row.get(role_field)); name=text(row.get(name_field))
        if role and name and any(x in role.lower() for x in ("contractor","general","electrical","plumbing","mechanical")): out.append(name)
    return list(dict.fromkeys(out))
def normalize(row,s,observed):
    m=s["mapping"]; rid=text(row.get(s["id"]))
    if not rid: raise ProbeError(f"missing source ID field {s['id']}")
    cls,evidence=classify(row,s); valuation=row.get(m.get("valuation"))
    return {"city":s["city"],"source_dataset":s["dataset"],"source_record_id":rid,"permit_number":text(row.get(s["permit"])),"source_url":f"{s['domain']}/d/{s['dataset']}","application_date":iso(row.get(m.get("application"))),"issue_date":iso(row.get(m.get("issue"))),"source_updated_at":text(row.get(m.get("updated"))),"observed_at":observed,"status_raw":text(row.get(m.get("status"))),"status_normalized":normalize_status(row.get(m.get("status"))),"permit_type":text(row.get(m.get("type"))),"work_description":text(row.get(m.get("description"))),"address":address(row,s),"postal_code":text(row.get(m.get("postal"))),"latitude":row.get(m.get("lat")),"longitude":row.get(m.get("lon")),"project_valuation":valuation,"valuation_currency":"USD" if valuation not in (None,"") else None,"contractor_names":contractors(row,s),"commercial_classification":cls,"classification_evidence":evidence,"possible_project_group_id":None}
class Client:
    def __init__(self,retries=2): self.retries=retries; self.requests=0; self.retries_used=0; self.bytes=0; self.errors=[]
    def get(self,url,params=None):
        full=url+("?"+urlencode(params) if params else ""); last=None
        for attempt in range(self.retries+1):
            if attempt: self.retries_used+=1; time.sleep(min(2**attempt,4))
            self.requests+=1
            try:
                req=Request(full,headers={"User-Agent":"commercial-permit-feasibility-probe/2.0"})
                with urlopen(req,timeout=25) as r: body=r.read(); self.bytes+=len(body); return json.loads(body)
            except HTTPError as e:
                if e.code == 400:
                    detail=e.read(1200).decode("utf-8","replace")
                    last=f"HTTP 400 Bad Request: {detail}"
                    self.errors.append({"url":full,"error":last})
                    raise ProbeError(last)
                last=str(e)
            except (URLError,TimeoutError,ValueError) as e: last=str(e)
        self.errors.append({"url":full,"error":last}); raise ProbeError(last)
def validate_schema(client,s):
    meta=client.get(f"{s['domain']}/api/views/{s['dataset']}"); names={c.get("fieldName") for c in meta.get("columns",[])}; m=s["mapping"]
    required=[s["id"],s["permit"],s["date"],m.get("status"),m.get("type"),m.get("description")]; missing=[x for x in required if x and x not in names]
    if missing: raise ProbeError(f"schema missing explicit fields: {missing}")
    optional=[]
    candidates=[m.get(x) for x in ("application","issue","updated","valuation","postal","address","lat","lon")]
    candidates += m.get("address_parts",[])
    candidates += [x for pair in m.get("contractor_fields",[]) for x in pair if x]
    candidates += m.get("verified_company_fields",[])
    for field in dict.fromkeys(x for x in candidates if x):
        if field not in names: optional.append(field)
    s["schema_fields"]=sorted(x for x in names if x); s["schema_metadata_url"]=f"{s['domain']}/api/views/{s['dataset']}"; s["optional_mappings_absent"]=optional; return meta
def query_city(client,s,since,until,limit,cohort):
    field=s["mapping"]["issue"] if cohort=="issued" else s["mapping"].get("application")
    if not field: raise ProbeError(f"no verified application field for {s['city']}")
    where=f"{field} between '{since}T00:00:00' and '{until}T23:59:59'"; order=f"{field} DESC, {s['id']} ASC"
    rows=client.get(s["url"],{"$where":where,"$order":order,"$limit":min(100,limit)}); count=client.get(s["url"],{"$select":"count(*) as n","$where":where})
    return rows,int(count[0]["n"]) if count else 0,where,order
def identity(row):
    ds=row.get("source_dataset"); rid=row.get("source_record_id")
    if not ds or not rid: raise ProbeError("missing source-scoped identity")
    return str(ds),str(rid),str(row.get("cohort") or "")
def load_rows(path):
    out={}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row=json.loads(line); key=identity(row)
        if key in out: raise ProbeError(f"duplicate identity: {key}")
        out[key]=row
    return out
def event(kind,key,row,changes=None):
    body={"event_type":kind,"source_dataset":key[0],"source_record_id":key[1],"cohort":key[2],"changes":changes or {},"record":row if kind=="new" else None}; digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]; body["event_id"]=f"{kind}:{key[0]}:{key[1]}:{key[2]}:{digest}"; return body
def compare(old,new,out,old_manifest=None,new_manifest=None):
    if old_manifest and new_manifest:
        a_meta=json.loads(Path(old_manifest).read_text(encoding="utf-8")); b_meta=json.loads(Path(new_manifest).read_text(encoding="utf-8"))
        for key in ("window","configuration"):
            if a_meta.get(key)!=b_meta.get(key): raise ProbeError(f"incompatible observations: {key} differs")
    a,b=load_rows(old),load_rows(new); events=[]
    for k in sorted(set(b)-set(a)): events.append(event("new",k,b[k]))
    for k in sorted(set(a)&set(b)):
        changes={f:{"old":a[k].get(f),"new":b[k].get(f)} for f in ("status_raw","project_valuation","work_description","contractor_names") if a[k].get(f)!=b[k].get(f)}
        if changes: events.append(event("changed",k,b[k],changes))
    atom_write(out,"".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in events)); return events
def csv_text(rows):
    import io; out=io.StringIO(); w=csv.DictWriter(out,fieldnames=FIELDS); w.writeheader()
    for r in rows: w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(list,dict)) else r[k] for k in FIELDS})
    return out.getvalue()
def run_live(args):
    observed=datetime.now(timezone.utc); end=date.fromisoformat(args.until) if args.until else observed.date(); start=date.fromisoformat(args.since) if args.since else end-timedelta(days=30)
    if start>end: raise ProbeError("since must not be after until")
    c=Client(args.retries); stamp=observed.strftime("%Y%m%dT%H%M%SZ"); root=Path(args.out).parent; snap=root/"snapshots"/stamp; baseline=root/"baselines"; previous=root/"previous"; rows=[]; manifest={"observed_at":observed.isoformat(),"window":{"since":str(start),"until":str(end),"timezone":"UTC","semantics":"inclusive whole UTC dates"},"configuration":{"cities":list(args.cities),"limit":min(100,args.limit),"seattle_application_sample":bool(args.seattle_in_progress)},"cities":{},"cohorts":{},"resource":{}}
    for name in args.cities:
        s=SOURCES[name]; t=time.monotonic(); city_rows=[]; status={"status":"failed","records_returned":0,"errors":[]}
        try:
            validate_schema(c,s); cohorts=["issued","application_date_sample"] if name=="seattle" and args.seattle_in_progress else ["issued"]
            for cohort in cohorts:
                try: raw,n,where,order=query_city(c,s,start,end,args.limit,cohort)
                except Exception as e:
                    manifest["cohorts"][f"{name}:{cohort}"]={"status":"failed","records_returned":0,"full_window_count":None,"errors":[str(e)]}
                    continue
                normalized=[normalize(x,s,observed.isoformat()) for x in raw]
                for x in normalized: x["cohort"]=cohort
                cohort_keys=[identity(x) for x in normalized]
                if len(cohort_keys)!=len(set(cohort_keys)): raise ProbeError(f"duplicate identity within cohort: {cohort}")
                atom_write(snap/name/f"{cohort}_raw.jsonl","".join(json.dumps(x,ensure_ascii=False)+"\n" for x in raw)); manifest["cohorts"][f"{name}:{cohort}"]={"status":"success" if normalized else "verified_empty","records_returned":len(normalized),"full_window_count":n,"where":where,"order":order}
                city_rows += normalized
            successful=[manifest["cohorts"].get(f"{name}:{x}",{}).get("status") in ("success","verified_empty") for x in cohorts]
            status["records_returned"]=len(city_rows); status["status"]=("success" if all(successful) and city_rows else "verified_empty" if all(successful) and not city_rows else "partial" if any(successful) else "failed")
            city_dir=snap/name; atom_write(city_dir/"normalized.jsonl","".join(json.dumps(x,ensure_ascii=False)+"\n" for x in city_rows)); atom_write(city_dir/"normalized.csv",csv_text(city_rows))
            old=baseline/f"{name}.jsonl"; prev=previous/f"{name}.jsonl"; manifest["cities"][name]={"status":status["status"],"records_returned":status["records_returned"],"errors":[],"previous_baseline":str(prev) if old.exists() else None,"current_snapshot":str(city_dir/"normalized.jsonl"),"optional_mappings_absent":s.get("optional_mappings_absent",[])}
            if old.exists(): atom_write(prev,old.read_text(encoding="utf-8"))
            if status["status"] in ("success","verified_empty"): atom_write(old,"".join(json.dumps(x,ensure_ascii=False)+"\n" for x in city_rows))
            rows += city_rows
        except Exception as e: status["errors"]=[str(e)]
        status["elapsed_seconds"]=round(time.monotonic()-t,3)
        if name not in manifest["cities"]: manifest["cities"][name]=status
    manifest["resource"]={"requests":c.requests,"retries":c.retries_used,"bytes_received":c.bytes,"errors":c.errors}; manifest["complete"]=all(x["status"] in ("success","verified_empty") for x in manifest["cities"].values())
    atom_write(args.out,csv_text(rows)); atom_write(Path(args.out).with_suffix(".jsonl"),"".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows)); manifest["aggregate_status"]="complete" if manifest["complete"] else "incomplete"
    atom_write(snap/"manifest.json",json.dumps(manifest,indent=2)+"\n"); atom_write(root/"run_metrics.json",json.dumps(manifest,indent=2)+"\n"); print(json.dumps(manifest,indent=2)); return 0 if manifest["complete"] else 2
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True); l=sub.add_parser("live"); l.add_argument("--cities",nargs="+",choices=SOURCES,default=list(SOURCES)); l.add_argument("--limit",type=int,default=100); l.add_argument("--retries",type=int,default=2); l.add_argument("--since"); l.add_argument("--until"); l.add_argument("--seattle-in-progress",action="store_true",help="also collect a separate application_date_sample; not an in-progress predicate"); l.add_argument("--out",default="outputs/live.csv"); l.set_defaults(func=run_live); c=sub.add_parser("compare"); c.add_argument("old"); c.add_argument("new"); c.add_argument("--out",default="outputs/events.jsonl"); c.add_argument("--old-manifest"); c.add_argument("--new-manifest"); c.set_defaults(func=lambda a:(print(json.dumps({"events":len(compare(a.old,a.new,a.out,a.old_manifest,a.new_manifest)),"output":a.out},indent=2)) or 0)); a=p.parse_args()
    try: raise SystemExit(a.func(a))
    except ProbeError as e: print(f"error: {e}",file=sys.stderr); raise SystemExit(2)
if __name__=="__main__": main()
