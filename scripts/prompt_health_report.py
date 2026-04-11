#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.prompt_templates import generate_prompt_health_report, validate_prompt_health_report


def main() -> int:
    report = generate_prompt_health_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    validate_prompt_health_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
