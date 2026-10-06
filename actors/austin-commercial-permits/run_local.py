#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
from austin_actor.core import ActorInputError, ExtractionError, run_extraction, validate_input, write_local_result

def main() -> int:
    parser=argparse.ArgumentParser(description="Run the Austin Commercial Permits beta locally without the Apify SDK.")
    parser.add_argument("--input",default="input.json",help="JSON input file")
    parser.add_argument("--output-dir",default="local_output",help="Output directory")
    args=parser.parse_args()
    try:
        data=validate_input(json.loads(Path(args.input).read_text(encoding="utf-8")))
        result=run_extraction(data); write_local_result(result,Path(args.output_dir)); print(json.dumps(result["summary"],indent=2)); return 0 if result["summary"]["completion"]=="complete" else 2
    except (ActorInputError, ExtractionError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
