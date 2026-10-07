import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_nested_actor_paths_and_schemas_are_present():
    manifest = json.loads((ROOT / ".actor/actor.json").read_text())
    assert manifest["dockerContextDir"] == ".."
    for key in ("dockerfile", "readme", "input", "output"):
        assert (ROOT / ".actor" / manifest[key].removeprefix("./")).exists() or (ROOT / manifest[key].removeprefix("./")).exists()
    assert json.loads((ROOT / ".actor/input_schema.json").read_text())["properties"]["maxProducts"]["maximum"] == 5000
    assert "actorOutputSchemaVersion" in json.loads((ROOT / ".actor/output_schema.json").read_text())
