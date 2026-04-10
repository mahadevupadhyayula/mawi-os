from __future__ import annotations

import logging


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("workflow")


def log_stage(stage: str, deal_id: str, run_id: str) -> None:
    logger.info("stage=%s deal_id=%s run_id=%s", stage, deal_id, run_id)
