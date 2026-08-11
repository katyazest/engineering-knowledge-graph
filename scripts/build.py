"""Run the Engineering KG MVP bootstrap pipeline."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.pipeline import run_pipeline


def main() -> int:
    parser = ArgumentParser(description="Run the Engineering KG MVP pipeline.")
    parser.add_argument(
        "registry_path",
        nargs="?",
        help="Optional local repo-index.yaml workspace registry path.",
    )
    parser.add_argument(
        "--persistence-path",
        help="Optional local LadybugDB persistence output path.",
    )
    parser.add_argument(
        "--openspec-store-id",
        help="Optional explicit registered OpenSpec store id for store source validation.",
    )
    args = parser.parse_args()

    result = run_pipeline(
        args.registry_path,
        persistence_path=args.persistence_path,
        openspec_store_id=args.openspec_store_id,
    )
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
