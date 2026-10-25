#!/usr/bin/env python3
"""Prepare/validate metadata-only drafts; post-freeze coverage is explicitly gated."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.attacks.development_review_package import stable_json
from src.attacks.review_handoff import (
    METHOD_PATHS, build_handoff, coverage_after_freeze, render_log_header, render_sheet, validate_handoff,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "validate", "coverage-after-freeze"))
    parser.add_argument("--manifest", type=Path, default=Path("configs/exp_027_hotpotqa_heldout_manifest.json"))
    parser.add_argument("--development-artifact", type=Path,
                        default=Path("results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl"))
    parser.add_argument("--directory", type=Path, default=Path("docs/reviews/phase4c"))
    parser.add_argument("--frozen-preregistration", type=Path)
    parser.add_argument("--preregistration-sha256")
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--authorize-heldout-text", action="store_true",
                        help="Only after genuine human freeze and explicit text-access authorization.")
    args = parser.parse_args()
    if args.mode != "coverage-after-freeze" and (args.queries or args.authorize_heldout_text or
                                               args.frozen_preregistration or args.preregistration_sha256):
        parser.error("Text/freeze arguments are forbidden in metadata-only modes")
    if args.mode == "build":
        files = build_handoff(manifest_path=args.manifest, development_artifact=args.development_artifact,
                              method_paths=list(METHOD_PATHS))
        contents = {name: stable_json(value) for name, value in files.items()}
        contents["review_sheet_blank.csv"] = render_sheet(files["review_handoff.json"])
        contents["candidate_review_log_blank.csv"] = render_log_header()
        outputs = [args.directory / name for name in contents]
        if any(path.exists() for path in outputs):
            parser.error("Refusing to overwrite handoff files; use validate or a fresh directory")
        args.directory.mkdir(parents=True, exist_ok=True)
        for name, content in contents.items():
            with (args.directory / name).open("x", encoding="utf-8", newline="") as output:
                output.write(content)
        report = files["coverage_metadata_only.json"]
    elif args.mode == "validate":
        report = validate_handoff(args.directory, manifest_path=args.manifest,
                                 development_artifact=args.development_artifact, method_paths=list(METHOD_PATHS))
    else:
        if not all((args.authorize_heldout_text, args.frozen_preregistration, args.preregistration_sha256, args.queries)):
            parser.error("Coverage requires human text authorization, a genuinely frozen preregistration, external SHA pin and query input")
        report = coverage_after_freeze(preregistration_path=args.frozen_preregistration,
            preregistration_sha256=args.preregistration_sha256, queries_path=args.queries,
            pool_path=args.directory / "candidate_pool.json", manifest_path=args.manifest,
            authorized=True)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
