import json, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
from pathlib import Path
import probe
from probe import SOURCES, ProbeError, compare, identity, load_rows, normalize

class ProbeTests(unittest.TestCase):
    def test_explicit_normalization_and_no_address_inference(self):
        s=SOURCES["austin"]
        row={"permit_number":"A-1","permit_location":"Office address","permit_type":"Building","description":"New building","est_project_cost":"100"}
        out=normalize(row,s,"2026-10-06T00:00:00Z")
        self.assertEqual(out["source_record_id"],"A-1"); self.assertEqual(out["commercial_classification"],"unknown")

    def test_seattle_company_field_is_contractor_evidence(self):
        s=SOURCES["seattle"]
        row={"permitnum":"S-1","permitclassmapped":"Commercial","description":"New building","contractorcompanyname":"Acme Builders LLC"}
        out=normalize(row,s,"2026-10-06T00:00:00Z")
        self.assertEqual(out["contractor_names"],["Acme Builders LLC"])

    def test_real_source_shaped_chicago_and_austin_fields(self):
        chicago=normalize({"id":"C-1","permit_":"P-1","permit_type":"PERMIT - RENOVATION/ALTERATION","work_description":"Commercial tenant buildout","street_number":"10","street_direction":"W","street_name":"MAIN ST","contact_1_type":"OWNER","contact_1_name":"Owner LLC","contact_2_type":"CONTRACTOR-GENERAL CONTRACTOR","contact_2_name":"Build Co LLC","reported_cost":"87000"},SOURCES["chicago"],"2026-10-06T00:00:00Z")
        self.assertEqual(chicago["address"],"10 W MAIN ST"); self.assertEqual(chicago["contractor_names"],["Build Co LLC"])
        austin=normalize({"permit_number":"A-1","permittype":"BP","permit_class_mapped":"Commercial","permit_location":"10 MAIN ST","description":"Office fit-out","total_job_valuation":"250000","status_current":"Active","contractor_trade":"General Contractor","contractor_company_name":"Austin Build LLC"},SOURCES["austin"],"2026-10-06T00:00:00Z")
        self.assertEqual(austin["commercial_classification"],"commercial"); self.assertEqual(austin["project_valuation"],"250000"); self.assertEqual(austin["contractor_names"],["Austin Build LLC"])

    def test_http_400_captures_body_without_retry(self):
        client=probe.Client(retries=2)
        err=HTTPError("https://example.test",400,"bad query",{},BytesIO(b"invalid field applicationdate"))
        with patch.object(probe,"urlopen",side_effect=err):
            with self.assertRaises(ProbeError) as caught: client.get("https://example.test")
        self.assertEqual(client.retries_used,0); self.assertIn("invalid field applicationdate",str(caught.exception))

    def test_source_scoped_identity_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"rows.jsonl"; p.write_text('\n'.join([
                json.dumps({"source_dataset":"ydr8-5enu","source_record_id":"1","status_raw":"A"}),
                json.dumps({"source_dataset":"76t5-zqzr","source_record_id":"1","status_raw":"B"})]))
            self.assertEqual(len(load_rows(p)),2)
            p.write_text(p.read_text()+"\n"+json.dumps({"source_dataset":"76t5-zqzr","source_record_id":"1","status_raw":"C"}))
            with self.assertRaises(ProbeError): load_rows(p)

    def test_partial_failure_does_not_change_baseline_logic(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/"old.jsonl"; new=Path(d)/"new.jsonl"; out=Path(d)/"events.jsonl"
            old.write_text(json.dumps({"source_dataset":"d","source_record_id":"1","status_raw":"A"})+"\n")
            new.write_text(json.dumps({"source_dataset":"d","source_record_id":"1","status_raw":"B"})+"\n")
            compare(old,new,out); self.assertEqual(len(out.read_text().splitlines()),1)
            self.assertEqual(load_rows(old)[("d","1","")]["status_raw"],"A")

    def test_verified_empty_is_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"empty.jsonl"; p.write_text(""); self.assertEqual(load_rows(p),{})

    def test_event_ids_distinguish_transitions_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/"old.jsonl"; mid=Path(d)/"mid.jsonl"; new=Path(d)/"new.jsonl"
            for p,status in ((old,"A"),(mid,"B"),(new,"C")): p.write_text(json.dumps({"source_dataset":"d","source_record_id":"1","status_raw":status})+"\n")
            e1=Path(d)/"e1"; e2=Path(d)/"e2"; e3=Path(d)/"e3"; compare(old,mid,e1); compare(mid,new,e2); compare(old,mid,e3)
            id1=json.loads(e1.read_text())["event_id"]; id2=json.loads(e2.read_text())["event_id"]; id3=json.loads(e3.read_text())["event_id"]
            self.assertNotEqual(id1,id2); self.assertEqual(id1,id3)

    def test_missing_id_rejected(self):
        with self.assertRaises(ProbeError): identity({"source_dataset":"x"})

    def test_overlapping_cohorts_are_distinct_but_duplicate_within_cohort_rejected(self):
        issued={"source_dataset":"76t5-zqzr","source_record_id":"606-1","cohort":"issued"}
        application={"source_dataset":"76t5-zqzr","source_record_id":"606-1","cohort":"application_date_sample"}
        self.assertNotEqual(identity(issued),identity(application))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"cohort.jsonl"; p.write_text(json.dumps(issued)+"\n"+json.dumps(issued)+"\n")
            with self.assertRaises(ProbeError): load_rows(p)

    def test_partial_and_all_city_failure_exit_without_advancing_baselines(self):
        class FakeClient:
            def __init__(self, retries=2): self.requests=0; self.retries_used=0; self.bytes=0; self.errors=[]
            def get(self, url, params=None):
                self.requests += 1
                for name, source in SOURCES.items():
                    if source["domain"] in url:
                        if "api/views" in url and name == "seattle": raise ProbeError("simulated Seattle failure")
                        if "api/views" in url:
                            m=source["mapping"]; fields={source["id"],source["permit"],source["date"],m["status"],m["type"],m["description"]}
                            return {"columns":[{"fieldName":x} for x in fields]}
                        if params and "$select" in params: return [{"n":"0"}]
                        return []
                raise AssertionError(url)
        with tempfile.TemporaryDirectory() as d, patch.object(probe,"Client",FakeClient):
            out=Path(d)/"live.csv"; baseline=Path(d)/"baselines"/"seattle.jsonl"; baseline.parent.mkdir(); baseline.write_text('{"source_dataset":"76t5-zqzr","source_record_id":"old"}\n')
            args=SimpleNamespace(cities=["chicago","seattle"],limit=100,retries=2,since="2026-09-01",until="2026-09-02",seattle_in_progress=False,out=str(out))
            self.assertEqual(probe.run_live(args),2); self.assertIn("old", baseline.read_text())
            # An all-city failure retains the already-created Chicago baseline.
            class AlwaysFail(FakeClient):
                def get(self, url, params=None): raise ProbeError("offline")
            with patch.object(probe,"Client",AlwaysFail):
                self.assertEqual(probe.run_live(args),2); self.assertIn("old", baseline.read_text())

    def test_successful_empty_retrieval_advances_empty_baseline(self):
        class EmptyClient:
            def __init__(self, retries=2): self.requests=0; self.retries_used=0; self.bytes=0; self.errors=[]
            def get(self, url, params=None):
                source=next(s for s in SOURCES.values() if s["domain"] in url); self.requests+=1
                if "api/views" in url:
                    m=source["mapping"]; return {"columns":[{"fieldName":x} for x in {source["id"],source["permit"],source["date"],m["status"],m["type"],m["description"]}]}
                return [{"n":"0"}] if params and "$select" in params else []
        with tempfile.TemporaryDirectory() as d, patch.object(probe,"Client",EmptyClient):
            args=SimpleNamespace(cities=["chicago"],limit=100,retries=2,since="2026-09-01",until="2026-09-02",seattle_in_progress=False,out=str(Path(d)/"live.csv"))
            self.assertEqual(probe.run_live(args),0); self.assertTrue((Path(d)/"baselines"/"chicago.jsonl").exists()); self.assertEqual((Path(d)/"baselines"/"chicago.jsonl").read_text(),"")

if __name__=="__main__": unittest.main()
