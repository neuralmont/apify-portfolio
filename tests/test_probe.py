import json, tempfile, unittest
from pathlib import Path
from probe import classify, normalize, compare

class ProbeTests(unittest.TestCase):
    s={"city":"X","dataset":"d","domain":"https://example.gov","id":"id","permit":"permit","date":"issue_date"}
    def test_normalization_and_nulls(self):
        r=normalize({"id":"1","permit":"A","issue_date":"2026-01-02","description":"Office fit-out","permit_type":"Commercial","contractor_company_name":"Acme LLC"},self.s,"2026-01-03T00:00:00Z")
        self.assertEqual(r["commercial_classification"],"commercial"); self.assertIsNone(r["latitude"]); self.assertEqual(r["source_record_id"],"1")
    def test_ambiguity(self): self.assertEqual(classify({"description":"New building","permit_type":""})[0],"unknown")
    def test_grouping_is_null_without_evidence(self): self.assertIsNone(normalize({"id":"1","address":"1 Main"},self.s,"now")["possible_project_group_id"])
    def test_compare_failure_safe(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"events.jsonl"; compare("fixtures/before.jsonl","fixtures/after.jsonl",str(out)); events=[json.loads(x) for x in out.read_text().splitlines()]; self.assertEqual(len(events),2); self.assertEqual({e["event_type"] for e in events},{"new","changed"})
if __name__=="__main__": unittest.main()
