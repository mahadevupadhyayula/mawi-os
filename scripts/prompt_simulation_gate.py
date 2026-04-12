#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prompt_health_report import main as prompt_health_main


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_prompt_simulation_regression")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    return prompt_health_main()


if __name__ == "__main__":
    raise SystemExit(main())
