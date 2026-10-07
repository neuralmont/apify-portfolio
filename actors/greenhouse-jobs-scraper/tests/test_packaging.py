import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_manifest_paths_and_schemas_are_valid():
    manifest = json.loads((ROOT / ".actor/actor.json").read_text())
    assert manifest["dockerContextDir"] == ".."
    for key in ("input", "output"):
        assert (ROOT / ".actor" / manifest[key].removeprefix("./")).exists()
    assert (ROOT / ".actor/dataset_schema.json").exists()
    assert (ROOT / "greenhouse_actor/directory.json").exists()
    assert (ROOT / "scripts/refresh_directory.py").exists()
    json.loads((ROOT / ".actor/input_schema.json").read_text())
    json.loads((ROOT / ".actor/output_schema.json").read_text())
    json.loads((ROOT / ".actor/dataset_schema.json").read_text())
    assert "apify==4.0.2" in (ROOT / "requirements.txt").read_text()
